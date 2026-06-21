Informe de Auditoría de Sistemas Financieros (QA/Optimizer) – **2026-06-20**

A la atención del Administrador del Sistema (Luis):

---

### 🧠 1. MEJORA DE DATOS (Filtros, Tickers y Sinónimos)

*   **ALERTA DE SINÓNIMOS:** Luis, tienes **20 sugerencias de sinónimos pendientes**. Por favor revisa la hoja `SUGERENCIAS_SINONIMOS` y cambia su estado a APROBADO o RECHAZADO para mejorar el mapeo de noticias.
*   **ACTIVACIÓN DE ACTIVOS INACTIVOS:** Se ha detectado flujo de noticias recientes para activos que actualmente están configurados como **INACTIVOS** en el `maestro_filtros`. Esto impide que el sistema genere órdenes automáticas basadas en esos drivers.
    *   *Acción:* Luis, los activos **ARKK, ASML, BTC, ETHA, MU, QQQ y SPY** tienen noticias relevantes pero están **INACTIVOS**. Considéralos activar para que el pipeline técnico calcule sus indicadores y la IA tome decisiones sobre ellos.
*   **NUEVO TICKER DETECTADO:** El mercado y los descartes mencionan actividad sobre **NVDA** y **GGAL** de forma recurrente. Asegúrate de que sus filtros en el maestro sean óptimos.

---

### 📊 2. AUDITORÍA DE NOTICIAS VS DECISIÓN (Calidad del Triage)

*   **Efectividad del Triage:** El módulo de descarte funcionó correctamente al filtrar noticias de "TanGo" que no afectaban a **YPF**, y al ignorar contenido deportivo que afectaba al ticker **USDARS**.
*   **Fuga de Drivers:** Se detectaron noticias sobre el "Aguinaldo 2.0" y "Dólar Blue" en el submodulo Telegram. Aunque se descartaron por "publicitarios", la presión sobre el **USDARS** es real (RSI 100). El Triage es correcto, pero el impacto macro debe ser absorbido por el driver "Brecha Cambiaria".

---

### 📉 3. CONTRADICCIONES TÉCNICAS (Veredicto IA vs Indicadores)

Se han detectado discrepancias severas en los siguientes activos:

*   **TICKER: C (Citigroup)**
    *   *Discrepancia:* La IA otorga un **SCORE: 9/10 (BULLISH/COMPRAR)** mientras el **RSI está en 71.57** (Sobrecompra). Comprar en este nivel técnico es de alto riesgo.
    *   *Auditoría:* El veredicto ignora el agotamiento del momentum.
*   **TICKER: DIS (Disney)**
    *   *Discrepancia:* El **RSI técnico es de 5.74** (Sobreventa extrema/Pánico), indicando una oportunidad potencial de rebote por agotamiento vendedor, pero la IA mantiene un veredicto **NEUTRAL/MANTENER** con Score 4.
    *   *Auditoría:* El modelo no está capturando la capitulación del precio como señal de compra contraria.
*   **TICKER: USDARS**
    *   *Discrepancia:* El **RSI es de 100** (valor matemáticamente extremo). La IA sugiere "Mantener" con Score 5/6. En este nivel, cualquier veredicto que no sea "Vender/Cubrir" o "Alerta Roja de Corrección" es técnicamente inconsistente.

---

### 📏 4. ERRORES DE ESCALA (Bloqueos de Seguridad 15x)

*   **TICKER: C:** Luis, el activo **C** muestra un CCL_IMPLICITO de **15151**. Esto es un desvío del 900% respecto a la media de 150.000. El activo fue bloqueado por seguridad (Escala 15x). Verifica si hay un error de carga en el precio local o un split no procesado.
*   **TICKER: VIST:** Luis, el activo **VIST** muestra un CCL_IMPLICITO de **15046**. Al igual que el anterior, presenta un error de escala (posiblemente falta un cero o hay un error en el factor de conversión).

---

### 🕒 5. SINCRONIZACIÓN DE DATOS (Discrepancias de Fechas)

*   **AVISO DE DISCREPANCIA:** Luis, el análisis de **AAPL** y **AMD** está desincronizado: precio y técnicos del **18 de junio** frente a veredictos y noticias del **20 de junio**. El sistema está operando con datos técnicos "viejos" (48hs) para un mercado volátil tras los comentarios de la Fed. **Re-ejecuta el Bridge Técnico inmediatamente.**

---

### ⚠️ 6. ALERTAS Y CALIDAD (Anomalías de Mercado)

*   **AUDITORÍA DE BRECHA (CCL):** Excluyendo los errores de escala (C y VIST), la media del CCL es de **150,634**.
    *   **Acción:** Luis, el CEDEAR de **META** cotiza con un CCL de **151,346** (+0.47% sobre la media). Está dentro de los límites, pero **XOM** cotiza a **149,989** (-0.42%). Existe una ligera ventaja de entrada en XOM por tipo de cambio implícito.
*   **ALERTAS DE SILENCIO:** Luis, busca manualmente en Twitter o Google qué pasó con **DIS** (RSI 5.74) y **USDARS** (RSI 100). Los movimientos son parabólicos y nuestro radar de noticias no ha procesado un driver de "Evento de Cisne Negro" que justifique tales extremos.

---

### ⚙️ 7. OPTIMIZACIÓN DE INSTRUCCIONES IA

*   **Sugerencia para 'Instrucciones_Fijas':** "Si el RSI es > 70, el SCORE de compra no puede superar 7, independientemente de las noticias, salvo que el ADX sea > 40. Si el RSI es < 15, elevar prioridad de análisis de rebote (Mean Reversion)."
*   **Sugerencia para 'Prompt_Triage_Noticias':** Reforzar la identificación de noticias sobre "Desregulación Cripto en Argentina" para los activos **ETH** y **ETHA**, ya que la IA los menciona pero el maestro los tiene inactivos.

---
**Auditor Senior de Sistemas Financieros**
*Final del Reporte*