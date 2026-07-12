"""
Orquestador de Captura y Triage de Noticias.
Coordina los sub-módulos de captura (RSS, Scraping, etc.) y utiliza
IA para filtrar y resumir antes de guardar en las tablas finales.
"""
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from google import genai
import auth_google
import config
import concurrent.futures
import procesamiento
import ia_utils
import logging_config

logger = logging_config.get_logger(__name__)

# Importamos los sub-módulos de captura
import news_rss
import news_scraping
import news_telegram
import news_google
import news_api


def inicializar_motor_noticias():
    """Inicializa la conexión a Google Sheets y al cliente de IA para captura de noticias."""
    sh = auth_google.conectar()
    if not sh:
        raise RuntimeError("No se pudo conectar a Google Sheets con las credenciales configuradas.")

    key = config.get_gemini_api_key()

    client = genai.Client(api_key=key)
    return sh, client


def acceder_hoja(sh, nombre):
    """Accede a una hoja de Google Sheets con validación robusta y reintentos para cuota 429."""
    for intento in range(8):
        try:
            return sh.worksheet(nombre)
        except Exception as e:
            if "429" in str(e) and intento < 7:
                delay = 3 * (intento + 1)
                logger.warning(f"    [!] Cuota 429 al acceder a la hoja '{nombre}'. Reintentando en {delay}s...")
                time.sleep(delay)
                continue
            
            # Si es otro error o agotamos intentos
            try:
                hojas_detectadas = [w.title for w in sh.worksheets()]
            except Exception:
                hojas_detectadas = ["(No se pudo listar hojas por cuota)"]
            msg = f"ERROR: No se encontró la pestaña '{nombre}'. Hojas disponibles: {hojas_detectadas}"
            logger.error(msg)
            raise RuntimeError(msg)
    raise RuntimeError(f"ERROR: No se pudo acceder a la pestaña '{nombre}' debido a cuota 429 persistente.")


def validar_hojas_requeridas(sh):
    """Valida que todas las hojas requeridas existan antes de iniciar el proceso, con reintentos para 429."""
    hojas_requeridas = [
        config.WS_LOG_SISTEMA,
        config.WS_ESTADO_PROCESOS,
        config.WS_MAESTRO_ACTIVOS,
        config.WS_NOTICIAS_SISTEMA,
        config.WS_NOTICIAS_DESCARTADAS,
        config.WS_CONFIG_IA_GENERAL,
        config.WS_CONFIG_SINONIMOS,
        config.WS_SUGERENCIAS_SINONIMOS,
        config.WS_CONFIG_TELEGRAM_CHANNELS
    ]
    
    hojas_disponibles = None
    for intento in range(8):
        try:
            hojas_disponibles = [w.title for w in sh.worksheets()]
            break
        except Exception as e:
            if "429" in str(e) and intento < 7:
                delay = 3 * (intento + 1)
                logger.warning(f"    [!] Cuota 429 al listar hojas en validación. Reintentando en {delay}s...")
                time.sleep(delay)
                continue
            raise e
            
    if hojas_disponibles is None:
        return False, "ERROR: No se pudo obtener la lista de hojas debido a límites de la API."
        
    faltantes = [h for h in hojas_requeridas if h not in hojas_disponibles]
    if faltantes:
        msg = f"ERROR CRÍTICO: Faltan las siguientes pestañas en Google Sheets: {faltantes}"
        logger.critical(msg)
        return False, msg
    
    return True, "Todas las hojas requeridas están presentes."


