"""
Librería de utilidades compartidas para el sistema.
Provee funciones comunes como el registro centralizado de logs,
actualización de semáforos de estado (ESTADO_PROCESOS) y rutinas
de scraping/captura de datos desde distintas fuentes web o APIs.
"""
import requests
import re
import time
from datetime import datetime
import config
import os
import inspect
import numpy as np
import pandas as pd
import logging_config

logger = logging_config.get_logger(__name__)

def limpiar_serie_numerica(serie):
    """
    Convierte una serie de strings con formatos monetarios variados a float64.
    Maneja inteligentemente '1.234,56', '1,234.56', '$1234' y limpia espacios.
    """
    def _convertir(val):
        if pd.isna(val) or val == '': return np.nan
        s = str(val).strip().replace('$', '').replace(' ', '')
        if not s: return np.nan
        
        # Caso 1: Tiene puntos y comas (ej: 1.234,56 o 1,234.56)
        if '.' in s and ',' in s:
            if s.rfind('.') > s.rfind(','): # Formato US: 1,234.56
                s = s.replace(',', '')
            else: # Formato AR: 1.234,56
                s = s.replace('.', '').replace(',', '.')
        # Caso 2: Solo comas (ej: 1234,56 o 1,234)
        elif ',' in s:
            partes = s.split(',')
            if len(partes[-1]) == 3 and len(partes) > 1: # Es separador de miles: 1,234
                s = s.replace(',', '')
            else: # Es separador decimal: 1234,56
                s = s.replace(',', '.')
        # Caso 3: Solo puntos (ej: 1.234 o 1.234.567)
        elif '.' in s:
            partes = s.split('.')
            # Si hay más de un punto, son miles: 1.234.567
            if len(partes) > 2:
                s = s.replace('.', '')
            # Si hay un solo punto y 3 dígitos después, es muy probable que sea miles (formato AR)
            elif len(partes) == 2 and len(partes[1]) == 3:
                s = s.replace('.', '')
        return s

    return pd.to_numeric(serie.apply(_convertir), errors='coerce')

def registrar_log(ws_log, nivel, mensaje, origen=None):
    """
    Registra un evento o mensaje en la hoja LOG_SISTEMA de Google Sheets.
    
    Argumentos:
        ws_log (Worksheet): Objeto de la hoja de cálculo destinada a los logs.
        nivel (str): Nivel de severidad del log (ej. 'INFO', 'WARNING', 'ERROR', 'CRITICAL').
        mensaje (str): El texto del mensaje que se desea registrar.
        origen (str, opcional): El identificador del proceso. Si es None, detecta automáticamente
                                el nombre del archivo de Python que está llamando a la función.
    """
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Detección automática del script origen
    if origen is None:
        try:
            # Extrae el nombre del archivo desde donde se llamó a la función (el stack anterior)
            frame = inspect.stack()[1]
            origen = os.path.basename(frame.filename).replace('.py', '')
        except Exception:
            # Fallback en caso de que falle la detección
            origen = getattr(config, 'ORIGEN_LOG', 'proceso_desconocido')

    # Implementación de reintentos para manejar cuota 429
    for intento in range(2):
        try:
            ws_log.append_row([ahora, nivel, origen, mensaje])
            return # Éxito
        except Exception as e:
            error_str = str(e)
            if "429" in error_str and intento == 0:
                time.sleep(2) # Espera de cortesía antes de reintentar
                continue
            
            # IMPORTANTE: No usar 'logger' aquí para evitar bucle infinito si falla Sheets
            print(f"[{ahora}] [CRITICAL] Fallo físico en LOG_SISTEMA: {error_str}")
            break

def filtrar_anomalias(nombre_dato, lista_valores, ws_log):
    """
    Filtra y descarta valores numéricos que se desvían significativamente del promedio.
    
    Calcula el promedio inicial de la lista y remueve aquellos valores cuyo desvío
    porcentual respecto al promedio supera el UMBRAL_ANOMALIA definido en la configuración.
    Los descartes se registran como WARNING en el log del sistema.
    
    Argumentos:
        nombre_dato (str): Nombre del dato o variable que se está evaluando.
        lista_valores (list): Lista de valores numéricos obtenidos de diferentes fuentes.
        ws_log (Worksheet): Objeto de la hoja de cálculo de logs.
        
    Retorna:
        list: Una nueva lista que contiene solo los valores que están dentro del rango aceptable.
    """
    if len(lista_valores) < 3:
        return lista_valores 

    promedio_sucio = sum(lista_valores) / len(lista_valores)
    lista_limpia = []
    
    for v in lista_valores:
        desvio = abs(v - promedio_sucio) / promedio_sucio
        if desvio <= config.UMBRAL_ANOMALIA:
            lista_limpia.append(v)
        else:
            msg = f"Anomalía en {nombre_dato}: Valor {v} descartado (Desvío: {round(desvio*100, 2)}%)"
            registrar_log(ws_log, "WARNING", msg)
    
    return lista_limpia

