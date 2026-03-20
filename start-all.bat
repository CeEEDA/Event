@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: =====================================================
:: Eventenergie Portal - Start
:: =====================================================
:: Startet MongoDB, Backend, Caddy (Reverse Proxy)
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
        echo   WARNUNG: DB-Backup fehlgeschlagen (wird beim naechsten Start erneut versucht)
    )
) else (
    echo   WARNUNG: mongodump nicht gefunden - Backup uebersprungen
    echo   Installation: https://www.mongodb.com/try/download/database-tools
)

:: Alte Startup-Backups aufraeumen (nur die letzten 5 behalten)
echo   Alte Startup-Backups aufraeumen...
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
    if %errorlevel% neq 0 (
        echo   FEHLER: Build fehlgeschlagen!
        echo   Bitte manuell ausfuehren: cd %FRONTEND_DIR% ^&^& npm run build
    ) else (
        echo   Build erfolgreich erstellt
    )
) else (
    echo   Build vorhanden
)

:: ====== Backend starten ======
echo.
echo  [6/7] Backend starten (Port 8002, intern)...
cd /d "%BACKEND_DIR%"
if exist "venv\Scripts\activate.bat" (
    start "Eventenergie Backend" cmd /c "cd /d %BACKEND_DIR% && call venv\Scripts\activate.bat && python -m uvicorn server:app --host 0.0.0.0 --port 8002"
) else (
    start "Eventenergie Backend" cmd /c "cd /d %BACKEND_DIR% && python -m uvicorn server:app --host 0.0.0.0 --port 8002"
)
timeout /t 3 /nobreak >nul
echo   Backend gestartet

:: ====== Caddy starten ======
echo.
echo  [7/7] Caddy starten (Port 8001, extern erreichbar)...
if exist "%PORTAL_DIR%\caddy.exe" (
    start "Eventenergie Caddy" cmd /c "cd /d %PORTAL_DIR% && caddy.exe run --config Caddyfile"
    echo   Caddy gestartet
) else (
    where caddy >nul 2>&1
    if !errorlevel! equ 0 (
        start "Eventenergie Caddy" cmd /c "cd /d %PORTAL_DIR% && caddy run --config Caddyfile"
        echo   Caddy gestartet
    ) else (
        echo   FEHLER: Caddy nicht gefunden!
        echo   Bitte caddy.exe herunterladen: https://caddyserver.com/download
        echo   Und nach %PORTAL_DIR%\caddy.exe kopieren
    )
)

:: ====== Fertig ======
echo.
echo  ==================================================
echo   Portal erfolgreich gestartet!
echo  ==================================================
echo.
echo   Backend:    http://localhost:8002  (intern)
echo   Caddy:      http://localhost:8001  (Frontend + API)
echo   Portal:     http://portal.eventenergie.com:8001
echo.
echo   Caddy leitet automatisch weiter:
echo     /api/*  -^> Backend (Port 8002)
echo     /*      -^> Frontend (Build-Ordner)
echo.
echo   DB-Backup:  %BACKUP_DIR%\
echo.
echo   Stoppen:    stop-all.bat ausfuehren
echo.
pause
