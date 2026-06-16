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

# Diccionario de nombres reales para los activos solicitados
INFO_NUEVOS = {
    "NKE": "Nike, Inc.",
    "BRKB": "Berkshire Hathaway Inc. Class B",
    "AMZN": "Amazon.com, Inc.",
    "META": "Meta Platforms, Inc.",
    "C": "Citigroup Inc.",
    "VIST": "Vista Energy, S.A.B. de C.V.",
    "SPGY": "SPDR Portfolio S&P 500 Growth ETF", # Nota: Verificar si es SPYG
    "SPYG": "SPDR Portfolio S&P 500 Growth ETF",
    "ARKK": "ARK Innovation ETF",
    "DISN": "The Walt Disney Company",
    "DIS": "The Walt Disney Company",
    "WMT": "Walmart Inc.",
    "ETHA": "iShares Ethereum Trust"
}

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
    Inserta nuevos tickers y ordena la tabla MAESTRO_ACTIVOS.
    """
    logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] >>> Iniciando Mantenimiento de Maestro...")
    
    ahora_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sh = auth_google.conectar()
    if not sh:
        return

    try:
        ws_maestro = sh.worksheet(config.WS_MAESTRO_ACTIVOS)
        ws_log = sh.worksheet(config.WS_LOG_SISTEMA)
        ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)

        procesamiento.registrar_log(ws_log, "INFO", "Iniciando inserción masiva de tickers")
        procesamiento.actualizar_estado_proceso(ws_status, "PROCESANDO", "Validando e insertando nuevos tickers...")

        # 1. Leer datos actuales
        all_values = ws_maestro.get_all_values()
        
        # Columnas según ESTRUCTURA_SHEETS.md:
        # A: Ticker_ID, B: Nombre_Largo, C: Filtro_Noticias, D: Ultima_Actualiz, 
        # E: Dias_Keep_Hist, F: Fuente_Data, G: ESTADO
        columnas_base = [
            "TICKER_ID", "NOMBRE_LARGO", "FILTRO_NOTICIAS", 
            "ULTIMA_ACTUALIZ", "DIAS_KEEP_HIST", "FUENTE_DATA", "ESTADO"
        ]

        if not all_values or len(all_values) == 0:
            logger.warning("La hoja está vacía. Reconstruyendo estructura base y títulos...")
            columnas_originales = columnas_base
            df_maestro = pd.DataFrame(columns=columnas_originales)
        else:
            # Extraer encabezados y datos existentes
            columnas_originales = [c.strip().upper() for c in all_values[0]]
            df_maestro = pd.DataFrame(all_values[1:], columns=columnas_originales)

        # 3. Nivelar y normalizar formatos de fecha existentes (según ESTANDARES.md)
        if 'ULTIMA_ACTUALIZ' in df_maestro.columns:
            def normalizar_ts(val):
                val_str = str(val).strip()
                if not val_str or val_str.lower() in ['nan', 'none', '']:
                    return ""
                # Intentar convertir a datetime y luego a string ISO
                dt = pd.to_datetime(val_str, errors='coerce')
                return dt.strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(dt) else ""
            
            df_maestro['ULTIMA_ACTUALIZ'] = df_maestro['ULTIMA_ACTUALIZ'].apply(normalizar_ts)
        
        # 2. Identificar tickers que NO existen
        existentes = set(df_maestro['TICKER_ID'].astype(str).str.upper().tolist()) if not df_maestro.empty else set()
        agregados = 0

        filas_nuevas = []
        for t, nombre in INFO_NUEVOS.items():
            t_upper = t.strip().upper()
            if t_upper not in existentes:
                logger.info(f"Validando {t_upper} en Yahoo Finance...")
                
                # Solo asignamos Bridge si existe en Yahoo, sino queda vacío
                fuente = "GF_BRIDGE" if verificar_yahoo(t_upper) else ""
                
                nuevo_registro = {
                    "TICKER_ID": t_upper,
                    "NOMBRE_LARGO": nombre,
                    "FILTRO_NOTICIAS": f"stock:{t_upper}",
                    "ULTIMA_ACTUALIZ": ahora_ts,
                    "DIAS_KEEP_HIST": 250,   # Suficiente para SMA_200 + margen
                    "FUENTE_DATA": fuente,
                    "ESTADO": "ACTIVO"
                }
                filas_nuevas.append(nuevo_registro)
                agregados += 1

        if filas_nuevas:
            df_nuevos = pd.DataFrame(filas_nuevas)
            df_maestro = pd.concat([df_maestro, df_nuevos], ignore_index=True)
            logger.info(f"Se identificaron {agregados} tickers nuevos para agregar.")
        else:
            logger.info("Todos los tickers ya existen en el maestro.")

        # 3. Ordenar por TICKER_ID
        df_maestro = df_maestro.sort_values(by="TICKER_ID")

        # 4. Sobrescribir la hoja con los datos ordenados y actualizados
        ws_maestro.clear()
        # Forzamos la escritura desde A1 para restaurar títulos y datos
        ws_maestro.update(range_name='A1', values=[columnas_originales] + df_maestro[columnas_originales].values.tolist())

        resumen = f"Maestro actualizado. Agregados: {agregados}. Total: {len(df_maestro)}."
        procesamiento.registrar_log(ws_log, "INFO", resumen)
        procesamiento.actualizar_estado_proceso(ws_status, "OK", resumen)
        logger.info(f"{resumen}")

    except Exception as e:
        error_msg = f"Error en mantenimiento maestro: {e}"
        logger.exception(error_msg)
        procesamiento.registrar_log(sh.worksheet(config.WS_LOG_SISTEMA), "ERROR", error_msg)

if __name__ == "__main__":
    ejecutar_actualizacion_maestro()