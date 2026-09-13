' 小鲸鱼桌宠 —— 静默启动器（双击即可，不弹控制台窗口）
'
' 用 Hermes 自带 venv 的 pythonw.exe（有 Pillow / PyYAML）；找不到就退回 PATH 上的 pythonw。
' 窗口模式 0 = 隐藏，False = 不等它退出（启动完这个脚本就结束）。
Option Explicit

Dim fso, shell, here, py, script
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

here = fso.GetParentFolderName(WScript.ScriptFullName)
script = here & "\whale-pet.pyw"

py = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\hermes\hermes-agent\venv\Scripts\pythonw.exe"
If Not fso.FileExists(py) Then py = "pythonw.exe"

shell.CurrentDirectory = here
shell.Run """" & py & """ """ & script & """", 0, False
