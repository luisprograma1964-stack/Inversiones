Como Auditor Senior de Sistemas Financieros, he analizado la matriz de datos y el flujo de noticias. A continuación, presento el informe de optimización:

### 🧠 1. MEJORA DE DATOS (Configuración)
**Fila para CONFIG_SINONIMOS:**
`bonos argentinos;BONOS_ARG`
`BID;GGAL`
`petroleras;YPFD`
`construcción de viviendas;XHB`
`operaciones digitales;BYMA`
`Criptomonedas;BYMA`

**Nuevos Activos para MAESTRO_ACTIVOS:**
`XHB;Homebuilders ETF;construction, housing starts, US housing market;2026-06-19 10:08:15;250;GF_BRIDGE;ACTIVO`
`BYMA;Bolsas y Mercados Argentinos;BYMA, mercado capitales argentina, finanzas digitales;2026-06-19 10:08:15;250;GF_BRIDGE;ACTIVO`

---

### 📊 2. AUDITORÍA DE NOTICIAS VS DECISIÓN
*   **Ajuste de Filtro:** El filtro para **AMZN** es demasiado genérico (`stock:AMZN`).
    *   *Acción:* "Luis, cambia el filtro de AMZN por 'Amazon AWS earnings, Amazon retail, cloud computing, AI logistics' en el Maestro para capturar drivers fundamentales reales".
*   **Ajuste de Filtro:** El activo **C (Citigroup)** no encuentra noticias relevantes porque el filtro `stock:C` es insuficiente.
    *   *Acción:* "Luis, actualiza el filtro de C a 'Citigroup earnings, bank restructuring, interest rate impact, global banking'".

---

### 📉 3. CONTRADICCIONES TÉCNICAS (IA vs. Indicadores)
*   **Caso ETH/ETHA:** El veredicto de IA es `BULLISH` (Score 6-7/10) mientras que los indicadores reportan `BAJISTA L.P.` y precio por debajo de la SMA200.
    *   *Alerta:* La IA está sobreponderando las noticias locales (impuestos) frente a la tendencia estructural. Riesgo alto de "trampa alcista".
*   **Caso USDARS:** El veredicto es `BULLISH` (Score 5-6/10) con `RSI=100`.
    *   *Alerta:* Existe una disonancia técnica. Un RSI de 100 indica agotamiento extremo. La IA debe corregir su Score a <3/10 ante condiciones de sobrecompra técnica extrema.

---

### 📏 4. ERRORES DE ESCALA (Seguridad 15x)
*   **Detección:** Los activos **AAPL, AMD, AMZN, ARKK, ASML, BRKB, C, CVX, DIS, DISN, ETH, ETHA, GLD, KO, META, MU, NKE, QQQ, SPY, SPYG, TSLA, VIST, WMT, XOM** presentan valores de RSI anómalos (ej: `5094` en lugar de `50.94`, `6119` en lugar de `61.19`).
    *   *Acción:* "Luis, el sistema está cargando el RSI sin el divisor decimal adecuado. Todos los activos presentan error de escala 100x. Bloquear operativa automática hasta ajustar el factor de normalización de datos."

---

### 🕒 5. SINCRONIZACIÓN DE DATOS (Discrepancia)
*   **Discrepancia:** **MU (Micron)** tiene una fecha de precio de `2026-06-17` (hace 24hs), mientras que los demás activos están al `2026-06-18`.
    *   *Acción:* "Luis, el análisis de MU está desincronizado: precio de hace 24hs vs noticias de mercado vigentes. Re-ejecuta el Bridge para Micron."

---

### ⚠️ 6. ALERTAS Y CALIDAD
*   **Silencio:** El activo **VIST** tiene fundamento positivo (Acuerdo UE-Mercosur) pero la IA reporta una `CONTRADICCIÓN` técnica por debilidad de corto plazo.
    *   *Acción:* "Luis, busca manualmente en Twitter o Google qué factores específicos de corto plazo están presionando a VIST a pesar del driver positivo mencionado."

---

### ⚙️ 7. OPTIMIZACIÓN DE INSTRUCCIONES (Prompting)
*   **Sugerencia para 'Instrucciones_Fijas':** Agregar regla: *"Si el RSI es > 85 o < 15, el Score máximo permitido es 3/10, independientemente del sentimiento de las noticias, para evitar sesgo de confirmación por sobreextensión técnica."*
*   **Sugerencia para 'Prompt_Triage_Noticias':** Añadir regla: *"Si el titular menciona un movimiento de precio ('sube un 7%', 'cayeron un 5%'), clasificar como 'Microeconomía/Ruido' salvo que explique la causa macroeconómica (ej: 'sube un 7% por cambio en política monetaria de la Fed')."*