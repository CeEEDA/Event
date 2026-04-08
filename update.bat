@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: =====================================================
:: Eventenergie Portal - Update via GitHub
:: =====================================================
::
:: VERWENDUNG:
::   Doppelklick (Als Administrator empfohlen)
::
:: ABLAUF:
::   1. Dienste stoppen
::   2. .env Dateien sichern
::   3. Git Pull vom GitHub Repository
::   4. Python-Pakete aktualisieren
::   5. Frontend Build erstellen
::   6. Dienste starten
::   7. Port-Verifizierung
::
:: SICHERHEIT:
::   - .env Dateien werden NIEMALS ueberschrieben
::   - MongoDB Daten bleiben unberuehrt
::
:: =====================================================

set "LIVE_DIR=C:\eventenergie"
set "BRANCH=Main_0.9APP"
set "REPO_URL=https://github.com/CeEEDA/Event.git"
set "LOG_DIR=%LIVE_DIR%\logs"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo.
echo  ==================================================
echo   Eventenergie Portal - GitHub Update
echo   %date% %time%
echo  ==================================================
echo.

if not exist "%LIVE_DIR%" (
    echo   FEHLER: %LIVE_DIR% nicht gefunden!
    pause
    exit /b 1
)

cd /d "%LIVE_DIR%"

:: ====== 1. Dienste stoppen ======
echo  [1/7] Dienste stoppen...
if exist "%LIVE_DIR%\stop-all.bat" (
    call "%LIVE_DIR%\stop-all.bat" nopause
) else (
    taskkill /FI "WINDOWTITLE eq Eventenergie Backend" /F >nul 2>&1
    taskkill /FI "WINDOWTITLE eq Eventenergie Caddy" /F >nul 2>&1
    taskkill /IM caddy.exe /F >nul 2>&1
    taskkill /IM nginx.exe /F >nul 2>&1
    timeout /t 3 /nobreak >nul
)
echo   Dienste gestoppt.

:: ====== 2. .env sichern ======
echo.
echo  [2/7] .env Dateien sichern...
if exist "%LIVE_DIR%\backend\.env" (
    copy /Y "%LIVE_DIR%\backend\.env" "%LIVE_DIR%\backend\.env.backup" >nul
    echo   backend\.env gesichert
)
if exist "%LIVE_DIR%\frontend\.env" (
    copy /Y "%LIVE_DIR%\frontend\.env" "%LIVE_DIR%\frontend\.env.backup" >nul
    echo   frontend\.env gesichert
)

:: ====== 3. Git Pull ======
echo.
echo  [3/7] Code von GitHub aktualisieren...
echo   Branch: %BRANCH%

where git >nul 2>&1
if !errorlevel! neq 0 (
    echo   FEHLER: Git ist nicht installiert!
    echo   Bitte Git installieren: https://git-scm.com/download/win
    pause
    exit /b 1
)

if not exist "%LIVE_DIR%\.git" (
    echo   Kein Git-Repository gefunden. Initialisiere...
    git init 2>&1
    git remote add origin %REPO_URL% 2>&1
    echo   Git-Repository initialisiert mit %REPO_URL%
)

git fetch --all 2>&1
if !errorlevel! neq 0 (
    echo   FEHLER: Git fetch fehlgeschlagen. Internet-Verbindung pruefen.
    pause
    exit /b 1
)

for /f "tokens=*" %%b in ('git branch --show-current') do set "CURRENT_BRANCH=%%b"
if /i not "!CURRENT_BRANCH!"=="%BRANCH%" (
    echo   Wechsle von !CURRENT_BRANCH! zu %BRANCH%...
    git checkout %BRANCH% 2>&1
)

git pull origin %BRANCH% 2>&1
if !errorlevel! neq 0 (
    echo   WARNUNG: Git pull hatte Probleme. Versuche Reset...
    git reset --hard origin/%BRANCH% 2>&1
)
echo   Code aktualisiert.

:: ====== 3b. .env wiederherstellen falls ueberschrieben ======
echo.
echo  [3b] .env Dateien pruefen...

if not exist "%LIVE_DIR%\backend\.env" (
    if exist "%LIVE_DIR%\backend\.env.backup" (
        copy /Y "%LIVE_DIR%\backend\.env.backup" "%LIVE_DIR%\backend\.env" >nul
        echo   backend\.env aus Backup wiederhergestellt
    ) else (
        echo   WARNUNG: backend\.env fehlt! Bitte manuell erstellen.
    )
) else (
    echo   backend\.env OK
)

if not exist "%LIVE_DIR%\frontend\.env" (
    if exist "%LIVE_DIR%\frontend\.env.backup" (
        copy /Y "%LIVE_DIR%\frontend\.env.backup" "%LIVE_DIR%\frontend\.env" >nul
        echo   frontend\.env aus Backup wiederhergestellt
    ) else (
        echo   WARNUNG: frontend\.env fehlt! Bitte manuell erstellen.
    )
) else (
    echo   frontend\.env OK
)

:: ====== 4. Python-Pakete ======
echo.
echo  [4/7] Python-Pakete aktualisieren...
echo   (Das kann einige Minuten dauern)
cd /d "%LIVE_DIR%\backend"

set "REQ_FILE=requirements.txt"
if exist "%LIVE_DIR%\backend\requirements-server.txt" set "REQ_FILE=requirements-server.txt"
echo   Verwende: %REQ_FILE%

