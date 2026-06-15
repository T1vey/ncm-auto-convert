@echo off
chcp 65001 >nul
echo ============================================
echo   NCM Auto Converter - 取消开机自启
echo ============================================
echo.

set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

if exist "%STARTUP_DIR%\ncm_watcher.vbs" (
    del "%STARTUP_DIR%\ncm_watcher.vbs"
    echo [OK] 已删除开机启动项
) else (
    echo [!] 启动项不存在，无需卸载
)

:: 尝试结束正在运行的守护进程
taskkill /IM pythonw.exe /F >nul 2>&1
if %errorlevel%==0 (
    echo [OK] 已终止后台守护进程
) else (
    echo [!] 没有发现运行中的守护进程
)

echo.
pause
