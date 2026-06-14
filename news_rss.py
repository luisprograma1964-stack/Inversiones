"""
Sub-módulo de captura de noticias vía RSS.
Extrae titulares y enlaces de fuentes financieras estándar.
"""
import feedparser
from datetime import datetime

# Configuración de fuentes RSS (Podrías mover esto a una tabla luego)
FUENTES_RSS = {
    "Reuters Business": "https://www.reutersagency.com/feed/?best-topics=business&post_type=best",
    "CNBC Finance": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
    "Ambito Financiero": "https://www.ambito.com/rss/pages/home.xml"
}

def capturar_rss():
    """
    Consulta todas las fuentes RSS y devuelve una lista de diccionarios normalizada.
    """
    noticias_capturadas = []
    
    for nombre_fuente, url in FUENTES_RSS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                # Normalización básica
                noticia = {
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "ticker": "9999", # Por defecto macro, el orquestador puede re-asignar
                    "titular": entry.title,
                    "fuente": nombre_fuente,
                    "submodulo": "RSS",
                    "url": entry.link,
                    "canal_origen": "N/A"
                }
                noticias_capturadas.append(noticia)
        except Exception as e:
            print(f"Error capturando RSS de {nombre_fuente}: {e}")
            
    return noticias_capturadas

if __name__ == "__main__":
    # Test rápido
    resultados = capturar_rss()
    print(f"Capturadas {len(resultados)} noticias vía RSS.")
    for r in resultados[:3]:
        print(f"- {r['titular']} ({r['fuente']})")