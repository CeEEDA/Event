@echo off
chcp 65001 >nul
echo ========================================
echo  Eventenergie Portal wird gestartet...
echo ========================================
echo.

echo [1/5] MongoDB pruefen...
sc query MongoDB | findstr "RUNNING" >nul 2>&1
if %errorlevel% neq 0 (
    echo   MongoDB starten...
    net start MongoDB
    timeout /t 3 /nobreak >nul
) else (
    echo   MongoDB laeuft bereits
)

echo.
echo [2/5] Frontend Build pruefen...
cd /d C:\eventenergie\frontend
if not exist "build" (
    echo   Kein Build vorhanden - erstelle Build...
    call npm run build
) else (
    echo   Build vorhanden. Bei Aenderungen: npm run build ausfuehren
)

echo.
echo [3/5] Caddy pruefen...
where caddy >nul 2>&1
if %errorlevel% neq 0 (
    if exist "C:\eventenergie\caddy.exe" (
        echo   Caddy gefunden in C:\eventenergie\caddy.exe
    ) else (
        echo   FEHLER: Caddy nicht gefunden!
        echo   Bitte caddy.exe herunterladen von: https://caddyserver.com/download
        echo   Datei nach C:\eventenergie\caddy.exe verschieben
        echo.
        echo   Oder per PowerShell:
        echo   Invoke-WebRequest -Uri "https://caddyserver.com/api/download?os=windows&arch=amd64" -OutFile "C:\eventenergie\caddy.exe"
        echo.
        pause
        exit /b 1
    )
)

echo.
echo [4/5] Backend starten (Port 8001)...
start "Eventenergie Backend" cmd /c "cd /d C:\eventenergie\backend && python -m uvicorn server:app --host 0.0.0.0 --port 8001"
timeout /t 3 /nobreak >nul

echo.
echo [5/5] Caddy starten (Port 3000 - Frontend + API Proxy)...
:: Caddy ersetzt npx serve: liefert Frontend aus UND leitet /api an Backend weiter
if exist "C:\eventenergie\caddy.exe" (
    start "Eventenergie Caddy" cmd /c "cd /d C:\eventenergie && caddy.exe run --config Caddyfile"
) else (
    start "Eventenergie Caddy" cmd /c "cd /d C:\eventenergie && caddy run --config Caddyfile"
)

echo.
echo ========================================
echo  Portal gestartet!
echo  Backend:  http://localhost:8001  (intern)
echo  Caddy:    http://localhost:3000  (Frontend + API Proxy)
echo  Portal:   https://portal.eventenergie.com
echo ========================================
echo.
echo  Caddy leitet automatisch weiter:
echo    /api/*  -^> Backend (Port 8001)
echo    /*      -^> Frontend (Build-Ordner)
echo.
echo  TIPP: Nach Code-Updates immer zuerst:
echo    cd C:\eventenergie\frontend
echo    npm run build
echo  ausfuehren, damit Aenderungen sichtbar werden!
echo.
pause
