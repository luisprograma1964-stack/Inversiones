# Plan de Implementación: Módulo de Noticias (Arquitectura Modular)

Este documento define la arquitectura para capturar, procesar y almacenar noticias relevantes por activo y de contexto macroeconómico (Ticker 9999).

## 1. Objetivo
Enriquecer el análisis del Motor de IA con contexto fundamental y macro, separando la captura en sub-módulos según la fuente para garantizar estabilidad y escalabilidad.

## 2. Gestión de Calidad y Auditoría
Para garantizar la relevancia de la información, se implementan dos mecanismos:
1. **Tabla de Descartes:** Toda noticia que la IA considere irrelevante o clickbait se moverá a `NOTICIAS_DESCARTADAS` con su motivo.
2. **Prompts Dinámicos:** El prompt de filtrado (Triage) se lee desde `CONFIG_IA_GENERAL[Prompt_Triage_Noticias]`.

## 3. Arquitectura del Código (Evolucionada)
El proceso se dividirá en un orquestador y cinco sub-módulos especializados:

### A. Orquestador: `captura_noticias.py`
- Lee los Tickers activos del `MAESTRO_ACTIVOS`.
- Llama a los sub-módulos y recolecta los resultados.
- **Deduplicación:** Verifica que la URL no exista ya en la tabla para evitar duplicados.
- **Triage con IA:** Usa el prompt de la tabla de configuración. 
- **Distribución:** Envía noticias aprobadas a `NOTICIAS_SISTEMA` y rechazadas a `NOTICIAS_DESCARTADAS`.

### B. Sub-módulo RSS: `news_rss.py`
- **Librería:** `feedparser`.
- **Fuentes:** Reuters (Business), CNBC (Finance), Ámbito Financiero.
- **Uso:** Ideal para noticias rápidas y generales.

### C. Sub-módulo News API: `news_api.py`
- **Librería:** `requests`.
- **Fuentes:** `NewsAPI.org` o `CryptoPanic`.
- **Uso:** Búsqueda específica por palabras clave (ej: "AL30", "FED", "Inflation").

### D. Sub-módulo Search: `news_google.py`
- **Librería:** `pygooglenews` o scraping RSS de Google News.
- **Uso:** Captura de noticias locales muy específicas usando el campo `FILTRO_NOTICIAS` del maestro.

### E. Sub-módulo Telegram: `news_telegram.py`
- **Librería:** `Telethon` o `Pyrogram` (User-Client).
- **Uso:** Monitoreo de canales específicos de finanzas.
- **Meta-información:** Registra obligatoriamente el nombre del canal en la columna `CANAL_ORIGEN`.

### F. Sub-módulo Scraping: `news_scraping.py`
- **Librería:** `BeautifulSoup`, `requests`.
- **Uso:** Explorar secciones de "Lo más leído" o "Análisis" en portales financieros (Investing, Ámbito, Cronista).
- **Objetivo:** Descubrir noticias no convencionales, tendencias incipientes o activos mencionados en columnas de opinión que no poseen feeds estructurados.

## 4. El Caso Especial: Ticker 9999 (Macro Context)
Este ticker no representa un activo, sino el "clima" del mercado. Se activará siempre con palabras clave fijas:
- **Internacional:** "FED interest rates", "US Inflation", "Geopolitics".
- **Local (Argentina):** "BCRA tasas", "IPC INDEC", "Acuerdo FMI", "Riesgo País".

## 5. Lógica de IA: El Filtro de Relevancia
El prompt de Triage debe solicitar a la IA una respuesta estructurada (JSON preferentemente) que incluya:
`{ "estado": "APROBADO/RECHAZADO", "resumen": "...", "sentimiento": "...", "motivo_descarte": "..." }`

## 6. Integración con el Motor de IA (Decisor)
En el Paso 4 del pipeline (`decisor_con_ia.py`), se modificará la carga de datos para incluir:
1. **News del Ticker:** Las 3 noticias más recientes del activo analizado.
2. **News 9999:** Las 3 noticias macro más recientes.
3. **Inyección al JSON:**
```json
"contexto_noticias": {
    "especificas": [{"titular": "...", "resumen": "...", "sentimiento": "..."}],
    "macro_9999": [{"titular": "...", "resumen": "..."}]
}
```

## 7. Estándares y Robustez
- **Manejo de Errores:** Si un sub-módulo falla (ej. NewsAPI sin cuota), el orquestador debe continuar con el resto (no detiene el pipeline).
- **Tiempos de Ejecución:** Cada sub-módulo registrará su duración.
- **Frecuencia:** Se recomienda correr este módulo **antes** del `decisor_con_ia.py` pero de forma independiente al inicio para testear.

## 8. Próximos Pasos [COMPLETADO]
1. [x] Crear la hoja `NOTICIAS_SISTEMA` en el Spreadsheet.
2. [x] Desarrollar `news_rss.py` como primer sub-módulo (es el más estable).
3. [x] Desarrollar el orquestador `captura_noticias.py` con integración a Gemini Flash.

## 9. El Caso Especial: Ticker 9999
Se define el Ticker `9999` como el contenedor de noticias que afectan a toda la cartera:
- Decisiones del BCRA (Tasas).
- Datos de Inflación (IPC).
- Acuerdos con el FMI.
- Riesgo País.
Esto permite que la IA sepa que, aunque una acción tenga un RSI excelente, el contexto macro puede sugerir cautela.