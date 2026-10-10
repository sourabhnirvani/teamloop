' Start TeamLoop without Electron: runs the server hidden, then opens the app in your browser.
Set sh = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(WScript.ScriptFullName)
py = root & "\.venv\Scripts\pythonw.exe"
If Not fs.FileExists(py) Then py = "pythonw"
sh.CurrentDirectory = root
sh.Run """" & py & """ -m teamloop", 0, False
WScript.Sleep 4000
sh.Run "http://127.0.0.1:8790"
