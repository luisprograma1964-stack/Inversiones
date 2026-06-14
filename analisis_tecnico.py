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
        
        # Detección de errores de escala (Fail-Fast por coma vs punto)
        if precio_actual > (max_reciente * 5) or precio_actual < (min_reciente / 5):
            return "Error (Escala)"

        retroceso = (max_reciente - precio_actual) / diff
        
        if retroceso < 0: return "Extensión (High)"
        elif retroceso <= 0.236: return "0.236"
        elif retroceso <= 0.382: return "0.382"
        elif retroceso <= 0.500: return "0.500"
        elif retroceso <= 0.618: return "0.618 (Golden)"
        elif retroceso <= 1.0: return "0.786"
        else: return "Extensión (Low)"
    except:
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

    # Conexión para logs (según estándar de Luis)
    sh = None
    ws_log = None
    try:
        sh = auth_google.conectar()
        ws_log = sh.worksheet(config.WS_LOG_SISTEMA) if sh else None
    except: pass
    
    # Nivelación de fechas en memoria para el cálculo (soportando números de serie de Google Sheets)
    def parse_fecha_tecnico(v):
        if isinstance(v, (int, float)):
            return pd.to_datetime(v, unit='D', origin='1899-12-30').floor('D')
        return pd.to_datetime(str(v), errors='coerce')
    
    df['FECHA'] = df['FECHA'].apply(parse_fecha_tecnico)
    df = df.dropna(subset=['FECHA', 'PRECIO_CIERRE'])
    
    for ticker in df['TICKER_ID'].unique():
        df_t = df[df['TICKER_ID'] == ticker].sort_values('FECHA').copy()
        
        if len(df_t) < config.MIN_DIAS_HISTORIAL:
            print(f"    [!] {ticker}: Saltado por historial insuficiente ({len(df_t)}/{config.MIN_DIAS_HISTORIAL} días).")
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
                
                # Solo es error crítico si hay salto de escala (x10)
                if curr_p > (avg_p * 10) or curr_p < (avg_p / 10):
                    # Devolvemos un valor centinela para que main_tecnico aborte
                    final_rsi_val_for_output = -1.0 
                    msg = f"ERROR CRÍTICO: Escala corrupta en {ticker} (Precio: {curr_p} vs Promedio: {avg_p}). Abortando."
                    print(f"    [!] {msg}")
                    if ws_log: procesamiento.registrar_log(ws_log, "CRITICAL", msg, config.ORIGEN_LOG_TECNICO)
                else:
                    # Es un activo plano (como USDARS), asignamos RSI neutral
                    final_rsi_val_for_output = 50.0 # Assign neutral for flat assets
                    msg = f"Aviso: {ticker} es un activo plano o sin volatilidad. Usando RSI neutral (50.0)."
                    print(f"    [*] {msg}")
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

        # Helper to format numbers as strings with comma decimal for Sheets
        def format_num_for_sheets(v):
            if pd.notnull(v) and not np.isinf(v):
                return float(round(float(v), 2))
            return None

        # Prepend "'" to FIBO_RET to force it as text in Sheets
        fibo_for_sheets = "'" + str(fibo)

        txt_trend = "ALCISTA L.P." if last['PRECIO_CIERRE'] > last['SMA_200'] else "BAJISTA L.P."

        resultados.append([
            ticker, 
            last['FECHA'].strftime('%Y-%m-%d'),
            format_num_for_sheets(final_rsi_val_for_output),
            txt_macd, txt_trend, 
            format_num_for_sheets(last['SMA_20']), format_num_for_sheets(last['SMA_50']), format_num_for_sheets(last['SMA_200']), 
            txt_psar, fibo_for_sheets, txt_dmi, "PENDIENTE", datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            format_num_for_sheets(last['PRECIO_CIERRE']),
            last['FECHA'].strftime('%Y-%m-%d') # FECHA_PRECIO_ACTUAL
        ])
    return resultados

if __name__ == "__main__":
    print("---------------------------------------------------------")
    print("[!] Este archivo es una LIBRERÍA y no se ejecuta solo.")
    print("[!] Por favor, ejecuta 'python main_tecnico.py'")
    print("---------------------------------------------------------")