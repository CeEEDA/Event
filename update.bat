@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: =====================================================
:: Eventenergie Portal - Automatisches Update
:: =====================================================
::
:: VERWENDUNG:
::   1. Update-ZIP entpacken
::   2. Diese Datei doppelklicken (Als Administrator)
::   3. Das Script erkennt automatisch den Quellordner
::      und fuehrt das Update selbststaendig durch
::   4. Am Ende werden alle Dienste automatisch gestartet
::
:: SICHERHEIT:
::   - .env Dateien werden NIEMALS ueberschrieben
::   - MongoDB Daten bleiben unberuehrt
::   - Backup wird vorher erstellt
::   - Bei Fehler wird .env aus Backup wiederhergestellt
::
:: =====================================================

set "LIVE_DIR=C:\eventenergie"
set "BACKUP_DIR=%LIVE_DIR%\backups"

:: ====== Update-Quelle automatisch erkennen ======
:: Das Script liegt im entpackten Update-Ordner
set "SCRIPT_DIR=%~dp0"
set "UPDATE_DIR=%SCRIPT_DIR%"

:: Pruefen ob backend/ im gleichen Ordner liegt
if exist "%UPDATE_DIR%backend" (
    echo   Update-Quelle erkannt: %UPDATE_DIR%
    goto :found_update
)

:: Pruefen ob es eine Ebene tiefer liegt (z.B. eventenergie_update_2026-03-20\)
for /d %%d in ("%UPDATE_DIR%*") do (
    if exist "%%d\backend" (
        set "UPDATE_DIR=%%d\"
        echo   Update-Quelle erkannt: !UPDATE_DIR!
        goto :found_update
    )
)

:: Letzte Moeglichkeit: Manuell fragen
echo   Update-Quelle nicht automatisch erkannt.
set /p "UPDATE_DIR=Pfad zum entpackten Update (z.B. C:\Downloads\eventenergie_update): "
if not exist "%UPDATE_DIR%\backend" (
    echo   FEHLER: Kein gueltiges Update gefunden (backend/ fehlt)
    pause
    exit /b 1
)

:found_update
echo.
echo  ==================================================
echo   Eventenergie Portal - Automatisches Update
echo   %date% %time%
echo  ==================================================
echo.
echo   LIVE:    %LIVE_DIR%
echo   QUELLE:  %UPDATE_DIR%
echo.

:: ====== Pruefen ob Live-Verzeichnis existiert ======
if not exist "%LIVE_DIR%" (
    echo   LIVE-Verzeichnis %LIVE_DIR% nicht vorhanden.
    echo   Erstelle Verzeichnisstruktur...
    mkdir "%LIVE_DIR%\backend" 2>nul
    mkdir "%LIVE_DIR%\frontend" 2>nul
)

:: ====== 1. .env sichern ======
echo  [1/8] .env Dateien sichern...
if exist "%LIVE_DIR%\backend\.env" (
    copy /Y "%LIVE_DIR%\backend\.env" "%LIVE_DIR%\backend\.env.backup" >nul
    echo     backend\.env gesichert
) else (
    echo     Kein backend\.env vorhanden (Erstinstallation?)
)
if exist "%LIVE_DIR%\frontend\.env" (
    copy /Y "%LIVE_DIR%\frontend\.env" "%LIVE_DIR%\frontend\.env.backup" >nul
    echo     frontend\.env gesichert
) else (
    echo     Kein frontend\.env vorhanden (Erstinstallation?)
)

:: ====== 2. DB-Backup ======
echo.
echo  [2/8] Datenbank-Backup erstellen...
if not exist "%BACKUP_DIR%\db" mkdir "%BACKUP_DIR%\db"

set "TIMESTAMP=%date:~6,4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"

where mongodump >nul 2>&1
if %errorlevel% equ 0 (
    mongodump --uri="mongodb://localhost:27017" --db=eventenergie --archive="%BACKUP_DIR%\db\pre_update_%TIMESTAMP%.gz" --gzip >nul 2>&1
    if %errorlevel% equ 0 (
        echo     DB-Backup: pre_update_%TIMESTAMP%.gz
    ) else (
        echo     WARNUNG: DB-Backup fehlgeschlagen
    )
) else (
    echo     mongodump nicht verfuegbar - DB-Backup uebersprungen
)

:: Code-Backup (kompakt: nur Kernfiles)
echo     Code-Backup erstellen...
if not exist "%BACKUP_DIR%\code" mkdir "%BACKUP_DIR%\code"
powershell -Command "& { $items = @(); if(Test-Path '%LIVE_DIR%\backend\server.py'){$items += '%LIVE_DIR%\backend\server.py'}; if(Test-Path '%LIVE_DIR%\backend\routes'){$items += '%LIVE_DIR%\backend\routes'}; if(Test-Path '%LIVE_DIR%\backend\.env'){$items += '%LIVE_DIR%\backend\.env'}; if(Test-Path '%LIVE_DIR%\frontend\src'){$items += '%LIVE_DIR%\frontend\src'}; if(Test-Path '%LIVE_DIR%\frontend\.env'){$items += '%LIVE_DIR%\frontend\.env'}; if($items.Count -gt 0){Compress-Archive -Path $items -DestinationPath '%BACKUP_DIR%\code\pre_update_%TIMESTAMP%.zip' -Force; Write-Host '    Code-Backup: pre_update_%TIMESTAMP%.zip'} else {Write-Host '    Keine Dateien zum Sichern'} }" 2>nul

