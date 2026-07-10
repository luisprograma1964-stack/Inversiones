"""
Archivo central de constantes y configuraciones.
Lee valores sensibles desde variables de entorno para evitar poner secretos en el repo.
Si existe, `python-dotenv` cargará automáticamente un archivo `.env` local.
"""
import os
from pathlib import Path

# Intentamos cargar .env opcionalmente (no es obligatorio)
try:
	from dotenv import load_dotenv
	_env_path = Path(__file__).parent / '.env'
	if _env_path.exists():
		load_dotenv(dotenv_path=_env_path, override=True)
	else:
		print(f"--- AVISO: No se encontró el archivo .env en {_env_path} ---")
except Exception as e:
	print(f"--- ERROR: Falló la carga de python-dotenv: {e} ---")

# --- CONFIGURACIÓN DE ACCESO (se recomienda usar GitHub Secrets / Secret Manager) ---
API_KEY_FILE = os.getenv('API_KEY_FILE', 'creds/api_key.txt')
JSON_FILE = os.getenv('JSON_FILE', 'creds/python-sheets-492415-9f916d7c2cd1.json')
# Usamos el nombre para gspread, pero recuerda que el ID es más seguro
SHEET_NAME = os.getenv('SHEET_NAME', 'Inversiones')
DIR_ESTRATEGIA = os.getenv('DIR_ESTRATEGIA', 'ESTRATEGIA_REPORTS')

# --- CREDENCIALES TELEGRAM (NO guardar secrets en el repo) ---
TELEGRAM_API_ID = int(os.getenv('TELEGRAM_API_ID', '0') or '0')
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH', '').strip()
WS_CONFIG_TELEGRAM_CHANNELS = os.getenv('WS_CONFIG_TELEGRAM_CHANNELS', 'CONFIG_TELEGRAM_CHANNELS')

# --- PARÁMETROS DEL PROCESO ---
UMBRAL_ANOMALIA = float(os.getenv('UMBRAL_ANOMALIA', '0.05'))

# --- IDENTIFICADORES DE PROCESOS ---
ORIGEN_LOG = os.getenv('ORIGEN_LOG', 'sistema_general')
ORIGEN_LOG_CARGA = os.getenv('ORIGEN_LOG_CARGA', 'carga_fuentes')
ORIGEN_LOG_TECNICO = os.getenv('ORIGEN_LOG_TECNICO', 'analisis_tecnico')

# --- NOMBRES DE LAS HOJAS (usar preferentemente variables de entorno si se requiere override) ---
WS_CONFIG_FUENTES = os.getenv('WS_CONFIG_FUENTES', 'CONFIG_FUENTES')
WS_VARIABLES_MERCADO = os.getenv('WS_VARIABLES_MERCADO', 'VARIABLES_MERCADO')
WS_LOG_SISTEMA = os.getenv('WS_LOG_SISTEMA', 'LOG_SISTEMA')
WS_ESTADO_PROCESOS = os.getenv('WS_ESTADO_PROCESOS', 'ESTADO_PROCESOS')
WS_HISTORICO_VALORES = os.getenv('WS_HISTORICO_VALORES', 'HISTORICO_VALORES')
WS_ANALISIS_TECNICO = os.getenv('WS_ANALISIS_TECNICO', 'ANALISIS_TECNICO')

# --- CONFIGURACIÓN TÉCNICA ---
PERIODO_FIBO = int(os.getenv('PERIODO_FIBO', '30'))
MIN_DIAS_HISTORIAL = int(os.getenv('MIN_DIAS_HISTORIAL', '200'))
CHUNK_SIZE_SHEETS = int(os.getenv('CHUNK_SIZE_SHEETS', '1000'))
DIAS_KEEP_REPORTE_IA = int(os.getenv('DIAS_KEEP_REPORTE_IA', '100'))
DIAS_KEEP_LOG = int(os.getenv('DIAS_KEEP_LOG', '100'))
UMBRAL_FILAS_LOG = int(os.getenv('UMBRAL_FILAS_LOG', '1000'))
UMBRAL_FILAS_REPORTE = int(os.getenv('UMBRAL_FILAS_REPORTE', '500'))

