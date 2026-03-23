@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: =====================================================
:: Eventenergie Portal - Start
:: =====================================================
:: Parameter: nopause - Ueberspringe pause am Ende
::   Beispiel: start-all.bat nopause
:: =====================================================

set "PORTAL_DIR=C:\eventenergie"
set "BACKEND_DIR=%PORTAL_DIR%\backend"
set "FRONTEND_DIR=%PORTAL_DIR%\frontend"
set "BACKUP_DIR=%PORTAL_DIR%\backups\db"
set "LOG_DIR=%PORTAL_DIR%\logs"

:: Logs-Ordner erstellen
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo.
echo  ==================================================
echo   Eventenergie Portal wird gestartet...
echo   %date% %time%
echo  ==================================================
echo.

:: ====== 1. Laufende Dienste stoppen ======
echo  [1/7] Laufende Dienste stoppen...

:: Nur gezielt unsere Prozesse beenden (NICHT explorer.exe oder Systemprozesse!)
taskkill /FI "WINDOWTITLE eq Eventenergie Backend" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Eventenergie Caddy" /F >nul 2>&1
taskkill /IM caddy.exe /F >nul 2>&1

:: Port 8001 freigeben - aber NUR wenn es UNSER Prozess ist (nicht System-PIDs)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "0.0.0.0:8001" ^| findstr LISTENING 2^>nul') do (
    if %%a GTR 100 (
        taskkill /PID %%a /F >nul 2>&1
    )
)
:: Port 8002 freigeben
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "0.0.0.0:8002" ^| findstr LISTENING 2^>nul') do (
    if %%a GTR 100 (
        taskkill /PID %%a /F >nul 2>&1
    )
)
timeout /t 3 /nobreak >nul
echo   Alte Prozesse beendet.

:: ====== 2. Mosquitto MQTT Broker starten ======
echo.
echo  [2/8] Mosquitto MQTT Broker pruefen...
set "MOSQUITTO_DIR=C:\Program Files\Mosquitto"
netstat -ano | findstr "0.0.0.0:1883" | findstr LISTENING >nul 2>&1
if !errorlevel! equ 0 (
    echo   Mosquitto laeuft bereits auf Port 1883
) else (
    if exist "%MOSQUITTO_DIR%\mosquitto.exe" (
        taskkill /IM mosquitto.exe /F >nul 2>&1
        timeout /t 1 /nobreak >nul
        start "Eventenergie MQTT" /min "%MOSQUITTO_DIR%\mosquitto.exe" -c "%MOSQUITTO_DIR%\mosquitto.conf"
        timeout /t 2 /nobreak >nul
        netstat -ano | findstr "0.0.0.0:1883" | findstr LISTENING >nul 2>&1
        if !errorlevel! equ 0 (
            echo   Mosquitto gestartet auf Port 1883
        ) else (
            echo   WARNUNG: Mosquitto konnte nicht gestartet werden!
        )
    ) else (
        echo   Mosquitto nicht installiert - MQTT uebersprungen
    )
)

:: ====== 3. MongoDB pruefen ======
echo.
echo  [3/8] MongoDB pruefen...
sc query MongoDB | findstr "RUNNING" >nul 2>&1
if !errorlevel! neq 0 (
    echo   MongoDB starten...
    net start MongoDB
    timeout /t 3 /nobreak >nul
) else (
    echo   MongoDB laeuft bereits
)

:: ====== 3. Datenbank-Backup ======
echo.
echo  [4/8] Sicherheits-Backup der Datenbank...
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"
set "TIMESTAMP=%date:~6,4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "TIMESTAMP=!TIMESTAMP: =0!"
where mongodump >nul 2>&1
if !errorlevel! equ 0 (
    mongodump --uri="mongodb://localhost:27017" --db=eventenergie --archive="%BACKUP_DIR%\startup_backup_!TIMESTAMP!.gz" --gzip >nul 2>&1
    if !errorlevel! equ 0 (
        echo   DB-Backup erstellt: startup_backup_!TIMESTAMP!.gz
    ) else (
        echo   WARNUNG: DB-Backup fehlgeschlagen
    )
) else (
    echo   mongodump nicht gefunden - Backup uebersprungen
)
:: Alte Startup-Backups aufraeumen (max 5)
set count=0
for /f "delims=" %%f in ('dir /b /o-d "%BACKUP_DIR%\startup_backup_*" 2^>nul') do (
    set /a count+=1
    if !count! gtr 5 del "%BACKUP_DIR%\%%f" >nul 2>&1
)

:: ====== 4. Python pruefen ======
echo.
echo  [5/8] Python-Umgebung pruefen...
cd /d "%BACKEND_DIR%"
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo   Python venv aktiviert
) else (
    echo   System-Python wird genutzt
)

:: ====== 5. Frontend Build pruefen ======
echo.
echo  [6/8] Frontend Build pruefen...
cd /d "%FRONTEND_DIR%"
if not exist "build" (
    echo   Kein Build vorhanden - erstelle Build...
    call npm run build
) else (
    echo   Build vorhanden
)

