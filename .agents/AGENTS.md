# Reglas y Estándares del Proyecto Inversiones

Este archivo contiene las directrices obligatorias para el asistente de IA (Antigravity). Estas reglas se cargan automáticamente en cada sesión.

## 1. Reglas Críticas de Interacción y Modificación
- **Autorización Obligatoria**: Queda terminantemente prohibido modificar, crear o eliminar sin consentimiento. Explicar el impacto detalladamente.
- **Visualización de Planes**: Es OBLIGATORIO que los Planes de Implementación se muestren y expliquen en el chat principal.
- **Cero Suposiciones**: Si una petición es ambigua, detenerse y preguntar.
- **Rol de Ingeniero Experto**: Analizar el sistema para sugerir mejoras arquitectónicas, optimizaciones y detectar bugs.

## 2. Estándares del Código (Python 3.10+)
- **Encapsulación**: La lógica principal debe residir en funciones ejecutables.
- **Configuración Centralizada**: Ningún string harcodeado de Google Sheets. Todo va a `config.py`.
- **Manejo de Errores**: Usar bloques `try/except` en APIs externas y loguear.

## 3. Integración con Google Sheets y Streamlit (Performance)
- **Validación Estricta**: Consultar `ESTRUCTURA_SHEETS.md` antes de modificar bases de datos.
- **Performance Web (Caché Obligatorio)**: Para evitar bloqueos, es imperativo usar `@st.cache_data` o `@st.cache_resource` al interactuar con Sheets. Queda prohibido usar `st.cache_data.clear()` a nivel global; se exige la limpieza granular (ej: `cargar_datos_hoja.clear("LOG_SISTEMA")`).
- **Renderizado Eficiente**: No abusar de `st.rerun()`. Utilizar `@st.fragment` (si Streamlit 1.37+) para actualizar métricas en tiempo real sin recargar la página entera.
- **Íconos y Formatos**: Usar etiquetas de Streamlit (`:material/...:`) SOLO en el frontend. Si se guardan datos en Sheets, logs `.txt`, reportes `.md` o `.json`, utilizar estricamente Emojis Unicode (`✅`, `🤖`, `📊`) para evitar errores de parseo externo.
- **Archivos Temporales y Git**: Los reportes generados o logs en JSON deben depositarse en directorios que estén ignorados por `.gitignore` (ej: `ESTRATEGIA_REPORTS/`) para no inflar el repositorio. Además, las tablas de sistema no formales deben limpiarse periódicamente.

## 4. Gestión de Commits y Secretos
- **Commits**: Usar el formato: `tipo: descripción breve`.
- **Seguridad**: Nunca subir secretos o `.env` al repositorio.
