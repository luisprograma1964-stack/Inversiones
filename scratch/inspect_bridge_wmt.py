import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import auth_google
import pandas as pd
import time
from datetime import datetime, timedelta
import config

def main():
    print("[*] Conectando a Sheets para simular la descarga de WMT en USD...")
    sh = auth_google.conectar()
    if not sh:
        return
        
    ws_buffer = sh.worksheet(config.WS_DOWNLOAD_BUFFER)
    
    # Escribir la fórmula de WMT en A1
    f_ini = "2026-06-19"
    f_fin = datetime.now().strftime("%Y-%m-%d")
    formula = f'=GOOGLEFINANCE("NYSE:WMT"; "all"; "{f_ini}"; "{f_fin}")'
    
    print(f"[*] Escribiendo fórmula en buffer A1: {formula}")
    ws_buffer.clear()
    ws_buffer.update(values=[[formula]], range_name="A1", raw=False)
    
    print("[*] Esperando 10 segundos para que Google Sheets resuelva la fórmula...")
    time.sleep(10)
    
    # Leer el buffer
    raw_buffer = ws_buffer.get_all_values()
    print(f"[*] Filas leídas del buffer: {len(raw_buffer)}")
    if len(raw_buffer) > 0:
        print("Primeras 5 filas del resultado de GOOGLEFINANCE:")
        for idx, row in enumerate(raw_buffer[:5]):
            print(f"Fila {idx}: {row}")
            
    # Sincronizar el par local BCBA:WMT
    formula_byma = f'=GOOGLEFINANCE("BCBA:WMT"; "all"; "{f_ini}"; "{f_fin}")'
    print(f"\n[*] Escribiendo fórmula BYMA en buffer A1: {formula_byma}")
    ws_buffer.clear()
    ws_buffer.update(values=[[formula_byma]], range_name="A1", raw=False)
    
    print("[*] Esperando 10 segundos...")
    time.sleep(10)
    
    raw_buffer_byma = ws_buffer.get_all_values()
    print(f"[*] Filas leídas del buffer BYMA: {len(raw_buffer_byma)}")
    if len(raw_buffer_byma) > 0:
        print("Primeras 5 filas del resultado de GOOGLEFINANCE BYMA:")
        for idx, row in enumerate(raw_buffer_byma[:5]):
            print(f"Fila {idx}: {row}")

if __name__ == "__main__":
    main()
