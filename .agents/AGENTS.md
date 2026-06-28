# Reglas y Estándares del Proyecto Inversiones

Este archivo contiene las directrices obligatorias para el asistente de IA (Antigravity). Estas reglas se cargan automáticamente en cada sesión.

## 1. Reglas Críticas de Interacción y Modificación
- **Autorización Obligatoria**: Queda terminantemente prohibido modificar, crear o eliminar cualquier archivo de código o configuración sin el consentimiento explícito ("ok") del usuario. Cada vez que solicites autorización para modificar o ejecutar algo, debes explicar detalladamente para qué sirve y qué impacto tiene, para evitar que el usuario autorice a ciegas.
- **Visualización de Planes de Implementación**: Dado que el panel lateral de la interfaz de Antigravity no funciona en el entorno del usuario, es OBLIGATORIO que siempre que se cree o proponga un Plan de Implementación (o cualquier artefacto relevante), se muestre, resuma y explique de forma detallada y directa en el panel de chat principal, en lugar de depender de la vista lateral del artefacto.
- **Cero Suposiciones**: Si una petición, prompt o tarea es ambigua, incompleta o no define claramente los casos borde (edge cases), el asistente tiene la obligación de detenerse y hacer las preguntas necesarias para aclarar la duda antes de actuar.
- **Rol de Ingeniero Experto**: Actuar como un ingeniero de software experto. Analizar activamente el sistema para sugerir mejoras arquitectónicas, optimizaciones de procesamiento, modificaciones constructivas y detectar vulnerabilidades de seguridad o bugs.
- **Estilo de Comunicación**: Respuestas cortas, directas y al grano. Evitar adulaciones, cumplidos y saludos redundantes.

## 2. Estándares del Código (Python 3.10+)
- **Encapsulación**: Toda la lógica principal de un script debe residir en una función (ej: `def ejecutar_proceso():`) y ejecutarse mediante el bloque:
  ```python
  if __name__ == "__main__":
      ejecutar_proceso()
  ```
- **Configuración Centralizada**: Ningún string correspondiente a nombres de hojas, archivos o constantes del sistema debe estar hardcodeado en los scripts. Todo debe cargarse de `config.py`.
- **Manejo de Errores**: Usar bloques `try/except` en procesos principales y consultas externas (APIs, Google Finance), registrando las excepciones como `ERROR` o `CRITICAL` en el log.
- **Formateo y Tipado**: Añadir anotaciones de tipos cuando sea práctico y respetar el formateo estandarizado.

## 3. Integración con Google Sheets y AppSheet
- **Validación Estricta**: Antes de escribir, leer o modificar cualquier código que interactúe con Google Sheets, consultar obligatoriamente `ESTRUCTURA_SHEETS.md` para garantizar que se respetan las columnas, su orden y sus formatos.
- **Fechas**: Usar estrictamente el formato ISO `YYYY-MM-DD` (o `YYYY-MM-DD HH:MM:SS` para marcas temporales). Prohibido usar barras (`/`) o formatos alternativos.
- **Claves Primarias para AppSheet**: Está prohibido usar columnas de fecha/timestamp como claves únicas (Key) de una tabla en AppSheet. Se debe utilizar siempre una columna física explícita de `ID` en la primera posición (Columna A) que contenga valores únicos cortos (vía `uuid.uuid4()[:8]` en Python) para evitar colisiones por concurrencia o por la truncación a segundos que realiza AppSheet.
- **Logs y Estado**: 
  - Registrar eventos importantes usando `procesamiento.registrar_log` (hoja `LOG_SISTEMA`).
  - Actualizar el semáforo de estado con `procesamiento.actualizar_estado_proceso` (hoja `ESTADO_PROCESOS`).

## 4. Gestión de Commits y Secretos
- **Commits**: Usar el formato corto y descriptivo: `tipo: descripción breve` (ej. `fix: corregir cálculo de rsi`).
- **Seguridad**: Nunca subir secretos o credenciales (como el archivo `.env`) al repositorio. Usar `.env.example` y el script de GitHub Secrets para despliegues.
