# Diccionario de Datos: Planilla Inversiones

Este documento mantiene el registro **REAL** de la estructura de todas las hojas (worksheets) dentro del archivo principal de Google Sheets (`Inversiones`).
Esta estructura es la fuente de la verdad para que los scripts de Python lean y escriban los datos correctamente.

---

## 1. Hojas de Sistema y Monitoreo

### `LOG_SISTEMA`
Registra todos los eventos, advertencias y errores de los scripts.
- **A.** `FECHA` (Formato: YYYY-MM-DD HH:MM:SS)
- **B.** `NIVEL` (INFO, WARNING, ERROR, CRITICAL)
- **C.** `Nombre_Proceso` (Nombre del archivo Python)
- **D.** `MENSAJE` (Texto descriptivo)

### `ESTADO_PROCESOS`
Semáforo de estado para ver rápidamente si un proceso falló o terminó bien.
- **A.** `Nombre_Proceso` (Nombre del archivo Python)
- **B.** `Ultima_Corrida` (Fecha y hora de última ejecución)
- **C.** `Estado` (PROCESANDO, OK, ERROR)
- **D.** `Detalle` (Mensaje corto de éxito o falla)

---

## 1.1 Hojas de Cartera Personal

### `TRANSACCIONES`
Registro histórico de todos los movimientos de compra y venta realizados.
- **A.** `FECHA` (YYYY-MM-DD)
- **B.** `TICKER`
- **C.** `OPERACION` (COMPRA / VENTA)
- **D.** `CANTIDAD`
- **E.** `PRECIO_UNITARIO`
- **F.** `TOTAL_BRUTO`
- **G.** `COMISIONES`
- **H.** `TOTAL_NETO`
- **I.** `MONEDA` (ARS / USD)

### `CAJA_LIQUIDEZ`
Estado actual del efectivo y saldos en cuenta en distintas monedas.
- **A.** `MONEDA` (ARS, USD, MEP, etc.)
- **B.** `SALDO` (Valor numérico)
- **C.** `TIPO_CUENTA` (EFECTIVO, BANCO, ALYC)
- **D.** `ULTIMA_ACTUALIZACION` (YYYY-MM-DD HH:MM:SS)

---

## 2. Hojas de Configuración

### `CONFIG_FUENTES`
Define de dónde se sacan los valores de mercado generales (Dólar, UVA, etc).
- **A.** `TIPO`
- **B.** `DATO` (Nombre de la variable, ej: Dolar Blue)
- **C.** `FUENTE / URL` (Enlace de la API o web)
- **D.** `SELECTOR / CAMPO` (Ruta JSON o texto a buscar)
- **E.** `ESTADO` (ACTIVO / INACTIVO)

### `MAESTRO_ACTIVOS`
Catálogo maestro de todos los Tickers que el sistema sigue.
- **A.** `Ticker_ID` (Ej: AAPL, GGAL)
- **B.** `Nombre_Largo`
- **C.** `Filtro_Noticias`
- **D.** `Ultima_Actualiz` (Fecha de última descarga)
- **E.** `Dias_Keep_Hist`
- **F.** `Fuente_Data` (Ej: GF_BRIDGE)
- **G.** `ESTADO` (ACTIVO / INACTIVO)

---

## 3. Hojas de Datos (Market Data)

### `VARIABLES_MERCADO`
Resultados procesados de las variables generales (Dólar, Inflación).
- **A.** `DATO`
- **B.** `VALOR_PROM`
- **C.** `VALOR_MIN`
- **D.** `VALOR_MAX`
- **E.** `GAP_PERC`
- **F.** `MUESTRAS`
- **G.** `FECHA_MODIF`

### `HISTORICO_VALORES`
Base de datos cruda con el precio diario de cada activo.
- **A.** `Ticker_ID`
- **B.** `Fecha` (Formato: YYYY-MM-DD)
- **C.** `Precio_Cierre`
- **D.** `Volumen`
- **E.** `Maximo_Dia`
- **F.** `Minimo_Dia`

### `DOWNLOAD_BUFFER`
Hoja técnica temporal utilizada por `carga_historica_bridge.py` para la descarga masiva y paralela mediante la fórmula `=GOOGLEFINANCE`.
Estructura dinámica de bloques (7 columnas por activo):
- **Col 1.** `Date` (Encabezado generado por Google)
- **Col 2.** `Open`
- **Col 3.** `High`
- **Col 4.** `Low`
- **Col 5.** `Close`
- **Col 6.** `Volume`
- **Col 7.** *(Espacio vacío para separación de bloques)*

*Nota: Esta hoja se limpia automáticamente al inicio de cada sincronización.*

### `PROGRAMA_CEDEARS`
Listado oficial de todos los CEDEARs vigentes capturado desde la API del Banco Comafi.
- **A.** `TICKER_LOCAL` (Ticker Byma local, ej: AAPL)
- **B.** `TICKER_SUBYACENTE` (Ticker internacional, ej: AAPL)
- **C.** `EMPRESA` (Nombre de la empresa o ETF subyacente)
- **D.** `ISIN_CEDEAR` (Código ISIN local de custodia)
- **E.** `ISIN_SUBYACENTE` (Código ISIN internacional)
- **F.** `RATIO` (Ratio de conversión, ej: 10:1 o 20:1)
- **G.** `TIPO` (Cedear Shares / Cedear ETF)
- **H.** `ULTIMA_ACTUALIZACION` (Fecha y hora de sincronización, YYYY-MM-DD HH:MM:SS)

---

## 4. Hojas de Análisis e Inteligencia Artificial

