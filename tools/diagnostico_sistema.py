"""
Script de Diagnóstico Rápido del Sistema.
Valida:
1. Presencia de archivos de credenciales (.json y .txt).
2. Conexión a Google Sheets API.
3. Existencia de todas las hojas requeridas definidas en auth_google.
4. Formato de encabezados en hojas críticas (Maestro, Histórico, Técnico).
5. Conexión a la API de Gemini (Google AI).
"""
import sys
import os
from pathlib import Path

# Añadir el directorio raíz al path para poder importar módulos del proyecto
sys.path.append(str(Path(__file__).parent.parent))

import config
import auth_google
from google import genai

def ejecutar_diagnostico():
    print("="*70)
    print("   🔍 DIAGNÓSTICO INTEGRAL DEL SISTEMA DE INVERSIONES")
    print("="*70)
    
    errores = 0
    advertencias = 0

    # 1. Validar Archivos Físicos
    print("\n[1] Verificando archivos de configuración y credenciales...")
    archivos = {
        "Credenciales Google Sheets (JSON)": config.JSON_FILE,
        "API Key de Gemini (TXT)": config.API_KEY_FILE
    }
    for desc, ruta in archivos.items():
        if not os.path.exists(ruta):
            print(f"❌ ERROR: No se encontró {desc} en: {ruta}")
            errores += 1
        else:
            print(f"✅ {desc} detectado.")

    # 2. Conexión a Google Sheets
    print("\n[2] Verificando conexión a Google Sheets...")
    sh = None
    try:
        sh = auth_google.conectar()
        if sh:
            print(f"✅ Conexión exitosa a la planilla: '{config.SHEET_NAME}'")
        else:
            print("❌ ERROR: No se pudo establecer la conexión (verificar credenciales o permisos).")
            errores += 1
    except Exception as e:
        print(f"❌ ERROR: Excepción durante la conexión: {e}")
        errores += 1

    # 3. Presencia de Hojas y Encabezados
    if sh:
        print("\n[3] Verificando estructura de la planilla...")
        missing_sheets = auth_google.validar_hojas_requeridas(sh)
        if missing_sheets:
            print(f"❌ ERROR: Faltan {len(missing_sheets)} hojas requeridas: {missing_sheets}")
            errores += len(missing_sheets)
        else:
            print("✅ Todas las hojas requeridas están presentes.")

        # Validación de Encabezados Críticos según ESTRUCTURA_SHEETS.md
        hojas_criticas = {
            config.WS_HISTORICO_VALORES: ['TICKER_ID', 'FECHA', 'PRECIO_CIERRE', 'VOLUMEN', 'MAXIMO_DIA', 'MINIMO_DIA'],
            config.WS_ANALISIS_TECNICO: ["TICKER_ID", "FECHA", "RSI", "MACD", "TREND", "SMA_20", "SMA_50", "SMA_200", "PSAR", "FIBO_RET", "DMI", "ESTADO"],
            config.WS_MAESTRO_ACTIVOS: ["TICKER_ID", "NOMBRE_LARGO", "FILTRO_NOTICIAS", "ULTIMA_ACTUALIZ", "DIAS_KEEP_HIST", "FUENTE_DATA", "ESTADO"]
        }

        for nombre_hoja, columnas_esperadas in hojas_criticas.items():
            try:
                ws = sh.worksheet(nombre_hoja)
                columnas_reales = [str(c).strip().upper() for c in ws.row_values(1)]
                faltantes = [c.upper() for c in columnas_esperadas if c.upper() not in columnas_reales]
                
                if faltantes:
                    print(f"❌ ERROR en '{nombre_hoja}': Faltan encabezados: {faltantes}")
                    errores += 1
                else:
                    print(f"✅ Encabezados de '{nombre_hoja}' validados.")
            except Exception as e:
                print(f"⚠️ Advertencia: No se pudo validar la hoja '{nombre_hoja}': {e}")
                advertencias += 1

    # 4. Conexión Gemini API
    print("\n[4] Verificando acceso a Google Gemini API...")
    try:
        if os.path.exists(config.API_KEY_FILE):
            with open(config.API_KEY_FILE, 'r', encoding='utf-8') as f:
                key = f.read().strip()
            client = genai.Client(api_key=key)
            # Intento de listar modelos disponibles para verificar la clave
            modelos = list(client.models.list(config=None))
            print(f"✅ API Gemini funcional. {len(modelos)} modelos detectados.")
        else:
            print("⚠️ Saltando validación de Gemini por falta de archivo de clave.")
            advertencias += 1
    except Exception as e:
        print(f"❌ ERROR: No se pudo conectar con la API de Gemini: {e}")
        errores += 1

    print("\n" + "="*70)
    print(f"   RESUMEN: {errores} errores, {advertencias} advertencias.")
    if errores == 0:
        print("   🚀 EL SISTEMA ESTÁ LISTO PARA EL PIPELINE.")
    else:
        print("   🛑 SE DETECTARON PROBLEMAS CRÍTICOS. REVISA LA LISTA ARRIBA.")
    print("="*70)

if __name__ == "__main__":
    ejecutar_diagnostico()