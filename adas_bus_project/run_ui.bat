@echo off
REM One-click launcher for UrbanShield ADAS (double-click to run)
SETLOCAL
PUSHD "%~dp0"
SET "VENV_PY=%~dp0\.venv\Scripts\python.exe"
IF EXIST "%VENV_PY%" (
    echo Using virtualenv python: "%VENV_PY%"
    "%VENV_PY%" -u "%~dp0main.py"
) ELSE (
    echo Virtualenv not found, falling back to `python` on PATH
    python -u "%~dp0main.py"
)
POPD
ENDLOCAL
EXIT /B %ERRORLEVEL%
