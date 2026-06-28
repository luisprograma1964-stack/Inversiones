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

## 2. Tareas Pendientes para Siguiente Sesión

- [ ] **Integración en AppSheet / Visualización de Recomendaciones**: Definir y desarrollar la forma de transferir y mostrar las acciones sugeridas por el Supervisor del Sistema (como rebalanceos de cartera, optimización de filtros, alertas de desincronización y activación de tickers inactivos) directamente en la interfaz móvil de AppSheet.
- [ ] **Integración de la Matriz de Decisión en AppSheet**: Vincular la hoja `MATRIZ_RECOMENDACIONES` a la aplicación móvil para poder visualizar de forma amigable y centralizada los veredictos históricos, scores de convicción de la IA y el sentimiento de cada activo desde el celular.

### Recordatorios Personales del Usuario (Otros Sistemas)
- [ ] **Corrección de Índices en Solapa 'Tareas' (Otra App)**: Resolver el problema con las Keys/índices en la tabla de tareas de tu otra aplicación de AppSheet para evitar que la aplicación navegue a filas incorrectas al hacer clic.

## 3. Ideas y Mejoras Futuras

- **Integración Móvil en AppSheet**:
  - Diseñar interfaces amigables para cargar transacciones rápidamente desde el celular.
  - Generar gráficos interactivos en el dashboard de AppSheet sobre la evolución patrimonial.
