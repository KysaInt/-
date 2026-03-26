@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "APP=%SCRIPT_DIR%audio_analyzer.pyw"

if not exist "%APP%" (
    echo App file not found: "%APP%"
    exit /b 1
)

where pyw.exe >nul 2>nul
if not errorlevel 1 (
    start "" pyw -3.11 "%APP%"
    exit /b 0
)

where pythonw.exe >nul 2>nul
if not errorlevel 1 (
    start "" pythonw "%APP%"
    exit /b 0
)

echo Global Python 3.11 not found. Install Python 3.11 system-wide and ensure pyw.exe or pythonw.exe is in PATH.
exit /b 1
