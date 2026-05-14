$ErrorActionPreference = "Continue"

$project = "$HOME\inbox-scout"
$python = "$project\.venv\Scripts\python.exe"
$logDir = "$project\data\logs"
$logPath = "$logDir\telegram_watcher_launcher.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-LauncherLog {
    param([string]$Message)
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logPath -Value "[$stamp] $Message"
}

Write-LauncherLog "Launcher starting. PID=$PID"

if (!(Test-Path $project)) {
    Write-LauncherLog "STOP: Project folder missing: $project"
    exit 1
}

if (!(Test-Path $python)) {
    Write-LauncherLog "STOP: venv Python missing. Refusing global Python fallback."
    exit 1
}

Set-Location $project
$env:PYTHONPATH = "$project\src"

$currentPid = $PID

Write-LauncherLog "Cleaning duplicate watcher processes."

Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -match "inbox_scout.telegram_watch" -or
        $_.CommandLine -match "Start-InboxScoutTelegramWatcher"
    } |
    ForEach-Object {
        $processIdToStop = $_.ProcessId
        $cmd = "$($_.CommandLine)"

        if ($processIdToStop -eq $currentPid) {
            Write-LauncherLog "Skipping current launcher PID ${processIdToStop}."
        } else {
            Write-LauncherLog "Stopping duplicate/stale process PID ${processIdToStop}: $cmd"
            Stop-Process -Id $processIdToStop -Force -ErrorAction SilentlyContinue
        }
    }

Start-Sleep -Seconds 2

Write-LauncherLog "Starting venv watcher only: $python"
Write-LauncherLog "PYTHONPATH=$env:PYTHONPATH"

& $python -m inbox_scout.telegram_watch

Write-LauncherLog "Watcher process exited."
