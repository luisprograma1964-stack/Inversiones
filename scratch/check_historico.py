import auth_google, config, pandas as pd
sh = auth_google.conectar()
ws = sh.worksheet(config.WS_HISTORICO_VALORES)
data = ws.get_all_records()
if data:
    df = pd.DataFrame(data)
    print("Unique TICKER_IDs:", df['TICKER_ID'].unique()[:50])
else:
    print("HISTORICO_VALORES is empty!")
