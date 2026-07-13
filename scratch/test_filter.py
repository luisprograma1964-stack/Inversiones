import sys
sys.path.append('C:\\Para mi\\Inversiones')
import auth_google
import config
import pandas as pd

sh = auth_google.conectar()
ws = sh.worksheet(config.WS_HISTORICO_VALORES)
data = ws.get_all_records()
df = pd.DataFrame(data)
df.columns = [c.strip().upper() for c in df.columns]

ticker_final = "BCBA:AAPL"
df_hist_act = df[df["TICKER_ID"].astype(str).str.strip().str.upper() == ticker_final.upper()]

print(f"Total rows: {len(df)}")
print(f"Rows for {ticker_final}: {len(df_hist_act)}")

if not df_hist_act.empty:
    print(df_hist_act.head(2))
