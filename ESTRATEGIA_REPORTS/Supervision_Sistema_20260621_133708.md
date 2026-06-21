Como **Auditor Senior de Sistemas Financieros**, presento el informe de optimización y calidad de datos basado en el estado actual de la matriz y los datos técnicos vigentes al 20 de junio de 2026.

---

### 🧠 1. MEJORA DE DATOS (Filtros, Tickers y Sinónimos)

*   **Alerta de Sinónimos:** Luis, tienes **36 sugerencias de sinónimos pendientes**. Por favor revisa la hoja `SUGERENCIAS_SINONIMOS` y cambia su estado a **APROBADO** o **RECHAZADO**.
*   **Actualización COMAFI:** Se detectaron **0** nuevos CEDEARs. No es necesario correr el script de mantenimiento.
*   **Nuevos Tickers Detectados (Maestro de Activos):** El flujo de noticias menciona repetidamente el ticker **NASDAQ** (vía futuros o índice) y el ticker interno **9999** (posible error de sistema o placeholder). Si deseas trackear el índice tecnológico formalmente, añade:
    *   `QQQ;Invesco QQQ Trust;NASDAQ 100 ETF tech;2026-06-21 13:36:47;250;GF_BRIDGE;ACTIVO`
*   **Activación de Activos Inactivos:**
    *   Luis, los activos **BTC, ETH, MU, ASML, ARKK, QQQ y SPY** tienen noticias relevantes procesadas pero figuran como **INACTIVO** en el `maestro_filtros`. 
    *   **Acción:** Considera activarlos para que el pipeline técnico calcule sus indicadores y la IA tome decisiones basadas en datos técnicos frescos, ya que actualmente la IA está analizando estos tickers "a ciegas" o basándose en flujos parciales.

---

### 📊 2. AUDITORÍA DE NOTICIAS VS DECISIÓN (Calidad del Triage)

*   **Detección de Omisión en Triage:** El Paso 4 (Triage) descartó la noticia sobre "Caída de bonos argentinos por falta de referencia en Wall Street" para el ticker **SPY**. 
    *   *Observación del Auditor:* Correcto descarte. Sin embargo, se detectó que para **SPY** el sistema cita noticias de un "Desplome" el 17/06 en el veredicto de la IA, pero no hay noticias aprobadas que detallen la causa macro (Fed, Inflación, etc.).
*   **Alerta de Silencio:** 
    *   **SPY**: El sistema reporta una "Contradicción Técnica" por un desplome reciente, pero los datos técnicos lo marcan como `ALCISTA L.P.`. Luis, busca manualmente en Twitter o Google qué pasó con **SPY**, ya que el radar de noticias captó el efecto pero no el driver específico.

---

### 📉 3. CONTRADICCIONES TÉCNICAS (Veredicto IA vs Indicadores)

*   **Anomalía en USDARS:**
    *   **Veredicto IA:** Score 5/6 (Bullish) con advertencia de sobrecompra.
    *   **Dato Técnico:** RSI = **100**. 
    *   *Auditoría:* Un RSI de 100 es matemáticamente extremo y suele preceder a bloqueos por escala o errores de feed. El Score de la IA es demasiado optimista (6/10 Agresivo) para un activo con RSI en el techo absoluto. Sugerencia: Bajar Score a <3 hasta corrección.
*   **Anomalía en NKE:**
    *   El veredicto indica Score 3/10 (Contradicción) basado en que el precio está "muy por debajo de la SMA200", pero los `datos_tecnicos_vigentes` muestran un RSI de 52.67 (Neutral). La IA está priorizando el sentimiento negativo de las noticias sobre la estabilización técnica.

---

### 📏 4. ERRORES DE ESCALA (Activos bloqueados 15x)

*   **Estado de Bloqueos:** No se detectaron activos con `RSI = -1` o `Fibo = Error`. 
*   **Alerta Preventiva:** El activo **USDARS** está al límite de activación del bloqueo por escala (RSI 100). Verificar si el feed de precio está congelado o si hubo un salto discrecional en el tipo de cambio oficial/paralelo no procesado por el suavizado del algoritmo.

---

### 🕒 5. SINCRONIZACIÓN DE DATOS (Discrepancia de Fechas)

*   **Aviso de Desincronización Crítica:**
    *   **AAPL y AMD:** Luis, el análisis de estos activos está desincronizado. Los `datos_tecnicos_vigentes` tienen fecha del **2026-06-18**, pero el `estado_actual_matriz` muestra veredictos del **2026-06-20**. 
    *   **Acción:** Estás analizando noticias de hoy con precios y tendencias de hace 48 horas. **Re-ejecuta el Bridge Técnico** inmediatamente.

---

### ⚠️ 6. AUDITORÍA DE BRECHA CAMBIARIA (CCL)

*   **Análisis de Media de Mercado:** La media del CCL para CEDEARs sanos se sitúa en los **150,500 - 151,000**.
*   **Detección de Errores de Carga:** 
    *   Luis, el CEDEAR de **C (Citigroup)** muestra un CCL de `15151`.
    *   Luis, el CEDEAR de **VIST** muestra un CCL de `15046`.
    *   **Acción:** Estos valores tienen un error de magnitud (falta un dígito). Esto distorsiona el promedio de brecha. Verifica el factor de conversión (ratio) en el Maestro de Activos para estos dos tickers.
*   **Alerta de Sobreprecio:** **META** cotiza con un CCL de `151346` (+0.5% sobre la media). No es crítico (>2.5%), pero es el activo más "caro" para entrar en pesos hoy.

---

### ⚙️ 7. OPTIMIZACIÓN DE INSTRUCCIONES IA

*   **Sugerencia para `Instrucciones_Fijas` (Criterio Financiero):** 
    *   Se observa que la IA da Scores altos (8/10) en activos con RSI > 70 (Caso **C**). 
    *   *Ajuste sugerido:* "Si el RSI es > 70, el SCORE no puede superar 6/10 a menos que exista una noticia de confluencia calificada como 'Transformacional/M&A'."
*   **Sugerencia para `Prompt_Triage_Noticias`:**
    *   La IA descartó noticias de bonos argentinos para el ticker **SPY**. 
    *   *Ajuste sugerido:* "Incluir noticias de deuda soberana local solo si el ticker es de origen argentino (ej. GGAL, YPF, VIST). Para tickers USA, ignorar volatilidad local a menos que afecte al CCL global."

---
**INFORME FINALIZADO**
*Estado del Sistema: REVISIÓN REQUERIDA (Desincronización de Fechas detectada).*