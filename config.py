"""
Archivo central de constantes y configuraciones.
Almacena credenciales, nombres de hojas de Google Sheets y parámetros globales de los procesos,
cumpliendo con la regla de centralización para evitar 'strings quemados' en el código.
"""
# --- CONFIGURACIÓN DE ACCESO ---
API_KEY_FILE = 'creds/api_key.txt'
JSON_FILE = 'creds/python-sheets-492415-9f916d7c2cd1.json' 
# Usamos el nombre para gspread, pero recuerda que el ID es más seguro
SHEET_NAME = 'Inversiones' 
DIR_ESTRATEGIA = "ESTRATEGIA_REPORTS"

# --- CREDENCIALES TELEGRAM ---
TELEGRAM_API_ID = 35776966          # Reemplaza por tu número sin comillas
TELEGRAM_API_HASH = 'd9ce01e2387a11fac12913d6ef14a7a6'  # Reemplaza por tu hash entre comillas
WS_CONFIG_TELEGRAM_CHANNELS = "CONFIG_TELEGRAM_CHANNELS"

# --- PARÁMETROS DEL PROCESO ---
UMBRAL_ANOMALIA = 0.05  # 5% de desvío máximo permitido
# --- IDENTIFICADORES DE PROCESOS ---
ORIGEN_LOG = "sistema_general"         # Por si algo falla
ORIGEN_LOG_CARGA = "carga_fuentes"      # Para el script de precios
ORIGEN_LOG_TECNICO = "analisis_tecnico" # Para este nuevo script

# --- NOMBRES DE LAS HOJAS  estas son para carga fuentes 
WS_CONFIG_FUENTES = "CONFIG_FUENTES"
WS_VARIABLES_MERCADO = "VARIABLES_MERCADO"
WS_LOG_SISTEMA = "LOG_SISTEMA"
WS_ESTADO_PROCESOS = "ESTADO_PROCESOS"
WS_HISTORICO_VALORES = "HISTORICO_VALORES"
WS_ANALISIS_TECNICO = "ANALISIS_TECNICO"

# --- CONFIGURACIÓN TÉCNICA ---
PERIODO_FIBO = 30
MIN_DIAS_HISTORIAL = 200
ORIGEN_LOG_TECNICO = "analisis_tecnico"
CHUNK_SIZE_SHEETS = 1000 # Para operaciones de escritura masiva en Sheets
DIAS_KEEP_REPORTE_IA = 100 # Días de historial a conservar en REPORTE_IA
DIAS_KEEP_LOG = 100 # Días de historial a conservar en LOG_SISTEMA
UMBRAL_FILAS_LOG = 1000   # Solo limpia si supera estas filas o es el primer run del día
UMBRAL_FILAS_REPORTE = 500

# --- CONFIGURACIÓN DE RETENCIÓN Y BORRADO DE NOTICIAS/SUGERENCIAS ---
DIAS_KEEP_NOTICIAS_DESCARTADAS = 30
DIAS_KEEP_SUGERENCIAS_SINONIMOS = 30
UMBRAL_FILAS_NOTICIAS_DESCARTADAS = 500
UMBRAL_FILAS_SUGERENCIAS_SINONIMOS = 100
UMBRAL_FILAS_BORRAR_MINIMO = 50  # Mínimo de filas eliminadas requerido para disparar escritura en Sheets


# --- HOJAS PARA ANÁLISIS ---
WS_MAESTRO_ACTIVOS = "MAESTRO_ACTIVOS"
WS_DOWNLOAD_BUFFER = "DOWNLOAD_BUFFER"

# --- HOJAS PARA IA ---
WS_CONFIG_IA_USUARIO = "CONFIG_IA_USUARIO"
WS_CONFIG_IA_GENERAL = "CONFIG_IA_GENERAL"
WS_REPORTE_IA = "REPORTE_IA"
WS_MATRIZ_RECOMENDACIONES = "MATRIZ_RECOMENDACIONES"
WS_NOTICIAS_SISTEMA = "NOTICIAS_SISTEMA"
WS_NOTICIAS_DESCARTADAS = "NOTICIAS_DESCARTADAS"
WS_CONFIG_SINONIMOS = "CONFIG_SINONIMOS"
WS_SUGERENCIAS_SINONIMOS = "SUGERENCIAS_SINONIMOS"
WS_TRANSACCIONES = "TRANSACCIONES"
WS_CAJA_LIQUIDEZ = "CAJA_LIQUIDEZ"
