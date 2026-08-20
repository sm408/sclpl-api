@echo off
REM ============================================================
REM  SCLPLAPI Web Studio Launcher
REM  Double-click to start the web UI server
REM ============================================================

setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo [INFO] SCLPLAPI Web Studio
echo.

REM ── Check Python ────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

REM ── Use venv Python directly ────────────────────────────────
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
    echo [INFO] Using virtual environment Python
) else (
    set "PYTHON=python"
    echo [INFO] Using system Python
)

REM ── Install dependencies if needed ──────────────────────────
if not exist ".installed" (
    echo.
    echo [SETUP] Installing SCLPLAPI with web dependencies...
    echo.
    "%PYTHON%" -m pip install -e .[web] --quiet
    if errorlevel 1 (
        echo [ERROR] Installation failed. Try: pip install -e .[web]
        pause
        exit /b 1
    )
    echo. > .installed
    echo [SETUP] Done!
    echo.
)

REM ── Create data directory ───────────────────────────────────
if not exist "data" mkdir data

REM ── Clean stale database lock files ─────────────────────────
if exist "data\sclplapi.db-shm" del /f /q "data\sclplapi.db-shm" >nul 2>&1
if exist "data\sclplapi.db-wal" (
    echo [INFO] Cleaning up stale database journal files...
    del /f /q "data\sclplapi.db-wal" >nul 2>&1
)

REM ── Launch Web UI Server ────────────────────────────────────
echo.
echo  =============================================
echo   SCLPLAPI Web Studio
echo  =============================================
echo.
echo  Frontend:    http://127.0.0.1:5173
echo  Backend:     http://127.0.0.1:8000
echo  API docs:    http://127.0.0.1:8000/docs
echo.
echo  Press Ctrl+C to stop the servers
echo.

"%PYTHON%" start-web.py

REM Open the frontend after a short delay
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:5173

REM ── Cleanup on exit ─────────────────────────────────────────
echo.
echo [INFO] Web server stopped.
pause
endlocal
