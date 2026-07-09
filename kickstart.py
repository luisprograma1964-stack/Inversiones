import sys
import time
import uuid
import datetime
import pandas as pd
import auth_google
import config
import ia_utils
import notificador_telegram
from logger_utils import registrar_log, actualizar_estado_proceso

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
        if 'ESTADO' in df_ma.columns and 'TICKER' in df_ma.columns:
            activos = df_ma[df_ma['ESTADO'].astype(str).str.upper() == 'ACTIVO']['TICKER'].dropna().unique()
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
            except Exception as e_yf:
                pass # Si hay error de red temporal, permitimos que siga
            # ----------------------------------------------

            
            prompt = f"Actúa como un experto en mercados financieros. Para el activo financiero (acción, ETF, bono o empresa) cuyo Ticker es '{ticker}', dime hasta 5 variaciones de cómo se lo suele nombrar en las noticias (ej. el nombre de la empresa completo, marcas clave, nombre coloquial). DEVUELVE SOLAMENTE LOS NOMBRES SEPARADOS POR COMAS, sin explicaciones ni viñetas. Si no lo conoces, devuelve 'DESCONOCIDO'."
            respuesta = ia_utils.consultar_gemini_generativo(prompt)
            
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
                
                # Notificar a TG
                for r in sug_rows:
                    msg = f"🔔 <b>Sugerencia Kickstart (AI)</b>\n\nSe sugiere el término <code>{r[3]}</code> para el activo <b>{r[4]}</b>.\n\n<b>Motivo/Explicación:</b> {r[5]}\n\nRevisalo en el Panel de Administración."
                    try:
                        notificador_telegram.enviar_mensaje_telegram(msg)
                    except: pass
                    
            time.sleep(2) # Evitar rate limit de Gemini
            
        duracion = f"{round((time.time() - t_inicio) / 60, 2)} min"
        msg_fin = f"Kickstart completado: Se sugirieron {nuevos_totales} sinónimos para {len(faltantes)} activos."
        actualizar_estado_proceso(ws_status, "OK", msg_fin, "kickstart_tickers", duracion)
        registrar_log(ws_log, "INFO", msg_fin, "kickstart_tickers")
        
        try:
            notificador_telegram.enviar_mensaje_telegram(f"✅ <b>Proceso de Inicialización de Tickers (Kickstart)</b> finalizado con éxito.\n{msg_fin}")
        except: pass

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
