@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: =====================================================
:: Eventenergie Portal - Start
:: =====================================================

set "PORTAL_DIR=C:\eventenergie"
set "BACKEND_DIR=%PORTAL_DIR%\backend"
set "FRONTEND_DIR=%PORTAL_DIR%\frontend"
set "BACKUP_DIR=%PORTAL_DIR%\backups\db"

echo.
echo  ==================================================
echo   Eventenergie Portal wird gestartet...
echo   %date% %time%
echo  ==================================================
echo.

:: ====== 1. Laufende Dienste stoppen ======
echo  [1/7] Laufende Dienste stoppen...
taskkill /FI "WINDOWTITLE eq Eventenergie*" /F >nul 2>&1
taskkill /IM caddy.exe /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING 2^>nul') do taskkill /PID %%a /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8002 ^| findstr LISTENING 2^>nul') do taskkill /PID %%a /F >nul 2>&1
timeout /t 2 /nobreak >nul
echo   Alte Prozesse beendet.

:: ====== 2. MongoDB pruefen ======
echo.
echo  [2/7] MongoDB pruefen...
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
echo  [3/7] Sicherheits-Backup der Datenbank...
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
echo  [4/7] Python-Umgebung pruefen...
cd /d "%BACKEND_DIR%"
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo   Python venv aktiviert
) else (
    echo   System-Python wird genutzt
)

:: ====== 5. Frontend Build pruefen ======
echo.
echo  [5/7] Frontend Build pruefen...
cd /d "%FRONTEND_DIR%"
if not exist "build" (
    echo   Kein Build vorhanden - erstelle Build...
    call npm run build
) else (
    echo   Build vorhanden
)

:: ====== 6. Backend starten (Port 8002) ======
echo.
echo  [6/7] Backend starten auf Port 8002...
cd /d "%BACKEND_DIR%"
if exist "venv\Scripts\activate.bat" (
    start "Eventenergie Backend" cmd /c "cd /d %BACKEND_DIR% && call venv\Scripts\activate.bat && python -m uvicorn server:app --host 0.0.0.0 --port 8002"
) else (
    start "Eventenergie Backend" cmd /c "cd /d %BACKEND_DIR% && python -m uvicorn server:app --host 0.0.0.0 --port 8002"
)
timeout /t 4 /nobreak >nul
echo   Backend gestartet

:: ====== 7. Caddy starten (Port 8001) ======
echo.
echo  [7/7] Caddy starten auf Port 8001...
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

if exist "%PORTAL_DIR%\caddy.exe" (
    start "Eventenergie Caddy" cmd /c "cd /d %PORTAL_DIR% && caddy.exe run --config Caddyfile"
    timeout /t 2 /nobreak >nul
    echo   Caddy gestartet
) else (
    echo   FEHLER: caddy.exe nicht gefunden in %PORTAL_DIR%
    echo   Bitte caddy.exe herunterladen: https://caddyserver.com/download
)

:: ====== Fertig ======
echo.
echo  ==================================================
echo   Portal erfolgreich gestartet!
echo  ==================================================
echo.
echo   Backend:  http://localhost:8002  (intern)
echo   Caddy:    http://localhost:8001  (extern)
echo   Portal:   http://portal.eventenergie.com:8001
echo.
echo   Stoppen:  stop-all.bat
echo.
pause
