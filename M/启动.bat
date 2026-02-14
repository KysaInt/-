@echo off
setlocal EnableExtensions
chcp 65001 >nul
title 音频可视化工具 (Python 3.13)

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%venv313"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "PYTHONW_EXE=%VENV_DIR%\Scripts\pythonw.exe"
set "REQ_FILE=%SCRIPT_DIR%requirements_audio_viz.txt"
set "TARGET=%SCRIPT_DIR%0.pyw"

cd /d "%SCRIPT_DIR%"

if not exist "%TARGET%" (
    echo [错误] 找不到主程序: %TARGET%
    pause
    exit /b 1
)

if not exist "%REQ_FILE%" (
    echo [错误] 找不到依赖文件: %REQ_FILE%
    pause
    exit /b 1
)

echo [1/4] 检查 Python 3.13...
where py >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 py 启动器，请先安装 Python 3.13。
    pause
    exit /b 1
)
py -3.13 -V >nul 2>nul
if errorlevel 1 (
    echo [错误] 当前系统未检测到 Python 3.13。
    echo 请先安装 Python 3.13 后重试。
    pause
    exit /b 1
)

echo [2/4] 准备虚拟环境: %VENV_DIR%
if not exist "%PYTHON_EXE%" (
    py -3.13 -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败。
        pause
        exit /b 1
    )
)

echo [3/4] 安装/更新依赖...
call "%PYTHON_EXE%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo [错误] pip 基础工具升级失败。
    pause
    exit /b 1
)

call "%PYTHON_EXE%" -m pip install -r "%REQ_FILE%"
if errorlevel 1 (
    echo [错误] 项目依赖安装失败。
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
