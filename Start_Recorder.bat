@echo off
REM Abgeloest. Diese Datei startet nichts mehr und nennt nur den neuen Weg.
REM Sie bleibt stehen, weil eine alte Verknuepfung auf dem Desktop sonst nur
REM "Datei nicht gefunden" sagen wuerde (design D11).
setlocal
title Backrec
echo.
echo Diese Datei wird nicht mehr benutzt.
echo.
echo Zum Einrichten:  Setup.cmd in diesem Ordner doppelklicken.
echo Zum Starten:     Start.cmd in diesem Ordner doppelklicken
echo                  oder das Symbol Backrec auf dem Desktop anklicken.
echo.
pause
endlocal & exit /b 1
