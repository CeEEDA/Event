@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: =====================================================
:: Eventenergie Portal - Sicheres Update
:: =====================================================
::
:: VERWENDUNG:
::   1. ZIP an beliebige Stelle entpacken (z.B. C:\Downloads\update)
::   2. Diese Datei doppelklicken (Als Admin ausfuehren)
::   3. Pfad zum entpackten Update eingeben
::   4. Fertig - nur Code wird aktualisiert
::
:: SICHER:
::   - .env Dateien werden NIEMALS ueberschrieben
::   - MongoDB Daten bleiben unberuehrt
::   - node_modules bleiben erhalten
::   - Backup wird vorher erstellt
::
:: =====================================================

set "LIVE_DIR=C:\eventenergie"
set "BACKUP_DIR=%LIVE_DIR%\backups"

echo.
echo  ==================================================
echo   Eventenergie Portal - Sicheres Update
echo   %date% %time%
echo  ==================================================
echo.
echo   LIVE-Verzeichnis: %LIVE_DIR%
echo.

:: ====== Quellverzeichnis abfragen ======
set /p "UPDATE_DIR=Pfad zum entpackten Update (z.B. C:\Downloads\update): "

if not exist "%UPDATE_DIR%" (
    echo.
    echo   FEHLER: Verzeichnis "%UPDATE_DIR%" nicht gefunden!
    pause
    exit /b 1
)

:: Pruefen ob es wie ein Portal-Update aussieht
if not exist "%UPDATE_DIR%\backend" (
    :: Vielleicht liegt es eine Ebene tiefer
    for /d %%d in ("%UPDATE_DIR%\*") do (
        if exist "%%d\backend" (
            set "UPDATE_DIR=%%d"
            echo   Update gefunden in: !UPDATE_DIR!
        )
    )
)

if not exist "%UPDATE_DIR%\backend" (
    echo   FEHLER: Kein gueltiges Update gefunden (backend/ fehlt)
    pause
    exit /b 1
)

echo.
echo   Update-Quelle: %UPDATE_DIR%
echo.

:: ====== Sicherheits-Checks ======
echo  [1/7] Sicherheits-Checks...

:: .env Dateien sichern (WICHTIGSTER SCHRITT)
echo   .env Dateien sichern...
if exist "%LIVE_DIR%\backend\.env" (
    copy /Y "%LIVE_DIR%\backend\.env" "%LIVE_DIR%\backend\.env.backup" >nul
    echo     backend\.env gesichert
) else (
    echo     WARNUNG: backend\.env nicht gefunden!
)
if exist "%LIVE_DIR%\frontend\.env" (
    copy /Y "%LIVE_DIR%\frontend\.env" "%LIVE_DIR%\frontend\.env.backup" >nul
    echo     frontend\.env gesichert
) else (
    echo     WARNUNG: frontend\.env nicht gefunden!
)

:: ====== Backup erstellen ======
echo.
echo  [2/7] Backup erstellen...
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

set "TIMESTAMP=%date:~6,4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"

:: Nur Quellcode sichern (nicht node_modules oder build)
powershell -Command "& { $src = @('%LIVE_DIR%\backend\server.py','%LIVE_DIR%\backend\routes','%LIVE_DIR%\backend\.env','%LIVE_DIR%\frontend\src','%LIVE_DIR%\frontend\.env','%LIVE_DIR%\frontend\package.json'); $existing = $src | Where-Object { Test-Path $_ }; if ($existing) { Compress-Archive -Path $existing -DestinationPath '%BACKUP_DIR%\backup_%TIMESTAMP%.zip' -Force } }" 2>nul
echo   Backup: %BACKUP_DIR%\backup_%TIMESTAMP%.zip

:: ====== Dienste stoppen ======
echo.
echo  [3/7] Dienste stoppen...
taskkill /FI "WINDOWTITLE eq Eventenergie Backend*" /F 2>nul
taskkill /FI "WINDOWTITLE eq Eventenergie Frontend*" /F 2>nul
where pm2 >nul 2>&1 && pm2 stop all 2>nul
timeout /t 2 /nobreak >nul
echo   Dienste gestoppt.

:: ====== Backend aktualisieren ======
echo.
echo  [4/7] Backend aktualisieren...

:: server.py
if exist "%UPDATE_DIR%\backend\server.py" (
    copy /Y "%UPDATE_DIR%\backend\server.py" "%LIVE_DIR%\backend\server.py" >nul
    echo     server.py aktualisiert
)

:: Routes
if exist "%UPDATE_DIR%\backend\routes" (
    xcopy /Y /E /I "%UPDATE_DIR%\backend\routes" "%LIVE_DIR%\backend\routes" >nul
    echo     routes\ aktualisiert
)

:: Services
if exist "%UPDATE_DIR%\backend\services" (
    xcopy /Y /E /I "%UPDATE_DIR%\backend\services" "%LIVE_DIR%\backend\services" >nul
    echo     services\ aktualisiert
)

:: mqtt_service.py
if exist "%UPDATE_DIR%\backend\mqtt_service.py" (
    copy /Y "%UPDATE_DIR%\backend\mqtt_service.py" "%LIVE_DIR%\backend\mqtt_service.py" >nul
    echo     mqtt_service.py aktualisiert
)

