@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"
set "INSTALLER=%SCRIPT_DIR%install_deps.bat"
set "TARGET=%SCRIPT_DIR%0.pyw"

if not exist "%INSTALLER%" (
    echo [错误] 找不到安装脚本: %INSTALLER%
    pause
    exit /b 1
)

if not exist "%TARGET%" (
    echo [错误] 找不到主程序: %TARGET%
    pause
    exit /b 1
)

call "%INSTALLER%"
if errorlevel 1 (
    echo 安装步骤失败，已停止启动。
    exit /b 1
)

where py >nul 2>nul
if not errorlevel 1 (
    start "" py -3.11w "%TARGET%"
    if not errorlevel 1 exit /b 0
    start "" py -3w "%TARGET%"
    if not errorlevel 1 exit /b 0
)

where pythonw >nul 2>nul
if not errorlevel 1 (
    start "" pythonw "%TARGET%"
    exit /b 0
)

echo [错误] 找不到可用的 pythonw/pyw 启动命令。
echo 你可以手动运行: python "%TARGET%"
pause
exit /b 1
