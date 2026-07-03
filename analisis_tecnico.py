"""
Librería de cálculo matemático y análisis técnico.
Implementa el uso de pandas_ta para computar indicadores como RSI, MACD,
Medias Móviles (SMA), Parabolic SAR, DMI y retrocesos de Fibonacci.
"""
import pandas as pd
import pandas_ta as ta
import numpy as np
import config
import procesamiento
import auth_google
from datetime import datetime
import logging_config

logger = logging_config.get_logger(__name__)

def calcular_fibonacci(df_t):
    """
    Calcula el nivel de retroceso de Fibonacci basado en los últimos 30 días operables.
    
    Toma el precio máximo y mínimo del último periodo para calcular el rango ("swing"), 
    y luego determina en qué nivel de Fibonacci (0.236, 0.382, 0.500, 0.618, 0.786) 
    se encuentra el precio actual de cierre.
    
    Argumentos:
        df_t (DataFrame): Conjunto de datos históricos filtrado por un ticker específico.
                          Debe contener 'MAXIMO_DIA', 'MINIMO_DIA' y 'PRECIO_CIERRE'.
                          
    Retorna:
        str: El nivel de retroceso actual en formato de texto (ej. '0.618 (Golden)'), 
             'N/A' si el rango es cero, o 'Error' en caso de fallo.
    """
    try:
        ultimas_30 = df_t.tail(30)
        max_reciente = ultimas_30['MAXIMO_DIA'].max()
        min_reciente = ultimas_30['MINIMO_DIA'].min()
        precio_actual = df_t['PRECIO_CIERRE'].iloc[-1]
        
        if pd.isna(precio_actual) or precio_actual <= 0:
            return "Error (Precio <= 0)"

        if pd.isna(max_reciente) or max_reciente <= 0: return "N/A"

        diff = max_reciente - min_reciente
        if diff == 0: return "N/A"
        
        # Detección de errores de escala (Fail-Fast por coma vs punto) - Estándar 15x
        if precio_actual > (max_reciente * 15) or precio_actual < (min_reciente / 15):
            return "Error (Escala)"

        retroceso = (max_reciente - precio_actual) / diff
        
        if retroceso < 0: return "Extensión (High)"
        elif retroceso <= 0.236: return "0.236"
        elif retroceso <= 0.382: return "0.382"
        elif retroceso <= 0.500: return "0.500"
        elif retroceso <= 0.618: return "0.618 (Golden)"
        elif retroceso <= 1.0: return "0.786"
        else: return "Extensión (Low)"
    except Exception as e:
        logger.exception(f"Error en cálculo Fibonacci: {e}")
        return "Error"

