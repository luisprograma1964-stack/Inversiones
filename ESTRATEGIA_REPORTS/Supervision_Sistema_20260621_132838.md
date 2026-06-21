Como Auditor Senior de Sistemas Financieros, he procedido a realizar el escrutinio técnico del **Sistema GF_BRIDGE** con fecha de auditoría **2026-06-20**. A continuación, presento los hallazgos críticos y las acciones de optimización necesarias para garantizar la integridad operativa.

---

### 🧠 1. MEJORA DE DATOS (Filtros, Tickers y Sinónimos)

*   **ALERTA DE SINÓNIMOS**: Luis, tienes **86 sugerencias de sinónimos pendientes**. Por favor revisa la hoja `SUGERENCIAS_SINONIMOS` y cambia su estado a APROBADO o RECHAZADO para mejorar el mapeo de noticias.
*   **ACTUALIZACIÓN MAESTRO_ACTIVOS**: Se ha detectado flujo de noticias sobre activos no monitoreados o con inconsistencias en el nombre. Se recomienda evaluar la inclusión de los siguientes para mayor cobertura:
    *   `YPF;YPF Sociedad Anonima;YPF news, Vaca Muerta, Galuccio;2026-06-21 13:28:16;250;GF_BRIDGE;ACTIVO`
    *   `GGAL;Grupo Financiero Galicia;Galicia ADR, bancos argentinos, tasa BCRA;2026-06-21 13:28:16;250;GF_BRIDGE;ACTIVO`
*   **ESTADO COMAFI**: Auditoría de CEDEARs Comafi limpia. No se requieren acciones de mantenimiento sobre la base de datos de conversión.

---

### 📊 2. AUDITORÍA DE ACTIVACIÓN DE ACTIVOS

He detectado una **fuga de eficiencia** en el pipeline. Los siguientes activos tienen **noticias recientes e impacto en la matriz**, pero figuran como **INACTIVOS** en tu maestro de filtros:

*   **Acción**: Luis, los activos **MU, ASML, ARKK, BTC, ETH, ETHA, GLD, QQQ, SPY y SPYG** tienen noticias relevantes o están siendo analizados por la IA, pero su estado es **INACTIVO** en el maestro.
    *   *Consecuencia*: El sistema está consumiendo tokens de IA para veredictos, pero el pipeline técnico no está priorizando la actualización de sus indicadores en tiempo real. **Cámbialos a ACTIVO**.

---

### 📉 3. CONTRADICCIONES TÉCNICAS (IA vs Indicadores)

*   **TICKER DIS (Disney)**:
    *   *Dato Técnico*: RSI de **5.74** (Sobrevendido extremo).
    *   *Veredicto IA*: Score **4/10 (Neutral)** y recomendación de "Mantener".
    *   *Dictamen Auditor*: Existe una falla de sensibilidad. Un RSI de 5.74 es una anomalía o una oportunidad de rebote técnico masivo. La IA está ignorando la capitulación técnica.
*   **TICKER C (Citigroup)**:
    *   *Dato Técnico*: RSI de **71.57** (Sobrecompra).
    *   *Veredicto IA*: Score **9/10 (Comprar)** para perfil agresivo.
    *   *Dictamen Auditor*: **Riesgo Alto**. Recomendar compra con RSI > 70 sin un catalizador de ruptura explosiva es peligroso. Se sugiere ajustar la instrucción de "Prudencia en Sobrecompra".

---

### 📏 4. ERRORES DE ESCALA Y DATOS CORRUPTOS

*   **ALERTA CRÍTICA DE CCL (Escala)**:
    *   **TICKER C**: Presenta un `CCL_IMPLICITO` de **15.15**.
    *   **TICKER VIST**: Presenta un `CCL_IMPLICITO` de **15.04**.
    *   *Acción*: Luis, los activos **C y VIST** fueron procesados con un error de escala (posiblemente un factor de 100x o error en el precio base). Verifica si hubo un split o un error en la carga del precio local/externo. **El cálculo de brecha está roto para estos activos.**
*   **FORMATO RSI**: Los valores de RSI en `datos_tecnicos_vigentes` (ej. 5094, 6119) sugieren que el sistema está omitiendo el separador decimal (50.94, 61.19). Esto puede confundir a modelos de IA menos robustos.

---

### 🕒 5. SINCRONIZACIÓN DE DATOS (Time-Lag)

*   **DISCREPANCIA DETECTADA**:
    *   **AAPL y AMD**: El análisis de la IA tiene fecha **2026-06-20**, pero los `datos_tecnicos_vigentes` (precios/indicadores) son del **2026-06-18**.
    *   **USDARS**: El técnico es del **2026-06-20** pero el veredicto de la matriz es del **2026-06-18**.
    *   **Acción**: Luis, el análisis de estos activos está desincronizado. La IA está decidiendo sobre precios de hace 48hs o viceversa. **Re-ejecuta el Bridge completo para unificar el timestamp.**

---

### ⚠️ 6. AUDITORÍA DE BRECHA CAMBIARIA (CCL)

*   **MEDIA DE MERCADO**: $1505.20
*   **DESVIACIÓN**:
    *   **AAPL**: Cotiza con un CCL de $1510.69 (**+0.36%** sobre la media).
    *   **XOM**: Cotiza con un CCL de $1499.89 (**-0.35%** sobre la media).
*   **Veredicto**: La brecha está estable y arbitrada, a excepción de los errores de escala reportados en el punto 4. No hay alertas de sobreprecio cambiario significativas hoy.

---

### ⚙️ 7. OPTIMIZACIÓN DE INSTRUCCIONES IA

Para mejorar la precisión del Auditor en el próximo ciclo, sugiero los siguientes ajustes:

1.  **En 'Instrucciones_Fijas'**:
    *   "Si el RSI es menor a 15, el sentimiento DEBE ser marcado como 'OVERSOLD/REBOTE' independientemente de la tendencia de largo plazo, a menos que existan noticias de quiebra inminente."
2.  **En 'Prompt_Triage_Noticias'**:
    *   Se detectó que el Triage descartó noticias de Walmart (WMT) calificándolas como "Microeconomía/Ruido". Sin embargo, un retroceso del 12% mensual (mencionado en el descarte) NO es ruido.
    *   *Ajuste*: "No descartar noticias que mencionen variaciones porcentuales superiores al 5% en el último mes, incluso si parecen análisis técnicos automáticos; el mercado reacciona a estos informes."

**Informe finalizado. Esperando órdenes para re-escaneo.**