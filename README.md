# Proyecto Inversiones

Este repositorio contiene un sistema en Python para análisis e integración de noticias y datos financieros.

## Estructura principal

- `main.py`, `main_tecnico.py`: archivos principales de ejecución
- `analisis_tecnico.py`, `control_calidad.py`, `procesamiento.py`: módulos de análisis y control
- `news_*`: módulos para obtención de noticias por distintas fuentes
- `carga_historica_bridge.py`: puente de carga de datos históricos
- `ia_utils.py`, `decisor_con_ia.py`: utilidades y decisor con IA
- `creds/`: credenciales locales (no versionadas)
- `.venv/`: entorno virtual local (no versionado)

## Cómo ponerlo en marcha

1. Abrir PowerShell en `c:\Para mi\Inversiones`
2. Crear y activar el entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Actualizar `pip` e instalar dependencias:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

4. Si quieres fijar versiones exactas en el futuro:

```powershell
python -m pip freeze > requirements.txt
```

## Git y GitHub

Este proyecto ya está inicializado con Git y vinculado al remoto:

- Remoto: `https://github.com/luisprograma1964-stack/Inversiones.git`
- Branch actual: `master`

### ¿Main vs Master?

- `master` y `main` son solo nombres de ramas.
- No hay ninguna diferencia funcional entre ellas.
- `master` es el nombre tradicional que usaban repositorios antiguos.
- `main` es el nombre moderno que GitHub usa por defecto hoy en día.

En este proyecto estamos usando `master`, y funciona perfectamente. Si prefieres cambiarlo a `main`, se puede hacer más adelante sin problema.

## Aclaraciones de seguridad

- No subas la carpeta `.venv/` ni `creds/` al repositorio.
- Las credenciales deben mantenerse fuera de GitHub.
- Ya está configurado `.gitignore` para evitar subir `backup/`, `BUP/`, `IA_LOGS/`, `.venv/`, `creds/`, `.env` y otros archivos temporales.

## Cómo avanzar

- Ejecuta los scripts `main.py` o `main_tecnico.py` según lo que necesites correr.
- Si quieres, puedo ayudarte a agregar un `README` más detallado de uso paso a paso y a renombrar la rama a `main`.
