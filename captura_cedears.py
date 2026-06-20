# --------------------------------------------------------------
# captura_cedears.py
# --------------------------------------------------------------
"""
Módulo de captura y sincronización de los programas vigentes de CEDEARs.
Consulta la API JSON de Banco Comafi para obtener tickers, nombres,
códigos ISIN y ratios oficiales de conversión, y los almacena en
la hoja PROGRAMA_CEDEARS.
"""

import os
import time
import requests
import urllib3
import pandas as pd
from datetime import datetime
import config
import auth_google
import procesamiento
import logging_config

# Deshabilitar alertas SSL por seguridad en entornos locales
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging_config.get_logger(__name__)

# Diccionario de equivalencias para tickers locales que difieren en el subyacente internacional
EXCEPCIONES_TICKERS = {
    "BRKB": "BRK-B",
    "BFB": "BF-B",
    "RDSB": "SHEL", # Shell renombró RDS.B a SHEL
    "RDSA": "SHEL",
}

def normalizar_ratio(ratio_str):
    """
    Normaliza y limpia el formato del ratio (ej. ' 20 : 1 ' -> '20:1').
    """
    if not ratio_str:
        return "1:1"
    parts = [p.strip() for p in str(ratio_str).split(':')]
    if len(parts) == 2:
        return f"{parts[0]}:{parts[1]}"
    return str(ratio_str).strip()

def obtener_ticker_subyacente(ticker_local):
    """
    Determina el ticker internacional subyacente para un ticker local de Byma.
    """
    t_clean = str(ticker_local).strip().upper()
    return EXCEPCIONES_TICKERS.get(t_clean, t_clean)

def ejecutar_captura_cedears():
    print("[*] Iniciando proceso de captura de CEDEARs Comafi...")
    logger.info("\n" + "="*60)
    logger.info(f"CAPTURA CEDEARS COMAFI | {datetime.now().strftime('%H:%M:%S')}")
    logger.info("="*60)
    t_inicio = time.time()
    
    sh = auth_google.conectar()
    if not sh:
        logger.error("No se pudo conectar a Google Sheets.")
        print("[🔴 ERROR] Conexión a Google Sheets falló.")
        return False
        
    ws_log = sh.worksheet(config.WS_LOG_SISTEMA)
    ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)
    
    procesamiento.registrar_log(ws_log, "INFO", "Iniciando captura de programas de CEDEARs", "captura_cedears")
    procesamiento.actualizar_estado_proceso(ws_status, "PROCESANDO", "Consultando API de Comafi...")

    try:
        # 1. Asegurar la existencia de la hoja PROGRAMA_CEDEARS
        try:
            ws_cedears = sh.worksheet(config.WS_PROGRAMA_CEDEARS)
        except Exception:
            logger.info(f"Hoja '{config.WS_PROGRAMA_CEDEARS}' no encontrada. Creándola...")
            ws_cedears = sh.add_worksheet(title=config.WS_PROGRAMA_CEDEARS, rows="500", cols="8")
            logger.info("Hoja creada exitosamente.")
            
        # 2. Consultar API de Comafi
        ts = int(time.time() * 1000)
        url = f"https://www.comafi.com.ar/custodiaglobal/json/apps/getproducts.aspx?ts={ts}&PageSize=1000"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        
        logger.info(f"Consumiendo API de Comafi: {url}")
        r = requests.get(url, headers=headers, verify=False, timeout=20)
        if r.status_code != 200:
            raise RuntimeError(f"Error HTTP {r.status_code} al consumir API de Comafi.")
            
        data = r.json()
        products = data.get('products', [])
        
        # Filtrar solo Cedears de acciones y ETFs
        cedears_raw = [p for p in products if p.get('section') in ["Cedear Shares", "Cedear ETF"]]
        
        if not cedears_raw:
            raise ValueError("La API de Comafi retornó 0 CEDEARs. Abortando escritura para no borrar datos vigentes.")
            
        logger.info(f"Se obtuvieron {len(cedears_raw)} CEDEARs vigentes.")
        
        # 3. Procesar filas
        filas_procesadas = []
        ahora_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for item in cedears_raw:
            ticker_local = str(item.get('name', '')).strip().upper()
            if not ticker_local:
                continue
                
            ticker_subyacente = obtener_ticker_subyacente(ticker_local)
            empresa = str(item.get('summary', '')).strip()
            isin_cedear = str(item.get('tip', '')).strip()
            isin_subyacente = str(item.get('tech', '')).strip()
            ratio = normalizar_ratio(item.get('character', ''))
            tipo = str(item.get('section', '')).strip()
            
            filas_procesadas.append([
                ticker_local,
                ticker_subyacente,
                empresa,
                isin_cedear,
                isin_subyacente,
                ratio,
                tipo,
                ahora_iso
            ])
            
        # 4. Volcar datos en la hoja
        encabezados = ["TICKER_LOCAL", "TICKER_SUBYACENTE", "EMPRESA", "ISIN_CEDEAR", "ISIN_SUBYACENTE", "RATIO", "TIPO", "ULTIMA_ACTUALIZACION"]
        
        ws_cedears.clear()
        ws_cedears.append_row(encabezados)
        
        # Guardar en lotes
        num_chunks = (len(filas_procesadas) + config.CHUNK_SIZE_SHEETS - 1) // config.CHUNK_SIZE_SHEETS
        for i in range(num_chunks):
            start_idx = i * config.CHUNK_SIZE_SHEETS
            end_idx = min((i + 1) * config.CHUNK_SIZE_SHEETS, len(filas_procesadas))
            ws_cedears.append_rows(filas_procesadas[start_idx:end_idx], value_input_option='USER_ENTERED')
            
        msg_exito = f"Sincronización de CEDEARs Comafi exitosa. {len(filas_procesadas)} activos registrados."
        logger.info(msg_exito)
        procesamiento.registrar_log(ws_log, "INFO", msg_exito, "captura_cedears")
        
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        procesamiento.actualizar_estado_proceso(ws_status, "OK", msg_exito, tiempo_ejecucion=duracion)
        print(f"[OK] {msg_exito} ({duracion})")
        return True
        
    except Exception as e:
        error_msg = f"Error crítico en captura_cedears: {e}"
        logger.exception(error_msg)
        procesamiento.registrar_log(ws_log, "ERROR", error_msg, "captura_cedears")
        procesamiento.actualizar_estado_proceso(ws_status, "ERROR", str(e)[:50])
        print(f"[ERROR] {error_msg}")
        return False

if __name__ == "__main__":
    ejecutar_captura_cedears()
