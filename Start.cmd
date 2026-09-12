@echo off
REM Duenner Wrapper: startet Backrec fensterlos. Keine Logik hier.
setlocal
cd /d "%~dp0"
chcp 65001 >nul
title Backrec starten
set PYTHONUTF8=1

if not exist ".venv\Scripts\backrec.exe" (
    echo Was ist passiert: Backrec ist noch nicht eingerichtet.
    echo Was tun: Setup.cmd in diesem Ordner doppelklicken.
    set EXITCODE=1
    goto :ende
)

".venv\Scripts\backrec.exe" start
set EXITCODE=%ERRORLEVEL%

:ende
REM Bei Erfolg schliesst sich dieses Fenster, auch beim Doppelklick: Backrec
REM meldet sich mit seinem eigenen Fenster, und eine Konsole daneben sieht nach
REM einem offenen Punkt aus.
if "%EXITCODE%"=="0" goto :raus
echo.
pause
:raus
endlocal & exit /b %EXITCODE%
