@echo off
title Backrec

:: Wechselt in den Ordner, in dem diese .bat Datei liegt
cd /d "%~dp0"

echo ==========================================
echo Backrec wird gestartet...
echo ==========================================

:: 1. Prüfen ob .venv existiert, wenn nicht: erstellen
if not exist ".venv\Scripts\activate.bat" (
    echo [Info] Erstelle virtuelle Umgebung ^(.venv^) beim ersten Start...
    echo [Info] Das kann einen Moment dauern.
    python -m venv .venv
)

:: 2. .venv aktivieren
call .venv\Scripts\activate

:: 3. Sicherstellen, dass die Bibliotheken installiert sind
echo [Info] Pruefe Abhaengigkeiten...
pip install -r requirements.txt >nul 2>&1

:: 4. Python UI starten (start "" sorgt dafuer, dass die .bat nicht wartet)
:: pythonw sorgt dafuer, dass kein schwarzes Python-Fenster offen bleibt
echo [Info] Starte Recorder...
start "" pythonw main.pyw

:: 5. CMD-Fenster schließen
exit