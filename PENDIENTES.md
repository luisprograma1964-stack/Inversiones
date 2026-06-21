# Pendientes y mejoras del sistema Inversiones

Fecha de revisión: 2026-06-21

## 1. Tareas Completadas (Sesión Actual)

- [x] **Lógica de Afectación de Saldos (AppSheet / Sheets)**: Implementada automatización del saldo de caja mediante fórmulas `SUMIFS` en la hoja `CAJA_LIQUIDEZ` integrando `MOVIMIENTOS_CAJA` y `TRANSACCIONES` en tiempo real.
- [x] **Lógica de Rentabilidad Real**: Desarrollado `valorador_cartera.py` (Paso 3.8) que agrupa transacciones, calcula costos promedio ponderados, valoriza con precios de mercado y determina aportes netos y la Rentabilidad Real % de cada propietario.
- [x] **Control Programático de Brecha Cambiaria (CCL)**: Implementado un guardrail determinista en `decisor_con_ia.py` que calcula el CCL promedio del mercado y penaliza automáticamente a un score máximo de `6/10` (con nota aclaratoria) a cualquier recomendación de compra sobre un CEDEAR que cotice con más de +2.5% de sobreprecio.
- [x] **Consolidación de Supervisores**: Retirado el script obsoleto `super_decisor.py` (movido a `BUP/`) y unificadas todas sus tareas en `supervisor_del_sistema.py`.
- [x] **Robustez ante Caídas de API (Rotación de Modelos)**: Implementada rotación y fallback de modelos en el Supervisor para evitar fallos por 503/429/404, logrando autodetectar fallbacks funcionales (como `gemini-3.1-flash-lite-preview`).
- [x] **Alineación de Payload del Supervisor**: Restaurado el parámetro `"variables_mercado"` en el payload del supervisor para permitir auditorías completas cruzando indicadores macro/cambiarios con precios y noticias.
- [x] **Medición de Tiempos en Mantenimiento Maestro**: Modificado `mantenimiento_cedears_comafi.py` para medir y loguear el tiempo de ejecución en `ESTADO_PROCESOS` e inyectar de forma explícitamente el nombre de proceso original `mantenimiento_maestro` para conservar enlaces de AppSheet.
- [x] **Flujo Simplificado de Sinónimos**: Creado `pre_mantenimiento.py` como el paso 0.5 del pipeline para incorporar sugerencias de sinónimos aprobados en `CONFIG_SINONIMOS` y limpiar la bandeja de entrada de `SUGERENCIAS_SINONIMOS`.
- [x] **Guardrail de Sobrecompra**: Implementada la penalización técnica automática en `decisor_con_ia.py` que limita el score a `6/10` si el RSI es mayor a 70.
- [x] **Limpieza de Prefijos y Descubrimiento Resiliente de IA**:
  - Remoción global del prefijo `"models/"` para asegurar compatibilidad total con el SDK `google-genai` y evitar errores `404 NOT_FOUND`.
  - Refactorización de `TEST/test_ia.py` (Paso 0) para evitar que modelos estándar rate-limitados (429/503) sean descartados de `modelos_activos.json`, aplicando una penalización de latencia (10.0s) para dejarlos al final de la cola.
  - Verificada la rotación automática en caliente durante el pipeline, resolviendo correctamente con `gemini-2.5-flash-lite` cuando `gemini-2.5-flash` agotó su cuota de uso.

## 2. Tareas Pendientes para Siguiente Sesión

- [ ] **Integración en AppSheet / Visualización de Recomendaciones**: Definir y desarrollar la forma de transferir y mostrar las acciones sugeridas por el Supervisor del Sistema (como rebalanceos de cartera, optimización de filtros, alertas de desincronización y activación de tickers inactivos) directamente en la interfaz móvil de AppSheet.
- [ ] **Integración de la Matriz de Decisión en AppSheet**: Vincular la hoja `MATRIZ_RECOMENDACIONES` a la aplicación móvil para poder visualizar de forma amigable y centralizada los veredictos históricos, scores de convicción de la IA y el sentimiento de cada activo desde el celular.

## 3. Ideas y Mejoras Futuras
- **Integración Móvil en AppSheet**:
  - Diseñar interfaces amigables para cargar transacciones rápidamente desde el celular.
  - Generar gráficos interactivos en el dashboard de AppSheet sobre la evolución patrimonial.
