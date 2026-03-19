@echo off
chcp 65001 >nul
echo ========================================
echo  Eventenergie Portal wird gestartet...
echo ========================================
echo.

echo [1/4] MongoDB pruefen...
sc query MongoDB | findstr "RUNNING" >nul 2>&1
if %errorlevel% neq 0 (
    echo   MongoDB starten...
    net start MongoDB
    timeout /t 3 /nobreak >nul
) else (
    echo   MongoDB laeuft bereits
)

echo.
echo [2/4] Frontend Build pruefen...
cd /d C:\eventenergie\frontend
if not exist "build" (
    echo   Kein Build vorhanden - erstelle Build...
    call npm run build
) else (
    :: Pruefen ob src neuer als build ist
    for /f %%a in ('dir /b /o-d src\*.js src\pages\*.js 2^>nul ^| head -1') do set "NEWEST_SRC=%%a"
    echo   Build vorhanden. Bei Aenderungen: npm run build ausfuehren
)

echo.
echo [3/4] Backend starten (Port 8001)...
start "Eventenergie Backend" cmd /c "cd /d C:\eventenergie\backend && python -m uvicorn server:app --host 0.0.0.0 --port 8001"
timeout /t 3 /nobreak >nul

echo.
echo [4/4] Frontend starten (Port 3000)...
start "Eventenergie Frontend" cmd /c "cd /d C:\eventenergie\frontend && npx serve -s build -l 3000"

echo.
echo ========================================
echo  Portal gestartet!
echo  Backend:  http://localhost:8001
echo  Frontend: http://localhost:3000
echo  Portal:   http://portal.eventenergie.com
echo ========================================
echo.
echo  TIPP: Nach Code-Updates immer zuerst:
echo    cd C:\eventenergie\frontend
echo    npm run build
echo  ausfuehren, damit Aenderungen sichtbar werden!
echo.
pause
