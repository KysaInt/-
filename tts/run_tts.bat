@echo off
REM TTS 程序启动脚本
REM 用于快速启动 TTS 主程序并检查图标显示

chcp 65001 > nul
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo ╔══════════════════════════════════════════╗
echo ║  TTS 工具集 - 启动程序 (已修复图标显示)  ║
echo ╚══════════════════════════════════════════╝
echo.

REM 检查 Python 环境
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未找到 Python 环境
    pause
    exit /b 1
)

REM 检查图标文件
if exist "icon.ico" (
    echo ✅ 已找到 icon.ico
) else (
    echo ⚠️  未找到 icon.ico，尝试生成...
    python generate_icon.py
    if errorlevel 1 (
        echo ⚠️  图标生成失败，继续运行...
    )
)

echo.
echo 📋 启动检查项:
echo   ✅ 检查窗口标题栏左上角的图标
echo   ✅ 检查 Windows 任务栏中的图标
echo   ✅ 按 Alt+Tab 查看窗口切换器中的图标
echo   ✅ 关闭程序后重启检查图标是否更新
echo.

echo 🚀 启动 TTS 程序...
echo.

python AYE_TTS_Main.pyw

pause
