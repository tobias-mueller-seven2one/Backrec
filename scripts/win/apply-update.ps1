# Spiegelt eine gepruefte, entpackte neue Fassung ein, waehrend sich Backrec
# gerade beendet.
#
# Warum ausserhalb der Arbeitsumgebung: der Code, der aktualisiert, laeuft aus
# genau dem Ordner, der ersetzt werden soll. Windows haelt die geladene
# Programmdatei offen, solange der Prozess lebt -- ein Prozess kann weder seinen
# eigenen Ordner umbenennen noch sich selbst ueberschreiben und danach
# weiterlaufen. Den letzten Schritt macht deshalb jemand, der daneben steht.
# Windows PowerShell 5.1 liegt auf jedem Windows 11 und braucht weder die
# Arbeitsumgebung noch das Hilfsprogramm.
#
# Gespiegelt statt getauscht: die Arbeitsumgebung liegt im Ordner, gehoert nicht
# zum Archiv und soll nicht neu aufgebaut werden muessen; und der Pfad des
# Ordners steckt in der Verknuepfung auf dem Desktop.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [Parameter(Mandatory = $true)][string]$StagingPath,
    [Parameter(Mandatory = $true)][int]$WaitForPid,
    [Parameter(Mandatory = $true)][string]$LogDir,
    [Parameter(Mandatory = $true)][string]$ManifestPath,
    [int]$WaitSeconds = 90
)

$ErrorActionPreference = 'Stop'
$logFile = Join-Path $LogDir 'update.log'

function Write-Zeile($text) {
    $stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    Write-Host $text
    try {
        New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
        Add-Content -Path $logFile -Value "$stamp $text" -Encoding UTF8
    } catch {
        # Eine nicht schreibbare Aufzeichnung darf das Aktualisieren nicht stoppen.
    }
}

$Host.UI.RawUI.WindowTitle = 'Backrec wird aktualisiert'
Write-Host 'Backrec wird aktualisiert ...'
Write-Zeile "Start (Ordner: $RepoPath, Nachbarordner: $StagingPath)"

# --- Auf das Ende der laufenden Anwendung warten ------------------------------
$deadline = (Get-Date).AddSeconds($WaitSeconds)
while ((Get-Date) -lt $deadline) {
    $alive = Get-Process -Id $WaitForPid -ErrorAction SilentlyContinue
    if (-not $alive) { break }
    Start-Sleep -Seconds 1
}

if (Get-Process -Id $WaitForPid -ErrorAction SilentlyContinue) {
    Write-Zeile "Abbruch: die laufende Anwendung ($WaitForPid) reagiert nicht. Der bisherige Stand bleibt unveraendert."
    Write-Host ''
    Write-Host 'Was ist passiert: Die laufende Anwendung hat sich nicht beendet.'
    Write-Host 'Was tun: Den Rechner neu starten und es noch einmal versuchen.'
    Start-Sleep -Seconds 10
    exit 1
}

# --- Die bisherige Liste lesen, bevor sie ueberschrieben wird -----------------
$alteDateien = @()
if (Test-Path $ManifestPath) {
    try {
        $altes = Get-Content -Raw -Path $ManifestPath -Encoding UTF8 | ConvertFrom-Json
        $alteDateien = @($altes.files | ForEach-Object { $_.path })
    } catch {
        Write-Zeile 'Die bisherige Liste ist unlesbar -- es wird nichts entfernt.'
    }
}

$neueDateien = @()
$neueListe = Join-Path $StagingPath 'release-manifest.json'
if (Test-Path $neueListe) {
    $neues = Get-Content -Raw -Path $neueListe -Encoding UTF8 | ConvertFrom-Json
    $neueDateien = @($neues.files | ForEach-Object { $_.path })
} else {
    Write-Zeile 'Abbruch: im Nachbarordner fehlt die Liste der Dateien.'
    exit 1
}

