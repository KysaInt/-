@echo off
setlocal enabledelayedexpansion

:: 获取用户自定义的命名前缀
set /p prefix=请输入文件名前缀：

:: 获取起始编号，如果为空则默认为 0
set /p startNum=请输入起始序号（默认 0）：
if "%startNum%"=="" set startNum=0

:: 设置初始计数器
set /a count=%startNum%

:: 获取当前脚本文件名
set scriptName=%~nx0

:: 遍历当前目录下的所有文件
for %%f in (*.*) do (
    if /I not "%%~nxf"=="%scriptName%" (
        set "ext=%%~xf"
        set "newName=%prefix%!count!%%~xf"
        echo 正在重命名：%%~nxf → !newName!
        ren "%%~nxf" "!newName!"
        set /a count+=1
    )
)

echo.
echo 所有文件已重命名完成！
pause