import streamlit as st
import sys
import os
import subprocess
import threading
import time
from pathlib import Path
import pandas as pd
import plotly.express as px
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

# Verificar de forma segura si el proceso de fondo ya terminó
if estado_global["objeto"] is not None:
    exit_code = estado_global["objeto"].poll()
    if exit_code is not None:
        estado_global["activo"] = None
        estado_global["objeto"] = None
        if exit_code == 0:
            estado_global["status"] = "Finalizado con éxito"
        else:
            estado_global["status"] = f"Error en Último Proceso (Código {exit_code})"

# Inicialización de banderas de ejecución locales de sesión
if "ejecutar_script" not in st.session_state:
    st.session_state["ejecutar_script"] = None

# --- 2. SELECTOR DE TEMAS VISUALES EN LA BARRA LATERAL ---
st.sidebar.title("🎨 Personalización")
tema_visual = st.sidebar.selectbox(
    "Seleccione el Tema Visual:",
    ["Azul Nórdico", "Esmeralda Nórdica", "Gris Nórdico"]
)

# Inyección de CSS según el tema (Sin hover, solapas grandes, botones densos y oscuros)
if tema_visual == "Esmeralda Nórdica":
    st.markdown("""
        <style>
        .stApp {
            background-color: #F4F7F6;
            color: #1B4332;
            font-family: 'Inter', sans-serif;
        }
        div[data-testid="stMetricValue"] {
            color: #2D6A4F;
            font-size: 2rem;
            font-weight: bold;
        }
        .stButton>button {
            background-color: #D8F3DC;
            color: #1B4332;
            font-size: 1.05rem;
            border-radius: 8px;
            border: 2px solid #B7E4C7;
            font-weight: 800;
            width: 100%;
        }
        /* Estilos para pestañas superiores más grandes y gruesas */
        button[data-testid="stBaseButton-tab"] p, div[data-testid="stTabBar"] button p {
            font-size: 1.45rem !important;
            font-weight: 800 !important;
            color: #1B4332 !important;
        }
        </style>
    """, unsafe_allow_html=True)
elif tema_visual == "Gris Nórdico":
    st.markdown("""
        <style>
        .stApp {
            background-color: #F3F4F6;
            color: #1F2937;
            font-family: 'Inter', sans-serif;
        }
        div[data-testid="stMetricValue"] {
            color: #374151;
            font-size: 2rem;
            font-weight: bold;
        }
        .stButton>button {
            background-color: #E5E7EB;
            color: #111827;
            font-size: 1.05rem;
            border-radius: 6px;
            border: 2px solid #D1D5DB;
            font-weight: 800;
            width: 100%;
        }
        /* Estilos para pestañas superiores más grandes y gruesas */
        button[data-testid="stBaseButton-tab"] p, div[data-testid="stTabBar"] button p {
            font-size: 1.45rem !important;
            font-weight: 800 !important;
            color: #374151 !important;
        }
        </style>
    """, unsafe_allow_html=True)
elif tema_visual == "Azul Nórdico":
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
            [python_exe, target_script],
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

@st.cache_data(ttl=300)
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

# Cargador específico para la tabla Semáforo con refresco rápido (10 segundos)
@st.cache_data(ttl=10)
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

# Pintar el semáforo lateral
estado_sheets_upper = estado_sheets.upper()

if hay_proceso_corriendo:
    st.sidebar.warning(f"⚙️ Corriendo de fondo:\n`{estado_global['activo']}`")
elif "ERROR" in estado_sheets_upper or "FAIL" in estado_sheets_upper or "FALL" in estado_sheets_upper:
    st.sidebar.error(f"❌ Error en Pipeline:\n{detalle_sheets[:60]}")
elif "CANCEL" in estado_sheets_upper or "ABORT" in estado_sheets_upper:
    st.sidebar.error(f"⚠️ Pipeline Cancelado")
elif "COMPLET" in estado_sheets_upper or "OK" in estado_sheets_upper or "EXIT" in estado_sheets_upper or "ÉXIT" in estado_sheets_upper:
    st.sidebar.success(f"✅ Pipeline Completado con Éxito")
else:
    st.sidebar.info("🟢 Sistema Listo / Libre")

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

# Procesar disparos
if st.session_state["ejecutar_script"] is not None:
    script_a_disparar = st.session_state["ejecutar_script"]
    st.session_state["ejecutar_script"] = None
    disparar_proceso_fondo(script_a_disparar)
    st.rerun()

# --- 6. APLICACIÓN PRINCIPAL ---

st.title("📈 Panel de Control de Inversiones con IA")
st.write("---")