def ejecutar_captura_noticias():
    t_inicio = time.time()
    logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando Captura de Noticias...")

    sh = None
    ws_log = None
    ws_status = None

    try:
        sh, client = inicializar_motor_noticias()
    except Exception as e:
        msg = f"ERROR CRÍTICO CAPTURA NOTICIAS: {e}"
        logger.critical(msg)  # ✅ Siempre se registra en terminal
        return False

    # 0.1 Validación Fail-Fast: Credenciales de Telegram
    if not config.TELEGRAM_API_ID or config.TELEGRAM_API_ID == 0 or not config.TELEGRAM_API_HASH:
        msg = "ERROR CRÍTICO: Credenciales de Telegram (API_ID/HASH) no configuradas en .env. Abortando Paso 3.5."
        logger.critical(msg)
        return False

    # Validar que todas las hojas requeridas existan ANTES de empezar
    try:
        hojas_ok, msg_hojas = validar_hojas_requeridas(sh)
        if not hojas_ok:
            logger.critical(msg_hojas)
            return False
    except Exception as e:
        msg = f"ERROR al validar hojas requeridas: {e}"
        logger.critical(msg)
        return False

    # Mantenimiento preventivo de tablas de noticias antes de comenzar
    procesamiento.limpiar_noticias_descartadas(sh)
    procesamiento.limpiar_sugerencias_sinonimos(sh)
    procesamiento.limpiar_noticias_sistema(sh)

    # Pausa defensiva + reconexión fresca después de las limpiezas preventivas.
    # Las funciones de limpieza pueden saturar la cuota 429 internamente; reconectar
    # garantiza que el objeto 'sh' esté limpio antes de cargar las hojas principales.
    time.sleep(5)
    try:
        sh, client = inicializar_motor_noticias()
    except Exception as e:
        logger.warning(f"    [!] No se pudo reconectar después de limpiezas preventivas: {e}. Usando conexión original.")

    # Carga de hojas principales (ahora sabemos que todas existen)
    try:
        ws_log = acceder_hoja(sh, config.WS_LOG_SISTEMA)
        ws_status = acceder_hoja(sh, config.WS_ESTADO_PROCESOS)
        ws_maestro = acceder_hoja(sh, config.WS_MAESTRO_ACTIVOS)
        ws_noticias = acceder_hoja(sh, config.WS_NOTICIAS_SISTEMA)
        ws_descartadas = acceder_hoja(sh, config.WS_NOTICIAS_DESCARTADAS)
        ws_config_ia = acceder_hoja(sh, config.WS_CONFIG_IA_GENERAL)
        ws_sinonimos = acceder_hoja(sh, config.WS_CONFIG_SINONIMOS)
        ws_sugerencias = acceder_hoja(sh, config.WS_SUGERENCIAS_SINONIMOS)
        ws_canales = acceder_hoja(sh, config.WS_CONFIG_TELEGRAM_CHANNELS)
    except Exception as e:
        msg = f"ERROR CRÍTICO al cargar hojas de Google Sheets: {e}"
        logger.critical(msg)
        if ws_log and ws_status:
            try:
                procesamiento.registrar_log(ws_log, "CRITICAL", msg)
                procesamiento.actualizar_estado_proceso(ws_status, "ERROR", "Fallo al cargar hojas requeridas")
            except Exception as sheet_error:
                logger.critical(f"No se pudo registrar en Google Sheets: {sheet_error}")
        return False

    procesamiento.actualizar_estado_proceso(ws_status, "PROCESANDO", "Capturando fuentes...")

    # 0. Cargar Maestro de Activos para mapeo dinámico de tickers
    try:
        records_maestro = ws_maestro.get_all_records()
        df_maestro = pd.DataFrame(records_maestro)
        df_maestro.columns = [c.strip().upper() for c in df_maestro.columns]
        # Mapeamos solo los activos ACTIVOS para no ensuciar el análisis con tickers viejos
        # Agregamos FILTRO_NOTICIAS para el módulo de Google
        activos_maestro = df_maestro[df_maestro['ESTADO'] == 'ACTIVO'][['TICKER_ID', 'NOMBRE_LARGO', 'FILTRO_NOTICIAS']].to_dict('records')
    except Exception as e:
        logger.warning(f"[!] Error cargando maestro para mapeo: {e}")
        activos_maestro = []

    # 0.1 Cargar Mapa de Sinónimos desde Google Sheets (Tu nueva forma de carga)
    try:
        records_raw = ws_sinonimos.get_all_records()
        MAPA_SINONIMOS = {}
        for r in records_raw:
            r_norm = {str(k).strip().upper(): v for k, v in r.items()}
            ticker = str(r_norm.get('TICKER', '')).strip().upper()
            sinonimos_str = str(r_norm.get('SINONIMOS', '')).strip()
            if ticker and sinonimos_str:
                # Separar por comas y normalizar a mayúsculas
                sinonimos_lista = [s.strip().upper() for s in sinonimos_str.split(',') if s.strip()]
                for sinonimo in sinonimos_lista:
                    MAPA_SINONIMOS[sinonimo] = ticker
        logger.info(f"[*] {len(MAPA_SINONIMOS)} sinónimos cargados desde la planilla (formato agrupado).")
    except Exception as e:
        logger.warning(f"[!] Error cargando tabla de sinónimos: {e}")
        MAPA_SINONIMOS = {}

    def identificar_ticker(titular):
        titular_up = titular.upper()
        # 1. Prioridad: Coincidencia exacta con Tickers (usando límites de palabra \b)
        for act in activos_maestro:
            tid = str(act.get('TICKER_ID', '')).upper()
            nombre = str(act.get('NOMBRE_LARGO', '')).upper()
            
            if tid:
                # \b asegura que busque la palabra exacta (ej: 'C' y no 'C' dentro de 'China')
                patron = r'\b' + re.escape(tid) + r'\b'
                if re.search(patron, titular_up) or (len(nombre) > 4 and nombre in titular_up):
                    return tid
        
        # 2. Segunda opción: Buscar en el mapa de sinónimos/sectores (usando Regex para precisión)
        for sinonimo, ticker_target in MAPA_SINONIMOS.items():
            # \b asegura que 'OIL' no coincida con 'BOILER'
            patron_sin = r'\b' + re.escape(sinonimo.upper()) + r'\b'
            if re.search(patron_sin, titular_up):
                return ticker_target
                
        return "9999" # Macro por defecto

    try:
        # 1. Obtener Configuración y Prompt de Triage desde la planilla
        conf_records = ws_config_ia.get_all_records()
        if not conf_records:
            raise ValueError("No se encontró configuración en CONFIG_IA_GENERAL")
        
        conf_ia = conf_records[0]
        # Leemos el prompt que acabas de agregar en la columna D
        prompt_triage_base = conf_ia.get('Prompt_Triage_Noticias', '')

        # Usamos ia_utils para obtener la lista de modelos sanos detectados en el Paso 0
        modelos_candidatos = ia_utils.obtener_modelos_activos()

        # 2. Recolectar noticias de todos los sub-módulos (La "Bolsa") en paralelo
        todas_las_noticias = []

        # Preparar datos para Google News y Telegram antes de lanzar hilos
        lista_google = []
        for act in activos_maestro:
            if act.get('FILTRO_NOTICIAS'):
                lista_google.append({'ticker': act['TICKER_ID'], 'filtro': act['FILTRO_NOTICIAS']})
        lista_google.append({'ticker': '9999', 'filtro': 'mercados financieros argentina eeuu'})

        canales_raw = ws_canales.get_all_records()
        canales_activos = [str(c['CANAL']).strip() for c in canales_raw if str(c.get('ESTADO', '')).upper() == 'ACTIVO']

        logger.info("[*] Iniciando recolección paralela de fuentes...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_rss = executor.submit(news_rss.capturar_rss)
            future_scraping = executor.submit(news_scraping.capturar_scraping)
            future_google = executor.submit(news_google.capturar_google_news, lista_google)
            future_telegram = executor.submit(news_telegram.capturar_telegram, canales_activos)
            future_api = executor.submit(news_api.capturar_cryptopanic)

            # Esperar resultados y combinar
            todas_las_noticias.extend(future_rss.result())
            todas_las_noticias.extend(future_scraping.result())
            todas_las_noticias.extend(future_google.result())
            todas_las_noticias.extend(future_telegram.result())
            todas_las_noticias.extend(future_api.result())

        # Fin de recolección paralela

        # Asignar timestamp natural a todas las noticias recolectadas
        base_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for n in todas_las_noticias:
            n['fecha'] = base_time

        if not todas_las_noticias:
            procesamiento.actualizar_estado_proceso(ws_status, "OK", "No se hallaron noticias", tiempo_ejecucion="0.00 min")
            return True

        # 3. Deduplicación (No procesar lo que ya tenemos o ya descartamos)
        # Usamos caché local para evitar descargar miles de filas de Sheets en cada corrida.
        cache_dir = Path("IA_LOGS")
        cache_dir.mkdir(exist_ok=True)
        cache_file = cache_dir / "noticias_procesadas.json"
        
        cache_procesadas = {}
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache_procesadas = json.load(f)
            except Exception as e:
                logger.warning(f"No se pudo leer el caché local de noticias: {e}")
        
        # Como fallback, si el caché está vacío, inicializarlo con lo que hay en Sheets
        # para no perder lo que ya se subió en días anteriores.
        if not cache_procesadas:
            logger.info("Caché local vacío. Inicializando desde Google Sheets...")
            try:
                urls_vistas = {str(r.get('URL', '')).strip() for r in ws_noticias.get_all_records() if r.get('URL')}
                titulares_descartados = {str(r.get('TITULAR', '')).strip().upper() for r in ws_descartadas.get_all_records() if r.get('TITULAR')}
                for url in urls_vistas:
                    cache_procesadas[url] = {"estado": "APROBADO", "fecha": ""}
                for tit in titulares_descartados:
                    cache_procesadas[f"titular_{tit}"] = {"estado": "RECHAZADO", "fecha": ""}
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(cache_procesadas, f, indent=4, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"Error inicializando caché desde Sheets: {e}")
                urls_vistas = set()
                titulares_descartados = set()
        else:
            urls_vistas = {url for url, info in cache_procesadas.items() if info.get("estado") == "APROBADO" and not url.startswith("titular_")}
            titulares_descartados = {url.replace("titular_", "") for url, info in cache_procesadas.items() if info.get("estado") == "RECHAZADO" and url.startswith("titular_")}

        nuevas = []
        for n in todas_las_noticias:
            url_n = str(n.get('url', '')).strip()
            tit_n = str(n.get('titular', '')).strip().upper()
            
            if url_n and (url_n in urls_vistas or url_n in cache_procesadas):
                continue
            if tit_n and (tit_n in titulares_descartados or f"titular_{tit_n}" in cache_procesadas):
                continue
            
            nuevas.append(n)

        # Ordenar por fecha descendente y limitar a 25 novedades
        nuevas.sort(key=lambda x: x.get('fecha'), reverse=True)
        if len(nuevas) > 25:
            nuevas = nuevas[:25]
        
        logger.info(f"[*] {len(nuevas)} noticias nuevas para Triage (de {len(todas_las_noticias)} encontradas).")
        if len(nuevas) == 0 and len(todas_las_noticias) > 0:
            logger.info("    [!] Todas las noticias encontradas ya fueron procesadas y están en tus tablas.")

        # 4. Triage con IA (Procesamiento por lotes o individual)
        aprobadas_batch = []
        descartadas_batch = []
        sugerencias_batch = []
        quota_error = False

        for n in nuevas:
            if quota_error: break
            
            # Identificación inteligente del Ticker antes del envío a la IA
            n['ticker'] = identificar_ticker(n['titular'])
            
            # Evitamos que la IA descarte noticias macro por no reconocer "9999" como un ticker real.
            ticker_para_ia = n['ticker']
            if n['ticker'] == "9999":
                ticker_para_ia = "Mercado General (Macroeconomía / Contexto Global)"
            
            prompt_final = prompt_triage_base.format(titular=n['titular'], ticker=ticker_para_ia)
            
            logro_triage = False
            response_text = ""
            # Rotación de modelos en caso de error de cuota (429)
            for mod_id in list(modelos_candidatos):
                if logro_triage: break
                try:
                    response = client.models.generate_content(
                        model=mod_id, 
                        contents=prompt_final,
                        config={"response_mime_type": "application/json"}
                    )
                    response_text = response.text
                    logro_triage = True
                except Exception as e:
                    err_msg = str(e)
                    if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                        logger.warning(f"    [!] Cuota agotada en {mod_id}. Rotando a siguiente modelo...")
                        if mod_id in modelos_candidatos: modelos_candidatos.remove(mod_id)
                        if not modelos_candidatos:
                            quota_error = True
                            logger.error("    [!!!] SIN CUOTA EN NINGÚN MODELO. Deteniendo proceso para no bloquear la API.")
                            break
                    else:
                        logger.warning(f"    [!] Error en modelo {mod_id}: {err_msg[:50]}")
                        continue
            
            if not logro_triage: continue

            try:
                res_ia = json.loads(response_text)
                region_ia = str(res_ia.get('region', 'GLOBAL')).upper()
                
                # Registrar el resultado en el caché de inmediato (Resiliente ante cortes)
                cache_key = n['url'] if n['url'] else f"titular_{n['titular'].upper()}"
                
                if res_ia.get('estado') == "APROBADO":
                    # Si es macro (9999), le ponemos el sufijo según lo que detectó la IA
                    ticker_final = n['ticker']
                    if ticker_final == "9999":
                        if "ARGENTINA" in region_ia:
                            ticker_final = "9999_AR"
                        elif "USA" in region_ia or "EEUU" in region_ia:
                            ticker_final = "9999_US"

                    logger.info(f"    [+] APROBADA [{ticker_final}] (Región: {region_ia}): {n['titular'][:50]}...")
                    # Orden Columnas NOTICIAS_SISTEMA: 
                    # ID, FECHA, TICKER_ID, TITULAR, FUENTE, SUBMODULO, URL, CANAL_ORIGEN, RESUMEN_IA, SENTIMIENTO
                    import uuid
                    noticia_id = str(uuid.uuid4())[:8]
                    aprobadas_batch.append([
                        noticia_id, n['fecha'], ticker_final, n['titular'], n['fuente'], 
                        n['submodulo'], n['url'], n['canal_origen'], 
                        res_ia.get('resumen'), res_ia.get('sentimiento')
                    ])
                    cache_procesadas[cache_key] = {
                        "estado": "APROBADO",
                        "fecha": n['fecha'],
                        "datos": res_ia
                    }
                else:
                    motivo = res_ia.get('motivo_descarte', 'Irrelevante')
                    logger.info(f"    [-] DESCARTADA [{n['ticker']}] (Región: {region_ia}): {n['titular'][:50]}... -> Motivo: {motivo}")
                    # Orden Columnas NOTICIAS_DESCARTADAS: 
                    # ID, FECHA, TICKER_ID, TITULAR, MOTIVO_DESCARTE, SUBMODULO
                    import uuid
                    noticia_id = str(uuid.uuid4())[:8]
                    descartadas_batch.append([
                        noticia_id, n['fecha'], n['ticker'], n['titular'], 
                        motivo, n['submodulo']
                    ])
                    cache_procesadas[cache_key] = {
                        "estado": "RECHAZADO",
                        "fecha": n['fecha'],
                        "datos": res_ia
                    }
                
                # 4.1 Capturar sugerencias si el ticker actual es 9999 y el ticker sugerido existe en el maestro
                sug_ticker = str(res_ia.get('sugerencia_ticker', '')).strip().upper()
                
                existe_en_maestro = False
                try:
                    if 'df_maestro' in locals() and not df_maestro.empty and 'TICKER_ID' in df_maestro.columns:
                        tickers_validos = set(df_maestro['TICKER_ID'].astype(str).str.strip().str.upper().unique())
                        existe_en_maestro = sug_ticker in tickers_validos
                except Exception as ex_maestro:
                    logger.warning(f"Error al verificar existencia de ticker sugerido en maestro: {ex_maestro}")
                    existe_en_maestro = False

                if n['ticker'] == "9999" and sug_ticker and sug_ticker != "9999" and existe_en_maestro:
                    import uuid
                    sug_id = str(uuid.uuid4())[:8]
                    sugerencias_batch.append([
                        sug_id, n['fecha'], n['titular'], res_ia.get('sugerencia_termino'),
                        sug_ticker, res_ia.get('resumen'), 'PENDIENTE'
                    ])

                # Guardar el caché actualizado inmediatamente en disco
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(cache_procesadas, f, indent=4, ensure_ascii=False)

                # Pausa estratégica para respetar el RPM de la capa gratuita (Free tier = 10 RPM)
                time.sleep(6)
                
            except Exception as e:
                logger.exception(f"    [!] Error en Triage para: {n['titular'][:30]}... -> {e}")

        # 4.2 Limpieza de caché local para registros antiguos (>30 días)
        try:
            limite_fecha_cache = datetime.now() - pd.Timedelta(days=30)
            llaves_a_borrar = []
            for k, info in cache_procesadas.items():
                fecha_str = info.get("fecha", "")
                if fecha_str:
                    try:
                        fecha_dt = pd.to_datetime(fecha_str)
                        if fecha_dt < limite_fecha_cache:
                            llaves_a_borrar.append(k)
                    except:
                        pass
            if llaves_a_borrar:
                for k in llaves_a_borrar:
                    cache_procesadas.pop(k, None)
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(cache_procesadas, f, indent=4, ensure_ascii=False)
                logger.info(f"[*] Limpieza de caché local completada: se eliminaron {len(llaves_a_borrar)} registros antiguos.")
        except Exception as e:
            logger.warning(f"No se pudo limpiar el caché local de noticias: {e}")

        # 5. Guardado en Google Sheets
        if aprobadas_batch:
            ws_noticias.append_rows(aprobadas_batch, value_input_option='RAW')
            logger.info(f"    [+] {len(aprobadas_batch)} noticias guardadas en sistema.")
            
        if descartadas_batch:
            ws_descartadas.append_rows(descartadas_batch, value_input_option='RAW')
            logger.info(f"    [-] {len(descartadas_batch)} noticias enviadas a descartes.")
            
        if sugerencias_batch:
            ws_sugerencias.append_rows(sugerencias_batch, value_input_option='RAW')
            logger.info(f"    [!] {len(sugerencias_batch)} sugerencias de sinónimos detectadas.")
            
        # --- BOLETÍN DE NOTICIAS PARA VICKY ---
        if aprobadas_batch:
            import notificador_telegram
            # Ordenar por importancia (Prioridad 1: Activos específicos, 2: Locales (9999_AR), 3: Global (9999_US))
            def score_prioridad(noticia):
                ticker = str(noticia[2])
                if ticker == "9999_AR": return 2
                if ticker == "9999_US": return 3
                return 1 # Ticker específico tiene más prioridad

            aprobadas_ordenadas = sorted(aprobadas_batch, key=score_prioridad)
            
            msg_boletin = "📰 <b>Resumen Diario de Noticias Relevantes</b>\n\n"
            
            for noti in aprobadas_ordenadas:
                ticker = noti[2]
                titular = noti[3]
                url = noti[6]
                sentimiento = noti[9]
                
                # Emoji según sentimiento
                emoji_sent = "🟢" if "POSITIV" in str(sentimiento).upper() else ("🔴" if "NEGATIV" in str(sentimiento).upper() else "⚪")
                
                msg_boletin += f"{emoji_sent} <b>[{ticker}]</b> {titular}\n"
                if url and str(url).startswith("http"):
                    msg_boletin += f"🔗 <a href='{url}'>Leer más</a>\n"
                msg_boletin += "\n"
                
            notificador_telegram.enviar_mensaje_telegram(msg_boletin, destinatario="VICKY")

        # 6. Finalización y Logs
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        total_procesadas = len(aprobadas_batch) + len(descartadas_batch)
        resumen = f"Finalizado: {total_procesadas} procesadas ({len(aprobadas_batch)} aprobadas, {len(descartadas_batch)} descartadas)."
        
        procesamiento.registrar_log(ws_log, "INFO", resumen)
        procesamiento.actualizar_estado_proceso(ws_status, "OK", resumen, tiempo_ejecucion=duracion)
        logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] {resumen} (Tiempo: {duracion})")
        return True

    except Exception as e:
        msg_err = f"Error crítico en captura_noticias: {e}"
        logger.critical(msg_err)  # ✅ Siempre se registra en terminal
        
        # Solo intenta registrar en Google Sheets si las conexiones están disponibles
        if ws_log is not None and ws_status is not None:
            try:
                procesamiento.registrar_log(ws_log, "CRITICAL", msg_err)
                procesamiento.actualizar_estado_proceso(ws_status, "ERROR", str(e)[:50])
            except Exception as sheet_error:
                logger.critical(f"No se pudo registrar el error en Google Sheets: {sheet_error}")
        
        return False

if __name__ == "__main__":
    ejecutar_captura_noticias()
