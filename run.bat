@echo off
title JARVIS - Personal AI Assistant

echo.
echo   ============================================
echo        J A R V I S
echo        Personal AI Assistant
echo   ============================================
echo.

cd /d "%~dp0"

:: Check Python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is required. Install from https://python.org
    pause
    exit /b 1
)

:: Check Python version (need 3.11 or 3.12 or 3.13)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PYMAJOR=%%a
    set PYMINOR=%%b
)
if %PYMAJOR% neq 3 (
    echo [ERROR] Python 3.11-3.13 is required. You have Python %PYVER%
    pause
    exit /b 1
)
if %PYMINOR% gtr 13 (
    echo [ERROR] Python 3.14+ is not yet supported. You have Python %PYVER%
    echo [ERROR] Please install Python 3.12 or 3.13 from https://python.org
    echo [ERROR] Make sure the older Python is first on your PATH.
    pause
    exit /b 1
)
if %PYMINOR% lss 11 (
    echo [ERROR] Python 3.11+ is required. You have Python %PYVER%
    pause
    exit /b 1
)

:: Create venv if needed
if not exist "venv" (
    echo [*] Creating virtual environment...
    python -m venv venv
)

:: Activate venv
call venv\Scripts\activate.bat

:: Install deps
echo [*] Installing dependencies...
pip install -q -r requirements.txt

:: Check for .env
if not exist ".env" (
    echo [!] No .env file found. Copying from .env.example
    copy .env.example .env >nul
    echo [!] Please edit .env and add your API keys!
    echo.
)

:: Create data dir
if not exist "data" mkdir data

:: Read port from .env or default
set PORT=8000
for /f "tokens=1,2 delims==" %%a in (.env) do (
    if "%%a"=="PORT" set PORT=%%b
)

echo [*] Starting JARVIS on http://localhost:%PORT%
echo [*] Open your browser and go to the URL above.
echo.

python -m uvicorn backend.main:app --host 0.0.0.0 --port %PORT% --reload

pause
