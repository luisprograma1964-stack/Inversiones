import time
import pandas as pd
import yfinance as yf
import auth_google
import logging_config

logger = logging_config.get_logger(__name__)

def limpiar_deslistados():
    sh = auth_google.conectar()
    ws = sh.worksheet('MAESTRO_ACTIVOS')
    datos = ws.get_all_records()
    
    # Identify headers to find ESTADO col index
    headers = ws.row_values(1)
    col_estado = headers.index('ESTADO') + 1
    
    deslistados_encontrados = []
    
    for idx, row in enumerate(datos):
        ticker = str(row.get('TICKER_ID', '')).strip()
        estado = str(row.get('ESTADO', '')).strip().upper()
        
        if not ticker or estado == 'DESLISTADO':
            continue
            
        # Check only INACTIVOS or those we suspect. Actually checking all 300+ takes time.
        # Let's check INACTIVO ones to see if they are completely dead.
        if estado == 'INACTIVO':
            try:
                # yfinance check
                t = yf.Ticker(ticker)
                hist = t.history(period="5d")
                if hist.empty:
                    # No data, it's dead/delisted
                    logger.info(f"Ticker {ticker} no devuelve datos. Marcando como DESLISTADO.")
                    # row + 2 because idx is 0-based and row 1 is header
                    ws.update_cell(idx + 2, col_estado, 'DESLISTADO')
                    deslistados_encontrados.append(ticker)
                    time.sleep(1) # Be nice to Google API
            except Exception as e:
                logger.warning(f"Error checking {ticker}: {e}")
                
    if deslistados_encontrados:
        logger.info(f"Proceso finalizado. Se marcaron como DESLISTADOS: {', '.join(deslistados_encontrados)}")
    else:
        logger.info("No se encontraron nuevos tickers deslistados.")

if __name__ == "__main__":
    limpiar_deslistados()
