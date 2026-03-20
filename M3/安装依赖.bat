@echo off
setlocal EnableExtensions
chcp 65001 >nul
title M3 依赖安装 (Python 3.13)

set "SCRIPT_DIR=%~dp0"
set "TARGET=%SCRIPT_DIR%0.pyw"
set "VENV_DIR=%SCRIPT_DIR%venv313"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "PYTHONW_EXE=%VENV_DIR%\Scripts\pythonw.exe"
set "REQ_FILE=%SCRIPT_DIR%requirements_audio_viz.txt"
set "HOST_PYTHON_CMD="

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

echo [1/3] 检查 Python 3.13...
call :resolve_python
if errorlevel 1 (
    pause
    exit /b 1
)

echo [2/3] 准备虚拟环境...
call :ensure_venv
if errorlevel 1 (
    pause
    exit /b 1
)

echo [3/3] 安装/更新依赖...
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

echo.
echo [完成] 依赖已经准备好，可以直接运行 启动.bat
pause
exit /b 0

:resolve_python
where py >nul 2>nul
if not errorlevel 1 (
    py -3.13 -V >nul 2>nul
    if not errorlevel 1 (
        set "HOST_PYTHON_CMD=py -3.13"
        echo [信息] 使用 py -3.13
        exit /b 0
    )
)

where python >nul 2>nul
if not errorlevel 1 (
    python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 13) else 1)" >nul 2>nul
    if not errorlevel 1 (
        set "HOST_PYTHON_CMD=python"
        echo [信息] 使用 python
        exit /b 0
    )
)

where winget >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 Python 3.13，且当前系统没有 winget 可用于自动安装。
    echo 请先安装 Python 3.13（勾选 Add Python to PATH），然后重新运行。
    exit /b 1
)

echo [信息] 未检测到 Python 3.13，尝试使用 winget 自动安装...
winget install --id Python.Python.3.13 -e --accept-package-agreements --accept-source-agreements --disable-interactivity
if errorlevel 1 (
    echo [错误] Python 3.13 自动安装失败。
    echo 请手动安装 Python 3.13 后重试。
    exit /b 1
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3.13 -V >nul 2>nul
    if not errorlevel 1 (
        set "HOST_PYTHON_CMD=py -3.13"
        echo [信息] Python 3.13 安装完成。
        exit /b 0
    )
)

where python >nul 2>nul
if not errorlevel 1 (
    python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 13) else 1)" >nul 2>nul
    if not errorlevel 1 (
        set "HOST_PYTHON_CMD=python"
        echo [信息] Python 3.13 安装完成。
        exit /b 0
    )
)

echo [错误] 已尝试自动安装，但仍未检测到 Python 3.13。
echo 请重启终端或注销后再试。
exit /b 1

:ensure_venv
if exist "%PYTHON_EXE%" if exist "%PYTHONW_EXE%" (
    call "%PYTHON_EXE%" -c "import sys" >nul 2>nul
    if not errorlevel 1 (
        echo [信息] 现有虚拟环境可用。
        exit /b 0
    )

    echo [信息] 检测到旧虚拟环境已失效，正在自动重建...
    rmdir /s /q "%VENV_DIR%" >nul 2>nul
)

call %HOST_PYTHON_CMD% -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo [错误] 创建虚拟环境失败。
    exit /b 1
)

if not exist "%PYTHON_EXE%" (
    echo [错误] 虚拟环境创建后未找到 python.exe。
    exit /b 1
)

if not exist "%PYTHONW_EXE%" (
    echo [错误] 虚拟环境创建后未找到 pythonw.exe。
    exit /b 1
)

call "%PYTHON_EXE%" -c "import sys" >nul 2>nul
if errorlevel 1 (
    echo [错误] 新建虚拟环境不可用。
    exit /b 1
)

echo [信息] 虚拟环境已准备完成。
exit /b 0
