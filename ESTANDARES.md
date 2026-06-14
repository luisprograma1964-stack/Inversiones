# Estándares de Programación - Proyecto Inversiones

Este documento define las reglas, estructuras y buenas prácticas para mantener la coherencia en todos los scripts de Python del proyecto.

## 1. Estructura de los Scripts y Ejecución
Para permitir que los scripts se puedan ejecutar tanto de forma independiente como orquestados desde un script maestro:
- Todo el código principal debe estar encapsulado en una función principal (ej: `def ejecutar_proceso():`).
- Al final de cada archivo, se debe incluir el bloque de ejecución estándar:
  ```python
  if __name__ == "__main__":
      ejecutar_proceso()
  ```

## 2. Configuración Centralizada
- Toda constante, nombre de hoja (Worksheet), nombre de archivo o variable global debe residir en `config.py`.
- No deben existir strings "quemados" (hardcodeados) en el código referentes a nombres de hojas (ej. usar `config.WS_LOG_SISTEMA` en lugar de `"LOG_SISTEMA"`).

## 3. Sistema de Logs (LOG_SISTEMA)
Todo evento importante, advertencia o error debe registrarse centralizadamente usando la función `procesamiento.registrar_log`.
- **Estructura en Sheets**: `[Fecha/Hora, Nivel, Origen, Mensaje]`
- **Niveles Permitidos**:
  - `INFO`: Inicio, fin o hitos normales del proceso.
  - `WARNING`: Anomalías o descartes que no detienen el proceso.
  - `ERROR`: Fallas en capturas específicas o funciones que no abortan todo el programa.
  - `CRITICAL`: Fallas graves que impiden que el script termine su ejecución.
- **Origen**: Se detecta automáticamente el nombre del archivo de Python que genera el log (ej. `main.py`). No es necesario pasarlo como parámetro, a menos que se quiera forzar un nombre distinto.

## 4. Estado de Procesos (ESTADO_PROCESOS)
Los scripts que corren periódicamente deben actualizar su estado para monitoreo (semáforos).
- Se debe usar la función centralizada `procesamiento.actualizar_estado_proceso(ws_status, estado, detalle)`.
- **Estructura en Sheets**: `[Nombre_Proceso, Fecha/Hora, Estado, Detalle, Tiempo_Ejecucion]`
- **Nombre_Proceso**: Al igual que en los logs, se detecta automáticamente el nombre del archivo de Python. Ya no es necesario pasarlo a mano.
- **Estados Permitidos**:
  - `PROCESANDO`: Al iniciar.
  - `OK`: Al finalizar exitosamente.
  - `ERROR`: Si el proceso falla globalmente.

## 5. Manejo de Fechas y Horas
- Para mantener coherencia universal y compatibilidad nativa con Pandas, el formato estándar estricto de Fecha debe ser la norma ISO: `YYYY-MM-DD` (ej. `2026-05-19`).
- Si se requiere fecha y hora (como en logs o marcas de actualización), el formato es: `YYYY-MM-DD HH:MM:SS`.
- Queda totalmente prohibido el uso de barras (`/`) o formatos como `DD/MM/YYYY`.

## 6. Conexión a Base de Datos (Google Sheets)
- Todas las conexiones deben iniciarse a través de `auth_google.conectar()`.
- Se debe validar siempre si la conexión fue exitosa antes de instanciar las hojas (Worksheets).
- **REGLA ESTRICTA PARA IA:** Antes de leer, escribir o modificar cualquier código que interactúe con las hojas de cálculo, el asistente debe consultar obligatoriamente el documento `ESTRUCTURA_SHEETS.md` para garantizar que se respetan las columnas, el orden y los formatos allí definidos.

## 7. Manejo de Errores (Try/Except)
- Todo bloque principal o consulta externa (APIs, Google Finance) debe estar dentro de bloques `try/except`.
- Los errores capturados en el `except Exception as e:` deben enviarse al log como `ERROR` o `CRITICAL` para no perder visibilidad.

## 8. Documentación y Comentarios (Docstrings)
- Todo programa debe incluir una descripción funcional al inicio del archivo explicando para qué sirve de forma general.
- Todas las funciones (especialmente las principales) deben tener un *Docstring* debajo de su definición (`def funcion(): ... """Descripción"""`) que explique qué hace.
- Se deben incluir comentarios breves (con `#`) en las rutinas comunes o pasos lógicos importantes para aclarar *qué* se está haciendo en cada paso, facilitando la lectura a futuros programadores.

## 9. Reglas Estrictas para el Asistente (IA)
- **Cero Suposiciones:** Si el requerimiento del usuario (prompts o tareas) es ambiguo, le falta contexto, o no define claramente cómo manejar bordes (edge cases), la IA tiene la obligación estricta de detenerse y hacer las preguntas necesarias para aclarar. Queda prohibido "asumir" o inventar la intención del usuario.
- **Validación de Estructura:** Antes de modificar cualquier interacción con Google Sheets, es obligatorio consultar `ESTRUCTURA_SHEETS.md` para evitar desincronizaciones de columnas.
