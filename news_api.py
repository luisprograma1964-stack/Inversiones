"""
Sub-módulo de captura de noticias vía API (CryptoPanic).
Extrae sentimiento y noticias de mercado global.
"""
import requests
from datetime import datetime

def capturar_cryptopanic():
    """
    Consulta la API de CryptoPanic para obtener noticias de mercado importantes.
    """
    noticias_capturadas = []
    url = "https://cryptopanic.com/api/v1/posts/?kind=news&filter=important"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for post in data.get('results', [])[:10]:
                noticias_capturadas.append({
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "ticker": "9999",
                    "titular": post.get('title'),
                    "fuente": post.get('source', {}).get('title', 'CryptoPanic'),
                    "submodulo": "NEWS_API",
                    "url": post.get('url'),
                    "canal_origen": "N/A"
                })
    except Exception as e:
        print(f"Error en News API (CryptoPanic): {e}")
            
    return noticias_capturadas