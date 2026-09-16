@echo off
REM A thin wrapper. No logic belongs in this file.
setlocal
cd /d "%~dp0"
chcp 65001 >nul
title Backrec einrichten
cls
set PYTHONUTF8=1

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\win\bootstrap-uv.ps1"
if errorlevel 1 goto :ende

REM The preparation script has just built the working environment -- it has to,
REM because the command below already runs inside it. With this hint step 2 of
REM the assistant does not build it a second time.
set BACKREC_ENV_READY=1

uv run --no-sync backrec setup %*

:ende
set EXITCODE=%ERRORLEVEL%
REM On a double click the window stays open so the summary can be read; invoked
REM with arguments it stays only on a failure.
if not "%~1"=="" if "%EXITCODE%"=="0" goto :raus
echo.
pause
:raus
endlocal & exit /b %EXITCODE%
