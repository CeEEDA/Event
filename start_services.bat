@echo off
chcp 65001 >nul
:: =====================================================
:: Eventenergie Portal - Dienste starten
:: =====================================================
:: HINWEIS: Bitte bevorzugt start-all.bat verwenden!
:: Dieses Script ist ein Alias fuer start-all.bat
:: =====================================================

set "PORTAL_DIR=C:\eventenergie"

echo.
echo  Weiterleitung an start-all.bat...
echo.

if exist "%PORTAL_DIR%\start-all.bat" (
    call "%PORTAL_DIR%\start-all.bat" %1
) else (
    echo  start-all.bat nicht gefunden!
    echo  Starte manuell...
    
    :: MongoDB
    sc query MongoDB | findstr "RUNNING" >nul 2>&1
    if %errorlevel% neq 0 (
        net start MongoDB
        timeout /t 3 /nobreak >nul
    )
    
    :: Backend
    start "Eventenergie Backend" cmd /k "cd /d %PORTAL_DIR%\backend && python -m uvicorn server:app --host 0.0.0.0 --port 8002"
    timeout /t 4 /nobreak >nul
    
    :: Caddy
    if exist "%PORTAL_DIR%\caddy.exe" (
        start "Eventenergie Caddy" cmd /k "cd /d %PORTAL_DIR% && caddy.exe run --config Caddyfile"
    )
    
    echo  Dienste gestartet.
    if /i not "%~1"=="nopause" pause
)
