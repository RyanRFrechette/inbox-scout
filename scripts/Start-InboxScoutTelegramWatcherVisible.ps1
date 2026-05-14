$project = "$HOME\inbox-scout"
Set-Location $project

$env:PYTHONPATH = "$project\src"

Write-Host "Project: $project"
Write-Host "PYTHONPATH: $env:PYTHONPATH"
Write-Host "Python:"
& "$project\.venv\Scripts\python.exe" -c "import sys; print(sys.executable); import inbox_scout; print('inbox_scout import OK')"

Write-Host "`nStarting Atlas visible watcher..."
& "$project\.venv\Scripts\python.exe" -m inbox_scout.telegram_watch
