# JARVIS - Personal AI Assistant (PowerShell Launcher)
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "     JARVIS - Personal AI Assistant" -ForegroundColor Cyan
Write-Host "     ==============================" -ForegroundColor Cyan
Write-Host ""

Set-Location $PSScriptRoot

# Check Python
$python = $null
foreach ($cmd in @("python", "python3", "py")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        $python = $cmd
        break
    }
}

if (-not $python) {
    Write-Host "[ERROR] Python is required. Install from https://python.org" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[*] Using: $python" -ForegroundColor Green

# Check Python version (3.11-3.13 required)
$pyVersion = & $python -c "import sys; print(f'{sys.version_info.minor}')" 2>$null
$pyMinor = [int]$pyVersion
if ($pyMinor -lt 11) {
    Write-Host "[ERROR] Python 3.11+ is required. You have Python 3.$pyMinor" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
if ($pyMinor -gt 13) {
    Write-Host "[ERROR] Python 3.14+ is not yet supported (pydantic-core has no wheels)." -ForegroundColor Red
    Write-Host "[ERROR] Please install Python 3.12 or 3.13 from https://python.org" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Create venv if needed
if (-not (Test-Path "venv")) {
    Write-Host "[*] Creating virtual environment..." -ForegroundColor Yellow
    & $python -m venv venv
}

# Activate venv
& ".\venv\Scripts\Activate.ps1"

# Install deps
Write-Host "[*] Installing dependencies..." -ForegroundColor Yellow
pip install -q -r requirements.txt

# Check for .env
if (-not (Test-Path ".env")) {
    Write-Host "[!] No .env file found. Copying from .env.example" -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "[!] IMPORTANT: Edit .env and add your ANTHROPIC_API_KEY!" -ForegroundColor Red
    Write-Host ""
}

# Create data dir
New-Item -ItemType Directory -Path "data" -Force | Out-Null

# Read port
$port = "8000"
if (Test-Path ".env") {
    $envContent = Get-Content ".env"
    foreach ($line in $envContent) {
        if ($line -match "^PORT=(.+)") {
            $port = $Matches[1].Trim()
        }
    }
}

Write-Host ""
Write-Host "[*] Starting JARVIS on http://localhost:$port" -ForegroundColor Green
Write-Host "[*] Open your browser to the URL above" -ForegroundColor Cyan
Write-Host ""

python -m uvicorn backend.main:app --host 0.0.0.0 --port $port --reload
