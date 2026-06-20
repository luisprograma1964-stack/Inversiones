"""
Script de mantenimiento para la tabla MAESTRO_ACTIVOS.
Permite insertar nuevos tickers de forma masiva (si no existen) 
y mantiene la tabla ordenada alfabéticamente.
"""
import pandas as pd
import config
import auth_google
import procesamiento
from datetime import datetime
import requests
import logging_config

logger = logging_config.get_logger(__name__)
# Tickers esenciales del sistema que no deben ser desactivados aunque no tengan CEDEAR
TICKERS_SISTEMA_EXCLUIDOS = {"USDARS", "MERVAL", "9999", "9999_AR", "9999_US"}

def verificar_yahoo(ticker):
    """
    Verifica si el ticker existe en Yahoo Finance usando su API de búsqueda rápida.
    """
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={ticker}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Si hay resultados en la lista de quotes, el ticker es válido en Yahoo
            return len(data.get('quotes', [])) > 0
    except:
        return False
    return False

def ejecutar_actualizacion_maestro():
    """
    Sincroniza MAESTRO_ACTIVOS con PROGRAMA_CEDEARS:
    - Desactiva activos que no figuran en Comafi (y no son del sistema).
    - Inserta nuevos CEDEARs detectados automáticamente.
    - Ordena la tabla alfabéticamente.
    """
    logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] >>> Iniciando Mantenimiento de Maestro...")
    print("[*] Iniciando sincronización de Maestro de Activos...")
    
    ahora_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sh = auth_google.conectar()
    if not sh:
        print("[ERROR] Conexión a Google Sheets falló.")
        return False

    try:
        ws_maestro = sh.worksheet(config.WS_MAESTRO_ACTIVOS)
        ws_cedears = sh.worksheet(config.WS_PROGRAMA_CEDEARS)
        ws_log = sh.worksheet(config.WS_LOG_SISTEMA)
        ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)

        procesamiento.registrar_log(ws_log, "INFO", "Iniciando mantenimiento del maestro con base en Comafi", "mantenimiento_maestro")
        procesamiento.actualizar_estado_proceso(ws_status, "PROCESANDO", "Sincronizando maestro con programas de Comafi...")

        # 1. Leer datos de CEDEARs oficiales de la planilla
        datos_cedears = ws_cedears.get_all_records()
        if not datos_cedears:
            raise ValueError("La tabla PROGRAMA_CEDEARS está vacía. Abortando mantenimiento para evitar desactivación masiva.")
            
        df_cedears = pd.DataFrame(datos_cedears)
        df_cedears.columns = [c.strip().upper() for c in df_cedears.columns]
        
        # Obtener el conjunto de tickers internacionales (subyacentes) permitidos
        subyacentes_validos = set(df_cedears['TICKER_SUBYACENTE'].astype(str).str.strip().str.upper().unique())

        # 2. Leer datos actuales del Maestro
        all_values = ws_maestro.get_all_values()
        columnas_originales = [
            "TICKER_ID", "NOMBRE_LARGO", "FILTRO_NOTICIAS", 
            "ULTIMA_ACTUALIZ", "DIAS_KEEP_HIST", "FUENTE_DATA", "ESTADO"
        ]

        if not all_values or len(all_values) == 0:
            df_maestro = pd.DataFrame(columns=columnas_originales)
        else:
            columnas_leidas = [c.strip().upper() for c in all_values[0]]
            # Asegurar que existan todas las columnas requeridas
            for col in columnas_originales:
                if col not in columnas_leidas:
                    raise KeyError(f"Columna crítica faltante en MAESTRO_ACTIVOS: {col}")
            df_maestro = pd.DataFrame(all_values[1:], columns=columnas_leidas)

        # Normalizar claves
        df_maestro['TICKER_ID'] = df_maestro['TICKER_ID'].astype(str).str.strip().str.upper()
        
        # 3. SANEAMIENTO: Desactivar activos ausentes en Comafi
        desactivados = 0
        for idx, row in df_maestro.iterrows():
            ticker = row['TICKER_ID']
            # Omitir los del sistema o los que empiezan con 9999
            if ticker in TICKERS_SISTEMA_EXCLUIDOS or ticker.startswith("9999"):
                continue
                
            # Si no está en el listado oficial de Comafi y está activo, lo desactivamos
            if ticker not in subyacentes_validos:
                if row['ESTADO'] == 'ACTIVO':
                    df_maestro.at[idx, 'ESTADO'] = 'INACTIVO'
                    df_maestro.at[idx, 'ULTIMA_ACTUALIZ'] = ahora_ts
                    desactivados += 1
                    logger.info(f"Desactivando {ticker} (no posee programa CEDEAR vigente)")

        # 4. AUTO-INSERTAR: Agregar nuevos CEDEARs ausentes en el Maestro
        existentes = set(df_maestro['TICKER_ID'].tolist())
        agregados = 0
        filas_nuevas = []

        # Agrupar cedears para obtener el nombre oficial del primer registro
        cedears_unicos = df_cedears.drop_duplicates(subset=['TICKER_SUBYACENTE']).copy()

        for _, r in cedears_unicos.iterrows():
            subyacente = str(r['TICKER_SUBYACENTE']).strip().upper()
            if not subyacente or subyacente in existentes:
                continue
                
            nombre_largo = str(r['EMPRESA']).strip()
            # Validar en Yahoo Finance si es operable
            fuente = "GF_BRIDGE" if verificar_yahoo(subyacente) else ""
            
            nuevo_registro = {
                "TICKER_ID": subyacente,
                "NOMBRE_LARGO": nombre_largo,
                "FILTRO_NOTICIAS": f"stock:{subyacente}",
                "ULTIMA_ACTUALIZ": ahora_ts,
                "DIAS_KEEP_HIST": "250",
                "FUENTE_DATA": fuente,
                "ESTADO": "INACTIVO" # Se auto-inserta inactivo por defecto, el usuario decide si activarlo
            }
            filas_nuevas.append(nuevo_registro)
            agregados += 1
            logger.info(f"Auto-insertando nuevo CEDEAR detectado: {subyacente} ({nombre_largo})")

        if filas_nuevas:
            df_nuevos = pd.DataFrame(filas_nuevas)
            df_maestro = pd.concat([df_maestro, df_nuevos], ignore_index=True)

        # 5. Ordenar por TICKER_ID
        df_maestro = df_maestro.sort_values(by="TICKER_ID")

        # 6. Sobrescribir hoja con datos ordenados
        ws_maestro.clear()
        ws_maestro.update(range_name='A1', values=[columnas_originales] + df_maestro[columnas_originales].values.tolist())

        resumen = f"Sincronización Maestro OK. Desactivados: {desactivados}. Agregados: {agregados}. Total: {len(df_maestro)}."
        logger.info(resumen)
        procesamiento.registrar_log(ws_log, "INFO", resumen, "mantenimiento_maestro")
        procesamiento.actualizar_estado_proceso(ws_status, "OK", resumen)
        print(f"[OK] {resumen}")
        return True

    except Exception as e:
        error_msg = f"Error en mantenimiento maestro: {e}"
        logger.exception(error_msg)
        try:
            procesamiento.registrar_log(sh.worksheet(config.WS_LOG_SISTEMA), "ERROR", error_msg, "mantenimiento_maestro")
            procesamiento.actualizar_estado_proceso(ws_status, "ERROR", str(e)[:50])
        except:
            pass
        print(f"[ERROR] {error_msg}")
        return False

if __name__ == "__main__":
    ejecutar_actualizacion_maestro()