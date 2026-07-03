import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import auth_google
import pandas as pd
import config

def main():
    print("[*] Conectando a Sheets para forzar análisis técnico en PENDIENTE...")
    sh = auth_google.conectar()
    if not sh:
        return
        
    ws = sh.worksheet(config.WS_ANALISIS_TECNICO)
    raw = ws.get_all_values()
    if not raw or len(raw) < 2:
        print("[!] No hay datos en ANALISIS_TECNICO.")
        return
        
    headers = [h.strip().upper() for h in raw[0]]
    col_estado_idx = headers.index("ESTADO") + 1
    
    print(f"[*] Modificando columna ESTADO (columna {col_estado_idx}) a 'PENDIENTE' para todos los activos...")
    
    # Recorrer filas y actualizar celda por celda
    for r_idx in range(2, len(raw) + 1):
        ws.update_cell(r_idx, col_estado_idx, "PENDIENTE")
        
    print("[OK] Todos los activos marcados como PENDIENTE en ANALISIS_TECNICO.")

if __name__ == "__main__":
    main()
