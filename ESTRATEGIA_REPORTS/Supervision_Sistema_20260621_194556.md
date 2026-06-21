Como Director de Inversiones (CIO) y Auditor de Calidad, he procesado la información consolidada. A continuación, presento el informe ejecutivo de gestión y auditoría.

---

### 💰 ESTRATEGIA DE CARTERA
El portafolio actual presenta una **subutilización de capital crítica**. El 100% de la tenencia es `AL30` (Bono soberano) para "Familiar" y no hay activos para "Matu" o "Anto".

*   **Orden de Rebalanceo:**
    *   **Para LUIS_MODERADO:** El target es 50% Bonos, 30% Cedears, 20% Cash.
        *   *Acción:* Vender 20% de la tenencia de `AL30` para generar liquidez. Comprar `ASML` (Score 8/10, fuerte tendencia fundamental) hasta completar el 30% del presupuesto de Cedears. Mantener el resto en `AL30` y Cash.
    *   **Para LUIS_AGRESIVO:** El target es 60% Cedears, 20% Acciones Locales, 10% Bonos, 10% Cash.
        *   *Acción:* Iniciar posiciones en `ASML` y `AMD` (Scores 9/10 y 6/10 respectivamente) aprovechando la fuerte confluencia de noticias técnicas. El capital actual es $0; se requiere un aporte inicial de liquidez.

### 🧠 MEJORA DE DATOS
*   **Sinónimos:** Luis, tienes **39 sugerencias de sinónimos pendientes**. Por favor, accede a la hoja `SUGERENCIAS_SINONIMOS` y cambia su estado a APROBADO o RECHAZADO para depurar el motor de búsqueda.
*   **Activos Inactivos con Noticias:** Los siguientes activos tienen flujo de noticias pero están `INACTIVO` en el maestro. Debes activarlos para que la IA los procese:
    *   `BTC`, `ETH`, `ETHA`, `MU`, `QQQ`.
*   **Optimización de Búsqueda:** El activo `DISN` no arroja resultados claros; cambia el filtro en el Maestro de `stock:DISN` a `Disney streaming subscriber growth content` para capturar drivers reales.

### 📊 AUDITORÍA DE NOTICIAS VS DECISIÓN
*   **Calidad del Triage:** El filtro actual está siendo demasiado restrictivo. Se descartaron noticias sobre "SpaceX" (que aunque es privada, afecta a empresas de tecnología/aeroespacial).
*   **Sugerencia:** Ajustar el `Prompt_Triage_Noticias` para permitir noticias sobre sectorial aeroespacial y empresas privadas de alto impacto en el ecosistema tecnológico.

### 📉 CONTRADICCIONES TÉCNICAS
*   **Alerta:** `META` y `NKE` presentan una contradicción técnica. El veredicto IA es cauteloso, pero el `RSI` muestra valores atípicos (ej: `AAPL` con RSI 5094).
*   **Detección:** Los valores de RSI parecen estar expresados en una escala errónea (posible falta de normalización a [0-100]). Auditoría urgente requerida sobre el script de cálculo técnico.

### 📏 ERRORES DE ESCALA (BLOQUEOS 15x)
*   **Alerta:** El activo `USDARS` presenta un RSI de `100` y `FIBO_RET` en `236` sobre un precio de 2026-06-20. Existe un error de carga en los datos de `FIBO_RET` para gran parte de los activos (ej: `AMZN` 786, `KO` 786). Estos no son valores de Fibonacci válidos.
*   **Acción:** Luis, revisa el pipeline de normalización de datos; los coeficientes Fibonacci están cargándose como enteros brutos en lugar de ratios.

### 🕒 SINCRONIZACIÓN DE DATOS
*   **Discrepancia:** `AAPL` y `AMD` tienen datos técnicos del 18/06 mientras que el contexto de mercado es del 21/06. **Re-ejecuta el Bridge** de forma inmediata; el portafolio está operando con una latencia de 72 horas.

### ⚠️ ALERTAS Y CALIDAD
*   **Brecha Cambiaria (CCL):** El CEDEAR de `C` cotiza con un CCL implícito de 15,151, mientras que el promedio de mercado es 14,782.
    *   *Acción:* **Evitar compra de `C` localmente**. Presenta un sobreprecio cambiario del ~2.5% respecto al resto del mercado.
*   **Silencio de Mercado:** No hay noticias sobre el sector petrolero que justifiquen el movimiento de `XOM` y `CVX`. *Luis, busca manualmente en Google qué ocurrió con los precios del crudo esta semana.*

### ⚙️ OPTIMIZACIÓN DE INSTRUCCIONES IA
*   **Cambio en 'Instrucciones_Fijas':** Modificar para que, ante la ausencia de noticias (`ALERTA DE MOMENTO SIN DRIVER`), la IA no sugiera "Mantener" automáticamente, sino que fuerce un "Reducir posición o Esperar" para mitigar el riesgo de volatilidad no informada.
*   **Cambio en 'Prompt_Triage_Noticias':** Incluir una instrucción de "Ignorar ruido de efemérides pero incluir noticias sobre fusiones, adquisiciones y movimientos en C-Level de empresas tecnológicas".