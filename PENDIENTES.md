# Pendientes y mejoras del sistema Inversiones

Fecha de revisión: 2026-06-16

## 1. Estado general
- El sistema está estructurado como un pipeline de módulos (`main.py`, `main_tecnico.py`, `ensamblador.py`, `captura_noticias.py`, `decisor_con_ia.py`).
- Hay buenas prácticas de documentación y estándares (`ESTANDARES.md`, `ESTRUCTURA_SHEETS.md`, `copilot-instructions.md`).
- Falta un documento único de seguimiento de tareas y mejoras; este archivo cubre esa necesidad.

## 2. Problemas graves detectados
 - [x] `config.py` define credenciales sensibles directamente: Movido a `os.getenv` con soporte `.env`.
 - [x] `config.py` duplicación: Se eliminó la doble definición de `ORIGEN_LOG_TECNICO`.
 - [x] `decisor_con_ia.py` inicialización: Movida dentro de `ejecutar_decisor()` para evitar fallos en importación.
 - [x] `README.md` rama: Actualizado a `main`.
- El sistema no tiene un registro único de pendientes ni un plan de continuidad; por eso es fácil olvidarlo.

## 3. Problemas importantes / riesgos críticos
 - [x] `captura_noticias.py` salida abrupta: Reemplazado `sys.exit(1)` por excepciones controladas.
 - [x] `decisor_con_ia.py` hardcoding: Ahora usa `config.WS_ESTADO_PROCESOS`.
- `carga_historica_bridge.py` descarga datos en un buffer de Sheets y depende de `GOOGLEFINANCE(...)` con espera fija de 20 segundos.
  - Esto es frágil si Google Sheets responde lento o la fórmula no se resuelve.
  - Recomendación: agregar reintentos y validación de que el buffer se cargó correctamente antes de parsearlo.

## 4. Problemas menores detectados
- El proyecto depende mucho de `print()` para estado y errores en lugar de un log central uniforme.
- Algunos módulos son mixtos: lógica principal y ejecución directa conviven sin una capa clara de importable/ejecutable.
- Hay impresión de debug y mensajes en consola en `main_tecnico.py` y `analisis_tecnico.py` que podrían reducirse o canalizarse a logs.
- `ESTRUCTURA_SHEETS.md` y `config.py` no listan explicitamente todas las hojas usadas en el proyecto (`DOWNLOAD_BUFFER`, `CAJA_LIQUIDEZ`, etc.).
- No hay pruebas unitarias generales del pipeline; solo hay tests puntuales en `TEST/test_ia.py`.

## 5. Mejoras recomendadas
- Establecer un flujo de ejecución claro en `README.md` con pasos de `setup`, `run`, y `debug`.
- Agregar validación previa de la planilla Google Sheets: verificar que todas las pestañas necesarias existan antes de iniciar el pipeline.
- Centralizar el manejo de configuración sensible en `config.py` mediante variables de entorno.
- Añadir un comando o script de diagnóstico rápido que valide:
  - credenciales
  - presencia de hojas en Sheets
  - formato de encabezados en las hojas críticas
- Mantener `copilot-instructions.md` actualizado con tus preferencias de interacción.
- Crear pruebas de integración mínima para que una ejecución de pipeline no rompa por cambios inesperados.

## 6. Acciones inmediatas sugeridas
 1. [x] Corregir `config.py` (Duplicación).
 2. [x] Refactorizar `decisor_con_ia.py` (Init segura).
 3. [x] Actualizar `README.md` (Rama main).
 4. [x] Validación de hojas en `captura_noticias.py` (Sin sys.exit).
5. Empezar a usar `PENDIENTES.md` como fuente única del estado del proyecto.

## 7. Cómo seguir
- Cada vez que haya un bug o mejora nueva, agregarlo aquí con fecha y estado.
- Si quieres, te ayudo a transformar estos pendientes en issues de GitHub o en tareas específicas paso a paso.

## 8. Acciones aplicadas (2026-06-16)
- Se actualizó `config.py` para leer valores sensibles desde variables de entorno (`os.environ`) y soportar opcionalmente `.env` mediante `python-dotenv`.
- Se creó `.env.example` con las claves/parametros necesarios (no contiene valores secretos).
- Se creó `.gitignore` incluyendo `.env`, `.venv/` y otros artefactos locales.

## 9. Próximo paso recomendado
- Decide dónde almacenar los secretos a largo plazo: `GitHub Secrets` (recomendado), `Cloud Secret Manager` o un gestor de contraseñas. Puedo automatizar el script de subida de secrets si elegís `GitHub Secrets`.

## 10. Acciones realizadas: GitHub Secrets (2026-06-16)
- Se añadió `SECRETS_RECOMMENDATIONS.md` con opciones gratuitas y de reputada seriedad.
- Se añadió `tools/gh_set_secrets.ps1` como script de ejemplo para subir secretos usando `gh` CLI (adaptable a tus rutas).

Nota: el script sube el contenido de ficheros codificado en base64 como secreto; en tus workflows deberás decodificarlo antes de usar.

## 11. Workflow añadido
- Se añadió el workflow de validación de secretos en `.github/workflows/validate-secrets.yml`.
- El workflow falla temprano si faltan `API_KEY_FILE_CONTENT_BASE64` o `JSON_FILE_CONTENT_BASE64`.
- Puedes ejecutar el workflow manualmente desde la pestaña "Actions" o al hacer `push` a `main`.

## 12. Documentación añadida
- Se añadió `README_SECRETS.md` con instrucciones paso a paso para usar `tools/gh_set_secrets.ps1`, subir secretos y decodificarlos en workflows.

## 13. Primer recuadro: Paso a paso de ejecución del sistema (resumen rápido)
Este es el checklist corto para no olvidarte qué se ejecuta y en qué orden. Pégalo en tu pantalla si querés.

1) Pre-flight / Paso 0 - Health Check IA
  - Verifica disponibilidad de modelos IA (si aplica).
  - Comprueba credenciales y conexión a Google Sheets.

2) Variables de Mercado - Paso 1
  - `main.ejecutar_sincronizacion()` descarga variables (Dólar, inflación, etc.) y las guarda en `VARIABLES_MERCADO`.

3) Sincronización Histórica - Paso 2
  - `carga_historica_bridge.ejecutar_carga_bridge()` actualiza `HISTORICO_VALORES` (Google Finance / API).

4) Análisis Técnico - Paso 3
  - `main_tecnico.ejecutar_analisis_completo()` calcula indicadores y escribe `ANALISIS_TECNICO`.

5) Captura de Noticias - Paso 3.5
  - `captura_noticias.ejecutar_captura_noticias()` recolecta y hace triage con IA (opcional para core).

6) Motor de IA / Decisor - Paso 4
  - `decisor_con_ia.ejecutar_decisor()` procesa `ANALISIS_TECNICO` y genera `REPORTE_IA` / `MATRIZ_RECOMENDACIONES`.

7) Cierre
  - Se actualizan `LOG_SISTEMA` y `ESTADO_PROCESOS` con resultados y tiempos.

Comandos locales rápidos:

```powershell
# Activar venv
.\.venv\Scripts\Activate.ps1

# Ejecutar ensamblador completo (haz backup de credenciales antes)
python ensamblador.py

# Ejecutar solo smoke (sin IA)
python tools\smoke_no_ia.py
```

Guarda este bloque como recordatorio y te lo actualizo si cambian los pasos.
