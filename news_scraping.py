"""
Sub-módulo de captura de noticias vía Scraping Puro (HTML parsing).
Diseñado para descubrir noticias en secciones que no poseen RSS o APIs.
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging_config

logger = logging_config.get_logger(__name__)

# URLs objetivo para "Descubrimiento" (Análisis, Tendencias y Opinión)
SITIOS_SCRAP = [
    {
        "nombre": "Investing Análisis",
        "url": "https://es.investing.com/analysis/most-popular-analysis",
        "selector": "article.articleItem", # Patrón común en Investing para noticias
        "base_url": "https://es.investing.com"
    },
    {
        "nombre": "Ámbito Economía",
        "url": "https://www.ambito.com/contenidos/economia.html",
        "selector": "article.news-article",
        "base_url": "https://www.ambito.com"
    },
    {
        "nombre": "Cronista Últimas",
        "url": "https://www.cronista.com/ultimas-noticias/",
        "selector": "article",
        "base_url": "https://www.cronista.com"
    }
]

def capturar_scraping():
    """
    Realiza el parseo HTML de sitios seleccionados para encontrar noticias extra.
    """
    noticias_capturadas = []
    # Header para simular navegador real y evitar bloqueos (403 Forbidden)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for sitio in SITIOS_SCRAP:
        try:
            r = requests.get(sitio["url"], headers=headers, timeout=15)
            if r.status_code != 200:
                continue
            
            soup = BeautifulSoup(r.text, 'html.parser')
            articulos = soup.select(sitio["selector"])
            
            for art in articulos[:10]: # Tomamos las 10 más recientes por sitio para evitar ruido
                link_tag = art.find('a')
                if not link_tag: continue
                
                titulo = link_tag.get_text(strip=True)
                url_final = link_tag.get('href', '')
                
                if not url_final.startswith('http'):
                    url_final = sitio["base_url"] + url_final
                
                if titulo and url_final:
                    noticias_capturadas.append({
                        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "ticker": "9999", # El orquestador o la IA lo reclasificarán
                        "titular": titulo,
                        "fuente": sitio["nombre"],
                        "submodulo": "SCRAPING",
                        "url": url_final,
                        "canal_origen": "N/A"
                    })
        except Exception as e:
            logger.exception(f"Error scrappeando {sitio['nombre']}: {e}")
            
    return noticias_capturadas

if __name__ == "__main__":
    # Test de funcionamiento independiente
    logger.info("Iniciando prueba de Scraping de Descubrimiento...")
    res = capturar_scraping()
    logger.info(f"Capturadas {len(res)} noticias.")
    for r in res[:5]:
        logger.info(f" - [{r['fuente']}] {r['titular']}")