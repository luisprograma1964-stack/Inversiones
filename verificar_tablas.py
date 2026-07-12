# --------------------------------------------------------------
# verificar_tablas.py
# --------------------------------------------------------------
"""
Verificación de integridad para todas las hojas de Google Sheets
definidas en `config.py`.

- Duplicados (según claves típicas)
- Fechas con formato ISO (YYYY‑MM‑DD)
- Valores numéricos negativos inesperados
- Posibles problemas de decimales (coma vs. punto)
- Genera un log resumido en `verificacion_tablas.log`
"""

import os
import pandas as pd
import logging
from datetime import datetime

import auth_google
import config

# ------------------------------------------------------------------
# Configurar logger
log_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "verificacion_tablas.log")
logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Definir las hojas que queremos inspeccionar (excluimos backups)
HOJAS = {
    "CONFIG_FUENTES": config.WS_CONFIG_FUENTES,
    "VARIABLES_MERCADO": config.WS_VARIABLES_MERCADO,
    "LOG_SISTEMA": config.WS_LOG_SISTEMA,
    "ESTADO_PROCESOS": config.WS_ESTADO_PROCESOS,
    "HISTORICO_VALORES": config.WS_HISTORICO_VALORES,
    "ANALISIS_TECNICO": config.WS_ANALISIS_TECNICO,
    "MAESTRO_ACTIVOS": config.WS_MAESTRO_ACTIVOS,
    "DOWNLOAD_BUFFER": config.WS_DOWNLOAD_BUFFER,
    "CONFIG_IA_USUARIO": config.WS_CARTERAS,
    "CONFIG_IA_GENERAL": config.WS_CONFIG_IA_GENERAL,

    "MATRIZ_RECOMENDACIONES": config.WS_MATRIZ_RECOMENDACIONES,
}

# ------------------------------------------------------------------
def conectar():
    sh = auth_google.conectar()
    if not sh:
        log.error("No se pudo conectar a Google Sheets.")
        raise RuntimeError("Conexión a Sheets falló.")
    return sh


def validar_fecha(series: pd.Series) -> pd.Series:
    """Devuelve una serie booleana: True si la fecha está en formato ISO."""
    def es_iso(val):
        if pd.isnull(val):
            return False
        try:
            datetime.strptime(str(val).strip(), "%Y-%m-%d")
            return True
        except Exception:
            return False
    return series.apply(es_iso)


def revisar_hoja(sh, nombre_hoja: str):
    log.info(f"--- Revisando hoja: {nombre_hoja} ---")
    datos = sh.worksheet(nombre_hoja).get_all_records(value_render_option="UNFORMATTED_VALUE")
    df = pd.DataFrame(datos)
    total = len(df)
    log.info(f"Total de registros: {total}")

    # ---------- Duplicados ----------
    claves_posibles = [
        ["Ticker_ID", "Fecha"],
        ["Ticker_ID"],
        ["Fecha"],
        [df.columns[0]],  # fallback a la primera columna
    ]
    clave = None
    for cand in claves_posibles:
        if all(col in df.columns for col in cand):
            clave = cand
            break
    if clave:
        dup = df.duplicated(subset=clave).sum()
        log.info(f"Duplicados (clave {clave}): {dup}")
    else:
        dup = 0
        log.info("No se encontró una columna clara de clave para detectar duplicados.")

    # ---------- Fechas ----------
    if "Fecha" in df.columns:
        ok_fechas = validar_fecha(df["Fecha"]).sum()
        inv_fechas = total - ok_fechas
        log.info(f"Fechas válidas: {ok_fechas} | Inválidas: {inv_fechas}")
    else:
        log.info("Columna 'Fecha' no presente en esta hoja.")

    # ---------- Números negativos ----------
    columnas_num = [c for c in df.columns if any(tok in c.lower() for tok in ["precio", "volumen", "maximo", "minimo", "cantidad", "valor"])]
    negativos = {}
    for col in columnas_num:
        if pd.api.types.is_numeric_dtype(df[col]):
            neg = (df[col] < 0).sum()
            if neg:
                negativos[col] = int(neg)
    if negativos:
        for col, cnt in negativos.items():
            log.info(f"Valores negativos en {col}: {cnt}")
    else:
        log.info("No se detectaron valores numéricos negativos.")

    # ---------- Decimales con coma ----------
    def contiene_coma(val):
        if isinstance(val, str):
            return ("," in val) and any(ch.isdigit() for ch in val)
        return False

    columnas_str = [c for c in df.columns if df[c].dtype == object]
    coma_problemas = {}
    for col in columnas_str:
        cnt = df[col].apply(contiene_coma).sum()
        if cnt:
            coma_problemas[col] = int(cnt)
    if coma_problemas:
        for col, cnt in coma_problemas.items():
            log.info(f"Posibles decimales mal formateados (coma) en {col}: {cnt}")
    else:
        log.info("No se encontraron comas dentro de campos de texto numéricos.")

    log.info(f"--- Fin de revisión: {nombre_hoja} ---\n")


def main():
    sh = conectar()
    missing = auth_google.validar_hojas_requeridas(sh)
    if missing:
        log.error(f"Faltan hojas requeridas: {missing}")
        raise RuntimeError(f"Faltan hojas requeridas: {missing}")

    for alias, nombre in HOJAS.items():
        try:
            revisar_hoja(sh, nombre)
        except Exception as e:
            log.error(f"Error al revisar {nombre}: {e}")

    log.info("✅ Verificación completada. Revisa `verificacion_tablas.log` para el detalle.")


if __name__ == "__main__":
    main()