def procesar_indicadores(df):
    """
    Procesa y calcula indicadores de análisis técnico para un conjunto de activos.
    
    Itera por cada ticker disponible en el DataFrame histórico, verifica si hay 
    suficientes días para el cálculo (según config.MIN_DIAS_HISTORIAL), y utiliza
    la librería pandas_ta para computar: RSI, Medias Móviles (SMA 20, 50, 200),
    MACD, Parabolic SAR (PSAR), y el Índice de Movimiento Direccional (DMI/ADX).
    También interpreta las señales obtenidas (alcistas o bajistas).
    
    Argumentos:
        df (DataFrame): Conjunto de datos con los precios históricos de todos los activos.
                        Debe incluir 'TICKER_ID', 'FECHA', 'PRECIO_CIERRE', 'MAXIMO_DIA' y 'MINIMO_DIA'.
                        
    Retorna:
        list: Una lista de listas, donde cada sub-lista representa una fila con los 
              resultados del análisis técnico de un ticker específico en su último día disponible.
    """
    resultados = []
    df.columns = [c.upper() for c in df.columns]

    # Conexión para logs y carga de ratios
    sh = None
    ws_log = None
    mapa_ratios = {}
    try:
        sh = auth_google.conectar()
        ws_log = sh.worksheet(config.WS_LOG_SISTEMA) if sh else None
        
        # Cargar los ratios del Comafi para calcular la brecha cambiaria (CCL)
        if sh:
            ws_cedears = sh.worksheet(config.WS_PROGRAMA_CEDEARS)
            datos_cedears = ws_cedears.get_all_records()
            if datos_cedears:
                df_cedears = pd.DataFrame(datos_cedears)
                df_cedears.columns = [c.strip().upper() for c in df_cedears.columns]
                for _, r in df_cedears.iterrows():
                    subyacente = str(r['TICKER_SUBYACENTE']).strip().upper()
                    ratio_str = str(r['RATIO']).strip()
                    try:
                        parts = ratio_str.split(':')
                        if len(parts) == 2:
                            a = float(parts[0].strip())
                            b = float(parts[1].strip())
                            if a > 0 and b > 0:
                                mapa_ratios[subyacente] = a / b
                    except:
                        pass
    except Exception as e:
        logger.warning(f"Error cargando ratios para cálculo de CCL: {e}")
    
    # Nivelación de fechas en memoria para el cálculo (soportando números de serie de Google Sheets)
    def parse_fecha_tecnico(v):
        if isinstance(v, (int, float)):
            return pd.to_datetime(v, unit='D', origin='1899-12-30').floor('D')
        return pd.to_datetime(str(v), errors='coerce')
    
    df['FECHA'] = df['FECHA'].apply(parse_fecha_tecnico)
    df = df.dropna(subset=['FECHA', 'PRECIO_CIERRE'])
    
    # Filtrar solo tickers que no sean de Byma (los BCBA: se usan para cruce, no se analizan por separado)
    tickers_analizar = [t for t in df['TICKER_ID'].unique() if not str(t).startswith("BCBA:")]
    
    for ticker in tickers_analizar:
        df_t = df[df['TICKER_ID'] == ticker].sort_values('FECHA').copy()
        
        if len(df_t) < config.MIN_DIAS_HISTORIAL:
            msg = f"{ticker}: Saltado por historial insuficiente ({len(df_t)}/{config.MIN_DIAS_HISTORIAL} días)."
            logger.info(f"    [!] {msg}")
            if ws_log: procesamiento.registrar_log(ws_log, "INFO", msg, config.ORIGEN_LOG_TECNICO)
            continue
        
        # Indicadores
        rsi_series = ta.rsi(df_t['PRECIO_CIERRE'], length=14)
        
        # Inicialización de seguridad para evitar UnboundLocalError
        final_rsi_val_for_output = 50.0 

        # Sanitización del RSI: Si da fuera de 0-100, la data de origen es basura
        if rsi_series is not None and not rsi_series.empty:
            final_rsi_val_for_output = rsi_series.iloc[-1] # Get the raw calculated RSI
            
            # Si el RSI no se puede calcular (NaN) o es absurdo
            if pd.isna(final_rsi_val_for_output) or final_rsi_val_for_output < 0 or final_rsi_val_for_output > 100:
                avg_p = df_t['PRECIO_CIERRE'].mean()
                curr_p = df_t['PRECIO_CIERRE'].iloc[-1]
                
                # Solo es error crítico si hay salto de escala (x15)
                if curr_p > (avg_p * 15) or curr_p < (avg_p / 15):
                    # Devolvemos un valor centinela para que main_tecnico aborte
                    final_rsi_val_for_output = -1.0 
                    msg = f"ERROR CRÍTICO: Escala corrupta en {ticker} (Precio: {curr_p} vs Promedio: {avg_p}). Abortando."
                    logger.critical(f"    [!] {msg}")
                    if ws_log: procesamiento.registrar_log(ws_log, "CRITICAL", msg, config.ORIGEN_LOG_TECNICO)
                else:
                    # Es un activo plano (como USDARS), asignamos RSI neutral
                    final_rsi_val_for_output = 50.0 # Assign neutral for flat assets
                    msg = f"Aviso: {ticker} es un activo plano o sin volatilidad. Usando RSI neutral (50.0)."
                    logger.warning(f"    [*] {msg}")
                    if ws_log: procesamiento.registrar_log(ws_log, "WARNING", msg, config.ORIGEN_LOG_TECNICO)

        df_t['SMA_20'] = ta.sma(df_t['PRECIO_CIERRE'], length=20)
        df_t['SMA_50'] = ta.sma(df_t['PRECIO_CIERRE'], length=50)
        df_t['SMA_200'] = ta.sma(df_t['PRECIO_CIERRE'], length=200)
        
        # Cálculos con validación de salida
        macd_raw = ta.macd(df_t['PRECIO_CIERRE'])
        psar_raw = ta.psar(df_t['MAXIMO_DIA'], df_t['MINIMO_DIA'], df_t['PRECIO_CIERRE'])
        dmi_raw = ta.adx(df_t['MAXIMO_DIA'], df_t['MINIMO_DIA'], df_t['PRECIO_CIERRE'], length=14)
        
        last = df_t.iloc[-1]
        
        fibo = calcular_fibonacci(df_t)
        
        # Interpretaciones con manejo de defaults y logs
        txt_macd = "NEUTRAL"
        if macd_raw is not None and not macd_raw.empty:
            txt_macd = "ALCISTA" if macd_raw.iloc[-1, 0] > macd_raw.iloc[-1, 2] else "BAJISTA"
        else:
            if ws_log: procesamiento.registrar_log(ws_log, "WARNING", f"MACD no calculable para {ticker}. Usando NEUTRAL.", config.ORIGEN_LOG_TECNICO)

        txt_psar = "BAJISTA (Arriba)"
        if psar_raw is not None and not psar_raw.empty:
            txt_psar = "ALCISTA (Abajo)" if not np.isnan(psar_raw.iloc[-1, 0]) else "BAJISTA (Arriba)"
        
        txt_dmi = "TENDENCIA INDEFINIDA"
        if dmi_raw is not None and not dmi_raw.empty:
            adx_val = dmi_raw.iloc[-1, 0]
            control = "COMPRADORES" if dmi_raw.iloc[-1, 1] > dmi_raw.iloc[-1, 2] else "VENDEDORES"
            txt_dmi = f"TENDENCIA {'FUERTE' if adx_val > 20 else 'DEBIL'} de {control}"

        # Helper to format numbers as floats for Sheets
        def format_num_for_sheets(v):
            if pd.notnull(v) and not np.isinf(v):
                try:
                    return round(float(v), 2)
                except:
                    return None
            return None

        # Prepend "'" to FIBO_RET to force it as text in Sheets
        fibo_for_sheets = "'" + str(fibo)

        txt_trend = "ALCISTA L.P." if last['PRECIO_CIERRE'] > last['SMA_200'] else "BAJISTA L.P."

        # Cálculo del CCL Implícito
        ccl_val = None
        if ticker in mapa_ratios:
            # Buscar el registro de Byma (BCBA:TICKER) para el mismo día
            fecha_busqueda = last['FECHA']
            df_local = df[(df['TICKER_ID'] == f"BCBA:{ticker}") & (df['FECHA'] == fecha_busqueda)]
            if not df_local.empty:
                try:
                    # Obtenemos precio en pesos (casteo seguro)
                    precio_ars_raw = df_local['PRECIO_CIERRE'].iloc[-1]
                    precio_ars = float(str(precio_ars_raw).replace(',', '.'))
                    precio_usd = float(str(last['PRECIO_CIERRE']).replace(',', '.'))
                    factor = mapa_ratios[ticker]
                    
                    if precio_usd > 0:
                        ccl_calc = (precio_ars * factor) / precio_usd
                        ccl_val = round(ccl_calc, 2)
                except Exception as ex:
                    logger.warning(f"Error al calcular CCL para {ticker} el {fecha_busqueda.strftime('%Y-%m-%d')}: {ex}")

        resultados.append([
            ticker, 
            last['FECHA'].strftime('%Y-%m-%d'),
            format_num_for_sheets(final_rsi_val_for_output),
            txt_macd, txt_trend, 
            format_num_for_sheets(last['SMA_20']), format_num_for_sheets(last['SMA_50']), format_num_for_sheets(last['SMA_200']), 
            txt_psar, fibo_for_sheets, txt_dmi, "PENDIENTE", datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            format_num_for_sheets(last['PRECIO_CIERRE']),
            last['FECHA'].strftime('%Y-%m-%d'), # FECHA_PRECIO_ACTUAL
            ccl_val
        ])
    return resultados

if __name__ == "__main__":
    logger.info("---------------------------------------------------------")
    logger.info("[!] Este archivo es una LIBRERÍA y no se ejecuta solo.")
    logger.info("[!] Por favor, ejecuta 'python main_tecnico.py'")
    logger.info("---------------------------------------------------------")