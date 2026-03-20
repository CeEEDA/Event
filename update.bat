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
::   1. Dienste stoppen (stop-all.bat)
::   2. .env Dateien sichern
::   3. Git Pull vom GitHub Repository
::   4. Python-Pakete aktualisieren
::   5. Frontend Build erstellen
::   6. Dienste starten (start-all.bat)
::
:: SICHERHEIT:
::   - .env Dateien werden NIEMALS ueberschrieben
::   - MongoDB Daten bleiben unberuehrt
::
:: =====================================================

set "LIVE_DIR=C:\eventenergie"
set "BRANCH=Main_0.9APP"

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
echo  [1/6] Dienste stoppen...
if exist "%LIVE_DIR%\stop-all.bat" (
    call "%LIVE_DIR%\stop-all.bat"
) else (
    taskkill /FI "WINDOWTITLE eq Eventenergie Backend" /F >nul 2>&1
    taskkill /FI "WINDOWTITLE eq Eventenergie Caddy" /F >nul 2>&1
    taskkill /IM caddy.exe /F >nul 2>&1
    timeout /t 2 /nobreak >nul
)
echo   Dienste gestoppt.

:: ====== 2. .env sichern ======
echo.
echo  [2/6] .env Dateien sichern...
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
echo  [3/6] Code von GitHub aktualisieren...
echo   Branch: %BRANCH%

where git >nul 2>&1
if !errorlevel! neq 0 (
    echo   FEHLER: Git ist nicht installiert!
    echo   Bitte Git installieren: https://git-scm.com/download/win
    pause
    exit /b 1
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
echo  [4/6] Python-Pakete aktualisieren...
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
echo  [5/6] Frontend Build erstellen...
cd /d "%LIVE_DIR%\frontend"
call npm install --legacy-peer-deps 2>nul
echo   Node-Pakete installiert
call npm run build
if !errorlevel! equ 0 (
    echo   Build erfolgreich!
) else (
    echo   FEHLER: Build fehlgeschlagen!
    echo   Bitte manuell pruefen: cd %LIVE_DIR%\frontend ^&^& npm run build
)

:: ====== 6. Dienste starten ======
echo.
echo  [6/6] Dienste starten...
cd /d "%LIVE_DIR%"
if exist "%LIVE_DIR%\start-all.bat" (
    call "%LIVE_DIR%\start-all.bat"
) else (
    echo   FEHLER: start-all.bat nicht gefunden!
)

:: ====== Zusammenfassung ======
echo.
echo  ==================================================
echo   Update abgeschlossen!
echo   %date% %time%
echo  ==================================================
echo.
echo   Branch:  %BRANCH%
echo   Portal:  http://portal.eventenergie.com:8001
echo.
echo   Geschuetzte Dateien (NICHT ueberschrieben):
echo     backend\.env   (Datenbank, JWT, SMTP)
echo     frontend\.env  (Portal-URL)
echo     MongoDB Daten  (unveraendert)
echo.
pause
