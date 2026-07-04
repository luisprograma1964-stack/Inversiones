"""
Motor de Inteligencia Artificial para veredictos de inversión.
Combina el análisis técnico con perfiles de usuario para generar recomendaciones
personalizadas utilizando el modelo de Google Gemini/Gemma.
"""
import gspread
import pandas as pd
from google import genai
from datetime import datetime
import time
import procesamiento
import json
import config
from pathlib import Path
import ia_utils
import auth_google
import logging_config
import notificador_telegram

logger = logging_config.get_logger(__name__)


def inicializar_motor_ia():
    """Inicializa conexión a Google Sheets y cliente de IA en tiempo de ejecución."""
    sh = auth_google.conectar()
    if not sh:
        raise RuntimeError("No se pudo conectar a Google Sheets con las credenciales configuradas.")

    api_key_path = Path(config.API_KEY_FILE)
    if not api_key_path.exists():
        raise FileNotFoundError(f"Archivo de API KEY no encontrado: {config.API_KEY_FILE}")

    with open(api_key_path, 'r', encoding='utf-8') as f:
        key = f.read().strip()

    if not key:
        raise ValueError(f"El archivo de API KEY está vacío: {config.API_KEY_FILE}")

    client = genai.Client(api_key=key)
    return sh, client

def limpiar_logs_antiguos(dias=10):
    """Borra archivos en la carpeta IA_LOGS con más de 'dias' de antigüedad."""
    log_dir = Path("IA_LOGS")
    if not log_dir.exists():
        return
    
    ahora = time.time()
    limite = ahora - (dias * 86400) # 86400 segundos = 1 día
    
    borrados = 0
    try:
        for archivo in log_dir.glob("req_*.json"):
            if archivo.is_file():
                # Verificamos la fecha de modificación del sistema de archivos
                if archivo.stat().st_mtime < limite:
                    archivo.unlink()
                    borrados += 1
        
        if borrados > 0:
            logger.info(f"[*] Mantenimiento: Se eliminaron {borrados} logs antiguos (> {dias} días).")
    except Exception as e:
        logger.exception(f"Error al limpiar logs antiguos: {e}")

