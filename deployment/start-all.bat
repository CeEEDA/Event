@echo off
echo ========================================
echo  Eventenergie Portal wird gestartet...
echo ========================================
echo.

echo [1/3] MongoDB pruefen...
sc query MongoDB | findstr "RUNNING" >nul 2>&1
if %errorlevel% neq 0 (
    echo   MongoDB starten...
    net start MongoDB
    timeout /t 3 /nobreak >nul
) else (
    echo   MongoDB laeuft bereits
)

echo.
echo [2/3] Backend starten (Port 8001)...
start "Eventenergie Backend" cmd /c "cd /d C:\eventenergie\backend && python -m uvicorn server:app --host 0.0.0.0 --port 8001"
timeout /t 3 /nobreak >nul

echo.
echo [3/3] Frontend starten (Port 3000)...
start "Eventenergie Frontend" cmd /c "cd /d C:\eventenergie\frontend && npx serve -s build -l 3000"

echo.
echo ========================================
echo  Portal gestartet!
echo  Backend:  http://localhost:8001
echo  Frontend: http://localhost:3000
echo  Portal:   http://portal.eventenergie.com
echo ========================================
echo.
echo Dieses Fenster kann geschlossen werden.
pause