def capturar_dato(url, campo_buscado):
    """
    Extrae un valor numérico específico desde una URL (ya sea una API JSON o una página Web).
    
    Esta función contiene lógica específica para parsear respuestas de diferentes
    fuentes conocidas como BCRA, ArgentinaDatos, Bluelytics y CriptoYa, así como un
    mecanismo genérico para navegar diccionarios o listas buscando el 'campo_buscado'.
    
    Argumentos:
        url (str): La dirección web o endpoint de la API a consultar.
        campo_buscado (str): El nombre del campo o identificador clave a extraer de la respuesta.
        
    Retorna:
        tuple: (valor_float, mensaje_de_estado).
               Si es exitoso, retorna el número y "OK".
               Si falla, retorna None y el mensaje de error correspondiente.
    """
    try:
        url_clean = str(url).strip()
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url_clean, headers=headers, timeout=15)
        
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"

        if "bcra.gob.ar" in url_clean:
            match = re.search(r'Unidad de Valor.*?(\d{1,3}(?:\.\d{3})*,\d{2})', r.text, re.DOTALL)
            if match:
                valor_str = match.group(1).replace('.', '').replace(',', '.')
                return float(valor_str), "OK"
            return None, "UVA no hallado en BCRA"

        data = r.json()
        
        if "argentinadatos" in url_clean.lower():
            if isinstance(data, list) and len(data) > 0:
                return float(data[-1].get('valor', 0)), "OK"

        if "bluelytics" in url_clean.lower():
            return float(data['blue']['value_sell']), "OK"
        
        if "criptoya" in url_clean.lower():
            valor = data.get(campo_buscado)
            if isinstance(valor, dict):
                return float(valor.get('ask') or valor.get('venta', 0)), "OK"
            return float(valor), "OK"

        if isinstance(data, list):
            for item in data:
                if str(item.get('casa', '')).lower() == str(campo_buscado).lower() or \
                   str(item.get('nombre', '')).lower() == str(campo_buscado).lower():
                    return float(item.get('venta') or item.get('valor', 0)), "OK"
        
        valor = data.get(campo_buscado)
        if valor is not None:
            if isinstance(valor, dict):
                valor = valor.get('venta') or valor.get('valor') or valor.get('precio')
            return float(valor), "OK"
        
        return None, f"Campo '{campo_buscado}' no hallado"
    except Exception as e:
        return None, f"Error técnico: {str(e)}"

def ya_ejecutado_hoy(ws_status, nombre_proceso):
    """
    Consulta la tabla ESTADO_PROCESOS para verificar si un proceso específico
    ya finalizó exitosamente ('OK') en la fecha actual.
    """
    try:
        hoy_str = datetime.now().strftime("%Y-%m-%d")
        data = ws_status.get_all_records()
        for fila in data:
            # Soporta tanto Nombre_Proceso como Proceso_ID por retrocompatibilidad
            nombre = str(fila.get('Nombre_Proceso', fila.get('Proceso_ID', '')))
            fecha = str(fila.get('Fecha/Hora', ''))
            estado = str(fila.get('Estado', '')).upper()
            if nombre == nombre_proceso and hoy_str in fecha and "OK" in estado:
                return True
    except Exception:
        pass
    return False

def actualizar_estado_proceso(ws_status, estado, detalle, nombre_proceso=None, tiempo_ejecucion=None):
    """
    Actualiza el estado de ejecución en la tabla ESTADO_PROCESOS en Google Sheets con texto plano.
    
    Argumentos:
        ws_status (Worksheet): Objeto de la hoja de cálculo de estado de procesos.
        estado (str): Estado actual (ej. 'PROCESANDO', 'OK', 'ERROR').
        detalle (str): Mensaje o detalle adicional.
        nombre_proceso (str, opcional): El identificador del proceso. Si es None, detecta 
                                        automáticamente el nombre del archivo.
        tiempo_ejecucion (str, opcional): Duración del proceso (ej. '12.5s').
    """
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Guardar estados limpios en texto plano
    estado_upper = str(estado).strip().upper()
    if "OK" in estado_upper:
        estado_visual = "OK"
    elif "ERROR" in estado_upper:
        estado_visual = "ERROR"
    elif "PROCESANDO" in estado_upper:
        estado_visual = "PROCESANDO"
    else:
        estado_visual = estado_upper

    if nombre_proceso is None:
        try:
            frame = inspect.stack()[1]
            nombre_proceso = os.path.basename(frame.filename).replace('.py', '')
        except Exception:
            nombre_proceso = getattr(config, 'ORIGEN_LOG', 'proceso_desconocido')
            
    # Intentar hasta 4 veces con una espera progresiva si da error 429 de Sheets API
    for intento in range(4):
        try:
            data = ws_status.get_all_records()
            nueva_fila = [nombre_proceso, ahora, estado_visual, detalle, tiempo_ejecucion if tiempo_ejecucion else ""]
            
            encontrado = False
            for i, fila in enumerate(data, start=2):
                clave_fila = str(fila.get('Nombre_Proceso', fila.get('Proceso_ID', '')))
                if clave_fila == nombre_proceso:
                    ws_status.update(values=[nueva_fila], range_name=f"A{i}:E{i}")
                    encontrado = True
                    break
                    
            if not encontrado:
                ws_status.append_row(nueva_fila)
            return # Éxito total
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                espera = (intento + 1) * 3  # Esperas: 3s, 6s, 9s, 12s
                time.sleep(espera)
                continue
            print(f"!!! Error actualizando ESTADO_PROCESOS: {e}")
            break

