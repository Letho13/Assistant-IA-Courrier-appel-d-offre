@echo off
setlocal
cd /d "%~dp0"

py -3 --version >nul 2>nul
if errorlevel 1 (
    python --version >nul 2>nul
    if errorlevel 1 (
        echo Python 3 est requis. Installe-le depuis https://www.python.org/downloads/
        pause
        exit /b 1
    )
    set "PYTHON=python"
) else (
    set "PYTHON=py -3"
)

if not exist ".venv\Scripts\python.exe" (
    echo Preparation de l'environnement de demonstration...
    %PYTHON% -m venv .venv
    if errorlevel 1 goto :error
)

echo Verification des dependances...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :error

echo Ouverture de la demonstration Assistant ADV...
".venv\Scripts\python.exe" -m streamlit run app.py
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo La demonstration n'a pas pu demarrer. Verifie Python et la connexion Internet.
pause
exit /b 1
