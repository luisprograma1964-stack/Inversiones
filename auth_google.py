"""
Módulo centralizado de conexión a la API de Google Sheets.
Garantiza que todos los scripts utilicen el mismo método autenticado y
apunta a la planilla principal definida en config.py.
"""
import gspread
import config

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
        print(f"Error crítico de conexión: {e}")
        return None