@echo off
REM Duenner Wrapper: Bootstrap, dann das Control-Surface. Keine Logik hier.
setlocal
cd /d "%~dp0"
chcp 65001 >nul
title Backrec einrichten
cls
set PYTHONUTF8=1

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\win\bootstrap-uv.ps1"
if errorlevel 1 goto :ende

REM Das Vorbereitungsskript hat die Arbeitsumgebung gerade gebaut -- es muss das,
REM denn der Aufruf darunter laeuft schon darin. Schritt 2 des Assistenten baut
REM sie mit diesem Hinweis nicht ein zweites Mal auf.
set BACKREC_ENV_READY=1

uv run --no-sync backrec setup %*

:ende
set EXITCODE=%ERRORLEVEL%
REM Beim Doppelklick bleibt das Fenster stehen, damit die Zusammenfassung lesbar
REM ist; mit Argumenten aufgerufen nur im Fehlerfall.
if not "%~1"=="" if "%EXITCODE%"=="0" goto :raus
echo.
pause
:raus
endlocal & exit /b %EXITCODE%