# Crear pestañas principales (Consola de Logs al final)
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Resumen de Cartera", 
    "📋 Reportes del Supervisor", 
    "✏️ Administrar Datos (Sheets)",
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
            df_val["VALOR_ACTUAL"] = pd.to_numeric(df_val["VALOR_ACTUAL"], errors='coerce').fillna(0.0)
        if "RENTABILIDAD_NOMINAL" in df_val:
            df_val["RENTABILIDAD_NOMINAL"] = pd.to_numeric(df_val["RENTABILIDAD_NOMINAL"], errors='coerce').fillna(0.0)
            
    if not df_caja.empty:
        tiene_datos = True
        if "SALDO" in df_caja:
            df_caja["SALDO"] = pd.to_numeric(df_caja["SALDO"], errors='coerce').fillna(0.0)

    if not tiene_datos:
        st.warning("No se pudieron cargar datos del portafolio o de caja desde Sheets en este momento. Intente presionar 'Refrescar Datos' en la Consola.")
    else:
        total_valuacion_cedears = df_val["VALOR_ACTUAL"].sum() if not df_val.empty and "VALOR_ACTUAL" in df_val else 0.0
        total_saldos_caja = df_caja["SALDO"].sum() if not df_caja.empty and "SALDO" in df_caja else 0.0
        patrimonio_neto = total_valuacion_cedears + total_saldos_caja
        
        # Tarjetas Métricas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Patrimonio Neto Est. (ARS)", f"${patrimonio_neto:,.2f}")
        with col2:
            st.metric("Valuación CEDEARs (ARS)", f"${total_valuacion_cedears:,.2f}")
        with col3:
            st.metric("Efectivo Total Caja (ARS)", f"${total_saldos_caja:,.2f}")
        
        st.write("---")
        
        g1, g2 = st.columns(2)
        with g1:
            if not df_val.empty and "VALOR_ACTUAL" in df_val and "TICKER" in df_val:
                st.subheader("Distribución de Cartera por Activo")
                fig_pie = px.pie(
                    df_val, 
                    values="VALOR_ACTUAL", 
                    names="TICKER", 
                    title="Distribución de Tenencias",
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Gráfico de tenencias no disponible.")
            
        with g2:
            if not df_val.empty and "RENTABILIDAD_NOMINAL" in df_val and "TICKER" in df_val:
                st.subheader("Rentabilidad Real por Ticker")
                fig_bar = px.bar(
                    df_val,
                    x="TICKER",
                    y="RENTABILIDAD_NOMINAL",
                    title="Rentabilidad Nominal en ARS",
                    color="RENTABILIDAD_NOMINAL",
                    color_continuous_scale=px.colors.diverging.RdYlGn
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("Gráfico de rentabilidad no disponible.")
        
        if not df_val.empty:
            st.subheader("Tenencias Consolidadas en Sheets")
            st.dataframe(df_val, use_container_width=True)

# ==========================================
# PESTAÑA 2: REPORTES DEL SUPERVISOR
# ==========================================
with tab2:
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
# PESTAÑA 3: ADMINISTRAR DATOS (SHEETS)
# ==========================================
with tab3:
    st.header("✏️ Editor de Planillas en Google Sheets")
    st.write("Edita directamente las celdas haciendo doble clic y presiona Guardar al terminar:")
    
    tabla_a_editar = st.selectbox("Seleccione la hoja a modificar:", ["TRANSACCIONES", "MOVIMIENTOS_CAJA", "SUGERENCIAS_SINONIMOS"])
    
    sh_edit = obtener_conexion_sheets()
    if sh_edit:
        try:
            ws_edit = sh_edit.worksheet(tabla_a_editar)
            raw_data = ws_edit.get_all_records()
            df_edit = pd.DataFrame(raw_data)
            
            df_modificado = st.data_editor(
                df_edit, 
                num_rows="dynamic", 
                use_container_width=True,
                key=f"editor_{tabla_a_editar}"
            )
            
            if st.button(f"💾 Guardar cambios en {tabla_a_editar}"):
                with st.spinner("Guardando en Google Sheets..."):
                    try:
                        ws_edit.clear()
                        cabeceras = [df_modificado.columns.tolist()]
                        valores = df_modificado.values.tolist()
                        valores_limpios = [[str(x) if pd.notna(x) else "" for x in row] for row in valores]
                        
                        ws_edit.update('A1', cabeceras + valores_limpios)
                        st.success(f"¡Cambios guardados exitosamente en la hoja `{tabla_a_editar}`!")
                        st.cache_data.clear()
                    except Exception as ex:
                        st.error(f"Error al escribir en Google Sheets: {ex}")
        except Exception as e:
            st.error(f"Error al conectar con la hoja `{tabla_a_editar}`: {e}")

# ==========================================
# PESTAÑA 4: CONSOLA DE LOGS (ESTADO Y LOG HISTÓRICO CON BOTÓN MANUAL)
# ==========================================
with tab4:
    st.header("💻 Consola de Procesos e Integridad")
    
    col_ref1, col_ref2 = st.columns([8, 2])
    with col_ref2:
        if st.button("🔄 Refrescar Datos", key="btn_refresh_logs_tab"):
            st.cache_data.clear()
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
            with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
                log_content = f.read()
        except Exception:
            pass
            
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

    # 3. Log de Sistema Histórico con Filtro por Fecha
    st.subheader("📂 Historial del Log de Sistema (Google Sheets)")
    
    df_log_completo = cargar_datos_hoja(config.WS_LOG_SISTEMA)
    
    if df_log_completo.empty:
        st.info("No se detectaron registros en la tabla de logs del sistema. Presiona 'Refrescar Datos'.")
    else:
        df_log_completo["FECHA_DIA"] = df_log_completo["FECHA"].astype(str).str.slice(0, 10)
        fechas_disponibles = sorted(df_log_completo["FECHA_DIA"].unique(), reverse=True)
        
        fecha_seleccionada = st.selectbox("Seleccione la Fecha para filtrar los logs:", fechas_disponibles)
        
        df_log_filtrado = df_log_completo[df_log_completo["FECHA_DIA"] == fecha_seleccionada]
        
        if "FECHA_DIA" in df_log_filtrado.columns:
            df_log_filtrado = df_log_filtrado.drop(columns=["FECHA_DIA"])
            
        st.dataframe(df_log_filtrado, use_container_width=True)
