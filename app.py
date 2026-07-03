import streamlit as st
import sys
import os
import subprocess
import threading
import time
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Agregar la ruta absoluta al path para importar módulos locales
WORKSPACE_DIR = "C:\\Para mi\\Inversiones"
if WORKSPACE_DIR not in sys.path:
    sys.path.append(WORKSPACE_DIR)

import auth_google
import config

# Crear carpeta de logs si no existe
LOGS_DIR = Path(WORKSPACE_DIR) / "logs"
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE_PATH = LOGS_DIR / "ejecucion_actual.log"

# Configuración de página de Streamlit (Estética Premium)
st.set_page_config(
    page_title="Inversiones - Panel de Control Inteligente",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Premium para agrandar las letras del Sidebar y Monitor de Divisas
st.markdown("""
<style>
    /* Agrandar texto general del sidebar */
    [data-testid="stSidebar"] {
        font-size: 15px !important;
    }
    [data-testid="stSidebar"] h3 {
        font-size: 19px !important;
        font-weight: bold !important;
    }
    [data-testid="stSidebar"] p {
        font-size: 14px !important;
    }
    /* Agrandar botones del sidebar */
    [data-testid="stSidebar"] button p {
        font-size: 14px !important;
        font-weight: 500 !important;
    }
    /* Reducir margen superior de la barra lateral */
    [data-testid="stSidebarUserContent"] {
        padding-top: 15px !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 1. ESTADO GLOBAL PERSISTENTE (Seguro por Hilos) ---
@st.cache_resource
def obtener_estado_global():
    return {"activo": None, "objeto": None, "status": "Libre"}

estado_global = obtener_estado_global()

if estado_global["objeto"] is not None:
    exit_code = estado_global["objeto"].poll()
    if exit_code is not None:
        estado_global["activo"] = None
        estado_global["objeto"] = None
        if exit_code == 0:
            estado_global["status"] = "Finalizado con éxito"
        else:
            estado_global["status"] = f"Error en Último Proceso (Código {exit_code})"
        
        # Limpiar caché de datos para ver los resultados calculados por el proceso finalizado
        st.cache_data.clear()

# Inicialización de banderas de ejecución locales de sesión
if "ejecutar_script" not in st.session_state:
    st.session_state["ejecutar_script"] = None

# --- 2. TEMA VISUAL NÓRDICO FIJO ---
st.markdown("""
    <style>
    .stApp {
        background-color: #F0F4F8;
        color: #1A365D;
        font-family: 'Inter', sans-serif;
    }
    div[data-testid="stMetricValue"] {
        color: #1E3A8A;
        font-size: 2rem;
        font-weight: bold;
    }
    .stButton>button {
        background-color: #E2EBF4;
        color: #1A365D;
        font-size: 1.05rem;
        border-radius: 8px;
        border: 2px solid #BFDBFE;
        font-weight: 800;
        width: 100%;
    }
    /* Estilos para pestañas superiores más grandes y gruesas */
    button[data-testid="stBaseButton-tab"] p, div[data-testid="stTabBar"] button p {
        font-size: 1.45rem !important;
        font-weight: 800 !important;
        color: #1A365D !important;
    }
    /* Límites definidos de selectbox (combo box) para mejorar la visibilidad */
    div[data-baseweb="select"] {
        border: 1.5px solid #4b5563 !important; /* Borde gris medio oscuro bien visible */
        border-radius: 6px;
        background-color: #ffffff !important;
    }
    </style>
""", unsafe_allow_html=True)

# Cargar conexión para caché inicial
def obtener_conexion_sheets():
    try:
        return auth_google.conectar()
    except:
        return None

# Diccionario global de activos para mostrar descripciones amigables
@st.cache_data
def obtener_diccionario_activos():
    sh = obtener_conexion_sheets()
    dicc = {}
    if sh:
        try:
            ws = sh.worksheet("MAESTRO_ACTIVOS")
            raw = ws.get_all_records()
            for r in raw:
                tk = str(r.get('TICKER_ID', '')).strip().upper()
                nombre = str(r.get('NOMBRE', r.get('DESCRIPCION', ''))).strip()
                if tk:
                    dicc[tk] = nombre
        except:
            pass
    return dicc

def formatear_ticker(ticker, dict_activos):
    if ticker == "Todos" or ticker == "Todos los Activos":
        return ticker
    # Extraer ticker en caso de que venga con Byma
    tk_clean = str(ticker).replace("BCBA:", "").strip().upper()
    nombre = dict_activos.get(tk_clean, "")
    return f"{ticker} ({nombre})" if nombre else ticker

# --- 3. LÓGICA DE EJECUCIÓN ASINCRÓNICA SEGUNDO PLANO ---
def target_ejecucion(script_name, log_path, global_ref):
    python_exe = os.path.join(WORKSPACE_DIR, ".venv", "Scripts", "python.exe")
    target_script = os.path.join(WORKSPACE_DIR, script_name)
    
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"--- INICIANDO EJECUCIÓN DE: {script_name} ({datetime.now().strftime('%H:%M:%S')}) ---\n\n")
        f.flush()
        
    try:
        proc = subprocess.Popen(
            [python_exe, "-u", target_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=WORKSPACE_DIR
        )
        
        global_ref["objeto"] = proc
        
        for line in proc.stdout:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
            
        proc.wait()
        
        with open(log_path, "a", encoding="utf-8") as f:
            if proc.returncode == 0:
                f.write(f"\n[OK] EJECUCIÓN FINALIZADA EXITOSAMENTE ({datetime.now().strftime('%H:%M:%S')})\n")
            else:
                f.write(f"\n[FAIL] EJECUCIÓN TERMINADA CON ERRORES (Código {proc.returncode} - {datetime.now().strftime('%H:%M:%S')})\n")
            f.flush()
            
    except Exception as e:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\nERROR EJECUTANDO SCRIPT: {e}\n")
            f.flush()

def disparar_proceso_fondo(script_name):
    if estado_global["activo"] is not None:
        return
        
    estado_global["activo"] = script_name
    estado_global["status"] = "Ejecutando de fondo..."
    
    t = threading.Thread(target=target_ejecucion, args=(script_name, str(LOG_FILE_PATH), estado_global))
    t.daemon = True
    t.start()

# --- 4. CARGA DE HOJAS CON CACHÉ (Optimizado a 5 minutos) ---
def obtener_conexion_sheets():
    try:
        sh = auth_google.conectar()
        return sh
    except Exception as e:
        st.error(f"Error conectando a Google Sheets: {e}")
        return None

@st.cache_data(ttl=120)
def cargar_datos_hoja(sheet_name):
    sh = obtener_conexion_sheets()
    if not sh:
        return pd.DataFrame()
    try:
        ws = sh.worksheet(sheet_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        df.columns = [c.strip().upper() for c in df.columns]
        return df
    except Exception as e:
        return pd.DataFrame()

# Cargador específico para la tabla Semáforo
@st.cache_data(ttl=120)
def cargar_datos_semaforo():
    sh = obtener_conexion_sheets()
    if not sh:
        return pd.DataFrame()
    try:
        ws = sh.worksheet(config.WS_ESTADO_PROCESOS)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        df.columns = [c.strip().upper() for c in df.columns]
        return df
    except Exception as e:
        return pd.DataFrame()

@st.cache_data
def cargar_logs_recientes(cantidad=50):
    sh = obtener_conexion_sheets()
    if not sh:
        return pd.DataFrame()
    try:
        ws = sh.worksheet(config.WS_LOG_SISTEMA)
        raw_values = ws.get_all_values()
        if len(raw_values) <= 1:
            return pd.DataFrame()
            
        headers = [str(c).strip().upper() for c in raw_values[0]]
        # Convertir a DataFrame
        df = pd.DataFrame(raw_values[1:], columns=headers)
        
        # Tomar las últimas 'cantidad' filas y darlas vuelta para mostrar las más nuevas arriba
        df_recientes = df.tail(cantidad).iloc[::-1].reset_index(drop=True)
        return df_recientes
    except Exception as e:
        return pd.DataFrame()

# Cargador de parámetros de IA
def obtener_parametros_ia():
    sh = obtener_conexion_sheets()
    if not sh:
        return {}
    try:
        ws = sh.worksheet(config.WS_CONFIG_IA_GENERAL)
        data = ws.get_all_records()
        if data:
            return {k.strip(): v for k, v in data[0].items()}
        return {}
    except Exception as e:
        return {}

# --- 5. BARRA LATERAL (MONITOR DE DIVISAS Y BRECHA CAMBIARIA) ---
def obtener_variables_cambiarias():
    df_mercado = cargar_datos_hoja(config.WS_VARIABLES_MERCADO)
    df_tecnico = cargar_datos_hoja(config.WS_ANALISIS_TECNICO)
    
    mep_c, mep_v = 0.0, 0.0
    blue_c, blue_v = 0.0, 0.0
    cripto_c, cripto_v = 0.0, 0.0
    
    if not df_mercado.empty:
        col_dato = next((c for c in df_mercado.columns if "DATO" in c), "DATO")
        col_compra = next((c for c in df_mercado.columns if "VALOR_COMPRA" in c or "COMPRA" in c), None)
        col_venta = next((c for c in df_mercado.columns if "VALOR_VENTA" in c or "VENTA" in c), None)
        col_prom = next((c for c in df_mercado.columns if "VALOR_PROM" in c or "VALOR" in c), "VALOR_PROM")
        
        col_c = col_compra if col_compra else col_prom
        col_v = col_venta if col_venta else col_prom

        def sanar_escala(val, es_blue=False):
            try:
                clean = float(str(val).replace(',', '.'))
                if clean > 0:
                    if es_blue and clean > 100000: clean /= 100.0
                    elif clean > 10000: clean /= 10.0
                    return clean
            except: pass
            return 0.0

        # MEP
        row_mep = df_mercado[df_mercado[col_dato].astype(str).str.contains('MEP', case=False, na=False)]
        if not row_mep.empty:
            mep_c = sanar_escala(row_mep.iloc[0][col_c])
            mep_v = sanar_escala(row_mep.iloc[0][col_v])
            
        # Blue
        row_blue = df_mercado[df_mercado[col_dato].astype(str).str.contains('Blue', case=False, na=False)]
        if not row_blue.empty:
            blue_c = sanar_escala(row_blue.iloc[0][col_c], es_blue=True)
            blue_v = sanar_escala(row_blue.iloc[0][col_v], es_blue=True)

        # Cripto
        row_cripto = df_mercado[df_mercado[col_dato].astype(str).str.contains('Cripto', case=False, na=False)]
        if not row_cripto.empty:
            cripto_c = sanar_escala(row_cripto.iloc[0][col_c])
            cripto_v = sanar_escala(row_cripto.iloc[0][col_v])

    ccl_vals = []
    if not df_tecnico.empty and 'CCL_IMPLICITO' in df_tecnico.columns:
        for v in df_tecnico['CCL_IMPLICITO']:
            try:
                clean_v = float(str(v).replace(',', '.'))
                if clean_v > 500:
                    if clean_v > 100000: clean_v /= 100.0
                    elif clean_v > 10000: clean_v /= 10.0
                    ccl_vals.append(clean_v)
            except: pass
            
    ccl_prom = sum(ccl_vals) / len(ccl_vals) if ccl_vals else 0.0
    return mep_c, mep_v, blue_c, blue_v, ccl_prom

mep_c, mep_v, blue_c, blue_v, ccl_prom = obtener_variables_cambiarias()
if mep_v > 0 or ccl_prom > 0:
    brecha = ((ccl_prom - mep_v) / mep_v) * 100 if mep_v > 0 and ccl_prom > 0 else 0.0
    
    if brecha > 2.5:
        color_card = "#FF4D4D"
        mensaje_brecha = f"🔴 Brecha Alta (+{brecha:.2f}%)"
        consejo = "Se sugiere evitar compras locales en ARS (Cedears con sobreprecio)."
    elif brecha < 1.5:
        color_card = "#2ECC71"
        mensaje_brecha = f"🟢 Brecha Baja (+{brecha:.2f}%)"
        consejo = "Oportunidad de compra de Cedears en pesos (ARS) por baja brecha."
    else:
        color_card = "#3498DB"
        mensaje_brecha = f"🔵 Brecha Normal (+{brecha:.2f}%)"
        consejo = "Operatoria cambiaria regular en pesos."

    html_card = f"""
    <div style="background-color: #1A1A1A; border-radius: 8px; padding: 14px; border-left: 5px solid {color_card}; margin-bottom: 15px; color: #FFFFFF; font-family: sans-serif; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h4 style="margin: 0 0 12px 0; font-size: 17px; color: #FFFFFF; font-weight: bold; display: flex; align-items: center; gap: 8px;">
            💵 Monitor de Divisas
        </h4>
        <table style="width: 100%; border-collapse: collapse; font-size: 14px; margin-bottom: 8px; text-align: right;">
            <thead>
                <tr style="border-bottom: 1px solid #333333; font-size: 11px; color: #AAAAAA; font-weight: bold; text-transform: uppercase;">
                    <th style="padding: 4px 0; text-align: left; font-weight: bold; color: #AAAAAA;">Divisa</th>
                    <th style="padding: 4px 6px; font-weight: bold; color: #AAAAAA; text-align: right;">Compra</th>
                    <th style="padding: 4px 0; font-weight: bold; color: #AAAAAA; text-align: right;">Venta</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom: 1px solid #222222;">
                    <td style="padding: 6px 0; text-align: left; color: #FFFFFF; font-weight: 500;">Dólar MEP</td>
                    <td style="padding: 6px 6px; font-weight: bold; color: #E0E0E0; text-align: right;">${mep_c:,.2f}</td>
                    <td style="padding: 6px 0; font-weight: bold; color: #E0E0E0; text-align: right;">${mep_v:,.2f}</td>
                </tr>
                <tr style="border-bottom: 1px solid #222222;">
                    <td style="padding: 6px 0; text-align: left; color: #FFFFFF; font-weight: 500;">Dólar Blue</td>
                    <td style="padding: 6px 6px; font-weight: bold; color: #E0E0E0; text-align: right;">${blue_c:,.2f}</td>
                    <td style="padding: 6px 0; font-weight: bold; color: #E0E0E0; text-align: right;">${blue_v:,.2f}</td>
                </tr>
                <tr style="border-bottom: 1px solid #222222;">
                    <td style="padding: 6px 0; text-align: left; color: #FFFFFF; font-weight: 500;">CCL Prom</td>
                    <td style="padding: 6px 6px; color: #888888; font-style: italic; text-align: right;">-</td>
                    <td style="padding: 6px 0; font-weight: bold; color: #E0E0E0; text-align: right;">${ccl_prom:,.2f}</td>
                </tr>
                <tr>
                    <td colspan="3" style="padding: 10px 0 0 0; color: {color_card}; font-weight: bold; font-size: 15px; line-height: 1.2; text-align: left;">{mensaje_brecha}</td>
                </tr>
            </tbody>
        </table>
        <div style="font-size: 12px; color: #CCCCCC; margin-top: 8px; line-height: 1.4; font-style: italic; text-align: left;">
            {consejo}
        </div>
    </div>
    """
    st.sidebar.markdown(html_card, unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.subheader("🚦 Estado del Proceso")

hay_proceso_corriendo = estado_global["activo"] is not None

# Obtener estado de Sheets para el Semáforo de la barra lateral (con caché rápido de 10s)
df_semaforo_side = cargar_datos_semaforo()
estado_sheets = "LIBRE"
detalle_sheets = ""

if not df_semaforo_side.empty:
    # Buscar dinámicamente las columnas del semáforo por aproximación de nombre
    col_proceso = next((c for c in df_semaforo_side.columns if "PROCESO" in c), None)
    col_estado = next((c for c in df_semaforo_side.columns if "ESTADO" in c), None)
    col_detalle = next((c for c in df_semaforo_side.columns if "DETALLE" in c), None)
    
    if col_proceso and col_estado:
        # Filtrar fila de ENSAMBLADOR (insensible a mayúsculas)
        row_ens = df_semaforo_side[df_semaforo_side[col_proceso].astype(str).str.upper() == "ENSAMBLADOR"]
        if not row_ens.empty:
            estado_sheets = str(row_ens.iloc[0][col_estado]).strip().upper()
            if col_detalle:
                detalle_sheets = str(row_ens.iloc[0][col_detalle])
            
            # Buscar columna de fecha/hora de la última corrida
            col_fecha_hora = next((c for c in df_semaforo_side.columns if "CORRIDA" in c or "FECHA" in c or "HORA" in c), None)
            fecha_sheets = ""
            if col_fecha_hora:
                fecha_sheets = str(row_ens.iloc[0][col_fecha_hora]).strip()

# Pintar el semáforo lateral
estado_sheets_upper = estado_sheets.upper()

if hay_proceso_corriendo:
    st.sidebar.warning(f"⚙️ Corriendo de fondo:\n`{estado_global['activo']}`")
elif "ERROR" in estado_sheets_upper or "FAIL" in estado_sheets_upper or "FALL" in estado_sheets_upper:
    st.sidebar.error(f"❌ Error en Pipeline:\n{detalle_sheets[:60]}\n\n⏱️ Última corrida:\n{fecha_sheets}")
elif "CANCEL" in estado_sheets_upper or "ABORT" in estado_sheets_upper:
    st.sidebar.error(f"⚠️ Pipeline Cancelado\n\n⏱️ Última corrida:\n{fecha_sheets}")
elif "COMPLET" in estado_sheets_upper or "OK" in estado_sheets_upper or "EXIT" in estado_sheets_upper or "ÉXIT" in estado_sheets_upper:
    st.sidebar.success(f"✅ Pipeline Completado con Éxito\n\n⏱️ Última corrida:\n{fecha_sheets}")
else:
    st.sidebar.info(f"🟢 Sistema Listo / Libre\n\n⏱️ Última corrida:\n{fecha_sheets}")

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Ejecución Rápida")

if hay_proceso_corriendo:
    # Botón de cancelación de emergencia
    if st.sidebar.button("🛑 Cancelar Proceso Activo", key="cancel_process_btn"):
        if estado_global["objeto"] is not None:
            try:
                estado_global["objeto"].terminate()
                with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
                    f.write(f"\n[STOP] PROCESO CANCELADO POR EL USUARIO DESDE LA WEB ({datetime.now().strftime('%H:%M:%S')})\n")
            except Exception as ex:
                st.sidebar.error(f"Error cancelando proceso: {ex}")
        estado_global["activo"] = None
        estado_global["objeto"] = None
        estado_global["status"] = "Cancelado por usuario"
        st.cache_data.clear()
        st.rerun()

# Deshabilitar botones si algo corre de fondo
if st.sidebar.button("🔄 Ejecutar Ensamblador (Completo)", disabled=hay_proceso_corriendo):
    st.session_state["ejecutar_script"] = "ensamblador.py"

if st.sidebar.button("🔍 Control de Calidad (QA)", disabled=hay_proceso_corriendo):
    st.session_state["ejecutar_script"] = "TEST/homologador.py"

if st.sidebar.button("📋 Correr Supervisor", disabled=hay_proceso_corriendo):
    st.session_state["ejecutar_script"] = "supervisor_del_sistema.py"

st.sidebar.write("---")
if st.sidebar.button("🔄 Refrescar Divisas y Procesos", key="sidebar_global_refresh_btn", help="Actualiza de forma rápida e instantánea el monitor cambiario, los logs y el semáforo de procesos desde Sheets."):
    with st.sidebar.spinner("Refrescando..."):
        cargar_datos_semaforo.clear()
        cargar_logs_recientes.clear()
        time.sleep(0.35)

# Procesar disparos
if st.session_state["ejecutar_script"] is not None:
    script_a_disparar = st.session_state["ejecutar_script"]
    st.session_state["ejecutar_script"] = None
    disparar_proceso_fondo(script_a_disparar)
    st.rerun()

# --- 6. APLICACIÓN PRINCIPAL ---
st.title("📈 Panel de Control de Inversiones con IA")
st.write("---")

# Crear las 7 pestañas principales de la aplicación en el nuevo orden
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📊 Resumen de Cartera", 
    "💸 Operaciones y Caja",
    "🎯 Matriz de Decisiones IA",
    "📋 Reportes del Supervisor", 
    "⚙️ Parámetros de la IA",
    "🛠️ Tablas Paramétricas",
    "💻 Consola de Logs"
])

# ==========================================
# PESTAÑA 1: RESUMEN DE CARTERA
# ==========================================
with tab1:
    st.header("📊 Rentabilidad y Distribución de Cartera")
    
    # Cargar datos
    df_val = cargar_datos_hoja("VALORACION_PORTAFOLIO")
    df_caja = cargar_datos_hoja("CAJA_LIQUIDEZ")
    
    tiene_datos = False
    if not df_val.empty:
        tiene_datos = True
        if "VALOR_ACTUAL" in df_val:
            df_val["VALOR_ACTUAL"] = pd.to_numeric(df_val["VALOR_ACTUAL"].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
        if "RENTABILIDAD_NOMINAL" in df_val:
            df_val["RENTABILIDAD_NOMINAL"] = pd.to_numeric(df_val["RENTABILIDAD_NOMINAL"].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
        if "APORTES_NETOS" in df_val:
            df_val["APORTES_NETOS"] = pd.to_numeric(df_val["APORTES_NETOS"].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
        if "CANTIDAD" in df_val:
            df_val["CANTIDAD"] = pd.to_numeric(df_val["CANTIDAD"].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
            
    if not df_caja.empty:
        tiene_datos = True
        if "SALDO" in df_caja:
            df_caja["SALDO"] = pd.to_numeric(df_caja["SALDO"].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)

    if not tiene_datos:
        st.warning("No se pudieron cargar datos del portafolio o de caja desde Sheets en este momento. Intente presionar 'Refrescar Datos' en la Consola.")
    else:
        # Extraer perfiles/propietarios para filtro
        propietarios_val = df_val["PROPIETARIO"].dropna().unique().tolist() if "PROPIETARIO" in df_val else []
        propietarios_caja = df_caja["PROPIETARIO"].dropna().unique().tolist() if "PROPIETARIO" in df_caja else []
        lista_perfiles = sorted(list(set(propietarios_val + propietarios_caja)))
        
        # Filtro de perfil
        col_f1, col_f2 = st.columns([4, 8])
        with col_f1:
            perfil_sel = st.selectbox(
                "👤 Filtrar Dashboard por Perfil / Propietario:", 
                ["Todos"] + lista_perfiles,
                key="dashboard_profile_select"
            )
            
        # Filtrado de DataFrames según selección
        if perfil_sel == "Todos":
            df_val_filtered = df_val
            df_caja_filtered = df_caja
        else:
            df_val_filtered = df_val[df_val["PROPIETARIO"].astype(str).str.strip().str.upper() == str(perfil_sel).strip().upper()] if not df_val.empty else df_val
            df_caja_filtered = df_caja[df_caja["PROPIETARIO"].astype(str).str.strip().str.upper() == str(perfil_sel).strip().upper()] if not df_caja.empty else df_caja

        # Calcular Métricas
        total_valuacion_cedears = df_val_filtered["VALOR_ACTUAL"].sum() if not df_val_filtered.empty and "VALOR_ACTUAL" in df_val_filtered else 0.0
        total_saldos_caja = df_caja_filtered["SALDO"].sum() if not df_caja_filtered.empty and "SALDO" in df_caja_filtered else 0.0
        patrimonio_neto = total_valuacion_cedears + total_saldos_caja
        
        # Filtrar activos reales para deltas (excluyendo totales de Sheets si hubiese)
        df_real_assets = df_val_filtered[~df_val_filtered["TICKER"].isin(["-TOTAL-", "-CASH-"])] if not df_val_filtered.empty else pd.DataFrame()
        rent_nominal = df_real_assets["RENTABILIDAD_NOMINAL"].sum() if not df_real_assets.empty and "RENTABILIDAD_NOMINAL" in df_real_assets else 0.0
        aportes_netos = df_real_assets["APORTES_NETOS"].sum() if not df_real_assets.empty and "APORTES_NETOS" in df_real_assets else 0.0
        rent_porc = (rent_nominal / aportes_netos * 100) if aportes_netos > 0 else 0.0
        
        liquidez_porc = (total_saldos_caja / patrimonio_neto * 100) if patrimonio_neto > 0 else 0.0
        
        # Tarjetas Métricas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                label=f"Patrimonio Neto ({perfil_sel})", 
                value=f"${patrimonio_neto:,.2f}", 
                delta=f"${rent_nominal:+,.2f} ({rent_porc:+.2f}%)"
            )
        with col2:
            st.metric(
                label=f"Valuación CEDEARs ({perfil_sel})", 
                value=f"${total_valuacion_cedears:,.2f}", 
                delta=f"${rent_nominal:+,.2f} (Ganancia Acum.)"
            )
        with col3:
            st.metric(
                label=f"Efectivo Total Caja ({perfil_sel})", 
                value=f"${total_saldos_caja:,.2f}", 
                delta=f"{liquidez_porc:.1f}% del capital",
                delta_color="normal" if total_saldos_caja > 0 else "off"
            )
        
        st.write("---")
        
        # Gráficos
        g1, g2 = st.columns(2)
        with g1:
            # Gráfico de Torta de distribución
            if not df_val_filtered.empty and "VALOR_ACTUAL" in df_val_filtered and "TICKER" in df_val_filtered:
                # Excluir totales si existieran
                df_pie_data = df_val_filtered[~df_val_filtered["TICKER"].isin(["-TOTAL-", "-CASH-"])]
                if not df_pie_data.empty:
                    st.subheader("Distribución de Cartera por Activo")
                    fig_pie = px.pie(
                        df_pie_data, 
                        values="VALOR_ACTUAL", 
                        names="TICKER", 
                        title=f"Distribución de Cartera ({perfil_sel})",
                        color_discrete_sequence=px.colors.qualitative.Pastel
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("No hay activos individuales para mostrar en el gráfico.")
            else:
                st.info("Gráfico de tenencias no disponible.")
            
        with g2:
            # Gráfico de Barras de rentabilidad
            if not df_val_filtered.empty and "RENTABILIDAD_NOMINAL" in df_val_filtered and "TICKER" in df_val_filtered:
                df_bar_data = df_val_filtered[~df_val_filtered["TICKER"].isin(["-TOTAL-", "-CASH-"])]
                if not df_bar_data.empty:
                    st.subheader("Rentabilidad Real por Ticker")
                    fig_bar = px.bar(
                        df_bar_data,
                        x="TICKER",
                        y="RENTABILIDAD_NOMINAL",
                        title=f"Rentabilidad Nominal en ARS ({perfil_sel})",
                        color="RENTABILIDAD_NOMINAL",
                        color_continuous_scale=px.colors.diverging.RdYlGn
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)
                else:
                    st.info("No hay activos individuales para mostrar en la rentabilidad.")
            else:
                st.info("Gráfico de rentabilidad no disponible.")
                
        # Gráfico extra para "Todos": Distribución por Perfil
        if perfil_sel == "Todos" and not df_val.empty:
            st.write("---")
            col_extra1, col_extra2 = st.columns(2)
            with col_extra1:
                st.subheader("Distribución de Patrimonio por Perfil")
                # Agrupar valoración y caja por Propietario
                df_val_prop = df_val[~df_val["TICKER"].isin(["-TOTAL-", "-CASH-"])].groupby("PROPIETARIO")["VALOR_ACTUAL"].sum().reset_index()
                df_caja_prop = df_caja.groupby("PROPIETARIO")["SALDO"].sum().reset_index()
                
                df_merge = pd.merge(df_val_prop, df_caja_prop, on="PROPIETARIO", how="outer").fillna(0.0)
                df_merge["PATRIMONIO_TOTAL"] = df_merge["VALOR_ACTUAL"] + df_merge["SALDO"]
                
                if not df_merge.empty and df_merge["PATRIMONIO_TOTAL"].sum() > 0:
                    fig_pie_perf = px.pie(
                        df_merge,
                        values="PATRIMONIO_TOTAL",
                        names="PROPIETARIO",
                        title="Distribución del Patrimonio Neto Total",
                        color_discrete_sequence=px.colors.qualitative.Safe
                    )
                    st.plotly_chart(fig_pie_perf, use_container_width=True)
                else:
                    st.info("Datos insuficientes para la distribución por perfiles.")
            with col_extra2:
                st.subheader("Saldos de Caja Líquida")
                if not df_caja.empty:
                    fig_caja_bar = px.bar(
                        df_caja,
                        x="PROPIETARIO",
                        y="SALDO",
                        color="MONEDA",
                        barmode="group",
                        title="Saldos en Efectivo por Perfil y Moneda",
                        color_discrete_sequence=px.colors.qualitative.Dark24
                    )
                    st.plotly_chart(fig_caja_bar, use_container_width=True)
                else:
                    st.info("No hay saldos de caja registrados.")
        
        st.write("---")
        if not df_val_filtered.empty:
            st.subheader(f"Tenencias Consolidadas ({perfil_sel})")
            st.dataframe(df_val_filtered, use_container_width=True)

    # ==========================================
    # SECCIÓN: ANÁLISIS TÉCNICO AVANZADO (CANDLESTICKS & RSI)
    # ==========================================
    st.write("---")
    with st.expander("📈 Visualizador de Trading Premium (Gráfico de Velas, SMA y RSI)", expanded=False):
        st.subheader("📊 Análisis Técnico con Velas Japonesas")
        st.write("Visualiza las cotizaciones históricas diarias descargadas en el sistema con medias móviles y oscilador de fuerza:")
        
        df_maestro_para_velas = cargar_datos_hoja("MAESTRO_ACTIVOS")
        lista_activos_velas = []
        if not df_maestro_para_velas.empty and "TICKER_ID" in df_maestro_para_velas and "ESTADO" in df_maestro_para_velas:
            # Filtrar solo tickers que estén activos
            df_act_filtrado = df_maestro_para_velas[df_maestro_para_velas["ESTADO"].astype(str).str.strip().str.upper() == "ACTIVO"]
            lista_activos_velas = df_act_filtrado["TICKER_ID"].dropna().unique().tolist()
            
        if not lista_activos_velas:
            lista_activos_velas = ["AAPL", "AMD", "AMZN", "C", "CVX", "DIS", "KO", "META", "NKE", "TSLA", "VIST", "WMT", "XOM"]
            
        col_v1, col_v2 = st.columns([4, 6])
        with col_v1:
            dict_act_v = obtener_diccionario_activos()
            activo_velas = st.selectbox(
                "Seleccione el Activo para graficar:", 
                sorted(lista_activos_velas), 
                format_func=lambda x: formatear_ticker(x, dict_act_v),
                key="select_velas_active"
            )
            graficar_local = st.checkbox("Ver par local de BYMA (BCBA)", value=True, help="Muestra la cotización en pesos (Cedear) en lugar del subyacente en dólares de USA.")
            
        ticker_final = f"BCBA:{activo_velas}" if graficar_local else activo_velas
        
        df_historico_velas = cargar_datos_hoja("HISTORICO_VALORES")
        
        if df_historico_velas.empty:
            st.info("No se encontraron registros en HISTORICO_VALORES. Ejecuta el pipeline para importar cotizaciones.")
        else:
            # Filtrar por activo
            df_hist_act = df_historico_velas[df_historico_velas["TICKER_ID"].astype(str).str.strip().str.upper() == ticker_final.upper()]
            
            if df_hist_act.empty:
                st.warning(f"⚠️ No hay registros históricos para el ticker `{ticker_final}`. Prueba desmarcando Byma o ejecuta el bridge.")
            else:
                # Procesar datos
                # Asegurar fechas datetime
                df_hist_act = df_hist_act.copy()
                df_hist_act["FECHA_DT"] = pd.to_datetime(df_hist_act["FECHA"].astype(str), errors='coerce')
                df_hist_act = df_hist_act.dropna(subset=["FECHA_DT"])
                df_hist_act = df_hist_act.sort_values(by="FECHA_DT").reset_index(drop=True)
                
                # Convertir precios a numéricos
                for col in ["PRECIO_CIERRE", "MAXIMO_DIA", "MINIMO_DIA", "VOLUMEN"]:
                    if col in df_hist_act:
                        df_hist_act[col] = pd.to_numeric(df_hist_act[col].astype(str).str.replace(',', '.'), errors='coerce')
                
                # Rellenar valores nulos
                df_hist_act = df_hist_act.ffill().bfill()
                
                # Asumimos que Open es igual al Cierre del día anterior para el dibujo
                df_hist_act["OPEN_DIA"] = df_hist_act["PRECIO_CIERRE"].shift(1).fillna(df_hist_act["PRECIO_CIERRE"])
                
                # Rango de fechas
                fechas_list = df_hist_act["FECHA_DT"].tolist()
                rango_fechas = st.slider(
                    "Seleccione Rango Temporal para Graficar:",
                    min_value=fechas_list[0].to_pydatetime(),
                    max_value=fechas_list[-1].to_pydatetime(),
                    value=(fechas_list[max(0, len(fechas_list)-100)].to_pydatetime(), fechas_list[-1].to_pydatetime()),
                    format="YYYY-MM-DD"
                )
                
                df_filtered_chart = df_hist_act[
                    (df_hist_act["FECHA_DT"] >= pd.Timestamp(rango_fechas[0])) &
                    (df_hist_act["FECHA_DT"] <= pd.Timestamp(rango_fechas[1]))
                ]
                
                if df_filtered_chart.empty:
                    st.info("Seleccione un rango de fechas que contenga registros.")
                else:
                    # Calcular Indicadores Técnicos en el DataFrame filtrado
                    df_filtered_chart = df_filtered_chart.copy()
                    df_filtered_chart["SMA_20"] = df_filtered_chart["PRECIO_CIERRE"].rolling(window=20, min_periods=1).mean()
                    df_filtered_chart["SMA_200"] = df_filtered_chart["PRECIO_CIERRE"].rolling(window=200, min_periods=1).mean()
                    
                    # Calcular RSI (14 días)
                    delta = df_filtered_chart["PRECIO_CIERRE"].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
                    rs = gain / loss.replace(0, 0.00001)
                    df_filtered_chart["RSI"] = 100 - (100 / (1.0 + rs))
                    df_filtered_chart["RSI"] = df_filtered_chart["RSI"].fillna(50.0)
                    
                    # --- GRAFICO 1: Velas y Medias Móviles ---
                    st.subheader(f"📈 Gráfico Candlestick: {ticker_final}")
                    
                    fig_velas = go.Figure()
                    
                    # Agregar Velas
                    fig_velas.add_trace(go.Candlestick(
                        x=df_filtered_chart["FECHA"],
                        open=df_filtered_chart["OPEN_DIA"],
                        high=df_filtered_chart["MAXIMO_DIA"],
                        low=df_filtered_chart["MINIMO_DIA"],
                        close=df_filtered_chart["PRECIO_CIERRE"],
                        name="Cotización"
                    ))
                    
                    # Agregar SMA 20
                    fig_velas.add_trace(go.Scatter(
                        x=df_filtered_chart["FECHA"],
                        y=df_filtered_chart["SMA_20"],
                        line=dict(color="#10B981", width=1.5),
                        name="Media Móvil SMA 20"
                    ))
                    
                    # Agregar SMA 200
                    fig_velas.add_trace(go.Scatter(
                        x=df_filtered_chart["FECHA"],
                        y=df_filtered_chart["SMA_200"],
                        line=dict(color="#EF4444", width=1.5),
                        name="Media Móvil SMA 200"
                    ))
                    
                    fig_velas.update_layout(
                        title=f"Velas y Medias Móviles - {ticker_final}",
                        xaxis_title="Fecha",
                        yaxis_title="Precio (ARS/USD)",
                        xaxis_rangeslider_visible=False,
                        height=550,
                        margin=dict(l=10, r=10, t=40, b=10)
                    )
                    st.plotly_chart(fig_velas, use_container_width=True)
                    
                    # --- GRAFICO 2: Oscilador RSI ---
                    st.subheader("🔍 Oscilador de Fuerza Relativa (RSI 14)")
                    
                    fig_rsi = go.Figure()
                    fig_rsi.add_trace(go.Scatter(
                        x=df_filtered_chart["FECHA"],
                        y=df_filtered_chart["RSI"],
                        line=dict(color="#3B82F6", width=2),
                        name="RSI"
                    ))
                    
                    # Línea de Sobrecompra (70)
                    fig_rsi.add_trace(go.Scatter(
                        x=df_filtered_chart["FECHA"],
                        y=[70] * len(df_filtered_chart),
                        line=dict(color="#EF4444", width=1, dash="dash"),
                        name="Sobrecompra (70)"
                    ))
                    
                    # Línea de Sobreventa (30)
                    fig_rsi.add_trace(go.Scatter(
                        x=df_filtered_chart["FECHA"],
                        y=[30] * len(df_filtered_chart),
                        line=dict(color="#10B981", width=1, dash="dash"),
                        name="Sobreventa (30)"
                    ))
                    
                    fig_rsi.update_layout(
                        yaxis=dict(range=[10, 90]),
                        height=180,
                        margin=dict(l=10, r=10, t=10, b=10),
                        xaxis_title="Fecha",
                        yaxis_title="RSI Value"
                    )
                    st.plotly_chart(fig_rsi, use_container_width=True)

# ==========================================
# PESTAÑA 2: OPERACIONES Y CAJA (APP-SHEET STYLE)
# ==========================================
with tab2:
    st.header("💸 Transacciones, Aportes y Liquidez")
    st.write("Registra compras/ventas de activos y movimientos de caja de forma guiada con validación de fondos en tiempo real:")
    
    # Cargar datos de caja para validación de fondos en caliente
    df_caja_val = cargar_datos_hoja("CAJA_LIQUIDEZ")
    
    # Función auxiliar para consultar saldo de caja en caliente
    def obtener_saldo_disponible(propietario, moneda):
        if df_caja_val.empty:
            return 0.0
        try:
            col_prop = next((c for c in df_caja_val.columns if "PROPIETARIO" in c or "PERFIL" in c or "USUARIO" in c), None)
            col_mon = next((c for c in df_caja_val.columns if "MONEDA" in c), None)
            col_saldo = next((c for c in df_caja_val.columns if "SALDO" in c or "DISPONIBLE" in c), None)
            
            if col_prop and col_mon and col_saldo:
                mask = (df_caja_val[col_prop].astype(str).str.strip().str.upper() == str(propietario).strip().upper()) & \
                       (df_caja_val[col_mon].astype(str).str.strip().str.upper() == str(moneda).strip().upper())
                row_caja = df_caja_val[mask]
                if not row_caja.empty:
                    saldo_str = str(row_caja.iloc[0][col_saldo]).strip().replace(',', '.')
                    if saldo_str.startswith('='):
                        return 99999999.0
                    try:
                        return float(saldo_str)
                    except:
                        return 0.0
        except:
            pass
        return 0.0

    # Cargar listas para selectores dinámicos
    df_usuarios_aux = cargar_datos_hoja("CONFIG_IA_USUARIO")
    lista_propietarios = []
    if not df_usuarios_aux.empty:
        col_prop = next((c for c in df_usuarios_aux.columns if "PROPIETARIO" in c or "PERFIL" in c or "USUARIO" in c), None)
        if col_prop:
            lista_propietarios = sorted(df_usuarios_aux[col_prop].dropna().astype(str).unique().tolist())
    if not lista_propietarios:
        lista_propietarios = ["LUIS", "LUIS_MODERADO", "LUIS_AGRESIVO"]
        
    df_activos_aux = cargar_datos_hoja("MAESTRO_ACTIVOS")
    lista_tickers = []
    if not df_activos_aux.empty:
        col_tick = next((c for c in df_activos_aux.columns if "TICKER" in c), None)
        if col_tick:
            lista_tickers = sorted(df_activos_aux[col_tick].dropna().astype(str).unique().tolist())
    if not lista_tickers:
        lista_tickers = ["AAPL", "AMZN", "META", "TSLA", "KO", "DIS", "AMD", "WMT", "VIST", "XOM"]

    # 1. ASISTENTE DE CARGA GUIADO (TIPO APP-SHEET)
    tipo_registro = st.radio(
        "Seleccione el Tipo de Registro:", 
        ["🛒 Transacción de Activos (CEDEARs, etc)", "🏦 Movimiento de Caja (Aportes/Retiros)"],
        key="ops_radio_type"
    )
    
    sh_form = obtener_conexion_sheets()
    
    if tipo_registro == "🛒 Transacción de Activos (CEDEARs, etc)":
        st.subheader("🛒 Registrar Operación de Activos")
        
        # Selectores interactivos fuera del formulario para permitir el dinamismo de Streamlit
        col_sel1, col_sel2, col_sel3 = st.columns(3)
        with col_sel1:
            op_tipo = st.selectbox("Operación:", ["Compra", "Venta"])
        with col_sel2:
            prop = st.selectbox("Propietario / Perfil:", lista_propietarios)
        with col_sel3:
            moneda = st.selectbox("Moneda de la Operación:", ["ARS", "USD"])
            
        # Filtrado dinámico de Tickers en caliente según tenencias si es Venta
        if op_tipo == "Venta":
            df_val_filtrado = df_val[
                (df_val['PROPIETARIO'].astype(str).str.strip().str.upper() == str(prop).strip().upper()) & \
                (~df_val['TICKER'].isin(['-CASH-', '-TOTAL-'])) & \
                (df_val['CANTIDAD'].astype(float) > 0.0) & \
                (df_val['MONEDA'].astype(str).str.strip().str.upper() == str(moneda).strip().upper())
            ]
            lista_tickers_disponibles = sorted(df_val_filtrado['TICKER'].unique().tolist())
            
            if not lista_tickers_disponibles:
                st.warning(f"⚠️ El perfil {prop} no posee activos en {moneda} para vender actualmente.")
                lista_tickers_disponibles = ["N/A"]
        else:
            # Compra: todos los tickers activos en el maestro
            lista_tickers_disponibles = sorted(lista_tickers)
            
        dict_act_ops = obtener_diccionario_activos()
        ticker = st.selectbox(
            "Activo (Ticker):", 
            lista_tickers_disponibles, 
            format_func=lambda x: formatear_ticker(x, dict_act_ops),
            key="select_ops_ticker"
        )
        
        with st.form("form_transaccion"):
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                fecha_op = st.date_input("Fecha de Operación:", datetime.now())
                cantidad = st.number_input("Cantidad nominal:", min_value=0.0, value=0.0, step=1.0)
            with col_t2:
                precio_u = st.number_input("Precio Unitario:", min_value=0.0, value=0.0, step=100.0)
                comision = st.number_input("Comisión Total cobrada por ALyC:", min_value=0.0, value=0.0, step=10.0)
                
            # Calcular total neto
            if op_tipo == "Compra":
                total_neto_est = (cantidad * precio_u) + comision
            else:
                total_neto_est = (cantidad * precio_u) - comision
                
            # Validar liquidez disponible en caliente
            saldo_caja = obtener_saldo_disponible(prop, moneda)
            fondos_suficientes = True
            
            if ticker == "N/A":
                fondos_suficientes = False
            elif total_neto_est == 0.0:
                st.info(f"💰 Saldo de caja disponible para {prop}: {moneda} {saldo_caja:,.2f}")
                fondos_suficientes = False
            elif op_tipo == "Compra" and total_neto_est > saldo_caja:
                fondos_suficientes = False
                st.error(f"❌ Fondos Insuficientes: {prop} dispone de {moneda} {saldo_caja:,.2f} en caja, pero esta compra requiere {moneda} {total_neto_est:,.2f}.")
            elif op_tipo == "Venta":
                # Validar tenencia máxima nominal
                tenencia_max = 0.0
                if ticker != "N/A" and not df_val_filtrado.empty:
                    row_tenencia = df_val_filtrado[df_val_filtrado['TICKER'] == ticker]
                    if not row_tenencia.empty:
                        tenencia_max = float(row_tenencia.iloc[0]['CANTIDAD'])
                
                if cantidad > tenencia_max:
                    fondos_suficientes = False
                    st.error(f"❌ Venta Inválida: {prop} posee únicamente {tenencia_max:,.2f} nominales de {ticker}, pero intenta vender {cantidad:,.2f} nominales.")
                else:
                    st.info(f"📈 Tenencia disponible de {ticker} para {prop}: {tenencia_max:,.2f} nominales.")
            else:
                st.info(f"💰 Saldo de caja disponible para {prop}: {moneda} {saldo_caja:,.2f} | Costo Neto Estimado: {moneda} {total_neto_est:,.2f}")
                
            btn_submit_trans = st.form_submit_button("💾 Guardar Transacción", disabled=not fondos_suficientes)
            
            if btn_submit_trans and sh_form:
                with st.spinner("Registrando transacción en Google Sheets..."):
                    try:
                        ws_trans = sh_form.worksheet("TRANSACCIONES")
                        headers = [str(h).strip().upper() for h in ws_trans.row_values(1)]
                        
                        ahora_completo = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        fecha_str = fecha_op.strftime("%Y-%m-%d") + " " + datetime.now().strftime("%H:%M:%S")
                        
                        row_dict = {
                            "FECHA": fecha_str,
                            "PROPIETARIO": prop,
                            "ACTIVO": ticker,
                            "OPERACIÓN": op_tipo,
                            "OPERACION": op_tipo,
                            "CANTIDAD": str(cantidad).replace('.', ','),
                            "PRECIO_UNITARIO": str(precio_u).replace('.', ','),
                            "COMISIÓN_TOTAL": str(comision).replace('.', ','),
                            "COMISION_TOTAL": str(comision).replace('.', ','),
                            "MONEDA": moneda,
                            "TOTAL_NETO": str(total_neto_est).replace('.', ','),
                            "FECHA_ACTUALIZACION": ahora_completo
                        }
                        
                        nueva_fila = [row_dict.get(h, "") for h in headers]
                        ws_trans.append_row(nueva_fila, value_input_option="USER_ENTERED")
                        st.success("¡Transacción registrada y liquidez recalculada exitosamente!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error registrando transacción: {e}")
                        
    else:
        st.subheader("🏦 Registrar Movimiento de Caja")
        
        # Selectores interactivos fuera del formulario
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            tipo_mov = st.selectbox("Tipo de Movimiento:", ["INGRESO", "EGRESO"])
        with col_c2:
            prop = st.selectbox("Propietario / Perfil:", lista_propietarios, key="caja_prop_sel")
        with col_c3:
            moneda = st.selectbox("Moneda:", ["ARS", "USD"], key="caja_mon_sel")
            
        with st.form("form_caja"):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                fecha_mov = st.date_input("Fecha de Movimiento:", datetime.now())
                monto = st.number_input("Monto en efectivo:", min_value=0.0, value=0.0, step=100.0)
            with col_f2:
                detalle_mov = st.text_input("Detalle/Concepto:", value="Aporte de capital")
                
            # Validar liquidez disponible en caliente
            saldo_caja = obtener_saldo_disponible(prop, moneda)
            fondos_suficientes = True
            
            if monto == 0.0:
                st.info(f"💰 Saldo de caja disponible para {prop}: {moneda} {saldo_caja:,.2f}")
                fondos_suficientes = False
            elif tipo_mov == "EGRESO" and monto > saldo_caja:
                fondos_suficientes = False
                st.error(f"❌ Retiro Inválido: {prop} dispone de {moneda} {saldo_caja:,.2f} en caja, pero el egreso solicitado es de {moneda} {monto:,.2f}.")
            else:
                st.info(f"💰 Saldo de caja disponible para {prop}: {moneda} {saldo_caja:,.2f} | Monto del movimiento: {moneda} {monto:,.2f}")
                
            btn_submit_caja = st.form_submit_button("💾 Guardar Movimiento de Caja", disabled=not fondos_suficientes)
            
            if btn_submit_caja and sh_form:
                with st.spinner("Registrando movimiento de caja en Google Sheets..."):
                    try:
                        ws_caja_sheet = sh_form.worksheet("MOVIMIENTOS_CAJA")
                        headers = [str(h).strip().upper() for h in ws_caja_sheet.row_values(1)]
                        
                        ahora_completo = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        fecha_str = fecha_mov.strftime("%Y-%m-%d") + " " + datetime.now().strftime("%H:%M:%S")
                        
                        row_dict = {
                            "FECHA": fecha_str,
                            "PROPIETARIO": prop,
                            "TIPO_MOVIMIENTO": tipo_mov,
                            "TIPO": tipo_mov,
                            "MONTO": str(monto).replace('.', ','),
                            "MONEDA": moneda,
                            "DETALLE": detalle_mov,
                            "FECHA_ACTUALIZACION": ahora_completo
                        }
                        
                        nueva_fila = [row_dict.get(h, "") for h in headers]
                        ws_caja_sheet.append_row(nueva_fila, value_input_option="USER_ENTERED")
                        st.success("¡Movimiento de caja registrado exitosamente!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error registrando movimiento: {e}")

    # 2. EDITOR AVANZADO PLEGABLE (Modificar históricos de operaciones)
    st.write("---")
    with st.expander("✏️ Editor Avanzado (Modificar en lote / Ver histórico de planillas)"):
        st.write("Edita directamente las celdas históricas de transacciones y caja. Presiona Guardar al finalizar:")
        
        tabla_ops_elegida = st.selectbox(
            "Seleccione la planilla operativa a modificar:", 
            ["TRANSACCIONES", "MOVIMIENTOS_CAJA"],
            key="ops_editor_select"
        )
        
        sh_ops = obtener_conexion_sheets()
        if sh_ops:
            try:
                df_ops = cargar_datos_hoja(tabla_ops_elegida)
                
                df_ops_mod = st.data_editor(
                    df_ops, 
                    num_rows="dynamic", 
                    use_container_width=True,
                    key=f"editor_ops_{tabla_ops_elegida}"
                )
                
                if st.button(f"💾 Guardar cambios en {tabla_ops_elegida}", key=f"btn_save_ops_{tabla_ops_elegida}"):
                    with st.spinner("Actualizando planilla en Google Sheets..."):
                        try:
                            ws_ops = sh_ops.worksheet(tabla_ops_elegida)
                            ws_ops.clear()
                            cabeceras = [df_ops_mod.columns.tolist()]
                            valores = df_ops_mod.values.tolist()
                            valores_limpios = [[str(x) if pd.notna(x) else "" for x in row] for row in valores]
                            
                            # Escribir con USER_ENTERED para que Sheets vuelva a calcular fórmulas
                            ws_ops.update(values=cabeceras + valores_limpios, range_name='A1', value_input_option='USER_ENTERED')
                            st.success(f"¡Hoja de operaciones `{tabla_ops_elegida}` actualizada exitosamente!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Error al escribir en Google Sheets: {ex}")
            except Exception as e:
                st.error(f"Error cargando la hoja `{tabla_ops_elegida}`: {e}")
                
    st.write("---")
    st.subheader("🏦 Resumen de Caja y Liquidez (Calculado en Sheets)")
    df_caja_readonly = cargar_datos_hoja("CAJA_LIQUIDEZ")
    if not df_caja_readonly.empty:
        st.dataframe(df_caja_readonly, use_container_width=True)
    else:
        st.info("No se pudieron cargar datos consolidados de caja.")


# ==========================================
# PESTAÑA 3: MATRIZ DE DECISIONES IA
# ==========================================
with tab3:
    st.header("🎯 Matriz de Decisiones y Veredictos de IA")
    st.write("Visualiza las recomendaciones de inversión (Comprar/Vender/Mantener) organizadas por perfil de inversión:")
    
    # Cargar datos necesarios
    df_matriz = cargar_datos_hoja(config.WS_MATRIZ_RECOMENDACIONES)
    df_tecnico = cargar_datos_hoja(config.WS_ANALISIS_TECNICO)
    df_maestro = cargar_datos_hoja(config.WS_MAESTRO_ACTIVOS)
    df_val = cargar_datos_hoja("VALORACION_PORTAFOLIO")
    
    if df_matriz.empty:
        st.info("No se encontraron registros de decisiones en la tabla MATRIZ_RECOMENDACIONES. Ejecuta el pipeline para generarlos.")
    else:
        # Ordenamos las filas de forma cronológica descendente si existe la columna Fecha
        col_fecha_matriz = next((c for c in df_matriz.columns if "FECHA" in c), None)
        if col_fecha_matriz:
            try:
                df_matriz = df_matriz.sort_values(by=col_fecha_matriz, ascending=False).reset_index(drop=True)
            except:
                pass
        
        # --- FUNCIÓN AUXILIAR PARA PARSEAR EL VEREDICTO ---
        def parsear_veredicto(texto):
            lineas = str(texto).split('\n')
            datos = {
                "horizonte": "N/A",
                "conviccion": "N/A",
                "score": "N/A",
                "riesgo": "N/A",
                "confluencia": "Sin datos de confluencia",
                "analisis": "Sin detalle de análisis"
            }
            analisis_lineas = []
            for l in lineas:
                l_clean = l.strip()
                if l_clean.startswith("🎯 HORIZONTE:"):
                    datos["horizonte"] = l_clean.replace("🎯 HORIZONTE:", "").strip()
                elif l_clean.startswith("🧠 CONVICCIÓN:") or l_clean.startswith("🧠 CONVICCION:"):
                    datos["conviccion"] = l_clean.replace("🧠 CONVICCIÓN:", "").replace("🧠 CONVICCION:", "").strip()
                elif l_clean.startswith("📊 SCORE:"):
                    datos["score"] = l_clean.replace("📊 SCORE:", "").strip()
                elif l_clean.startswith("⚠️ RIESGO:"):
                    datos["riesgo"] = l_clean.replace("⚠️ RIESGO:", "").strip()
                elif l_clean.startswith("📰 CONFLUENCIA NOTICIAS:"):
                    datos["confluencia"] = l_clean.replace("📰 CONFLUENCIA NOTICIAS:", "").strip()
                elif l_clean.startswith("📝 ANÁLISIS:") or l_clean.startswith("📝 ANALISIS:"):
                    datos["analisis"] = l_clean.replace("📝 ANÁLISIS:", "").replace("📝 ANALISIS:", "").strip()
                elif l_clean and not any(l_clean.startswith(pref) for pref in ["🎯", "🧠", "📊", "⚠️", "📰", "📝"]):
                    analisis_lineas.append(l_clean)
            
            if analisis_lineas:
                if datos["analisis"] == "Sin detalle de análisis" or len(datos["analisis"]) < 10:
                    datos["analisis"] = " ".join(analisis_lineas)
            return datos

        # Normalizar columnas
        df_matriz.columns = [c.upper() for c in df_matriz.columns]
        if not df_tecnico.empty:
            df_tecnico.columns = [c.upper() for c in df_tecnico.columns]
        if not df_maestro.empty:
            df_maestro.columns = [c.upper() for c in df_maestro.columns]
        if not df_val.empty:
            df_val.columns = [c.upper() for c in df_val.columns]

        # Crear diccionario de descripciones de activos
        mapeo_descripciones = {}
        if not df_maestro.empty and 'TICKER_ID' in df_maestro.columns:
            for _, r_m in df_maestro.iterrows():
                tk_id = str(r_m['TICKER_ID']).strip().upper()
                desc = str(r_m.get('DESCRIPCION', r_m.get('NOMBRE', ''))).strip()
                if tk_id:
                    mapeo_descripciones[tk_id] = desc

        # --- SECCIÓN DE FILTROS ---
        st.write("### 🔍 Filtros de Búsqueda")
        col_f1, col_f2 = st.columns(2)
        
        tickers_disponibles = sorted(list(df_matriz['TICKER'].dropna().unique()))
        sentimientos_disponibles = sorted(list(df_matriz['SENTIMIENTO'].dropna().unique()))
        
        with col_f1:
            dict_act_matriz = obtener_diccionario_activos()
            filtro_t = st.selectbox(
                "Ticker / Activo:", 
                ["Todos"] + sorted(tickers_disponibles), 
                format_func=lambda x: formatear_ticker(x, dict_act_matriz),
                key="select_filtro_t_matriz"
            )
        with col_f2:
            filtro_s = st.selectbox("Sentimiento IA:", ["Todos"] + sentimientos_disponibles, key="select_filtro_s_matriz")
            
        # Control global de expansión de tarjetas
        expandir_todos = st.checkbox("📂 Expandir todos los análisis de esta pestaña", value=False, key="expandir_matriz_checkbox")

        # Configurar pestañas por Perfil de inversión
        lista_perfiles_ui = [
            ("LUIS", "👤 LUIS (Agresivo)"),
            ("LUIS_MODERADO", "👤 LUIS_MODERADO (Moderado)"),
            ("VICKY", "👤 VICKY (Conservador)"),
            ("ANTO", "👤 ANTO (Conservador)")
        ]
        
        perfiles_tabs = st.tabs([p[1] for p in lista_perfiles_ui])
        
        for idx_tab, (p_id, p_label) in enumerate(lista_perfiles_ui):
            with perfiles_tabs[idx_tab]:
                # Filtrar datos de la matriz para este perfil específico
                df_perfil = df_matriz[df_matriz['PERFIL'] == p_id].copy()
                
                # Aplicar filtros adicionales de Ticker y Sentimiento
                if filtro_t != "Todos":
                    df_perfil = df_perfil[df_perfil['TICKER'] == filtro_t]
                if filtro_s != "Todos":
                    df_perfil = df_perfil[df_perfil['SENTIMIENTO'] == filtro_s]
                
                if df_perfil.empty:
                    st.info(f"No se encontraron veredictos de IA para el perfil {p_id} con los filtros seleccionados.")
                    continue
                
                # Tarjetas métricas específicas para este perfil
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                with col_m1:
                    st.metric("Activos Analizados", len(df_perfil['TICKER'].unique()))
                with col_m2:
                    c_compras = len(df_perfil[df_perfil['SENTIMIENTO'].str.contains("BULL|COMPRA", case=False, na=False)])
                    st.metric("Comprar 🟢", c_compras)
                with col_m3:
                    c_hold = len(df_perfil[df_perfil['SENTIMIENTO'].str.contains("HOLD|NEUTRAL|MANT", case=False, na=False)])
                    st.metric("Mantener 🟡", c_hold)
                with col_m4:
                    c_ventas = len(df_perfil[df_perfil['SENTIMIENTO'].str.contains("BEAR|VENTA", case=False, na=False)])
                    st.metric("Vender 🔴", c_ventas)
                
                st.write("---")
                
                # Listar veredictos de este perfil por activo
                tickers_perfil = list(df_perfil['TICKER'].unique())
                for tk in tickers_perfil:
                    df_tk = df_perfil[df_perfil['TICKER'] == tk].iloc[0]
                    v_parsed = parsear_veredicto(df_tk['VEREDICTO_IA'])
                    
                    sentimiento = str(df_tk['SENTIMIENTO']).strip().upper()
                    
                    # Semáforo de color y emoji
                    color_emoji = "🟡"
                    sent_label = "HOLD / NEUTRAL"
                    if "BULL" in sentimiento or "COMPRA" in sentimiento:
                        color_emoji = "🟢"
                        sent_label = "BULLISH (COMPRA)"
                    elif "BEAR" in sentimiento or "VENTA" in sentimiento:
                        color_emoji = "🔴"
                        sent_label = "BEARISH (VENTA)"

                    # Buscar descripción del activo
                    desc_act = mapeo_descripciones.get(tk.upper(), "")
                    label_ticker = f"{tk} ({desc_act})" if desc_act else tk

                    # Determinar si el activo ya está en cartera de este perfil
                    tiene_activo = False
                    if not df_val.empty and 'PROPIETARIO' in df_val.columns and 'TICKER' in df_val.columns:
                        df_val_fil = df_val[
                            (df_val['PROPIETARIO'].astype(str).str.strip().str.upper() == p_id.upper()) & 
                            (df_val['TICKER'].astype(str).str.strip().str.upper() == tk.upper())
                        ]
                        if not df_val_fil.empty:
                            try:
                                cant = float(str(df_val_fil.iloc[0].get('CANTIDAD', 0.0)).replace(',', '.'))
                                if cant > 0.0:
                                    tiene_activo = True
                            except:
                                pass

                    badge_tenencia = "💼 [En Cartera]" if tiene_activo else "🚀 [Nueva Oportunidad]"

                    # Score máximo del activo
                    score = v_parsed["score"]
                    fecha_val = str(df_tk['FECHA']).split()[0]
                    
                    # Calcular brecha cambiaria del activo frente al MEP de venta
                    brecha_tk = 0.0
                    insignia_brecha = ""
                    consejo_corto = ""
                    ccl_num_val = None
                    
                    if not df_tecnico.empty:
                        df_tk_tec = df_tecnico[df_tecnico['TICKER_ID'] == tk.upper()]
                        if not df_tk_tec.empty:
                            try:
                                ccl_raw = df_tk_tec.iloc[0].get('CCL_IMPLICITO')
                                if ccl_raw is not None and str(ccl_raw).strip() != '':
                                    ccl_num_val = float(str(ccl_raw).replace(',', '.'))
                                    # Sanar escala
                                    if ccl_num_val > 100000: ccl_num_val /= 100.0
                                    elif ccl_num_val > 10000: ccl_num_val /= 10.0
                                    
                                    if ccl_num_val > 500 and mep_v > 0:
                                        brecha_tk = ((ccl_num_val - mep_v) / mep_v) * 100
                                        if brecha_tk > 2.5:
                                            insignia_brecha = f" ⚠️ (+{brecha_tk:.1f}% ARS Caro)"
                                            consejo_corto = "Sobreprecio en pesos local."
                                        elif brecha_tk < 1.5:
                                            insignia_brecha = f" 🟢 (+{brecha_tk:.1f}% ARS Oferta)"
                                            consejo_corto = "Buen tipo de cambio en pesos."
                                        else:
                                            insignia_brecha = f" 🔵 (+{brecha_tk:.1f}%)"
                                            consejo_corto = "Tipo de cambio estándar."
                            except:
                                pass
                                
                    header_exp = f"{color_emoji} {label_ticker}{insignia_brecha} | {sent_label} | Score: {score} | {badge_tenencia} | Actualizado: {fecha_val}"
                    
                    with st.expander(header_exp, expanded=expandir_todos):
                        # 1. Banners de Datos Técnicos en Contenedor Claro Nativo (Alto Contraste)
                        if not df_tecnico.empty:
                            df_tk_tec = df_tecnico[df_tecnico['TICKER_ID'] == tk]
                            if not df_tk_tec.empty:
                                tec_row = df_tk_tec.iloc[0]
                                rsi_val = tec_row.get('RSI', 'N/A')
                                trend_val = tec_row.get('TREND', 'N/A')
                                ccl_val = tec_row.get('CCL_IMPLICITO', 'N/A')
                                sma20_val = tec_row.get('SMA_20', 'N/A')
                                sma200_val = tec_row.get('SMA_200', 'N/A')
                                
                                # Si tenemos el número formateado, lo mostramos estilizado
                                ccl_display = f"{ccl_num_val:,.2f} ARS" if ccl_num_val else f"{ccl_val} ARS"
                                ccl_label = f"<div style='font-size: 15px;'>💵 <b>CCL:</b><br><code style='font-size: 15px;'>{ccl_display}</code>"
                                if ccl_num_val and mep_v > 0:
                                    color_brecha = '#FF4D4D' if brecha_tk > 2.5 else '#2ECC71' if brecha_tk < 1.5 else '#3498DB'
                                    ccl_label += f"<br><span style='font-size: 13px; font-weight: bold; color: {color_brecha};'>*{consejo_corto}*</span>"
                                ccl_label += "</div>"
                                
                                with st.container(border=True):
                                    col_t1, col_t2, col_t3, col_t4, col_t5 = st.columns(5)
                                    col_t1.markdown(f"<div style='font-size: 15px;'>📊 <b>RSI:</b><br><code style='font-size: 16px;'>{rsi_val}</code></div>", unsafe_allow_html=True)
                                    col_t2.markdown(f"<div style='font-size: 15px;'>📈 <b>Tendencia:</b><br><code style='font-size: 15px;'>{trend_val}</code></div>", unsafe_allow_html=True)
                                    col_t3.markdown(ccl_label, unsafe_allow_html=True)
                                    col_t4.markdown(f"<div style='font-size: 15px;'>📍 <b>SMA 20:</b><br><code style='font-size: 16px;'>{sma20_val}</code></div>", unsafe_allow_html=True)
                                    col_t5.markdown(f"<div style='font-size: 15px;'>📍 <b>SMA 200:</b><br><code style='font-size: 16px;'>{sma200_val}</code></div>", unsafe_allow_html=True)

                        # 2. Detalles del Veredicto en Contenedor Nativo (Alto Contraste)
                        with st.container(border=True):
                            st.markdown(f"### 🎯 Recomendación para Perfil: **{p_id}**")
                            
                            col_v1, col_v2 = st.columns([2, 3])
                            with col_v1:
                                st.markdown(f"**⏳ Horizonte Temporal:** {v_parsed['horizonte']}")
                                st.markdown(f"**⚠️ Nivel de Riesgo:** {v_parsed['riesgo']}")
                                st.markdown(f"**🧠 Convicción del Motor:** {v_parsed['conviccion']}")
                                
                                # Progreso visual del Score
                                sc_num_str = score.split('/')[0].strip()
                                if sc_num_str.isdigit():
                                    st.progress(int(sc_num_str) / 10.0, text=f"📊 **Score Calculado: {sc_num_str}/10**")
                                else:
                                    st.write(f"📊 **Score Calculado:** {score}")
                                    
                            with col_v2:
                                # Desglosar textos largos con alto contraste y tipografía estándar
                                st.markdown(f"**📰 Confluencia de Noticias:**\n{v_parsed['confluencia']}")
                                st.markdown(f"**📝 Análisis Técnico y Fundamental:**\n{v_parsed['analisis']}")

        # --- GRIDS Y DESCARGAS DE RESPALDO ---
        st.write("---")
        with st.expander("📂 Mostrar Tabla de Datos Original (Sheets)"):
            st.dataframe(df_matriz, use_container_width=True)

# ==========================================
# PESTAÑA 4: REPORTES DEL SUPERVISOR
# ==========================================
with tab4:
    st.header("📋 Reportes de Supervisión del Sistema")
    
    rep_dir = Path(os.path.join(WORKSPACE_DIR, "ESTRATEGIA_REPORTS"))
    if not rep_dir.exists():
        st.warning("No se encontró la carpeta de reportes `ESTRATEGIA_REPORTS`.")
    else:
        archivos_reportes = sorted(list(rep_dir.glob("Supervision_Sistema_*.md")), key=lambda x: x.stat().st_mtime, reverse=True)
        archivos_reportes += sorted(list(rep_dir.glob("Estrategia_*.md")), key=lambda x: x.stat().st_mtime, reverse=True)
        
        if not archivos_reportes:
            st.info("No se encontraron reportes generados en la carpeta `ESTRATEGIA_REPORTS`.")
        else:
            nombres_archivos = [a.name for a in archivos_reportes]
            seleccionado = st.selectbox("Seleccione el reporte a visualizar:", nombres_archivos)
            
            path_completo = rep_dir / seleccionado
            try:
                with open(path_completo, "r", encoding="utf-8") as f:
                    cuerpo_reporte = f.read()
                
                st.write("---")
                st.markdown(cuerpo_reporte)
            except Exception as e:
                st.error(f"Error leyendo el reporte: {e}")

# ==========================================
# PESTAÑA 5: PARÁMETROS DE LA IA
# ==========================================
with tab5:
    st.header("⚙️ Parámetros y Prompts del Motor de IA")
    st.write("Modifica el comportamiento y comportamiento estratégico de los modelos Gemini de producción:")
    
    params_ia = obtener_parametros_ia()
    
    if not params_ia:
        st.warning("No se pudieron cargar los parámetros de la IA desde la hoja CONFIG_IA_GENERAL. Presiona 'Refrescar Datos' en la Consola.")
    else:
        prompt_general_val = params_ia.get('Instrucciones_Fijas', '')
        prompt_triage_val = params_ia.get('Prompt_Triage_Noticias', '')
        
        prompt_general = st.text_area(
            "📝 Prompt de Comportamiento del Decisor (Instrucciones_Fijas):",
            value=prompt_general_val,
            height=300,
            help="Prompt maestro que le indica al decisor cómo ponderar indicadores técnicos y perfiles de riesgo."
        )
        
        prompt_triage = st.text_area(
            "📰 Prompt de Triage y Filtrado de Noticias (Prompt_Triage_Noticias):",
            value=prompt_triage_val,
            height=300,
            help="Prompt para evaluar la relevancia macroeconómica y el sentimiento de las noticias capturadas."
        )
        
        if st.button("💾 Guardar Parámetros de IA", key="btn_save_ia_params"):
            sh_ia = obtener_conexion_sheets()
            if sh_ia:
                with st.spinner("Guardando prompts de la IA en Google Sheets..."):
                    try:
                        ws_ia = sh_ia.worksheet(config.WS_CONFIG_IA_GENERAL)
                        raw_headers = ws_ia.row_values(1)
                        
                        nueva_fila = []
                        for h in raw_headers:
                            h_clean = h.strip()
                            if h_clean == 'Instrucciones_Fijas':
                                nueva_fila.append(prompt_general)
                            elif h_clean == 'Prompt_Triage_Noticias':
                                nueva_fila.append(prompt_triage)
                            else:
                                nueva_fila.append(params_ia.get(h_clean, ''))
                        
                        # Sobrescribir fila 2
                        ws_ia.update(values=[nueva_fila], range_name="A2:Z2", raw=True)
                        st.success("¡Parámetros de la IA actualizados con éxito!")
                        st.cache_data.clear()
                    except Exception as ex:
                        st.error(f"Error escribiendo en Google Sheets: {ex}")

# ==========================================
# PESTAÑA 6: TABLAS PARAMÉTRICAS (UI AMIGABLE Y APORTES DE SINÓNIMOS)
# ==========================================
with tab6:
    st.header("🛠️ Configuración y Tablas Paramétricas")
    st.write("Gestiona canales de Telegram, aprueba sinónimos y modifica tablas de configuración de forma fluida:")
    
    param_modo = st.selectbox(
        "Seleccione qué desea configurar:", 
        [
            "📢 Canales de Telegram Consultados", 
            "🔍 Sugerencias de Sinónimos (Aprobación)", 
            "✏️ Otras Tablas Paramétricas (Grilla)"
        ],
        key="param_modo_selectbox"
    )
    
    sh_param = obtener_conexion_sheets()
    
    if param_modo == "📢 Canales de Telegram Consultados":
        st.subheader("📢 Canales de Telegram Consultados")
        st.write("Modifica la lista de canales de Telegram de los cuales el bot lee noticias. Realiza todos tus cambios y presiona Guardar Canales al finalizar:")
        
        if sh_param:
            try:
                df_tg = cargar_datos_hoja("CONFIG_TELEGRAM_CHANNELS")
                df_tg.columns = [c.strip().upper() for c in df_tg.columns]
                df_tg_mod = st.data_editor(
                    df_tg, 
                    num_rows="dynamic", 
                    use_container_width=True,
                    column_config={
                        "ESTADO": st.column_config.SelectboxColumn(
                            "Estado del Canal",
                            help="Seleccione si el canal está ACTIVO o INACTIVO para la lectura de noticias",
                            options=["ACTIVO", "INACTIVO"],
                            required=True
                        )
                    },
                    key="editor_telegram_channels"
                )
                
                if st.button("💾 Guardar Canales de Telegram", key="btn_save_tg_channels"):
                    with st.spinner("Guardando configuración de Telegram en Google Sheets..."):
                        try:
                            ws_param = sh_param.worksheet("CONFIG_TELEGRAM_CHANNELS")
                            ws_param.clear()
                            cabeceras = [df_tg_mod.columns.tolist()]
                            valores = df_tg_mod.values.tolist()
                            valores_limpios = [[str(x) if pd.notna(x) else "" for x in row] for row in valores]
                            
                            ws_param.update(values=cabeceras + valores_limpios, range_name='A1', value_input_option='USER_ENTERED')
                            st.success("¡Configuración de Canales de Telegram guardada exitosamente!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Error escribiendo en Google Sheets: {ex}")
            except Exception as e:
                st.error(f"Error leyendo la hoja CONFIG_TELEGRAM_CHANNELS: {e}")
                
    elif param_modo == "🔍 Sugerencias de Sinónimos (Aprobación)":
        st.subheader("🔍 Aprobación de Sinónimos de Activos")
        
        col_sug_sub, col_sug_ref = st.columns([8, 2])
        with col_sug_sub:
            st.write("Cuando la IA captura una noticia y encuentra un término desconocido, el supervisor te propone asociarlo a un Ticker. Apruébalo aquí para que se auto-cargue en las próximas lecturas:")
        with col_sug_ref:
            if st.button("🔄 Refrescar", key="btn_ref_sinonimos_sug", help="Refresca las sugerencias de sinónimos desde Sheets."):
                st.cache_data.clear()
                
        try:
            def normalizar_id(val):
                val_str = str(val).strip()
                if val_str.endswith(".0"):
                    val_str = val_str[:-2]
                if val_str == "0,00E+00" or val_str == "0.0" or val_str == "0":
                    return "0"
                return val_str.upper()

            df_sug = cargar_datos_hoja("SUGERENCIAS_SINONIMOS")
            
            if df_sug.empty:
                st.success("🎉 ¡No hay sugerencias registradas!")
            else:
                df_sug.columns = [c.strip().upper() for c in df_sug.columns]
                df_pendientes = df_sug[df_sug['ESTADO'].astype(str).str.strip().str.upper() == "PENDIENTE"].copy()
                
                if df_pendientes.empty:
                    st.success("🎉 ¡No hay sugerencias de sinónimos pendientes de aprobación!")
                else:
                    st.write(f"Tienes **{len(df_pendientes)}** sugerencias pendientes de revisión:")
                    
                    # Cargar tickers del maestro para validación
                    tickers_maestro = set()
                    try:
                        df_maestro_sug = cargar_datos_hoja(config.WS_MAESTRO_ACTIVOS)
                        if not df_maestro_sug.empty:
                            df_maestro_sug.columns = [c.upper() for c in df_maestro_sug.columns]
                            tickers_maestro = {str(r.get('TICKER_ID', '')).strip().upper() for _, r in df_maestro_sug.iterrows() if r.get('TICKER_ID')}
                    except Exception as m_err:
                        st.warning(f"No se pudo cargar el maestro de activos para validación de tickers: {m_err}")

                    # Inicializar o recuperar diccionario de estado de decisiones en session_state
                    session_key = "sinonimos_decisiones"
                    if session_key not in st.session_state:
                        st.session_state[session_key] = {}
                    
                    # Asegurar que todas las sugerencias pendientes tengan un estado de decisión
                    for _, row in df_pendientes.iterrows():
                        sug_id = normalizar_id(row['ID'])
                        if sug_id not in st.session_state[session_key]:
                            st.session_state[session_key][sug_id] = "Dejar Pendiente"

                    # Botones de Acción Masiva
                    col_all_1, col_all_2, col_all_3 = st.columns([1.5, 1.5, 3])
                    with col_all_1:
                        if st.button("👍 Preseleccionar TODOS como Aprobar", key="btn_aprove_all_syn"):
                            for _, row in df_pendientes.iterrows():
                                s_id = normalizar_id(row['ID'])
                                st.session_state[session_key][s_id] = "Aprobar"
                                st.session_state[f"rad_decision_{s_id}"] = "Aprobar"
                            st.rerun()
                    with col_all_2:
                        if st.button("👎 Preseleccionar TODOS como Rechazar", key="btn_reject_all_syn"):
                            for _, row in df_pendientes.iterrows():
                                s_id = normalizar_id(row['ID'])
                                st.session_state[session_key][s_id] = "Rechazar"
                                st.session_state[f"rad_decision_{s_id}"] = "Rechazar"
                            st.rerun()

                    st.write("---")

                    # Envolver las sugerencias en un formulario para evitar reruns al hacer clicks individuales
                    with st.form("form_sinonimos_pendientes", clear_on_submit=False):
                        # Renderizar las sugerencias pendientes en formato Cards legibles
                        for _, row in df_pendientes.iterrows():
                            sug_id = normalizar_id(row['ID'])
                            fecha = str(row['FECHA']).strip()
                            titular = str(row['TITULAR']).strip()
                            termino = str(row['TERMINO_SUGERIDO']).strip()
                            ticker_prop = str(row['TICKER_SUGERIDO']).strip()
                            explicacion = str(row['EXPLICACION']).strip()

                            # Dibujar tarjeta de la sugerencia
                            with st.container(border=True):
                                st.markdown(f"### 📰 {titular}")
                                st.markdown(f"📅 *Fecha:* {fecha}")
                                
                                # Resaltar la propuesta de asociación
                                st.markdown(f"""
                                <div style='font-size: 1.15rem; margin-top: 10px; margin-bottom: 10px;'>
                                    IA propone asociar: <code style='font-size:1.25rem; color:#d97706;'>{termino}</code> ➔ Ticker: <code style='font-size:1.25rem; color:#1d4ed8;'>{ticker_prop}</code>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                st.write(f"💡 *Motivo / Explicación:* {explicacion}")

                                # Validar si el ticker existe en el maestro
                                if tickers_maestro and ticker_prop.upper() not in tickers_maestro:
                                    st.warning(f"⚠️ El ticker sugerido '{ticker_prop}' no existe en el Maestro de Activos.")

                                # Control de decisión individual
                                current_val = st.session_state[session_key].get(sug_id, "Dejar Pendiente")
                                try:
                                    index_val = ["Dejar Pendiente", "Aprobar", "Rechazar"].index(current_val)
                                except ValueError:
                                    index_val = 0

                                col_lbl, col_rad = st.columns([1, 4])
                                with col_lbl:
                                    st.markdown("<p style='font-size:1.1rem; font-weight:bold; margin-top:8px;'>Decisión:</p>", unsafe_allow_html=True)
                                with col_rad:
                                    dec = st.radio(
                                        "Seleccione acción:",
                                        ["Dejar Pendiente", "Aprobar", "Rechazar"],
                                        index=index_val,
                                        horizontal=True,
                                        key=f"rad_decision_{sug_id}",
                                        label_visibility="collapsed"
                                    )
                                    # Guardar cambio en el estado de sesión temporal
                                    st.session_state[session_key][sug_id] = dec

                        st.write("---")

                        # Botón de envío del formulario
                        btn_apply = st.form_submit_button("💾 Aplicar Decisiones sobre Sinónimos", type="primary")

                    if btn_apply:
                        # Leer decisiones directamente del estado de los radios en el submit
                        acciones_a_procesar = {}
                        for _, row in df_pendientes.iterrows():
                            sug_id = normalizar_id(row['ID'])
                            val_radio = st.session_state.get(f"rad_decision_{sug_id}", "Dejar Pendiente")
                            if val_radio != "Dejar Pendiente":
                                acciones_a_procesar[sug_id] = val_radio
                        
                        if not acciones_a_procesar:
                            st.warning("No has seleccionado ninguna acción (Aprobar/Rechazar) para aplicar.")
                        else:
                            with st.spinner("Procesando decisiones en Google Sheets..."):
                                try:
                                    ws_sin = sh_param.worksheet("CONFIG_SINONIMOS")
                                    ws_sug = sh_param.worksheet("SUGERENCIAS_SINONIMOS")
                                    raw_sin = ws_sin.get_all_records()
                                    df_sin = pd.DataFrame(raw_sin)
                                    df_sin.columns = [c.strip().upper() for c in df_sin.columns]
                                    
                                    # Mapeo en diccionario para buscar y editar rápido
                                    sinonimos_dict = {}
                                    for _, r in df_sin.iterrows():
                                        sinonimos_dict[str(r['TICKER']).strip().upper()] = str(r['SINONIMOS']).strip()
                                        
                                    # Procesar decisiones
                                    cambio_sugerencias = False
                                    cambio_sinonimos = False
                                    
                                    # Obtener valores crudos de SUGERENCIAS_SINONIMOS para mapear fila exacta por ID
                                    raw_sug_rows = ws_sug.get_all_values()
                                    headers_sug = [h.strip().upper() for h in raw_sug_rows[0]]
                                    id_col_idx = headers_sug.index("ID") + 1
                                    estado_col_idx = headers_sug.index("ESTADO") + 1
                                    
                                    # Iterar sobre las sugerencias que cambiaron
                                    for sug_id, dec in acciones_a_procesar.items():
                                        # Buscar los valores de la sugerencia en la lista original
                                        sug_row_data = None
                                        row_number = None
                                        for idx_row, row_val in enumerate(raw_sug_rows[1:], start=2):
                                            if normalizar_id(row_val[id_col_idx - 1]) == sug_id:
                                                sug_row_data = row_val
                                                row_number = idx_row
                                                break
                                        
                                        if not sug_row_data or not row_number:
                                            continue
                                            
                                        # Extraer datos de la fila original
                                        termino_col_idx = headers_sug.index("TERMINO_SUGERIDO")
                                        ticker_col_idx = headers_sug.index("TICKER_SUGERIDO")
                                        
                                        termino = str(sug_row_data[termino_col_idx]).strip()
                                        ticker_prop = str(sug_row_data[ticker_col_idx]).strip()
                                        
                                        if dec == "Aprobar":
                                            tk_upper = ticker_prop.strip().upper()
                                            t_clean = termino.strip()
                                            
                                            if tk_upper in sinonimos_dict:
                                                lista_actual = [s.strip().upper() for s in sinonimos_dict[tk_upper].split(",") if s.strip()]
                                                if t_clean.upper() not in lista_actual:
                                                    sinonimos_dict[tk_upper] = sinonimos_dict[tk_upper] + "," + t_clean
                                                    cambio_sinonimos = True
                                            else:
                                                sinonimos_dict[tk_upper] = t_clean
                                                cambio_sinonimos = True
                                                
                                            ws_sug.update_cell(row_number, estado_col_idx, "PROCESADO")
                                            cambio_sugerencias = True
                                            
                                        elif dec == "Rechazar":
                                            ws_sug.update_cell(row_number, estado_col_idx, "RECHAZADO")
                                            cambio_sugerencias = True
                                            
                                    # Guardar CONFIG_SINONIMOS de vuelta completa si cambió
                                    if cambio_sinonimos:
                                        nuevas_filas_sin = []
                                        for tk, sins in sinonimos_dict.items():
                                            nuevas_filas_sin.append([tk, sins])
                                            
                                        ws_sin.clear()
                                        ws_sin.update(values=[['TICKER', 'SINONIMOS']] + nuevas_filas_sin, range_name='A1', value_input_option='USER_ENTERED')
                                        
                                    st.success("¡Decisiones aplicadas con éxito! Las sugerencias aprobadas se han incorporado a la tabla de sinónimos activos.")
                                    
                                    # Limpiar estado del editor en session_state para la próxima carga
                                    if session_key in st.session_state:
                                        del st.session_state[session_key]
                                        
                                    st.cache_data.clear()
                                    st.rerun()
                                except Exception as ex:
                                    st.error(f"Error procesando aprobaciones: {ex}")
        except Exception as e:
            st.error(f"Error leyendo la hoja SUGERENCIAS_SINONIMOS: {e}")
                
    else:
        # Grilla para otras tablas
        tablas_reales = ["MAESTRO_ACTIVOS", "PROGRAMA_CEDEARS", "CONFIG_FUENTES", "CONFIG_SINONIMOS", "SUGERENCIAS_SINONIMOS"]
        tabla_elegida = st.selectbox("Seleccione la tabla de grilla a modificar:", tablas_reales, key="grilla_param_select")
        
        if sh_param:
            try:
                df_param = cargar_datos_hoja(tabla_elegida)
                
                # Armar configuración de columnas dinámica para facilitar la edición sin tipear
                col_config_dinamico = {}
                for col_name in df_param.columns:
                    col_upper = col_name.strip().upper()
                    if col_upper == "ESTADO":
                        col_config_dinamico[col_name] = st.column_config.SelectboxColumn(
                            col_name,
                            help="Seleccione el estado (ACTIVO o INACTIVO)",
                            options=["ACTIVO", "INACTIVO"],
                            required=True
                        )
                    elif col_upper == "MONEDA":
                        col_config_dinamico[col_name] = st.column_config.SelectboxColumn(
                            col_name,
                            help="Seleccione la moneda (ARS o USD)",
                            options=["ARS", "USD"],
                            required=True
                        )

                df_param_mod = st.data_editor(
                    df_param, 
                    num_rows="dynamic", 
                    use_container_width=True,
                    column_config=col_config_dinamico,
                    key=f"editor_param_grilla_{tabla_elegida}"
                )
                
                if st.button(f"💾 Guardar cambios en {tabla_elegida}", key=f"btn_save_param_grilla_{tabla_elegida}"):
                    with st.spinner("Escribiendo datos en Google Sheets..."):
                        try:
                            ws_param = sh_param.worksheet(tabla_elegida)
                            ws_param.clear()
                            cabeceras = [df_param_mod.columns.tolist()]
                            valores = df_param_mod.values.tolist()
                            valores_limpios = [[str(x) if pd.notna(x) else "" for x in row] for row in valores]
                            
                            ws_param.update(values=cabeceras + valores_limpios, range_name='A1', value_input_option='USER_ENTERED')
                            st.success(f"¡Cambios guardados en la tabla paramétrica `{tabla_elegida}`!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Error al escribir en Google Sheets: {ex}")
            except Exception as e:
                st.error(f"Error cargando la tabla paramétrica `{tabla_elegida}`: {e}")

# ==========================================
# PESTAÑA 7: CONSOLA DE LOGS
# ==========================================
with tab7:
    st.header("💻 Consola de Procesos e Integridad")
    
    col_ref1, col_ref2 = st.columns([8, 2])
    with col_ref2:
        if st.button("🔄 Refrescar Logs", key="btn_refresh_logs_tab", help="Refresca en caliente la tabla del semáforo y el historial de logs de Sheets sin limpiar los datos del portafolio."):
            cargar_logs_recientes.clear()
            cargar_datos_semaforo.clear()
            
    # 1. Planilla del Semáforo (ESTADO_PROCESOS)
    st.subheader("🚦 Tabla Semáforo (Estado de Procesos)")
    df_semaforo = cargar_datos_semaforo()
    if not df_semaforo.empty:
        st.dataframe(df_semaforo, use_container_width=True)
    else:
        st.info("No se pudieron cargar los datos de la tabla semáforo. Presiona 'Refrescar Datos'.")
        
    st.write("---")

    # 2. Log de Ejecución Actual (Plegable en expander)
    log_content = ""
    if LOG_FILE_PATH.exists():
        try:
            with open(LOG_FILE_PATH, "r", encoding="utf-8", errors="replace") as f:
                log_content = f.read()
        except Exception as ex:
            log_content = f"Error al abrir archivo de bitácora: {ex}"
            
    if log_content != "":
        with st.expander("📝 Bitácora de la Última Corrida (Consola)", expanded=True):
            if hay_proceso_corriendo:
                st.warning(f"⚙️ Corriendo de fondo: `{estado_global['activo']}` (Estado: {estado_global['status']})")
            elif "ERROR" in estado_sheets_upper or "FAIL" in estado_sheets_upper or "FALL" in estado_sheets_upper:
                st.error(f"❌ Corrida Finalizada con Errores.")
            elif "CANCEL" in estado_sheets_upper or "ABORT" in estado_sheets_upper:
                st.warning(f"⚠️ Corrida Cancelada.")
            elif "COMPLET" in estado_sheets_upper or "OK" in estado_sheets_upper or "EXIT" in estado_sheets_upper or "ÉXIT" in estado_sheets_upper:
                st.success(f"🟢 Corrida Finalizada con Éxito.")
            else:
                st.info(f"🟢 Corrida Finalizada (Estado: {estado_sheets}).")
            
            st.code(log_content, language="text")
    else:
        st.info("No hay registros de corridas en esta sesión en disco.")
        
    st.write("---")

    # 3. Log de Sistema Histórico Optimizado (Carga rápida por defecto)
    st.subheader("📂 Historial del Log de Sistema (Google Sheets)")
    
    # Cargamos solo 50 registros para arranque ultra-veloz
    df_log_recientes = cargar_logs_recientes(cantidad=50)
    
    if df_log_recientes.empty:
        st.info("No se detectaron registros recientes en la tabla de logs del sistema.")
    else:
        st.write("💡 *Mostrando los últimos 50 logs de sistema para optimizar la velocidad de la web.*")
        st.dataframe(df_log_recientes, use_container_width=True)
        
        # Búsqueda histórica (Lazy loading dentro de un expander para no ralentizar el inicio)
        with st.expander("🔍 Buscar Logs Históricos por Fecha (Consulta Lenta)"):
            st.info("Esta consulta descargará el historial completo desde Google Sheets para buscar por fecha.")
            if st.checkbox("Habilitar Búsqueda Histórica Completa", value=False, key="chk_buscar_logs_hist"):
                df_log_completo = cargar_datos_hoja(config.WS_LOG_SISTEMA)
                
                if not df_log_completo.empty:
                    df_log_completo["FECHA_DIA"] = df_log_completo["FECHA"].astype(str).str.slice(0, 10)
                    fechas_disponibles = sorted(df_log_completo["FECHA_DIA"].unique(), reverse=True)
                    
                    fecha_seleccionada = st.selectbox("Seleccione la Fecha para filtrar los logs:", fechas_disponibles)
                    df_log_filtrado = df_log_completo[df_log_completo["FECHA_DIA"] == fecha_seleccionada]
                    
                    if "FECHA_DIA" in df_log_filtrado.columns:
                        df_log_filtrado = df_log_filtrado.drop(columns=["FECHA_DIA"])
                        
                    st.dataframe(df_log_filtrado, use_container_width=True)
