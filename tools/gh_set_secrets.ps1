<#
Script de ejemplo para subir secretos a GitHub usando `gh` (GitHub CLI).

Requisitos:
- `gh` instalado y autenticado (`gh auth login`).

Uso:
.\tools\gh_set_secrets.ps1 -RepoOwner "owner" -RepoName "Inversiones" -ApiKeyFile ".\creds\api_key.txt"

Este script solo muestra ejemplos; verifica las rutas y usa con cuidado.
#>

param(
    [string]$RepoOwner = "",
    [string]$RepoName = "",
    [string]$ApiKeyFile = ".\creds\api_key.txt",
    [string]$JsonCredFile = ".\creds\python-sheets-492415-9f916d7c2cd1.json"
)

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "gh CLI no está instalado. Instala desde https://cli.github.com/"
    exit 1
}

if (-not $RepoOwner -or -not $RepoName) {
    Write-Host "Por favor provee -RepoOwner y -RepoName. Ej: -RepoOwner luisprograma1964-stack -RepoName Inversiones"
    exit 1
}

$repo = "$RepoOwner/$RepoName"

Write-Host "Subiendo secretos al repositorio $repo (no guarda valores en texto en este script)..."

# Helper: set secret from file content
function Set-SecretFromFile([string]$secretName, [string]$filePath) {
    if (Test-Path $filePath) {
        $content = Get-Content $filePath -Raw
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($content)
        $base64 = [System.Convert]::ToBase64String($bytes)
        # gh secret set acepta --body, pero para contenido binario usamos base64 y luego lo decodificamos en el workflow si es necesario
        gh secret set $secretName --repo $repo --body $base64
        Write-Host "  - Secret $secretName seteado (desde $filePath)"
    } else {
        Write-Warning "Archivo $filePath no existe. Saltando $secretName."
    }
}

# Ejemplos: adapta a tus ficheros locales
Set-SecretFromFile -secretName "API_KEY_FILE_CONTENT_BASE64" -filePath $ApiKeyFile
Set-SecretFromFile -secretName "JSON_FILE_CONTENT_BASE64" -filePath $JsonCredFile

Write-Host "Listo. Revisa en https://github.com/$repo/settings/secrets" 
