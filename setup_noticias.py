"""
Script inicial para la creación de las tablas de noticias.
Ejecutar una sola vez para preparar la estructura en Google Sheets.
"""
import auth_google
import config
import logging_config

logger = logging_config.get_logger(__name__)

def crear_tablas_noticias():
    logger.info("--- Iniciando creación de tablas de noticias ---")
    sh = auth_google.conectar()
    if not sh:
        logger.error("No se pudo conectar a Google Sheets.")
        return

    # Definición de estructuras según ESTRUCTURA_SHEETS.md
    TABLAS = {
        config.WS_NOTICIAS_SISTEMA: [
            "FECHA", "TICKER_ID", "TITULAR", "FUENTE", 
            "SUBMODULO", "URL", "CANAL_ORIGEN", "RESUMEN_IA", "SENTIMIENTO"
        ],
        config.WS_NOTICIAS_DESCARTADAS: [
            "FECHA", "TICKER_ID", "TITULAR", "MOTIVO_DESCARTE", "SUBMODULO"
        ],
        config.WS_SUGERENCIAS_SINONIMOS: [
            "FECHA", "TITULAR", "TERMINO_SUGERIDO", "TICKER_SUGERIDO", "EXPLICACION"
        ],
        config.WS_CONFIG_SINONIMOS: [
            "TERMINO", "TICKER_ASOCIADO"
        ],
        config.WS_CONFIG_TELEGRAM_CHANNELS: [
            "CANAL", "ESTADO"
        ]
    }

    for nombre_hoja, encabezados in TABLAS.items():
        try:
            # Intentar abrir la hoja
            sh.worksheet(nombre_hoja)
            logger.info(f"La hoja '{nombre_hoja}' ya existe.")
        except:
            # Si falla, la creamos
            logger.info(f"Creando hoja '{nombre_hoja}'...")
            nueva_hoja = sh.add_worksheet(title=nombre_hoja, rows="1000", cols=len(encabezados))
            nueva_hoja.append_row(encabezados)
            logger.info(f"Encabezados creados para {nombre_hoja}")

    # Verificación adicional de la columna en CONFIG_IA_GENERAL
    try:
        ws_config = sh.worksheet(config.WS_CONFIG_IA_GENERAL)
        headers = ws_config.row_values(1)
        if "Prompt_Triage_Noticias" not in headers:
            logger.warning("Aviso: Recuerda que 'CONFIG_IA_GENERAL' debe tener la columna 'Prompt_Triage_Noticias'.")
        else:
            logger.info("CONFIG_IA_GENERAL ya tiene la columna de Prompt de Triage.")
    except Exception as e:
        logger.exception(f"Error verificando CONFIG_IA_GENERAL: {e}")

    logger.info("--- Proceso finalizado con éxito ---")

if __name__ == "__main__":
    crear_tablas_noticias()