# Pendientes y Mejoras del Sistema Inversiones

Fecha de revisión: 2026-07-09

## 1. Tareas Completadas (Recientes)
- [x] **Unificación de Interfaz en Streamlit (`app.py`)**: Panel de control interactivo con caché granular para evitar latencia (se removió `st.cache_data.clear()`).
- [x] **Gestión Segura de Ejecución Local**: Botón "Kickstart Backend" agregado al UI. Emojis sincronizados.
- [x] **Fijado de Lectura de Valores Puros**: Implementada la regla `UNFORMATTED_VALUE` global mediante `robust_decorator` en `auth_google.py` para asegurar consistencia matemática.
- [x] **Notificaciones por Telegram**: Paso a formato HTML enriquecido, previniendo errores de asteriscos huérfanos generados por la IA.
- [x] **Variables de Mercado Completas**: Los dólares Oficial y Tarjeta se integran en el sidebar y en `VARIABLES_MERCADO`.

## 2. Tareas en Curso (Migración Cloud)
- [ ] **Punto 1: Despliegue de la Web App en Streamlit Cloud**:
  - [ ] Subir la aplicación web unificada `app.py` y dependencias a un repositorio privado de GitHub.
  - [ ] Vincular el repositorio a Streamlit Community Cloud (gratis) para ejecución remota.
  - [ ] Configurar secrets en Streamlit Cloud y `config.py` para las credenciales de Sheets y Gemini API.
- [ ] **Punto 2: GitHub Actions (Orquestador Automático)**:
  - [ ] Configurar `.github/workflows/orquestador.yml` para ejecutar a las 7 AM.

## 3. Backlog y Mejoras Futuras
- [ ] **Unificación de Alertas del Supervisor (Bandeja Única)**:
  - Crear hoja consolidada `ALERTAS_SUPERVISOR` para unificar sugerencias de sinónimos y alertas estratégicas (actualmente divididas entre `SUGERENCIAS_SINONIMOS` y `REPORTE_SUPERVISOR`).
  - Integrar lectura y aprobación de estas alertas en una grilla interactiva (Inbox) directamente en la Pestaña 4 de la Web App.
- [ ] **Migración de Base de Datos a Supabase (PostgreSQL en la Nube)**:
  - Reemplazar progresivamente Google Sheets por Supabase para eliminar la latencia de 1.5s a 3s por consulta.
  - Esto permitirá acceso concurrente desde múltiples máquinas y ejecución nativa en procesos batch en la nube.
- [ ] **Auditoría de Tablas Paramétricas**: Limpiar tablas sobrantes como `CONFIG_FUENTES`, `CONFIG_SINONIMOS` y optimizar columnas no utilizadas.
- [ ] **Testeo Integral de Compra/Venta**: Pruebas masivas y de frontera para operaciones, asegurando rebote por sobregiro y correcta trazabilidad en la cartera y `CAJA_LIQUIDEZ`.
