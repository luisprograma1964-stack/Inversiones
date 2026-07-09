# Estándares de Programación - Proyecto Inversiones

Este documento define las reglas, estructuras y buenas prácticas para mantener la coherencia en todos los scripts de Python del proyecto.

## 1. Estructura de los Scripts y Ejecución
Para permitir que los scripts se puedan ejecutar tanto de forma independiente como orquestados desde un script maestro:
- Todo el código principal debe estar encapsulado en una función principal (ej: `def ejecutar_proceso():`).
- Al final de cada archivo, se debe incluir el bloque de ejecución estándar:
  ```python
  if __name__ == "__main__":
      ejecutar_proceso()
  ```

## 2. Configuración Centralizada
- Toda constante, nombre de hoja (Worksheet), nombre de archivo o variable global debe residir en `config.py`.
- No deben existir strings "quemados" (hardcodeados) en el código referentes a nombres de hojas.

## 3. Sistema de Logs y Reportes
Todo evento importante, advertencia o error debe registrarse centralizadamente usando la función `procesamiento.registrar_log`.
- **Estructura en Sheets**: `[Fecha/Hora, Nivel, Origen, Mensaje]`
- **Formatos de Texto**: Los archivos `.md` o `.json` generados como reportes (ej. Supervisor) NO deben utilizar etiquetas exclusivas de Streamlit (`:material/...:`). En su lugar, se exige el uso de **Emojis Unicode** (✅, 🤖, ⚠️) para garantizar compatibilidad multiplataforma.
- **Git Ignore y Limpieza**: Todo archivo `.json`, `.md` autogenerado o log efímero debe almacenarse en un directorio ignorado por Git (ej. `ESTRATEGIA_REPORTS/`). Las tablas no formales en Google Sheets deben limpiarse cada 30 días.

## 4. Estado de Procesos (ESTADO_PROCESOS)
Los scripts que corren periódicamente deben actualizar su estado para monitoreo (semáforos) usando `procesamiento.actualizar_estado_proceso`.

## 5. Manejo de Fechas y Horas
- Formato estándar estricto de Fecha: ISO `YYYY-MM-DD`.
- Formato de Fecha/Hora: `YYYY-MM-DD HH:MM:SS`.

## 6. Conexión a Base de Datos (Google Sheets) y AppSheet
- **Desuso de AppSheet**: Se elimina oficialmente la regla de utilizar columnas de ID / UUID generados artificialmente en la columna A. Google Sheets y Pandas nativamente manejan los datetimes precisos para cruces.
- **Validación Estricta**: Antes de leer o escribir, es obligatorio consultar `ESTRUCTURA_SHEETS.md`.

## 7. Performance Web (Streamlit y Caché)
- **Uso Obligatorio de Caché**: Todo llamado a Google Sheets o APIs lentas DEBE usar `@st.cache_data` o `@st.cache_resource` en la medida de las posibilidades.
- **Borrados Granulares**: Está prohibido el uso masivo de `st.cache_data.clear()` que provoque latencia extrema al usuario. Utilizar siempre el borrado parametrizado (ej. `cargar_datos_hoja.clear("REPORTE_IA")`).
- **Recargas Selectivas**: Evitar abusar de `st.rerun()`. Priorizar redibujados localizados y usar `@st.fragment` (en Streamlit 1.37+) para aislar métricas en tiempo real de la página principal.

## 8. Manejo de Errores y Docstrings
- Los errores capturados deben enviarse al log.
- Todo programa y función compleja debe tener docstrings y comentarios de paso a paso.

## 9. Reglas Estrictas para el Asistente (IA)
- **Cero Suposiciones:** Si el requerimiento es ambiguo, detenerse y hacer preguntas.
- **Validación de Estructura:** Consultar `ESTRUCTURA_SHEETS.md` antes de modificar flujos de datos.

## 10. Lectura de Datos y Formatos (UNFORMATTED_VALUE)
- **Datos Puros:** Al extraer informacin numrica o de fechas de Google Sheets usando gspread, est ESTRICTAMENTE PROHIBIDO leer los datos con su formato visual (ej. $1,234.00). 
- **Implementacin:** El script uth_google.py ya inyecta por defecto el parmetro alue_render_option='UNFORMATTED_VALUE' en todas las llamadas a get_all_values(), get_all_records() y get(). Todo nuevo script debe respetar esta metodologa y no intentar parsear strings manualmente a menos que sea inevitable.
