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

    api_key_path = Path(config.API_KEY_FILE)
    if not api_key_path.exists():
        raise FileNotFoundError(f"Archivo de API KEY no encontrado: {config.API_KEY_FILE}")

    with open(api_key_path, 'r', encoding='utf-8') as f:
        key = f.read().strip()

    if not key:
        raise ValueError(f"El archivo de API KEY está vacío: {config.API_KEY_FILE}")

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
    notificador_telegram.enviar_mensaje_telegram("🚀 <b>[Supervisor]</b> Iniciando Análisis y Auditoría del Sistema...")
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
        df_ia_usuarios = get_df(config.WS_CONFIG_IA_USUARIO)
        df_sinonimos_actuales = get_df(config.WS_CONFIG_SINONIMOS)
        df_mercado = get_df(config.WS_VARIABLES_MERCADO)
        df_descartes = get_df(config.WS_NOTICIAS_DESCARTADAS).tail(20) # Últimos descartes
        df_sug_raw = get_df(config.WS_SUGERENCIAS_SINONIMOS)
        df_valoracion = get_df("VALORACION_PORTAFOLIO")
        df_caja = get_df(config.WS_CAJA_LIQUIDEZ)
        
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
        tickers_con_noticias = df_noticias['TICKER_ID'].unique().tolist() if (not df_noticias.empty and 'TICKER_ID' in df_noticias.columns) else []

        # 1.4 Cálculo de Equity Consolidado (ARS/USD) por Propietario
        dolar_mep = 1.0
        if not df_mercado.empty:
            mask_mep = df_mercado['DATO'].astype(str).str.contains('MEP', case=False, na=False)
            if any(mask_mep):
                try:
                    val_mep = str(df_mercado[mask_mep]['VALOR_PROM'].iloc[0]).replace(',', '.')
                    dolar_mep = float(val_mep)
                except Exception:
                    dolar_mep = 1.0
        
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
           - Genera órdenes concretas y directas de rebalanceo segmentadas por propietario (ej: para Luis Agresivo vs Luis Moderado): 'Luis, compra X' o 'Luis, vende Y' para alinear las tenencias reales al target de su perfil de riesgo.
           - CONSOLIDACIÓN MULTIMONEDA: Usa 'variables_mercado' (Dólar MEP/Blue) para calcular el poder de compra. Si sugieres comprar en USD usando ARS, detalla la conversión estimada.
        2. RADAR DE OPORTUNIDADES (EXPANSIÓN): 
           - Identifica activos que el usuario no tiene actualmente pero que muestran alta convicción en 'estado_actual_matriz' (Score >= 8). Acción sugerida: 'Luis, inicia posición en Z'.
        3. MEJORADOR DE DATOS (SINÓNIMOS Y TICKERS): 
           - SINÓNIMOS: Si hay 'sugerencias_pendientes_sinonimos' > 0, genera una alerta indicando: 'Luis, tienes X sugerencias de sinónimos pendientes. Por favor revisa la hoja SUGERENCIAS_SINONIMOS y cambia su estado a APROBADO o RECHAZADO.'
           - NUEVOS TICKERS: Si el mercado habla de algo que no seguimos, dame la fila EXACTA para MAESTRO_ACTIVOS: TICKER_ID;Nombre_Largo;Filtro_Noticias;{ahora_iso};250;GF_BRIDGE;ACTIVO.
           - ACTUALIZACIÓN COMAFI: Si 'cantidad_nuevos' en 'auditoria_cedears_comafi' es > 0, alerta: 'Luis, se detectaron X nuevos CEDEARs en Comafi. Por favor corre `mantenimiento_cedears_comafi.py` para agregarlos al Maestro.'
           - OPTIMIZACIÓN DE BÚSQUEDA: Si un activo importante no trae noticias en absoluto, sugiere la acción: 'Luis, cambia el filtro de X por Y en el Maestro' sugiriendo un término de búsqueda más adecuado.
        4. ACTIVACIÓN DE ACTIVOS INACTIVOS: 
           - Revisa 'tickers_con_noticias_recientes' y cruza con 'maestro_filtros'. Si un activo está en estado 'INACTIVO' en el maestro pero tiene flujo de noticias recientes, genera una alerta para el usuario:
             Acción: 'Luis, el activo X tiene noticias relevantes pero está INACTIVO en tu maestro. Considera activarlo para que el pipeline técnico calcule sus indicadores y la IA tome decisiones'.
         5. COMPARATIVA E INTEGRIDAD (AUDITORÍA): 
            - Detecta si el Paso 4 ignoró noticias.
            - **AVISO DE DISCREPANCIA**: Compara las fechas en 'datos_tecnicos_vigentes' con las fechas en 'noticias_aprobadas_recientes'. Si el técnico tiene un rezago mayor a 48 horas, genera la alerta correspondiente. Nota: Una diferencia de hasta 24 horas (ej. precios del día anterior vs noticias de hoy) es perfectamente normal y saludable si el mercado aún está operando y la rueda actual no ha cerrado; NO emitas alertas de discrepancia en este caso.
         6. AUDITORÍA DE BRECHA CAMBIARIA (CCL):
           - Analiza el campo 'CCL_IMPLICITO' en 'datos_tecnicos_vigentes'. 
           - Calcula la brecha (tipo de cambio implícito) promedio del mercado. Si algún activo se desvía más de un 2.5% del promedio (presentando un CCL significativamente alto/caro o bajo/barato relativo), genera una alerta:
             Acción: 'Luis, el CEDEAR de X cotiza localmente con un sobreprecio cambiario de Y% respecto a la media de mercado. Se sugiere evitar compras locales temporales'.
        7. ANÁLISIS DE CONTRADICCIÓN TÉCNICA: 
           - Identifica discrepancias severas entre el veredicto de la IA (SENTIMIENTO/SCORE en 'estado_actual_matriz') y la realidad técnica (TREND/RSI en 'datos_tecnicos_vigentes').
           - Alerta si el Score es alto (>7) en tendencia bajista o bajo (<4) en tendencia alcista sin noticias de peso que lo justifiquen.
        8. REPORTE DE BLOQUEOS POR ESCALA (15x):
           - Revisa en 'datos_tecnicos_vigentes' si existen activos con RSI = -1 o FIBO_RET que contenga 'Error (Escala)'.
           - Acción: 'Luis, el activo X fue bloqueado por seguridad (Escala 15x). Verifica si hay un error de carga o un split no procesado'.
        9. ALERTAS DE SILENCIO: Activos que suben/bajan fuerte pero nuestro radar de noticias no sabe por qué. Acción: 'Luis, busca manualmente en Twitter o Google qué pasó con X'.
        10. OPTIMIZACIÓN DE PROMPTS: 
            - Si el fallo es de criterio financiero: Sugiere un cambio para 'Instrucciones_Fijas'. Debes especificar de forma obligatoria la sección exacta donde se debe acoplar el cambio (por ejemplo, '[SECCIÓN 3: LÍMITES TÉCNICOS Y GUARDRAILS DE SCORE]').
            - Si el fallo es de descarte de noticias: Sugiere un cambio para 'Prompt_Triage_Noticias'. Debes especificar de forma obligatoria la sección exacta donde se debe acoplar el cambio (por ejemplo, '[SECCIÓN 2: CRITERIOS DE APROBACIÓN Y FILTRO GENERAL]').
            
            Las secciones lógicas estructuradas en el sistema para 'Instrucciones_Fijas' son:
            - [SECCIÓN 1: ROL, MISIÓN Y HORIZONTE]
            - [SECCIÓN 2: CONFLUENCIA TÉCNICA Y DE CONTEXTO]
            - [SECCIÓN 3: LÍMITES TÉCNICOS Y GUARDRAILS DE SCORE]
            - [SECCIÓN 4: REGLAS DE OPERATORIA LOCAL Y BRECHA CAMBIARIA]
            - [SECCIÓN 5: FORMATO DE SALIDA OBLIGATORIO]

            Las secciones lógicas estructuradas en el sistema para 'Prompt_Triage_Noticias' son:
            - [SECCIÓN 1: MISIÓN Y FORMATO JSON]
            - [SECCIÓN 2: CRITERIOS DE APROBACIÓN Y FILTRO GENERAL]
            - [SECCIÓN 3: TRATAMIENTO DE EMISORES Y CAMBIOS CORPORATIVOS]
            - [SECCIÓN 4: REGLAS ADICIONALES]
 
        ESTRUCTURA DEL INFORME:
        - ESTRATEGIA DE CARTERA (Rebalanceo de Cartera, órdenes de compra/venta y cotizaciones)
        - MEJORA DE DATOS (Filtros de búsqueda, nuevos Tickers y Sinónimos)
        - AUDITORIA DE NOTICIAS VS DECISION (Calidad del Triage)
        - CONTRADICCIONES TECNICAS (Veredicto IA vs Indicadores)
        - ERRORES DE ESCALA (Activos bloqueados por seguridad 15x)
        - SINCRONIZACION DE DATOS (Avisos de discrepancia de fechas)
        - ALERTAS Y CALIDAD (Anomalías detectadas y ajustes de IA)
        - OPTIMIZACION DE INSTRUCCIONES IA (Sugerencias estructuradas detallando el prompt, la sección sugerida exacta y la regla a insertar)

        REGLA DE FORMATO CRÍTICA: Comienza directamente con el encabezado de nivel 2 '## ESTRATEGIA DE CARTERA'. No incluyas ningún título de nivel 1 (#) ni preámbulos introductorios, ya que tu informe será concatenado a un encabezado estructurado por el sistema. No uses emojis ni caracteres gráficos en los encabezados ni en el contenido del informe.
        """

        # 4. CONSULTA A GEMINI (Usamos Pro si está disponible para máxima calidad estratégica, con rotación en caso de error)
        modelos_activos = ia_utils.obtener_modelos_activos()
        candidatos = ["gemini-1.5-pro", "gemini-2.0-flash", "gemini-1.5-flash"]
        for m in modelos_activos:
            if m not in candidatos:
                candidatos.append(m)

        informe = None
        ultimo_error = None
        modelo_exitoso = None

        for modelo_candidato in candidatos:
            logger.info(f"Generando informe estratégico con {modelo_candidato}...")
            try:
                response = client.models.generate_content(
                    model=modelo_candidato,
                    contents=prompt_estrategico
                )
                if response and response.text:
                    informe = response.text
                    modelo_exitoso = modelo_candidato
                    logger.info(f"¡Informe estratégico generado con éxito usando {modelo_candidato}!")
                    break
            except Exception as e:
                ultimo_error = e
                logger.warning(f"Error generando informe con {modelo_candidato}: {e}. Intentando fallback...")
                time.sleep(1) # Pequeña pausa antes del reintento

        if not informe:
            raise RuntimeError(f"Todos los modelos de IA fallaron. Último error: {ultimo_error}")

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
        informe_completo = punto_1_audit + informe

        # 5. GUARDAR REPORTE EN GOOGLE SHEETS
        try:
            ws_supervisor = sh.worksheet(config.WS_REPORTE_SUPERVISOR)
            ahora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            import re
            
            alertas = ""
            match_alertas = re.search(r'## ALERTAS Y CALIDAD(.*?)##', informe_completo, re.DOTALL | re.IGNORECASE)
            if match_alertas:
                alertas = match_alertas.group(1).strip()[:800]
                
            resumen = ""
            match_est = re.search(r'## ESTRATEGIA DE CARTERA(.*?)##', informe_completo, re.DOTALL | re.IGNORECASE)
            if match_est:
                resumen = match_est.group(1).strip()[:800]
                
            row = [ahora_str, resumen, alertas, "N/A", informe_completo]
            ws_supervisor.append_row(row)
            path_md = "Google Sheets: REPORTE_SUPERVISOR"
            logger.info("[+] Reporte guardado en hoja REPORTE_SUPERVISOR")
        except Exception as esh:
            path_md = "ERROR AL GUARDAR EN SHEETS"
            logger.error(f"[-] Error guardando reporte en Sheets: {esh}")
            

        # 6. SALIDA POR TERMINAL Y REGISTRO
        try:
            print(f"\n[OK] Informe de supervisión guardado en: {path_md}\n")
            print("="*60)
            print("INFORME DE SUPERVISIÓN Y MEJORA ESTRATÉGICA:")
            print(informe_completo)
            print("="*60)
        except UnicodeEncodeError:
            try:
                sys_stdout_encoding = sys.stdout.encoding or 'ascii'
                safe_informe = informe_completo.encode(sys_stdout_encoding, errors='replace').decode(sys_stdout_encoding)
                print(f"\n[OK] Informe de supervision guardado en: {path_md}\n")
                print("="*60)
                print("INFORME DE SUPERVISION Y MEJORA ESTRATEGICA (Safe Encoding):")
                print(safe_informe)
                print("="*60)
            except Exception:
                pass
        
        logger.info("="*60)
        logger.info("INFORME DE SUPERVISIÓN Y MEJORA")
        logger.info(f"Reporte guardado en: {path_md}")
        logger.info(informe_completo)
        logger.info("="*60)
 
        # Guardar en log histórico
        procesamiento.registrar_log(ws_log, "INFO", f"Informe de supervisión generado exitosamente (modelo: {modelo_exitoso})", "SUPERVISOR")
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        procesamiento.actualizar_estado_proceso(ws_status, "OK", f"Informe generado ({modelo_exitoso})", nombre_proceso="supervisor_del_sistema", tiempo_ejecucion=duracion)
        print(f"[OK] Supervisor finalizado exitosamente en {duracion}.\n")
        import notificador_telegram
        notificador_telegram.enviar_mensaje_telegram(f"✅ <b>[Supervisor]</b> Finalizado con éxito.\n⏱️ Tiempo: {duracion}")
        
        return informe_completo

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
