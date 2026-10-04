' Trackeep Lit 启动器：双击即开，不弹黑色命令行窗口
Dim fso, sh, root
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
root = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = root
sh.Run """" & root & "\venv\Scripts\pythonw.exe"" """ & root & "\gui.py""", 0, False
