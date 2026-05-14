$project = "$HOME\inbox-scout"
Set-Location $project
$env:PYTHONPATH = "$project\src"

$python = "$project\.venv\Scripts\python.exe"
if (!(Test-Path $python)) {
    $python = "python"
}

& $python -m inbox_scout.telegram_watch
