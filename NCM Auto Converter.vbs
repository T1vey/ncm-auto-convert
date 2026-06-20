' NCM Auto Converter 启动器
' 固定优先使用已验证可用的 Python，避免 Explorer 双击时 PATH 不同导致静默失败

Dim fso, shell, scriptDir, pythonExe, hermesPython, logPath, logFile, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
hermesPython = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\hermes\hermes-agent\venv\Scripts\python.exe"
logPath = scriptDir & "\launcher.log"

If fso.FileExists(hermesPython) Then
    pythonExe = hermesPython
ElseIf fso.FileExists(scriptDir & "\venv\Scripts\python.exe") Then
    pythonExe = scriptDir & "\venv\Scripts\python.exe"
ElseIf fso.FileExists(scriptDir & "\.venv\Scripts\python.exe") Then
    pythonExe = scriptDir & "\.venv\Scripts\python.exe"
Else
    pythonExe = "python.exe"
End If

Set logFile = fso.OpenTextFile(logPath, 8, True)
logFile.WriteLine "==== " & Now & " ===="
logFile.WriteLine "cwd=" & scriptDir
logFile.WriteLine "python=" & pythonExe
logFile.Close

shell.CurrentDirectory = scriptDir
cmd = Chr(34) & pythonExe & Chr(34) & " " & Chr(34) & scriptDir & "\tray_app.py" & Chr(34)
shell.Run cmd, 1, False
