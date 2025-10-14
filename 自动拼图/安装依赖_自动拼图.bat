@echo off
rem 強制使用 UTF-8 代碼頁，避免中文亂碼；若失敗則回退當前系統代碼頁
chcp 65001 >nul 2>nul
set "PYTHONUTF8=1"
setlocal EnableExtensions EnableDelayedExpansion
title 自动拼图 依赖安装器 (numpy + opencv-contrib-python + PySide6)

rem =============================
rem 配置
rem =============================
set "PACKAGES=numpy>=1.24.0 opencv-contrib-python>=4.8.0 PySide6>=6.5.0"
set "MIRROR_URL=https://pypi.tuna.tsinghua.edu.cn/simple"
rem 顯示用轉義（避免 > 觸發重定向）
set "PACKAGES_ECHO=%PACKAGES:>=^>%"

echo.
echo ================================================
echo   自 动 拼 图 - 依 赖 安 装 器
echo   将安装/升级以下 Python 包：
echo     %PACKAGES_ECHO%
echo   安装过程将显示下載進度條（pip 進度）
echo ================================================
echo.

rem 检测 Python
set "PYEXE="
where py >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE (
    where python >nul 2>nul && set "PYEXE=python"
)
if not defined PYEXE (
    echo [錯誤] 未检测到 Python。請先安裝 Python 3.8+：
    echo        https://www.python.org/downloads/
    echo.
    echo 按任意鍵打開下載頁面並退出...
    pause >nul
    start https://www.python.org/downloads/
    exit /b 1
)

rem 检测/安装 pip
%PYEXE% -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [提示] 未檢測到 pip，嘗試使用 ensurepip 安裝...
    %PYEXE% -m ensurepip --upgrade
)

rem 再次确认 pip 可用
%PYEXE% -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [錯誤] pip 不可用。請檢查 Python 安裝後重試。
    pause
    exit /b 1
)

echo.
echo [1/3] 升級 pip / setuptools / wheel ...
%PYEXE% -m pip install -U pip setuptools wheel --progress-bar pretty
if errorlevel 1 (
    echo [警告] 升級 pip 失敗，將繼續嘗試安裝依賴。
)

echo.
echo [2/3] 安裝依賴（官方源）...
call :install_try ""
if errorlevel 1 (
    echo.
    echo [提示] 從官方源安裝失敗。是否嘗試使用清華鏡像加速？(Y/N)
    set /p "USE_MIRROR=>> "
    if /I "!USE_MIRROR!"=="Y" (
        echo.
        echo [2/3] 使用鏡像 %MIRROR_URL% 重新安裝...
        call :install_try "-i %MIRROR_URL%"
        if errorlevel 1 (
            echo [錯誤] 依賴安裝仍然失敗，請稍後重試或檢查網絡/代理。
            goto :end_fail
        ) else (
            goto :verify
        )
    ) else (
        echo 已取消鏡像重試。
        goto :end_fail
    )
)

:verify
echo.
echo [3/3] 驗證安裝...
%PYEXE% -c "import cv2, numpy, PySide6; import sys; print('OK'); print('numpy=', numpy.__version__); print('opencv=', cv2.__version__); print('PySide6=', getattr(PySide6, '__version__', 'unknown'))" || (
    echo [錯誤] 依賴導入測試失敗，請回顧上方輸出訊息。
    goto :end_fail
)

echo.
echo ================================================
echo   ✅ 依賴已安裝完成，可直接運行：
echo      auto stitch copy.pyw 或 auto stitch.pyw
echo   若從資源管理器打開失敗，可在此目錄終端執行：
echo      %PYEXE% "auto stitch copy.pyw"
echo ================================================
echo.
pause
exit /b 0

rem ----------------------------------------------
rem 子程序：嘗試安裝（先不加 --user，失敗再加 --user）
rem 參數1：附加 pip 參數（如 -i 鏡像）
rem ----------------------------------------------
:install_try
setlocal
set "EXTRA=%~1"
echo  - 嘗試：pip install -U %PACKAGES% %EXTRA%
%PYEXE% -m pip install -U %PACKAGES% --progress-bar pretty %EXTRA%
if errorlevel 1 (
    echo  - 第一次安裝失敗，嘗試加入 --user ...
    %PYEXE% -m pip install --user -U %PACKAGES% --progress-bar pretty %EXTRA%
    if errorlevel 1 (
        endlocal & exit /b 1
    ) else (
        endlocal & exit /b 0
    )
)
endlocal & exit /b 0

:end_fail
echo.
echo ================================================
echo   ❌ 安裝未成功
echo   建議：
echo   1) 檢查網絡連接或更換鏡像後重試
echo   2) 手動執行以下命令觀察報錯：
echo      %PYEXE% -m pip install -U %PACKAGES_ECHO%
echo   3) 若權限報錯，可嘗試加上 --user 參數
echo ================================================
echo.
pause
exit /b 1
