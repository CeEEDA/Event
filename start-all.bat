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

:: Ergebnis-Variablen initialisieren
set "BACKEND_OK=0"
set "CADDY_OK=0"
set "NGINX_OK=0"
set "MQTT_OK=0"

:: ====== 1. Laufende Dienste stoppen ======
echo  [1/8] Laufende Dienste stoppen...
taskkill /FI "WINDOWTITLE eq Eventenergie Backend" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Eventenergie Caddy" /F >nul 2>&1
taskkill /IM caddy.exe /F >nul 2>&1
taskkill /IM nginx.exe /F >nul 2>&1
call :kill_port 8001
call :kill_port 8002
call :kill_port 443
timeout /t 3 /nobreak >nul
echo   Alte Prozesse beendet.

:: ====== 2. Mosquitto MQTT Broker ======
echo.
echo  [2/8] Mosquitto MQTT Broker pruefen...
set "MOSQUITTO_DIR=C:\Program Files\Mosquitto"
call :check_port 1883
if !errorlevel! equ 0 (
    set "MQTT_OK=1"
    echo   Mosquitto laeuft bereits auf Port 1883
    goto :mqtt_done
)
if not exist "%MOSQUITTO_DIR%\mosquitto.exe" (
    echo   Mosquitto nicht installiert - MQTT uebersprungen
    set "MQTT_OK=2"
    goto :mqtt_done
)
taskkill /IM mosquitto.exe /F >nul 2>&1
timeout /t 1 /nobreak >nul
start "Eventenergie MQTT" /min "%MOSQUITTO_DIR%\mosquitto.exe" -c "%MOSQUITTO_DIR%\mosquitto.conf"
timeout /t 3 /nobreak >nul
call :check_port 1883
if !errorlevel! equ 0 (
    set "MQTT_OK=1"
    echo   Mosquitto gestartet auf Port 1883
) else (
    echo   WARNUNG: Mosquitto konnte nicht gestartet werden
)
:mqtt_done

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

:: ====== 4. Datenbank-Backup ======
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

:: ====== 5. Python venv ======
echo.
echo  [5/8] Python-Umgebung pruefen...
cd /d "%BACKEND_DIR%"
if exist "%PORTAL_DIR%\venv\Scripts\activate.bat" (
    call "%PORTAL_DIR%\venv\Scripts\activate.bat"
    echo   Python venv aktiviert (%PORTAL_DIR%\venv)
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo   Python venv aktiviert (backend\venv)
) else (
    echo   System-Python wird genutzt
)

:: ====== 6. Frontend Build ======
echo.
echo  [6/8] Frontend Build pruefen...
cd /d "%FRONTEND_DIR%"
if not exist "build" (
    echo   Kein Build vorhanden - erstelle Build...
    call npm run build
) else (
    echo   Build vorhanden
)

:: ====== 7. Backend starten (Port 8002) ======
echo.
echo  [7/8] Backend starten auf Port 8002...
cd /d "%BACKEND_DIR%"
if exist "%PORTAL_DIR%\venv\Scripts\activate.bat" (
    start "Eventenergie Backend" cmd /k "cd /d %BACKEND_DIR% && call %PORTAL_DIR%\venv\Scripts\activate.bat && python -m uvicorn server:app --host 0.0.0.0 --port 8002"
) else if exist "venv\Scripts\activate.bat" (
    start "Eventenergie Backend" cmd /k "cd /d %BACKEND_DIR% && call venv\Scripts\activate.bat && python -m uvicorn server:app --host 0.0.0.0 --port 8002"
) else (
    start "Eventenergie Backend" cmd /k "cd /d %BACKEND_DIR% && python -m uvicorn server:app --host 0.0.0.0 --port 8002"
)
echo   Warte auf Backend-Start (max 20s)...
set /a "_bw=0"
:wait_backend
if !_bw! geq 10 goto :backend_done
set /a "_bw+=1"
timeout /t 2 /nobreak >nul
call :check_port 8002
if !errorlevel! equ 0 (
    set "BACKEND_OK=1"
    echo   Backend laeuft auf Port 8002
    goto :backend_done
)
goto :wait_backend
:backend_done
if !BACKEND_OK! equ 0 (
    echo   WARNUNG: Backend antwortet nicht auf Port 8002
    echo   Pruefe das "Eventenergie Backend" Fenster fuer Fehlermeldungen.
)

:: ====== 8. Caddy + Nginx starten ======
echo.
echo  [8/8] Caddy (HTTP) + nginx (HTTPS) starten...
cd /d "%PORTAL_DIR%"

