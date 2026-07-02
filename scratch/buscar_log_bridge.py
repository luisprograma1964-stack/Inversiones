import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def main():
    print("[*] Buscando mensajes del Bridge en el log de inversiones...")
    log_path = "logs/inversiones.log"
    if not os.path.exists(log_path):
        print("El archivo logs/inversiones.log no existe.")
        return
        
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
        
    print(f"Total líneas de log: {len(lines)}")
    print("\n--- Mensajes del Bridge (Últimas 100 líneas) ---")
    bridge_lines = [l for l in lines if "bridge" in l.lower() or "carga_historica" in l.lower()]
    for l in bridge_lines[-100:]:
        print(l.strip().encode('ascii', errors='replace').decode('ascii'))

if __name__ == "__main__":
    main()
