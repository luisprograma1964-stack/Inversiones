"""
Script de Control de Calidad e Integridad de Datos.
- Verifica la coherencia entre MAESTRO_ACTIVOS e HISTORICO_VALORES.
- Detecta registros huérfanos, activos sin historial y tickers inactivos con datos.
- Identifica inconsistencias de precios (negativos, ceros, máximos < mínimos).
- Detecta saltos abruptos de precios (posibles splits mal cargados o anomalías).
- Identifica brechas temporales (gaps) y falta de datos recientes en activos activos.
"""
import pandas as pd
import numpy as np
import auth_google
import config
from datetime import datetime, timedelta
import logging_config

logger = logging_config.get_logger(__name__)

def ejecutar_control():
    logger.info("==================================================")
    logger.info("[+] INICIANDO CONTROL DE CALIDAD Y CONFIGURACIÓN")
    logger.info("==================================================")

    # 1. Conexión a Google Sheets
    sh = auth_google.conectar()
    if not sh:
        logger.error("No se pudo conectar a Google Sheets.")
        return False

    # 2. Descargar hojas necesarias
    logger.info("Descargando hojas: MAESTRO_ACTIVOS e HISTORICO_VALORES...")
    try:
        ws_maestro = sh.worksheet(config.WS_MAESTRO_ACTIVOS)
        ws_historico = sh.worksheet(config.WS_HISTORICO_VALORES)
        
        df_maestro = pd.DataFrame(ws_maestro.get_all_records(value_render_option='UNFORMATTED_VALUE'))
        df_historico = pd.DataFrame(ws_historico.get_all_records(value_render_option='UNFORMATTED_VALUE'))
    except Exception as e:
        logger.exception(f"ERROR al descargar datos: {e}")
        return False

    # Estandarizar nombres de columnas a mayúsculas
    df_maestro.columns = [str(c).strip().upper() for c in df_maestro.columns]
    df_historico.columns = [str(c).strip().upper() for c in df_historico.columns]

    logger.info(f"Cargados {len(df_maestro)} activos en el Maestro.")
    logger.info(f"Cargados {len(df_historico)} registros en el Histórico.")

    # Estandarizar columnas clave
    df_maestro['TICKER_ID'] = df_maestro['TICKER_ID'].astype(str).str.strip().str.upper()
    df_maestro['ESTADO'] = df_maestro['ESTADO'].astype(str).str.strip().str.upper()
    
    df_historico['TICKER_ID'] = df_historico['TICKER_ID'].astype(str).str.strip().str.upper()
    df_historico['FECHA'] = pd.to_datetime(df_historico['FECHA'], errors='coerce')
    
    # 3. CONTROL DE INTEGRIDAD REFERENCIAL
    logger.info("--- 1. CONTROL DE INTEGRIDAD REFERENCIAL ---")
    
    activos_maestro = set(df_maestro['TICKER_ID'].unique())
    activos_activos_maestro = set(df_maestro[df_maestro['ESTADO'] == 'ACTIVO']['TICKER_ID'].unique())
    activos_inactivos_maestro = set(df_maestro[df_maestro['ESTADO'] == 'INACTIVO']['TICKER_ID'].unique())
    activos_historico = set(df_historico['TICKER_ID'].unique())

    # A. Activos ACTIVOS en el maestro que NO tienen datos en el histórico
    activos_sin_historial = activos_activos_maestro - activos_historico
    if activos_sin_historial:
        logger.warning(f"ADVERTENCIA: {len(activos_sin_historial)} activos ACTIVOS en el maestro no tienen ningún registro histórico: {sorted(list(activos_sin_historial))}")
    else:
        logger.info("Todos los activos activos en el maestro tienen al menos un registro en el histórico.")

    # B. Registros huérfanos: Tickers en HISTORICO_VALORES que NO existen en MAESTRO_ACTIVOS
    huerfanos = activos_historico - activos_maestro
    if huerfanos:
        logger.warning(f"ALERTA: {len(huerfanos)} tickers en HISTORICO_VALORES no existen en MAESTRO_ACTIVOS (huérfanos): {sorted(list(huerfanos))}")
    else:
        logger.info("No hay tickers huérfanos en el histórico.")

    # C. Activos INACTIVOS en el maestro que tienen registros en el histórico
    inactivos_con_datos = activos_inactivos_maestro & activos_historico
    if inactivos_con_datos:
        logger.info(f"NOTA: {len(inactivos_con_datos)} activos INACTIVOS en el maestro tienen registros históricos: {sorted(list(inactivos_con_datos))}")

    # 4. CONTROL DE FORMATO Y VALORES NULOS
    logger.info("--- 2. CONTROL DE VALORES NULOS Y FORMATOS ---")
    
    # Fechas no válidas
    fechas_nulas = df_historico['FECHA'].isnull().sum()
    if fechas_nulas > 0:
        logger.warning(f"Hay {fechas_nulas} registros con fechas nulas o en formato inválido.")
    else:
        logger.info("No hay fechas nulas o inválidas.")

    # Valores nulos en precios o volumen
    for col in ['PRECIO_CIERRE', 'VOLUMEN', 'MAXIMO_DIA', 'MINIMO_DIA']:
        if col in df_historico.columns:
            # Reemplazar vacíos por NaN
            df_historico[col] = pd.to_numeric(df_historico[col], errors='coerce')
            nulos = df_historico[col].isnull().sum()
            if nulos > 0:
                logger.warning(f"Columna {col} tiene {nulos} valores nulos o no numéricos.")
            else:
                logger.info(f"Columna {col} no tiene valores nulos.")

    # 5. CONTROL DE COHERENCIA DE PRECIOS Y VOLUMEN
    logger.info("--- 3. CONTROL DE COHERENCIA DE PRECIOS Y VOLUMEN ---")
    
    # Precios menores o iguales a cero
    precios_invalidos = df_historico[df_historico['PRECIO_CIERRE'] <= 0]
    if not precios_invalidos.empty:
        logger.warning(f"Hay {len(precios_invalidos)} registros con precio de cierre <= 0:\n{precios_invalidos[['TICKER_ID', 'FECHA', 'PRECIO_CIERRE']].head(10).to_string()}")
    else:
        logger.info("Todos los precios de cierre son mayores a cero.")

    # Máximo menor al mínimo
    max_menor_min = df_historico[df_historico['MAXIMO_DIA'] < df_historico['MINIMO_DIA']]
    if not max_menor_min.empty:
        logger.warning(f"Hay {len(max_menor_min)} registros donde MAXIMO_DIA < MINIMO_DIA:\n{max_menor_min[['TICKER_ID', 'FECHA', 'MAXIMO_DIA', 'MINIMO_DIA']].head(10).to_string()}")
    else:
        logger.info("No hay registros donde el máximo del día sea menor al mínimo.")

    # Precio fuera del rango diario (Cierre no está entre Min y Max)
    cierre_fuera = df_historico[
        (df_historico['PRECIO_CIERRE'] < df_historico['MINIMO_DIA']) | 
        (df_historico['PRECIO_CIERRE'] > df_historico['MAXIMO_DIA'])
    ]
    # Ignoramos si Min o Max son cero (a veces pasa por falta de datos)
    cierre_fuera_filtrado = cierre_fuera[
        (cierre_fuera['MINIMO_DIA'] > 0) & (cierre_fuera['MAXIMO_DIA'] > 0)
    ]
    if not cierre_fuera_filtrado.empty:
        logger.warning(f"Hay {len(cierre_fuera_filtrado)} registros donde el precio de cierre está fuera del rango [Mínimo, Máximo]:\n{cierre_fuera_filtrado[['TICKER_ID', 'FECHA', 'MINIMO_DIA', 'PRECIO_CIERRE', 'MAXIMO_DIA']].head(10).to_string()}")
    else:
        logger.info("Los precios de cierre se encuentran dentro del rango [Mínimo, Máximo] diario.")

    # 6. ANÁLISIS DE ANOMALÍAS DE PRECIO (VARIACIONES EXTREMAS)
    logger.info("--- 4. VARIACIONES EXTREMAS Y ANOMALÍAS (POSIBLES ERRORES / SPLITS) ---")
    
    # Ordenar por ticker y fecha para calcular variaciones porcentuales
    df_temp = df_historico.sort_values(by=['TICKER_ID', 'FECHA']).copy()
    df_temp['RET_DIA'] = df_temp.groupby('TICKER_ID')['PRECIO_CIERRE'].pct_change()
    
    # Umbral de variación del 50% diario (suba o baja extrema)
    VARIACION_LIMITE = 0.50
    variaciones_extremas = df_temp[df_temp['RET_DIA'].abs() > VARIACION_LIMITE]
    
    if not variaciones_extremas.empty:
        logger.warning(f"Detectadas {len(variaciones_extremas)} variaciones de precio diarias mayores al {VARIACION_LIMITE * 100}%:")
        # Mostrar las más significativas
        for idx, row in variaciones_extremas.sort_values(by='RET_DIA', key=abs, ascending=False).head(15).iterrows():
            pct = row['RET_DIA'] * 100
            fecha_str = row['FECHA'].strftime('%Y-%m-%d')
            logger.warning(f"- {row['TICKER_ID']} el {fecha_str}: Var: {pct:+.2f}% | Cierre: {row['PRECIO_CIERRE']:.2f}")
    else:
        logger.info(f"No se detectaron variaciones diarias extremas (> {VARIACION_LIMITE*100}%).")

    # 7. ANÁLISIS DE RECIENCIA Y BRECHAS (GAPS)
    logger.info("--- 5. RECIENCIA Y BRECHAS DE ACTUALIZACIÓN ---")
    
    hoy = datetime.now()
    limite_actualidad = hoy - timedelta(days=7) # Consideramos desactualizado si no tiene datos hace más de 7 días
    
    tickers_desactualizados = []
    brechas_grandes = []
    
    for ticker in activos_activos_maestro:
        df_t = df_temp[df_temp['TICKER_ID'] == ticker]
        if df_t.empty:
            continue
            
        max_fecha = df_t['FECHA'].max()
        dias_desde_actualizacion = (hoy - max_fecha).days
        
        if dias_desde_actualizacion > 7:
            tickers_desactualizados.append((ticker, max_fecha.strftime('%Y-%m-%d'), dias_desde_actualizacion))
            
        # Calcular brechas entre fechas consecutivas
        df_t = df_t.sort_values('FECHA')
        diferencia_fechas = df_t['FECHA'].diff().dt.days
        
        # Ignoramos fines de semana (brechas > 4 días)
        brechas_t = df_t[diferencia_fechas > 4]
        if not brechas_t.empty:
            for idx, row in brechas_t.iterrows():
                prev_row = df_t.loc[idx - 1] if idx - 1 in df_t.index else None
                prev_fecha = prev_row['FECHA'].strftime('%Y-%m-%d') if prev_row is not None else "N/A"
                gap_days = diferencia_fechas.loc[idx]
                brechas_grandes.append((ticker, prev_fecha, row['FECHA'].strftime('%Y-%m-%d'), gap_days))

    if tickers_desactualizados:
        logger.warning(f"{len(tickers_desactualizados)} activos activos no registran actualizaciones recientes (últimos 7 días):")
        for ticker, ult_fecha, dias in sorted(tickers_desactualizados, key=lambda x: x[2], reverse=True)[:15]:
            logger.warning(f"- {ticker}: última actualización el {ult_fecha} ({dias} días sin datos)")
    else:
        logger.info("Todos los activos activos tienen datos actualizados al menos en los últimos 7 días.")

    if brechas_grandes:
        logger.warning(f"Se detectaron {len(brechas_grandes)} saltos de fechas inusuales (> 4 días):")
        for ticker, f_desde, f_hasta, dias in sorted(brechas_grandes, key=lambda x: x[3], reverse=True)[:15]:
            logger.warning(f"- {ticker}: brecha de {dias} días sin datos entre {f_desde} y {f_hasta}")
    else:
        logger.info("No se detectaron brechas de días inusuales (> 4 días) entre registros consecutivos.")

    logger.info("==================================================")
    logger.info("[+] CONTROL DE CALIDAD Y CONFIGURACIÓN FINALIZADO")
    logger.info("==================================================")
    return True

if __name__ == "__main__":
    ejecutar_control()
