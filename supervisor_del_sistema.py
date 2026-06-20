"""
Supervisor del Sistema de Inversiones.
Analiza la calidad del proceso, audita el descarte de noticias y sugiere mejoras 
en los diccionarios de datos (sinónimos, filtros y nuevos activos).
"""
import json
import os
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


def ejecutar_supervisor():
    print("[*] Iniciando Supervisor del Sistema...")
    logger.info("" + "X"*60)
    logger.info(f"SUPERVISOR Y MEJORADOR DEL SISTEMA | {datetime.now().strftime('%H:%M:%S')}")
    logger.info("X"*60)
    t_inicio = time.time()
    
    try:
        sh, client = inicializar_motor_ia()
    except Exception as e:
        logger.critical(f"ERROR CRÍTICO SUPERVISOR: {e}")
        return None

    ws_log = sh.worksheet(config.WS_LOG_SISTEMA)
    ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)
    procesamiento.registrar_log(ws_log, "INFO", "Iniciando Supervisor del Sistema")
    procesamiento.actualizar_estado_proceso(ws_status, "PROCESANDO", "Auditando calidad del sistema...")

    try:
        # 1. RECOLECCIÓN DE DATOS PARA EL CONTEXTO GLOBAL
        def get_df(ws_name):
            try: 
                df = pd.DataFrame(sh.worksheet(ws_name).get_all_records())
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
        df_sug_raw = get_df(config.WS_SUGERENCIAS_SINONIMOS).tail(20)
        
        # 1.1 Filtrar sugerencias de sinónimos que YA existen en la tabla real
        if not df_sug_raw.empty and not df_sinonimos_actuales.empty:
            vistos = set(df_sinonimos_actuales['TERMINO'].astype(str).str.upper())
            df_sugerencias = df_sug_raw[~df_sug_raw['TERMINO_SUGERIDO'].astype(str).str.upper().isin(vistos)].copy()
        else:
            df_sugerencias = df_sug_raw

        # 1.1 Resumen de cobertura de noticias para detectar "silencios"
        tickers_con_noticias = df_noticias['TICKER_ID'].unique().tolist() if (not df_noticias.empty and 'TICKER_ID' in df_noticias.columns) else []

        # 2. ARMADO DEL PAYLOAD PARA LA IA ESTRATÉGICA
        ahora_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        payload = {
            "estado_actual_matriz": df_matriz.to_dict('records'),
            "datos_tecnicos_vigentes": df_tecnico[['TICKER_ID', 'TREND', 'RSI', 'FIBO_RET', 'FECHA_PRECIO_ACTUAL', 'CCL_IMPLICITO']].to_dict('records') if not df_tecnico.empty and 'CCL_IMPLICITO' in df_tecnico.columns else (df_tecnico[['TICKER_ID', 'TREND', 'RSI', 'FIBO_RET', 'FECHA_PRECIO_ACTUAL']].to_dict('records') if not df_tecnico.empty else []),
            "maestro_filtros": df_maestro[['TICKER_ID', 'FILTRO_NOTICIAS', 'ESTADO']].to_dict('records') if not df_maestro.empty and 'TICKER_ID' in df_maestro.columns else [],
            "tickers_con_noticias_recientes": tickers_con_noticias,
            "auditoria_noticias": {
                "ultimos_descartes": df_descartes[['TITULAR', 'MOTIVO_DESCARTE', 'SUBMODULO']].to_dict('records') if not df_descartes.empty and 'TITULAR' in df_descartes.columns else [],
                "sugerencias_pendientes_sinonimos": df_sugerencias.to_dict('records')
            }
        }

        # 3. PROMPT ESTRATÉGICO
        prompt_estrategico = f"""
        Actúas como un Auditor Senior de Sistemas Financieros (QA/Optimizer). Tu misión es mejorar la precisión de los datos.
        
        CONTEXTO DEL SISTEMA:
        {json.dumps(payload, indent=2, ensure_ascii=False)}
        
        TAREAS OBLIGATORIAS:
        1. MEJORADOR DE DATOS (SINÓNIMOS Y TICKERS): 
           - SINÓNIMOS: Revisa 'sugerencias_pendientes'. Dame la fila EXACTA (TERMINO;TICKER_ASOCIADO) para pegar en CONFIG_SINONIMOS.
           - NUEVOS TICKERS: Si el mercado habla de algo que no seguimos, dame la fila EXACTA para MAESTRO_ACTIVOS: TICKER_ID;Nombre_Largo;Filtro_Noticias;{ahora_iso};250;GF_BRIDGE;ACTIVO.
        2. ACTIVACIÓN DE ACTIVOS INACTIVOS: 
           - Revisa 'tickers_con_noticias_recientes' y cruza con 'maestro_filtros'. Si un activo está en estado 'INACTIVO' en el maestro pero tiene flujo de noticias recientes, genera una alerta para el usuario:
             Acción: 'Luis, el activo X tiene noticias relevantes pero está INACTIVO en tu maestro. Considera activarlo para que el pipeline técnico calcule sus indicadores y la IA tome decisiones'.
        3. COMPARATIVA E INTEGRIDAD (AUDITORÍA): 
           - Detecta si el Paso 4 ignoró noticias.
           - **AVISO DE DISCREPANCIA**: Compara las fechas en 'datos_tecnicos_vigentes' con las fechas en 'noticias_aprobadas_recientes'. Si el técnico es antiguo pero hay noticias nuevas, acción: 'Luis, el análisis de X está desincronizado: precio de hace 24hs vs noticias de hace 1h. Re-ejecuta el Bridge'.
        4. AUDITORÍA DE BRECHA CAMBIARIA (CCL):
           - Analiza el campo 'CCL_IMPLICITO' en 'datos_tecnicos_vigentes'. 
           - Calcula la brecha (tipo de cambio implícito) promedio del mercado. Si algún activo se desvía más de un 2.5% del promedio (presentando un CCL significativamente alto/caro o bajo/barato relativo), genera una alerta:
             Acción: 'Luis, el CEDEAR de X cotiza localmente con un sobreprecio cambiario de Y% respecto a la media de mercado. Se sugiere evitar compras locales temporales'.
        5. ANÁLISIS DE CONTRADICCIÓN TÉCNICA: 
           - Identifica discrepancias severas entre el veredicto de la IA (SENTIMIENTO/SCORE en 'estado_actual_matriz') y la realidad técnica (TREND/RSI en 'datos_tecnicos_vigentes').
           - Alerta si el Score es alto (>7) en tendencia bajista o bajo (<4) en tendencia alcista sin noticias de peso que lo justifiquen.
        5. REPORTE DE BLOQUEOS POR ESCALA (15x):
           - Revisa en 'datos_tecnicos_vigentes' si existen activos con RSI = -1 o FIBO_RET que contenga 'Error (Escala)'.
           - Acción: 'Luis, el activo X fue bloqueado por seguridad (Escala 15x). Verifica si hay un error de carga o un split no procesado'.
        6. ALERTAS DE SILENCIO: Activos que suben/bajan fuerte pero nuestro radar de noticias no sabe por qué. Acción: 'Luis, busca manualmente en Twitter o Google qué pasó con X'.
        7. OPTIMIZACIÓN DE PROMPTS: 
           - Si el fallo es de criterio financiero: Sugiere cambio en 'Instrucciones_Fijas'.
           - Si el fallo es de descarte de noticias: Sugiere cambio en 'Prompt_Triage_Noticias'.

        ESTRUCTURA DEL INFORME:
        - 🧠 MEJORA DE DATOS (Filtros de búsqueda, nuevos Tickers y Sinónimos)
        - 📊 AUDITORÍA DE NOTICIAS VS DECISIÓN (Calidad del Triage)
        - 📉 CONTRADICCIONES TÉCNICAS (Veredicto IA vs Indicadores)
        - 📏 ERRORES DE ESCALA (Activos bloqueados por seguridad 15x)
        - 🕒 SINCRONIZACIÓN DE DATOS (Avisos de discrepancia de fechas)
        - ⚠️ ALERTAS Y CALIDAD (Anomalías detectadas y ajustes de IA)
        - ⚙️ OPTIMIZACIÓN DE INSTRUCCIONES IA (Sugerencias para 'Instrucciones_Fijas')
        """

        # 4. CONSULTA A GEMINI (Usamos Pro si está disponible para máxima calidad estratégica)
        modelos = ia_utils.obtener_modelos_activos()
        modelo_estrategico = "models/gemini-1.5-pro" if "models/gemini-1.5-pro" in modelos else modelos[0]
        
        logger.info(f"Generando informe estratégico con {modelo_estrategico}...")
        response = client.models.generate_content(
            model=modelo_estrategico,
            contents=prompt_estrategico
        )

        informe = response.text

        # 5. GUARDAR REPORTE EN ARCHIVO MD
        os.makedirs(config.DIR_ESTRATEGIA, exist_ok=True)
        filename = f"Supervision_Sistema_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        path_md = os.path.join(config.DIR_ESTRATEGIA, filename)
        with open(path_md, "w", encoding="utf-8") as f:
            f.write(informe)
        
        # 6. SALIDA POR TERMINAL Y REGISTRO
        print(f"\n[OK] Informe de supervisión guardado en: {path_md}\n")
        print("="*60)
        print("INFORME DE SUPERVISIÓN Y MEJORA ESTRATÉGICA:")
        print(informe)
        print("="*60)
        
        logger.info("="*60)
        logger.info("INFORME DE SUPERVISIÓN Y MEJORA")
        logger.info(f"Reporte guardado en: {path_md}")
        logger.info(informe)
        logger.info("="*60)

        # Guardar en log histórico
        procesamiento.registrar_log(ws_log, "INFO", "Informe de supervisión generado exitosamente", "SUPERVISOR")
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        procesamiento.actualizar_estado_proceso(ws_status, "OK", "Informe generado", tiempo_ejecucion=duracion)
        print(f"[OK] Supervisor finalizado exitosamente en {duracion}.\n")
        
        return informe

    except Exception as e:
        msg = f"Error en Supervisor: {e}"
        logger.exception(msg)
        procesamiento.actualizar_estado_proceso(ws_status, "ERROR", str(e)[:50])
        return None

if __name__ == "__main__":
    ejecutar_supervisor()
