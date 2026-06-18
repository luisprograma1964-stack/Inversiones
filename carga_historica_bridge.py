"""
Módulo de Sincronización Incremental (Bridge).
Se encarga de descargar la cotización histórica diaria de los activos desde
distintas fuentes (como Google Finance o DolarAPI) y anexar solo los días
faltantes en la hoja HISTORICO_VALORES.
"""
import requests  
import gspread
import pandas as pd
import time
import auth_google
import config
import procesamiento
import logging
import logging_config
from datetime import datetime, timedelta

# --- CONFIGURACIÓN LOCAL ---
PROCESO_ID = "CARGA_DATOS_BRIDGE"
ETIQUETA_FUENTE = "GF_BRIDGE"


def actualizar_maestro_lote(ws_maestro, tickers_exitosos):
    """Actualiza la columna ULTIMA_ACTUALIZ en lote para reducir llamadas a la API."""
    if not tickers_exitosos:
        return
    
    ahora_completo = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger = logging.getLogger('inversiones')
    try:
        # 1. Obtener todos los datos del maestro
        # Usamos get_all_values para tener la matriz completa incluyendo encabezados
        raw_data = ws_maestro.get_all_values()
        if not raw_data:
            return
            
        header = [str(c).strip().upper() for c in raw_data[0]]
        try:
            col_idx = header.index('ULTIMA_ACTUALIZ')
            ticker_idx = header.index('TICKER_ID')
        except ValueError:
            logger.warning("No se encontraron columnas 'TICKER_ID' o 'ULTIMA_ACTUALIZ' en el Maestro.")
            return

        # 2. Modificar registros en memoria
        modificado = False
        for i in range(1, len(raw_data)):
            t_id = str(raw_data[i][ticker_idx]).strip().upper()
            if t_id in tickers_exitosos:
                raw_data[i][col_idx] = ahora_completo
                modificado = True
        
        # 3. Escribir de vuelta la matriz completa (1 sola llamada de escritura)
        if modificado:
            ws_maestro.update(values=raw_data, range_name='A1')
            logger.info(f"    [*] Maestro actualizado en lote ({len(tickers_exitosos)} activos).")
            
    except Exception as e:
        logger.warning(f"Error actualizando maestro en lote: {e}")

