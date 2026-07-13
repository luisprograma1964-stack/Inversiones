import sys
import os
import streamlit as st
import pandas as pd

sys.path.append('C:\\Para mi\\Inversiones')
import auth_google
import config

def cargar_datos_hoja(sheet_name):
    sh = auth_google.conectar()
    ws = sh.worksheet(sheet_name)
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    df.columns = [c.strip().upper() for c in df.columns]
    return df

df_historico_velas = cargar_datos_hoja(config.WS_HISTORICO_VALORES)

st.write(f"Total rows: {len(df_historico_velas)}")
ticker_final = "BCBA:AAPL"
df_hist_act = df_historico_velas[df_historico_velas["TICKER_ID"].astype(str).str.strip().str.upper() == ticker_final.upper()]
st.write(f"Rows for {ticker_final}: {len(df_hist_act)}")

# Guardar un archivo local para que yo pueda leer el resultado
with open("test_result.txt", "w") as f:
    f.write(f"Total rows: {len(df_historico_velas)}\nRows for {ticker_final}: {len(df_hist_act)}")