def ejecutar_decisor():
    logger.info("\n" + "="*60)
    logger.info(f"MOTOR IA - ANÁLISIS TÉCNICO PROFESIONAL | {datetime.now().strftime('%H:%M:%S')}")
    logger.info("="*60)
    t_inicio = time.time()
    
    activos_procesados = 0
    errores = 0

    # Ejecutar limpieza de historial antes de empezar el análisis
    limpiar_logs_antiguos(dias=10)

    sh = None  # Inicializar como None para verificar luego
    try:
        sh, client = inicializar_motor_ia()
    except Exception as e:
        msg = f"ERROR CRÍTICO MOTOR IA: {e}"
        logger.critical(msg)  # ✅ Siempre se registra en terminal
        # No intentamos registrar en Sheets porque la conexión falló
        return False

    procesamiento.limpiar_reporte_ia(sh)
    procesamiento.actualizar_estado_proceso(sh.worksheet(config.WS_ESTADO_PROCESOS), "PROCESANDO", "Analizando activos con IA...")

    try:
        # 1. MAPEO DE USUARIOS
        usuarios_raw = sh.worksheet(config.WS_CONFIG_IA_USUARIO).get_all_records()
        # Extraemos la lista única de perfiles de riesgo configurados
        perfiles_set = {str(u['Perfil_Riesgo']).strip().capitalize() for u in usuarios_raw if u.get('Perfil_Riesgo')}
        perfiles_lista = list(perfiles_set)
        # Mapeamos el perfil a sí mismo para que la IA guarde el nombre del perfil (ej: "Conservador") en la matriz
        mapa_usuarios = {p: p for p in perfiles_lista}

        # 2. DATOS TÉCNICOS
        ws_analisis = sh.worksheet(config.WS_ANALISIS_TECNICO)
        # Usamos UNFORMATTED_VALUE para leer el número real de la celda y evitar confusiones con puntos de miles
        df_tecnico = pd.DataFrame(ws_analisis.get_all_records(value_render_option='UNFORMATTED_VALUE'))
        df_tecnico.columns = [c.strip().upper() for c in df_tecnico.columns]
        
        df_tecnico['ESTADO'] = df_tecnico['ESTADO'].astype(str).str.strip().str.replace('.', '', regex=False).str.upper()
        pendientes = df_tecnico[df_tecnico['ESTADO'] == 'PENDIENTE'].copy()

        # Cruce con MAESTRO_ACTIVOS para excluir inactivos de la cola de decisión
        try:
            df_maestro = pd.DataFrame(sh.worksheet(config.WS_MAESTRO_ACTIVOS).get_all_records())
            df_maestro.columns = [c.strip().upper() for c in df_maestro.columns]
            tickers_activos = set(df_maestro[df_maestro['ESTADO'].astype(str).str.strip().str.upper() == 'ACTIVO']['TICKER_ID'].astype(str).str.strip().str.upper().tolist())
            pendientes = pendientes[pendientes['TICKER_ID'].astype(str).str.strip().str.upper().isin(tickers_activos)].copy()
            logger.info(f"[*] Total activos pendientes y activos en el maestro a procesar: {len(pendientes)}")
        except Exception as e_m:
            logger.warning(f"No se pudo cruzar con MAESTRO_ACTIVOS para filtrar inactivos: {e_m}")

        # --- CÁLCULO DE CCL PROMEDIO DE MERCADO ---
        ccl_values = []
        if 'CCL_IMPLICITO' in df_tecnico.columns:
            for val in df_tecnico['CCL_IMPLICITO']:
                try:
                    if val is not None and str(val).strip() != '' and str(val).strip() != '0':
                        clean_val = float(str(val).replace(',', '.'))
                        if clean_val > 500: # Filtro de cordura: el CCL debe estar en rango realista (> 500 ARS)
                            ccl_values.append(clean_val)
                except Exception:
                    pass
        ccl_promedio = sum(ccl_values) / len(ccl_values) if len(ccl_values) > 0 else 0.0
        if ccl_promedio > 0:
            logger.info(f"[*] Tipo de cambio CCL Promedio de Mercado: {ccl_promedio:.2f} ARS (basado en {len(ccl_values)} activos)")
        else:
            logger.warning("[!] No se pudo calcular el CCL Promedio del Mercado o no hay activos con CCL válido.")


        if pendientes.empty:
            logger.info(">>> No hay activos pendientes.")
            duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
            procesamiento.actualizar_estado_proceso(sh.worksheet(config.WS_ESTADO_PROCESOS), "OK", "Sin activos pendientes", tiempo_ejecucion=duracion)
            return

        gen_data = sh.worksheet(config.WS_CONFIG_IA_GENERAL).get_all_records()[0]
        ws_gen = {k.strip(): v for k, v in gen_data.items()}
        ws_reporte = sh.worksheet(config.WS_REPORTE_IA)
        ws_matriz = sh.worksheet(config.WS_MATRIZ_RECOMENDACIONES)
        ws_historial = sh.worksheet(config.WS_HISTORIAL_VEREDICTOS)

        # --- CONTEXTO FINANCIERO INTEGRAL ---
        def get_df_raw(ws_name):
            try: 
                df = pd.DataFrame(sh.worksheet(ws_name).get_all_records(value_render_option='UNFORMATTED_VALUE'))
                df.columns = [c.strip().upper() for c in df.columns]
                return df
            except: return pd.DataFrame()

        df_mercado = get_df_raw(config.WS_VARIABLES_MERCADO)
        df_caja = get_df_raw(config.WS_CAJA_LIQUIDEZ)
        df_valoracion = get_df_raw("VALORACION_PORTAFOLIO")

        dolar_mep = 1.0
        if not df_mercado.empty:
            mask_mep = df_mercado['DATO'].str.contains('MEP', case=False, na=False)
            if any(mask_mep):
                dolar_mep = float(str(df_mercado[mask_mep]['VALOR_PROM'].iloc[0]).replace(',', '.'))
        
        contexto_financiero = {
            "variables_market": df_mercado.to_dict('records') if not df_mercado.empty else [],
            "saldos_caja_disponibles": df_caja.to_dict('records') if not df_caja.empty else [],
            "valoracion_cartera_propietarios": df_valoracion.to_dict('records') if not df_valoracion.empty else [],
            "referencia_dolar_mep": dolar_mep
        }
        # ------------------------------------
        
        # 3. CARGA DE MATRIZ (Normalizada para evitar duplicados)
        raw_values = ws_matriz.get_all_values()
        if raw_values:
            columnas_matriz = [c.strip().upper() for c in raw_values[0]]
            df_matriz = pd.DataFrame(raw_values[1:], columns=columnas_matriz)
            # Normalizamos Ticker y Perfil para que la limpieza sea infalible
            df_matriz['TICKER'] = df_matriz['TICKER'].astype(str).str.strip().str.upper()
            df_matriz['PERFIL'] = df_matriz['PERFIL'].astype(str).str.strip().str.upper()
        else:
            columnas_matriz = ["FECHA", "TICKER", "PERFIL", "SENTIMIENTO", "VEREDICTO_IA"]
            df_matriz = pd.DataFrame(columns=columnas_matriz)
        matriz_modificada = False

        reporte_acumulado = []

        modelos = ia_utils.obtener_modelos_activos()
        quota_error = False  # flag to stop processing when cuota/servicio falla
        for index, row in pendientes.iterrows():
            if quota_error:
                break
            ticker = row['TICKER_ID']
            logger.info(f"[*] Analizando confluencia en {ticker}...")

            # --- GUARDIA DE DATOS (Check de Cordura) ---
            apto, motivo = ia_utils.validar_datos_tecnicos(row)
            if not apto:
                error_fatal = f"FALLA DE INTEGRIDAD TÉCNICA CRÍTICA en {ticker}: {motivo}"
                logger.critical(error_fatal)
                procesamiento.registrar_log(sh.worksheet(config.WS_LOG_SISTEMA), "CRITICAL", error_fatal)
                procesamiento.actualizar_estado_proceso(sh.worksheet(config.WS_ESTADO_PROCESOS), "ERROR", error_fatal[:50])
                return False

            # --- ARMADO DEL PROMPT Y VERIFICACIÓN DE DATOS ---
            instrucciones_excel = ws_gen.get('Instrucciones_Fijas', '')
            
            # Debug: Verificar que los campos técnicos tengan datos
            missing = [c for c in ia_utils.CAMPO_TECNICO if c not in row or not str(row[c]).strip()]
            if missing:
                logger.warning(f"Advertencia: Faltan datos para {missing}. Verificando JSON...")
            else:
                logger.info(f"Datos técnicos cargados: {len(ia_utils.CAMPO_TECNICO)} indicadores.")

            # --- INTEGRACIÓN DE NOTICIAS ---
            # Buscamos las noticias recientes del activo y el contexto macro (9999_AR/US)
            noticias_ctx = ia_utils.obtener_noticias_recientes(sh, ticker)

            cuerpo_prompt = ia_utils.crear_prompt(
                row, 
                perfiles_lista, 
                instrucciones_excel, 
                noticias_contexto=noticias_ctx,
                financiero_contexto=contexto_financiero
            )
            
            logro_procesar = False
            config_ia = ia_utils.obtener_config_generacion()
            
            for mod_id in list(modelos): # Copia de la lista para poder modificarla
                if logro_procesar: break
                logger.info(f"Probando modelo: {mod_id}...")
                
                # --- AUDITORÍA Y LIMPIEZA DE PROMPT ---
                try:
                    payload = json.loads(cuerpo_prompt)
                    # Extraemos la metadata de origen (lo que no va a las tablas)
                    metadata_audit = payload.pop("_ORIGEN_DE_DATOS", {})
                    metadata_audit["modelo_seleccionado"] = mod_id
                    metadata_audit["timestamp_envio"] = datetime.now().isoformat()

                    # --- ROTACIÓN DE LOGS (Historial por Ticker) ---
                    audit_log = {
                        "auditoria_fuentes": metadata_audit,
                        "prompt_final_enviado": payload
                    }
                    
                    log_dir = Path("IA_LOGS")
                    log_dir.mkdir(exist_ok=True) # Crea la carpeta si no existe
                    ts_f = datetime.now().strftime("%Y%m%d_%H%M%S")
                    path_log = log_dir / f"req_{ticker}_{ts_f}.json"

                    with open(path_log, "w", encoding="utf-8") as f:
                        json.dump(audit_log, f, indent=4, ensure_ascii=False)
                    
                    # El prompt que realmente viaja a la IA (sin rastro de las tablas/fuentes)
                    cuerpo_enviar = json.dumps(payload, ensure_ascii=False)
                except Exception as e:
                    logger.exception(f"Error al procesar JSON de auditoría: {e}")
                    cuerpo_enviar = cuerpo_prompt

                try:
                    response = client.models.generate_content(
                        model=mod_id, 
                        contents=cuerpo_enviar,
                        config=config_ia
                    )
                    if not response or not response.text:
                        logger.warning("FALLIDO: Respuesta vacía.")
                        continue

                    bloques = [b.strip() for b in response.text.split('===') if b.strip()]
                    if len(bloques) < len(perfiles_lista):
                        # Split resiliente: ignora preámbulo y divide por la etiqueta PERFIL:
                        partes_raw = response.text.split('PERFIL:')
                        bloques = ["PERFIL:" + b.strip() for b in partes_raw if b.strip() and '|' in b]
                    
                    if not bloques:
                        logger.warning("RECHAZADO: Formato irreconocible (sin bloques '===' o 'PERFIL:').")
                        continue

                    perfiles_hallados = []
                    filas_grabar = []
                    ahora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    for bloque in bloques:
                        # Intentar extraer campos clave del bloque
                        partes = {}
                        for p in bloque.split('|'):
                            if ':' in p:
                                k, v = p.split(':', 1)
                                partes[k.strip().upper()] = v.strip()
                        
                        nombre_ia = partes.get('PERFIL', '')
                        usuario_final = "Desconocido"
                        sentimiento = partes.get('SENTIMIENTO', 'Neutral').upper()

                        # Validar si el perfil devuelto coincide con nuestros usuarios
                        for p_riesgo, u_id in mapa_usuarios.items():
                            if p_riesgo.lower() in nombre_ia.lower() or p_riesgo.lower() in bloque.lower():
                                usuario_final = u_id
                                break
                        
                        if usuario_final == "Desconocido":
                            logger.warning(f"Bloque ignorado: Perfil '{nombre_ia}' no reconocido en configuración.")
                            continue

                        # Limpieza de Score y extracción de metadatos
                        score_raw = str(partes.get('SCORE', 'N/A'))
                        score = score_raw.split('/')[0].strip() if "/" in score_raw else score_raw
                        
                        horiz = partes.get('HORIZONTE', 'CORTO PLAZO')
                        riesgo = partes.get('RIESGO', 'N/A')
                        conflu = partes.get('CONFLUENCIA', 'Sin datos de contexto')
                        conviccion = partes.get('CONVICCION', 'Basada en indicadores técnicos')
                        detalle = partes.get('VEREDICTO_IA', 'Sin detalle técnico')

                        # --- GUARDRAILS TÉCNICOS: Validación de Consistencia de Score vs RSI ---
                        try:
                            rsi = float(str(row.get('RSI', 50)).replace(',', '.'))
                        except Exception:
                            rsi = 50.0

                        try:
                            score_num = int(score)
                        except ValueError:
                            score_num = None

                        if score_num is not None:
                            # Regla de Sobrecompra (RSI > 70): Evitar compras de alto riesgo. Si es alcista, máximo score = 6
                            if rsi > 70:
                                if "BULL" in sentimiento or "COMPR" in sentimiento:
                                    if score_num > 6:
                                        score = "6"
                                        detalle = f"{detalle} [Ajuste Guardrail: Score limitado a 6/10 por sobrecompra (RSI: {rsi:.1f})]"

                            # Regla de Sobreprecio Cambiario CCL (Desvío > +2.5% sobre la media o sobre el Dólar MEP de referencia):
                            try:
                                ccl_activo = float(str(row.get('CCL_IMPLICITO', 0.0)).replace(',', '.'))
                            except Exception:
                                ccl_activo = 0.0

                            if ccl_activo > 500:
                                # 1. Desvío contra Dólar MEP de referencia (si existe)
                                if dolar_mep > 1.0:
                                    desvio_mep = (ccl_activo - dolar_mep) / dolar_mep
                                    if desvio_mep > 0.025:
                                        desvio_mep_pct = desvio_mep * 100
                                        if "BULL" in sentimiento or "COMPR" in sentimiento:
                                            if score_num > 5:
                                                score = "5"
                                            detalle = f"{detalle} [Alerta MEP: Compra penalizada por sobreprecio cambiario de +{desvio_mep_pct:.1f}% respecto al Dólar MEP (${dolar_mep:.1f}). CCL Implícito: ${ccl_activo:.1f}]"
                                        else:
                                            detalle = f"{detalle} [Alerta MEP: Brecha cambiaria alta de +{desvio_mep_pct:.1f}% respecto al Dólar MEP (CCL: {ccl_activo:.1f} vs MEP: {dolar_mep:.1f})]"
                                    elif desvio_mep <= 0.015:
                                        if "BULL" in sentimiento or "COMPR" in sentimiento:
                                            msg_tele = (
                                                f"⚡ *[Oportunidad]* El CEDEAR *{ticker.upper()}* presenta brecha cambiaria baja del "
                                                f"{desvio_mep * 100:.1f}% respecto al MEP de referencia (${dolar_mep:.1f}) y "
                                                f"sentimiento alcista ({sentimiento}) para el perfil *{usuario_final}*."
                                            )
                                            notificador_telegram.enviar_mensaje_telegram(msg_tele)

                                # 2. Desvío clásico contra la media de Cedears (para confluencia de mercado)
                                if ccl_promedio > 0:
                                    desvio_ccl = (ccl_activo - ccl_promedio) / ccl_promedio
                                    if desvio_ccl > 0.025:
                                        desvio_pct = desvio_ccl * 100
                                        if "BULL" in sentimiento or "COMPR" in sentimiento:
                                            if score_num > 6:
                                                score = "6"
                                            detalle = f"{detalle} [Ajuste Guardrail: Compra advertida por sobreprecio CCL (+{desvio_pct:.1f}% sobre la media de Cedears). CCL Activo: {ccl_activo:.1f} vs Promedio: {ccl_promedio:.1f}]"
                                        else:
                                            detalle = f"{detalle} [Alerta CCL: El CEDEAR cotiza con un sobreprecio del +{desvio_pct:.1f}% respecto a la media de Cedears (CCL: {ccl_activo:.1f} vs Promedio: {ccl_promedio:.1f})]"

                        # Unificamos el formato: siempre mostramos la confluencia de noticias
                        prefix = "CONTRADICCION TECNICA: " if "CONTRADICCION" in sentimiento else ""
                        veredicto_final = (
                            f"HORIZONTE: {horiz.upper()}\n"
                            f"CONVICCION: {conviccion}\n"
                            f"SCORE: {score}/10\n"
                            f"RIESGO: {riesgo.upper()}\n"
                            f"CONFLUENCIA NOTICIAS: {conflu}\n"
                            f"ANALISIS: {prefix}{detalle}"
                        )
                        
                        if "CONTRADICCION" in sentimiento:
                            logger.warning(f"Contradicción registrada para {usuario_final}")

                        filas_grabar.append([
                            ahora_str, ticker.upper(), usuario_final,
                            sentimiento,
                            veredicto_final
                        ])
                        perfiles_hallados.append(usuario_final)

                    # Validación de integridad: si el modelo no generó todos los perfiles, pasamos al siguiente
                    if len(filas_grabar) < len(perfiles_lista):
                        logger.warning(f"FALLIDO: El modelo solo generó {len(filas_grabar)} de {len(perfiles_lista)} perfiles.")
                        continue

                    if filas_grabar:
                        # 1. Actualizar Matriz: Borrado total de seguridad para este Ticker
                        if not df_matriz.empty:
                            df_matriz = df_matriz[df_matriz['TICKER'] != ticker.upper()].copy()

                        # Construir registros mapeando columnas por nombre para evitar desalineación
                        nuevos_datos = []
                        for f in filas_grabar:
                            nuevos_datos.append({
                                "FECHA": f[0], "TICKER": f[1], "PERFIL": f[2],
                                "SENTIMIENTO": f[3], "VEREDICTO_IA": f[4]
                            })
                        
                        df_nuevas = pd.DataFrame(nuevos_datos)
                        df_matriz = pd.concat([df_matriz, df_nuevas], ignore_index=True)
                        
                        # 2. Acumular Reporte (Copia exacta de los datos de la matriz para historial)
                        reporte_acumulado.extend(filas_grabar)
                        df_tecnico.at[index, 'ESTADO'] = "PROCESADO"
                        matriz_modificada = True
                        logger.info(f"ACEPTADO: {len(perfiles_hallados)}/{len(perfiles_lista)} perfiles generados.")
                    
                    # Si el modelo respondió (aunque sea con contradicciones), lo damos por procesado
                    if len(bloques) > 0:
                        logro_procesar = True 
                        activos_procesados += 1
                        break
                    else:
                        logger.warning("RECHAZADO: El modelo respondió pero no se identificaron perfiles válidos.")

                except Exception as e:
                    err_msg = str(e)
                    # Detect quota or service unavailable errors
                    if "RESOURCE_EXHAUSTED" in err_msg or "UNAVAILABLE" in err_msg:
                        logger.error(f"Cuota agotada o servicio no disponible en {mod_id}.")
                        quota_error = True
                    elif "404" in err_msg or "not found" in err_msg.lower():
                        logger.warning(f"DESCARTADO: El modelo '{mod_id}' no existe o no está disponible.")
                        if mod_id in modelos:
                            modelos.remove(mod_id)
                    else:
                        logger.error(f"ERROR TÉCNICO en {mod_id}: {err_msg[:200]}")
                time.sleep(1) # Pausa mínima entre reintentos de modelos

            if not logro_procesar:
                errores += 1
                logger.warning("No se pudo procesar este activo con ninguno de los modelos candidatos.")
                time.sleep(10)
            else:
                logger.info("Esperando 4 segundos para cuidar cuota (15 RPM free tier)...")
                time.sleep(4)

        # Guardar cambios
        logger.info("Sincronizando resultados con Google Sheets...")
        ws_analisis.update([df_tecnico.columns.values.tolist()] + df_tecnico.values.tolist())
        
        if reporte_acumulado:
            ws_reporte.append_rows(reporte_acumulado)
            try:
                ws_historial.append_rows(reporte_acumulado)
                logger.info("[+] Historial de veredictos guardado en HISTORIAL_VEREDICTOS.")
            except Exception as e_h:
                logger.error(f"[-] No se pudo guardar historial de veredictos: {e_h}")
            
        if matriz_modificada:
            # Reordenar columnas para asegurar consistencia con el encabezado antes de grabar
            orden_columnas = ["FECHA", "TICKER", "PERFIL", "SENTIMIENTO", "VEREDICTO_IA"]
            # Aseguramos que todas las columnas existan antes de reordenar
            df_matriz = df_matriz.reindex(columns=orden_columnas)
            # Limpieza final de duplicados accidentales
            df_matriz = df_matriz.drop_duplicates(subset=['TICKER', 'PERFIL'], keep='last')
            
            ws_matriz.clear()
            ws_matriz.update([orden_columnas] + df_matriz.values.tolist())

        resumen = f"Motor completado. Activos: {len(df_tecnico)}. Procesados: {activos_procesados}."
        logger.info(resumen)
        procesamiento.registrar_log(sh.worksheet(config.WS_LOG_SISTEMA), "INFO", resumen)
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        
        if activos_procesados == 0 and len(pendientes) > 0:
            procesamiento.actualizar_estado_proceso(sh.worksheet(config.WS_ESTADO_PROCESOS), "ERROR", "No se pudo procesar ningún activo por cuota", tiempo_ejecucion=duracion)
            return False
            
        procesamiento.actualizar_estado_proceso(sh.worksheet(config.WS_ESTADO_PROCESOS), "OK", f"Recs: {activos_procesados}", tiempo_ejecucion=duracion)
        logger.info(f"Tiempo total de ejecución: {duracion}")
        return True

    except Exception as e:
        msg = f"ERROR CRÍTICO MOTOR IA: {e}"
        logger.critical(msg)  # ✅ Siempre se registra en terminal
        
        # Solo intenta registrar en Google Sheets si la conexión existe
        if sh is not None:
            try:
                procesamiento.registrar_log(sh.worksheet(config.WS_LOG_SISTEMA), "CRITICAL", msg)
                procesamiento.actualizar_estado_proceso(sh.worksheet(config.WS_ESTADO_PROCESOS), "ERROR", "Falla global")
            except Exception as sheet_error:
                logger.critical(f"No se pudo registrar en Google Sheets: {sheet_error}")
                return False  # ❌ Termina el proceso si Sheets falla
        
        return False

if __name__ == "__main__":
    ejecutar_decisor()
