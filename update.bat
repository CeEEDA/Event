@echo off
:: =====================================================================
:: Eventenergie Portal - Update-Wrapper (delegiert an PowerShell)
:: =====================================================================
:: Die eigentliche Logik liegt in update-live.ps1 (NSSM-Service-basiert)
:: Diese .bat ist nur ein Kompatibilitaets-Wrapper fuer Doppelklick.
:: =====================================================================

set "SCRIPT_DIR=%~dp0"
set "PS1=%SCRIPT_DIR%update-live.ps1"

if not exist "%PS1%" (
    echo FEHLER: update-live.ps1 nicht gefunden neben dieser update.bat!
    echo Pfad: %PS1%
    pause
    exit /b 1
)

echo.
echo  ==================================================
echo   Eventenergie Portal - Live-Update
echo  ==================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*
exit /b %errorlevel%
