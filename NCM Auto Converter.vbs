Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\32318\Desktop\ncm-auto-convert"
WshShell.Run "python tray_app.py", 0, False