:: migrate_db.py
if exist "%UPDATE_DIR%\backend\migrate_db.py" (
    copy /Y "%UPDATE_DIR%\backend\migrate_db.py" "%LIVE_DIR%\backend\migrate_db.py" >nul
    echo     migrate_db.py aktualisiert
)

:: Static files (Pi scripts, Mosquitto etc.)
if exist "%UPDATE_DIR%\backend\static" (
    xcopy /Y /E /I "%UPDATE_DIR%\backend\static" "%LIVE_DIR%\backend\static" >nul
    echo     static\ aktualisiert
)

:: Assets
if exist "%UPDATE_DIR%\backend\assets" (
    xcopy /Y /E /I "%UPDATE_DIR%\backend\assets" "%LIVE_DIR%\backend\assets" >nul
    echo     assets\ aktualisiert
)

:: requirements.txt (nur kopieren, nicht .env!)
if exist "%UPDATE_DIR%\backend\requirements.txt" (
    copy /Y "%UPDATE_DIR%\backend\requirements.txt" "%LIVE_DIR%\backend\requirements.txt" >nul
    echo     requirements.txt aktualisiert
)

:: .env NICHT kopieren!
echo     .env NICHT ueberschrieben (geschuetzt)

:: ====== Frontend aktualisieren ======
echo.
echo  [5/7] Frontend aktualisieren...

:: src/ Verzeichnis (der gesamte Quellcode)
if exist "%UPDATE_DIR%\frontend\src" (
    xcopy /Y /E /I "%UPDATE_DIR%\frontend\src" "%LIVE_DIR%\frontend\src" >nul
    echo     src\ aktualisiert
)

:: public/ Verzeichnis
if exist "%UPDATE_DIR%\frontend\public" (
    xcopy /Y /E /I "%UPDATE_DIR%\frontend\public" "%LIVE_DIR%\frontend\public" >nul
    echo     public\ aktualisiert
)

:: package.json (fuer neue Abhaengigkeiten)
if exist "%UPDATE_DIR%\frontend\package.json" (
    copy /Y "%UPDATE_DIR%\frontend\package.json" "%LIVE_DIR%\frontend\package.json" >nul
    echo     package.json aktualisiert
)

:: tailwind / postcss config
if exist "%UPDATE_DIR%\frontend\tailwind.config.js" (
    copy /Y "%UPDATE_DIR%\frontend\tailwind.config.js" "%LIVE_DIR%\frontend\tailwind.config.js" >nul
)

:: .env NICHT kopieren!
echo     .env NICHT ueberschrieben (geschuetzt)

:: ====== .env wiederherstellen (Sicherheitsnetz) ======
echo.
echo  [5b] .env Dateien pruefen...
if exist "%LIVE_DIR%\backend\.env.backup" (
    :: Pruefen ob .env noch korrekt ist
    findstr /C:"MONGO_URL" "%LIVE_DIR%\backend\.env" >nul 2>&1
    if %errorlevel% neq 0 (
        echo     WARNUNG: backend\.env war beschaedigt - stelle Backup wieder her
        copy /Y "%LIVE_DIR%\backend\.env.backup" "%LIVE_DIR%\backend\.env" >nul
    ) else (
        echo     backend\.env ist OK
    )
)
if exist "%LIVE_DIR%\frontend\.env.backup" (
    findstr /C:"REACT_APP" "%LIVE_DIR%\frontend\.env" >nul 2>&1
    if %errorlevel% neq 0 (
        echo     WARNUNG: frontend\.env war beschaedigt - stelle Backup wieder her
        copy /Y "%LIVE_DIR%\frontend\.env.backup" "%LIVE_DIR%\frontend\.env" >nul
    ) else (
        echo     frontend\.env ist OK
    )
)

:: ====== Abhaengigkeiten + Build ======
echo.
echo  [6/7] Abhaengigkeiten installieren + Build...

:: Python
cd /d "%LIVE_DIR%\backend"
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    pip install -r requirements.txt --quiet 2>nul
    echo     Python-Pakete aktualisiert
) else (
    pip install -r requirements.txt --quiet 2>nul
    echo     Python-Pakete aktualisiert (ohne venv)
)

:: Node.js
cd /d "%LIVE_DIR%\frontend"
call npm install --legacy-peer-deps 2>nul
echo     Node-Pakete aktualisiert

:: Build
echo     Frontend Build erstellen...
call npm run build
echo     Build erstellt!

:: ====== Migration + Neustart ======
echo.
echo  [7/7] Datenbank-Migration + Neustart...

cd /d "%LIVE_DIR%\backend"
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)
if exist "migrate_db.py" (
    python migrate_db.py
) else (
    echo     Keine Migration noetig
)

:: ====== Zusammenfassung ======
echo.
echo  ==================================================
echo   Update abgeschlossen!
echo  ==================================================
echo.
echo   Geschuetzte Dateien (NICHT ueberschrieben):
echo     - backend\.env   (Datenbank-Zugangsdaten)
echo     - frontend\.env  (Portal-URL)
echo     - MongoDB Daten  (unveraendert)
echo     - node_modules   (nur ergaenzt)
echo.
echo   Jetzt starten mit: start-all.bat
echo.
echo   Falls Daten fehlen sollten:
echo     .env Backup: backend\.env.backup
echo     Code Backup: %BACKUP_DIR%\
echo.
pause