def validar_datos_tecnicos(row_dict):
    """
    Realiza un chequeo de cordura financiera sobre los datos técnicos.
    Retorna (True, "") si los datos son aptos, (False, "razón") si detecta anomalías.
    """
    try:
        # 1. Validar RSI (0-100)
        rsi_val = row_dict.get('RSI', '')
        if rsi_val is not None and str(rsi_val).strip() != '':
            try:
                # Convertimos coma a punto para que Python pueda validarlo como float
                rsi = float(str(rsi_val).replace(',', '.'))
            except ValueError:
                return False, f"RSI no es un número válido (Valor: '{rsi_val}')"
            if rsi < 0 or rsi > 100:
                return False, f"RSI fuera de rango lógico (Valor: {rsi})"
        else:
            return False, "RSI ausente o nulo"

        # 2. Validar SMA_200 vs Precio_Cierre (Error de decimales común)
        precio_raw = row_dict.get('PRECIO_CIERRE_VALIDACION') or row_dict.get('PRECIO_ACTUAL')
        sma200_raw = row_dict.get('SMA_200')      # Dato calculado
        
        if precio_raw and sma200_raw:
            precio = float(str(precio_raw).replace(',', '.'))
            sma200 = float(str(sma200_raw).replace(',', '.'))
            # Si la media es 15 veces más grande que el precio, hay un error de escala (estándar 15x).
            if sma200 > 0 and precio > 0 and (sma200 / precio > 15):
                 return False, f"Incongruencia SMA_200 ({sma200}) vs Precio ({precio}). Error de escala."

        # 3. Validar Fibonacci (Detectar errores de cálculo previos)
        fibo = str(row_dict.get('FIBO_RET', ''))
        if "Error" in fibo:
            return False, f"FIBO_RET reportó fallo: {fibo}"
            
        # Validación de magnitud si es numérico (vía split para ignorar "(Golden)")
        try:
            # Remove leading apostrophe if present (from Sheets forcing text)
            clean_fibo_str = fibo.lstrip("'")
            val_fibo_str = clean_fibo_str.split(' ')[0]
            # Manejo de coma decimal para validación de Fibonacci
            if float(val_fibo_str.replace(',', '.')) > 15: 
                return False, f"FIBO_RET fuera de rango lógico ({val_fibo_str})"
        except (ValueError, IndexError):
            pass # Es un texto como "N/A" o "Extensión", se acepta

        return True, "OK"
    except Exception as e:
        return False, f"Error en validación técnica: {e}"

def limpiar_historico_valores(sh, dias_a_mantener=None):
    """
    Limpia la hoja HISTORICO_VALORES, manteniendo solo los 'dias_a_mantener' más recientes
    para cada Ticker_ID. Si dias_a_mantener es None, usa config.MIN_DIAS_HISTORIAL + 20.
    
    Argumentos:
        sh (gspread.Spreadsheet): Objeto del documento completo (Spreadsheet).
        dias_a_mantener (int, opcional): Número de días a mantener por ticker.
                                        Si es None, usa config.MIN_DIAS_HISTORIAL + 20.
    """
    ws_hist = sh.worksheet(config.WS_HISTORICO_VALORES)
    ws_maestro = sh.worksheet(config.WS_MAESTRO_ACTIVOS)
    ws_log = sh.worksheet(config.WS_LOG_SISTEMA)
    ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)

    if ya_ejecutado_hoy(ws_status, "limpieza_historico"):
        logger.info("    [-] Saltando limpieza inteligente de HISTORICO_VALORES (ya ejecutada hoy)")
        return

    t_inicio = time.time()
    
    msg_inicio = "Iniciando limpieza inteligente de HISTORICO_VALORES..."
    logger.info(f"[*] {msg_inicio}")
    registrar_log(ws_log, "INFO", msg_inicio, "limpieza_historico")

    try:
        actualizar_estado_proceso(ws_status, "PROCESANDO", "Limpiando histórico...", "limpieza_historico")
        # 1. Obtener reglas del Maestro
        # Usamos UNFORMATTED_VALUE para obtener números reales, no strings con comas
        df_maestro = pd.DataFrame(ws_maestro.get_all_records(value_render_option='UNFORMATTED_VALUE'))
        df_maestro.columns = [str(c).strip().rstrip('.').upper() for c in df_maestro.columns]
        
        # Crear diccionario de reglas: {TICKER: {'estado': ESTADO, 'dias': DIAS_KEEP_HIST}}
        reglas = {}
        for _, r in df_maestro.iterrows():
            t_id = str(r['TICKER_ID']).strip().upper()
            reglas[t_id] = {
                'activo': str(r['ESTADO']).strip().upper() == 'ACTIVO',
                'dias': int(r['DIAS_KEEP_HIST']) if str(r['DIAS_KEEP_HIST']).isdigit() else (config.MIN_DIAS_HISTORIAL + 20)
            }

        # 2. Procesar Historial
        df_historico = pd.DataFrame(ws_hist.get_all_records(value_render_option='UNFORMATTED_VALUE'))
        if df_historico.empty:
            logger.info("    [!] HISTORICO_VALORES está vacío. Nada que limpiar.")
            return

        df_historico.columns = [str(c).strip().rstrip('.').upper() for c in df_historico.columns]
        total_antes = len(df_historico)
        
        columnas_headers = df_historico.columns.tolist()

        # Manejo robusto de fechas: Google entrega números de serie si usamos UNFORMATTED_VALUE
        def parse_fecha_google(v):
            if isinstance(v, (int, float)): # Es número de serie de Excel/Google
                return pd.to_datetime(v, unit='D', origin='1899-12-30').floor('D')
            return pd.to_datetime(str(v), errors='coerce')

        df_historico['FECHA'] = df_historico['FECHA'].apply(parse_fecha_google)
        df_historico = df_historico.dropna(subset=['FECHA'])

        df_limpio = pd.DataFrame()
        for ticker in df_historico['TICKER_ID'].unique():
            t_upper = str(ticker).strip().upper()
            subyacente = t_upper.replace("BCBA:", "")
            
            # Si el ticker (o su subyacente local de Byma) no está en el maestro o está INACTIVO, se descarta
            if subyacente in reglas and reglas[subyacente]['activo']:
                # PISO DE SEGURIDAD: Aumentamos a +50 para evitar quedarnos cortos por feriados
                limite = max(reglas[subyacente]['dias'], config.MIN_DIAS_HISTORIAL + 50)
                df_t = df_historico[df_historico['TICKER_ID'] == ticker].sort_values('FECHA', ascending=False)
                df_limpio = pd.concat([df_limpio, df_t.head(limite)], ignore_index=True)
            else:
                # Se limpia el historial si el activo no se sigue más
                continue
        
        # Ordenar el DataFrame final para una mejor visualización en Sheets
        df_limpio = df_limpio.sort_values(by=['TICKER_ID', 'FECHA']).reset_index(drop=True)
        
        # Estándar 5: Convertir fechas a string ISO antes de subir a Sheets
        df_limpio['FECHA'] = df_limpio['FECHA'].dt.strftime('%Y-%m-%d')

        eliminados = total_antes - len(df_limpio)
        if eliminados < getattr(config, 'UMBRAL_FILAS_BORRAR_MINIMO', 50):
            msg_skip = f"Saltando escritura de HISTORICO_VALORES: solo se identificaron {eliminados} filas viejas para borrar (umbral mínimo: {getattr(config, 'UMBRAL_FILAS_BORRAR_MINIMO', 50)})."
            logger.info(f"    [-] {msg_skip}")
            registrar_log(ws_log, "INFO", msg_skip, "limpieza_historico")
            duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
            actualizar_estado_proceso(ws_status, "OK", f"Sin cambios significativos ({eliminados} filas)", "limpieza_historico", tiempo_ejecucion=duracion)
            return

        # Escribir los datos limpios en Sheets en lotes
        ws_hist.clear()
        ws_hist.append_row(columnas_headers) # Escribir encabezados

        datos_limpios = df_limpio.values.tolist()

        # Dividir el DataFrame en lotes y escribir
        num_chunks = (len(df_limpio) + config.CHUNK_SIZE_SHEETS - 1) // config.CHUNK_SIZE_SHEETS
        for i in range(num_chunks):
            start_idx = i * config.CHUNK_SIZE_SHEETS
            end_idx = min((i + 1) * config.CHUNK_SIZE_SHEETS, len(df_limpio))
            ws_hist.append_rows(datos_limpios[start_idx:end_idx], value_input_option='USER_ENTERED')

        msg_fin = f"Limpieza completada. Se eliminaron {eliminados} filas. Quedan {len(df_limpio)} registros."
        logger.info(f"[OK] {msg_fin}")
        registrar_log(ws_log, "INFO", msg_fin, "limpieza_historico")
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        actualizar_estado_proceso(ws_status, "OK", msg_fin, "limpieza_historico", tiempo_ejecucion=duracion)
    except Exception as e:
        registrar_log(ws_log, "ERROR", f"Error durante la limpieza de HISTORICO_VALORES: {e}", "limpieza_historico")
        actualizar_estado_proceso(ws_status, "ERROR", str(e)[:50], "limpieza_historico", tiempo_ejecucion="0.00 min")

