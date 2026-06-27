# Pendientes y mejoras del sistema Inversiones

Fecha de revisión: 2026-06-27

## 1. Tareas Completadas (Sesión Actual)

- [x] **Unicidad de Fechas en Noticias (AppSheet Keys)**:
  - Re-escritas todas las fechas históricas (191 en `NOTICIAS_SISTEMA`, 270 en `NOTICIAS_DESCARTADAS` y 35 en `SUGERENCIAS_SINONIMOS`) en formato estándar `YYYY-MM-DD HH:MM:SS` aplicando segundos únicos progresivos por fila. Esto corrige el problema en AppSheet que trunca los microsegundos y generaba duplicaciones.
  - Modificados los scrapers para mantener el formato estándar y actualizado [captura_noticias.py](file:///C:/Para%20mi/Inversiones/captura_noticias.py) para inyectar una fecha única desplazada por segundos (`base_time + timedelta(seconds=idx)`) de forma secuencial en cada ejecución.
- [x] **Clave ID en Sugerencias de Sinónimos (AppSheet Selection Fix)**:
  - Agregada la columna `ID` al inicio de `SUGERENCIAS_SINONIMOS` y pobladas las 83 sugerencias históricas con códigos hash únicos de 8 caracteres.
  - Actualizados `captura_noticias.py` para generar el `sug_id` de manera dinámica usando `uuid` al escribir nuevas sugerencias.
  - Comprobado que el Step 0.5 (`pre_mantenimiento.py`) lee y re-escribe correctamente la hoja respetando la columna `ID` y actualizando estados de manera dinámica.
- [x] **Lógica de Afectación de Saldos (AppSheet / Sheets)**: Implementada automatización del saldo de caja mediante fórmulas `SUMIFS` en la hoja `CAJA_LIQUIDEZ` integrando `MOVIMIENTOS_CAJA` y `TRANSACCIONES` en tiempo real.
- [x] **Lógica de Rentabilidad Real**: Desarrollado `valorador_cartera.py` (Paso 3.8) que agrupa transacciones, calcula costos promedio ponderados, valoriza con precios de mercado y determina aportes netos y la Rentabilidad Real % de cada propietario.
- [x] **Control Programático de Brecha Cambiaria (CCL)**: Implementado un guardrail determinista en `decisor_con_ia.py` que calcula el CCL promedio del mercado y penaliza automáticamente a un score máximo de `6/10` (con nota aclaratoria) a cualquier recomendación de compra sobre un CEDEAR que cotice con más de +2.5% de sobreprecio.
- [x] **Consolidación de Supervisores**: Retirado el script obsoleto `super_decisor.py` (movido a `BUP/`) y unificadas todas sus tareas en `supervisor_del_sistema.py`.
- [x] **Robustez ante Caídas de API (Rotación de Modelos)**: Implementada rotación y fallback de modelos en el Supervisor para evitar fallos por 503/429/404, logrando autodetectar fallbacks funcionales (como `gemini-3.1-flash-lite-preview`).
- [x] **Alineación de Payload del Supervisor**: Restaurado el parámetro `"variables_mercado"` en el payload del supervisor para permitir auditorías completas cruzando indicadores macro/cambiarios con precios y noticias.
- [x] **Medición de Tiempos en Mantenimiento Maestro**: Modificado `mantenimiento_cedears_comafi.py` para medir y loguear el tiempo de ejecución en `ESTADO_PROCESOS` e inyectar de forma explícitamente el nombre de proceso original `mantenimiento_maestro` para conservar enlaces de AppSheet.
- [x] **Flujo Simplificado de Sinónimos**: Creado `pre_mantenimiento.py` como el paso 0.5 del pipeline para integrar sugerencias de sinónimos aprobados en `CONFIG_SINONIMOS` y limpiar la bandeja de entrada de `SUGERENCIAS_SINONIMOS`.
- [x] **Guardrail de Sobrecompra**: Implementada la penalización técnica automática en `decisor_con_ia.py` que limita el score a `6/10` si el RSI es mayor a 70.
- [x] **Limpieza de Prefijos y Descubrimiento Resiliente de IA**:
  - Remoción global del prefijo `"models/"` para asegurar compatibilidad total con el SDK `google-genai` y evitar errores `404 NOT_FOUND`.
  - Refactorización de `TEST/test_ia.py` (Paso 0) para evitar que modelos estándar rate-limitados (429/503) sean descartados de `modelos_activos.json`, aplicando una penalización de latencia (10.0s) para dejarlos al final de la cola.
  - Verificada la rotación automática en caliente durante el pipeline, resolviendo correctamente con `gemini-2.5-flash-lite` cuando `gemini-2.5-flash` agotó su cuota de uso.

## 2. Tareas Pendientes para Siguiente Sesión

- [ ] **Configurar Claves Virtuales en AppSheet (Evitar Falsos Ruteos)**:
  - [ ] **`REPORTE_IA`**: Crear columna virtual `CONCATENATE([FECHA], "_", [TICKER], "_", [PERFIL])` y marcarla como Key.
  - [ ] **`MATRIZ_RECOMENDACIONES`**: Crear columna virtual `CONCATENATE([TICKER], "_", [PERFIL])` y marcarla como Key.
  - [ ] **`VALORACION_PORTAFOLIO`**: Crear columna virtual `CONCATENATE([PROPIETARIO], "_", [ACTIVO])` y marcarla como Key.
  - [ ] **`CAJA_LIQUIDEZ`**: Crear columna virtual `CONCATENATE([PROPIETARIO], "_", [MONEDA], "_", [TIPO_CUENTA])` y marcarla como Key.
  - [ ] **`HISTORICO_VALORES`**: Crear columna virtual `CONCATENATE([Ticker_ID], "_", [Fecha])` y marcarla como Key (si se visualiza en la app).
- [ ] **Integración en AppSheet / Visualización de Recomendaciones**: Definir y desarrollar la forma de transferir y mostrar las acciones sugeridas por el Supervisor del Sistema (como rebalanceos de cartera, optimización de filtros, alertas de desincronización y activación de tickers inactivos) directamente en la interfaz móvil de AppSheet.
- [ ] **Integración de la Matriz de Decisión en AppSheet**: Vincular la hoja `MATRIZ_RECOMENDACIONES` a la aplicación móvil para poder visualizar de forma amigable y centralizada los veredictos históricos, scores de convicción de la IA y el sentimiento de cada activo desde el celular.
- [ ] **Corrección de Índices de Tareas en AppSheet**: Investigar y solucionar los problemas con los índices/claves de las tareas en la aplicación móvil de AppSheet para asegurar una correcta selección y ruteo.
- [ ] **Homologador y Reportes de Datos en Supervisor**: Para el proceso de inversiones, diseñar e implementar un módulo homologador de activos/tickers y habilitar la generación estructurada de reportes de datos de cartera dentro de la ejecución del Supervisor.

## 3. Ideas y Mejoras Futuras
- **Integración Móvil en AppSheet**:
  - Diseñar interfaces amigables para cargar transacciones rápidamente desde el celular.
  - Generar gráficos interactivos en el dashboard de AppSheet sobre la evolución patrimonial.
