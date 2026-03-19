@echo off
chcp 65001 >nul
:: =====================================================
:: Eventenergie Portal - Dienste stoppen
:: =====================================================

echo  Stoppe Eventenergie Portal...

:: PM2
where pm2 >nul 2>&1
if %errorlevel% equ 0 (
    pm2 stop all 2>nul
    echo  PM2 Prozesse gestoppt.
)

:: Fenster-Prozesse
taskkill /FI "WINDOWTITLE eq Eventenergie Backend*" /F 2>nul
taskkill /FI "WINDOWTITLE eq Eventenergie Frontend*" /F 2>nul

echo  Dienste gestoppt.
pause