def limpiar_historial_veredictos(sh, dias_a_mantener=None):
    """
    Limpia la hoja HISTORIAL_VEREDICTOS, manteniendo solo los registros de los últimos X días.
    Evita que el crecimiento infinito de la hoja ralentice las consultas de la IA.
    """
    ws_reporte = sh.worksheet(config.WS_HISTORIAL_VEREDICTOS)
    ws_log = sh.worksheet(config.WS_LOG_SISTEMA)
    ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)
    
    if dias_a_mantener is None:
        dias_a_mantener = getattr(config, 'DIAS_KEEP_HISTORIAL_VEREDICTOS', 100)

    try:
        t_inicio = time.time()
        data = ws_reporte.get_all_records()
        total_actual = len(data)
        
        # Verificar si ya se limpió hoy consultando ESTADO_PROCESOS
        ya_limpio_hoy = ya_ejecutado_hoy(ws_status, "limpieza_historial_veredictos")

        # Solo limpiar si supera el umbral o si es el primer run del día
        if total_actual < config.UMBRAL_FILAS_REPORTE and ya_limpio_hoy:
            logger.info(f"    [-] Saltando limpieza de reporte (Filas: {total_actual}, ya limpio hoy)")
            return

        msg_inicio = f"Iniciando limpieza de {config.WS_HISTORIAL_VEREDICTOS} ({dias_a_mantener} días)..."
        logger.info(f"[*] {msg_inicio}")
        registrar_log(ws_log, "INFO", msg_inicio, "limpieza_historial_veredictos")

        actualizar_estado_proceso(ws_status, "PROCESANDO", "Limpiando reporte IA...", "limpieza_historial_veredictos")
        if not data:
            actualizar_estado_proceso(ws_status, "OK", "Sin datos para limpiar", "limpieza_historial_veredictos", tiempo_ejecucion="0.00 min")
            return

        df = pd.DataFrame(data)
        df.columns = [c.strip().upper() for c in df.columns]
        total_antes = len(df)

        if 'FECHA_HORA' not in df.columns:
            msg_err = "Columna FECHA_HORA no encontrada en HISTORIAL_VEREDICTOS."
            registrar_log(ws_log, "ERROR", msg_err, "limpieza_historial_veredictos")
            actualizar_estado_proceso(ws_status, "ERROR", msg_err, "limpieza_historial_veredictos", tiempo_ejecucion="0.00 min")
            return

        # Convertir a datetime y filtrar por antigüedad
        df['FECHA_DT'] = pd.to_datetime(df['FECHA_HORA'].astype(str), errors='coerce')
        limite = datetime.now() - pd.Timedelta(days=dias_a_mantener)
        
        df_limpio = df[df['FECHA_DT'] >= limite].copy()
        df_limpio = df_limpio.drop(columns=['FECHA_DT'])
        
        import numpy as np
        df_limpio = df_limpio.replace([np.inf, -np.inf], np.nan).fillna("")

        eliminados = total_antes - len(df_limpio)
        if eliminados < getattr(config, 'UMBRAL_FILAS_BORRAR_MINIMO', 50):
            msg_skip = f"Saltando escritura de HISTORIAL_VEREDICTOS: solo se identificaron {eliminados} filas viejas para borrar (umbral mínimo: {getattr(config, 'UMBRAL_FILAS_BORRAR_MINIMO', 50)})."
            logger.info(f"    [-] {msg_skip}")
            registrar_log(ws_log, "INFO", msg_skip, "limpieza_historial_veredictos")
            duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
            actualizar_estado_proceso(ws_status, "OK", f"Sin cambios significativos ({eliminados} filas)", "limpieza_historial_veredictos", tiempo_ejecucion=duracion)
            return

        # Sobrescribir la hoja con los datos vigentes usando el sistema de lotes
        ws_reporte.clear()
        ws_reporte.append_row(df_limpio.columns.values.tolist())
        
        if not df_limpio.empty:
            num_chunks = (len(df_limpio) + config.CHUNK_SIZE_SHEETS - 1) // config.CHUNK_SIZE_SHEETS
            for i in range(num_chunks):
                start_idx = i * config.CHUNK_SIZE_SHEETS
                end_idx = min((i + 1) * config.CHUNK_SIZE_SHEETS, len(df_limpio))
                ws_reporte.append_rows(df_limpio.iloc[start_idx:end_idx].values.tolist())

        msg_fin = f"Limpieza HISTORIAL_VEREDICTOS completada. Se eliminaron {eliminados} registros."
        logger.info(f"[OK] {msg_fin}")
        registrar_log(ws_log, "INFO", msg_fin, "limpieza_historial_veredictos")
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        actualizar_estado_proceso(ws_status, "OK", msg_fin, "limpieza_historial_veredictos", tiempo_ejecucion=duracion)
    except Exception as e:
        registrar_log(ws_log, "ERROR", f"Error en limpieza_historial_veredictos: {e}", "limpieza_historial_veredictos")
        actualizar_estado_proceso(ws_status, "ERROR", str(e)[:50], "limpieza_historial_veredictos", tiempo_ejecucion="0.00 min")