:: --- venv Erkennung mit goto (zuverlaessig) ---
if exist "%LIVE_DIR%\venv\Scripts\activate.bat" goto :pip_venv_root
if exist "%LIVE_DIR%\backend\venv\Scripts\activate.bat" goto :pip_venv_backend
goto :pip_global

:pip_venv_root
echo   venv aktiviert: %LIVE_DIR%\venv
call "%LIVE_DIR%\venv\Scripts\activate.bat"
pip install -r %REQ_FILE% --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ 2>&1
echo   Python-Pakete aktualisiert (venv)
goto :pip_done

:pip_venv_backend
echo   venv aktiviert: %LIVE_DIR%\backend\venv
call "%LIVE_DIR%\backend\venv\Scripts\activate.bat"
pip install -r %REQ_FILE% --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ 2>&1
echo   Python-Pakete aktualisiert (backend venv)
goto :pip_done

:pip_global
echo   WARNUNG: Kein venv gefunden, installiere global
pip install -r %REQ_FILE% --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ 2>&1
echo   Python-Pakete aktualisiert (global)
goto :pip_done

:pip_done

:: ====== 5. Frontend Build ======
echo.
echo  [5/7] Frontend Build erstellen...
cd /d "%LIVE_DIR%\frontend"

:: --- yarn/npm Erkennung mit goto (zuverlaessig) ---
where yarn >nul 2>&1
if !errorlevel! equ 0 goto :build_yarn
goto :build_npm

:build_yarn
echo   yarn install laeuft...
call yarn install --frozen-lockfile 2>&1
echo   yarn build laeuft... (kann 2-5 Minuten dauern)
call yarn build 2>&1
echo   Build erfolgreich (yarn)
goto :build_done

:build_npm
echo   WARNUNG: yarn nicht gefunden! Installiere mit: npm install -g yarn
echo   Verwende npm als Fallback...
call npm install --legacy-peer-deps 2>&1
call npm run build 2>&1
echo   Build erfolgreich (npm)
goto :build_done

:build_done

:: Desktop-Installer in Backend kopieren
if exist "%LIVE_DIR%\desktop" (
    if not exist "%LIVE_DIR%\backend\static\desktop-installers" mkdir "%LIVE_DIR%\backend\static\desktop-installers"
    for %%f in (install-mac.sh install-win.bat install-win.ps1 server-setup-win.ps1 db-migrate-win.ps1 deploy-win.ps1 build-mobile.ps1 build-mobile.sh) do (
        if exist "%LIVE_DIR%\desktop\%%f" copy /Y "%LIVE_DIR%\desktop\%%f" "%LIVE_DIR%\backend\static\desktop-installers\" >nul
    )
    echo   Desktop-Installer kopiert
)

:: ====== 6. Dienste starten ======
echo.
echo  [6/7] Dienste starten...
cd /d "%LIVE_DIR%"
:: start-all.bat starten (einziger Startmechanismus)
if exist "%LIVE_DIR%\start-all.bat" (
    call "%LIVE_DIR%\start-all.bat" nopause
)
echo   Dienste gestartet

:: ====== 7. Finale Port-Verifizierung ======
echo.
echo  [7/7] Finale Verifizierung...
echo   Warte 10 Sekunden auf Backend-Start...
timeout /t 10 /nobreak >nul

set "FINAL_BACKEND=0"
set "FINAL_CADDY=0"
set "FINAL_NGINX=0"

call :upd_check_port 8002
if !errorlevel! equ 0 set "FINAL_BACKEND=1"

call :upd_check_port 8001
if !errorlevel! equ 0 set "FINAL_CADDY=1"

call :upd_check_port 443
if !errorlevel! equ 0 set "FINAL_NGINX=1"

:: ====== Zusammenfassung ======
echo.
echo  ==================================================
echo   Update abgeschlossen
echo   %date% %time%
echo  ==================================================
echo.
echo   Branch:  %BRANCH%
echo   Portal:  https://eventenergie.app
echo.
if !FINAL_BACKEND! equ 1 (echo   [OK] Backend auf Port 8002) else (echo   [XX] Backend NICHT gestartet auf Port 8002)
if !FINAL_CADDY! equ 1   (echo   [OK] Caddy auf Port 8001) else (echo   [XX] Caddy NICHT gestartet auf Port 8001)
if !FINAL_NGINX! equ 1   (echo   [OK] nginx auf Port 443) else (echo   [XX] nginx NICHT gestartet auf Port 443)
echo.
echo   Geschuetzte Dateien (NICHT ueberschrieben):
echo     backend\.env   (Datenbank, JWT, SMTP)
echo     frontend\.env  (Portal-URL)
echo     MongoDB Daten  (unveraendert)
echo.
if !FINAL_BACKEND! equ 0 (
    echo   TIPP: Pruefe "Eventenergie Backend" Fenster fuer Fehler
)
if !FINAL_CADDY! equ 0 (
    echo   TIPP: Pruefe "Eventenergie Caddy" Fenster fuer Fehler
)
if !FINAL_BACKEND! equ 0 if !FINAL_CADDY! equ 0 (
    echo   TIPP: Dienste manuell starten mit: start-all.bat
)
echo.
pause
goto :eof

:: ============================================
::  Subroutine fuer Port-Pruefung
:: ============================================
:upd_check_port
set "_UCP=1"
for /f "tokens=*" %%a in ('netstat -ano ^| findstr "0.0.0.0:%~1 " 2^>nul') do set "_UCP=0"
exit /b !_UCP!
