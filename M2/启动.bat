@echo off
setlocal EnableExtensions
chcp 65001 >nul
title 音频可视化工具 OpenGL 版 (Python 3.13)

set "SCRIPT_DIR=%~dp0"
set "TARGET=%SCRIPT_DIR%0.pyw"
set "PYTHONW_EXE=%SCRIPT_DIR%venv313\Scripts\pythonw.exe"

cd /d "%SCRIPT_DIR%"

if not exist "%TARGET%" (
    echo [错误] 找不到主程序: %TARGET%
    pause
    exit /b 1
)

call "%SCRIPT_DIR%准备环境.bat"
if errorlevel 1 (
    pause
    exit /b 1
)

echo [4/4] 启动程序...
start "" "%PYTHONW_EXE%" "%TARGET%"
if errorlevel 1 (
    echo [错误] 启动失败。
    pause
    exit /b 1
)

exit /b 0