@echo off
chcp 65001 >nul
:: =====================================================
:: Eventenergie Portal - Dienste starten
:: =====================================================
:: Startet Backend und Frontend in separaten Fenstern.
:: Alternativ: PM2 verwenden (empfohlen fuer Produktion)
:: =====================================================

set "PORTAL_DIR=C:\eventenergie"
set "BACKEND_DIR=%PORTAL_DIR%\backend"
set "FRONTEND_DIR=%PORTAL_DIR%\frontend"

echo.
echo  Eventenergie Portal starten...
echo.

:: Backend starten (neues Fenster)
echo  Starte Backend (Port 8001)...
start "Eventenergie Backend" cmd /k "cd /d %BACKEND_DIR% && call venv\Scripts\activate.bat && python -m uvicorn server:app --host 0.0.0.0 --port 8001 --reload"

:: Kurz warten damit Backend hochfaehrt
timeout /t 5 /nobreak >nul

:: Frontend starten (neues Fenster)
echo  Starte Frontend (Port 3000)...
start "Eventenergie Frontend" cmd /k "cd /d %FRONTEND_DIR% && set PORT=3000 && npm start"

echo.
echo  Dienste gestartet!
echo  Backend:  http://localhost:8001
echo  Frontend: http://localhost:3000
echo.
echo  Fenster nicht schliessen!
echo.
pause