:: ====== 6. Backend starten (Port 8002) ======
echo.
echo  [7/8] Backend starten auf Port 8002...
cd /d "%BACKEND_DIR%"
if exist "venv\Scripts\activate.bat" (
    start "Eventenergie Backend" cmd /k "cd /d %BACKEND_DIR% && call venv\Scripts\activate.bat && python -m uvicorn server:app --host 0.0.0.0 --port 8002"
) else (
    start "Eventenergie Backend" cmd /k "cd /d %BACKEND_DIR% && python -m uvicorn server:app --host 0.0.0.0 --port 8002"
)

:: Warten und pruefen ob Backend tatsaechlich laeuft
echo   Warte auf Backend-Start...
set "BACKEND_OK=0"
for /l %%i in (1,1,10) do (
    if !BACKEND_OK! equ 0 (
        timeout /t 2 /nobreak >nul
        netstat -ano | findstr "0.0.0.0:8002" | findstr LISTENING >nul 2>&1
        if !errorlevel! equ 0 (
            set "BACKEND_OK=1"
            echo   Backend laeuft auf Port 8002
        )
    )
)
if !BACKEND_OK! equ 0 (
    echo   WARNUNG: Backend antwortet nicht auf Port 8002!
    echo   Pruefe das offene "Eventenergie Backend" Fenster fuer Fehlermeldungen.
)

:: ====== 7. Caddy starten (Port 8001) ======
echo.
echo  [8/8] Caddy starten (HTTPS)...
cd /d "%PORTAL_DIR%"

:: SSL-Ordner pruefen
if not exist "%PORTAL_DIR%\ssl" (
    echo   WARNUNG: SSL-Ordner nicht gefunden!
    echo   Bitte SSL-Zertifikat und Key nach %PORTAL_DIR%\ssl\ kopieren:
    echo     eventenergie.app.cer
    echo     eventenergie.app.key
)
cd /d "%PORTAL_DIR%"

:: Caddyfile erstellen falls nicht vorhanden
if not exist "%PORTAL_DIR%\Caddyfile" (
    echo   Caddyfile wird erstellt...
    >"%PORTAL_DIR%\Caddyfile" (
        echo eventenergie.app {
        echo     tls C:\eventenergie\ssl\eventenergie.app.cer C:\eventenergie\ssl\eventenergie.app.key
        echo     handle /api/* {
        echo         reverse_proxy localhost:8002
        echo     }
        echo     handle {
        echo         root * C:\eventenergie\frontend\build
        echo         try_files {path} /index.html
        echo         file_server
        echo     }
        echo }
    )
)

if exist "%PORTAL_DIR%\caddy.exe" (
    start "Eventenergie Caddy" cmd /k "cd /d %PORTAL_DIR% && caddy.exe run --config Caddyfile"
) else (
    echo   FEHLER: caddy.exe nicht gefunden in %PORTAL_DIR%
    echo   Bitte caddy.exe herunterladen: https://caddyserver.com/download
    goto :fertig
)

:: Warten und pruefen ob Caddy tatsaechlich laeuft
echo   Warte auf Caddy-Start...
set "CADDY_OK=0"
for /l %%i in (1,1,8) do (
    if !CADDY_OK! equ 0 (
        timeout /t 2 /nobreak >nul
        netstat -ano | findstr "0.0.0.0:443" | findstr LISTENING >nul 2>&1
        if !errorlevel! equ 0 (
            set "CADDY_OK=1"
            echo   Caddy laeuft auf Port 443 (HTTPS)
        )
    )
)
if !CADDY_OK! equ 0 (
    echo   WARNUNG: Caddy antwortet nicht auf Port 443!
    echo   Pruefe das offene "Eventenergie Caddy" Fenster fuer Fehlermeldungen.
)

:: ====== Zusammenfassung ======
:fertig
echo.
echo  ==================================================
if !BACKEND_OK! equ 1 if !CADDY_OK! equ 1 (
    echo   Portal erfolgreich gestartet!
) else (
    echo   WARNUNG: Nicht alle Dienste gestartet!
)
echo  ==================================================
echo.
echo   Backend:  http://localhost:8002  (intern)
echo   Caddy:    https://eventenergie.app (HTTPS, Port 443)
echo   MQTT:     Port 1883 (extern), Port 1884 (lokal)
echo   Portal:   https://eventenergie.app
echo.
if !BACKEND_OK! equ 0 echo   [!] Backend NICHT gestartet - siehe "Eventenergie Backend" Fenster
if !CADDY_OK! equ 0 echo   [!] Caddy NICHT gestartet - siehe "Eventenergie Caddy" Fenster
echo.
echo   Stoppen:  stop-all.bat
echo   Logs:     %LOG_DIR%\
echo.
if /i not "%~1"=="nopause" pause
