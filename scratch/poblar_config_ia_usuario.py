import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import auth_google
import pandas as pd
import config

def main():
    print("[*] Conectando a Sheets para poblar CONFIG_IA_USUARIO...")
    sh = auth_google.conectar()
    if not sh:
        return
        
    ws = sh.worksheet(config.WS_CONFIG_IA_USUARIO)
    
    # Datos de perfiles de riesgo coherentes
    datos = [
        {"Usuario_ID": "LUIS", "Perfil_Riesgo": "Agresivo", "Mix_Target": "Acciones Tech: 60%, Cedears Estables: 30%, Liquidez: 10%", "Tolerancia_Desvio": "0.10"},
        {"Usuario_ID": "LUIS_MODERADO", "Perfil_Riesgo": "Moderado", "Mix_Target": "ETF Indexados: 50%, Bonos: 30%, Oro/Soberanos: 10%, Liquidez: 10%", "Tolerancia_Desvio": "0.05"},
        {"Usuario_ID": "VICKY", "Perfil_Riesgo": "Conservador", "Mix_Target": "Dólar Billete: 50%, Plazo Fijo/Leliqs: 30%, Obligaciones Negociables: 20%", "Tolerancia_Desvio": "0.02"},
        {"Usuario_ID": "ANTO", "Perfil_Riesgo": "Conservador", "Mix_Target": "Fondo Común de Inversión: 60%, Renta Fija: 30%, Liquidez: 10%", "Tolerancia_Desvio": "0.02"}
    ]
    
    df = pd.DataFrame(datos)
    
    ws.clear()
    # Escribir encabezados
    ws.update(values=[df.columns.values.tolist()], range_name="A1")
    # Escribir filas
    ws.append_rows(df.values.tolist())
    
    print("[OK] CONFIG_IA_USUARIO poblada exitosamente.")

if __name__ == "__main__":
    main()
