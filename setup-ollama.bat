@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
:: =====================================================
:: Eventenergie Portal - Ollama (KI) Setup
:: =====================================================
:: Laedt das konfigurierte Modell, setzt CPU-Limits und
:: startet Ollama einmalig als Warmlauf.
:: Ideal nach frischer Ollama-Installation oder Modellwechsel.
:: =====================================================

set "LIVE_DIR=C:\eventenergie"
set "OLLAMA_EXE=C:\Users\Administrator\AppData\Local\Programs\Ollama\ollama.exe"
set "OLLAMA_MODEL=gemma3:1b"

:: Modell aus .env lesen falls vorhanden
if exist "%LIVE_DIR%\backend\.env" (
    for /f "tokens=1,* delims==" %%a in ('findstr /b "OLLAMA_MODEL=" "%LIVE_DIR%\backend\.env"') do set "OLLAMA_MODEL=%%b"
)

echo.
echo  ==================================================
echo   Eventenergie Portal - Ollama Setup
echo   Modell: %OLLAMA_MODEL%
echo  ==================================================
echo.

if not exist "%OLLAMA_EXE%" (
    echo   FEHLER: Ollama nicht installiert.
    echo   Download: https://ollama.com/download/OllamaSetup.exe
    pause
    exit /b 1
)

:: ====== CPU-Limits dauerhaft setzen ======
echo  [1/3] CPU-Limits setzen (Umgebungsvariablen)...
setx OLLAMA_HOST "127.0.0.1:11434" >nul
setx OLLAMA_NUM_PARALLEL "1" >nul
setx OLLAMA_MAX_LOADED_MODELS "1" >nul
setx OLLAMA_KEEP_ALIVE "5m" >nul
setx OLLAMA_NUM_THREADS "2" >nul
echo   OK (greifen nach Ollama-Neustart)

:: ====== Ollama stoppen ======
echo.
echo  [2/3] Ollama vorbereiten...
taskkill /IM ollama.exe /F >nul 2>&1
taskkill /IM "ollama app.exe" /F >nul 2>&1
timeout /t 2 /nobreak >nul

:: Mit Limits starten fuer das Pull + Warmup
set "OLLAMA_HOST=127.0.0.1:11434"
set "OLLAMA_NUM_PARALLEL=1"
set "OLLAMA_MAX_LOADED_MODELS=1"
set "OLLAMA_KEEP_ALIVE=5m"
set "OLLAMA_NUM_THREADS=2"
start "Eventenergie Ollama" /min /belownormal "%OLLAMA_EXE%" serve
timeout /t 5 /nobreak >nul

:: ====== Modell pullen ======
echo.
echo  [3/3] Modell pruefen / herunterladen: %OLLAMA_MODEL%
"%OLLAMA_EXE%" pull %OLLAMA_MODEL%
if !errorlevel! neq 0 (
    echo   WARNUNG: Modell-Pull fehlgeschlagen. Pruefe Internet / Proxy.
)
echo.
echo   Verfuegbare Modelle:
"%OLLAMA_EXE%" list

echo.
echo  ==================================================
echo   Setup abgeschlossen.
echo   Ollama laeuft unter http://127.0.0.1:11434
echo  ==================================================
echo.
pause