:: ====== 3. Dienste stoppen ======
echo.
echo  [3/8] Dienste stoppen...
taskkill /FI "WINDOWTITLE eq Eventenergie Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Eventenergie Caddy*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Eventenergie Frontend*" /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 2 /nobreak >nul
echo     Dienste gestoppt.

:: ====== 4. Backend aktualisieren ======
echo.
echo  [4/8] Backend aktualisieren...

if exist "%UPDATE_DIR%backend\server.py" (
    copy /Y "%UPDATE_DIR%backend\server.py" "%LIVE_DIR%\backend\server.py" >nul
    echo     server.py
)
if exist "%UPDATE_DIR%backend\email_service.py" (
    copy /Y "%UPDATE_DIR%backend\email_service.py" "%LIVE_DIR%\backend\email_service.py" >nul
    echo     email_service.py
)
if exist "%UPDATE_DIR%backend\mqtt_service.py" (
    copy /Y "%UPDATE_DIR%backend\mqtt_service.py" "%LIVE_DIR%\backend\mqtt_service.py" >nul
    echo     mqtt_service.py
)
if exist "%UPDATE_DIR%backend\migrate_db.py" (
    copy /Y "%UPDATE_DIR%backend\migrate_db.py" "%LIVE_DIR%\backend\migrate_db.py" >nul
    echo     migrate_db.py
)
if exist "%UPDATE_DIR%backend\routes" (
    xcopy /Y /E /I "%UPDATE_DIR%backend\routes" "%LIVE_DIR%\backend\routes" >nul
    echo     routes\
)
if exist "%UPDATE_DIR%backend\services" (
    xcopy /Y /E /I "%UPDATE_DIR%backend\services" "%LIVE_DIR%\backend\services" >nul
    echo     services\
)
if exist "%UPDATE_DIR%backend\static" (
    xcopy /Y /E /I "%UPDATE_DIR%backend\static" "%LIVE_DIR%\backend\static" >nul
    echo     static\
)
if exist "%UPDATE_DIR%backend\assets" (
    xcopy /Y /E /I "%UPDATE_DIR%backend\assets" "%LIVE_DIR%\backend\assets" >nul
    echo     assets\
)
if exist "%UPDATE_DIR%backend\requirements.txt" (
    copy /Y "%UPDATE_DIR%backend\requirements.txt" "%LIVE_DIR%\backend\requirements.txt" >nul
    echo     requirements.txt
)
echo     .env NICHT ueberschrieben (geschuetzt)

:: ====== 5. Frontend aktualisieren ======
echo.
echo  [5/8] Frontend aktualisieren...

if exist "%UPDATE_DIR%frontend\src" (
    xcopy /Y /E /I "%UPDATE_DIR%frontend\src" "%LIVE_DIR%\frontend\src" >nul
    echo     src\
)
if exist "%UPDATE_DIR%frontend\public" (
    xcopy /Y /E /I "%UPDATE_DIR%frontend\public" "%LIVE_DIR%\frontend\public" >nul
    echo     public\
)
if exist "%UPDATE_DIR%frontend\package.json" (
    copy /Y "%UPDATE_DIR%frontend\package.json" "%LIVE_DIR%\frontend\package.json" >nul
    echo     package.json
)
if exist "%UPDATE_DIR%frontend\tailwind.config.js" (
    copy /Y "%UPDATE_DIR%frontend\tailwind.config.js" "%LIVE_DIR%\frontend\tailwind.config.js" >nul
    echo     tailwind.config.js
)
if exist "%UPDATE_DIR%frontend\craco.config.js" (
    copy /Y "%UPDATE_DIR%frontend\craco.config.js" "%LIVE_DIR%\frontend\craco.config.js" >nul
    echo     craco.config.js
)
if exist "%UPDATE_DIR%frontend\postcss.config.js" (
    copy /Y "%UPDATE_DIR%frontend\postcss.config.js" "%LIVE_DIR%\frontend\postcss.config.js" >nul
    echo     postcss.config.js
)
echo     .env NICHT ueberschrieben (geschuetzt)

:: Root-Dateien aktualisieren (Caddyfile, Startscripts)
if exist "%UPDATE_DIR%Caddyfile" (
    copy /Y "%UPDATE_DIR%Caddyfile" "%LIVE_DIR%\Caddyfile" >nul
    echo     Caddyfile
)
if exist "%UPDATE_DIR%start-all.bat" (
    copy /Y "%UPDATE_DIR%start-all.bat" "%LIVE_DIR%\start-all.bat" >nul
    echo     start-all.bat
)
if exist "%UPDATE_DIR%stop-all.bat" (
    copy /Y "%UPDATE_DIR%stop-all.bat" "%LIVE_DIR%\stop-all.bat" >nul
    echo     stop-all.bat
)
if exist "%UPDATE_DIR%UPDATE_ANLEITUNG.md" (
    copy /Y "%UPDATE_DIR%UPDATE_ANLEITUNG.md" "%LIVE_DIR%\UPDATE_ANLEITUNG.md" >nul
    echo     UPDATE_ANLEITUNG.md
)

