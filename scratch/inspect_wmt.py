import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import auth_google
import pandas as pd

def main():
    print("[*] Conectando a Sheets para inspeccionar WMT...")
    sh = auth_google.conectar()
    if not sh:
        return
        
    # Verificar en HISTORICO_VALORES
    ws_hist = sh.worksheet("HISTORICO_VALORES")
    df_hist = pd.DataFrame(ws_hist.get_all_records())
    df_hist.columns = [c.strip().upper() for c in df_hist.columns]
    
    print("\n--- HISTORICO_VALORES para WMT ---")
    df_wmt = df_hist[df_hist["TICKER_ID"].astype(str).str.contains("WMT", case=False)]
    if df_wmt.empty:
        print("No se encontraron registros de WMT en HISTORICO_VALORES.")
    else:
        print(f"Total registros WMT: {len(df_wmt)}")
        df_wmt_sorted = df_wmt.sort_values(by="FECHA", ascending=False)
        print("Últimos 5 registros históricos de WMT:")
        print(df_wmt_sorted.head(5))

    # Verificar en ANALISIS_TECNICO
    ws_tecnico = sh.worksheet("ANALISIS_TECNICO")
    df_tecnico = pd.DataFrame(ws_tecnico.get_all_records())
    df_tecnico.columns = [c.strip().upper() for c in df_tecnico.columns]
    
    print("\n--- ANALISIS_TECNICO para WMT ---")
    df_tec_wmt = df_tecnico[df_tecnico["TICKER_ID"].astype(str).str.contains("WMT", case=False)]
    if df_tec_wmt.empty:
        print("No se encontró registro de WMT en ANALISIS_TECNICO.")
    else:
        print(df_tec_wmt)

if __name__ == "__main__":
    main()
