import sys
sys.path.append('C:\\Para mi\\Inversiones')
import auth_google, config
import pandas as pd

sh = auth_google.conectar()

# 1. Traer los logs del sistema
try:
    ws_log = sh.worksheet(config.WS_LOG_SISTEMA)
    df_log = pd.DataFrame(ws_log.get_all_records())
    print("\n--- ÚLTIMOS 20 LOGS DEL SISTEMA ---")
    if not df_log.empty:
        print(df_log.tail(20).to_string())
    else:
        print("Log vacío.")
except Exception as e:
    print("Error leyendo logs:", e)

# 2. Traer el estado de procesos
try:
    ws_status = sh.worksheet(config.WS_ESTADO_PROCESOS)
    df_status = pd.DataFrame(ws_status.get_all_records())
    print("\n--- ESTADO PROCESOS ---")
    print(df_status.to_string())
except Exception as e:
    print("Error leyendo estado procesos:", e)

# 3. Traer el historial de veredictos de IA
try:
    ws_ia = sh.worksheet(config.WS_HISTORIAL_VEREDICTOS)
    df_ia = pd.DataFrame(ws_ia.get_all_records())
    print("\n--- ÚLTIMOS VEREDICTOS DE IA ---")
    if not df_ia.empty:
        print(f"Total veredictos generados: {len(df_ia)}")
        print(df_ia.tail(5)[['TICKER_ID', 'USUARIO', 'FECHA', 'ACCION_SUGERIDA']].to_string())
    else:
        print("Historial IA vacío.")
except Exception as e:
    print("Error leyendo historial IA:", e)
