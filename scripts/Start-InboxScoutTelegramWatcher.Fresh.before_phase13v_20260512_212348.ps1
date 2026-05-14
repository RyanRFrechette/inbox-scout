cd "C:\Users\ryanr\inbox-scout"
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m inbox_scout.telegram_watch
