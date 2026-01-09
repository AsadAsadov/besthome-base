@echo off
cd /d "D:\Proyekt\31.10.2025 18.10"

python estatebase_sync.py --days -1
python auto_zip.py
python upload_dropbox.py
python notify_bot.py