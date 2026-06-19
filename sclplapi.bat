@echo off
REM SCLPLAPI Portable Launcher for Windows
REM Double-click this file or run: sclplapi.bat

setlocal

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Please install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

REM Install dependencies if needed
if not exist ".installed" (
    echo.
    echo Installing SCLPLAPI dependencies...
    echo.
    pip install -e ".[all]" --quiet
    if errorlevel 1 (
        echo Installation failed. Try running: pip install -e ".[all]"
        pause
        exit /b 1
    )
    echo. > .installed
    echo Installation complete!
    echo.
)

REM Create data directory if needed
if not exist "data" mkdir data

REM Launch
python -m app %*

endlocal
