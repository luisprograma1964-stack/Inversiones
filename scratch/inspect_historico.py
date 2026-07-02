import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import auth_google
import pandas as pd

def inspect():
    sh = auth_google.conectar()
    ws = sh.worksheet("HISTORICO_VALORES")
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    print("Columnas de HISTORICO_VALORES:", df.columns.tolist())
    print("Total registros:", len(df))
    if not df.empty:
        col_ticker = next((c for c in df.columns if "TICKER" in c.upper()), None)
        if col_ticker:
            print("Tickers únicos en base:", df[col_ticker].unique())
            # Ver registros para BCBA:AAPL
            df_aapl = df[df[col_ticker].astype(str).str.strip().str.upper() == "BCBA:AAPL"]
            print("Registros BCBA:AAPL encontrados:", len(df_aapl))
            if not df_aapl.empty:
                print("Primeros 5 registros de BCBA:AAPL:")
                print(df_aapl.head(5))
        else:
            print("No se encontró columna Ticker")

if __name__ == "__main__":
    inspect()
