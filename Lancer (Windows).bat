@echo off
setlocal
cd /d "%~dp0"
title Adhesions - Foyer Rural de Mondonville

echo Recherche de Python...
set "PY="

rem 1) lanceur "py" (installations python.org)
py -3 -c "import sys" 1>nul 2>nul
if not errorlevel 1 set "PY=py -3"

rem 2) commande "python"
if not defined PY (
  python -c "import sys" 1>nul 2>nul
  if not errorlevel 1 set "PY=python"
)

rem 3) emplacements d'installation courants
if not defined PY if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set "PY=%LocalAppData%\Programs\Python\Python313\python.exe"
if not defined PY if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PY if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PY=%LocalAppData%\Programs\Python\Python311\python.exe"

if not defined PY goto INSTALL
goto RUN

:INSTALL
echo.
echo ============================================================
echo   INSTALLATION DE PYTHON EN COURS - MERCI DE PATIENTER
echo   Ne fermez pas cette fenetre (1 a 2 minutes).
echo ============================================================
echo.
set "EXE=%TEMP%\python-foyer.exe"
echo Telechargement...
powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe' -OutFile '%EXE%'"
if not exist "%EXE%" goto DLFAIL
echo Installation...
"%EXE%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1
echo Installation terminee.
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PY set "PY=py -3"
goto RUN

:DLFAIL
echo.
echo Echec du telechargement de Python.
echo Installez Python manuellement depuis https://www.python.org/downloads/
echo (cochez "Add Python to PATH"), puis relancez ce fichier.
echo.
pause
exit /b 1

:RUN
echo Python detecte : %PY%
echo Demarrage de l'application... Laissez CETTE fenetre ouverte pendant l'utilisation.
echo (Une page va s'ouvrir dans votre navigateur.)
echo.
if "%PY%"=="py -3" (
  py -3 "%~dp0foyer_app.py"
) else if "%PY%"=="python" (
  python "%~dp0foyer_app.py"
) else (
  "%PY%" "%~dp0foyer_app.py"
)
echo.
echo L'application est fermee. Vous pouvez fermer cette fenetre.
pause
endlocal
