import requests
import logging_config

logger = logging_config.get_logger(__name__)

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

    logger.info("--- Trayendo Datos Reales (Ámbito) ---")
    
    for nombre, url in activos.items():
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                # En Ámbito para bonos el valor es 'ultimo', para dólar es 'venta'
                precio = data.get('ultimo') or data.get('venta')
                
                logger.info(f"[{nombre}] Precio: {precio} Fecha: {data.get('fecha', 'N/A')}")
            else:
                logger.warning(f"[{nombre}] Error {res.status_code} - URL desactualizada.")
        except Exception as e:
            logger.exception(f"[{nombre}] Error: {e}")

if __name__ == "__main__":
    fuente_definitiva_ambito()