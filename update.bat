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
::   1. Dienste stoppen (stop-all.bat nopause)
::   2. .env Dateien sichern
::   3. Git Pull vom GitHub Repository
::   4. Python-Pakete aktualisieren
::   5. Frontend Build erstellen
::   6. Dienste starten (start-all.bat nopause)
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

:: Logs-Ordner erstellen
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo.
echo  ==================================================
echo   Eventenergie Portal - GitHub Update
echo   %date% %time%
echo  ==================================================
echo.

:: Pruefen ob Live-Verzeichnis existiert
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

:: Pruefen ob .git existiert, falls nicht: initialisieren
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

:: Zum richtigen Branch wechseln falls noetig
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
cd /d "%LIVE_DIR%\backend"
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    pip install -r requirements.txt --quiet 2>nul
    echo   Python-Pakete aktualisiert (venv)
) else (
    pip install -r requirements.txt --quiet 2>nul
    echo   Python-Pakete aktualisiert
)

:: ====== 5. Frontend Build ======
echo.
echo  [5/7] Frontend Build erstellen...
cd /d "%LIVE_DIR%\frontend"
call npm install --legacy-peer-deps 2>nul
echo   Node-Pakete installiert
call npm run build
if !errorlevel! equ 0 (
    echo   Build erfolgreich
) else (
    echo   FEHLER: Build fehlgeschlagen
    echo   Bitte manuell pruefen: cd %LIVE_DIR%\frontend ^&^& npm run build
)

:: ====== 6. Dienste starten ======
echo.
echo  [6/7] Dienste starten...
cd /d "%LIVE_DIR%"
if exist "%LIVE_DIR%\start-all.bat" (
    call "%LIVE_DIR%\start-all.bat" nopause
) else (
    echo   FEHLER: start-all.bat nicht gefunden!
    pause
    exit /b 1
)

:: ====== 7. Finale Port-Verifizierung ======
echo.
echo  [7/7] Finale Verifizierung...
echo   Warte 5 Sekunden...
timeout /t 5 /nobreak >nul

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
::  Sucht nach 0.0.0.0:PORT (locale-unabhaengig)
::  Deutsch: "ABHOEREN" statt "LISTENING"
:: ============================================
:upd_check_port
set "_UCP=1"
for /f "tokens=*" %%a in ('netstat -ano ^| findstr "0.0.0.0:%~1 " 2^>nul') do set "_UCP=0"
exit /b !_UCP!
