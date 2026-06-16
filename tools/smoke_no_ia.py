#!/usr/bin/env python3
"""Smoke test ligero sin ejecutar la IA.

Comprueba:
- Conexión a Google Sheets usando `auth_google.conectar()`.
- Presencia de las hojas críticas indicadas en `config.py`.

Salida:
- Código 0: OK
- Código 2: No se pudo conectar a Sheets
- Código 3: Faltan pestañas críticas
"""
import sys
import config
import auth_google
import logging_config

logger = logging_config.get_logger(__name__)

def main():
    sh = auth_google.conectar()
    if not sh:
        logger.error("No se pudo conectar a Google Sheets.")
        sys.exit(2)

    try:
        missing = auth_google.validar_hojas_requeridas(sh)
    except Exception as e:
        logger.exception(f"no se pudo validar hojas requeridas: {e}")
        sys.exit(2)

    if missing:
        logger.error(f"MISSING SHEETS: {missing}")
        sys.exit(3)

    logger.info("SMOKE OK: Conexión a Sheets y pestañas críticas presentes.")
    sys.exit(0)

if __name__ == '__main__':
    main()
