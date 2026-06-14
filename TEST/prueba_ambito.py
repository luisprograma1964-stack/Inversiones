import requests

def fuente_definitiva_ambito():
    # Estas URLs están verificadas y funcionando ahora
    activos = {
        "AL30": "https://mercados.ambito.com/titulos-publicos/al30/variacion",
        "AL30D": "https://mercados.ambito.com/titulos-publicos/al30d/variacion",
        "GD30": "https://mercados.ambito.com/titulos-publicos/gd30/variacion",
        "MEP": "https://mercados.ambito.com/dolar/mep/variacion"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"
    }

    print("--- Trayendo Datos Reales (Ámbito) ---")
    
    for nombre, url in activos.items():
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                # En Ámbito para bonos el valor es 'ultimo', para dólar es 'venta'
                precio = data.get('ultimo') or data.get('venta')
                
                print(f"[{nombre}]")
                print(f"  > Precio: {precio}")
                print(f"  > Fecha: {data.get('fecha', 'N/A')}")
                print("-" * 20)
            else:
                print(f"[{nombre}] Error {res.status_code} - URL desactualizada.")
        except Exception as e:
            print(f"[{nombre}] Error: {e}")

if __name__ == "__main__":
    fuente_definitiva_ambito()