@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
:: =====================================================
:: Eventenergie - Datenbank Import
:: =====================================================
:: Importiert ein Backup in die lokale MongoDB
:: Nutzung: Auf dem NEUEN Server ausfuehren
:: =====================================================

set "BACKUP_DIR=C:\eventenergie\migration"
set "DB_NAME=eventenergie"
set "SAFETY_DIR=C:\eventenergie\backups\pre-migration"

echo.
echo  ==================================================
echo   Eventenergie - Datenbank Import (NEUER Server)
echo   %date% %time%
echo  ==================================================
echo.

:: Pruefen ob mongorestore vorhanden
where mongorestore >nul 2>&1
if !errorlevel! neq 0 (
    echo   FEHLER: mongorestore nicht gefunden!
    echo   MongoDB Database Tools muessen installiert sein.
    echo   Download: https://www.mongodb.com/try/download/database-tools
    pause
    exit /b 1
)

:: Pruefen ob Migration-Ordner existiert
if not exist "%BACKUP_DIR%" (
    echo   FEHLER: Ordner %BACKUP_DIR% nicht gefunden!
    echo   Bitte die Backup-Datei vom alten Server hierher kopieren.
    pause
    exit /b 1
)

:: Neueste Backup-Datei finden
set "LATEST="
for /f "delims=" %%f in ('dir /b /o-d "%BACKUP_DIR%\*.gz" 2^>nul') do (
    if not defined LATEST set "LATEST=%%f"
)

if not defined LATEST (
    echo   FEHLER: Keine .gz Backup-Datei gefunden in %BACKUP_DIR%
    echo   Bitte die Backup-Datei vom alten Server hierher kopieren.
    pause
    exit /b 1
)

echo   Gefundene Backup-Datei: %LATEST%
for %%A in ("%BACKUP_DIR%\%LATEST%") do set "SIZE=%%~zA"
set /a "SIZE_MB=!SIZE!/1048576"
echo   Groesse: !SIZE_MB! MB
echo.

:: Sicherheits-Backup der aktuellen DB
echo  [1/4] Sicherheits-Backup der aktuellen Datenbank...
if not exist "%SAFETY_DIR%" mkdir "%SAFETY_DIR%"
set "TIMESTAMP=%date:~6,4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%"
set "TIMESTAMP=!TIMESTAMP: =0!"
mongodump --uri="mongodb://localhost:27017" --db=%DB_NAME% --archive="%SAFETY_DIR%\pre_migration_%TIMESTAMP%.gz" --gzip >nul 2>&1
if !errorlevel! equ 0 (
    echo   Sicherheits-Backup erstellt: pre_migration_%TIMESTAMP%.gz
) else (
    echo   Hinweis: Kein bestehendes Backup noetig (DB evtl. leer)
)

:: Backend stoppen
echo.
echo  [2/4] Backend stoppen...
taskkill /FI "WINDOWTITLE eq Eventenergie Backend" /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8002 " 2^>nul') do (
    if %%a GTR 100 taskkill /PID %%a /F >nul 2>&1
)
timeout /t 2 /nobreak >nul
echo   Backend gestoppt.

:: Bestaetigung vom Benutzer
echo.
echo  ==================================================
echo   ACHTUNG: Die bestehende Datenbank "%DB_NAME%"
echo   wird KOMPLETT durch das Backup ersetzt!
echo  ==================================================
echo.
echo   Backup-Datei: %LATEST%
echo   Sicherung:    %SAFETY_DIR%\pre_migration_%TIMESTAMP%.gz
echo.
set /p "CONFIRM=  Fortfahren? (J/N): "
if /i not "!CONFIRM!"=="J" (
    echo   Abgebrochen.
    pause
    exit /b 0
)

:: Import durchfuehren
echo.
echo  [3/4] Datenbank importieren...
echo   (Das kann einige Minuten dauern)
echo.
mongorestore --uri="mongodb://localhost:27017" --db=%DB_NAME% --archive="%BACKUP_DIR%\%LATEST%" --gzip --drop 2>&1
if !errorlevel! neq 0 (
    echo.
    echo   FEHLER: Import fehlgeschlagen!
    echo   Die alte Datenbank kann wiederhergestellt werden mit:
    echo     mongorestore --uri="mongodb://localhost:27017" --db=%DB_NAME% --archive="%SAFETY_DIR%\pre_migration_%TIMESTAMP%.gz" --gzip --drop
    pause
    exit /b 1
)

:: MQTT Config auf Port 1883 aktualisieren
echo.
echo  [4/4] MQTT-Konfiguration aktualisieren...
mongo --quiet --eval "db = db.getSiblingDB('%DB_NAME%'); db.mqtt_config.updateOne({}, {$set: {broker_port: 1883}}); print('  MQTT Port auf 1883 gesetzt');" 2>nul

:: Statistik anzeigen
echo.
echo  Importierte Datenbank:
mongo --quiet --eval "db = db.getSiblingDB('%DB_NAME%'); var cols = db.getCollectionNames(); print('  Collections: ' + cols.length); cols.forEach(function(c) { var count = db[c].countDocuments({}); print('    - ' + c + ': ' + count + ' Dokumente'); });" 2>nul

echo.
echo  ==================================================
echo   Import erfolgreich!
echo  ==================================================
echo.
echo   Datenbank "%DB_NAME%" wurde importiert.
echo   MQTT Port auf 1883 gesetzt.
echo.
echo   NAECHSTER SCHRITT:
echo   Dienste starten mit: start-all.bat
echo.
pause
