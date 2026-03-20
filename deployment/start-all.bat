@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: =====================================================
:: Eventenergie Portal - Start (Deployment Version)
:: =====================================================
:: Identisch mit dem Hauptordner start-all.bat
:: Startet MongoDB, Backend (uvicorn), Caddy (Reverse Proxy)
:: Fuehrt beim Start zuerst ein Datenbank-Backup durch
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

:: ====== Laufende Dienste stoppen ======
echo  [1/7] Laufende Dienste stoppen...
taskkill /FI "WINDOWTITLE eq Eventenergie Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Eventenergie Caddy*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Eventenergie Frontend*" /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)
echo   Alte Prozesse beendet.

:: ====== MongoDB pruefen ======
echo.
echo  [2/7] MongoDB pruefen...
sc query MongoDB | findstr "RUNNING" >nul 2>&1
if %errorlevel% neq 0 (
    echo   MongoDB starten...
    net start MongoDB
    timeout /t 3 /nobreak >nul
) else (
    echo   MongoDB laeuft bereits
)

:: ====== Datenbank-Backup vor Start ======
echo.
echo  [3/7] Sicherheits-Backup der Datenbank...
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

set "TIMESTAMP=%date:~6,4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"

where mongodump >nul 2>&1
if %errorlevel% equ 0 (
    mongodump --uri="mongodb://localhost:27017" --db=eventenergie --archive="%BACKUP_DIR%\startup_backup_%TIMESTAMP%.gz" --gzip >nul 2>&1
    if %errorlevel% equ 0 (
        echo   DB-Backup erstellt: startup_backup_%TIMESTAMP%.gz
    ) else (
        echo   WARNUNG: DB-Backup fehlgeschlagen
    )
) else (
    echo   WARNUNG: mongodump nicht gefunden - Backup uebersprungen
)

:: Alte Startup-Backups aufraeumen (nur die letzten 5 behalten)
set count=0
for /f "delims=" %%f in ('dir /b /o-d "%BACKUP_DIR%\startup_backup_*" 2^>nul') do (
    set /a count+=1
    if !count! gtr 5 (
        del "%BACKUP_DIR%\%%f" >nul 2>&1
    )
)

:: ====== Python venv aktivieren ======
echo.
echo  [4/7] Python-Umgebung pruefen...
cd /d "%BACKEND_DIR%"
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo   Python venv aktiviert
) else (
    echo   Kein venv gefunden - nutze System-Python
)

:: ====== Frontend Build pruefen ======
echo.
echo  [5/7] Frontend Build pruefen...
cd /d "%FRONTEND_DIR%"
if not exist "build" (
    echo   Kein Build vorhanden - erstelle Build...
    call npm run build
) else (
    echo   Build vorhanden
)

:: ====== Backend starten ======
echo.
echo  [6/7] Backend starten (Port 8001)...
cd /d "%BACKEND_DIR%"
if exist "venv\Scripts\activate.bat" (
    start "Eventenergie Backend" cmd /c "cd /d %BACKEND_DIR% && call venv\Scripts\activate.bat && python -m uvicorn server:app --host 0.0.0.0 --port 8001"
) else (
    start "Eventenergie Backend" cmd /c "cd /d %BACKEND_DIR% && python -m uvicorn server:app --host 0.0.0.0 --port 8001"
)
timeout /t 3 /nobreak >nul
echo   Backend gestartet

:: ====== Caddy starten ======
echo.
echo  [7/7] Caddy starten (Reverse Proxy auf Port 3000)...
if exist "%PORTAL_DIR%\caddy.exe" (
    start "Eventenergie Caddy" cmd /c "cd /d %PORTAL_DIR% && caddy.exe run --config Caddyfile"
    echo   Caddy gestartet
) else (
    where caddy >nul 2>&1
    if %errorlevel% equ 0 (
        start "Eventenergie Caddy" cmd /c "cd /d %PORTAL_DIR% && caddy run --config Caddyfile"
        echo   Caddy gestartet
    ) else (
        echo   FEHLER: Caddy nicht gefunden!
        echo   Fallback: npx serve
        start "Eventenergie Frontend" cmd /c "cd /d %FRONTEND_DIR% && npx serve -s build -l 3000"
    )
)

echo.
echo  ==================================================
echo   Portal erfolgreich gestartet!
echo  ==================================================
echo.
echo   Backend:    http://localhost:8001
echo   Caddy:      http://localhost:3000
echo   Portal:     https://portal.eventenergie.com
echo.
pause
