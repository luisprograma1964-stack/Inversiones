"""
Módulo de mantenimiento previo.
Se ejecuta al inicio del pipeline para procesar tareas manuales pendientes aprobadas por el usuario,
tales como la integración de sugerencias de sinónimos.
"""
import pandas as pd
import auth_google
import config
import logging_config
import time

logger = logging_config.get_logger(__name__)

def depurar_sugerencias_duplicadas(sh):
    """
    Elimina duplicados y limpia el buzón de sugerencias:
    1. Si una sugerencia PENDIENTE ya existe en CONFIG_SINONIMOS, se marca como PROCESADO.
    2. Si hay múltiples sugerencias PENDIENTE del mismo (TERMINO_SUGERIDO, TICKER_SUGERIDO),
       se conserva únicamente la más reciente como PENDIENTE, y las demás se marcan como PROCESADO.
    3. Si alguna sugerencia tiene el campo ESTADO vacío, se inicializa a PENDIENTE.
    """
    try:
        ws_sugerencias = sh.worksheet(config.WS_SUGERENCIAS_SINONIMOS)
        ws_sinonimos = sh.worksheet(config.WS_CONFIG_SINONIMOS)
        
        datos_sugerencias = ws_sugerencias.get_all_records()
        if not datos_sugerencias:
            logger.info("    [+] No hay sugerencias de sinónimos para depurar.")
            return
            
        df_sug = pd.DataFrame(datos_sugerencias)
        # Guardar columnas originales en el casing correcto
        columnas_originales = list(df_sug.columns)
        
        # Trabajar internamente con columnas normalizadas a mayúsculas
        df_sug.columns = [str(c).strip().upper() for c in df_sug.columns]
        
        # Verificar columnas requeridas
        columnas_requeridas = ['TERMINO_SUGERIDO', 'TICKER_SUGERIDO', 'ESTADO']
        for col in columnas_requeridas:
            if col not in df_sug.columns:
                logger.warning(f"    [!] Falta columna requerida '{col}' en SUGERENCIAS_SINONIMOS. Omitiendo depuración.")
                return

        # Cargar sinónimos actuales de CONFIG_SINONIMOS
        datos_sinonimos = ws_sinonimos.get_all_records()
        sinonimos_activos = set()
        if datos_sinonimos:
            df_sin = pd.DataFrame(datos_sinonimos)
            df_sin.columns = [str(c).strip().upper() for c in df_sin.columns]
            if 'TICKER' in df_sin.columns and 'SINONIMOS' in df_sin.columns:
                for idx, row in df_sin.iterrows():
                    ticker = str(row['TICKER']).strip().upper()
                    sinonimos_str = str(row['SINONIMOS']).strip()
                    if ticker and sinonimos_str:
                        for s in sinonimos_str.split(','):
                            s_clean = s.strip().upper()
                            if s_clean:
                                sinonimos_activos.add((s_clean, ticker))
        # Cargar tickers válidos del Maestro de Activos
        ws_maestro = sh.worksheet(config.WS_MAESTRO_ACTIVOS)
        datos_maestro = ws_maestro.get_all_records()
        tickers_validos = set()
        if datos_maestro:
            df_maestro = pd.DataFrame(datos_maestro)
            df_maestro.columns = [str(c).strip().upper() for c in df_maestro.columns]
            if 'TICKER_ID' in df_maestro.columns:
                tickers_validos = set(df_maestro['TICKER_ID'].astype(str).str.strip().str.upper().unique())

        # Asegurar que el estado no contenga nulos/vacíos y sea string normalizado
        df_sug['ESTADO'] = df_sug['ESTADO'].astype(str).str.strip().str.upper()
        # Reemplazar valores vacíos o nulos por PENDIENTE
        df_sug.loc[df_sug['ESTADO'] == '', 'ESTADO'] = 'PENDIENTE'
        df_sug.loc[df_sug['ESTADO'] == 'NAN', 'ESTADO'] = 'PENDIENTE'

        # Recorremos de abajo hacia arriba (el más nuevo primero)
        vistos_pendientes = set()
        cambios = 0
        
        for idx in reversed(df_sug.index):
            row = df_sug.loc[idx]
            estado = row['ESTADO']
            
            if estado == 'PENDIENTE':
                termino = str(row['TERMINO_SUGERIDO']).strip().upper()
                ticker = str(row['TICKER_SUGERIDO']).strip().upper()
                
                if not termino or not ticker:
                    continue
                
                # Caso 0: Ticker sugerido no existe en el Maestro de Activos (Ticker inválido)
                if ticker not in tickers_validos:
                    df_sug.at[idx, 'ESTADO'] = 'PROCESADO'
                    cambios += 1
                    logger.info(f"    [+] Depurado (Ticker '{ticker}' inválido/no en maestro): '{termino}' marcado como PROCESADO.")
                    continue
                
                # Caso 1: Ya existe en CONFIG_SINONIMOS
                if (termino, ticker) in sinonimos_activos:
                    df_sug.at[idx, 'ESTADO'] = 'PROCESADO'
                    cambios += 1
                    logger.info(f"    [+] Depurado (Ya existe en config): '{termino}' -> {ticker} marcado como PROCESADO.")
                
                # Caso 2: Es un duplicado pendiente (ya vimos uno más nuevo)
                elif (termino, ticker) in vistos_pendientes:
                    df_sug.at[idx, 'ESTADO'] = 'PROCESADO'
                    cambios += 1
                    logger.info(f"    [+] Depurado (Duplicado antiguo): '{termino}' -> {ticker} marcado como PROCESADO.")
                
                else:
                    vistos_pendientes.add((termino, ticker))

        if cambios > 0:
            logger.info(f"    [*] Aplicando depuración sobre {cambios} filas en SUGERENCIAS_SINONIMOS...")
            # Restaurar las columnas al casing original
            df_sug.columns = columnas_originales
            
            # Sobrescribir hoja
            ws_sugerencias.clear()
            ws_sugerencias.update(range_name='A1', values=[columnas_originales] + df_sug.values.tolist())
            logger.info("    [OK] Depuración guardada en Google Sheets.")
        else:
            logger.info("    [+] No se detectaron sugerencias pendientes duplicadas.")

    except Exception as e:
        logger.error(f"    [!] Error en depurar_sugerencias_duplicadas: {e}")

