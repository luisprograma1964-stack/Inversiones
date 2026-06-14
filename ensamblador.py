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

# Importar los módulos del pipeline
import main
import carga_historica_bridge
import main_tecnico
import captura_noticias
import decisor_con_ia
from TEST.test_ia import descubrir_modelos

def ejecutar_pipeline():
    inicio_global = time.time()
    
    print(f"==================================================")
    print(f"[+] INICIANDO PIPELINE DE INVERSIONES")
    print(f"[*] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"==================================================")
    
    # Pre-flight check: Verificar conexión a Sheets
    sh = auth_google.conectar()
    if not sh:
        print("!!! ERROR FATAL: No se pudo conectar a Google Sheets. Abortando pipeline.")
        sys.exit(1)
        
    ws_log = sh.worksheet(config.WS_LOG_SISTEMA)
    ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)
    
    # Verificación de compatibilidad regional (Locale)
    compatible, locale_name = procesamiento.verificar_locale_compatible(sh)
    if compatible is False:
        print(f"\n[!] ADVERTENCIA DE CONFIGURACIÓN REGIONAL")
        print(f"    La planilla usa el locale '{locale_name}', que probablemente requiere PUNTOS decimales.")
        print(f"    El script está enviando COMAS. Esto causará errores de escala (ej: 3572000).")
        print(f"    Sugerencia: Cambie el país en Archivo -> Configuración de la hoja de cálculo a 'Argentina'.\n")
        procesamiento.registrar_log(ws_log, "WARNING", f"Locale '{locale_name}' detectado. Riesgo de error decimal.")
    elif compatible is True:
        print(f"[*] Configuración regional '{locale_name}' validada (Compatible con comas).")

    procesamiento.registrar_log(ws_log, "INFO", "Iniciando Pipeline Global de Inversiones", "ENSAMBLADOR")
    procesamiento.actualizar_estado_proceso(ws_status, "PROCESANDO", "Pipeline en ejecución...")

    try:
        # ==================================================
        # PASO 0: Health Check de Modelos IA
        # ==================================================
        t0 = time.time()
        print("\n[PASO 0/4] Verificando disponibilidad de modelos Gemini...")
        try:
            modelos_vivos = descubrir_modelos()
            if not modelos_vivos:
                cancelar_pipeline(ws_log, ws_status, "Paso 0 (Health Check IA) falló: No se encontraron modelos operativos.", inicio_global)
                return False
        except Exception as e:
            cancelar_pipeline(ws_log, ws_status, f"Paso 0 (Health Check IA) falló por error técnico: {e}", inicio_global)
            return False
        duracion_p0 = (time.time() - t0) / 60
        print(f"[OK] PASO 0 COMPLETADO EN {duracion_p0:.2f} min")
        
        # ==================================================
        # PASO 1: Variables de Mercado General
        # ==================================================
        t1 = time.time()
        print("\n[PASO 1/4] Descargando Variables de Mercado (Dólar, Inflación, etc)...")
        if not main.ejecutar_sincronizacion():
            cancelar_pipeline(ws_log, ws_status, "Paso 1 (Variables Mercado) falló", inicio_global)
            return False
        duracion_p1 = (time.time() - t1) / 60
        print(f"[OK] PASO 1 COMPLETADO EN {duracion_p1:.2f} min")

        # ==================================================
        # PASO 2: Sincronización Histórica (Precios)
        # ==================================================
        t2 = time.time()
        print("\n[PASO 2/4] Sincronización Histórica de Activos (Bridge)...")
        if not carga_historica_bridge.ejecutar_carga_bridge():
            cancelar_pipeline(ws_log, ws_status, "Paso 2 (Bridge Histórico) falló", inicio_global)
            return False
        duracion_p2 = (time.time() - t2) / 60
        print(f"[OK] PASO 2 COMPLETADO EN {duracion_p2:.2f} min")

        # ==================================================
        # PASO 3: Análisis Técnico Computarizado
        # ==================================================
        t3 = time.time()
        print("\n[PASO 3/4] Calculando Indicadores de Análisis Técnico...")
        if not main_tecnico.ejecutar_analisis_completo():
            cancelar_pipeline(ws_log, ws_status, "Paso 3 (Análisis Técnico) falló", inicio_global)
            return False
        duracion_p3 = (time.time() - t3) / 60
        print(f"[OK] PASO 3 COMPLETADO EN {duracion_p3:.2f} min")

        # ==================================================
        # PASO 3.5: Captura de Noticias y Contexto
        # ==================================================
        t_news = time.time()
        print("\n[PASO 3.5] Capturando noticias y sentimiento de mercado...")
        if not captura_noticias.ejecutar_captura_noticias():
            # No es crítico para detener el flujo, pero registramos el aviso
            print("    [!] Advertencia: La captura de noticias falló. Se continuará sin contexto extra.")
        else:
            print(f"[OK] NOTICIAS CAPTURADAS EN {(time.time() - t_news) / 60:.2f} min")

        # ==================================================
        # PASO 4: Motor de Inteligencia Artificial
        # ==================================================
        t4 = time.time()
        print("\n[PASO 4/4] Ejecutando Motor de IA sobre los resultados...")
        if not decisor_con_ia.ejecutar_decisor():
            cancelar_pipeline(ws_log, ws_status, "Paso 4 (Motor IA) falló", inicio_global)
            return False
        duracion_p4 = (time.time() - t4) / 60
        print(f"[OK] PASO 4 COMPLETADO EN {duracion_p4:.2f} min")

    except Exception as e:
        cancelar_pipeline(ws_log, ws_status, f"Error inesperado en orquestador: {e}", inicio_global)

    # ==================================================
    # FIN EXITOSO
    # ==================================================
    duracion_total = (time.time() - inicio_global) / 60
    tiempo_str = f"{round(duracion_total, 2)} min"
    resumen_final = f"PIPELINE COMPLETADO CON ÉXITO"
    
    print(f"\n==================================================")
    print(f"[OK] {resumen_final} | Tiempo: {tiempo_str}")
    print(f"[*] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"==================================================")
    
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
    print(f"\n==================================================")
    print(f"[ERROR] {msg}")
    if duracion:
        print(f"[*] Tiempo transcurrido: {duracion}")
    print(f"==================================================")
    
    procesamiento.registrar_log(ws_log, "CRITICAL", msg, "ENSAMBLADOR")
    procesamiento.actualizar_estado_proceso(ws_status, "ERROR", msg[:100], tiempo_ejecucion=duracion)
    sys.exit(1)  # Detención física inmediata del sistema

if __name__ == "__main__":
    ejecutar_pipeline()