import os
from pathlib import Path
from datetime import datetime

def main():
    print("[*] Inspeccionando archivos en la carpeta logs/...")
    logs_dir = Path("logs")
    if not logs_dir.exists():
        print("La carpeta logs/ no existe.")
        return
        
    archivos = list(logs_dir.glob("*.log"))
    if not archivos:
        print("No se encontraron archivos .log en la carpeta logs/.")
        return
        
    for idx, f in enumerate(archivos, start=1):
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        size = f.stat().st_size
        print(f"Archivo {idx}: {f.name} | Tamaño: {size} bytes | Modificado: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
