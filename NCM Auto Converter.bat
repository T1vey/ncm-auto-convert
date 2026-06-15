@echo off
cd /d "%~dp0"
:: 用 python.exe + 最小化窗口（避免 pythonw.exe 的 DLL 错误）
start /min "NCM Auto Converter" python tray_app.py
