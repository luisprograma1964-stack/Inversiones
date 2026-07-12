"""
Supervisor del Sistema de Inversiones.
Analiza la calidad del proceso, audita el descarte de noticias y sugiere mejoras 
en los diccionarios de datos (sinónimos, filtros y nuevos activos).
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
import pandas as pd
from google import genai
import auth_google
import config
import procesamiento
import ia_utils
import logging_config

logger = logging_config.get_logger(__name__)


def inicializar_motor_ia():
    """Inicializa la conexión a Google Sheets y cliente de IA para el Super Decisor."""
    sh = auth_google.conectar()
    if not sh:
        raise RuntimeError("No se pudo conectar a Google Sheets con las credenciales configuradas.")

    key = config.get_gemini_api_key()

    client = genai.Client(api_key=key)
    return sh, client


def limpiar_reportes_antiguos(dias=30):
    """Borra reportes estratégicos antiguos de la carpeta ESTRATEGIA_REPORTS para no acumular basura."""
    try:
        report_dir = Path(config.DIR_ESTRATEGIA)
        if not report_dir.exists():
            return
        
        ahora = time.time()
        limite = ahora - (dias * 86400) # 86400 segundos = 1 día
        
        borrados = 0
        for archivo in report_dir.glob("Supervision_Sistema_*.md"):
            if archivo.is_file():
                if archivo.stat().st_mtime < limite:
                    archivo.unlink()
                    borrados += 1
        
        for archivo in report_dir.glob("Estrategia_*.md"):
            if archivo.is_file():
                if archivo.stat().st_mtime < limite:
                    archivo.unlink()
                    borrados += 1
                    
        if borrados > 0:
            logger.info(f"[*] Mantenimiento Supervisor: Se eliminaron {borrados} reportes antiguos (> {dias} días).")
            print(f"[*] Mantenimiento: Se eliminaron {borrados} reportes antiguos de {config.DIR_ESTRATEGIA}.")
    except Exception as e:
        logger.exception(f"Error al limpiar reportes antiguos: {e}")


def ejecutar_supervisor():
    import notificador_telegram
    # notificador_telegram.enviar_mensaje_telegram("🚀 <b>[Supervisor]</b> Iniciando Análisis y Auditoría del Sistema...")
    print("[*] Iniciando Supervisor del Sistema...")
    logger.info("" + "X"*60)
    logger.info(f"SUPERVISOR Y MEJORADOR DEL SISTEMA | {datetime.now().strftime('%H:%M:%S')}")
    logger.info("X"*60)
    t_inicio = time.time()
    
    # Mantenimiento de reportes viejos antes de iniciar
    limpiar_reportes_antiguos(dias=30)
    
    try:
        sh, client = inicializar_motor_ia()
    except Exception as e:
        logger.critical(f"ERROR CRÍTICO SUPERVISOR: {e}")
        return None

    ws_log = sh.worksheet(config.WS_LOG_SISTEMA)
    ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)
    procesamiento.registrar_log(ws_log, "INFO", "Iniciando Supervisor del Sistema")
    procesamiento.actualizar_estado_proceso(ws_status, "PROCESANDO", "Auditando calidad del sistema...", nombre_proceso="supervisor_del_sistema")

    try:
        # 1. RECOLECCIÓN DE DATOS PARA EL CONTEXTO GLOBAL
        def get_df(ws_name):
            try: 
                df = pd.DataFrame(sh.worksheet(ws_name).get_all_records(value_render_option='UNFORMATTED_VALUE'))
                # Estandarizamos cabeceras a mayúsculas para evitar errores de casing
                df.columns = [c.strip().upper() for c in df.columns]
                return df
            except: return pd.DataFrame()

        df_matriz = get_df(config.WS_MATRIZ_RECOMENDACIONES)
        df_maestro = get_df(config.WS_MAESTRO_ACTIVOS)
        df_tecnico = get_df(config.WS_ANALISIS_TECNICO)
        df_noticias = get_df(config.WS_NOTICIAS_SISTEMA)
        df_ia_usuarios = get_df(config.WS_CARTERAS)
        df_sinonimos_actuales = get_df(config.WS_CONFIG_SINONIMOS)
        df_mercado = get_df(config.WS_VARIABLES_MERCADO)
        df_descartes = get_df(config.WS_NOTICIAS_DESCARTADAS).tail(20) # Últimos descartes
        df_sug_raw = get_df(config.WS_SUGERENCIAS_SINONIMOS)
        df_valoracion = get_df("VALORACION_PORTAFOLIO")
        df_caja = get_df(config.WS_CAJA_LIQUIDEZ)
        df_procesos = get_df(config.WS_ESTADO_PROCESOS)
        df_logs = get_df(config.WS_LOG_SISTEMA)
        # 1.1 Filtrar sugerencias de sinónimos pendientes en toda la hoja (no solo las últimas 20)
        if not df_sug_raw.empty:
            # Si el campo ESTADO está vacío, se asume PENDIENTE por compatibilidad
            estado_sug = df_sug_raw['ESTADO'].astype(str).str.strip().str.upper()
            df_sugerencias = df_sug_raw[(estado_sug == 'PENDIENTE') | (estado_sug == '')]
        else:
            df_sugerencias = df_sug_raw

        # 1.2 Chequeo de actualizaciones de Comafi vs Maestro
        df_cedears = get_df(config.WS_PROGRAMA_CEDEARS)
        nuevos_cedears = []
        if not df_cedears.empty and not df_maestro.empty:
            subyacentes_comafi = set(df_cedears['TICKER_SUBYACENTE'].astype(str).str.strip().str.upper().unique())
            tickers_maestro = set(df_maestro['TICKER_ID'].astype(str).str.strip().str.upper())
            nuevos_cedears = list(subyacentes_comafi - tickers_maestro)

        # 1.3 Resumen de cobertura de noticias para detectar "silencios"
        tickers_con_noticias = []
        fecha_max_noticias = None
        if not df_noticias.empty and 'TICKER_ID' in df_noticias.columns:
            tickers_con_noticias = df_noticias['TICKER_ID'].unique().tolist()
            if 'FECHA' in df_noticias.columns:
                try:
                    df_noticias['FECHA_DT'] = pd.to_datetime(df_noticias['FECHA'], errors='coerce')
                    fecha_max_noticias = df_noticias['FECHA_DT'].max()
                except:
                    pass

        # 1.4 Cálculo de Equity Consolidado (ARS/USD) por Propietario
        dolar_mep = 1350.0 # Fallback realista
        if not df_mercado.empty:
            mask_dolar = df_mercado['DATO'].astype(str).str.contains('MEP|Comafi|CCL', case=False, na=False)
            if any(mask_dolar):
                try:
                    val_dolar = str(df_mercado[mask_dolar]['VALOR_PROM'].iloc[0]).replace(',', '.')
                    dolar_mep = float(val_dolar)
                except Exception:
                    pass
        
        patrimonios_por_propietario = {}
        if not df_caja.empty:
            for _, r in df_caja.iterrows():
                try:
                    prop = str(r.get('PROPIETARIO', 'LUIS')).strip()
                    moneda = str(r.get('MONEDA', 'ARS')).upper()
                    saldo = float(str(r.get('SALDO', 0)).replace(',', '.'))
                    
                    if prop not in patrimonios_por_propietario:
                        patrimonios_por_propietario[prop] = {"total_ars": 0.0, "total_usd_mep": 0.0}
                        
                    if "ARS" in moneda or "PESO" in moneda:
                        patrimonios_por_propietario[prop]["total_ars"] += saldo
                        patrimonios_por_propietario[prop]["total_usd_mep"] += saldo / dolar_mep
                    else:
                        patrimonios_por_propietario[prop]["total_usd_mep"] += saldo
                        patrimonios_por_propietario[prop]["total_ars"] += saldo * dolar_mep
                except Exception:
                    pass

        # 2. ARMADO DEL PAYLOAD PARA LA IA ESTRATÉGICA
        ahora_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        payload = {
            "configuracion_usuario": df_ia_usuarios.to_dict('records') if not df_ia_usuarios.empty else [],
            "patrimonio_consolidado_por_propietario": patrimonios_por_propietario,
            "cotizacion_dolar_usada": dolar_mep,
            "valoracion_y_tenencias_cartera": df_valoracion.to_dict('records') if not df_valoracion.empty else [],
            "estado_actual_matriz": df_matriz.to_dict('records') if not df_matriz.empty else [],
            "variables_mercado": df_mercado.to_dict('records') if not df_mercado.empty else [],
            "datos_tecnicos_vigentes": df_tecnico[['TICKER_ID', 'TREND', 'RSI', 'FIBO_RET', 'FECHA_PRECIO_ACTUAL', 'CCL_IMPLICITO']].to_dict('records') if not df_tecnico.empty and 'CCL_IMPLICITO' in df_tecnico.columns else (df_tecnico[['TICKER_ID', 'TREND', 'RSI', 'FIBO_RET', 'FECHA_PRECIO_ACTUAL']].to_dict('records') if not df_tecnico.empty else []),
            "maestro_filtros": df_maestro[['TICKER_ID', 'FILTRO_NOTICIAS', 'ESTADO']].to_dict('records') if not df_maestro.empty and 'TICKER_ID' in df_maestro.columns else [],
            "tickers_con_noticias_recientes": tickers_con_noticias,
            "auditoria_noticias": {
                "ultimos_descartes": df_descartes[['TITULAR', 'MOTIVO_DESCARTE', 'SUBMODULO']].to_dict('records') if not df_descartes.empty and 'TITULAR' in df_descartes.columns else [],
                "sugerencias_pendientes_sinonimos": len(df_sugerencias)
            },
            "auditoria_cedears_comafi": {
                "nuevos_cedears_detectados": nuevos_cedears,
                "cantidad_nuevos": len(nuevos_cedears)
            }
        }

        # 3. PROMPT ESTRATÉGICO
        prompt_estrategico = f"""
        Actúas como un Director de Inversiones (CIO) Senior y Auditor de Calidad del Sistema. Tu doble misión es:
        1. Evaluar y auditar la calidad del proceso técnico y noticias (QA/Optimizer).
        2. Traducir el estado financiero y las oportunidades en órdenes de rebalanceo de cartera accionables según el Mix_Target del usuario.
        
        CONTEXTO DEL SISTEMA:
        {json.dumps(payload, indent=2, ensure_ascii=False)}
        
        TAREAS OBLIGATORIAS:
        1. GESTIÓN Y REBALANCEO DE CARTERA: 
           - Revisa 'configuracion_usuario' (Mix_Target), 'patrimonio_consolidado_por_propietario' y 'valoracion_y_tenencias_cartera'.
           - Genera órdenes concretas y directas de rebalanceo segmentadas por propietario.
        2. RADAR DE OPORTUNIDADES (EXPANSIÓN): 
           - Identifica activos que el usuario no tiene actualmente pero que muestran alta convicción en 'estado_actual_matriz' (Score >= 8).
        3. MEJORADOR DE DATOS: 
           - Si un activo importante no trae noticias en absoluto, sugiere la acción: 'Cambia el filtro de X por Y en el Maestro'.
        4. ACTIVACIÓN DE ACTIVOS INACTIVOS: 
           - Si un activo está INACTIVO pero tiene noticias relevantes, alerta para considerarlo activarlo.
        5. COMPARATIVA E INTEGRIDAD (AUDITORÍA): 
           - Detecta si el técnico tiene un rezago mayor a 48 horas frente a las noticias aprobadas.
        6. ANÁLISIS DE CONTRADICCIÓN TÉCNICA: 
           - Identifica discrepancias severas entre el veredicto de la IA y la realidad técnica.
           - REGLA ESPECIAL ARGENTINA: Ignorar valores extremos de RSI (como 100) para pares de divisas como USDARS. Al estar regulados por crawling peg, suben matemáticamente todos los días sin bajas, por lo que el RSI pierde validez y no debe ser reportado como sobrecompra o anomalía.
        7. ALERTAS DE SILENCIO: Activos que suben/bajan fuerte pero nuestro radar de noticias no sabe por qué.
        8. OPTIMIZACIÓN DE PROMPTS (CALIDAD DEL TRIAGE Y ESTRATEGIA): 
           - Si la IA descartó erróneamente una noticia (ej. macroeconomía tomada como corporativa), sugiere de forma explícita cómo ajustar el 'Prompt_Triage_Noticias' detallando la sección lógica.
           - Secciones lógicas en 'Instrucciones_Fijas': [SECCIÓN 1...], [SECCIÓN 2...], etc.
           - Secciones lógicas en 'Prompt_Triage_Noticias': [SECCIÓN 1...], [SECCIÓN 2...], etc.
           
        FORMATO DE SALIDA (JSON OBLIGATORIO):
        Debes retornar ÚNICAMENTE un objeto JSON con la siguiente estructura exacta, sin Markdown extra fuera del JSON:
        {{
          "resumen_ejecutivo": "Texto breve de 1-2 párrafos resumiendo el estado del sistema y la cartera.",
          "alertas_criticas_texto": "Texto en viñetas con los errores graves o contradicciones detectadas.",
          "cuerpo_markdown": "El reporte detallado narrado en Markdown. Comienza directamente con '## ESTRATEGIA DE CARTERA', no incluyas ningún título de nivel 1. Desarrolla aquí todo el informe.",
          "alertas_inbox": [
             {{
               "categoria": "ALERTA_CRITICA",
               "tipo": "ERROR_TECNICO / CONTRADICCION_TECNICA / BRECHA_CCL",
               "mensaje": "Mensaje súper claro diseñado para que el usuario me lo copie en el chat. Ej: 'Hay una contradicción en TSLA, por favor analizalo.'"
             }},
             {{
               "categoria": "MEJORA_CONSTANTE",
               "tipo": "AJUSTE_PROMPT",
               "mensaje": "Texto claro para que el usuario me lo copie. Ej: 'Actualizá la Sección 2 del Triage agregando esta regla: ...'"
             }}
          ]
        }}
        """

        # 4. CONSULTA A GEMINI (Usamos Pro si está disponible para máxima calidad estratégica)
        import google.genai.types as types
        modelos_activos = ia_utils.obtener_modelos_activos()
        candidatos = ia_utils.obtener_modelos_activos()

        informe_json_str = None
        ultimo_error = None
        modelo_exitoso = None

        for modelo_candidato in candidatos:
            logger.info(f"Generando informe estratégico con {modelo_candidato} (JSON mode)...")
            try:
                response = client.models.generate_content(
                    model=modelo_candidato,
                    contents=prompt_estrategico,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                    )
                )
                if response and response.text:
                    informe_json_str = response.text
                    modelo_exitoso = modelo_candidato
                    logger.info(f"¡Informe estratégico generado con éxito usando {modelo_candidato}!")
                    break
            except Exception as e:
                ultimo_error = e
                logger.warning(f"Error generando informe con {modelo_candidato}: {e}. Intentando fallback...")
                time.sleep(1)

        if not informe_json_str:
            raise RuntimeError(f"Todos los modelos de IA fallaron. Último error: {ultimo_error}")

        try:
            # Remover posibles bloques markdown de código si la IA ignoró las instrucciones de solo JSON
            limpio = informe_json_str.strip()
            if limpio.startswith("```json"): limpio = limpio[7:]
            if limpio.startswith("```"): limpio = limpio[3:]
            if limpio.endswith("```"): limpio = limpio[:-3]
            
            informe_dict = json.loads(limpio.strip())
        except Exception as e:
            logger.error(f"Error parseando el JSON de Gemini: {e}")
            informe_dict = {
                "resumen_ejecutivo": "Error parseando respuesta IA",
                "alertas_criticas_texto": str(e),
                "cuerpo_markdown": informe_json_str,
                "alertas_inbox": []
            }

        # --- PREPARAR ALERTAS DETERMINISTAS ---
        alertas_inbox_total = []
        ahora_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Nuevos Cedears
        for idx, nc in enumerate(nuevos_cedears):
            alertas_inbox_total.append([
                f"AL-NC-{int(time.time())}-{idx}",
                ahora_timestamp,
                "MEJORA_CONSTANTE",
                "NUEVO_ACTIVO",
                f"Nuevo activo detectado en Comafi: {nc}. Presiona [Inicializar Nuevos Activos] para agregarlo al Maestro.",
                "PENDIENTE"
            ])
            
        # Sinónimos Pendientes
        if len(df_sugerencias) > 0:
            alertas_inbox_total.append([
                f"AL-SIN-{int(time.time())}",
                ahora_timestamp,
                "MEJORA_CONSTANTE",
                "SINONIMO_PENDIENTE",
                f"Tienes {len(df_sugerencias)} sugerencias de sinónimos pendientes. Ve a la pestaña 'Control de Sinónimos' para aprobarlos.",
                "PENDIENTE"
            ])
            
        # Errores Técnicos (Escala / -1)
        if not df_tecnico.empty:
            for idx, row in df_tecnico.iterrows():
                try:
                    rsi = row.get('RSI')
                    fibo = str(row.get('FIBO_RET', ''))
                    if rsi == -1 or 'Error' in fibo:
                        alertas_inbox_total.append([
                            f"AL-ERR-{int(time.time())}-{idx}",
                            ahora_timestamp,
                            "ALERTA_CRITICA",
                            "ERROR_TECNICO",
                            f"El activo {row.get('TICKER_ID', 'N/A')} fue bloqueado por seguridad (RSI=-1 o Error Escala 15x). Copia esto y pasáselo a Antigravity.",
                            "PENDIENTE"
                        ])
                except:
                    pass


        # Alerta CCL Determinista
        if not df_tecnico.empty and 'CCL_IMPLICITO' in df_tecnico.columns:
            df_tecnico_ccl = df_tecnico.copy()
            df_tecnico_ccl['CCL_IMPLICITO'] = pd.to_numeric(df_tecnico_ccl['CCL_IMPLICITO'].astype(str).str.replace(',', '.'), errors='coerce')
            df_ccl_valid = df_tecnico_ccl.dropna(subset=['CCL_IMPLICITO'])
            
            if not df_ccl_valid.empty:
                ccl_promedio = df_ccl_valid['CCL_IMPLICITO'].mean()
                tickers_caros = []
                for idx, row in df_ccl_valid.iterrows():
                    ccl_activo = row['CCL_IMPLICITO']
                    if ccl_promedio > 0:
                        desvio = ((ccl_activo / ccl_promedio) - 1) * 100
                        if desvio > 2.5:
                            tickers_caros.append(row['TICKER_ID'])
                
                if tickers_caros:
                    tickers_str = ", ".join(tickers_caros)
                    alertas_inbox_total.append([
                        f"AL-CCL-{int(time.time())}",
                        ahora_timestamp,
                        "ALERTA_CRITICA",
                        "BRECHA_CCL",
                        f"Alerta CCL: Los activos {tickers_str} cotizan con un sobreprecio >2.5% respecto a la media del mercado. Evaluar suspender compras locales.",
                        "PENDIENTE"
                    ])

        # Alerta de Apagón de Noticias (Noticias obsoletas > 48hs)
        if fecha_max_noticias is not None and not pd.isna(fecha_max_noticias):
            antiguedad_horas = (datetime.now() - fecha_max_noticias).total_seconds() / 3600
            if antiguedad_horas > 48:
                alertas_inbox_total.append([
                    f"AL-NEWS-{int(time.time())}",
                    ahora_timestamp,
                    "ALERTA_CRITICA",
                    "APAGON_NOTICIAS",
                    f"¡ALERTA DE APAGÓN! La noticia más reciente en el sistema tiene {int(antiguedad_horas)} horas de antigüedad. El scraper podría estar fallando o bloqueado.",
                    "PENDIENTE"
                ])

        # Alerta de Recomendaciones Obsoletas (> 2hs)
        if not df_matriz.empty and 'FECHA' in df_matriz.columns:
            try:
                df_matriz_fechas = pd.to_datetime(df_matriz['FECHA'], errors='coerce')
                min_fecha_matriz = df_matriz_fechas.min()
                if pd.notna(min_fecha_matriz):
                    antiguedad_recs = (datetime.now() - min_fecha_matriz).total_seconds() / 3600
                    if antiguedad_recs > 2:
                        alertas_inbox_total.append([
                            f"AL-MATRIZ-{int(time.time())}",
                            ahora_timestamp,
                            "ALERTA_CRITICA",
                            "RECOMENDACIONES_OBSOLETAS",
                            f"ALERTA CRITICA: Se detectaron recomendaciones en la Matriz con más de 2 horas de antigüedad ({int(antiguedad_recs)}hs). El motor de IA (decisor_con_ia) no se ejecutó inmediatamente después del análisis técnico o falló. Las decisiones en el dashboard son obsoletas y peligrosas.",
                            "PENDIENTE"
                        ])
        # Alerta de Procesos en Error (Motor Caído)
        if not df_procesos.empty and 'ESTADO' in df_procesos.columns:
            procesos_caidos = df_procesos[df_procesos['ESTADO'].astype(str).str.strip().str.upper() == 'ERROR']
            for _, proc in procesos_caidos.iterrows():
                nombre_proc = proc.get('NOMBRE_PROCESO', 'Desconocido')
                detalle_err = proc.get('DETALLE', 'Sin detalle')
                alertas_inbox_total.append([
                    f"AL-PROC-{int(time.time())}",
                    ahora_timestamp,
                    "ALERTA_CRITICA",
                    "PROCESO_CAIDO",
                    f"ALERTA CRITICA: El proceso '{nombre_proc}' se encuentra en estado ERROR. Detalle: {detalle_err}",
                    "PENDIENTE"
                ])

        # Alerta de Errores Críticos Recientes en el Log del Sistema (Últimas 12 horas)
        if not df_logs.empty and 'FECHA' in df_logs.columns and 'NIVEL' in df_logs.columns:
            try:
                df_logs_fechas = pd.to_datetime(df_logs['FECHA'], errors='coerce')
                doce_horas_atras = datetime.now() - pd.Timedelta(hours=12)
                errores_recientes = df_logs[
                    (df_logs['NIVEL'].astype(str).str.strip().str.upper() == 'ERROR') & 
                    (df_logs_fechas >= doce_horas_atras)
                ]
                if not errores_recientes.empty:
                    alertas_inbox_total.append([
                        f"AL-LOGS-{int(time.time())}",
                        ahora_timestamp,
                        "ALERTA_CRITICA",
                        "ERRORES_SISTEMA",
                        f"ALERTA CRITICA: Se detectaron {len(errores_recientes)} errores en el log del sistema (LOG_SISTEMA) en las últimas 12 horas. Revisa la consola para más detalles.",
                        "PENDIENTE"
                    ])
            except Exception:
                pass


        # Agregar Alertas de IA
        alertas_ia = informe_dict.get("alertas_inbox", [])
        for idx, a in enumerate(alertas_ia):
            cat = str(a.get("categoria", "MEJORA_CONSTANTE")).strip()
            tip = str(a.get("tipo", "SUGERENCIA_IA")).strip()
            msg = str(a.get("mensaje", "")).strip()
            if msg:
                alertas_inbox_total.append([
                    f"AL-IA-{int(time.time())}-{idx}",
                    ahora_timestamp,
                    cat,
                    tip,
                    msg,
                    "PENDIENTE"
                ])

        # --- GENERAR PUNTO 1: ESTRUCTURA DE INPUTS DE LA IA DECISORA (DETERMINISTA) ---
        campos_tecnicos = ia_utils.CAMPO_TECNICO
        punto_1_audit = f"""# INFORME DE SUPERVISIÓN Y MEJORA ESTRATÉGICA

