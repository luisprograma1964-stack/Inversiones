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
    Con reintentos resilientes ante cuotas 429 de Google Sheets.
    """
    import time
    for intento in range(8):
        try:
            gc = gspread.service_account(filename=config.JSON_FILE)
            sh = gc.open(config.SHEET_NAME)
            return sh
        except Exception as e:
            if "429" in str(e) and intento < 7:
                delay = 15
                logger.warning(f"    [!] Cuota 429 al abrir Spreadsheet '{config.SHEET_NAME}'. Reintentando en {delay}s (Intento {intento+1}/8)...")
                time.sleep(delay)
                continue
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
    config.WS_PROGRAMA_CEDEARS,
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


# --- MONKEY PATCH PARA RESILIENCIA ANTE ERRORES 429 EN GSPREAD ---
def _hacer_resiliente_gspread():
    import time
    
    def robust_decorator(method, max_retries=8, initial_delay=15):
        def wrapper(*args, **kwargs):
            for intento in range(max_retries):
                try:
                    return method(*args, **kwargs)
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str and intento < max_retries - 1:
                        delay = initial_delay + 3 * intento
                        print(f"    [!] gspread 429 detectado al ejecutar '{method.__name__}'. Reintentando en {delay}s (Intento {intento+1}/{max_retries})...")
                        time.sleep(delay)
                        continue
                    raise e
        # Mantener metadatos del método original
        wrapper.__name__ = method.__name__
        wrapper.__doc__ = method.__doc__
        return wrapper

    # Decorar Spreadsheet
    gspread.Spreadsheet.worksheet = robust_decorator(gspread.Spreadsheet.worksheet)
    gspread.Spreadsheet.worksheets = robust_decorator(gspread.Spreadsheet.worksheets)

    # Decorar Worksheet (lecturas y escrituras comunes)
    gspread.Worksheet.get_all_values = robust_decorator(gspread.Worksheet.get_all_values)
    gspread.Worksheet.get_all_records = robust_decorator(gspread.Worksheet.get_all_records)
    gspread.Worksheet.update = robust_decorator(gspread.Worksheet.update)
    gspread.Worksheet.update_cell = robust_decorator(gspread.Worksheet.update_cell)
    gspread.Worksheet.update_cells = robust_decorator(gspread.Worksheet.update_cells)
    gspread.Worksheet.append_row = robust_decorator(gspread.Worksheet.append_row)
    gspread.Worksheet.append_rows = robust_decorator(gspread.Worksheet.append_rows)
    gspread.Worksheet.clear = robust_decorator(gspread.Worksheet.clear)
    gspread.Worksheet.get = robust_decorator(gspread.Worksheet.get)

# Ejecutar el parche al importar el módulo
try:
    _hacer_resiliente_gspread()
except Exception as patch_err:
    print(f"    [!] Error al aplicar monkey patch de resiliencia gspread: {patch_err}")