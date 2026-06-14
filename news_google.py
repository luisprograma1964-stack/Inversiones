"""
Sub-módulo de captura de noticias vía Google News.
Realiza búsquedas específicas basadas en los filtros definidos en el Maestro de Activos.
"""
from pygooglenews import GoogleNews
from datetime import datetime

def capturar_google_news(lista_busquedas):
    """
    Recibe una lista de diccionarios con {'ticker': ..., 'filtro': ...}
    y devuelve los resultados encontrados en las últimas 24hs.
    """
    gn = GoogleNews(lang='es', country='AR')
    noticias_capturadas = []

    for item in lista_busquedas:
        ticker = item.get('ticker')
        query = item.get('filtro')
        
        if not query:
            continue
            
        try:
            # Buscamos noticias del último día para no traer cosas viejas
            search = gn.search(f"{query} when:24h")
            
            for entry in search['entries'][:3]: # Tomamos las 3 más relevantes por filtro
                noticias_capturadas.append({
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "ticker": ticker,
                    "titular": entry.title,
                    "fuente": "Google News",
                    "submodulo": "GOOGLE_SEARCH",
                    "url": entry.link,
                    "canal_origen": "N/A"
                })
        except Exception as e:
            print(f"    [!] Error buscando '{query}' en Google News: {e}")
            
    return noticias_capturadas

if __name__ == "__main__":
    # Test rápido
    test_busqueda = [
        {'ticker': '9999', 'filtro': 'inflacion argentina indec'},
        {'ticker': 'GGAL', 'filtro': 'Galicia ADR'}
    ]
    res = capturar_google_news(test_busqueda)
    print(f"Capturadas {len(res)} noticias de prueba.")
    for r in res:
        print(f" - [{r['ticker']}] {r['titular']}")