@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
:: =====================================================
:: Eventenergie Portal - Alle Dienste stoppen
:: =====================================================
:: Parameter: nopause - Ueberspringe pause am Ende
:: =====================================================

echo.
echo  Eventenergie Portal wird gestoppt...
echo.

:: Backend stoppen
echo  Backend stoppen...
taskkill /FI "WINDOWTITLE eq Eventenergie Backend" /F >nul 2>&1
call :kill_port 8002
echo   Backend gestoppt.

:: Caddy stoppen (HTTP + Admin-Port)
echo  Caddy stoppen...
taskkill /FI "WINDOWTITLE eq Eventenergie Caddy" /F >nul 2>&1
taskkill /IM caddy.exe /F >nul 2>&1
call :kill_port 8001
call :kill_port 2019
echo   Caddy gestoppt.

:: nginx stoppen
echo  nginx stoppen...
taskkill /IM nginx.exe /F >nul 2>&1
call :kill_port 443
echo   nginx gestoppt.

:: Mosquitto MQTT stoppen
echo  Mosquitto stoppen...
taskkill /FI "WINDOWTITLE eq Eventenergie MQTT" /F >nul 2>&1
taskkill /IM mosquitto.exe /F >nul 2>&1
echo   Mosquitto gestoppt.

:: Ollama KI stoppen
echo  Ollama stoppen...
taskkill /FI "WINDOWTITLE eq Eventenergie Ollama" /F >nul 2>&1
taskkill /IM ollama.exe /F >nul 2>&1
taskkill /IM "ollama app.exe" /F >nul 2>&1
call :kill_port 11434
echo   Ollama gestoppt.

:: Alte Frontend-Fenster (Fallback)
taskkill /FI "WINDOWTITLE eq Eventenergie Frontend" /F >nul 2>&1

:: PM2 (falls installiert)
where pm2 >nul 2>&1
if !errorlevel! equ 0 (
    pm2 stop all >nul 2>&1
    echo  PM2 Prozesse gestoppt.
)

:: Warten bis Ports wirklich frei sind
timeout /t 3 /nobreak >nul

echo.
echo  Alle Dienste gestoppt.
echo.
if /i not "%~1"=="nopause" pause
goto :eof

:: ============================================
::  Subroutine: Port beenden (locale-unabhaengig)
::  Funktioniert auf DE + EN Windows
:: ============================================
:kill_port
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%~1 " 2^>nul') do (
    if %%a GTR 100 taskkill /PID %%a /F >nul 2>&1
)
exit /b 0
