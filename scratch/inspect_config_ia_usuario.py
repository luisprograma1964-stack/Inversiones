import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import auth_google
import pandas as pd
import config

def main():
    print("[*] Conectando a Sheets para inspeccionar CONFIG_IA_USUARIO...")
    sh = auth_google.conectar()
    if not sh:
        return
        
    ws = sh.worksheet(config.WS_CONFIG_IA_USUARIO)
    df = pd.DataFrame(ws.get_all_records())
    
    print("\n--- CONFIG_IA_USUARIO ---")
    print(df)
    
    mapa_usuarios = {str(u['Perfil_Riesgo']).strip(): str(u['Usuario_ID']).strip() for u in ws.get_all_records() if u.get('Perfil_Riesgo')}
    print("\n--- mapa_usuarios construido en decisor_con_ia.py ---")
    print(mapa_usuarios)

if __name__ == "__main__":
    main()
