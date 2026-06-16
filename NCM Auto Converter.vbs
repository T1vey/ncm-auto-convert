' NCM Auto Converter 启动器
' 自动检测当前目录下的 Python 环境并启动 tray_app.py

Dim fso, shell, scriptDir, pythonExe
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' 优先查找 venv 中的 python
pythonExe = ""
If fso.FileExists(scriptDir & "\venv\Scripts\python.exe") Then
    pythonExe = scriptDir & "\venv\Scripts\python.exe"
ElseIf fso.FileExists(scriptDir & "\.venv\Scripts\python.exe") Then
    pythonExe = scriptDir & "\.venv\Scripts\python.exe"
Else
    ' 使用系统 PATH 中的 python
    pythonExe = "python.exe"
End If

shell.CurrentDirectory = scriptDir
shell.Run """" & pythonExe & """ tray_app.py", 0, False
