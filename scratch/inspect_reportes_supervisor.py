import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pathlib import Path
import auth_google
import pandas as pd
from datetime import datetime

def main():
    print("[*] Conectando a Sheets para verificar fechas de ejecución...")
    sh = auth_google.conectar()
    if not sh:
        return
        
    ws_status = sh.worksheet("ESTADO_PROCESOS")
    raw_values = ws_status.get_all_values()
    df = pd.DataFrame(raw_values[1:], columns=[str(h).strip().upper() for h in raw_values[0]])
    
    print("\n--- ULTIMA CORRIDA EN ESTADO_PROCESOS ---")
    output_str = df[['NOMBRE_PROCESO', 'ESTADO', 'ULTIMA_CORRIDA', 'DETALLE']].to_string()
    print(output_str.encode('ascii', errors='replace').decode('ascii'))
    
    # 2. Listar reportes en ESTRATEGIA_REPORTS
    print("\n--- REPORTES EN ESTRATEGIA_REPORTS ---")
    workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rep_dir = Path(os.path.join(workspace_dir, "ESTRATEGIA_REPORTS"))
    
    if not rep_dir.exists():
        print("La carpeta ESTRATEGIA_REPORTS no existe.")
        return
        
    archivos = sorted(list(rep_dir.glob("*.md")), key=lambda x: x.stat().st_mtime, reverse=True)
    if not archivos:
        print("No se encontraron reportes .md.")
        return
        
    for idx, f in enumerate(archivos[:5], start=1):
        mtime_dt = datetime.fromtimestamp(f.stat().st_mtime)
        print(f"Reporte {idx}: {f.name} | Modificado: {mtime_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        
    # Leer el contenido del reporte más reciente para ver su contenido
    print(f"\n--- CONTENIDO DEL REPORTE MAS RECIENTE ({archivos[0].name}) ---")
    with open(archivos[0], "r", encoding="utf-8") as f:
        content = f.read()
        print(content.encode('ascii', errors='replace').decode('ascii'))

if __name__ == "__main__":
    main()
