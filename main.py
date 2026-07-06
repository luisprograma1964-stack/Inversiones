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
import logging_config

logger = logging_config.get_logger(__name__)


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
    logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando proceso {config.ORIGEN_LOG_CARGA}...")
    t_inicio = time.time()
    
    sh = auth_google.conectar()
    if not sh:
        logger.error("ERROR: No se pudo conectar con Google Sheets.")
        return False

    try:
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

        # 2. Leer configuración de fuentes
        fuentes = ws_fuentes.get_all_records()
        resultados_agrupados = {}

        # 3. Captura de datos
        for f in fuentes:
            if str(f.get('ESTADO', '')).strip().upper() == 'ACTIVO':
                nombre = f.get('DATO')
                logger.info(f"Capturando: {nombre}...")
                valor, msg = procesamiento.capturar_dato(f.get('FUENTE / URL'), f.get('SELECTOR / CAMPO'))
                
                if valor:
                    if nombre not in resultados_agrupados:
                        resultados_agrupados[nombre] = []
                    resultados_agrupados[nombre].append(valor)
                else:
                    procesamiento.registrar_log(ws_log, "ERROR", f"Variable: {nombre} | {msg}")

        logger.info(f"\n[{datetime.now().strftime('%H:%M:%S')}] Procesando y guardando datos...")

        # 4. Procesamiento y escritura en VARIABLES_MERCADO
        import requests
        ahora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        datos_actuales = ws_vars.get_all_values()
        
        # Mapeamos los nombres actuales en la hoja para saber en qué fila sobreescribir
        headers_vars = [h.strip().upper() for h in datos_actuales[0]] if datos_actuales else []
        filas_existentes = {str(row[0]).strip().upper(): idx for idx, row in enumerate(datos_actuales, start=1) if row}

        # Consolidar los resultados procesados
        variables_consolidadas = {}

        # 4.1 Obtener Dólar MEP, Blue y Cripto con DolarApi de forma nativa e infalible (Compra y Venta)
        endpoints_dolar = {
            "Dólar MEP": "https://dolarapi.com/v1/dolares/mep",
            "Dólar Blue": "https://dolarapi.com/v1/dolares/blue",
            "Dólar Cripto": "https://dolarapi.com/v1/dolares/cripto"
        }

        for nombre_dolar, url in endpoints_dolar.items():
            logger.info(f"Consultando cotización oficial en DolarApi para: {nombre_dolar}...")
            try:
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    compra = float(data.get("compra", 0.0))
                    venta = float(data.get("venta", 0.0))
                    if compra > 0 and venta > 0:
                        v_prom = round((compra + venta) / 2.0, 2)
                        variables_consolidadas[nombre_dolar] = [nombre_dolar, compra, venta, v_prom, compra, venta, "0.0%", 1, ahora_str]
                        logger.info(f"  [OK] {nombre_dolar} -> Compra: {compra} / Venta: {venta}")
                        continue
            except Exception as e:
                logger.warning(f"Error consultando DolarApi para {nombre_dolar}: {e}. Se utilizará el raspado clásico de respaldo.")

        # 4.1.5 Obtener Riesgo País desde ArgentinaDatos API
        logger.info("Consultando Riesgo País en api.argentinadatos.com...")
        try:
            r_rp = requests.get("https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais", timeout=10)
            if r_rp.status_code == 200:
                data_rp = r_rp.json()
                if data_rp and len(data_rp) > 0:
                    ultimo_dato = data_rp[-1]
                    valor_rp = float(ultimo_dato.get("valor", 0.0))
                    if valor_rp > 0:
                        variables_consolidadas["Riesgo País"] = ["Riesgo País", valor_rp, valor_rp, valor_rp, valor_rp, valor_rp, "0.0%", 1, ahora_str]
                        logger.info(f"  [OK] Riesgo País -> {valor_rp}")
        except Exception as e_rp:
            logger.warning(f"Error consultando Riesgo País: {e_rp}")

        # 4.2 Cargar el resto de las variables por el método tradicional
        for nombre, valores in resultados_agrupados.items():
            # Si ya se procesó de forma nativa arriba, lo salteamos
            if nombre in variables_consolidadas:
                continue

            valores_limpios = procesamiento.filtrar_anomalias(nombre, valores, ws_log)
            if not valores_limpios:
                procesamiento.registrar_log(ws_log, "CRITICAL", f"Sin datos consistentes para {nombre}.")
                continue

            v_min, v_max = min(valores_limpios), max(valores_limpios)
            v_prom = round(sum(valores_limpios) / len(valores_limpios), 2)
            gap = f"{round(((v_max - v_min) / v_min) * 100, 2)}%" if v_min > 0 else "0%"
            
            # Para variables no cambiarias, compra y venta es igual al valor promedio
            variables_consolidadas[nombre] = [nombre, v_prom, v_prom, v_prom, v_min, v_max, gap, len(valores_limpios), ahora_str]

        # 4.3 Escribir todos los resultados consolidados en VARIABLES_MERCADO
        # Mapeamos también la fecha y valor previo para construir el CIERRE_ANTERIOR
        datos_previos_map = {str(row[0]).strip().upper(): row for row in datos_actuales[1:] if row}
        
        for nombre, nueva_fila in variables_consolidadas.items():
            encontrado_idx = filas_existentes.get(nombre.upper())
            cierre_anterior = ""
            if encontrado_idx:
                fila_vieja = datos_previos_map.get(nombre.upper(), [])
                if len(fila_vieja) >= 9:
                    fecha_vieja = str(fila_vieja[8]).strip()
                    v_prom_viejo = str(fila_vieja[3]).strip()
                    c_ant_viejo = str(fila_vieja[9]).strip() if len(fila_vieja) >= 10 else v_prom_viejo
                    
                    # Si la fecha de la última corrida es de un día distinto al de hoy, el valor anterior pasa a ser el cierre
                    if fecha_vieja.split(" ")[0] != ahora_str.split(" ")[0]:
                        cierre_anterior = v_prom_viejo
                    else:
                        cierre_anterior = c_ant_viejo
                else:
                    cierre_anterior = str(nueva_fila[3])
            else:
                cierre_anterior = str(nueva_fila[3])
                
            nueva_fila.append(cierre_anterior)
            
            if encontrado_idx:
                # Escribimos las 10 columnas en el rango correspondiente de la fila i
                ws_vars.update(values=[nueva_fila], range_name=f"A{encontrado_idx}:J{encontrado_idx}")
                logger.info(f"Actualizada variable {nombre} en fila {encontrado_idx}")
            else:
                ws_vars.append_row(nueva_fila)
                logger.info(f"Agregada variable nueva {nombre}")

        # 5. Finalización y Logs de éxito
        resumen = f"OK: {len(variables_consolidadas)} variables procesadas."
        procesamiento.registrar_log(ws_log, "INFO", resumen)
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        procesamiento.actualizar_estado_proceso(ws_status, "OK", resumen, tiempo_ejecucion=duracion)
        logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] >>> Sincronización Finalizada.")
        return True
        
    except Exception as e:
        msg_error = f"Error crítico en proceso general: {e}"
        logger.exception(msg_error)
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        try:
            # Usamos ORIGEN_LOG_CARGA ya que ORIGEN_LOG_MAIN no está definido en config.py
            procesamiento.registrar_log(ws_log, "CRITICAL", msg_error, config.ORIGEN_LOG_CARGA)
            procesamiento.actualizar_estado_proceso(ws_status, "ERROR", "Falla crítica global", tiempo_ejecucion=duracion)
        except:
            pass
        return False

if __name__ == "__main__":
    ejecutar_sincronizacion()