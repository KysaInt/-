@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title 音频可视化工具 OpenGL 版 (Python 3.13)

set "SCRIPT_DIR=%~dp0"
set "TARGET=%SCRIPT_DIR%0.pyw"
set "VENV_DIR=%SCRIPT_DIR%venv313"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "PYTHONW_EXE=%VENV_DIR%\Scripts\pythonw.exe"
set "RUN_MODE=%~1"

cd /d "%SCRIPT_DIR%"

if /I "%RUN_MODE%"=="debug" (
    title 音频可视化工具 OpenGL 版 调试启动 (Python 3.13)
)

if not exist "%TARGET%" (
    echo [错误] 找不到主程序: %TARGET%
    pause
    exit /b 1
)

if not exist "%PYTHON_EXE%" (
    echo [错误] 未找到虚拟环境 Python: %PYTHON_EXE%
    echo 请先运行 安装依赖.bat 完成环境准备。
    pause
    exit /b 1
)

if not exist "%PYTHONW_EXE%" (
    echo [错误] 未找到虚拟环境 Pythonw: %PYTHONW_EXE%
    echo 请先运行 安装依赖.bat 完成环境准备。
    pause
    exit /b 1
)

call "%PYTHON_EXE%" -c "import sys" >nul 2>nul
if errorlevel 1 (
    echo [错误] 当前虚拟环境不可用。
    echo 请重新运行 安装依赖.bat 修复环境。
    pause
    exit /b 1
)

echo [快速启动] 使用现有虚拟环境启动程序...
if /I "%RUN_MODE%"=="debug" (
    echo [调试] 当前为控制台调试模式。
    echo [DEBUG] Run .\启动.bat for normal startup.
    echo.
    call "%PYTHON_EXE%" "%TARGET%"
    echo.
    echo [调试] 程序已退出，退出码: !errorlevel!
    pause
    exit /b !errorlevel!
)

start "" "%PYTHONW_EXE%" "%TARGET%"
if errorlevel 1 (
    echo [错误] 启动失败。
    pause
    exit /b 1
)

exit /b 0
