"""
Módulo centralizado de conexión a la API de Google Sheets.
Garantiza que todos los scripts utilicen el mismo método autenticado y
apunta a la planilla principal definida en config.py.
"""
import gspread
import config
import logging_config

logger = logging_config.get_logger(__name__)

def conectar():
    """
    Establece la conexión con la API de Google Sheets utilizando credenciales de cuenta de servicio.
    
    Lee el archivo JSON de credenciales y el nombre del documento definidos en el
    archivo de configuración (config.py).
    
    Retorna:
        gspread.Spreadsheet: Objeto que representa el documento completo (Spreadsheet), 
                             del cual luego se pueden extraer las distintas hojas de cálculo.
        None: Si ocurre un error durante el proceso de autenticación o conexión.
    """
    try:
        gc = gspread.service_account(filename=config.JSON_FILE)
        sh = gc.open(config.SHEET_NAME)
        return sh
    except Exception as e:
        logger.exception(f"Error crítico de conexión: {e}")
        return None


REQUIRED_SHEETS = [
    config.WS_CONFIG_FUENTES,
    config.WS_VARIABLES_MERCADO,
    config.WS_LOG_SISTEMA,
    config.WS_ESTADO_PROCESOS,
    config.WS_HISTORICO_VALORES,
    config.WS_ANALISIS_TECNICO,
    config.WS_MAESTRO_ACTIVOS,
    config.WS_DOWNLOAD_BUFFER,
    config.WS_CONFIG_IA_USUARIO,
    config.WS_CONFIG_IA_GENERAL,
    config.WS_REPORTE_IA,
    config.WS_MATRIZ_RECOMENDACIONES,
    config.WS_NOTICIAS_SISTEMA,
    config.WS_NOTICIAS_DESCARTADAS,
    config.WS_CONFIG_SINONIMOS,
    config.WS_SUGERENCIAS_SINONIMOS,
    config.WS_TRANSACCIONES,
    config.WS_CAJA_LIQUIDEZ,
]


def validar_hojas_requeridas(sh=None, required_sheets=None):
    """Valida que la planilla tenga todas las hojas requeridas definidas en config."""
    if sh is None:
        sh = conectar()
        if not sh:
            raise RuntimeError("No se pudo conectar a Google Sheets para validar las hojas requeridas.")

    if required_sheets is None:
        required_sheets = REQUIRED_SHEETS

    existing = {worksheet.title for worksheet in sh.worksheets()}
    missing = [name for name in required_sheets if name not in existing]
    return missing