# --- Spiegeln -----------------------------------------------------------------
$gespiegelt = 0
foreach ($relativ in $neueDateien) {
    $quelle = Join-Path $StagingPath ($relativ -replace '/', '\')
    $ziel = Join-Path $RepoPath ($relativ -replace '/', '\')
    $zielOrdner = Split-Path -Parent $ziel
    if ($zielOrdner -and -not (Test-Path $zielOrdner)) {
        New-Item -ItemType Directory -Force -Path $zielOrdner | Out-Null
    }
    Copy-Item -Path $quelle -Destination $ziel -Force
    $gespiegelt++
}
# Die Liste fuehrt sich nicht selbst auf. Ohne diese Zeile bliebe die Liste der
# vorherigen Fassung im Ordner stehen -- und die Einrichtung gleich danach haelt
# jede Datei, die neu in dieser Fassung ist, fuer eine Altlast und loescht sie.
Copy-Item -Path $neueListe -Destination (Join-Path $RepoPath 'release-manifest.json') -Force
Write-Zeile "$gespiegelt Datei(en) uebernommen."

# --- Altdateien entfernen ----------------------------------------------------
$entfernt = 0
foreach ($relativ in $alteDateien) {
    if ($neueDateien -contains $relativ) { continue }
    $ziel = Join-Path $RepoPath ($relativ -replace '/', '\')
    if (Test-Path $ziel) {
        Remove-Item -Path $ziel -Force -ErrorAction SilentlyContinue
        $entfernt++
    }
}
Write-Zeile "$entfernt nicht mehr benoetigte Datei(en) entfernt."

Copy-Item -Path $neueListe -Destination $ManifestPath -Force

# Erst jetzt: bis hierher war der Nachbarordner der Rueckweg.
Remove-Item -Path $StagingPath -Recurse -Force -ErrorAction SilentlyContinue

# --- Ohne Rueckfragen einrichten, dann wieder starten -------------------------
# --start, weil Backrec sich fuer diese Aktualisierung selbst beendet hat: ohne
# den Schalter fragt der unbeaufsichtigte Lauf nichts und startet nichts.
#
# Ueber Setup.cmd statt mit einem eigenen Abgleich: Setup.cmd ruft zuerst
# scripts\win\bootstrap-uv.ps1 auf, und dort steht --reinstall-package, das nach
# dem Spiegeln Pflicht ist -- ein Abgleich ohne das liesse lautlos den alten
# Stand weiterlaufen. Beide Skripte stehen ausserhalb der Arbeitsumgebung, und
# genau das ist die Voraussetzung. Wer diesen Aufruf ersetzt, muss das Neu-
# Einrichten des eigenen Pakets mitnehmen.
#
# Start-Process mit vollem Pfad, nicht "cmd /c Setup.cmd": Push-Location setzt
# nur den Ort dieser Sitzung, nicht das Arbeitsverzeichnis, das ein Kindprozess
# erbt. Das startende cmd suchte Setup.cmd deshalb dort, wo Backrec gestartet
# wurde, fand nichts -- und das Aktualisieren endete mit gespiegelten Dateien,
# ohne nachgezogene Arbeitsumgebung und ohne Neustart.
Write-Zeile 'Die Einrichtung wird ohne Rueckfragen nachgezogen.'
$einrichten = Join-Path $RepoPath 'Setup.cmd'
if (-not (Test-Path $einrichten)) {
    Write-Zeile "Abbruch: $einrichten gibt es nicht."
    Write-Host ''
    Write-Host 'Was ist passiert: Im Ordner von Backrec fehlt die Datei zum Einrichten.'
    Write-Host 'Was tun: Die neue Fassung noch einmal ueber den Ordner entpacken.'
    Start-Sleep -Seconds 10
    exit 1
}

# -PassThru mit WaitForExit statt -Wait: -Wait wartet auf den Vorgang *und alle
# seine Nachkommen*, und das Einrichten startet Backrec zum Schluss abgekoppelt.
# Damit wartete dieses Fenster, solange Backrec laeuft -- also bis zum Feierabend,
# ohne je "fertig" zu sagen.
$lauf = Start-Process -FilePath $einrichten `
                      -ArgumentList '--unattended', '--start' `
                      -WorkingDirectory $RepoPath `
                      -NoNewWindow -PassThru
$lauf.WaitForExit()
$code = $lauf.ExitCode
Write-Zeile "Einrichtung beendet (Ergebnis $code)."

if ($code -eq 0) {
    Write-Host ''
    Write-Host 'Fertig. Backrec laeuft wieder.'
} else {
    Write-Host ''
    Write-Host 'Was ist passiert: Nach dem Aktualisieren ist noch etwas offen.'
    Write-Host 'Was tun: Setup.cmd im Ordner von Backrec doppelklicken.'
}
Start-Sleep -Seconds 8
exit $code