# --- CONFIGURACIÓN DE RETENCIÓN Y BORRADO DE NOTICIAS/SUGERENCIAS ---
DIAS_KEEP_NOTICIAS_SISTEMA = int(os.getenv('DIAS_KEEP_NOTICIAS_SISTEMA', '30'))
UMBRAL_FILAS_NOTICIAS_SISTEMA = int(os.getenv('UMBRAL_FILAS_NOTICIAS_SISTEMA', '500'))
DIAS_KEEP_NOTICIAS_DESCARTADAS = int(os.getenv('DIAS_KEEP_NOTICIAS_DESCARTADAS', '30'))
DIAS_KEEP_SUGERENCIAS_SINONIMOS = int(os.getenv('DIAS_KEEP_SUGERENCIAS_SINONIMOS', '30'))
UMBRAL_FILAS_NOTICIAS_DESCARTADAS = int(os.getenv('UMBRAL_FILAS_NOTICIAS_DESCARTADAS', '500'))
UMBRAL_FILAS_SUGERENCIAS_SINONIMOS = int(os.getenv('UMBRAL_FILAS_SUGERENCIAS_SINONIMOS', '100'))
UMBRAL_FILAS_BORRAR_MINIMO = int(os.getenv('UMBRAL_FILAS_BORRAR_MINIMO', '50'))


# --- HOJAS PARA ANÁLISIS ---
WS_MAESTRO_ACTIVOS = os.getenv('WS_MAESTRO_ACTIVOS', 'MAESTRO_ACTIVOS')
WS_DOWNLOAD_BUFFER = os.getenv('WS_DOWNLOAD_BUFFER', 'DOWNLOAD_BUFFER')

# Parámetros para lectura/polling del Bridge (GOOGLEFINANCE)
BRIDGE_POLL_INTERVAL_SECONDS = int(os.getenv('BRIDGE_POLL_INTERVAL_SECONDS', '5'))
BRIDGE_POLL_TIMEOUT_SECONDS = int(os.getenv('BRIDGE_POLL_TIMEOUT_SECONDS', '120'))
BRIDGE_MAX_RETRIES = int(os.getenv('BRIDGE_MAX_RETRIES', '2'))

# --- HOJAS PARA IA ---
WS_CONFIG_IA_USUARIO = os.getenv('WS_CONFIG_IA_USUARIO', 'CONFIG_IA_USUARIO')
WS_CONFIG_IA_GENERAL = os.getenv('WS_CONFIG_IA_GENERAL', 'CONFIG_IA_GENERAL')
WS_REPORTE_IA = os.getenv('WS_REPORTE_IA', 'REPORTE_IA')
WS_MATRIZ_RECOMENDACIONES = os.getenv('WS_MATRIZ_RECOMENDACIONES', 'MATRIZ_RECOMENDACIONES')
WS_NOTICIAS_SISTEMA = os.getenv('WS_NOTICIAS_SISTEMA', 'NOTICIAS_SISTEMA')
WS_NOTICIAS_DESCARTADAS = os.getenv('WS_NOTICIAS_DESCARTADAS', 'NOTICIAS_DESCARTADAS')
WS_CONFIG_SINONIMOS = os.getenv('WS_CONFIG_SINONIMOS', 'CONFIG_SINONIMOS')
WS_SUGERENCIAS_SINONIMOS = os.getenv('WS_SUGERENCIAS_SINONIMOS', 'SUGERENCIAS_SINONIMOS')
WS_TRANSACCIONES = os.getenv('WS_TRANSACCIONES', 'TRANSACCIONES')
WS_CAJA_LIQUIDEZ = os.getenv('WS_CAJA_LIQUIDEZ', 'CAJA_LIQUIDEZ')
WS_PROGRAMA_CEDEARS = os.getenv('WS_PROGRAMA_CEDEARS', 'PROGRAMA_CEDEARS')

# --- NUEVAS HOJAS PARA EVOLUCIÓN ---
WS_CONFIG_USUARIOS = os.getenv('WS_CONFIG_USUARIOS', 'CONFIG_USUARIOS')
WS_FEEDBACK_USUARIOS = os.getenv('WS_FEEDBACK_USUARIOS', 'FEEDBACK_USUARIOS')
WS_HISTORIAL_VEREDICTOS = os.getenv('WS_HISTORIAL_VEREDICTOS', 'HISTORIAL_VEREDICTOS')

WS_REPORTE_SUPERVISOR = os.getenv("WS_REPORTE_SUPERVISOR", "REPORTE_SUPERVISOR")
WS_ALERTAS_SUPERVISOR = os.getenv("WS_ALERTAS_SUPERVISOR", "ALERTAS_SUPERVISOR")
