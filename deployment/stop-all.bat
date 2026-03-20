@echo off
chcp 65001 >nul
:: =====================================================
:: Eventenergie Portal - Alle Dienste stoppen
:: =====================================================

echo.
echo  Eventenergie Portal wird gestoppt...
echo.

:: Backend stoppen
echo  Backend stoppen...
taskkill /FI "WINDOWTITLE eq Eventenergie Backend*" /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)
echo   Backend gestoppt.

:: Caddy stoppen
echo  Caddy stoppen...
taskkill /FI "WINDOWTITLE eq Eventenergie Caddy*" /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)
echo   Caddy gestoppt.

:: Alte Frontend-Fenster (Fallback)
taskkill /FI "WINDOWTITLE eq Eventenergie Frontend*" /F >nul 2>&1

:: PM2 (falls installiert)
where pm2 >nul 2>&1
if %errorlevel% equ 0 (
    pm2 stop all >nul 2>&1
    echo  PM2 Prozesse gestoppt.
)

echo.
echo  Alle Dienste gestoppt.
echo.
pause
