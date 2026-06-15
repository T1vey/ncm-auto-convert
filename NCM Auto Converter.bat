@echo off
cd /d "%~dp0"

:: 清理残留锁文件（如果进程已死）
del /q "%LOCALAPPDATA%\NCM-AutoConvert\.lock" 2>nul

:: 启动（无窗口）
start "" pythonw.exe tray_app.py
