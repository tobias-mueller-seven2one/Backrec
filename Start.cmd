@echo off
REM A thin wrapper. No logic belongs in this file.
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
REM On success this window closes, even on a double click: Backrec reports with
REM a window of its own, and a console beside it looks like an open issue.
if "%EXITCODE%"=="0" goto :raus
echo.
pause
:raus
endlocal & exit /b %EXITCODE%
