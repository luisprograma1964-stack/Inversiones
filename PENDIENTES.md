# Pendientes y mejoras del sistema Inversiones

Fecha de revisión: 2026-06-20

## 1. Tareas Completadas (Sesión Actual)

- [x] **Integración de CEDEARs Comafi**: Creado `captura_cedears.py` para sincronizar automáticamente los 358 activos de la API del Banco Comafi en la nueva hoja `PROGRAMA_CEDEARS`.
- [x] **Mantenimiento Dinámico del Maestro**: Modificado `mantenimiento_maestro.py` para auto-desactivar activos huérfanos y auto-insertar nuevos programas en estado `INACTIVO` por defecto para proteger cuotas de red.
- [x] **Descarga Dual e Integridad de Decimales**: Ajustado `carga_historica_bridge.py` para descargar subyacente internacional y Byma (`BCBA:`) en paralelo. Se inyectaron prefijos de mercado (NASDAQ/NYSE) y se forzó el formato regional de comas decimales para evitar el error de escala 100x.
- [x] **Cálculo de Brecha Cambiaria (CCL)**: Modificados `main_tecnico.py` y `analisis_tecnico.py` para calcular el Dólar CCL implícito diario cruzando precios y ratios. La brecha ahora se guarda en la columna `CCL_IMPLICITO` de `ANALISIS_TECNICO`.
- [x] **Integración de IA (CCL)**: Añadido `CCL_IMPLICITO` a `ia_params.json` para enviarlo nativamente al motor de Gemini en cada prompt de análisis técnico.
- [x] **Semáforos y Alertas en Supervisor**: Modificado `supervisor_del_sistema.py` para incorporar la auditoría de desvíos del tipo de cambio implícito, la detección de noticias sobre activos `INACTIVOS` relevantes, y el uso nativo de semáforos de colores (🔴 🟡 🟢) en `ESTADO_PROCESOS`.

## 2. Tareas Pendientes para Siguiente Sesión

- [ ] **Verificación del Supervisor**: Correr `supervisor_del_sistema.py` para verificar que genere el reporte estratégico correctamente en la carpeta `ESTRATEGIA_REPORTS` y audite con éxito la brecha cambiaria y alertas de activos inactivos.
- [ ] **Evaluación del Nuevo Prompt en Gemini**: Monitorear que la IA en la próxima corrida del pipeline principal penalice o advierta correctamente compras locales en pesos si el desvío de brecha de ese CEDEAR supera el +2.5% de la media de mercado.

## 3. Ideas y Mejoras Futuras

- [ ] **Compatibilidad y Explotación desde AppSheet**:
  - Diseñar la integración móvil para el registro de transacciones.
  - Implementar lógica de afectación de saldos en `CAJA_LIQUIDEZ` al operar en `TRANSACCIONES`.
  - Crear la lógica de rentabilidad real (Aportes netos vs Valor de portafolio).
  - *Nota*: Consultar propuesta de diseño preliminar en el artefacto de planificación local [plan_appsheet.md](file:///C:/Users/lberz/.gemini/antigravity/brain/a4f28076-2632-46cf-8dfd-1d015b3bdb26/plan_appsheet.md).
