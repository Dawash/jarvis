@echo off
chcp 65001 >nul 2>&1
title JARVIS - Personal AI Assistant

echo.
echo      ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
echo      ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
echo      ██║███████║██████╔╝██║   ██║██║███████╗
echo ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
echo ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
echo  ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
echo.
echo    Personal AI Assistant
echo.

cd /d "%~dp0"

:: Check Python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is required. Install from https://python.org
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
