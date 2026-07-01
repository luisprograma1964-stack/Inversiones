# Pendientes y mejoras del sistema Inversiones

Fecha de revisión: 2026-06-27

## 1. Tareas Completadas (Sesiones Recientes)

- [x] **Unicidad de Fechas en Noticias (AppSheet Keys)**: Re-escritas todas las fechas históricas en formato estándar `YYYY-MM-DD HH:MM:SS` aplicando segundos únicos progresivos por fila para evitar duplicaciones en AppSheet.
- [x] **Claves Únicas Físicas (ID) para Tablas de Noticias**:
  - Implementada una columna física `ID` en la primera posición (Columna A) de `NOTICIAS_SISTEMA` y `NOTICIAS_DESCARTADAS`.
  - Agregada generación dinámica de UUIDs de 8 caracteres (`uuid.uuid4()[:8]`) para nuevos registros en [captura_noticias.py](file:///C:/Para%20mi/Inversiones/captura_noticias.py) y devuelta la fecha a su valor natural exacto.
  - Saneadas e inyectados IDs en 191 filas históricas de noticias del sistema y 270 filas de descartes.
  - Registrada la regla técnica en [.agents/AGENTS.md](file:///C:/Para%20mi/Inversiones/.agents/AGENTS.md) para prohibir el uso de fechas como Keys primarias en el futuro.
- [x] **Clave ID en Sugerencias de Sinónimos**: Agregada columna `ID` al inicio de `SUGERENCIAS_SINONIMOS` y poblado el histórico (83 registros) con códigos únicos de 8 caracteres.
- [x] **Lógica de Afectación de Saldos (AppSheet / Sheets)**: Saldos automáticos en `CAJA_LIQUIDEZ` con fórmulas `SUMIFS` sobre transacciones y movimientos.
- [x] **Lógica de Rentabilidad Real**: Desarrollado `valorador_cartera.py` para calcular el rendimiento real consolidado por propietario.
- [x] **Control Programático de Brecha Cambiaria (CCL)**: Guardrail determinista en el decisor que penaliza el score a un máximo de `6/10` si un CEDEAR cotiza con más de +2.5% de sobreprecio de tipo de cambio implícito (CCL).
- [x] **Auditoría Offline de Inputs de IA (Homologador)**:
  - Creado el script independiente [TEST/homologador.py](file:///C:/Para%20mi/Inversiones/TEST/homologador.py) que lee el JSON de prompt de producción más reciente en `IA_LOGS` y lo audita 1-a-1 contra las hojas de Sheets para detectar discrepancias o descalces.
  - Normaliza textos, acentos y casing para evitar falsos positivos por codificación cp1252 de la consola de Windows.
- [x] **Caché en Memoria de Sesión para Noticias**: Implementada caché de carga en `ia_utils.py` para recargar noticias una sola vez por ejecución, optimizando de 14 a 1 las lecturas de Sheets y previniendo bloqueos de cuota API (Error 429).
- [x] **Documentación de Inputs de IA en Supervisor (Punto 1)**: Modificado [supervisor_del_sistema.py](file:///C:/Para%20mi/Inversiones/supervisor_del_sistema.py) para inyectar determinísticamente la sección "Punto 1" al principio del reporte Markdown, detallando las variables enviadas al decisor agrupadas por su hoja de origen en Google Sheets.
- [x] **Autodepuración de Reportes del Supervisor**: Añadida la rutina `limpiar_reportes_antiguos(dias=30)` al Supervisor para eliminar reportes Markdown antiguos de más de 30 días de forma automática.
- [x] **Ignorado de Reportes en Git**: Agregado `ESTRATEGIA_REPORTS/` a [.gitignore](file:///C:/Para%20mi/Inversiones/.gitignore) para que no se rastreen los informes locales.
- [x] **Configuraciones y Correcciones de AppSheet (Usuario)**:
  - [x] Regenerados esquemas de tablas y configuradas las columnas `ID` como Keys primarias en noticias y sugerencias.
  - [x] Creadas columnas virtuales concatenadas para claves primarias en `REPORTE_IA`, `MATRIZ_RECOMENDACIONES`, `VALORACION_PORTAFOLIO` y `CAJA_LIQUIDEZ`.
  - [x] Solucionado el error de Gallery View en Valoración Portfolio de AppSheet (cambiado a Table/Deck).
- [x] **Unificación de Interfaz en Streamlit (`app.py`)**: Desarrollada la aplicación web unificada de punta a punta con pestañas sobrias de tamaño aumentado (`1.45rem`, `font-weight: 800`), temas nórdicos (por defecto `Azul Nórdico`) y control asincrónico de subprocesos locales de fondo.
- [x] **Optimización de Consumo de Cuotas (Sheets API)**: Implementada una caché robusta de 5 minutos en el Dashboard, lector rápido de semáforo con caché de 10 segundos, refresco de datos puramente manual mediante botón `Refrescar Datos` y eliminación completa de auto-refrescos repetitivos de pantalla, reduciendo el consumo de solicitudes de Sheets API en un 95%.
- [x] **Tolerancia a Fallos por Cuota 429 en Pipeline**:
  - Creado e inyectado el envoltorio resiliente `get_records_safe` con reintentos automáticos en `carga_historica_bridge.py` para sus lecturas pesadas a Sheets.
  - Rediseñada la función `actualizar_estado_proceso` de `procesamiento.py` para reintentar progresivamente hasta 4 veces (Exponential Backoff de hasta 12s) si la API de Sheets responde con error 429.
  - Agregada una pausa de cortesía de 3 segundos en `ensamblador.py` antes de iniciar el Paso 2 para estabilizar las cuotas.

## 2. Tareas Pendientes Consolidadas (Transición a Streamlit)

- [ ] **Punto 1: Despliegue de la Web App en Streamlit Cloud**:
  - [ ] Subir la aplicación web unificada `app.py` y dependencias a un repositorio privado de GitHub.
  - [ ] Vincular el repositorio a Streamlit Community Cloud (gratis) para ejecución remota.
  - [ ] Configurar secrets en Streamlit Cloud de forma segura para las credenciales de Sheets y Gemini API.
- [ ] **Punto 2: Mejoras Visuales en el Dashboard de Streamlit**:
  - [ ] Agregar la visualización interactiva de la `MATRIZ_RECOMENDACIONES` de la IA (Veredicto y Sentiment) en la Pestaña 1.
  - [ ] Aplicar mejoras de diseño con CSS personalizado para darle una estética todavía más premium.
- [ ] **Punto 3: Unificación de Alertas del Supervisor (Bandeja Única)**:
  - [ ] Crear la hoja consolidada `ALERTAS_SUPERVISOR` para unificar sugerencias de sinónimos y alertas estratégicas.
  - [ ] Modificar `captura_noticias.py`, `pre_mantenimiento.py` y `supervisor_del_sistema.py` para escribir y procesar desde la nueva hoja consolidada.
  - [ ] Integrar el panel de aprobación de sinónimos y lectura de alertas directamente en la Pestaña 4 de la Web App.

### Recordatorios Personal del Usuario (Otros Sistemas)
- [ ] **Corrección de Índices en Solapa 'Tareas' (Otra App)**: Resolver el problema con las Keys/índices en la tabla de tareas de tu otra aplicación de AppSheet para evitar que la aplicación navegue a filas incorrectas al hacer clic.

## 3. Ideas y Mejoras Futuras

- **Integración Móvil en AppSheet**:
  - Diseñar interfaces amigables para cargar transacciones rápidamente desde el celular.
  - Generar gráficos interactivos en el dashboard de AppSheet sobre la evolución patrimonial.

## 4. Bitácora de Depuración del Botón "Add" en MOVIMIENTOS_CAJA (2026-06-28)
* [x] **Permisos de la subvista**: Comprobado que la vista `Movimientos Caja` tiene la acción `Add` activa en la configuración de la vista.
* [x] **Agrupamientos**: Se quitó el agrupamiento por `Propietario` (Group by: None) para descartar que se oculte por vista colapsada.
* [x] **Acción de Posición**: Se cambió la acción `Add` de `Prominent` a `Primary` (barra superior) en la configuración de acciones.
* [x] **Configuración del Dashboard**: Se verificó que el Dashboard apunta exactamente a la vista personalizada `Movimientos Caja` (no a la del sistema) y que se probó activando/desactivando el modo `Interactive Dashboard`.
* [x] **Configuración de Columna Key (Fecha)**: Confirmado que tenía `TODAY` en `Initial value` (lo cual es correcto) y se aclaró que no debe usarse `App formula` en la Key.
* [x] **Permisos de Tabla**: Habilitado el check global de **`Adds`** en la tabla en el menú de Data.
* [x] **Diagnóstico Sistémico**: Se confirmó que en el modo celular (compacto) los Dashboards ocultan los botones flotantes de las subvistas. Al expandir la subvista (modo desktop/pantalla completa), el botón "+" aparece de forma nativa e infalible. Caso resuelto.