def ejecutar_carga_bridge():
    """
    Orquesta la sincronización incremental de datos históricos en paralelo.
    
    Esta función se encarga de:
    1. Leer los activos configurados para carga vía "GF_BRIDGE" en el maestro.
    2. Determinar la última fecha en que se obtuvieron datos para cada activo.
    3. Agrupar las consultas y escribir todas las fórmulas =GOOGLEFINANCE en paralelo
       horizontalmente en la hoja temporal WS_DOWNLOAD_BUFFER.
    4. Realizar una única espera de 20 segundos para que se resuelvan todas en paralelo.
    5. Descargar todo el buffer en bloque, parsear y guardar en HISTORICO_VALORES.
    """
    logging.getLogger('inversiones').info(f"[{datetime.now().strftime('%H:%M:%S')}] >>> Iniciando Sincronización Bridge...")
    t_inicio = time.time()
    
    sh = auth_google.conectar()
    if not sh:
        logging.getLogger('inversiones').error("ERROR: No se pudo conectar con Google Sheets.")
        return False

    todas_las_filas_nuevas = []
    ahora = datetime.now()
    tickers_exitosos = set()
    estado_final = "OK"
    detalle_final = ""
    logger = logging.getLogger('inversiones')
    
    try:
        ws_maestro = sh.worksheet(config.WS_MAESTRO_ACTIVOS)
        ws_historico = sh.worksheet(config.WS_HISTORICO_VALORES)
        ws_buffer = sh.worksheet(config.WS_DOWNLOAD_BUFFER)
        ws_log = sh.worksheet(config.WS_LOG_SISTEMA)
        ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)

        # 0. Verificar si ya se ejecutó con éxito hoy (Fail-Fast)
        if procesamiento.ya_ejecutado_hoy(ws_status, PROCESO_ID):
            logging.getLogger('inversiones').info(f"    [-] Saltando {PROCESO_ID}: ya se ejecutó exitosamente hoy.")
            return True

        # Inicializar logger central y vincular el handler de Sheets
        logger = logging_config.setup_logging(ws_log=ws_log)
        logger = logging_config.get_logger(__name__)

        procesamiento.registrar_log(ws_log, "INFO", "INICIO: Sincronización Bridge", config.ORIGEN_LOG_CARGA)
        
        # Limpieza preventiva: Mantenemos la base liviana antes de buscar nuevos datos
        procesamiento.limpiar_historico_valores(sh)

        procesamiento.actualizar_estado_proceso(ws_status, "PROCESANDO", "Buscando nuevos registros...")

        # 1. Obtener Tickers Activos de esta fuente
        df_maestro = pd.DataFrame(ws_maestro.get_all_records(value_render_option='UNFORMATTED_VALUE'))
        df_maestro.columns = [str(c).strip().upper() for c in df_maestro.columns]
        mask = (df_maestro['ESTADO'] == 'ACTIVO') & (df_maestro['FUENTE_DATA'] == ETIQUETA_FUENTE)
        tickers = df_maestro[mask]['TICKER_ID'].unique().tolist()

        # 2. Cargar históricos actuales para saber desde dónde arrancar
        df_hist = pd.DataFrame(ws_historico.get_all_records(value_render_option='UNFORMATTED_VALUE'))
        
        if not df_hist.empty:
            df_hist.columns = [str(c).strip().upper() for c in df_hist.columns]
            
            if 'FECHA' in df_hist.columns:
                def parse_fecha_bridge(v):
                    if isinstance(v, (int, float)):
                        return pd.to_datetime(v, unit='D', origin='1899-12-30').floor('D')
                    return pd.to_datetime(str(v), errors='coerce')
                
                df_hist['FECHA_DT'] = df_hist['FECHA'].apply(parse_fecha_bridge)
        else:
            # Si está vacío, inicializamos estructura mínima para evitar KeyErrors
            df_hist = pd.DataFrame(columns=['TICKER_ID', 'FECHA', 'FECHA_DT', 'PRECIO_CIERRE'])

        # Limpiar buffer temporal al inicio
        ws_buffer.clear()
        
        # Guardaremos la lista de tickers que procesaremos vía Google Finance
        gf_jobs = []
        
        for t in tickers:
            t_clean = str(t).strip().upper()
            
            # 2.1 Obtener configuración de días desde el maestro con Piso de Seguridad
            row_maestro = df_maestro[df_maestro['TICKER_ID'] == t_clean]
            dias_base = config.MIN_DIAS_HISTORIAL + 60 # Margen extra
            
            if not row_maestro.empty:
                try:
                    val_maestro = int(row_maestro['DIAS_KEEP_HIST'].iloc[0])
                    dias_a_pedir = max(val_maestro, dias_base)
                except:
                    dias_a_pedir = dias_base
            else:
                dias_a_pedir = dias_base

            # 2.2 Determinar fecha de inicio (última fecha en base + 1 día o carga inicial completa)
            df_t_actual = df_hist[df_hist['TICKER_ID'] == t_clean]
            conteo_actual = df_t_actual['FECHA_DT'].nunique() if not df_t_actual.empty else 0
            ultima_f = df_t_actual['FECHA_DT'].max() if not df_t_actual.empty else None
            
            # --- DETECCIÓN DE CORRUPCIÓN DE ESCALA (Mejorada) ---
            if not df_t_actual.empty and t_clean not in ['BTC', 'ETH', 'USDARS']:
                p_numeric = pd.to_numeric(df_t_actual['PRECIO_CIERRE'], errors='coerce')
                p_min, p_max = p_numeric.min(), p_numeric.max()
                if p_min > 0 and (p_max / p_min > 15): # Subimos umbral a 15x para evitar falsos positivos en stocks
                    logger.warning(f"    [!] {t_clean}: Posible corrupción de escala (Ratio {round(p_max/p_min,1)}x). Purgando para recarga limpia...")
                    conteo_actual = 0 # Fuerza la recarga completa
                    ultima_f = None
            
            # Guardamos las fechas que YA existen para no duplicar si forzamos recarga
            fechas_existentes = set()
            if not df_t_actual.empty:
                fechas_existentes = {d.strftime('%Y-%m-%d') for d in df_t_actual['FECHA_DT'] if pd.notnull(d)}

            # Si tenemos menos de lo necesario para el análisis técnico, forzamos carga desde el pasado
            if conteo_actual < config.MIN_DIAS_HISTORIAL:
                start_dt = ahora - timedelta(days=int(dias_a_pedir * 2.0))
                logger.info(f"    [*] {t_clean}: Historial insuficiente ({conteo_actual}/{config.MIN_DIAS_HISTORIAL}). Forzando recarga desde {start_dt.date()}...")
            else:
                start_dt = (ultima_f + timedelta(days=1)) if pd.notnull(ultima_f) else (ahora - timedelta(days=int(dias_a_pedir * 1.5)))

            if start_dt.date() >= ahora.date():
                continue

            f_ini = start_dt.strftime('%Y-%m-%d')
            f_fin = ahora.strftime('%Y-%m-%d')

            # --- CASO ESPECIAL: USDARS (Dólar API) ---
            if t_clean == "USDARS":
                try:
                    res = requests.get("https://dolarapi.com/v1/dolares/oficial")
                    precio_val = float(res.json()['venta'])
                    
                    temp_date = start_dt.date()
                    hoy_date = ahora.date()
                    
                    while temp_date <= hoy_date:
                        f_iso = temp_date.strftime('%Y-%m-%d')
                        if f_iso not in fechas_existentes:
                            todas_las_filas_nuevas.append([
                                t_clean, f_iso,
                                precio_val, 0, precio_val, precio_val
                            ])
                        temp_date += timedelta(days=1)
                    tickers_exitosos.add(t_clean)
                except Exception as e:
                    procesamiento.registrar_log(ws_log, "ERROR", f"Error USDARS: {e}", config.ORIGEN_LOG_CARGA)

            # --- CASO GENERAL: Google Finance ---
            else:
                formula = f'=GOOGLEFINANCE("{t_clean}"; "all"; "{f_ini}"; "{f_fin}")'
                gf_jobs.append({
                    'ticker': t_clean,
                    'formula': formula,
                    'fechas_existentes': fechas_existentes
                })

        # 3. Descargar fórmulas de Google Finance en paralelo
        if gf_jobs:
            logger.info(f"    [*] Preparando descarga en paralelo para {len(gf_jobs)} tickers...")
            
            # Construir fila horizontal de fórmulas espaciadas por 7 columnas
            row_formulas = []
            for job in gf_jobs:
                row_formulas.append(job['formula'])
                row_formulas.extend(["", "", "", "", "", ""]) # Spacing de 6 celdas vacías
            
            ws_buffer.update(range_name='A1', values=[row_formulas], raw=False)

            logger.info(f"    [*] Enviadas fórmulas. Iniciando polling (timeout {config.BRIDGE_POLL_TIMEOUT_SECONDS}s)...")
            start_poll = time.time()
            data_buffer = []

            # Inicializar estados de trabajo
            for job in gf_jobs:
                job['state'] = 'pending'  # pending, ready, error

            # Poll hasta que todas estén ready o timeout
            while True:
                try:
                    data_buffer = ws_buffer.get_all_values(value_render_option='UNFORMATTED_VALUE')
                except Exception as e:
                    procesamiento.registrar_log(ws_log, 'WARNING', f'Error leyendo buffer: {e}', config.ORIGEN_LOG_CARGA)
                    logger.warning(f"Error leyendo buffer: {e}")
                    data_buffer = []

                if data_buffer and len(data_buffer) > 0:
                    header_row = data_buffer[0]
                    for idx, job in enumerate(gf_jobs):
                        if job.get('state') in ('ready', 'error'):
                            continue
                        col_start = idx * 7
                        if len(header_row) > col_start:
                            cell = str(header_row[col_start]).strip()
                            if cell.upper() == 'DATE':
                                job['state'] = 'ready'
                            elif cell.startswith('#'):
                                # Podría ser #N/A u otro error; dejaremos en pending para intentar hasta timeout
                                job['state'] = 'pending'
                            elif cell == '':
                                job['state'] = 'pending'
                            else:
                                # Valor inesperado, mantenemos pending
                                job['state'] = 'pending'
                # Comprobar si quedan pendientes
                pending_exists = any(j.get('state') == 'pending' for j in gf_jobs)
                if not pending_exists:
                    break
                if time.time() - start_poll > config.BRIDGE_POLL_TIMEOUT_SECONDS:
                    # Time out: marcar pendientes como error
                    for j in gf_jobs:
                        if j.get('state') == 'pending':
                            j['state'] = 'error'
                    procesamiento.registrar_log(ws_log, 'WARNING', f'Timeout polling GOOGLEFINANCE after {config.BRIDGE_POLL_TIMEOUT_SECONDS}s', config.ORIGEN_LOG_CARGA)
                    logger.warning(f"Timeout polling GOOGLEFINANCE after {config.BRIDGE_POLL_TIMEOUT_SECONDS}s")
                    break
                time.sleep(config.BRIDGE_POLL_INTERVAL_SECONDS)
            
            for idx, job in enumerate(gf_jobs):
                t_clean = job['ticker']
                fechas_existentes = job['fechas_existentes']
                col_start = idx * 7

                state = job.get('state', 'error')
                if state != 'ready':
                    # No se pudieron obtener datos para este ticker
                    err_msg = '(no data or timeout)'
                    if data_buffer and len(data_buffer) > 0 and len(data_buffer[0]) > col_start:
                        err_msg = str(data_buffer[0][col_start])
                    procesamiento.registrar_log(ws_log, 'WARNING', f'{t_clean}: No data from GOOGLEFINANCE ({err_msg})', config.ORIGEN_LOG_CARGA)
                    logger.warning(f"        [!] {t_clean}: No se obtuvieron datos ({err_msg})")
                    continue

                if len(data_buffer) > 0:
                    header_row = data_buffer[0]
                    # Verificar cobertura de columnas
                    if len(header_row) > col_start:
                        first_header_cell = str(header_row[col_start]).strip().upper()
                        if first_header_cell == 'DATE':
                            conteo_ticker = 0
                            for row in data_buffer[1:]:
                                if len(row) > col_start + 5:
                                    val_fecha = row[col_start]
                                    if val_fecha == '' or val_fecha is None or str(val_fecha).startswith('#'):
                                        continue
                                    try:
                                        # Parsear fecha
                                        if str(val_fecha).replace('.', '').isdigit():
                                            dt_obj = datetime(1899, 12, 30) + timedelta(days=float(val_fecha))
                                        else:
                                            raw_fecha = str(val_fecha).split()[0]
                                            try:
                                                dt_obj = pd.to_datetime(raw_fecha, format='%Y-%m-%d')
                                            except:
                                                dt_obj = pd.to_datetime(raw_fecha, dayfirst=True)

                                        f_nivelada = dt_obj.strftime('%Y-%m-%d')

                                        if f_nivelada in fechas_existentes:
                                            continue

                                        close = row[col_start + 4]
                                        high = row[col_start + 2]
                                        low = row[col_start + 3]
                                        vol = row[col_start + 5] if row[col_start + 5] != '' else 0

                                        # Casteo seguro
                                        if not all(isinstance(x, (int, float)) for x in [close, high, low, vol]):
                                            try:
                                                close = float(close)
                                                high = float(high)
                                                low = float(low)
                                                vol = int(float(vol))
                                            except:
                                                continue

                                        todas_las_filas_nuevas.append([
                                            t_clean, f_nivelada,
                                            float(close),
                                            int(vol),
                                            float(high),
                                            float(low)
                                        ])
                                        conteo_ticker += 1
                                    except Exception:
                                        continue

                            logger.info(f"        [OK] {t_clean}: {conteo_ticker} filas nuevas preparadas.")
                            tickers_exitosos.add(t_clean)

        if todas_las_filas_nuevas:
            logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] Grabando {len(todas_las_filas_nuevas)} registros en HISTORICO_VALORES...")
            ws_historico.append_rows(todas_las_filas_nuevas, value_input_option='USER_ENTERED')
            registros_totales = len(todas_las_filas_nuevas)
        else:
            registros_totales = 0

        # 4. Actualizar el maestro en lote al final (Eficiencia de API)
        actualizar_maestro_lote(ws_maestro, tickers_exitosos)

        detalle_final = f"Sincronizados {registros_totales} registros en {len(tickers_exitosos)} activos."

    except Exception as e:
        import traceback
        traceback.print_exc()
        estado_final = "ERROR"
        detalle_final = f"Falla: {str(e)[:50]}"
        procesamiento.registrar_log(ws_log, "CRITICAL", f"Error Bridge: {str(e)}", config.ORIGEN_LOG_CARGA)
    
    finally:
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        try:
            procesamiento.actualizar_estado_proceso(ws_status, estado_final, detalle_final, tiempo_ejecucion=duracion)
            procesamiento.registrar_log(ws_log, "INFO", f"FIN: {detalle_final}", config.ORIGEN_LOG_CARGA)
        except:
            pass
        if logger:
            logger.info(f">>> {detalle_final}")
        return estado_final == "OK"

if __name__ == "__main__":
    ejecutar_carga_bridge()