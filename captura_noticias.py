"""
Orquestador de Captura y Triage de Noticias.
Coordina los sub-módulos de captura (RSS, Scraping, etc.) y utiliza
IA para filtrar y resumir antes de guardar en las tablas finales.
"""
import json
import re
import time
import sys
from datetime import datetime
from pathlib import Path
import pandas as pd
from google import genai
import auth_google
import config
import concurrent.futures
import procesamiento
import ia_utils

# Importamos los sub-módulos de captura
import news_rss
import news_scraping
import news_telegram
import news_google
import news_api

def ejecutar_captura_noticias():
    t_inicio = time.time()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando Captura de Noticias...")
    
    sh = auth_google.conectar()
    if not sh: return
    
    # Mantenimiento preventivo de tablas de noticias antes de comenzar
    procesamiento.limpiar_noticias_descartadas(sh)
    procesamiento.limpiar_sugerencias_sinonimos(sh)
    
    # Función auxiliar para acceso seguro con aviso claro y detención
    def acceder_hoja(nombre):
        try:
            return sh.worksheet(nombre)
        except Exception:
            hojas_detectadas = [w.title for w in sh.worksheets()]
            msg = f"ERROR CRÍTICO: No se encontró la pestaña '{nombre}'."
            print(f"\n[!!!] {msg}")
            print(f"      Hojas encontradas en tu planilla: {hojas_detectadas}")
            print(f"      Verifica si hay espacios extras o errores de escritura en el nombre.")
            sys.exit(1) # Detenemos la ejecución como solicitaste

    # Carga de hojas principales
    ws_log = acceder_hoja(config.WS_LOG_SISTEMA)
    ws_status = acceder_hoja(config.WS_ESTADO_PROCESOS)
    ws_maestro = acceder_hoja(config.WS_MAESTRO_ACTIVOS)
    ws_noticias = acceder_hoja(config.WS_NOTICIAS_SISTEMA)
    ws_descartadas = acceder_hoja(config.WS_NOTICIAS_DESCARTADAS)
    ws_config_ia = acceder_hoja(config.WS_CONFIG_IA_GENERAL)
    ws_sinonimos = acceder_hoja(config.WS_CONFIG_SINONIMOS)
    ws_sugerencias = acceder_hoja(config.WS_SUGERENCIAS_SINONIMOS)
    ws_canales = acceder_hoja(config.WS_CONFIG_TELEGRAM_CHANNELS)

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
        print(f"[!] Error cargando maestro para mapeo: {e}")
        activos_maestro = []

    # 0.1 Cargar Mapa de Sinónimos desde Google Sheets (Tu nueva forma de carga)
    try:
        records_raw = ws_sinonimos.get_all_records()
        # Creamos el diccionario dinámicamente: {"TECNOLOGÍA": "NASDAQ", ...}
        MAPA_SINONIMOS = {}
        for r in records_raw:
            # Normalizamos las llaves del diccionario (las cabeceras de la fila 1) para evitar el KeyError
            r_norm = {str(k).strip().upper(): v for k, v in r.items()}
            termino = str(r_norm.get('TERMINO', '')).strip().upper()
            ticker = str(r_norm.get('TICKER_ASOCIADO', '')).strip().upper()
            if termino and ticker:
                MAPA_SINONIMOS[termino] = ticker
        print(f"[*] {len(MAPA_SINONIMOS)} sinónimos cargados desde la planilla.")
    except Exception as e:
        print(f"[!] Error cargando tabla de sinónimos: {e}")
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

        with open(config.API_KEY_FILE, 'r') as f:
            client = genai.Client(api_key=f.read().strip())

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

        print("[*] Iniciando recolección paralela de fuentes...")
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

        if not todas_las_noticias:
            procesamiento.actualizar_estado_proceso(ws_status, "OK", "No se hallaron noticias", tiempo_ejecucion="0.00 min")
            return

        # 3. Deduplicación (No procesar lo que ya tenemos o ya descartamos)
        # Leemos URL de noticias existentes y Titulares de descartadas
        urls_vistas = {str(r.get('URL', '')).strip() for r in ws_noticias.get_all_records() if r.get('URL')}
        titulares_descartados = {str(r.get('TITULAR', '')).strip().upper() for r in ws_descartadas.get_all_records() if r.get('TITULAR')}
        
        nuevas = []
        for n in todas_las_noticias:
            url_n = str(n.get('url', '')).strip()
            tit_n = str(n.get('titular', '')).strip().upper()
            
            # Si la URL ya existe, la saltamos
            if url_n and url_n in urls_vistas:
                continue
            # Si el titular ya fue descartado antes, lo saltamos
            if tit_n and tit_n in titulares_descartados:
                continue
            
            nuevas.append(n)
        # Ordenar por fecha descendente y limitar a 25 novedades
        nuevas.sort(key=lambda x: x.get('fecha'), reverse=True)
        if len(nuevas) > 25:
            nuevas = nuevas[:25]
        
        print(f"[*] {len(nuevas)} noticias nuevas para Triage (de {len(todas_las_noticias)} encontradas).")
        if len(nuevas) == 0 and len(todas_las_noticias) > 0:
            print("    [!] Todas las noticias encontradas ya fueron procesadas y están en tus tablas.")

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
            # Si el ticker es 9999, le pasamos una descripción amigable para el análisis.
            ticker_para_ia = n['ticker']
            if n['ticker'] == "9999":
                ticker_para_ia = "Mercado General (Macroeconomía / Contexto Global)"
            
            prompt_final = prompt_triage_base.format(titular=n['titular'], ticker=ticker_para_ia)
            
            logro_triage = False
            # Rotación de modelos en caso de error de cuota (429)
            for mod_id in list(modelos_candidatos):
                if logro_triage: break
                try:
                    response = client.models.generate_content(
                        model=mod_id, 
                        contents=prompt_final,
                        config={"response_mime_type": "application/json"}
                    )
                    logro_triage = True
                except Exception as e:
                    err_msg = str(e)
                    if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                        print(f"    [!] Cuota agotada en {mod_id}. Rotando a siguiente modelo...")
                        if mod_id in modelos_candidatos: modelos_candidatos.remove(mod_id)
                        if not modelos_candidatos:
                            quota_error = True
                            print("    [!!!] SIN CUOTA EN NINGÚN MODELO. Deteniendo proceso para no bloquear la API.")
                            break
                    else:
                        print(f"    [!] Error en modelo {mod_id}: {err_msg[:50]}")
                        continue
            
            if not logro_triage: continue

            try:
                res_ia = json.loads(response.text)
                region_ia = str(res_ia.get('region', 'GLOBAL')).upper()
                
                if res_ia.get('estado') == "APROBADO":
                    # Si es macro (9999), le ponemos el sufijo según lo que detectó la IA
                    ticker_final = n['ticker']
                    if ticker_final == "9999":
                        if "ARGENTINA" in region_ia:
                            ticker_final = "9999_AR"
                        elif "USA" in region_ia or "EEUU" in region_ia:
                            ticker_final = "9999_US"

                    print(f"    [+] APROBADA [{ticker_final}] (Región: {region_ia}): {n['titular'][:50]}...")
                    # Orden Columnas NOTICIAS_SISTEMA: 
                    # FECHA, TICKER_ID, TITULAR, FUENTE, SUBMODULO, URL, CANAL_ORIGEN, RESUMEN_IA, SENTIMIENTO
                    aprobadas_batch.append([
                        n['fecha'], ticker_final, n['titular'], n['fuente'], 
                        n['submodulo'], n['url'], n['canal_origen'], 
                        res_ia.get('resumen'), res_ia.get('sentimiento')
                    ])
                else:
                    motivo = res_ia.get('motivo_descarte', 'Irrelevante')
                    print(f"    [-] DESCARTADA [{n['ticker']}] (Región: {region_ia}): {n['titular'][:50]}... -> Motivo: {motivo}")
                    # Orden Columnas NOTICIAS_DESCARTADAS: 
                    # FECHA, TICKER_ID, TITULAR, MOTIVO_DESCARTE, SUBMODULO
                    descartadas_batch.append([
                        n['fecha'], n['ticker'], n['titular'], 
                        res_ia.get('motivo_descarte', 'Irrelevante'), n['submodulo']
                    ])
                
                # 4.1 Capturar sugerencias si el ticker actual es 9999
                sug_ticker = res_ia.get('sugerencia_ticker')
                if n['ticker'] == "9999" and sug_ticker and str(sug_ticker).upper() != "9999":
                    sugerencias_batch.append([
                        n['fecha'], n['titular'], res_ia.get('sugerencia_termino'),
                        sug_ticker, res_ia.get('resumen')
                    ])

                # Pausa estratégica para respetar el RPM de la capa gratuita (Free tier = 10 RPM)
                time.sleep(6)
                
            except Exception as e:
                print(f"    [!] Error en Triage para: {n['titular'][:30]}... -> {e}")

        # 5. Guardado en Google Sheets
        if aprobadas_batch:
            ws_noticias.append_rows(aprobadas_batch, value_input_option='USER_ENTERED')
            print(f"    [+] {len(aprobadas_batch)} noticias guardadas en sistema.")
            
        if descartadas_batch:
            ws_descartadas.append_rows(descartadas_batch, value_input_option='USER_ENTERED')
            print(f"    [-] {len(descartadas_batch)} noticias enviadas a descartes.")
            
        if sugerencias_batch:
            ws_sugerencias.append_rows(sugerencias_batch, value_input_option='USER_ENTERED')
            print(f"    [!] {len(sugerencias_batch)} sugerencias de sinónimos detectadas.")

        # 6. Finalización y Logs
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        total_procesadas = len(aprobadas_batch) + len(descartadas_batch)
        resumen = f"Finalizado: {total_procesadas} procesadas ({len(aprobadas_batch)} aprobadas, {len(descartadas_batch)} descartadas)."
        
        procesamiento.registrar_log(ws_log, "INFO", resumen)
        procesamiento.actualizar_estado_proceso(ws_status, "OK", resumen, tiempo_ejecucion=duracion)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {resumen} (Tiempo: {duracion})")
        return True

    except Exception as e:
        msg_err = f"Error crítico en captura_noticias: {e}"
        print(f"!!! {msg_err}")
        try:
            procesamiento.registrar_log(ws_log, "ERROR", msg_err)
            procesamiento.actualizar_estado_proceso(ws_status, "ERROR", str(e)[:50])
        except: pass
        return False

if __name__ == "__main__":
    ejecutar_captura_noticias()