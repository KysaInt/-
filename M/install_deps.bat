@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

title Audio Visualizer - Install Dependencies

set "SCRIPT_DIR=%~dp0"
set "REQ_FILE=%SCRIPT_DIR%requirements_audio_viz.txt"
set "PY_CMD="

echo ==============================================
echo [1/5] 检查 Python...
echo ==============================================

where py >nul 2>nul
if not errorlevel 1 (
    py -3.11 -V >nul 2>nul
    if not errorlevel 1 (
        set "PY_CMD=py -3.11"
        goto :python_ready
    )
    py -3 -V >nul 2>nul
    if not errorlevel 1 (
        set "PY_CMD=py -3"
        goto :python_ready
    )
)

where python >nul 2>nul
if not errorlevel 1 (
    python -V >nul 2>nul
    if not errorlevel 1 (
        set "PY_CMD=python"
        goto :python_ready
    )
)

echo 未检测到可用 Python，尝试使用 winget 安装 Python 3.11...
where winget >nul 2>nul
if errorlevel 1 (
    echo [错误] 当前系统没有 winget，无法自动安装 Python。
    echo 请先手动安装 Python 3.11+，再重新运行本脚本。
    echo 下载地址: https://www.python.org/downloads/windows/
    pause
    exit /b 1
)

winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo [错误] winget 安装 Python 失败，请手动安装后重试。
    pause
    exit /b 1
)

echo Python 安装完成，重新探测...
where py >nul 2>nul
if not errorlevel 1 (
    py -3.11 -V >nul 2>nul
    if not errorlevel 1 (
        set "PY_CMD=py -3.11"
        goto :python_ready
    )
    py -3 -V >nul 2>nul
    if not errorlevel 1 (
        set "PY_CMD=py -3"
        goto :python_ready
    )
)

where python >nul 2>nul
if not errorlevel 1 (
    python -V >nul 2>nul
    if not errorlevel 1 (
        set "PY_CMD=python"
        goto :python_ready
    )
)

echo [错误] Python 安装后仍不可用。请重启终端或注销后重试。
pause
exit /b 1

:python_ready
echo 检测到 Python 命令: %PY_CMD%

if not exist "%REQ_FILE%" (
    echo [错误] 未找到依赖文件: %REQ_FILE%
    pause
    exit /b 1
)

echo.
echo ==============================================
echo [2/5] 升级 pip/setuptools/wheel...
echo ==============================================
call %PY_CMD% -m ensurepip --upgrade
call %PY_CMD% -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo [错误] pip 基础工具升级失败。
    pause
    exit /b 1
)

echo.
echo ==============================================
echo [3/5] 安装项目依赖...
echo ==============================================
call %PY_CMD% -m pip install -r "%REQ_FILE%"
if errorlevel 1 (
    echo [错误] 依赖安装失败。
    echo 你可以稍后手动执行：
    echo   %PY_CMD% -m pip install -r "%REQ_FILE%"
    pause
    exit /b 1
)

echo.
echo ==============================================
echo [4/5] 验证关键依赖导入...
echo ==============================================
call %PY_CMD% -c "import PySide6, numpy, scipy, pygame; import pyaudiowpatch; print('依赖导入检查通过')"
if errorlevel 1 (
    echo [错误] 依赖导入检查失败，请查看上方报错。
    pause
    exit /b 1
)

echo.
echo ==============================================
echo [5/5] 完成
echo ==============================================
echo 环境准备完成，可运行 0.pyw。
pause
exit /b 0