:: ====== 5b. .env pruefen und wiederherstellen ======
echo.
echo  [5b] .env Dateien pruefen...

:: Backend .env
if not exist "%LIVE_DIR%\backend\.env" (
    if exist "%LIVE_DIR%\backend\.env.backup" (
        copy /Y "%LIVE_DIR%\backend\.env.backup" "%LIVE_DIR%\backend\.env" >nul
        echo     backend\.env aus Backup wiederhergestellt
    ) else (
        echo     WARNUNG: backend\.env fehlt und kein Backup vorhanden!
        echo     Bitte manuell erstellen - siehe backend\.env.example
    )
) else (
    findstr /C:"MONGO_URL" "%LIVE_DIR%\backend\.env" >nul 2>&1
    if %errorlevel% neq 0 (
        if exist "%LIVE_DIR%\backend\.env.backup" (
            copy /Y "%LIVE_DIR%\backend\.env.backup" "%LIVE_DIR%\backend\.env" >nul
            echo     backend\.env war beschaedigt - Backup wiederhergestellt
        )
    ) else (
        echo     backend\.env OK
    )
)

:: Frontend .env
if not exist "%LIVE_DIR%\frontend\.env" (
    if exist "%LIVE_DIR%\frontend\.env.backup" (
        copy /Y "%LIVE_DIR%\frontend\.env.backup" "%LIVE_DIR%\frontend\.env" >nul
        echo     frontend\.env aus Backup wiederhergestellt
    ) else (
        echo REACT_APP_BACKEND_URL=https://portal.eventenergie.com> "%LIVE_DIR%\frontend\.env"
        echo     frontend\.env mit Standard-URL erstellt
    )
) else (
    findstr /C:"REACT_APP" "%LIVE_DIR%\frontend\.env" >nul 2>&1
    if %errorlevel% neq 0 (
        if exist "%LIVE_DIR%\frontend\.env.backup" (
            copy /Y "%LIVE_DIR%\frontend\.env.backup" "%LIVE_DIR%\frontend\.env" >nul
            echo     frontend\.env war beschaedigt - Backup wiederhergestellt
        )
    ) else (
        echo     frontend\.env OK
    )
)

:: ====== 6. Python-Pakete installieren ======
echo.
echo  [6/8] Python-Pakete aktualisieren...
cd /d "%LIVE_DIR%\backend"
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    pip install -r requirements.txt --quiet 2>nul
    echo     Python-Pakete aktualisiert (venv)
) else (
    pip install -r requirements.txt --quiet 2>nul
    echo     Python-Pakete aktualisiert
)

:: ====== 7. Frontend Build ======
echo.
echo  [7/8] Frontend Build erstellen...
cd /d "%LIVE_DIR%\frontend"
call npm install --legacy-peer-deps 2>nul
echo     Node-Pakete installiert
call npm run build
if %errorlevel% equ 0 (
    echo     Build erfolgreich!
) else (
    echo     FEHLER: Build fehlgeschlagen!
    echo     Pruefen Sie frontend\.env und versuchen Sie:
    echo       cd %FRONTEND_DIR% ^&^& npm run build
)

:: ====== 8. Migration + Neustart ======
echo.
echo  [8/8] Migration + Dienste starten...

:: Migration
cd /d "%LIVE_DIR%\backend"
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)
if exist "migrate_db.py" (
    python migrate_db.py 2>nul
    echo     Migration ausgefuehrt
)

:: Dienste starten
echo     Dienste werden gestartet...
cd /d "%LIVE_DIR%"
if exist "start-all.bat" (
    call start-all.bat
) else (
    echo     start-all.bat nicht gefunden - starte manuell...
    start "Eventenergie Backend" cmd /c "cd /d %LIVE_DIR%\backend && python -m uvicorn server:app --host 0.0.0.0 --port 8001"
    timeout /t 3 /nobreak >nul
    if exist "%LIVE_DIR%\caddy.exe" (
        start "Eventenergie Caddy" cmd /c "cd /d %LIVE_DIR% && caddy.exe run --config Caddyfile"
    )
)

:: ====== Zusammenfassung ======
echo.
echo  ==================================================
echo   Update erfolgreich abgeschlossen!
echo   %date% %time%
echo  ==================================================
echo.
echo   Geschuetzte Dateien (NICHT ueberschrieben):
echo     backend\.env   (Datenbank, SMTP)
echo     frontend\.env  (Portal-URL)
echo     MongoDB Daten  (unveraendert)
echo.
echo   Backups erstellt in:
echo     DB:    %BACKUP_DIR%\db\
echo     Code:  %BACKUP_DIR%\code\
echo.
echo   Portal:  https://portal.eventenergie.com
echo.
pause
