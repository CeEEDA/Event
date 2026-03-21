@echo off
chcp 65001 >nul
:: =====================================================
:: Eventenergie Portal - Alle Dienste stoppen
:: =====================================================
:: HINWEIS: Bitte bevorzugt stop-all.bat verwenden!
:: Dieses Script ist ein Alias fuer stop-all.bat
:: =====================================================

set "PORTAL_DIR=C:\eventenergie"

echo.
echo  Weiterleitung an stop-all.bat...
echo.

if exist "%PORTAL_DIR%\stop-all.bat" (
    call "%PORTAL_DIR%\stop-all.bat" %1
) else (
    echo  stop-all.bat nicht gefunden!
    
    :: Fallback
    taskkill /FI "WINDOWTITLE eq Eventenergie Backend" /F >nul 2>&1
    taskkill /FI "WINDOWTITLE eq Eventenergie Caddy" /F >nul 2>&1
    taskkill /IM caddy.exe /F >nul 2>&1
    
    echo  Dienste gestoppt.
    if /i not "%~1"=="nopause" pause
)