## 📋 1. ESTRUCTURA DE INPUTS DE LA IA DECISORA (AUDITORÍA)

Este apartado detalla el catálogo completo de datos y campos que se inyectan dinámicamente en el prompt de la IA decisora (`decisor_con_ia.py`), agrupados por su origen de datos en Google Sheets:

### 📊 Origen: `ANALISIS_TECNICO` (Datos Técnicos del Activo)
Métricas matemáticas y de precio que definen la situación técnica de cada Ticker:
* **Identificación**: `TICKER_ID`, `FECHA` (Fecha de cálculo).
* **Indicadores Técnicos**: {", ".join([f"`{c}`" for c in campos_tecnicos])}
* **Valores de Control**: `ESTADO` (Debe ser `PENDIENTE` para procesar).

### 📰 Origen: `NOTICIAS_SISTEMA` (Contexto Fundamental y Sentimiento)
Noticias recolectadas en paralelo y filtradas por la IA. Se inyectan las 5 más recientes del Ticker y las 5 más recientes de contexto macroeconómico global (Ticker 9999):
* **Campos por noticia**: `FECHA`, `TITULAR`, `RESUMEN_IA`, `SENTIMIENTO`, `FUENTE`.

### 💼 Origen: `VALORACION_PORTAFOLIO` (Situación de Cartera)
Tenencias y rentabilidades consolidadas por propietario calculadas en el Paso 3.8:
* **Campos**: `PROPIETARIO`, `ACTIVO`, `CANTIDAD`, `PRECIO_PROMEDIO_COMPRA`, `VALORACION_MERCADO`, `RENTABILIDAD_NOMINAL`, `RENTABILIDAD_REAL_PERC`.

