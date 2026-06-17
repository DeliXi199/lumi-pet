@echo off
cd /d "%~dp0"
if not exist .venv (
  echo Please run install-deps.bat first.
  exit /b 1
)
.venv\Scripts\pyinstaller.exe --noconfirm --windowed --name DesktopPet --add-data "README.md;." pet_app.py
