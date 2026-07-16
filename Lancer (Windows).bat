@echo off
setlocal enabledelayedexpansion
rem Lanceur Windows : trouve Python (chemins connus, pas seulement le PATH),
rem l'installe automatiquement s'il est absent, puis demarre l'application.
cd /d "%~dp0"

set "PYVER=3.12.7"
set "PY="

rem 1) lanceur "py"
where py >nul 2>nul && ( for /f "delims=" %%i in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i" )
rem 2) "python" du PATH
if not defined PY ( where python >nul 2>nul && ( for /f "delims=" %%i in ('python -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i" ) )
rem 3) emplacements d'installation par defaut
if not defined PY if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PY if exist "%ProgramFiles%\Python312\python.exe" set "PY=%ProgramFiles%\Python312\python.exe"

if not defined PY (
  echo.
  echo Python est necessaire mais n'est pas installe.
  echo Telechargement et installation automatique ^(cela peut prendre 1 a 2 minutes^)...
  echo.
  set "EXE=%TEMP%\python-foyer-%PYVER%.exe"
  powershell -NoProfile -Command "try{[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-amd64.exe' -OutFile '%EXE%'}catch{exit 1}"
  if errorlevel 1 ( echo Echec du telechargement. Installez Python manuellement depuis python.org ^(voir le guide^). & pause & exit /b 1 )
  "%EXE%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1
  if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
  if not defined PY ( where py >nul 2>nul && ( for /f "delims=" %%i in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i" ) )
)

if not defined PY ( echo Python introuvable apres installation. Redemarrez le PC puis relancez. & pause & exit /b 1 )

"%PY%" -c "import certifi" 2>nul || "%PY%" -m pip install --quiet certifi >nul 2>nul
echo Demarrage de l'application...
"%PY%" foyer_app.py
if errorlevel 1 pause
endlocal