### 💵 Origen: `CAJA_LIQUIDEZ` (Saldos Disponibles)
Saldos líquidos por cuenta, propietario y moneda (ARS, USD, MEP):
* **Campos**: `MONEDA`, `SALDO`, `TIPO_CUENTA`, `ULTIMA_ACTUALIZACION`, `PROPIETARIO`.

### 📈 Origen: `VARIABLES_MERCADO` (Contexto de Referencia Financiera)
Monitoreo de tipos de cambio de referencia e inflación:
* **Campos**: `DATO`, `VALOR_PROM`, `VALOR_MIN`, `VALOR_MAX`, `GAP_PERC`.

### 👥 Origen: `CONFIG_IA_USUARIO` (Perfiles y Reglas del Inversor)
Define la política y ponderaciones que la IA debe contrastar:
* **Campos**: `Usuario_ID`, `Perfil_Riesgo`, `Mix_Target`, `Tolerancia_Desvio`.

---

"""
        informe_completo_md = punto_1_audit + str(informe_dict.get("cuerpo_markdown", ""))

        # 5. GUARDAR REPORTE EN GOOGLE SHEETS
        try:
            ws_supervisor = sh.worksheet(config.WS_REPORTE_SUPERVISOR)
            ahora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            resumen = str(informe_dict.get("resumen_ejecutivo", ""))[:800]
            alertas_txt = str(informe_dict.get("alertas_criticas_texto", ""))[:800]
            
            row = [ahora_str, resumen, alertas_txt, "N/A", informe_completo_md]
            ws_supervisor.append_row(row)
            
            # Guardar alertas estructuradas
            if alertas_inbox_total:
                try:
                    ws_alertas = sh.worksheet(config.WS_ALERTAS_SUPERVISOR)
                    ws_alertas.append_rows(alertas_inbox_total)
                except Exception as ea:
                    logger.error(f"Error insertando en ALERTAS_SUPERVISOR: {ea}")
            
            # Chequear si hubo un error de Telegram (Alerta Crítica)
            hay_alerta_critica = any(a[2] == "ALERTA_CRITICA" for a in alertas_inbox_total)
            if hay_alerta_critica:
                import notificador_telegram
                notificador_telegram.enviar_mensaje_telegram(f"🚨 <b>[Supervisor]</b> Se han detectado ALERTAS CRÍTICAS en el sistema. Revisa la bandeja de entrada en la Web App de inmediato.")
                
            path_md = "Google Sheets: REPORTE_SUPERVISOR y ALERTAS_SUPERVISOR"
            logger.info("[+] Reporte guardado en hoja REPORTE_SUPERVISOR")
        except Exception as esh:
            path_md = "ERROR AL GUARDAR EN SHEETS"
            logger.error(f"[-] Error guardando reporte en Sheets: {esh}")
            

        # 6. SALIDA POR TERMINAL Y REGISTRO
        try:
            print(f"\n[OK] Informe de supervisión guardado en: {path_md}\n")
            print("="*60)
            print("INFORME DE SUPERVISIÓN Y MEJORA ESTRATÉGICA:")
            print(informe_completo_md)
            print("="*60)
        except UnicodeEncodeError:
            pass
        
        logger.info("="*60)
        logger.info("INFORME DE SUPERVISIÓN Y MEJORA")
        logger.info(f"Reporte guardado en: {path_md}")
        logger.info("="*60)
 
        # Guardar en log histórico
        procesamiento.registrar_log(ws_log, "INFO", f"Informe de supervisión generado exitosamente (modelo: {modelo_exitoso})", "SUPERVISOR")
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        procesamiento.actualizar_estado_proceso(ws_status, "OK", f"Informe generado ({modelo_exitoso})", nombre_proceso="supervisor_del_sistema", tiempo_ejecucion=duracion)
        print(f"[OK] Supervisor finalizado exitosamente en {duracion}.\n")
        import notificador_telegram
        notificador_telegram.enviar_mensaje_telegram(f"✅ <b>[Supervisor]</b> Finalizado con éxito.\n⏱️ Tiempo: {duracion}")
        
        return informe_completo_md

    except Exception as e:
        msg = f"Error en Supervisor: {e}"
        logger.exception(msg)
        try:
            import notificador_telegram
            notificador_telegram.enviar_mensaje_telegram(f"❌ <b>[Supervisor]</b> Error crítico:\n<code>{str(e)[:150]}</code>")
        except:
            pass
        procesamiento.actualizar_estado_proceso(ws_status, "ERROR", str(e)[:50], nombre_proceso="supervisor_del_sistema")
        return None

if __name__ == "__main__":
    ejecutar_supervisor()
