Set shell = CreateObject("WScript.Shell")
shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""C:\Users\ryanr\inbox-scout\scripts\Start-InboxScoutTelegramWatcher.ps1""", 0, False
