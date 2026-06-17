@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe pet_app.py
) else (
  python pet_app.py
)
