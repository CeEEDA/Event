@echo off
:: ============================================================================
::  Eventenergie Portal - Windows Installer
::  Einfach doppelklicken zum Starten!
:: ============================================================================
echo.
echo ================================================
echo   Eventenergie Portal - Windows Installer
echo ================================================
echo.
echo Starte Installation...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0install-win.ps1"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [FEHLER] Installation fehlgeschlagen.
    echo Bitte starten Sie PowerShell als Administrator und fuehren Sie aus:
    echo   powershell -ExecutionPolicy Bypass -File install-win.ps1
    echo.
    pause
)
