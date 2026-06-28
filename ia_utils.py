# ia_utils.py
"""Utility helpers for the IA decision engine.

- Load the declarative configuration (`ia_params.json`).
- Build prompts dynamically from the list of technical fields.
- Check Gemini quota (if enabled).
- Manage batch processing and state‑backup.
"""

import json
import os
from pathlib import Path
from datetime import datetime
import time
import pandas as pd
import config
from google import genai
import procesamiento
import logging_config

logger = logging_config.get_logger(__name__)

# ----------------------------------------------------------------------
# 1️⃣ Load configuration -------------------------------------------------
# ----------------------------------------------------------------------
CONFIG_PATH = Path(__file__).parent / "ia_params.json"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CFG = json.load(f)

INSTRUCCIONES = CFG["instrucciones_fijas"]
CAMPO_TECNICO = CFG["campos_tecnicos"]
CAMPO_USUARIO = CFG["campos_usuario"]
MODELO_PREF = CFG["modelo_preferido"]
TEMPERATURA = CFG.get("temperatura", 0.7)
TOP_P = CFG.get("top_p", 0.95)
MAX_TOKENS = CFG.get("max_tokens", 1024)
CHEQUEAR_CUOTA = CFG.get("chequeo_cuota", True)
LOTE_MAXIMO = CFG.get("lote_maximo", 5)


def crear_prompt(ticker_row, perfiles, instrucciones, noticias_contexto=None, financiero_contexto=None):
    """Construye un payload JSON con los datos técnicos y las instrucciones para la IA."""
    payload = {
        "_ORIGEN_DE_DATOS": {
            "instrucciones_maestras": "Constante (Cargada desde ia_params.json)",
            "contexto_activo": "Tabla Google Sheets: ANALISIS_TECNICO",
            "indicadores_tecnicos": f"Tabla Google Sheets: ANALISIS_TECNICO (Campos: {', '.join(CAMPO_TECNICO)})",
            "perfiles_a_evaluar": "Tabla Google Sheets: CONFIG_IA_USUARIO",
            "configuracion_vuelo": {
                "temperatura": TEMPERATURA,
                "top_p": TOP_P,
                "max_tokens": MAX_TOKENS
            }
        },
        "instrucciones_maestras": instrucciones,
        "contexto_activo": {
            "ticker": ticker_row.get('TICKER_ID'),
            "fecha_datos": ticker_row.get('FECHA')
        },
        "indicadores_tecnicos": {campo: ticker_row.get(campo, '') for campo in CAMPO_TECNICO},
        "perfiles_a_evaluar": perfiles,
        "contexto_noticias": noticias_contexto if noticias_contexto else {},
        "contexto_financiero": financiero_contexto if financiero_contexto else {}
    }
    return json.dumps(payload, indent=4, ensure_ascii=False)

# Variable de caché global para la sesión de noticias
_CACHE_NOTICIAS = None

def obtener_noticias_recientes(sh, ticker, limite=5):
    """
    Extrae las noticias más recientes para el ticker y el contexto macro (9999) 
    desde la hoja NOTICIAS_SISTEMA. Utiliza caché en memoria para no saturar la API.
    """
    global _CACHE_NOTICIAS
    try:
        if _CACHE_NOTICIAS is None:
            logger.info(f"Descargando noticias desde {config.WS_NOTICIAS_SISTEMA}...")
            ws_noticias = sh.worksheet(config.WS_NOTICIAS_SISTEMA)
            _CACHE_NOTICIAS = ws_noticias.get_all_records()
            
        data = _CACHE_NOTICIAS
        if not data:
            logger.info(f"No hay noticias registradas en {config.WS_NOTICIAS_SISTEMA}.")
            return {"especificas": [], "macro": []}

        df = pd.DataFrame(data)
        df['TICKER_ID'] = df['TICKER_ID'].astype(str).str.upper()
        # Aseguramos orden cronológico para que tail() traiga lo último de verdad
        df['FECHA'] = pd.to_datetime(df['FECHA'], errors='coerce')
        df = df.sort_values('FECHA')
        
        # 1. Noticias específicas del activo
        df_ticker = df[df['TICKER_ID'] == str(ticker).upper()].tail(limite).copy()
        df_ticker['FECHA'] = df_ticker['FECHA'].dt.strftime('%Y-%m-%d %H:%M:%S')
        especificas = df_ticker[['FECHA', 'TITULAR', 'RESUMEN_IA', 'SENTIMIENTO', 'FUENTE']].to_dict('records')

        # 2. Noticias Macro (Buscamos 9999 y también MERVAL/BYMA como contexto local)
        filtro_macro = df['TICKER_ID'].str.startswith('9999') | df['TICKER_ID'].isin(['MERVAL', 'BYMA', 'SPY', 'NASDAQ'])
        df_macro = df[filtro_macro].tail(limite).copy()
        df_macro['FECHA'] = df_macro['FECHA'].dt.strftime('%Y-%m-%d %H:%M:%S')
        macro = df_macro[['FECHA', 'TITULAR', 'RESUMEN_IA', 'SENTIMIENTO', 'FUENTE']].to_dict('records')

        logger.info(f"Contexto recuperado: {len(especificas)} específicas, {len(macro)} macro.")

        return {
            "especificas": especificas,
            "macro": macro
        }
    except Exception as e:
        logger.exception(f"Error recuperando noticias para el prompt: {e}")
        return {"especificas": [], "macro": []}

def validar_datos_tecnicos(ticker_row):
    """
    Realiza un chequeo de cordura financiera sobre los datos antes de enviarlos a la IA.
    Retorna (True, "") si los datos son aptos, (False, "razón") si detecta anomalías.
    """
    return procesamiento.validar_datos_tecnicos(ticker_row)

def obtener_config_generacion():
    """Retorna el objeto de configuración para la generación de contenido."""
    return {
        "temperature": TEMPERATURA,
        "top_p": TOP_P,
        "max_output_tokens": MAX_TOKENS,
        "response_mime_type": "text/plain"
    }


def obtener_modelos_activos():
    """Return ordered list of candidate models, starting with the preferred one."""
    # 1. Intentar cargar el descubrimiento dinámico del Paso 0 (Health Check)
    try:
        path_activos = Path(__file__).parent / "modelos_activos.json"
        if path_activos.exists():
            with open(path_activos, "r", encoding="utf-8") as f:
                descubiertos = json.load(f)
                if descubiertos:
                    return descubiertos
    except:
        pass

    # 2. Fallback: lista estática si el Health Check no se ejecutó o falló (sin prefijo models/)
    pref_clean = MODELO_PREF.replace("models/", "") if MODELO_PREF else None
    candidatos = [pref_clean, "gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]
    
    vistos = set()
    ordenados = []
    for c in candidatos:
        if c and c.strip():
            c_clean = c.strip().replace("models/", "")
            if c_clean not in vistos:
                vistos.add(c_clean)
                ordenados.append(c_clean)
    return ordenados


def chequear_cuota(client):
    """Return True if the free‑tier quota still has capacity, False otherwise."""
    try:
        quota = client.models.get_quota()
        return quota.get("total_tokens", 0) > 0
    except Exception:
        return False


def guardar_backup(df, backup_dir):
    """Persist a CSV snapshot of the pending tickets before processing."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"pendientes_{ts}.csv"
    df.to_csv(backup_path, index=False)
    return backup_path
