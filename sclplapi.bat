@echo off
REM SCLPLAPI Launcher for Windows
REM Double-click to launch the TUI

setlocal
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

REM Install dependencies if needed
if not exist ".installed" (
    echo.
    echo Installing SCLPLAPI...
    echo.
    pip install -e . --quiet
    if errorlevel 1 (
        echo Installation failed. Try: pip install -e .
        pause
        exit /b 1
    )
    echo. > .installed
    echo Done!
    echo.
)

REM Create data directory
if not exist "data" mkdir data

REM Launch TUI
python -m app %*

endlocal
