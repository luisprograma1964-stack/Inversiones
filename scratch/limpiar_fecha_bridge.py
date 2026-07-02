import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import auth_google
import pandas as pd

def main():
    print("[*] Conectando a Sheets para forzar corrida del Bridge...")
    sh = auth_google.conectar()
    if not sh:
        return
        
    ws_status = sh.worksheet("ESTADO_PROCESOS")
    raw_values = ws_status.get_all_values()
    headers = [h.strip().upper() for h in raw_values[0]]
    
    col_proc_idx = headers.index("NOMBRE_PROCESO") + 1
    col_fecha_idx = headers.index("ULTIMA_CORRIDA") + 1
    col_estado_idx = headers.index("ESTADO") + 1
    col_detalle_idx = headers.index("DETALLE") + 1
    
    # Buscar la fila de carga_historica_bridge
    row_num = None
    for idx, row in enumerate(raw_values[1:], start=2):
        if row[col_proc_idx - 1] == "carga_historica_bridge":
            row_num = idx
            break
            
    if row_num:
        # Ponemos una fecha del mes pasado para forzar la ejecución hoy
        ws_status.update_cell(row_num, col_fecha_idx, "2026-06-15 00:00:00")
        ws_status.update_cell(row_num, col_estado_idx, "PENDIENTE")
        ws_status.update_cell(row_num, col_detalle_idx, "Forzado para recarga de históricos")
        print("[OK] Fecha de última corrida de carga_historica_bridge restablecida. El Bridge se ejecutará en la próxima corrida.")
    else:
        print("[FAIL] No se encontró el proceso 'carga_historica_bridge' en la tabla.")

if __name__ == "__main__":
    main()
