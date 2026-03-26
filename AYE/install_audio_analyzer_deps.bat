@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "PYTHON_CMD="

call :find_python
if not defined PYTHON_CMD (
    echo No usable global Python was found.
    echo Install Python 3.11 or 3.13 system-wide, then rerun this script.
    exit /b 1
)

echo Using Python: %PYTHON_CMD%
echo.

echo Installing core packages...
call %PYTHON_CMD% -m pip install numpy PySide6 soundcard
if errorlevel 1 (
    echo Failed to install core packages.
    exit /b 1
)

echo.
echo Installing aubio separately...
call %PYTHON_CMD% -m pip install aubio
if errorlevel 1 (
    echo.
    echo aubio installation failed.
    echo On Windows this usually means C++ Build Tools are missing,
    echo or this Python version has no prebuilt aubio wheel.
    echo.
    echo Suggested next steps:
    echo 1. Install Microsoft C++ Build Tools 14.0 or newer.
    echo 2. Prefer a global Python 3.11 installation for this app.
    echo 3. Rerun this script after Build Tools are installed.
    exit /b 2
)

echo.
echo All required packages were installed successfully.
exit /b 0

:find_python
where py.exe >nul 2>nul
if not errorlevel 1 (
    py -3.11 -c "import sys" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=py -3.11"
        goto :eof
    )

    py -3.13 -c "import sys" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=py -3.13"
        goto :eof
    )
)

where python.exe >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    goto :eof
)

goto :eof