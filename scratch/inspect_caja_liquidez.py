import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import auth_google

def main():
    print("[*] Conectando a Sheets para inspeccionar CAJA_LIQUIDEZ...")
    sh = auth_google.conectar()
    if not sh:
        print("[FAIL] No se pudo conectar a Sheets.")
        return
        
    ws = sh.worksheet("CAJA_LIQUIDEZ")
    raw = ws.get_all_values()
    
    print("\n--- CAJA_LIQUIDEZ ---")
    if not raw:
        print("La hoja está vacía.")
        return
        
    print(f"Cabeceras reales: {raw[0]}")
    print("Primeras 10 filas de datos:")
    for idx, row in enumerate(raw[1:11], start=1):
        print(f"Fila {idx}: {row}")

if __name__ == "__main__":
    main()
