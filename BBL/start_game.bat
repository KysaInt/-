@echo off
setlocal
set PORT=8000
set HOST=127.0.0.1
set SCRIPT=%~dp0serve.pyw

REM Try Python launcher first
where py >nul 2>&1 && (
  py "%SCRIPT%" --host %HOST% --port %PORT% --open
  goto :eof
)

REM Fallback to python
where python >nul 2>&1 && (
  python "%SCRIPT%" --host %HOST% --port %PORT% --open
  goto :eof
)

echo 未找到 Python。请安装 Python 3 并将其加入 PATH。
pause
