@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
:: =====================================================
:: Eventenergie - Datenbank Migration
:: =====================================================
:: Erstellt ein komprimiertes Backup der MongoDB
:: Nutzung: Auf dem ALTEN Server ausfuehren
:: =====================================================

set "BACKUP_DIR=C:\eventenergie\migration"
set "DB_NAME=eventenergie"
set "TIMESTAMP=%date:~6,4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%"
set "TIMESTAMP=!TIMESTAMP: =0!"
set "BACKUP_FILE=%BACKUP_DIR%\%DB_NAME%_migration_%TIMESTAMP%.gz"

echo.
echo  ==================================================
echo   Eventenergie - Datenbank Export (ALTER Server)
echo   %date% %time%
echo  ==================================================
echo.

if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

:: Pruefen ob mongodump vorhanden
where mongodump >nul 2>&1
if !errorlevel! neq 0 (
    echo   FEHLER: mongodump nicht gefunden!
    echo   MongoDB Database Tools muessen installiert sein.
    echo   Download: https://www.mongodb.com/try/download/database-tools
    pause
    exit /b 1
)

:: Pruefen ob MongoDB laeuft
sc query MongoDB | findstr "RUNNING" >nul 2>&1
if !errorlevel! neq 0 (
    echo   WARNUNG: MongoDB scheint nicht zu laufen.
    echo   Versuche trotzdem...
)

echo  [1/3] Datenbank-Statistik...
echo.
mongo --quiet --eval "db = db.getSiblingDB('%DB_NAME%'); var cols = db.getCollectionNames(); print('  Datenbank: %DB_NAME%'); print('  Collections: ' + cols.length); cols.forEach(function(c) { var count = db[c].countDocuments({}); print('    - ' + c + ': ' + count + ' Dokumente'); });" 2>nul
echo.

echo  [2/3] Backup erstellen...
echo   Ziel: %BACKUP_FILE%
echo   (Das kann einige Minuten dauern bei grossen Datenbanken)
echo.
mongodump --uri="mongodb://localhost:27017" --db=%DB_NAME% --archive="%BACKUP_FILE%" --gzip 2>&1
if !errorlevel! neq 0 (
    echo.
    echo   FEHLER: Backup fehlgeschlagen!
    pause
    exit /b 1
)

echo.
echo  [3/3] Backup pruefen...
for %%A in ("%BACKUP_FILE%") do set "SIZE=%%~zA"
set /a "SIZE_MB=!SIZE!/1048576"
echo   Datei: %BACKUP_FILE%
echo   Groesse: !SIZE_MB! MB (!SIZE! Bytes)

echo.
echo  ==================================================
echo   Export erfolgreich!
echo  ==================================================
echo.
echo   Backup-Datei: %BACKUP_FILE%
echo.
echo   NAECHSTER SCHRITT:
echo   Diese Datei auf den NEUEN Server kopieren nach:
echo     C:\eventenergie\migration\
echo.
echo   Dann auf dem NEUEN Server ausfuehren:
echo     db-import.bat
echo.
pause
