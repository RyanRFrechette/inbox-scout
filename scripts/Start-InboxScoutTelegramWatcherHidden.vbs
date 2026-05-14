Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\Users\ryanr\inbox-scout"
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File " & Chr(34) & "C:\Users\ryanr\inbox-scout\scripts\Start-InboxScoutTelegramWatcher.ps1" & Chr(34)
shell.Run cmd, 0, False