def procesar_sinonimos_aprobados(sh):
    """
    Busca sugerencias con ESTADO='APROBADO', las añade a CONFIG_SINONIMOS,
    y cambia el estado de las procesadas (tanto Aprobadas como Rechazadas) a 'PROCESADO'.
    """
    try:
        ws_sugerencias = sh.worksheet(config.WS_SUGERENCIAS_SINONIMOS)
        ws_sinonimos = sh.worksheet(config.WS_CONFIG_SINONIMOS)
        
        datos_sugerencias = ws_sugerencias.get_all_records()
        if not datos_sugerencias:
            logger.info("    [+] No hay sugerencias de sinónimos para procesar.")
            return

        df_sug = pd.DataFrame(datos_sugerencias)
        # Normalizar columnas
        df_sug.columns = [str(c).strip().upper() for c in df_sug.columns]
        
        if 'ESTADO' not in df_sug.columns:
            logger.warning("    [!] La columna ESTADO no existe en SUGERENCIAS_SINONIMOS.")
            return

        # Filtrar pendientes de procesar
        # Queremos procesar APROBADO (se añade y se cambia a PROCESADO)
        # y RECHAZADO (no se añade, pero se cambia a PROCESADO)
        filas_a_procesar = df_sug[df_sug['ESTADO'].astype(str).str.strip().str.upper().isin(['APROBADO', 'RECHAZADO'])]
        
        if filas_a_procesar.empty:
            logger.info("    [+] No hay sinónimos pendientes de procesar.")
            return
            
        logger.info(f"    [*] Se encontraron {len(filas_a_procesar)} sugerencias con estado APROBADO/RECHAZADO.")
        
        # Obtener los sinónimos actuales
        datos_sinonimos = ws_sinonimos.get_all_records()
        df_sin = pd.DataFrame(datos_sinonimos)
        if df_sin.empty:
            df_sin = pd.DataFrame(columns=['TICKER', 'SINONIMOS'])
        else:
            df_sin.columns = [str(c).strip().upper() for c in df_sin.columns]
            
        # Asegurar que existan las columnas
        for col in ['TICKER', 'SINONIMOS']:
            if col not in df_sin.columns:
                df_sin[col] = ""

        # Normalizar TICKER para búsqueda
        df_sin['TICKER_KEY'] = df_sin['TICKER'].astype(str).str.strip().str.upper()

        nuevos_agregados = 0
        filas_modificadas_indices = []

        for idx, row in filas_a_procesar.iterrows():
            estado = str(row.get('ESTADO', '')).strip().upper()
            
            if estado == 'APROBADO':
                termino = str(row.get('TERMINO_SUGERIDO', '')).strip()
                ticker = str(row.get('TICKER_SUGERIDO', '')).strip().upper()
                
                if termino and ticker:
                    # Buscar si el ticker ya existe
                    mask = df_sin['TICKER_KEY'] == ticker
                    if mask.any():
                        # Obtener índice de la fila existente
                        idx_sin = df_sin[mask].index[0]
                        sinonimos_actuales = str(df_sin.at[idx_sin, 'SINONIMOS']).strip()
                        
                        # Verificamos si el término ya está en la lista para evitar duplicados
                        lista_actual = [s.strip().upper() for s in sinonimos_actuales.split(',') if s.strip()]
                        if termino.upper() not in lista_actual:
                            # Añadir a la lista
                            if sinonimos_actuales:
                                df_sin.at[idx_sin, 'SINONIMOS'] = f"{sinonimos_actuales}, {termino}"
                            else:
                                df_sin.at[idx_sin, 'SINONIMOS'] = termino
                            nuevos_agregados += 1
                    else:
                        # Si no existe, crear nueva fila
                        nueva_fila = pd.DataFrame([{'TICKER': ticker, 'SINONIMOS': termino, 'TICKER_KEY': ticker}])
                        df_sin = pd.concat([df_sin, nueva_fila], ignore_index=True)
                        nuevos_agregados += 1

            # Anotar el índice de sugerencia para actualizar en Sheets (+2 por encabezado y 0-index)
            # idx es el index del dataframe original de pandas, correspondiente a fila de Google Sheets: idx + 2
            filas_modificadas_indices.append(idx + 2)

        # Si hubo aprobados, guardar la tabla de sinónimos completa
        if nuevos_agregados > 0:
            logger.info(f"    [*] Añadiendo {nuevos_agregados} nuevos términos a CONFIG_SINONIMOS...")
            # Asegurar que TICKER sea string para evitar errores de comparación al ordenar (ej: 9999 vs 'AAPL')
            df_sin['TICKER'] = df_sin['TICKER'].astype(str)
            df_sin = df_sin.sort_values('TICKER')
            ws_sinonimos.clear()
            ws_sinonimos.update(range_name='A1', values=[['TICKER', 'SINONIMOS']] + df_sin[['TICKER', 'SINONIMOS']].values.tolist())

        # Actualizar los estados en la hoja SUGERENCIAS_SINONIMOS a PROCESADO
        if filas_modificadas_indices:
            logger.info(f"    [*] Actualizando el estado a PROCESADO en {len(filas_modificadas_indices)} filas...")
            # Encontrar el índice de la columna ESTADO
            headers = ws_sugerencias.row_values(1)
            try:
                col_estado_idx = headers.index('ESTADO') + 1
            except ValueError:
                # Si no está ESTADO, no podemos actualizar
                return
                
            # Para evitar múltiples llamadas a la API si hay muchas filas, 
            # podemos preparar un lote de actualizaciones (batch_update)
            requests = []
            for num_fila in filas_modificadas_indices:
                requests.append({
                    "updateCells": {
                        "range": {
                            "sheetId": ws_sugerencias.id,
                            "startRowIndex": num_fila - 1,
                            "endRowIndex": num_fila,
                            "startColumnIndex": col_estado_idx - 1,
                            "endColumnIndex": col_estado_idx
                        },
                        "rows": [
                            {
                                "values": [{"userEnteredValue": {"stringValue": "PROCESADO"}}]
                            }
                        ],
                        "fields": "userEnteredValue"
                    }
                })
            
            if requests:
                sh.batch_update({"requests": requests})
                
        logger.info(f"    [OK] Procesamiento de sinónimos completado. Nuevos términos integrados: {nuevos_agregados}")

    except Exception as e:
        logger.error(f"    [!] Error en procesar_sinonimos_aprobados: {e}")

