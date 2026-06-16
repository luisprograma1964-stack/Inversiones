# Gestión de secretos: recomendaciones y opciones

Breve: usar `GitHub Secrets` para CI + `.env` local para desarrollo. Mantener backups seguros (p. ej. Bitwarden).

Opciones gratuitas y de reconocida seriedad
- **GitHub Secrets**: integrado en GitHub, ideal para almacenar secretos para Actions y workflows. Gratis para repos públicos y privados (con límites de uso de Actions según plan). Recomendado para este repo.
- **Bitwarden**: gestor de contraseñas con plan gratuito y opción self-host. Reputado y práctico para guardar copias de `.env` y contraseñas.
- **HashiCorp Vault (OSS)**: solución open-source para gestión de secretos en infraestructuras más complejas. Requiere despliegue propio pero es muy robusto.
- **GPG (gpg)**: cifrar archivos de configuración (`.env`) y guardarlos en el repositorio como archivo cifrado. Libre y seguro si se gestiona bien.
- **python-dotenv**: biblioteca gratuita para cargar `.env` localmente (no gestiona secretos, solo facilita uso local).
- **GitHub CLI (`gh`)**: herramienta gratuita para interactuar con GitHub y subir secrets con `gh secret set`.

Opciones comerciales (reputadas)
- **1Password**, **AWS Secrets Manager**, **GCP Secret Manager**, **Azure Key Vault** — opciones empresariales con características avanzadas. Son reputadas pero pueden generar costes.

Recomendación práctica para este proyecto
1. Guardar secretos de ejecución en **GitHub Secrets** (capa remota segura para CI/Actions).
2. Mantener un `.env` local para desarrollo y guardar una copia en **Bitwarden** o equivalente.
3. Evitar subir `.env` al repositorio. Usar `.env.example` para documentar variables.
4. Usar el script `tools/gh_set_secrets.ps1` para subir secretos fácilmente desde tu máquina local.

Si querés, automatizo la creación de un workflow de GitHub Actions que valide que los secrets están presentes antes de ejecutar el pipeline.