def limpiar_log_sistema(sh, dias_a_mantener=None):
    """
    Limpia la hoja LOG_SISTEMA, manteniendo solo los registros de los últimos X días.
    """
    ws_log_sheet = sh.worksheet(config.WS_LOG_SISTEMA)
    ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)
    
    if dias_a_mantener is None:
        dias_a_mantener = getattr(config, 'DIAS_KEEP_LOG', 100)

    try:
        t_inicio = time.time()
        data = ws_log_sheet.get_all_records()
        if not data:
            return

        df = pd.DataFrame(data)
        df.columns = [c.strip().upper() for c in df.columns]
        total_antes = len(df)

        # Verificar si ya se limpió hoy consultando ESTADO_PROCESOS
        ya_limpio_hoy = ya_ejecutado_hoy(ws_status, "limpieza_log")

        if total_antes < config.UMBRAL_FILAS_LOG and ya_limpio_hoy:
            logger.info(f"    [-] Saltando mantenimiento de logs (Filas: {total_antes}, ya limpio hoy)")
            return
        logger.info(f"[*] Realizando mantenimiento de LOG_SISTEMA (Keep: {dias_a_mantener} días)...")
        actualizar_estado_proceso(ws_status, "PROCESANDO", "Limpiando logs...", "limpieza_log")
        if 'FECHA' not in df.columns:
            actualizar_estado_proceso(ws_status, "ERROR", "Columna FECHA no hallada", "limpieza_log", tiempo_ejecucion="0.00 min")
            return

        # Convertir a datetime y filtrar por antigüedad
        df['FECHA_DT'] = pd.to_datetime(df['FECHA'], errors='coerce')
        limite = datetime.now() - pd.Timedelta(days=dias_a_mantener)
        
        df_limpio = df[df['FECHA_DT'] >= limite].copy()
        df_limpio = df_limpio.drop(columns=['FECHA_DT'])
        
        import numpy as np
        df_limpio = df_limpio.replace([np.inf, -np.inf], np.nan).fillna("")

        eliminados = total_antes - len(df_limpio)
        if eliminados < getattr(config, 'UMBRAL_FILAS_BORRAR_MINIMO', 50):
            msg_skip = f"Saltando escritura de LOG_SISTEMA: solo se identificaron {eliminados} filas viejas para borrar (umbral mínimo: {getattr(config, 'UMBRAL_FILAS_BORRAR_MINIMO', 50)})."
            logger.info(f"    [-] {msg_skip}")
            duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
            actualizar_estado_proceso(ws_status, "OK", f"Sin cambios significativos ({eliminados} filas)", "limpieza_log", tiempo_ejecucion=duracion)
            return

        # Sobrescribir la hoja con los datos vigentes usando el sistema de lotes
        ws_log_sheet.clear()
        ws_log_sheet.append_row(df_limpio.columns.values.tolist())
        
        if not df_limpio.empty:
            num_chunks = (len(df_limpio) + config.CHUNK_SIZE_SHEETS - 1) // config.CHUNK_SIZE_SHEETS
            for i in range(num_chunks):
                start_idx = i * config.CHUNK_SIZE_SHEETS
                end_idx = min((i + 1) * config.CHUNK_SIZE_SHEETS, len(df_limpio))
                ws_log_sheet.append_rows(df_limpio.iloc[start_idx:end_idx].values.tolist())

        # Registramos la acción de limpieza como el primer log de la nueva etapa
        registrar_log(ws_log_sheet, "INFO", f"Mantenimiento: Se eliminaron {eliminados} logs antiguos (> {dias_a_mantener} días).", "limpieza_log")
        logger.info(f"[OK] Mantenimiento de logs finalizado. {eliminados} filas removidas.")
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        actualizar_estado_proceso(ws_status, "OK", f"Eliminados: {eliminados}", "limpieza_log", tiempo_ejecucion=duracion)
    except Exception as e:
        actualizar_estado_proceso(ws_status, "ERROR", str(e)[:50], "limpieza_log", tiempo_ejecucion="0.00 min")
        logger.exception(f"Error técnico en limpieza_log: {e}")

