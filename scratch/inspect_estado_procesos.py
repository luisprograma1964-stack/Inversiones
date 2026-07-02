import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import auth_google
import pandas as pd

def main():
    print("[*] Conectando a Sheets para inspeccionar ESTADO_PROCESOS...")
    sh = auth_google.conectar()
    if not sh:
        return
        
    ws = sh.worksheet("ESTADO_PROCESOS")
    df = pd.DataFrame(ws.get_all_records())
    df.columns = [c.strip().upper() for c in df.columns]
    
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print("\n--- ESTADO_PROCESOS ---")
    output_str = df[['NOMBRE_PROCESO', 'ESTADO', 'DETALLE', 'ULTIMA_CORRIDA']].to_string()
    print(output_str.encode('ascii', errors='replace').decode('ascii'))

if __name__ == "__main__":
    main()
