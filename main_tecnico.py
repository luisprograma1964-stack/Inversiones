"""
Orquestador del cálculo de indicadores técnicos.
Se encarga de recuperar los precios históricos de las acciones (HISTORICO_VALORES),
alimentar la librería de cálculo técnico y guardar los resultados procesados en
la hoja de ANALISIS_TECNICO para su posterior uso por la Inteligencia Artificial.
"""
import config
import auth_google
import procesamiento  # Aquí vive registrar_log
import analisis_tecnico
from datetime import datetime
import time
import pandas as pd
import logging_config

logger = logging_config.get_logger(__name__)


def ejecutar_analisis_completo():
    """
    Función principal que coordina y ejecuta el análisis técnico completo.
    
    Esta rutina realiza los siguientes pasos:
    1. Se conecta a Google Sheets.
    2. Registra el inicio del proceso en el log y el semáforo.
    3. Obtiene los datos históricos de los valores.
    4. Procesa y calcula los indicadores técnicos (ej. RSI, MACD, etc).
    5. Escribe los resultados obtenidos en la hoja correspondiente.
    6. Actualiza el log y el semáforo con el resultado de la operación.
    """
    logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] >>> Iniciando Módulo Técnico...")
    t_inicio = time.time()
    
    sh = auth_google.conectar()
    if not sh: return False

    try:
        # 1. Instanciar todas las hojas necesarias
        ws_hist = sh.worksheet(config.WS_HISTORICO_VALORES)
        ws_analisis = sh.worksheet(config.WS_ANALISIS_TECNICO)
        ws_log = sh.worksheet(config.WS_LOG_SISTEMA)
        ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)
        ws_maestro = sh.worksheet(config.WS_MAESTRO_ACTIVOS)

        # 2. LOG DE INICIO (Forzado)
        # Asegúrate que registrar_log reciba (hoja, nivel, mensaje)
        procesamiento.registrar_log(ws_log, "INFO", "Iniciando Análisis Técnico", config.ORIGEN_LOG_TECNICO)
        procesamiento.actualizar_estado_proceso(ws_status, "PROCESANDO", "Calculando indicadores...")

        # 3. OBTENER DATOS
        # Lectura robusta via raw values para evitar error por encabezados duplicados en la hoja
        raw_hist = ws_hist.get_all_values(value_render_option='UNFORMATTED_VALUE')
        if not raw_hist or len(raw_hist) < 2:
            procesamiento.registrar_log(ws_log, "WARNING", "No hay datos en HISTORICO_VALORES")
            return False
        # Usar solo las primeras apariciones de cada encabezado para evitar duplicados
        header_raw = [str(h).strip().rstrip('.').upper() for h in raw_hist[0]]
        seen_h = {}
        header_clean = []
        for h in header_raw:
            if h not in seen_h:
                seen_h[h] = True
                header_clean.append(h)
            else:
                header_clean.append(None)  # columna duplicada: ignorar
        rows_hist = []
        for row in raw_hist[1:]:
            row_dict = {}
            for i, val in enumerate(row):
                col = header_clean[i] if i < len(header_clean) else None
                if col:
                    row_dict[col] = val
            rows_hist.append(row_dict)
        data = rows_hist

        # Obtener lista de activos esperados para validación de cobertura
        raw_maestro = ws_maestro.get_all_values(value_render_option='UNFORMATTED_VALUE')
        if raw_maestro and len(raw_maestro) >= 2:
            hdr_m = [str(h).strip().rstrip('.').upper() for h in raw_maestro[0]]
            df_maestro = pd.DataFrame(raw_maestro[1:], columns=hdr_m)
        else:
            df_maestro = pd.DataFrame()
        df_maestro.columns = [c.strip().upper() for c in df_maestro.columns]

        # Definir activos esperados para la validación de cobertura
        activos_activos = df_maestro[df_maestro['ESTADO'] == 'ACTIVO']['TICKER_ID'].unique().tolist()
        conteo_esperado = len(activos_activos)

        # 4. PROCESAR
        df = pd.DataFrame(data)
        df.columns = [str(c).strip().rstrip('.').upper() for c in df.columns]

        # Diagnóstico: mostrar columnas reales leídas de la hoja
        logger.debug(f"    [DEBUG] Columnas detectadas en HISTORICO_VALORES: {list(df.columns)}")

        # Eliminar duplicados accidentales por Ticker y Fecha antes de calcular
        cols_dedup = [c for c in ['TICKER_ID', 'FECHA'] if c in df.columns]
        if cols_dedup:
            df = df.drop_duplicates(subset=cols_dedup, keep='last')

        # 4. LIMPIEZA ROBUSTA (Usa la nueva función de procesamiento)
        cols_precios = ['PRECIO_CIERRE', 'MAXIMO_DIA', 'MINIMO_DIA']
        for col in cols_precios:
            if col in df.columns:
                df[col] = procesamiento.limpiar_serie_numerica(df[col])

        # Verificación de existencia de columnas críticas (Fail-Fast)
        cols_requeridas = ['TICKER_ID', 'FECHA', 'PRECIO_CIERRE', 'MAXIMO_DIA', 'MINIMO_DIA']
        faltantes = [c for c in cols_requeridas if c not in df.columns]
        if faltantes:
            error_headers = f"ERROR CRÍTICO: Faltan encabezados en {config.WS_HISTORICO_VALORES}: {', '.join(faltantes)}. ¿Se borró la primera fila de la hoja?"
            logger.critical(f"\n    [!] {error_headers}")
            procesamiento.registrar_log(ws_log, "CRITICAL", error_headers, config.ORIGEN_LOG_TECNICO)
            return False
        
        # Eliminar filas que quedaron vacías por errores de conversión
        df = df.dropna(subset=['PRECIO_CIERRE'])

        # FILTRO DE SANIDAD: Eliminar registros con escala sospechosa.
        # En lugar de un valor fijo (1M), comparamos cada registro contra el último precio (Pivot).
        # Esto limpia registros viejos mal formateados que ensucian las medias móviles.
        df['FECHA_DT'] = pd.to_datetime(df['FECHA'], format='mixed', dayfirst=True, errors='coerce')
        df = df.sort_values(['TICKER_ID', 'FECHA_DT'])
        
        ultimos_precios = df.groupby('TICKER_ID')['PRECIO_CIERRE'].transform('last')
        
        # Si un precio histórico es 15 veces mayor o menor al último, se descarta (evita ruidos de carga)
        mask_ok = (df['TICKER_ID'].isin(['BTC', 'ETH', 'USDARS'])) | \
                  ((df['PRECIO_CIERRE'] < ultimos_precios * 15) & (df['PRECIO_CIERRE'] > ultimos_precios * (1/15)))
        
        if not mask_ok.all():
            locos = df[~mask_ok]['TICKER_ID'].unique().tolist()
            f_min = df[~mask_ok]['FECHA_DT'].min().strftime('%Y-%m-%d')
            f_max = df[~mask_ok]['FECHA_DT'].max().strftime('%Y-%m-%d')
            
            msg_desc = f"Descartando {sum(~mask_ok)} registros por escala extrema en: {locos} (Rango: {f_min} a {f_max})"
            logger.warning(f"    [!] {msg_desc}")
            procesamiento.registrar_log(ws_log, "WARNING", msg_desc, config.ORIGEN_LOG_TECNICO)
            df = df[mask_ok]
            logger.info("    [*] Historial saneado en memoria para el cálculo técnico.")
            procesamiento.registrar_log(ws_log, "INFO", "Historial saneado en memoria", config.ORIGEN_LOG_TECNICO)

        resultados = analisis_tecnico.procesar_indicadores(df)

        # 5. ESCRIBIR RESULTADOS
        encabezados = ["TICKER_ID", "FECHA", "RSI", "MACD", "TREND", "SMA_20", "SMA_50", "SMA_200", "PSAR", "FIBO_RET", "DMI", "ESTADO", "ULTIMA_ACTUALIZACION", "PRECIO_ACTUAL", "FECHA_PRECIO_ACTUAL", "CCL_IMPLICITO"]
        
        if resultados:
            # VALIDACIÓN DE COBERTURA: Detener si no se procesaron todos los activos activos
            if len(resultados) < conteo_esperado:
                activos_procesados = [r[0] for r in resultados]
                faltantes = [a for a in activos_activos if a not in activos_procesados]
                error_cobertura = f"FALLA DE COBERTURA: Se esperaban {conteo_esperado} activos (Maestro), pero solo se procesaron {len(resultados)}. Faltan en histórico: {', '.join(faltantes)}"
                logger.critical(error_cobertura)
                procesamiento.registrar_log(ws_log, "CRITICAL", error_cobertura, config.ORIGEN_LOG_TECNICO)
                return False # Esto aborta el pipeline en el ensamblador para no gastar tokens

            # LIMPIEZA PREVENTIVA: Borramos la hoja antes de validar. 
            # Si la validación falla, la hoja queda vacía (sin "zombies") y el pipeline se detiene.
            ws_analisis.clear()
            ws_analisis.append_row(encabezados)

            # VALIDACIÓN DE INTEGRIDAD (Fail-Fast)
            for res in resultados:
                row_dict = dict(zip(encabezados, res))
                
                # Check de aborto por error de escala detectado en analisis_tecnico
                if str(row_dict.get('RSI')).replace(',', '.') in ['-1.0', '-1.00', '-1']:
                    error_fatal = f"ERROR CRÍTICO: Escala de precios corrupta detectada en {row_dict['TICKER_ID']}"
                    procesamiento.registrar_log(ws_log, "CRITICAL", error_fatal, config.ORIGEN_LOG_TECNICO)
                    return False

                # Inyectamos el precio actual del DF para que validar_datos_tecnicos pueda chequear la escala
                ticker = row_dict['TICKER_ID']
                precio_actual = df[df['TICKER_ID'] == ticker]['PRECIO_CIERRE'].iloc[-1]
                row_dict['PRECIO_CIERRE_VALIDACION'] = precio_actual
                logger.info(f"    [*] Validando integridad técnica de {ticker} (RSI: {row_dict.get('RSI')})")
                
                es_valido, motivo = procesamiento.validar_datos_tecnicos(row_dict) # Usa PRECIO_CIERRE_VALIDACION internamente
                if not es_valido:
                    error_integ = f"Falla de Integridad Técnica en {row_dict['TICKER_ID']}: {motivo}"
                    procesamiento.registrar_log(ws_log, "CRITICAL", error_integ, config.ORIGEN_LOG_TECNICO)
                    logger.critical(f"\n    [!] ABORTANDO: {error_integ}")
                    return False # Aborta para que el ensamblador detecte el error
            
            # Si todos son válidos, grabamos el bloque completo
            # Forzamos USER_ENTERED para que Google Sheets respete el tipo de dato numérico
            ws_analisis.append_rows(resultados, value_input_option='USER_ENTERED')
            
            msg_exito = f"Análisis técnico finalizado con éxito: {len(resultados)} activos."
            duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
            procesamiento.registrar_log(ws_log, "INFO", msg_exito, config.ORIGEN_LOG_TECNICO)
            procesamiento.actualizar_estado_proceso(ws_status, "OK", msg_exito, tiempo_ejecucion=duracion)
            logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] {msg_exito}")
            return True
        else:
            procesamiento.registrar_log(ws_log, "WARNING", "No se generaron resultados técnicos.")
            return False

    except Exception as e:
        error_msg = f"Error Crítico Técnico: {str(e)}"
        logger.exception(error_msg)
        try:
            # Intentamos registrar el error en el log si la hoja está disponible
            procesamiento.registrar_log(ws_log, "ERROR", error_msg)
            procesamiento.actualizar_estado_proceso(ws_status, "ERROR", str(e)[:50])
        except:
            pass
        return False

if __name__ == "__main__":
    ejecutar_analisis_completo()