def verificar_locale_compatible(sh):
    """
    Verifica si el locale de la planilla es compatible con el uso de comas decimales.
    Retorna (True, locale) si es compatible, (False, locale) si no lo es.
    """
    try:
        # Obtener metadatos de la hoja
        metadata = sh.fetch_sheet_metadata()
        locale = metadata.get('properties', {}).get('locale', 'desconocido')
        
        # Lista de locales que usan coma decimal convencionalmente
        locales_coma = [
            'es_AR', 'es_ES', 'es_UY', 'es_PY', 'pt_BR', 
            'it_IT', 'fr_FR', 'de_DE', 'ru_RU'
        ]
        
        if any(l.lower() in locale.lower() for l in locales_coma):
            return True, locale
        else:
            return False, locale
    except Exception as e:
        logger.exception(f"!!! No se pudo verificar el locale: {e}")
        return None, "error"


def limpiar_noticias_descartadas(sh, dias_a_mantener=None):
    """
    Limpia la hoja NOTICIAS_DESCARTADAS, manteniendo solo los registros de los últimos X días.
    """
    ws_noticias = sh.worksheet(config.WS_NOTICIAS_DESCARTADAS)
    ws_log = sh.worksheet(config.WS_LOG_SISTEMA)
    ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)
    
    if dias_a_mantener is None:
        dias_a_mantener = getattr(config, 'DIAS_KEEP_NOTICIAS_DESCARTADAS', 30)

    try:
        t_inicio = time.time()
        # Verificar si ya se limpió hoy
        if ya_ejecutado_hoy(ws_status, "limpieza_noticias_descartadas"):
            logger.info("    [-] Saltando limpieza de NOTICIAS_DESCARTADAS (ya ejecutada hoy)")
            return

        data = ws_noticias.get_all_records()
        total_actual = len(data)
        
        # Solo limpiar si supera el umbral de filas
        if total_actual < getattr(config, 'UMBRAL_FILAS_NOTICIAS_DESCARTADAS', 500):
            logger.info(f"    [-] Saltando limpieza de noticias descartadas (Filas: {total_actual} < {getattr(config, 'UMBRAL_FILAS_NOTICIAS_DESCARTADAS', 500)})")
            return

        logger.info(f"[*] Iniciando limpieza de {config.WS_NOTICIAS_DESCARTADAS} ({dias_a_mantener} días)...")
        actualizar_estado_proceso(ws_status, "PROCESANDO", "Limpiando descartes...", "limpieza_noticias_descartadas")
        
        if not data:
            actualizar_estado_proceso(ws_status, "OK", "Sin datos para limpiar", "limpieza_noticias_descartadas", tiempo_ejecucion="0.00 min")
            return

        df = pd.DataFrame(data)
        df.columns = [c.strip().upper() for c in df.columns]
        total_antes = len(df)

        if 'FECHA' not in df.columns:
            actualizar_estado_proceso(ws_status, "ERROR", "Columna FECHA no hallada", "limpieza_noticias_descartadas", tiempo_ejecucion="0.00 min")
            return

        df['FECHA_DT'] = pd.to_datetime(df['FECHA'], errors='coerce')
        limite = datetime.now() - pd.Timedelta(days=dias_a_mantener)
        
        df_limpio = df[df['FECHA_DT'] >= limite].copy()
        df_limpio = df_limpio.drop(columns=['FECHA_DT'])
        
        import numpy as np
        # Convertir todo a string, o llenar NaNs con string vacío para evitar errores JSON
        df_limpio = df_limpio.fillna("")

        eliminados = total_antes - len(df_limpio)
        if eliminados < getattr(config, 'UMBRAL_FILAS_BORRAR_MINIMO', 50):
            msg_skip = f"Saltando escritura de NOTICIAS_DESCARTADAS: solo se identificaron {eliminados} filas viejas para borrar."
            logger.info(f"    [-] {msg_skip}")
            duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
            actualizar_estado_proceso(ws_status, "OK", f"Sin cambios significativos ({eliminados} filas)", "limpieza_noticias_descartadas", tiempo_ejecucion=duracion)
            return

        # Sobrescribir la hoja
        ws_noticias.clear()
        ws_noticias.append_row(df_limpio.columns.values.tolist())
        
        if not df_limpio.empty:
            num_chunks = (len(df_limpio) + config.CHUNK_SIZE_SHEETS - 1) // config.CHUNK_SIZE_SHEETS
            for i in range(num_chunks):
                start_idx = i * config.CHUNK_SIZE_SHEETS
                end_idx = min((i + 1) * config.CHUNK_SIZE_SHEETS, len(df_limpio))
                ws_noticias.append_rows(df_limpio.iloc[start_idx:end_idx].values.tolist())
                time.sleep(2) # PREVENIR ERROR 429 QUOTA EXCEEDED

        msg_fin = f"Limpieza completada. Se eliminaron {eliminados} descartes viejos."
        logger.info(f"[OK] {msg_fin}")
        registrar_log(ws_log, "INFO", msg_fin, "limpieza_noticias_descartadas")
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        actualizar_estado_proceso(ws_status, "OK", msg_fin, "limpieza_noticias_descartadas", tiempo_ejecucion=duracion)
    except Exception as e:
        actualizar_estado_proceso(ws_status, "ERROR", str(e)[:50], "limpieza_noticias_descartadas", tiempo_ejecucion="0.00 min")
        logger.exception(f"Error técnico en limpieza de descartes: {e}")


