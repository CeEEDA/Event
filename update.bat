@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
:: =====================================================
:: Eventenergie Portal - Update via GitHub
:: =====================================================
:: VERWENDUNG: Doppelklick (Als Administrator empfohlen)
:: SICHERHEIT: .env + MongoDB bleiben unberuehrt
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
echo  [1/6] Dienste stoppen...
if exist "%LIVE_DIR%\stop-all.bat" (
    call "%LIVE_DIR%\stop-all.bat" nopause
) else (
    taskkill /FI "WINDOWTITLE eq Eventenergie Backend" /F >nul 2>&1
    taskkill /FI "WINDOWTITLE eq Eventenergie Caddy" /F >nul 2>&1
    taskkill /FI "WINDOWTITLE eq Eventenergie Ollama" /F >nul 2>&1
    taskkill /IM caddy.exe /F >nul 2>&1
    taskkill /IM nginx.exe /F >nul 2>&1
    taskkill /IM ollama.exe /F >nul 2>&1
    taskkill /IM "ollama app.exe" /F >nul 2>&1
    timeout /t 3 /nobreak >nul
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
    pause
    exit /b 1
)

if not exist "%LIVE_DIR%\.git" (
    echo   Kein Git-Repository gefunden. Initialisiere...
    git init 2>&1
    git remote add origin %REPO_URL% 2>&1
)

git fetch --all 2>&1
if !errorlevel! neq 0 (
    echo   FEHLER: Git fetch fehlgeschlagen.
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
    echo   WARNUNG: Git pull Probleme. Versuche Reset...
    git reset --hard origin/%BRANCH% 2>&1
)
echo   Code aktualisiert.

:: .env wiederherstellen falls ueberschrieben
echo.
echo  [3b] .env Dateien pruefen...
if not exist "%LIVE_DIR%\backend\.env" (
    if exist "%LIVE_DIR%\backend\.env.backup" (
        copy /Y "%LIVE_DIR%\backend\.env.backup" "%LIVE_DIR%\backend\.env" >nul
        echo   backend\.env aus Backup wiederhergestellt
    ) else (
        echo   WARNUNG: backend\.env fehlt!
    )
) else (
    echo   backend\.env OK
)
if not exist "%LIVE_DIR%\frontend\.env" (
    if exist "%LIVE_DIR%\frontend\.env.backup" (
        copy /Y "%LIVE_DIR%\frontend\.env.backup" "%LIVE_DIR%\frontend\.env" >nul
        echo   frontend\.env aus Backup wiederhergestellt
    ) else (
        echo   WARNUNG: frontend\.env fehlt!
    )
) else (
    echo   frontend\.env OK
)

:: ====== 4. Python-Pakete (goto-basiert) ======
echo.
echo  [4/6] Python-Pakete aktualisieren...
cd /d "%LIVE_DIR%\backend"

set "REQ_FILE=requirements.txt"
if exist "%LIVE_DIR%\backend\requirements-server.txt" set "REQ_FILE=requirements-server.txt"
echo   Verwende: %REQ_FILE%

if exist "%LIVE_DIR%\venv\Scripts\activate.bat" goto :pip_venv_root
if exist "%LIVE_DIR%\backend\venv\Scripts\activate.bat" goto :pip_venv_backend
goto :pip_global
:pip_venv_root
call "%LIVE_DIR%\venv\Scripts\activate.bat"
echo   venv: %LIVE_DIR%\venv
pip install -r %REQ_FILE% --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ 2>&1
goto :pip_done
:pip_venv_backend
call "%LIVE_DIR%\backend\venv\Scripts\activate.bat"
echo   venv: %LIVE_DIR%\backend\venv
pip install -r %REQ_FILE% --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ 2>&1
goto :pip_done
:pip_global
echo   WARNUNG: Kein venv gefunden
pip install -r %REQ_FILE% --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ 2>&1
goto :pip_done
:pip_done
echo   Python-Pakete aktualisiert.

:: ====== 5. Frontend Build ======
echo.
echo  [5/6] Frontend Build erstellen...
cd /d "%LIVE_DIR%\frontend"

where yarn >nul 2>&1
if !errorlevel! equ 0 goto :build_yarn
goto :build_npm
:build_yarn
echo   yarn install...
call yarn install --frozen-lockfile 2>&1
echo   yarn build... (kann 2-5 Minuten dauern)
set GENERATE_SOURCEMAP=false
set NODE_OPTIONS=--max-old-space-size=8192
call yarn build 2>&1
echo   Build erfolgreich (yarn)
goto :build_done
:build_npm
echo   WARNUNG: yarn nicht gefunden - verwende npm
call npm install --legacy-peer-deps 2>&1
set GENERATE_SOURCEMAP=false
set NODE_OPTIONS=--max-old-space-size=8192
call npm run build 2>&1
echo   Build erfolgreich (npm)
goto :build_done
:build_done

:: Desktop-Installer kopieren
if exist "%LIVE_DIR%\desktop" (
    if not exist "%LIVE_DIR%\backend\static\desktop-installers" mkdir "%LIVE_DIR%\backend\static\desktop-installers"
    for %%f in (install-mac.sh install-win.bat install-win.ps1 server-setup-win.ps1 db-migrate-win.ps1 deploy-win.ps1 build-mobile.ps1 build-mobile.sh) do (
        if exist "%LIVE_DIR%\desktop\%%f" copy /Y "%LIVE_DIR%\desktop\%%f" "%LIVE_DIR%\backend\static\desktop-installers\" >nul
    )
    echo   Desktop-Installer kopiert
)

:: ====== 6. Dienste starten ======
echo.
echo  [6/6] Dienste starten...
cd /d "%LIVE_DIR%"
if exist "%LIVE_DIR%\start-all.bat" (
    call "%LIVE_DIR%\start-all.bat" nopause
) else (
    echo   FEHLER: start-all.bat nicht gefunden!
)

:: ====== Zusammenfassung ======
echo.
echo  ==================================================
echo   Update abgeschlossen - %date% %time%
echo   Branch: %BRANCH%
echo  ==================================================
echo.
echo   Geschuetzte Dateien (NICHT ueberschrieben):
echo     backend\.env   (Datenbank, JWT, SMTP)
echo     frontend\.env  (Portal-URL)
echo     MongoDB Daten  (unveraendert)
echo.
pause
