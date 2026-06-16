# Instrucciones para Copilot / Asistente

Propósito: proporcionar directrices claras sobre estilo, expectativas y prompts frecuentes para que las sugerencias sean coherentes con el proyecto.

1. Estilo de código
- Lenguaje principal: Python 3.10+
- Formateo: usa `black` y `isort` (líneas de 88 caracteres)
- Tipado: añade anotaciones de tipos cuando sea práctico

2. Prompts y ejemplos
- "Genera una función que calcule la media móvil exponencial (EMA) para una serie de precios, con parámetros de ventana y manejo de NaN. Incluye docstring y test simple." 
- "Refactoriza este bloque para que sea más legible y añade manejo de errores"

3. Reglas de respuesta
- Prefiere soluciones simples y explícitas antes que micro-optimizaciones.
- Incluye docstrings y ejemplos de uso para funciones públicas.
- Añade tests unitarios cuando la tarea modifica lógica crítica.

4. Flujo de commits
- Mensajes: usa formato corto y descriptivo: `tipo: descripción breve` (ej. `fix: manejar None en carga_historica`)

5. Información de contexto para prompts
- Ruta principal del proyecto: la raíz contiene scripts: `main.py`, `analisis_tecnico.py`, `decisor_con_ia.py`.
- Evitar sugerencias que intenten subir claves o credenciales (archivos `.env` deben mantenerse fuera del control de versiones).

6. Preferencias de interacción con el asistente
- Respuestas cortas y directas.
- Sin adulaciones, cumplidos ni saludos innecesarios.
- Si la petición no es clara, preguntar antes de actuar.
- Preguntar antes de modificar archivos directamente.
- Actuar como experto y revisar detalles del pedido.
- Priorizar claridad y precisión por encima de explicación extensa.

Si quieres, personalizo estos ejemplos con tus reglas exactas (nombres de linters, convenciones de commits, o frases para priorizar).

6. Preferencias de interacción
- Respuestas cortas y directas.
- Sin adulaciones, cumplidos ni saludos innecesarios.
- Si la petición no es clara, preguntar antes de actuar.
- Preguntar antes de modificar archivos directamente.
- Actuar como experto y revisar detalles del pedido.
- Priorizar claridad y precisión por encima de explicación extensa.
- Preferir herramientas gratuitas cuando sea posible (p. ej. `.env` local, `GitHub Secrets` para integraciones).