def limpiar_sugerencias_sinonimos(sh, dias_a_mantener=None):
    """
    Limpia la hoja SUGERENCIAS_SINONIMOS, manteniendo solo los registros de los últimos X días.
    """
    ws_sugerencias = sh.worksheet(config.WS_SUGERENCIAS_SINONIMOS)
    ws_log = sh.worksheet(config.WS_LOG_SISTEMA)
    ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)
    
    if dias_a_mantener is None:
        dias_a_mantener = getattr(config, 'DIAS_KEEP_SUGERENCIAS_SINONIMOS', 30)

    try:
        t_inicio = time.time()
        # Verificar si ya se limpió hoy
        if ya_ejecutado_hoy(ws_status, "limpieza_sugerencias_sinonimos"):
            logger.info("    [-] Saltando limpieza de SUGERENCIAS_SINONIMOS (ya ejecutada hoy)")
            return

        data = ws_sugerencias.get_all_records()
        total_actual = len(data)
        
        # Solo limpiar si supera el umbral de filas
        if total_actual < getattr(config, 'UMBRAL_FILAS_SUGERENCIAS_SINONIMOS', 100):
            logger.info(f"    [-] Saltando limpieza de sugerencias sinónimos (Filas: {total_actual} < {getattr(config, 'UMBRAL_FILAS_SUGERENCIAS_SINONIMOS', 100)})")
            return

        logger.info(f"[*] Iniciando limpieza de {config.WS_SUGERENCIAS_SINONIMOS} ({dias_a_mantener} días)...")
        actualizar_estado_proceso(ws_status, "PROCESANDO", "Limpiando sugerencias...", "limpieza_sugerencias_sinonimos")
        
        if not data:
            actualizar_estado_proceso(ws_status, "OK", "Sin datos para limpiar", "limpieza_sugerencias_sinonimos", tiempo_ejecucion="0.00 min")
            return

        df = pd.DataFrame(data)
        df.columns = [c.strip().upper() for c in df.columns]
        total_antes = len(df)

        if 'FECHA' not in df.columns:
            actualizar_estado_proceso(ws_status, "ERROR", "Columna FECHA no hallada", "limpieza_sugerencias_sinonimos", tiempo_ejecucion="0.00 min")
            return

        df['FECHA_DT'] = pd.to_datetime(df['FECHA'], errors='coerce')
        limite = datetime.now() - pd.Timedelta(days=dias_a_mantener)
        
        # Conservar registros que no estén PROCESADOS o que sean más recientes que el límite
        df['ESTADO_NORM'] = df['ESTADO'].astype(str).str.strip().str.upper()
        condicion_conservar = (df['ESTADO_NORM'] != 'PROCESADO') | (df['FECHA_DT'] >= limite)
        
        df_limpio = df[condicion_conservar].copy()
        df_limpio = df_limpio.drop(columns=['FECHA_DT', 'ESTADO_NORM'])

        eliminados = total_antes - len(df_limpio)
        if eliminados < getattr(config, 'UMBRAL_FILAS_BORRAR_MINIMO', 50):
            msg_skip = f"Saltando escritura de SUGERENCIAS_SINONIMOS: solo se identificaron {eliminados} filas viejas para borrar."
            logger.info(f"    [-] {msg_skip}")
            duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
            actualizar_estado_proceso(ws_status, "OK", f"Sin cambios significativos ({eliminados} filas)", "limpieza_sugerencias_sinonimos", tiempo_ejecucion=duracion)
            return

        # Sobrescribir la hoja
        ws_sugerencias.clear()
        ws_sugerencias.append_row(df_limpio.columns.values.tolist())
        
        if not df_limpio.empty:
            num_chunks = (len(df_limpio) + config.CHUNK_SIZE_SHEETS - 1) // config.CHUNK_SIZE_SHEETS
            for i in range(num_chunks):
                start_idx = i * config.CHUNK_SIZE_SHEETS
                end_idx = min((i + 1) * config.CHUNK_SIZE_SHEETS, len(df_limpio))
                ws_sugerencias.append_rows(df_limpio.iloc[start_idx:end_idx].values.tolist())

        msg_fin = f"Limpieza completada. Se eliminaron {eliminados} sugerencias viejas."
        logger.info(f"[OK] {msg_fin}")
        registrar_log(ws_log, "INFO", msg_fin, "limpieza_sugerencias_sinonimos")
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        actualizar_estado_proceso(ws_status, "OK", msg_fin, "limpieza_sugerencias_sinonimos", tiempo_ejecucion=duracion)
    except Exception as e:
        actualizar_estado_proceso(ws_status, "ERROR", str(e)[:50], "limpieza_sugerencias_sinonimos", tiempo_ejecucion="0.00 min")
        logger.exception(f"Error técnico en limpieza de sugerencias: {e}")


