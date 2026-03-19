@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: =====================================================
:: Eventenergie Portal - Update Script
:: =====================================================
:: Pfad: C:\eventenergie
:: Ausfuehren: Rechtsklick -> Als Administrator ausfuehren
::
:: Dieses Script:
::   1. Stoppt laufende Dienste
::   2. Erstellt ein Backup
::   3. Aktualisiert den Code (Git Pull oder manuell)
::   4. Installiert Abhaengigkeiten
::   5. Fuehrt Datenbank-Migration durch
::   6. Startet die Dienste neu
:: =====================================================

set "PORTAL_DIR=C:\eventenergie"
set "BACKEND_DIR=%PORTAL_DIR%\backend"
set "FRONTEND_DIR=%PORTAL_DIR%\frontend"
set "BACKUP_DIR=%PORTAL_DIR%\backups"
set "TIMESTAMP=%date:~6,4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"

echo.
echo  ================================================
echo   Eventenergie Portal - Update
echo   %date% %time%
echo  ================================================
echo.

:: Admin-Rechte pruefen
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo  FEHLER: Bitte als Administrator ausfuehren!
    pause
    exit /b 1
)

:: ====== 1. Dienste stoppen ======
echo  [1/6] Dienste stoppen...

:: PM2 (falls installiert)
where pm2 >nul 2>&1
if %errorlevel% equ 0 (
    echo   PM2 erkannt - stoppe Prozesse...
    pm2 stop all 2>nul
    set "USE_PM2=1"
) else (
    set "USE_PM2=0"
)

:: Falls als Windows-Dienst laeuft
sc query EventenergieBackend >nul 2>&1
if %errorlevel% equ 0 (
    echo   Windows-Dienst erkannt - stoppe...
    net stop EventenergieBackend 2>nul
    net stop EventenergieFrontend 2>nul
    set "USE_SERVICE=1"
) else (
    set "USE_SERVICE=0"
)

:: Node/Python Prozesse beenden (Fallback)
echo   Beende laufende Prozesse...
taskkill /F /IM "node.exe" /FI "WINDOWTITLE eq *eventenergie*" 2>nul
taskkill /F /IM "python.exe" /FI "WINDOWTITLE eq *eventenergie*" 2>nul

:: Kurze Wartezeit
timeout /t 3 /nobreak >nul
echo   Dienste gestoppt.
echo.

:: ====== 2. Backup erstellen ======
echo  [2/6] Backup erstellen...
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

set "BACKUP_FILE=%BACKUP_DIR%\backup_%TIMESTAMP%.zip"

:: Nur wichtige Dateien sichern (nicht node_modules)
echo   Sichere Backend und Frontend...
powershell -Command "Compress-Archive -Path '%BACKEND_DIR%\*.py','%BACKEND_DIR%\routes','%BACKEND_DIR%\services','%BACKEND_DIR%\.env','%FRONTEND_DIR%\src','%FRONTEND_DIR%\.env','%FRONTEND_DIR%\package.json' -DestinationPath '%BACKUP_FILE%' -Force" 2>nul

if exist "%BACKUP_FILE%" (
    echo   Backup erstellt: %BACKUP_FILE%
) else (
    echo   WARNUNG: Backup konnte nicht erstellt werden, fahre trotzdem fort...
)
echo.

:: ====== 3. Code aktualisieren ======
echo  [3/6] Code aktualisieren...

cd /d "%PORTAL_DIR%"

:: Pruefen ob Git-Repo vorhanden
if exist ".git" (
    echo   Git-Repository erkannt...
    git stash 2>nul
    git pull origin main
    if %errorlevel% neq 0 (
        echo   WARNUNG: Git Pull fehlgeschlagen. Versuche force pull...
        git fetch --all
        git reset --hard origin/main
    )
    echo   Code aktualisiert via Git.
) else (
    echo   Kein Git-Repository gefunden.
    echo   Bitte Code manuell nach %PORTAL_DIR% kopieren
    echo   oder "git clone" ausfuehren.
    echo.
    echo   Falls Sie den Code als ZIP haben:
    echo   Entpacken Sie ihn nach %PORTAL_DIR%
    echo.
    set /p CONTINUE="   Weiter mit Installation? (j/n): "
    if /i "!CONTINUE!" neq "j" (
        echo   Abgebrochen.
        pause
        exit /b 0
    )
)
echo.

:: ====== 4. Abhaengigkeiten installieren ======
echo  [4/6] Abhaengigkeiten installieren...

:: Python Backend
echo   Backend (Python)...
cd /d "%BACKEND_DIR%"

:: Virtual Environment pruefen/erstellen
if not exist "venv" (
    echo   Erstelle Virtual Environment...
    python -m venv venv
)

:: Aktivieren und installieren
call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet 2>nul
if %errorlevel% neq 0 (
    echo   WARNUNG: Einige Python-Pakete konnten nicht installiert werden
    pip install -r requirements.txt
)
echo   Backend-Abhaengigkeiten installiert.

:: Node.js Frontend
echo   Frontend (Node.js)...
cd /d "%FRONTEND_DIR%"

:: Pruefen ob yarn verfuegbar
where yarn >nul 2>&1
if %errorlevel% equ 0 (
    yarn install --frozen-lockfile 2>nul || yarn install
) else (
    npm install
)
echo   Frontend-Abhaengigkeiten installiert.

:: Frontend Build erstellen
echo   Frontend Build...
if defined USE_PM2 (
    :: Bei PM2 brauchen wir einen Build
    yarn build 2>nul || npm run build
    echo   Frontend Build erstellt.
) else (
    echo   Frontend laeuft im Dev-Modus, kein Build noetig.
)
echo.

:: ====== 5. Datenbank-Migration ======
echo  [5/6] Datenbank-Migration...
cd /d "%BACKEND_DIR%"

:: Migration-Script ausfuehren
call venv\Scripts\activate.bat
python migrate_db.py
echo   Migration abgeschlossen.
echo.

:: ====== 6. Dienste starten ======
echo  [6/6] Dienste starten...

if "%USE_PM2%"=="1" (
    echo   Starte mit PM2...
    cd /d "%PORTAL_DIR%"
    pm2 start ecosystem.config.js 2>nul || (
        :: PM2 Konfiguration erstellen falls nicht vorhanden
        echo   Erstelle PM2 Konfiguration...
        pm2 start "%BACKEND_DIR%\venv\Scripts\python.exe" --name "eventenergie-backend" -- -m uvicorn server:app --host 0.0.0.0 --port 8001 --app-dir "%BACKEND_DIR%"
        pm2 start "npx" --name "eventenergie-frontend" -- serve -s build -l 3000 --cwd "%FRONTEND_DIR%"
    )
    pm2 save
    echo   PM2 Prozesse gestartet.
) else if "%USE_SERVICE%"=="1" (
    echo   Starte Windows-Dienste...
    net start EventenergieBackend
    net start EventenergieFrontend
) else (
    echo   Starte mit start_services.bat...
    call "%PORTAL_DIR%\start_services.bat"
)

echo.
echo  ================================================
echo   Update abgeschlossen!
echo  ================================================
echo.
echo   Backend:  http://localhost:8001
echo   Frontend: http://localhost:3000
echo.
echo   Logs pruefen:
echo     Backend:  %BACKEND_DIR%\logs\
echo     Frontend: PM2 logs oder Konsole
echo.
echo   Bei Problemen: update.bat nochmal ausfuehren
echo   Backup liegt unter: %BACKUP_DIR%
echo.
pause
