@echo off
title JARVIS - Personal AI Assistant

echo.
echo   ============================================
echo        J A R V I S
echo        Personal AI Assistant
echo   ============================================
echo.

cd /d "%~dp0"

:: Find a compatible Python (3.11, 3.12, or 3.13)
set PYTHON=
set PYVER=

:: Try py launcher first (preferred on Windows)
where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    for %%V in (3.13 3.12 3.11) do (
        if not defined PYTHON (
            py -%%V --version >nul 2>&1
            if not errorlevel 1 (
                set PYTHON=py -%%V
                for /f "tokens=2 delims= " %%r in ('py -%%V --version 2^>^&1') do set PYVER=%%r
            )
        )
    )
)

:: Try versioned executables on PATH
if not defined PYTHON (
    for %%V in (3.13 3.12 3.11) do (
        if not defined PYTHON (
            where python%%V >nul 2>&1
            if not errorlevel 1 (
                set PYTHON=python%%V
                for /f "tokens=2 delims= " %%r in ('python%%V --version 2^>^&1') do set PYVER=%%r
            )
        )
    )
)

:: Fall back to default python if it's a compatible version
if not defined PYTHON (
    where python >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Python is required. Install from https://python.org
        pause
        exit /b 1
    )
    for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
    for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
        if %%a equ 3 if %%b geq 11 if %%b leq 13 set PYTHON=python
    )
)

if not defined PYTHON (
    echo [ERROR] Python 3.11-3.13 is required but not found.
    echo [ERROR] Default python is %PYVER%
    echo [ERROR] Install Python 3.12 or 3.13 from https://python.org
    pause
    exit /b 1
)

echo [*] Using %PYTHON% (Python %PYVER%)

:: Create venv if needed
if not exist "venv" (
    echo [*] Creating virtual environment...
    %PYTHON% -m venv venv
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