def limpiar_noticias_sistema(sh, dias_a_mantener=None):
    """
    Limpia la hoja NOTICIAS_SISTEMA, manteniendo solo los registros de los últimos X días.
    """
    ws_noticias = sh.worksheet(config.WS_NOTICIAS_SISTEMA)
    ws_log = sh.worksheet(config.WS_LOG_SISTEMA)
    ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)
    
    if dias_a_mantener is None:
        dias_a_mantener = getattr(config, 'DIAS_KEEP_NOTICIAS_SISTEMA', 30)

    try:
        t_inicio = time.time()
        # Verificar si ya se limpió hoy
        if ya_ejecutado_hoy(ws_status, "limpieza_noticias_sistema"):
            logger.info("    [-] Saltando limpieza de NOTICIAS_SISTEMA (ya ejecutada hoy)")
            return

        # Lectura resiliente con reintentos ante cuota 429
        data = None
        for intento in range(8):
            try:
                data = ws_noticias.get_all_records()
                break
            except Exception as ex:
                if "429" in str(ex):
                    logger.warning(f"    [!] Cuota 429 al leer NOTICIAS_SISTEMA. Reintentando en 15s (Intento {intento+1}/8)...")
                    time.sleep(15)
                else:
                    raise ex
        if data is None:
            logger.error("    [!] No se pudo leer NOTICIAS_SISTEMA tras 8 intentos. Saltando limpieza.")
            return

        total_actual = len(data)
        
        # Solo limpiar si supera el umbral de filas
        if total_actual < getattr(config, 'UMBRAL_FILAS_NOTICIAS_SISTEMA', 500):
            logger.info(f"    [-] Saltando limpieza de noticias aprobadas (Filas: {total_actual} < {getattr(config, 'UMBRAL_FILAS_NOTICIAS_SISTEMA', 500)})")
            return

        logger.info(f"[*] Iniciando limpieza de {config.WS_NOTICIAS_SISTEMA} ({dias_a_mantener} días)...")
        actualizar_estado_proceso(ws_status, "PROCESANDO", "Limpiando noticias aprobadas...", "limpieza_noticias_sistema")
        
        if not data:
            actualizar_estado_proceso(ws_status, "OK", "Sin datos para limpiar", "limpieza_noticias_sistema", tiempo_ejecucion="0.00 min")
            return

        df = pd.DataFrame(data)
        df.columns = [c.strip().upper() for c in df.columns]
        total_antes = len(df)

        if 'FECHA' not in df.columns:
            actualizar_estado_proceso(ws_status, "ERROR", "Columna FECHA no hallada", "limpieza_noticias_sistema", tiempo_ejecucion="0.00 min")
            return

        df['FECHA_DT'] = pd.to_datetime(df['FECHA'], errors='coerce')
        limite = datetime.now() - pd.Timedelta(days=dias_a_mantener)
        
        df_limpio = df[df['FECHA_DT'] >= limite].copy()
        df_limpio = df_limpio.drop(columns=['FECHA_DT'])
        
        import numpy as np
        # Llenado seguro para evitar "Out of range float values are not JSON compliant"
        df_limpio = df_limpio.fillna("")

        eliminados = total_antes - len(df_limpio)
        if eliminados < getattr(config, 'UMBRAL_FILAS_BORRAR_MINIMO', 50):
            msg_skip = f"Saltando escritura de NOTICIAS_SISTEMA: solo se identificaron {eliminados} filas viejas para borrar."
            logger.info(f"    [-] {msg_skip}")
            duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
            actualizar_estado_proceso(ws_status, "OK", f"Sin cambios significativos ({eliminados} filas)", "limpieza_noticias_sistema", tiempo_ejecucion=duracion)
            return

        # Escritura resiliente ante cuota 429
        for intento_escritura in range(5):
            try:
                # Sobrescribir la hoja
                ws_noticias.clear()
                ws_noticias.append_row(df_limpio.columns.values.tolist())
                
                if not df_limpio.empty:
                    num_chunks = (len(df_limpio) + config.CHUNK_SIZE_SHEETS - 1) // config.CHUNK_SIZE_SHEETS
                    for i in range(num_chunks):
                        start_idx = i * config.CHUNK_SIZE_SHEETS
                        end_idx = min((i + 1) * config.CHUNK_SIZE_SHEETS, len(df_limpio))
                        ws_noticias.append_rows(df_limpio.iloc[start_idx:end_idx].values.tolist())
                        time.sleep(3) # PREVENIR ERROR 429 QUOTA EXCEEDED
                break # Éxito en escritura
            except Exception as e_write:
                if "429" in str(e_write) and intento_escritura < 4:
                    logger.warning(f"    [!] Cuota 429 al escribir NOTICIAS_SISTEMA. Reintentando en 15s (Intento {intento_escritura+1}/5)...")
                    time.sleep(15)
                else:
                    raise e_write

        msg_fin = f"Limpieza completada. Se eliminaron {eliminados} noticias aprobadas viejas."
        logger.info(f"[OK] {msg_fin}")
        registrar_log(ws_log, "INFO", msg_fin, "limpieza_noticias_sistema")
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        actualizar_estado_proceso(ws_status, "OK", msg_fin, "limpieza_noticias_sistema", tiempo_ejecucion=duracion)
    except Exception as e:
        actualizar_estado_proceso(ws_status, "ERROR", str(e)[:50], "limpieza_noticias_sistema", tiempo_ejecucion="0.00 min")
        logger.exception(f"Error técnico en limpieza de noticias aprobadas: {e}")
def limpiar_reporte_supervisor(sh, dias_a_mantener=30):
    try:
        import pandas as pd
        from datetime import datetime
        import config
        ws_supervisor = sh.worksheet(config.WS_REPORTE_SUPERVISOR)
        data = ws_supervisor.get_all_records()
        if not data: return
        
        df = pd.DataFrame(data)
        total_antes = len(df)
        if total_antes < 20: return 
        
        if 'FECHA_HORA' not in df.columns: return
        
        df['FECHA_DT'] = pd.to_datetime(df['FECHA_HORA'], errors='coerce')
        limite = datetime.now() - pd.Timedelta(days=dias_a_mantener)
        
        df_limpio = df[df['FECHA_DT'] >= limite].copy()
        df_limpio = df_limpio.drop(columns=['FECHA_DT'])
        
        import numpy as np
        df_limpio = df_limpio.replace([np.inf, -np.inf], np.nan).fillna("")
        
        eliminados = total_antes - len(df_limpio)
        if eliminados > 0:
            ws_supervisor.clear()
            ws_supervisor.append_row(df_limpio.columns.values.tolist())
            
            chunk_limpio = [[str(x) if pd.notna(x) else "" for x in row] for row in df_limpio.values.tolist()]
            ws_supervisor.append_rows(chunk_limpio, value_input_option='USER_ENTERED')
            logger.info(f"[*] Limpieza de Supervisor completada: {eliminados} reportes antiguos eliminados.")
            
    except Exception as e:
        logger.error(f"[!] Error en limpieza de supervisor: {e}")
