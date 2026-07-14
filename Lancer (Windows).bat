@echo off
rem Double-cliquez pour lancer l'application (Windows).
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 foyer_app.py
) else (
  python foyer_app.py
)
if errorlevel 1 pause
