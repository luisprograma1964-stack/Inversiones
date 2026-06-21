A continuación, presento mi informe de auditoría de precisión y optimización del sistema financiero. Se han detectado inconsistencias críticas en la sincronización de datos y errores de escala que requieren intervención inmediata.

---

### 🧠 1. MEJORA DE DATOS (Sinónimos, Tickers y Filtros)

*   **Sugerencias de Sinónimos:** ⚠️ **Luis, tienes 36 sugerencias de sinónimos pendientes.** Por favor revisa la hoja `SUGERENCIAS_SINONIMOS` y cambia su estado a APROBADO o RECHAZADO para mejorar el Triage.
*   **Activación por Flujo de Noticias:** Se han detectado activos con alto volumen de noticias pero apagados en el motor de cálculo:
    *   Acción: **Luis, los activos ARKK, ASML, BTC, ETH/ETHA, MU, QQQ y SPY tienen noticias relevantes pero están INACTIVOS en tu maestro.** Considera activarlos para que el pipeline técnico calcule sus indicadores y la IA tome decisiones informadas sobre ellos.
*   **Nuevos Tickers Detectados:** El mercado está operando con fuerza en sectores no mapeados totalmente. Agregar a `MAESTRO_ACTIVOS`:
    *   `NVDA;NVIDIA Corporation;NVDA stock, Blackwell chips, Jensen Huang;2026-06-21 13:40:41;250;GF_BRIDGE;ACTIVO`
    *   `GGAL;Grupo Financiero Galicia;GGAL ADR, Grupo Galicia, acciones argentinas;2026-06-21 13:40:41;250;GF_BRIDGE;ACTIVO`

---

### 📊 2. AUDITORÍA DE NOTICIAS VS DECISIÓN

*   **Detección de Omisión:** La IA emitió un veredicto sobre **SPY** el 18/06 mencionando "desplome en Wall Street" basándose en noticias del 17/06. Sin embargo, en el `estado_actual_matriz` para activos como **AAPL** y **AMD** (procesados el 20/06), se ignora esta tendencia de desplome y se centra en la "Fed hawkish".
*   **Calidad del Triage:** Se observa un descarte correcto en temas triviales (salsa ranchera, MLB), pero el descarte de "Amazon vs Nvidia en chips" para el ticker **AMZN** fue un error; se clasificó como "microeconomía/ruido" cuando afecta directamente el driver de innovación mencionado en el análisis de otros activos semiconductores.

---

### 📉 3. CONTRADICCIONES TÉCNICAS (IA vs Indicadores)

*   **DIS (Disney):** **Alerta de Inconsistencia.** El RSI técnico es de **5.74** (sobreventa extrema/pánico), pero el veredicto de la IA otorga un SCORE de 4/10 y sentimiento "NEUTRAL". Un RSI de 5 suele implicar un evento de capitulación que la IA no está ponderando adecuadamente en el Score de riesgo.
*   **C (Citigroup):** El RSI es de **71.57** (sobrecompra). La IA otorga un SCORE de 9/10 (Agresivo) recomendando "Comprar". **Riesgo:** Comprar en el pico de un impulso sin driver de ruptura inminente.
*   **USDARS:** El RSI es de **100**. Esto es un error de saturación del indicador o una anomalía de datos (RSI no puede ser 100 sostenido). La IA lo detecta como "alerta roja", lo cual es correcto, pero el dato técnico de origen debe ser auditado.

---

### 📏 4. ERRORES DE ESCALA Y BLOQUEOS (15x)

*   ⚠️ **Luis, los activos C y VIST fueron bloqueados por seguridad (Escala 15x).**
    *   **C:** El CCL_IMPLICITO figura en **15,151** mientras el promedio de mercado es de **150,500**. Esto indica un error de carga en el precio local o un split de 10:1 no procesado en el script de precios.
    *   **VIST:** El CCL_IMPLICITO figura en **15,046**. Misma anomalía de factor 10x.
    *   **Consecuencia:** El sistema está calculando que estos CEDEARs son "extremadamente baratos" por un error de coma decimal, lo que podría disparar señales de compra falsas.

---

### 🕒 5. SINCRONIZACIÓN DE DATOS (Discrepancias)

*   **Aviso de Desincronización:**
    *   **AAPL y AMD:** Luis, el análisis de estos activos está desincronizado. El veredicto de la IA es del **20/06**, pero los datos técnicos (RSI, Trend) son del **18/06**. Estás analizando noticias nuevas con precios viejos. **Re-ejecuta el Bridge.**
    *   **USDARS:** El técnico es del **20/06** pero el veredicto IA es del **18/06**. La IA no está viendo la subida del Blue/RSI 100 de las últimas 48hs.

---

### ⚠️ 6. ALERTAS DE SILENCIO (Movimientos sin Driver)

*   **Luis, busca manualmente en Twitter o Google qué pasó con DIS (Disney).** El RSI de **5.74** indica un desplome masivo de precio, pero el submódulo de noticias reporta "⚪ No existen noticias específicas". Hay un "agujero negro" informativo entre el 18/06 y el 20/06 para este activo.

---

### ⚙️ 7. OPTIMIZACIÓN DE INSTRUCCIONES IA

*   **Sugerencia para `Instrucciones_Fijas`:** "Si el RSI es menor a 15 o mayor a 85, el SENTIMIENTO debe ser obligatoriamente precedido por la palabra 'EXTREMO' y el SCORE debe ajustarse un -2 por riesgo de reversión, a menos que exista una noticia de impacto 'MUY ALTO' que justifique la verticalidad."
*   **Sugerencia para `Prompt_Triage_Noticias`:** "No descartar noticias de competencia directa (ej. Nvidia vs Amazon) como 'Microeconomía' si el ticker afectado es uno de los líderes del sector; estas noticias deben ser consideradas 'Confluencia Sectorial'."

---
**Auditor Senior de Sistemas Financieros**
*Estado del Sistema: ESTABLE CON ALERTAS DE DATOS*