:: Caddyfile erstellen falls nicht vorhanden
if not exist "%PORTAL_DIR%\Caddyfile" (
    echo   Caddyfile wird erstellt...
    >"%PORTAL_DIR%\Caddyfile" (
        echo :8001 {
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

:: Caddy starten (HTTP Port 8001)
if not exist "%PORTAL_DIR%\caddy.exe" (
    echo   caddy.exe nicht gefunden - versuche Download...
    where curl >nul 2>&1
    if !errorlevel! equ 0 (
        curl -sL -o "%PORTAL_DIR%\caddy.exe" "https://caddyserver.com/api/download?os=windows&arch=amd64"
        if exist "%PORTAL_DIR%\caddy.exe" (
            echo   Caddy erfolgreich heruntergeladen
        ) else (
            echo   FEHLER: Caddy Download fehlgeschlagen
            echo   Bitte manuell herunterladen: https://caddyserver.com/download
            echo   caddy.exe nach %PORTAL_DIR% kopieren
            goto :skip_nginx
        )
    ) else (
        echo   FEHLER: curl nicht verfuegbar fuer Caddy-Download
        echo   Bitte caddy.exe manuell nach %PORTAL_DIR% kopieren
        echo   Download: https://caddyserver.com/download
        goto :skip_nginx
    )
)
start "Eventenergie Caddy" /min cmd /c "cd /d %PORTAL_DIR% && caddy.exe run --config Caddyfile"
echo   Warte auf Caddy-Start (max 12s)...
set /a "_cw=0"
:wait_caddy
if !_cw! geq 6 goto :caddy_done
set /a "_cw+=1"
timeout /t 2 /nobreak >nul
call :check_port 8001
if !errorlevel! equ 0 (
    set "CADDY_OK=1"
    echo   Caddy laeuft auf Port 8001 (HTTP)
    goto :caddy_done
)
goto :wait_caddy
:caddy_done
if !CADDY_OK! equ 0 (
    echo   WARNUNG: Caddy antwortet nicht auf Port 8001
)

:: Nginx starten (HTTPS Port 443)
if not exist "C:\nginx\nginx.exe" (
    echo   nginx nicht gefunden unter C:\nginx - nur HTTP verfuegbar
    goto :skip_nginx
)
copy /Y "%PORTAL_DIR%\nginx.conf" "C:\nginx\conf\nginx.conf" >nul 2>&1
taskkill /IM nginx.exe /F >nul 2>&1
timeout /t 1 /nobreak >nul
if not exist "C:\nginx\logs" mkdir "C:\nginx\logs"
cd /d "C:\nginx"
start "" nginx.exe
cd /d "%PORTAL_DIR%"
echo   Warte auf nginx-Start (max 8s)...
set /a "_nw=0"
:wait_nginx
if !_nw! geq 4 goto :nginx_done
set /a "_nw+=1"
timeout /t 2 /nobreak >nul
call :check_port 443
if !errorlevel! equ 0 (
    set "NGINX_OK=1"
    echo   nginx laeuft auf Port 443 (HTTPS)
    goto :nginx_done
)
goto :wait_nginx
:nginx_done
if !NGINX_OK! equ 0 (
    echo   WARNUNG: nginx antwortet nicht auf Port 443
    echo   Pruefe: C:\nginx\logs\error.log
)
:skip_nginx

:: ====== Zusammenfassung ======
echo.
echo  ==================================================
set /a "_ok=0"
set /a "_total=3"
if !BACKEND_OK! equ 1 set /a "_ok+=1"
if !CADDY_OK! equ 1 set /a "_ok+=1"
if !NGINX_OK! equ 1 set /a "_ok+=1"

if !_ok! equ !_total! (
    echo   Alle Dienste erfolgreich gestartet [!_ok!/!_total!]
) else (
    echo   Dienste-Status: !_ok!/!_total! gestartet
)
echo  ==================================================
echo.
if !BACKEND_OK! equ 1 (echo   [OK] Backend:    Port 8002) else (echo   [XX] Backend:    NICHT gestartet)
if !CADDY_OK! equ 1   (echo   [OK] Caddy:      Port 8001 HTTP) else (echo   [XX] Caddy:      NICHT gestartet)
if !NGINX_OK! equ 1   (echo   [OK] nginx:      Port 443 HTTPS) else (echo   [XX] nginx:      NICHT gestartet)
if !MQTT_OK! equ 1 echo   [OK] Mosquitto:  Port 1883
if !MQTT_OK! equ 2 echo   [--] Mosquitto:  nicht installiert
if !MQTT_OK! equ 0 echo   [XX] Mosquitto:  NICHT gestartet
echo.
echo   Portal:   https://eventenergie.app
echo   Lokal:    https://localhost
echo   Stoppen:  stop-all.bat
echo   Logs:     %LOG_DIR%\
echo.
if /i not "%~1"=="nopause" pause
goto :eof

:: ============================================
::  Subroutinen
:: ============================================

:check_port
:: Prueft ob ein Port gebunden ist (locale-unabhaengig)
:: Sucht nach 0.0.0.0:PORT statt nach "LISTENING" (deutsch: ABHOEREN)
:: Parameter: %1 = Portnummer
:: Return: errorlevel 0 = Port aktiv, 1 = nicht aktiv
set "_CP=1"
for /f "tokens=*" %%a in ('netstat -ano ^| findstr "0.0.0.0:%~1 " 2^>nul') do set "_CP=0"
exit /b !_CP!

:kill_port
:: Beendet Prozesse auf einem bestimmten Port
:: Parameter: %1 = Portnummer
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "0.0.0.0:%~1" 2^>nul') do (
    if %%a GTR 100 taskkill /PID %%a /F >nul 2>&1
)
exit /b 0
