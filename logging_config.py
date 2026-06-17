import logging


class SheetsHandler(logging.Handler):
    """Logging handler that writes formatted messages to the Google Sheets log via `procesamiento.registrar_log`.

    The handler stores a reference to a worksheet and will append rows when emitting records.
    The worksheet can be set later via `set_ws` to allow lazy initialization.
    """

    def __init__(self, ws=None):
        super().__init__()
        self.ws = ws

    def set_ws(self, ws):
        self.ws = ws

    def emit(self, record):
        if self.ws is None:
            return
        try:
            import procesamiento
            msg = self.format(record)
            nivel = record.levelname
            # Use procesamiento.registrar_log to keep behaviour consistent
            procesamiento.registrar_log(self.ws, nivel, msg)
        except Exception:
            # Avoid raising from logging; record handler failures to the root logger
            try:
                logging.getLogger('inversiones').error(f"LOG_HANDLER ERROR: failed to write log for record: {record}")
            except Exception:
                pass


def setup_logging(ws_log=None, level=logging.INFO, sheets_level=logging.WARNING):
    """Configure a central logger for the application.

    - Adds a console handler and a SheetsHandler that writes to `ws_log` if provided.
    - Safe to call multiple times; won't duplicate handlers.
    """
    logger = logging.getLogger('inversiones')
    logger.setLevel(level)

    # Add console handler if not present
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(ch)

    # Add SheetsHandler if not present
    sheet_handler = None
    for h in logger.handlers:
        if isinstance(h, SheetsHandler):
            sheet_handler = h
            break

    if sheet_handler is None:
        sheet_handler = SheetsHandler(ws=ws_log)
        sheet_handler.setLevel(sheets_level)
        sheet_handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(sheet_handler)
    else:
        # Update worksheet if provided
        if ws_log is not None:
            sheet_handler.set_ws(ws_log)

    return logger


def get_logger(name=None):
    base = logging.getLogger('inversiones')
    if name:
        return base.getChild(name)
    return base


if __name__ == "__main__":
    # Prueba local para verificar que el logger funciona correctamente
    test_logger = setup_logging()
    test_logger.info("Módulo logging_config cargado y funcionando correctamente.")
    print("Prueba de logger finalizada (revisa la línea de arriba).")
