# README - Subir y usar Secrets (GitHub)

Este documento explica cómo usar el script `tools/gh_set_secrets.ps1` para subir secretos a GitHub, y cómo decodificarlos en un workflow de Actions.

Requisitos locales:
- `gh` (GitHub CLI) instalado y autenticado: `gh auth login`
- PowerShell (Windows) o PowerShell Core

1) Subir secretos con el script (PowerShell)

Ejemplo (desde la raíz del repo):

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\tools\gh_set_secrets.ps1 -RepoOwner "luisprograma1964-stack" -RepoName "Inversiones" -ApiKeyFile ".\creds\api_key.txt" -JsonCredFile ".\creds\python-sheets-492415-9f916d7c2cd1.json"
```

El script sube el contenido de los archivos codificado en base64 como secretos llamados:
- `API_KEY_FILE_CONTENT_BASE64`
- `JSON_FILE_CONTENT_BASE64`

2) Subir secretos manualmente (opcional)

Con `gh` puedes también subir un secreto simple:

```bash
gh secret set API_KEY_FILE_CONTENT_BASE64 --repo luisprograma1964-stack/Inversiones --body "$(base64 -w0 creds/api_key.txt)"
```

3) Decodificar y usar los secretos en un workflow de GitHub Actions

Dentro de tu workflow (ej. `validate-secrets.yml` o el pipeline), decodifica y escribe los archivos:

```yaml
- name: Restore credentials
  run: |
    echo "${{ secrets.API_KEY_FILE_CONTENT_BASE64 }}" | base64 --decode > creds/api_key.txt
    echo "${{ secrets.JSON_FILE_CONTENT_BASE64 }}" | base64 --decode > creds/python-sheets-492415-9f916d7c2cd1.json
```

Después puedes exportar la variable de entorno que algunas librerías esperan:

```yaml
- name: Set GOOGLE_APPLICATION_CREDENTIALS
  run: |
    echo "GOOGLE_APPLICATION_CREDENTIALS=creds/python-sheets-492415-9f916d7c2cd1.json" >> $GITHUB_ENV
```

4) Buenas prácticas
- No subas `.env` al repo; usa `.env.example` para documentar variables.
- Mantén una copia de los secretos en un gestor seguro (Bitwarden, 1Password) fuera del repo.
- Prueba el script en tu máquina antes de usarlo en producción.

Si querés, agrego un pequeño ejemplo de workflow que restaure los secretos y ejecute un paso de verificación.
