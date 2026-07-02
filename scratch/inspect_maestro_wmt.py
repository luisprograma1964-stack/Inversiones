import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import auth_google
import pandas as pd

def main():
    print("[*] Conectando a Sheets para inspeccionar WMT en MAESTRO_ACTIVOS...")
    sh = auth_google.conectar()
    if not sh:
        return
        
    ws = sh.worksheet("MAESTRO_ACTIVOS")
    df = pd.DataFrame(ws.get_all_records())
    df.columns = [c.strip().upper() for c in df.columns]
    
    print("\n--- MAESTRO_ACTIVOS para WMT ---")
    df_wmt = df[df["TICKER_ID"].astype(str).str.contains("WMT", case=False)]
    print(df_wmt)

if __name__ == "__main__":
    main()
