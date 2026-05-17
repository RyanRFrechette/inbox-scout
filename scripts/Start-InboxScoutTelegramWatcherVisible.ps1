$project = "$HOME\inbox-scout"
Set-Location $project

$env:PYTHONPATH = "$project\src"

# --- Startup validation: ensure .env has required Telegram config ---
$envFile = Join-Path $project ".env"
if (-not (Test-Path $envFile)) { New-Item -ItemType File -Path $envFile -Force | Out-Null }

$envText = Get-Content $envFile -Raw -ErrorAction SilentlyContinue
if ($envText -notmatch 'TELEGRAM_BOT_TOKEN\s*=\s*\S') {
    Write-Host "TELEGRAM_BOT_TOKEN is not set in .env."
    $tok = Read-Host "Enter TELEGRAM_BOT_TOKEN (will be saved to .env)"
    if ($tok) {
        Add-Content -Path $envFile -Value "TELEGRAM_BOT_TOKEN=$tok"
        Write-Host "TELEGRAM_BOT_TOKEN saved to .env."
    } else {
        Write-Host "Warning: no token entered — watcher will fail to start."
    }
}

$envText = Get-Content $envFile -Raw -ErrorAction SilentlyContinue
if ($envText -notmatch 'TELEGRAM_CHAT_ID\s*=\s*\S') {
    Write-Host "TELEGRAM_CHAT_ID is not set in .env."
    $cid = Read-Host "Enter TELEGRAM_CHAT_ID"
    if ($cid) {
        Add-Content -Path $envFile -Value "TELEGRAM_CHAT_ID=$cid"
        Write-Host "TELEGRAM_CHAT_ID saved to .env."
    } else {
        Write-Host "Warning: no chat ID entered — watcher will fail to start."
    }
}

# --- Stop old Python telegram_watch processes only (never kills shells) ---
Write-Host "Stopping any duplicate/stale telegram_watch Python processes..."
$currentPid = $PID
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match "telegram_watch" -and $_.ExecutablePath -match "python" } |
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
