# Mirrors a checked, already unpacked new version in while Backrec shuts down.
#
# Why this runs outside the working environment: the code that updates lives in
# the very folder that is to be replaced. Windows keeps the loaded executable
# open while the process lives -- a process can neither rename its own folder nor
# overwrite itself and keep running. So the last leg is done by someone standing
# outside. Windows PowerShell 5.1 is on every Windows 11 and needs neither the
# working environment nor the helper program.
#
# Mirrored instead of swapped: the working environment lives in the folder, does
# not belong to the archive and should not have to be rebuilt; and the folder's
# path is written into the shortcut on the desktop.

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
        # An unwritable record must never stop the update itself.
    }
}

$Host.UI.RawUI.WindowTitle = 'Backrec wird aktualisiert'
Write-Host 'Backrec wird aktualisiert ...'
Write-Zeile "Start (Ordner: $RepoPath, Nachbarordner: $StagingPath)"

# --- Wait for the running application to end ----------------------------------
$deadline = (Get-Date).AddSeconds($WaitSeconds)
while ((Get-Date) -lt $deadline) {
    $alive = Get-Process -Id $WaitForPid -ErrorAction SilentlyContinue
    if (-not $alive) { break }
    Start-Sleep -Seconds 1
}

if (Get-Process -Id $WaitForPid -ErrorAction SilentlyContinue) {
    Write-Zeile "Abbruch: die laufende Anwendung ($WaitForPid) reagiert nicht. Der bisherige Stand bleibt unverändert."
    Write-Host ''
    Write-Host 'Was ist passiert: Die laufende Anwendung hat sich nicht beendet.'
    Write-Host 'Was tun: Den Rechner neu starten und es noch einmal versuchen.'
    Start-Sleep -Seconds 10
    exit 1
}

# --- Read the previous list before it is overwritten --------------------------
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

# --- Mirror -------------------------------------------------------------------
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
# The list does not name itself. Without this line the previous version's list
# would stay behind in the folder -- and the setup right afterwards would take
# every file that is new in this version for a leftover and delete it.
Copy-Item -Path $neueListe -Destination (Join-Path $RepoPath 'release-manifest.json') -Force
Write-Zeile "$gespiegelt Datei(en) übernommen."

# --- Remove files that no longer belong -------------------------------------
$entfernt = 0
foreach ($relativ in $alteDateien) {
    if ($neueDateien -contains $relativ) { continue }
    $ziel = Join-Path $RepoPath ($relativ -replace '/', '\')
    if (Test-Path $ziel) {
        Remove-Item -Path $ziel -Force -ErrorAction SilentlyContinue
        $entfernt++
    }
}
Write-Zeile "$entfernt nicht mehr benötigte Datei(en) entfernt."

Copy-Item -Path $neueListe -Destination $ManifestPath -Force

# Only now: up to here the neighbouring folder was the way back.
Remove-Item -Path $StagingPath -Recurse -Force -ErrorAction SilentlyContinue

# --- Set up without questions, then start again -------------------------------
# --start, because Backrec ended itself for this update: without the switch the
# unattended run asks nothing and starts nothing.
#
# Through Setup.cmd rather than a sync of our own: Setup.cmd calls
# scripts\win\bootstrap-uv.ps1 first, and that is where --reinstall-package
# stands, which is mandatory after mirroring -- a sync without it would silently
# keep the old state running. Both scripts live outside the working environment,
# and that is exactly the precondition. Whoever replaces this call has to bring
# the reinstall of our own package along.
#
# Start-Process with the full path, not "cmd /c Setup.cmd": Push-Location only
# moves the location of this session, not the working directory a child process
# inherits. The starting cmd therefore looked for Setup.cmd wherever Backrec had
# been started from, found nothing -- and the update ended with mirrored files,
# no environment brought up to date and no restart.
Write-Zeile 'Die Einrichtung wird ohne Rückfragen nachgezogen.'
$einrichten = Join-Path $RepoPath 'Setup.cmd'
if (-not (Test-Path $einrichten)) {
    Write-Zeile "Abbruch: $einrichten gibt es nicht."
    Write-Host ''
    Write-Host 'Was ist passiert: Im Ordner von Backrec fehlt die Datei zum Einrichten.'
    Write-Host 'Was tun: Die neue Fassung noch einmal über den Ordner entpacken.'
    Start-Sleep -Seconds 10
    exit 1
}

# -PassThru with WaitForExit instead of -Wait: -Wait waits for the process *and
# all its descendants*, and the setup starts Backrec detached at the end. This
# window therefore waited for as long as Backrec runs -- until knocking-off time,
# without ever saying "finished".
$lauf = Start-Process -FilePath $einrichten `
                      -ArgumentList '--unattended', '--start' `
                      -WorkingDirectory $RepoPath `
                      -NoNewWindow -PassThru
# Reading .Handle makes the process id stick. Without this line .ExitCode stays
# empty after the wait -- and this window then reported something left open after
# every successful update.
$null = $lauf.Handle
$lauf.WaitForExit()
$code = $lauf.ExitCode
if ($null -eq $code) { $code = 1 }
Write-Zeile "Einrichtung beendet (Ergebnis $code)."

if ($code -eq 0) {
    Write-Host ''
    Write-Host 'Fertig. Backrec läuft wieder.'
} else {
    Write-Host ''
    Write-Host 'Was ist passiert: Nach dem Aktualisieren ist noch etwas offen.'
    Write-Host 'Was tun: Setup.cmd im Ordner von Backrec doppelklicken.'
}
Start-Sleep -Seconds 8
exit $code
