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
    </style>
""", unsafe_allow_html=True)

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

@st.cache_data
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
@st.cache_data
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
@st.cache_data(ttl=300)
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

# --- 5. BARRA LATERAL (SEMÁFORO SINCRONIZADO CON SHEETS) ---
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
if st.sidebar.button("🔄 Refrescar Datos Generales", key="sidebar_global_refresh_btn", help="Fuerza la descarga completa de todas las planillas de Google Sheets para actualizar todo el panel de control."):
    st.cache_data.clear()
    st.rerun()

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
            activo_velas = st.selectbox("Seleccione el Activo para graficar:", sorted(lista_activos_velas), key="select_velas_active")
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
            lista_tickers_disponibles = lista_tickers
            
        ticker = st.selectbox("Activo (Ticker):", lista_tickers_disponibles)
        
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
                ws_ops = sh_ops.worksheet(tabla_ops_elegida)
                raw_ops = ws_ops.get_all_records()
                df_ops = pd.DataFrame(raw_ops)
                
                df_ops_mod = st.data_editor(
                    df_ops, 
                    num_rows="dynamic", 
                    use_container_width=True,
                    key=f"editor_ops_{tabla_ops_elegida}"
                )
                
                if st.button(f"💾 Guardar cambios en {tabla_ops_elegida}", key=f"btn_save_ops_{tabla_ops_elegida}"):
                    with st.spinner("Actualizando planilla en Google Sheets..."):
                        try:
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
    st.write("Visualiza las recomendaciones de inversión (Comprar/Vender/Mantener) generadas por los perfiles del Decisor:")
    
    df_matriz = cargar_datos_hoja(config.WS_MATRIZ_RECOMENDACIONES)
    
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
                        ws_ia.update(values=[nueva_fila], range_name="A2:Z2")
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
                ws_param = sh_param.worksheet("CONFIG_TELEGRAM_CHANNELS")
                raw_param = ws_param.get_all_records()
                df_tg = pd.DataFrame(raw_param)
                
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
        st.write("Cuando la IA captura una noticia y encuentra un término desconocido, el supervisor te propone asociarlo a un Ticker. Apruébalo aquí para que se auto-cargue en las próximas lecturas:")
        
        if sh_param:
            try:
                ws_sug = sh_param.worksheet("SUGERENCIAS_SINONIMOS")
                raw_sug = ws_sug.get_all_records()
                df_sug = pd.DataFrame(raw_sug)
                
                if df_sug.empty:
                    st.success("🎉 ¡No hay sugerencias registradas!")
                else:
                    df_sug.columns = [c.strip().upper() for c in df_sug.columns]
                    df_pendientes = df_sug[df_sug['ESTADO'].astype(str).str.strip().str.upper() == "PENDIENTE"]
                    
                    if df_pendientes.empty:
                        st.success("🎉 ¡No hay sugerencias de sinónimos pendientes de aprobación!")
                    else:
                        st.write(f"Tienes **{len(df_pendientes)}** sugerencias pendientes de revisión:")
                        st.dataframe(df_pendientes[['FECHA', 'TITULAR', 'TERMINO_SUGERIDO', 'TICKER_SUGERIDO', 'EXPLICACION']], use_container_width=True)
                        
                        decisiones_usuario = {}
                        st.write("---")
                        st.subheader("✍️ Tomar Decisiones sobre Sinónimos")
                        
                        for idx, row in df_pendientes.iterrows():
                            sug_id = row['ID']
                            termino = row['TERMINO_SUGERIDO']
                            ticker_prop = row['TICKER_SUGERIDO']
                            explicacion = row['EXPLICACION']
                            
                            st.markdown(f"**Asociar:** `{termino}` ➔ Ticker `{ticker_prop}`")
                            st.markdown(f"*Motivo:* {explicacion}")
                            
                            dec = st.selectbox(
                                "Acción a realizar:", 
                                ["Dejar Pendiente", "Aprobar (SI)", "Rechazar (NO)"], 
                                key=f"sel_dec_sin_{sug_id}"
                            )
                            decisiones_usuario[sug_id] = (termino, ticker_prop, dec)
                            st.markdown("---")
                            
                        if st.button("💾 Aplicar Aprobaciones de Sinónimos", key="btn_apply_synonyms"):
                            with st.spinner("Procesando decisiones en Google Sheets..."):
                                try:
                                    ws_sin = sh_param.worksheet("CONFIG_SINONIMOS")
                                    raw_sin = ws_sin.get_all_records()
                                    df_sin = pd.DataFrame(raw_sin)
                                    df_sin.columns = [c.strip().upper() for c in df_sin.columns]
                                    
                                    # Mapeo en diccionario para buscar y editar rápido
                                    sinonimos_dict = {}
                                    for _, r in df_sin.iterrows():
                                        sinonimos_dict[str(r['TICKER']).strip().upper()] = str(r['SINONIMOS']).strip()
                                        
                                    # Procesar decisiones en memoria
                                    cambio_sugerencias = False
                                    cambio_sinonimos = False
                                    
                                    # Actualizar estados de SUGERENCIAS_SINONIMOS
                                    raw_sug_rows = ws_sug.get_all_values()
                                    headers_sug = [h.strip().upper() for h in raw_sug_rows[0]]
                                    id_col_idx = headers_sug.index("ID") + 1
                                    estado_col_idx = headers_sug.index("ESTADO") + 1
                                    
                                    for sug_id, (termino, ticker_prop, dec) in decisiones_usuario.items():
                                        if dec == "Dejar Pendiente":
                                            continue
                                            
                                        # Buscar fila en Sheets por ID
                                        row_number = None
                                        for r_idx, r_val in enumerate(raw_sug_rows[1:], start=2):
                                            if r_val[id_col_idx - 1] == sug_id:
                                                row_number = r_idx
                                                break
                                                
                                        if not row_number:
                                            continue
                                            
                                        if dec == "Aprobar (SI)":
                                            # Modificar o añadir en CONFIG_SINONIMOS
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
                                            
                                        elif dec == "Rechazar (NO)":
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
                ws_param = sh_param.worksheet(tabla_elegida)
                raw_param = ws_param.get_all_records()
                df_param = pd.DataFrame(raw_param)
                
                df_param_mod = st.data_editor(
                    df_param, 
                    num_rows="dynamic", 
                    use_container_width=True,
                    key=f"editor_param_grilla_{tabla_elegida}"
                )
                
                if st.button(f"💾 Guardar cambios en {tabla_elegida}", key=f"btn_save_param_grilla_{tabla_elegida}"):
                    with st.spinner("Escribiendo datos en Google Sheets..."):
                        try:
                            ws_param.clear()
                            cabeceras = [df_param_mod.columns.tolist()]
                            valores = df_param_mod.values.tolist()
                            valores_limpios = [[str(x) if pd.notna(x) else "" for x in row] for row in valores]
                            
                            ws_param.update(values=cabeceras + valores_limpios, range_name='A1', value_input_option='USER_ENTERED')
                            st.success(f"¡Cambios guardados en la tabla paramétrica `{tabla_elegida}`!")
                            st.cache_data.clear()
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
            st.rerun()
            
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
            df_log_completo = cargar_datos_hoja(config.WS_LOG_SISTEMA)
            
            if not df_log_completo.empty:
                df_log_completo["FECHA_DIA"] = df_log_completo["FECHA"].astype(str).str.slice(0, 10)
                fechas_disponibles = sorted(df_log_completo["FECHA_DIA"].unique(), reverse=True)
                
                fecha_seleccionada = st.selectbox("Seleccione la Fecha para filtrar los logs:", fechas_disponibles)
                df_log_filtrado = df_log_completo[df_log_completo["FECHA_DIA"] == fecha_seleccionada]
                
                if "FECHA_DIA" in df_log_filtrado.columns:
                    df_log_filtrado = df_log_filtrado.drop(columns=["FECHA_DIA"])
                    
                st.dataframe(df_log_filtrado, use_container_width=True)
