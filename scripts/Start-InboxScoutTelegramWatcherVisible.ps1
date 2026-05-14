$project = "$HOME\inbox-scout"
Set-Location $project

$env:PYTHONPATH = "$project\src"

Write-Host "Stopping any duplicate/stale telegram_watch processes..."
$currentPid = $PID
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match "telegram_watch" } |
    ForEach-Object {
        if ($_.ProcessId -ne $currentPid) {
            Write-Host "  Stopping PID $($_.ProcessId): $($_.ExecutablePath)"
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
Start-Sleep -Seconds 1

Write-Host "Project: $project"
Write-Host "PYTHONPATH: $env:PYTHONPATH"
Write-Host "Python:"
& "$project\.venv\Scripts\python.exe" -c "import sys; print(sys.executable); import inbox_scout; print('inbox_scout import OK')"

Write-Host "`nStarting Atlas visible watcher..."
& "$project\.venv\Scripts\python.exe" -m inbox_scout.telegram_watch
