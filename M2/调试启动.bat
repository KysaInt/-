@echo off
setlocal EnableExtensions
chcp 65001 >nul
title 音频可视化工具 OpenGL 版 调试启动 (Python 3.13)

set "SCRIPT_DIR=%~dp0"
set "TARGET=%SCRIPT_DIR%0.pyw"
set "PYTHON_EXE=%SCRIPT_DIR%venv313\Scripts\python.exe"

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

echo [调试] 使用控制台模式启动 0.pyw
echo [调试] 如果 pyw 直接双击没有反应，可优先用这个脚本查看报错。
echo.
call "%PYTHON_EXE%" "%TARGET%"
echo.
echo [调试] 程序已退出，退出码: %errorlevel%
pause