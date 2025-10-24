@echo off
REM -*- coding: utf-8 -*-
REM GitHub TTS目录下载器（批处理版）
REM 运行此程序会自动下载 https://github.com/KysaInt/-/tree/main/tts

setlocal enabledelayedexpansion

cls
echo ============================================================
echo GitHub TTS目录下载器
echo ============================================================
echo.

REM 检查Git是否安装
git --version >nul 2>&1
if errorlevel 1 (
    echo ✗ 错误: 未检测到Git
    echo.
    echo 请先安装Git:
    echo   https://git-scm.com/download/win
    echo   或使用包管理器: choco install git
    pause
    exit /b 1
)

echo ✓ Git已安装
echo.

REM 设置变量
set REPO_URL=https://github.com/KysaInt/-
set BRANCH=main
set TARGET_FOLDER=tts
set SCRIPT_DIR=%~dp0
set OUTPUT_DIR=%SCRIPT_DIR:~0,-1%
for %%A in ("%OUTPUT_DIR%") do set OUTPUT_DIR=%%~dpA

echo 配置信息:
echo   仓库地址: %REPO_URL%
echo   分支: %BRANCH%
echo   目录: %TARGET_FOLDER%
echo   输出目录: %OUTPUT_DIR%
echo.

REM 创建临时目录
set TEMP_DIR=%OUTPUT_DIR%.git_temp
if exist "%TEMP_DIR%" (
    rmdir /s /q "%TEMP_DIR%"
)
mkdir "%TEMP_DIR%"

echo 开始下载...
echo.

REM 初始化Git仓库
cd /d "%TEMP_DIR%"
git init
git remote add origin %REPO_URL%
git config core.sparseCheckout true

REM 配置稀疏检出
if not exist ".git\info" mkdir ".git\info"
(echo %TARGET_FOLDER%/) > .git\info\sparse-checkout

REM 拉取分支
echo 拉取 %BRANCH% 分支（仅包含 %TARGET_FOLDER% 目录）...
git pull origin %BRANCH%

if errorlevel 1 (
    echo.
    echo ✗ 下载失败
    echo.
    cd /d "%OUTPUT_DIR%"
    rmdir /s /q "%TEMP_DIR%"
    pause
    exit /b 1
)

REM 移动目录
cd /d "%OUTPUT_DIR%"
if exist "%OUTPUT_DIR%%TARGET_FOLDER%" (
    echo 目标目录 %TARGET_FOLDER% 已存在，删除旧目录...
    rmdir /s /q "%OUTPUT_DIR%%TARGET_FOLDER%"
)

move "%TEMP_DIR%%TARGET_FOLDER%" "%OUTPUT_DIR%%TARGET_FOLDER%"

REM 清理临时目录
rmdir /s /q "%TEMP_DIR%"

echo.
echo ============================================================
echo ✓ 下载完成！
echo ============================================================
echo.
echo 下载的目录位置: %OUTPUT_DIR%%TARGET_FOLDER%
echo.
pause