### `ANALISIS_TECNICO`
Resultados matemáticos de los indicadores para cada Ticker.
- **A.** `TICKER_ID`
- **B.** `FECHA`
- **C.** `RSI`
- **D.** `MACD`
- **E.** `TREND` (Tendencia)
- **F.** `SMA_20` (Media Móvil 20)
- **G.** `SMA_50` (Media Móvil 50)
- **H.** `SMA_200` (Media Móvil 200)
- **I.** `PSAR`
- **J.** `FIBO_RET` (Retroceso Fibonacci)
- **K.** `DMI`
- **L.** `ESTADO` (PENDIENTE / PROCESADO - Para que la IA sepa qué leer)
- **M.** `ULTIMA_ACTUALIZACION` (Fecha y hora de ejecución del cálculo)
- **N.** `PRECIO_ACTUAL` (Valor de cierre más reciente)
- **O.** `FECHA_PRECIO_ACTUAL` (Fecha de la que se obtuvo el PRECIO_ACTUAL)
- **P.** `CCL_IMPLICITO` (Tipo de cambio implícito en Byma vs subyacente internacional)

### `CONFIG_IA_USUARIO`
Mapeo de los inversores y su perfil de riesgo para la IA.
- **A.** `Usuario_ID`
- **B.** `Perfil_Riesgo`
- **C.** `Mix_Target`
- **D.** `Tolerancia_Desvio`

### `CONFIG_IA_GENERAL`
- **A.** `Modelo_IA`
- **B.** `Instrucciones_Fijas` (El prompt maestro para Gemini/Gemma)
- **C.** `Dias_Analisis`
- **D.** `Prompt_Triage_Noticias` (Prompt para resumir y descartar noticias)

### `CONFIG_SINONIMOS`
Listado maestro de sinónimos consolidados en mapeo 1-a-N.
- **A.** `TICKER` (El símbolo del activo, ej: AAPL, GGAL)
- **B.** `SINONIMOS` (Listado de sinónimos separados por comas, ej: Apple, Apple Inc)

### `CONFIG_TELEGRAM_CHANNELS`
Lista dinámica de canales a monitorear.
- **A.** `CANAL` (Ej: @DolarHoy)
- **B.** `ESTADO` (ACTIVO / INACTIVO)

### `SUGERENCIAS_SINONIMOS`
Sugerencias automáticas de la IA para nuevos mapeos, para aprobación/rechazo manual del usuario (compatible con AppSheet).
- **A.** `FECHA`
- **B.** `TITULAR`
- **C.** `TERMINO_SUGERIDO`
- **D.** `TICKER_SUGERIDO`
- **E.** `EXPLICACION`
- **F.** `ESTADO` (PENDIENTE, APROBADO, RECHAZADO, PROCESADO)

### `NOTICIAS_SISTEMA`
Almacena las noticias validadas por la IA para su uso en el motor de decisiones.
- **A.** `FECHA` (YYYY-MM-DD HH:MM:SS)
- **B.** `TICKER_ID` (Ticker o 9999)
- **C.** `TITULAR`
- **D.** `FUENTE` (Reuters, Telegram, etc.)
- **E.** `SUBMODULO` (RSS, API, Search, Telegram)
- **F.** `URL` (Opcional)
- **G.** `CANAL_ORIGEN` (Nombre del canal si es Telegram)
- **H.** `RESUMEN_IA`
- **I.** `SENTIMIENTO`

### `NOTICIAS_DESCARTADAS`
Registro de auditoría para mejorar la calidad del filtrado.
- **A.** `FECHA`
- **B.** `TICKER_ID`
- **C.** `TITULAR`
- **D.** `MOTIVO_DESCARTE` (Explicación breve de la IA)
- **E.** `SUBMODULO`

### `REPORTE_IA`
Salida de IA general.

### `REPORTE_SUPERVISOR`
Almacena el output del script Supervisor del Sistema en formato de base de datos para consumo de Streamlit, reemplazando los antiguos archivos `.md`.
- **A.** `FECHA_HORA` (Timestamp de la ejecución)
- **B.** `RESUMEN_EJECUTIVO` (Texto clave)
- **C.** `ALERTAS_CRITICAS` (Alertas detectadas)
- **D.** `EVALUACION_RIESGO` (Evaluación de riesgo general)
- **E.** `CUERPO_COMPLETO` (El Markdown completo generado por la IA)

### `ALERTAS_SUPERVISOR`
Bandeja de entrada (Inbox) interactiva para anomalías y sugerencias detectadas por el Supervisor.
- **A.** `ID_ALERTA` (Identificador único, ej: AL-20240710-001)
- **B.** `FECHA_DETECCION` (Timestamp)
- **C.** `CATEGORIA` (ALERTA_CRITICA o MEJORA_CONSTANTE)
- **D.** `TIPO` (NUEVO_ACTIVO, AJUSTE_PROMPT, ERROR_TECNICO, etc.)
- **E.** `MENSAJE_ALERTA` (Texto claro y accionable)
- **F.** `ESTADO` (PENDIENTE, RESUELTO, IGNORADO)

### `HISTORIAL_REPORTE_IA`
El historial acumulado de todas las recomendaciones generadas.
- **A.** `FECHA` (YYYY-MM-DD HH:MM:SS)
- **B.** `TICKER`
- **C.** `PERFIL`
- **D.** `SENTIMIENTO` (Bullish, Bearish, Neutral)
- **E.** `VEREDICTO_IA` (Texto detallado con la recomendación)

### `MATRIZ_RECOMENDACIONES`
Misma estructura que REPORTE_IA, pero solo mantiene el veredicto más reciente por Ticker/Perfil.
- **A.** `FECHA`
- **B.** `TICKER`
- **C.** `PERFIL`
- **D.** `SENTIMIENTO`
- **E.** `VEREDICTO_IA`
