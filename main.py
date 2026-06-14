"""
Orquestador de captura de datos de mercado.
Lee la configuración de fuentes, descarga los indicadores (como el dólar, inflación, etc.),
los procesa eliminando anomalías y guarda los resultados en VARIABLES_MERCADO.
"""
from datetime import datetime
import config
import time
import auth_google
import procesamiento


def ejecutar_sincronizacion():
    """
    Orquestador principal del proceso de sincronización y carga de fuentes de mercado.
    
    Esta rutina realiza los siguientes pasos:
    1. Se conecta a Google Sheets y obtiene las hojas necesarias (Fuentes, Variables, Log y Estado).
    2. Registra el inicio de la sincronización en el log y el semáforo.
    3. Itera sobre las fuentes activas configuradas, capturando los datos correspondientes.
    4. Agrupa y procesa los datos obtenidos (filtra anomalías, calcula mínimos, máximos, promedios y gaps).
    5. Escribe los resultados procesados en la hoja de VARIABLES_MERCADO.
    6. Finaliza el proceso actualizando los logs y el semáforo indicando el éxito o falla de la operación.
    """
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando proceso {config.ORIGEN_LOG_CARGA}...")
    t_inicio = time.time()
    
    sh = auth_google.conectar()
    if not sh: 
        print("ERROR: No se pudo conectar con Google Sheets.")
        return

    # Instanciar hojas de trabajo
    ws_fuentes = sh.worksheet(config.WS_CONFIG_FUENTES)
    ws_vars = sh.worksheet(config.WS_VARIABLES_MERCADO)
    ws_log = sh.worksheet(config.WS_LOG_SISTEMA)
    ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)

    # Mantenimiento preventivo de logs antes de iniciar la jornada
    procesamiento.limpiar_log_sistema(sh)

    # 1. Logs de Inicio
    procesamiento.registrar_log(ws_log, "INFO", "Iniciando sincronización periódica de mercado")
    procesamiento.actualizar_estado_proceso(ws_status, "PROCESANDO", "Iniciando captura de datos...")

    try:
        # 2. Leer configuración de fuentes
        fuentes = ws_fuentes.get_all_records()
        resultados_agrupados = {}

        # 3. Captura de datos
        for f in fuentes:
            if str(f.get('ESTADO', '')).strip().upper() == 'ACTIVO':
                nombre = f.get('DATO')
                print(f"Capturando: {nombre}...", end="\r")
                valor, msg = procesamiento.capturar_dato(f.get('FUENTE / URL'), f.get('SELECTOR / CAMPO'))
                
                if valor:
                    if nombre not in resultados_agrupados:
                        resultados_agrupados[nombre] = []
                    resultados_agrupados[nombre].append(valor)
                else:
                    procesamiento.registrar_log(ws_log, "ERROR", f"Variable: {nombre} | {msg}")

        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Procesando y guardando datos...")

        # 4. Procesamiento y escritura en VARIABLES_MERCADO
        ahora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        datos_actuales = ws_vars.get_all_records()

        for nombre, valores in resultados_agrupados.items():
            valores_limpios = procesamiento.filtrar_anomalias(nombre, valores, ws_log)
            
            if not valores_limpios:
                procesamiento.registrar_log(ws_log, "CRITICAL", f"Sin datos consistentes para {nombre}.")
                continue

            v_min, v_max = min(valores_limpios), max(valores_limpios)
            v_prom = round(sum(valores_limpios) / len(valores_limpios), 2)
            gap = f"{round(((v_max - v_min) / v_min) * 100, 2)}%" if v_min > 0 else "0%"
            
            nueva_fila = [nombre, v_prom, v_min, v_max, gap, len(valores_limpios), ahora_str]
            
            encontrado = False
            for i, fila_dict in enumerate(datos_actuales, start=2):
                if str(fila_dict.get('DATO')).strip() == str(nombre).strip():
                    ws_vars.update(values=[nueva_fila], range_name=f"A{i}:G{i}")
                    encontrado = True
                    break
            
            if not encontrado:
                ws_vars.append_row(nueva_fila)

        # 5. Finalización y Logs de éxito
        resumen = f"OK: {len(resultados_agrupados)} variables procesadas."
        procesamiento.registrar_log(ws_log, "INFO", resumen)
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        procesamiento.actualizar_estado_proceso(ws_status, "OK", resumen, tiempo_ejecucion=duracion)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] >>> Sincronización Finalizada.")
        return True
        
    except Exception as e:
        msg_error = f"Error crítico en proceso general: {e}"
        print(msg_error)
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        procesamiento.registrar_log(ws_log, "CRITICAL", msg_error, config.ORIGEN_LOG_MAIN)
        procesamiento.actualizar_estado_proceso(ws_status, "ERROR", "Falla crítica global", tiempo_ejecucion=duracion)
        return False

if __name__ == "__main__":
    ejecutar_sincronizacion()