def ejecutar_mantenimiento_previo():
    """
    Función orquestadora de los chequeos pre-corrida.
    """
    logger.info("==================================================")
    logger.info("[PASO 0.5] INICIANDO MANTENIMIENTO PREVIO")
    logger.info("==================================================")
    t_inicio = time.time()
    
    sh = auth_google.conectar()
    if not sh:
        logger.error("No se pudo conectar a Google Sheets para mantenimiento previo.")
        return False
        
    try:
        # Tarea 1: Depurar sugerencias pendientes duplicadas
        logger.info("[*] Depurando sugerencias duplicadas y obsoletas...")
        depurar_sugerencias_duplicadas(sh)
        
        # Tarea 2: Procesar sugerencias de sinónimos aprobadas
        logger.info("[*] Revisando aprobaciones de sinónimos...")
        procesar_sinonimos_aprobados(sh)
        
        # (Futuras tareas pre-corrida se pueden añadir aquí)
        
    except Exception as e:
        logger.error(f"[!] Error general en mantenimiento previo: {e}")
        return False
        
    duracion = (time.time() - t_inicio) / 60
    logger.info(f"[OK] MANTENIMIENTO PREVIO COMPLETADO EN {duracion:.2f} min")
    return True

if __name__ == "__main__":
    logging_config.setup_logging()
    ejecutar_mantenimiento_previo()
