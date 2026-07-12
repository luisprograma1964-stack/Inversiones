import sys
import time
import uuid
import datetime
import pandas as pd
import auth_google
import config
import ia_utils
from procesamiento import registrar_log, actualizar_estado_proceso
import notificador_telegram

def run_kickstart():
    t_inicio = time.time()
    sh = auth_google.conectar()
    if not sh:
        print("Error: No se pudo conectar a Sheets.")
        return

    ws_log = sh.worksheet(config.WS_LOG_SISTEMA)
    ws_status = sh.worksheet("ESTADO_PROCESOS")
    
    actualizar_estado_proceso(ws_status, "PROCESANDO", "Iniciando Kickstart de Tickers", "kickstart_tickers")
    registrar_log(ws_log, "INFO", "Iniciando Kickstart automático para tickers sin sinónimos.", "kickstart_tickers")
    
    try:
        # 1. Traer Maestro Activos
        ws_ma = sh.worksheet("MAESTRO_ACTIVOS")
        df_ma = pd.DataFrame(ws_ma.get_all_records())
        df_ma.columns = [str(c).strip().upper() for c in df_ma.columns]
        
        # 2. Traer Sinónimos Actuales
        ws_sin = sh.worksheet("CONFIG_SINONIMOS")
        df_sin = pd.DataFrame(ws_sin.get_all_records())
        df_sin.columns = [str(c).strip().upper() for c in df_sin.columns]
        
        # 3. Filtrar Activos sin Sinónimos
        col_tk = 'TICKER_ID' if 'TICKER_ID' in df_ma.columns else ('TICKER' if 'TICKER' in df_ma.columns else None)
        if 'ESTADO' in df_ma.columns and col_tk:
            activos = df_ma[df_ma['ESTADO'].astype(str).str.upper() == 'ACTIVO'][col_tk].dropna().unique()
        else:
            activos = []
            
        con_sinonimos = df_sin['TICKER'].dropna().unique() if 'TICKER' in df_sin.columns else []
        
        faltantes = [t for t in activos if t not in con_sinonimos]
        
        # Si se pasa un ticker específico por arg, priorizarlo (por compatibilidad o pruebas)
        if len(sys.argv) > 1:
            tk_arg = sys.argv[1].upper()
            if tk_arg not in con_sinonimos:
                faltantes = [tk_arg]
            else:
                faltantes = []
                
        if not faltantes:
            msg = "No hay tickers activos que requieran kickstart (todos tienen sinónimos)."
            actualizar_estado_proceso(ws_status, "OK", msg, "kickstart_tickers", f"{round((time.time() - t_inicio) / 60, 2)} min")
            registrar_log(ws_log, "INFO", msg, "kickstart_tickers")
            try:
                notificador_telegram.enviar_mensaje_telegram("🚀 <b>Kickstart finalizado</b>: No hay tickers nuevos sin sinónimos.")
            except: pass
            return

        ws_sug = sh.worksheet("SUGERENCIAS_SINONIMOS")
        nuevos_totales = 0
        
        import yfinance as yf
        
        for ticker in faltantes:
            registrar_log(ws_log, "INFO", f"Generando sugerencias para {ticker}...", "kickstart_tickers")
            
            # --- VALIDACIÓN DE SUPERVIVENCIA (yfinance) ---
            ticker_activado = False
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="5d")
                if hist.empty:
                    msg_dead = f"El ticker {ticker} parece estar deslistado o sin precios recientes en el mercado. Se aborta la creación de sinónimos."
                    registrar_log(ws_log, "WARNING", msg_dead, "kickstart_tickers")
                    
                    # Auto-Deslistar en el Maestro
                    try:
                        celda = ws_ma.find(ticker)
                        if celda:
                            headers = ws_ma.row_values(1)
                            if 'ESTADO' in headers:
                                ws_ma.update_cell(celda.row, headers.index('ESTADO') + 1, 'DESLISTADO')
                                msg_dead += " Fue movido automáticamente a DESLISTADO."
                    except Exception as e_sheets:
                        pass
                        
                    try:
                        notificador_telegram.enviar_mensaje_telegram(f"⚠️ <b>Ticker Deslistado</b>\n\n{msg_dead}")
                    except: pass
                    continue
                else:
                    # ES VALIDO. Validamos/Activamos en el MAESTRO_ACTIVOS
                    try:
                        celda = ws_ma.find(ticker)
                        headers = ws_ma.row_values(1)
                        if celda:
                            if 'ESTADO' in headers:
                                current_state = ws_ma.cell(celda.row, headers.index('ESTADO') + 1).value
                                if str(current_state).strip().upper() != 'ACTIVO':
                                    ws_ma.update_cell(celda.row, headers.index('ESTADO') + 1, 'ACTIVO')
                                    ticker_activado = True
                        else:
                            # NO EXISTE EN EL MAESTRO. LO CREAMOS!
                            nueva_fila = []
                            for h in headers:
                                h_upper = h.upper()
                                if h_upper in ['TICKER', 'TICKER_ID']:
                                    nueva_fila.append(ticker)
                                elif h_upper == 'ESTADO':
                                    nueva_fila.append('ACTIVO')
                                elif h_upper == 'MERCADO':
                                    nueva_fila.append('US') # default
                                elif h_upper == 'MONEDA':
                                    nueva_fila.append('USD')
                                elif h_upper in ['NOMBRE', 'DESCRIPCION']:
                                    nueva_fila.append(f'Auto-creado por Kickstart ({ticker})')
                                else:
                                    nueva_fila.append('')
                            ws_ma.append_row(nueva_fila, value_input_option='USER_ENTERED')
                            ticker_activado = True
                    except Exception as ex_maestro:
                        print("Error actualizando maestro:", ex_maestro)
            except Exception as e_yf:
                pass # Si hay error de red temporal, permitimos que siga
            # ----------------------------------------------

            prompt = f"Actúa como un experto en mercados financieros. Para el activo financiero (acción, ETF, bono o empresa) cuyo Ticker es '{ticker}', dime hasta 5 variaciones de cómo se lo suele nombrar en las noticias (ej. marcas clave, nombre coloquial). IMPORTANTE: No incluyas sufijos ni nombres corporativos largos (como 'Group', 'Inc.', 'SA', 'LLC', 'Corp') si también vas a incluir la versión corta, ya que en la búsqueda de texto la versión corta ya engloba a la larga. Sé minimalista y devuelve SOLAMENTE LOS NOMBRES SEPARADOS POR COMAS, sin explicaciones ni viñetas. Si no lo conoces, devuelve 'DESCONOCIDO'."
            
            respuesta = None
            try:
                from google import genai
                import google.genai.types as types
                from pathlib import Path
                
                key = config.get_gemini_api_key()                
                client = genai.Client(api_key=key)
                
                candidatos = ia_utils.obtener_modelos_activos()
                        
                for m in candidatos:
                    try:
                        response = client.models.generate_content(
                            model=m,
                            contents=prompt,
                            config=types.GenerateContentConfig(temperature=0.2)
                        )
                        respuesta = response.text
                        break
                    except Exception as ex:
                        error_str = str(ex)
                        print(f"Error AI con {m}: {error_str}")
                        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                            print(f"Cuota agotada en {m}. Esperando 60 segundos antes de reintentar...")
                            time.sleep(60)
                            try:
                                response = client.models.generate_content(
                                    model=m,
                                    contents=prompt,
                                    config=types.GenerateContentConfig(temperature=0.2)
                                )
                                respuesta = response.text
                                break
                            except Exception as retry_ex:
                                print(f"Fallo en reintento con {m}: {retry_ex}")
            except Exception as e_init:
                print(f"Error AI Init: {e_init}")
            
            
            if not respuesta or "DESCONOCIDO" in respuesta.upper():
                registrar_log(ws_log, "WARNING", f"IA no encontró sinónimos obvios para {ticker}.", "kickstart_tickers")
                continue
                
            sinonimos = [s.strip() for s in respuesta.split(',')]
            ahora_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            nuevos_ticker = 0
            sug_rows = []
            for sin in sinonimos:
                if sin:
                    sug_id = str(uuid.uuid4())[:8]
                    # Format: ID, FECHA, TITULAR, TERMINO, TICKER, EXPLICACION, ESTADO
                    sug_rows.append([
                        sug_id,
                        ahora_str,
                        f"KICKSTART: Búsqueda proactiva para {ticker}",
                        sin,
                        ticker,
                        "Generado por Inicialización Rápida (Kickstart).",
                        "PENDIENTE"
                    ])
                    nuevos_ticker += 1
            
            if sug_rows:
                ws_sug.append_rows(sug_rows, value_input_option='USER_ENTERED')
                nuevos_totales += nuevos_ticker
                
                # Notificar a TG (Consolidado)
                msg_tg = f"✅ <b>Kickstart Exitoso para {ticker}</b>\n\n"
                if ticker_activado:
                    msg_tg += f"🔹 El activo fue <b>activado/creado</b> exitosamente en el Maestro.\n"
                msg_tg += f"🔹 Se generaron <b>{nuevos_ticker} sugerencias</b> de sinónimos."
                try:
                    notificador_telegram.enviar_mensaje_telegram(msg_tg)
                except: pass
                    
            time.sleep(2) # Evitar rate limit de Gemini
            
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        msg_fin = f"Kickstart completado: Se sugirieron {nuevos_totales} sinónimos para {len(faltantes)} activos."
        actualizar_estado_proceso(ws_status, "OK", msg_fin, "kickstart_tickers", duracion)
        registrar_log(ws_log, "INFO", msg_fin, "kickstart_tickers")
        
        # try:
        #     notificador_telegram.enviar_mensaje_telegram(f"✅ <b>Proceso de Inicialización de Tickers (Kickstart)</b> finalizado con éxito.\n{msg_fin}")
        # except: pass

    except Exception as e:
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        msg_error = f"Error en kickstart: {str(e)[:50]}"
        actualizar_estado_proceso(ws_status, "ERROR", msg_error, "kickstart_tickers", duracion)
        registrar_log(ws_log, "ERROR", msg_error, "kickstart_tickers")
        try:
            notificador_telegram.enviar_mensaje_telegram(f"❌ <b>Error en Kickstart</b>: {msg_error}")
        except: pass

if __name__ == "__main__":
    run_kickstart()
