@echo off
chcp 65001 >nul
echo ============================================
echo   NCM Auto Converter - 开机自启安装
echo ============================================
echo.

set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SCRIPT_DIR=%~dp0"

echo Set WshShell = CreateObject("WScript.Shell") > "%STARTUP_DIR%\ncm_watcher.vbs"
echo WshShell.CurrentDirectory = "%SCRIPT_DIR%" >> "%STARTUP_DIR%\ncm_watcher.vbs"
echo WshShell.Run "pythonw ncm_auto_convert.py", 0, False >> "%STARTUP_DIR%\ncm_watcher.vbs"

echo [OK] 已创建开机启动项
echo   位置: %STARTUP_DIR%\ncm_watcher.vbs
echo.
echo 重启后将自动在后台运行，无窗口弹出。
echo 卸载请运行 uninstall_startup.bat
echo.
pause
