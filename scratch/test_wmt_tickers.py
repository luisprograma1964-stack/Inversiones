import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import auth_google
import time

def test_ticker(ws, formula_str, label):
    """Escribe una formula en A1 y reporta el resultado despues de 8 segundos."""
    ws.clear()
    ws.update(values=[[formula_str]], range_name="A1", raw=False)
    time.sleep(8)
    raw = ws.get_all_values()
    if raw:
        cell = raw[0][0] if raw[0] else "(vacío)"
        rows = len(raw)
        print(f"  [{label}] Celdas leídas: {rows} filas | Primera celda: '{cell}'")
    else:
        print(f"  [{label}] Sin datos")
    return raw

def main():
    print("[*] Conectando a Sheets para probar formatos de ticker WMT...")
    sh = auth_google.conectar()
    if not sh:
        return
        
    import config
    ws = sh.worksheet(config.WS_DOWNLOAD_BUFFER)
    
    f_ini = "2026-06-25"
    f_fin = "2026-07-01"
    
    tickers_a_probar = [
        ("NYSE:WMT",   f'=GOOGLEFINANCE("NYSE:WMT"; "close"; "{f_ini}"; "{f_fin}")'),
        ("WMT",        f'=GOOGLEFINANCE("WMT"; "close"; "{f_ini}"; "{f_fin}")'),
        ("NYSEARCA:WMT", f'=GOOGLEFINANCE("NYSEARCA:WMT"; "close"; "{f_ini}"; "{f_fin}")'),
        ("BCBA:WMT",   f'=GOOGLEFINANCE("BCBA:WMT"; "close"; "{f_ini}"; "{f_fin}")'),
    ]
    
    print(f"\n--- Probando formatos para WMT (rango {f_ini} a {f_fin}) ---")
    for label, formula in tickers_a_probar:
        test_ticker(ws, formula, label)
    
    ws.clear()
    print("\n[*] Prueba finalizada.")

if __name__ == "__main__":
    main()
