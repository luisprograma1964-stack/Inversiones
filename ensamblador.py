"""
Orquestador Principal (Ensamblador).
Ejecuta todos los módulos del sistema en orden secuencial.
Si un módulo falla de forma crítica, detiene la ejecución en cadena para
proteger la integridad de los datos, cumpliendo el principio Fail-Fast.
"""
from datetime import datetime
import sys
import time
import argparse

# Importar herramientas propias
import auth_google
import procesamiento
import config
import logging_config

logger = logging_config.get_logger(__name__)

# Importar los módulos del pipeline
import main
import carga_historica_bridge
import main_tecnico
import captura_noticias
import valorador_cartera
import decisor_con_ia
import pre_mantenimiento
from TEST.test_ia import descubrir_modelos

def ejecutar_pipeline():
    inicio_global = time.time()
    
    logger.info("==================================================")
    logger.info("[+] INICIANDO PIPELINE DE INVERSIONES")
    logger.info(f"[*] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("==================================================")
    
    # Pre-flight check: Verificar conexión a Sheets
    sh = auth_google.conectar()
    if not sh:
        logger.critical("!!! ERROR FATAL: No se pudo conectar a Google Sheets. Abortando pipeline.")
        return False
        
    ws_log = sh.worksheet(config.WS_LOG_SISTEMA)
    ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)
    
    # Verificación de compatibilidad regional (Locale)
    compatible, locale_name = procesamiento.verificar_locale_compatible(sh)
    if compatible is False:
        logger.warning(f"\n[!] ADVERTENCIA DE CONFIGURACIÓN REGIONAL")
        logger.warning(f"    La planilla usa el locale '{locale_name}', que probablemente requiere PUNTOS decimales.")
        logger.warning(f"    El script está enviando COMAS. Esto causará errores de escala (ej: 3572000).")
        logger.warning(f"    Sugerencia: Cambie el país en Archivo -> Configuración de la hoja de cálculo a 'Argentina'.\n")
        procesamiento.registrar_log(ws_log, "WARNING", f"Locale '{locale_name}' detectado. Riesgo de error decimal.")
    elif compatible is True:
        logger.info(f"[*] Configuración regional '{locale_name}' validada (Compatible con comas).")

    procesamiento.registrar_log(ws_log, "INFO", "Iniciando Pipeline Global de Inversiones", "ENSAMBLADOR")
    procesamiento.actualizar_estado_proceso(ws_status, "PROCESANDO", "Pipeline en ejecución...")

    try:
        # ==================================================
        # PASO 0: Health Check de Modelos IA
        # ==================================================
        t0 = time.time()
        logger.info("\n[PASO 0/4] Verificando disponibilidad de modelos Gemini...")
        try:
            modelos_vivos = descubrir_modelos()
            if not modelos_vivos:
                cancelar_pipeline(ws_log, ws_status, "Paso 0 (Health Check IA) falló: No se encontraron modelos operativos.", inicio_global)
                return False
        except Exception as e:
            cancelar_pipeline(ws_log, ws_status, f"Paso 0 (Health Check IA) falló por error técnico: {e}", inicio_global)
            return False
        duracion_p0 = (time.time() - t0) / 60
        logger.info(f"[OK] PASO 0 COMPLETADO EN {duracion_p0:.2f} min")
        # ==================================================
        # PASO 0.5: Mantenimiento Previo (Sinónimos, etc.)
        # ==================================================
        t05 = time.time()
        logger.info("\n[PASO 0.5] Ejecutando rutinas de mantenimiento previo...")
        if not pre_mantenimiento.ejecutar_mantenimiento_previo():
            logger.warning("[!] El mantenimiento previo reportó un error, pero el pipeline continuará.")
        duracion_p05 = (time.time() - t05) / 60
        logger.info(f"[OK] PASO 0.5 COMPLETADO EN {duracion_p05:.2f} min")

        # ==================================================
        # PASO 1: Variables de Mercado General
        # ==================================================
        t1 = time.time()
        logger.info("\n[PASO 1/4] Descargando Variables de Mercado (Dólar, Inflación, etc)...")
        if not main.ejecutar_sincronizacion():
            cancelar_pipeline(ws_log, ws_status, "Paso 1 (Variables Mercado) falló", inicio_global)
            return False
        duracion_p1 = (time.time() - t1) / 60
        logger.info(f"[OK] PASO 1 COMPLETADO EN {duracion_p1:.2f} min")

        # ==================================================
        # PASO 2: Sincronización Histórica (Precios)
        # ==================================================
        t2 = time.time()
        logger.info("\n[PASO 2/4] Sincronización Histórica de Activos (Bridge)...")
        if not carga_historica_bridge.ejecutar_carga_bridge():
            cancelar_pipeline(ws_log, ws_status, "Paso 2 (Bridge Histórico) falló", inicio_global)
            return False
        duracion_p2 = (time.time() - t2) / 60
        logger.info(f"[OK] PASO 2 COMPLETADO EN {duracion_p2:.2f} min")

        # ==================================================
        # PASO 3: Análisis Técnico Computarizado
        # ==================================================
        t3 = time.time()
        logger.info("\n[PASO 3/4] Calculando Indicadores de Análisis Técnico...")
        if not main_tecnico.ejecutar_analisis_completo():
            cancelar_pipeline(ws_log, ws_status, "Paso 3 (Análisis Técnico) falló", inicio_global)
            return False
        duracion_p3 = (time.time() - t3) / 60
        logger.info(f"[OK] PASO 3 COMPLETADO EN {duracion_p3:.2f} min")

        # ==================================================
        # PASO 3.5: Captura de Noticias y Contexto
        # ==================================================
        t_news = time.time()
        logger.info("\n[PASO 3.5] Capturando noticias y sentimiento de mercado...")
        if not captura_noticias.ejecutar_captura_noticias():
            cancelar_pipeline(ws_log, ws_status, "Paso 3.5 (Captura de Noticias) falló", inicio_global)
            return False
        else:
            logger.info(f"[OK] NOTICIAS CAPTURADAS EN {(time.time() - t_news) / 60:.2f} min")

        # ==================================================
        # PASO 3.8: Valuación de Cartera y Rentabilidad
        # ==================================================
        t_val = time.time()
        logger.info("\n[PASO 3.8] Calculando tenencias y rentabilidad de cartera...")
        if not valorador_cartera.ejecutar_valoracion():
            cancelar_pipeline(ws_log, ws_status, "Paso 3.8 (Valuación de Cartera) falló", inicio_global)
            return False
        else:
            logger.info(f"[OK] CARTERA VALORIZADA EN {(time.time() - t_val) / 60:.2f} min")

        # ==================================================
        # PASO 4: Motor de Inteligencia Artificial
        # ==================================================
        t4 = time.time()
        logger.info("\n[PASO 4/4] Ejecutando Motor de IA sobre los resultados...")
        if not decisor_con_ia.ejecutar_decisor():
            cancelar_pipeline(ws_log, ws_status, "Paso 4 (Motor IA) falló", inicio_global)
            return False
        duracion_p4 = (time.time() - t4) / 60
        logger.info(f"[OK] PASO 4 COMPLETADO EN {duracion_p4:.2f} min")

    except Exception as e:
        return cancelar_pipeline(ws_log, ws_status, f"Error inesperado en orquestador: {e}", inicio_global)

    # ==================================================
    # FIN EXITOSO
    # ==================================================
    duracion_total = (time.time() - inicio_global) / 60
    tiempo_str = f"{round(duracion_total, 2)} min"
    resumen_final = f"PIPELINE COMPLETADO CON ÉXITO"
    
    logger.info(f"\n==================================================")
    logger.info(f"[OK] {resumen_final} | Tiempo: {tiempo_str}")
    logger.info(f"[*] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"==================================================")
    
    procesamiento.registrar_log(ws_log, "INFO", resumen_final, "ENSAMBLADOR")
    # Ahora pasamos el tiempo total a la tabla de estados
    procesamiento.actualizar_estado_proceso(ws_status, "OK", resumen_final, tiempo_ejecucion=tiempo_str)
    return True

def cancelar_pipeline(ws_log, ws_status, razon, t_inicio=None):
    """Rutina de parada de emergencia"""
    duracion = ""
    if t_inicio:
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        
    msg = f"PIPELINE CANCELADO EN CADENA. Motivo: {razon}"
    logger.critical(f"\n==================================================")
    logger.critical(f"[ERROR] {msg}")
    if duracion:
        logger.critical(f"[*] Tiempo transcurrido: {duracion}")
    logger.critical(f"==================================================")
    
    procesamiento.registrar_log(ws_log, "CRITICAL", msg, "ENSAMBLADOR")
    procesamiento.actualizar_estado_proceso(ws_status, "ERROR", msg[:100], tiempo_ejecucion=duracion)
    return False

if __name__ == "__main__":
    sys.exit(0 if ejecutar_pipeline() else 1)
