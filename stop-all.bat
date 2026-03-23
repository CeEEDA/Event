@echo off
chcp 65001 >nul
:: =====================================================
:: Eventenergie Portal - Alle Dienste stoppen
:: =====================================================
:: Parameter: nopause - Ueberspring pause am Ende
::   Beispiel: stop-all.bat nopause
:: =====================================================

echo.
echo  Eventenergie Portal wird gestoppt...
echo.

:: Backend stoppen
echo  Backend stoppen...
taskkill /FI "WINDOWTITLE eq Eventenergie Backend" /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "0.0.0.0:8002" ^| findstr LISTENING 2^>nul') do (
    if %%a GTR 100 taskkill /PID %%a /F >nul 2>&1
)
echo   Backend gestoppt.

:: Caddy stoppen
echo  Caddy stoppen...
taskkill /FI "WINDOWTITLE eq Eventenergie Caddy" /F >nul 2>&1
taskkill /IM caddy.exe /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "0.0.0.0:8001" ^| findstr LISTENING 2^>nul') do (
    if %%a GTR 100 taskkill /PID %%a /F >nul 2>&1
)
echo   Caddy gestoppt.

:: nginx stoppen
echo  nginx stoppen...
taskkill /IM nginx.exe /F >nul 2>&1
echo   nginx gestoppt.

:: Mosquitto MQTT stoppen
echo  Mosquitto stoppen...
taskkill /FI "WINDOWTITLE eq Eventenergie MQTT" /F >nul 2>&1
taskkill /IM mosquitto.exe /F >nul 2>&1
echo   Mosquitto gestoppt.

:: Alte Frontend-Fenster (Fallback)
taskkill /FI "WINDOWTITLE eq Eventenergie Frontend" /F >nul 2>&1

:: PM2 (falls installiert)
where pm2 >nul 2>&1
if %errorlevel% equ 0 (
    pm2 stop all >nul 2>&1
    echo  PM2 Prozesse gestoppt.
)

:: Warten bis Ports wirklich frei sind
timeout /t 3 /nobreak >nul

echo.
echo  Alle Dienste gestoppt.
echo.
if /i not "%~1"=="nopause" pause
