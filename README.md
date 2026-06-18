# Proyecto Inversiones

Sistema automatizado de análisis financiero, captura de noticias y toma de decisiones mediante IA (Gemini).

## 🛠 1. Pre-requisitos del Sistema
Antes de comenzar, asegúrate de tener instalado:
1. **Python 3.10 o superior**: Descargar aquí.
2. **Git**: Opcional, para clonar el repositorio.
3. **Cuenta de Google Cloud**: Con la API de Google Sheets habilitada y una Cuenta de Servicio con su archivo JSON.
4. **Gemini API Key**: Obtenida desde Google AI Studio.
5. **Telegram API ID/Hash**: Obtenidos desde my.telegram.org (para el módulo de noticias).

## 🚀 2. Instalación desde Cero

### Paso 1: Clonar y crear carpetas base
Abre una terminal (PowerShell recomendado) en la carpeta raíz:
```powershell
mkdir creds
mkdir ESTRATEGIA_REPORTS
```

### Paso 2: Configurar el Entorno Virtual
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```
*Nota: Si no tienes el archivo requirements.txt, instala manualmente las críticas:*
`pip install pandas pandas_ta gspread oauth2client google-genai python-dotenv telethon feedparser beautifulsoup4 requests`

### Paso 3: Configurar Credenciales
1. Coloca tu JSON de Google en `creds/` y el archivo `api_key.txt` con tu clave de Gemini.
2. Crea un archivo `.env` en la raíz con este formato:
```env
API_KEY_FILE=creds/api_key.txt
JSON_FILE=creds/tu_archivo_google.json
SHEET_NAME=Inversiones
TELEGRAM_API_ID=1234567
TELEGRAM_API_HASH=tu_hash_aqui
```

## 📈 3. Flujo de Ejecución
El sistema se opera mediante dos procesos principales en este orden:

### Etapa 1: El Ensamblador
Prepara todos los datos técnicos, financieros y noticias. Es el "cerebro operativo".
```powershell
python ensamblador.py
```
**¿Qué hace?**
- Verifica modelos de IA.
- Descarga precios y variables macro (Dólar, UVA).
- Calcula indicadores (RSI, MACD, Fibonacci).
- Captura y filtra noticias de Telegram/Web.
- Genera el veredicto inicial basado en tu liquidez y tenencias.

### Etapa 2: El Supervisor del Sistema
Audita el trabajo del ensamblador y sugiere mejoras de calidad.
```powershell
python supervisor_del_sistema.py
```
**¿Qué hace?**
- Detecta si la IA contradijo la tendencia técnica.
- Sugiere nuevos sinónimos para el mapeo de noticias.
- Identifica si hay desincronización de precios.

## ⚠️ Seguridad y Mantenimiento
- **NO SUBIR** las carpetas `.venv/`, `creds/` ni el archivo `.env` a GitHub.
- Si el pipeline falla con error de Telegram, verifica que el `TELEGRAM_API_ID` en el `.env` sea un número sin comillas.
- Puedes usar `python tools/diagnostico_sistema.py` para verificar que todo esté bien configurado.

---
*Mantenimiento: `master` y `main` son equivalentes, pero este proyecto utiliza **main** por defecto.*
