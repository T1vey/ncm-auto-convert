Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\32318\Desktop\ncm-auto-convert"
WshShell.Run "C:\Users\32318\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe tray_app.py", 0, False
