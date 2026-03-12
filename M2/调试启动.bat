@echo off
setlocal EnableExtensions
chcp 65001 >nul
title 音频可视化工具 OpenGL 版 调试启动 (Python 3.13)

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%venv313"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "REQ_FILE=%SCRIPT_DIR%requirements_audio_viz.txt"
set "TARGET=%SCRIPT_DIR%0.pyw"

cd /d "%SCRIPT_DIR%"

if not exist "%PYTHON_EXE%" (
    echo [错误] 尚未检测到虚拟环境。
    echo 请先运行一次 启动.bat 完成环境安装。
    pause
    exit /b 1
)

if not exist "%TARGET%" (
    echo [错误] 找不到主程序: %TARGET%
    pause
    exit /b 1
)

echo [调试] 使用控制台模式启动 0.pyw
echo [调试] 如果 pyw 直接双击没有反应，可优先用这个脚本查看报错。
echo.
call "%PYTHON_EXE%" "%TARGET%"
echo.
echo [调试] 程序已退出，退出码: %errorlevel%
pause