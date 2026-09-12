# Bootstrap fuer Setup.cmd: Zonenkennung entfernen, Hilfsprogramm beschaffen,
# Arbeitsumgebung aufbauen.
#
# Warum ueberhaupt ein Skript vor dem eigentlichen Einrichten: das Einrichten
# selbst laeuft in der Arbeitsumgebung, die es hier erst gibt. Und die
# Zonenkennung muss weg, bevor Windows das naechste Hilfsskript blockiert.
#
# PowerShell 5.1 kompatibel: kein ternaerer Operator, kein ?? und kein
# ForEach-Object -Parallel.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repo

function Write-Schritt($text) { Write-Host $text }
function Write-Gut($text)     { Write-Host "    [OK] $text" }
function Write-Schlecht($was, $tun) {
    Write-Host "    [X] Was ist passiert: $was"
    Write-Host "        Was tun: $tun"
}

# --- Zonenkennung ------------------------------------------------------------
# Aus dem Internet bezogene Archive geben eine Zonenkennung an jede entpackte
# Datei weiter. Der eine Sicherheitsdialog beim allerersten Doppelklick auf
# Setup.cmd laesst sich damit nicht vermeiden -- jeder weitere schon.
try {
    Get-ChildItem -Path $repo -Recurse -File -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch '\\\.git\\' -and $_.FullName -notmatch '\\\.venv\\' } |
        Unblock-File -ErrorAction SilentlyContinue
} catch {
    # Nicht fatal: schlimmstenfalls erscheint ein weiterer Sicherheitsdialog.
    Write-Host '    [!] Die Kennzeichnung aus dem Internet liess sich nicht entfernen.'
    Write-Host '        Es kann daher ein weiterer Sicherheitsdialog erscheinen; dort'
    Write-Host '        in den Eigenschaften der Datei auf Zulassen klicken.'
}

# --- Hilfsprogramm -----------------------------------------------------------
Write-Schritt 'Vorbereitung: Hilfsprogramme'

$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Host '    Das Hilfsprogramm fuer die Einrichtung fehlt und wird jetzt geholt.'
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        & winget install --id astral-sh.uv -e --scope user --accept-package-agreements --accept-source-agreements | Out-Null
    }
    $uv = Get-Command uv -ErrorAction SilentlyContinue
}

if (-not $uv) {
    try {
        Invoke-RestMethod https://astral.sh/uv/0.11.21/install.ps1 | Invoke-Expression
    } catch {
        Write-Verbose "Zweiter Weg fehlgeschlagen: $($_.Exception.Message)"
    }
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    $uv = Get-Command uv -ErrorAction SilentlyContinue
}

if (-not $uv) {
    Write-Schlecht 'Das Hilfsprogramm fuer die Einrichtung liess sich nicht holen.' `
                   'Internetverbindung pruefen und Setup.cmd erneut doppelklicken.'
    exit 1
}
Write-Gut 'Hilfsprogramm vorhanden'

# --- Arbeitsumgebung ---------------------------------------------------------
Write-Schritt 'Vorbereitung: Arbeitsumgebung'

# Ein Deinstallieren, das aus der Arbeitsumgebung selbst lief, kann sie nicht
# vollstaendig entfernen: Windows gibt die laufende Programmdatei nicht frei.
# Zurueck bleibt ein Ordner ohne pyvenv.cfg, den ein erneutes Aufbauen
# kommentarlos stehen laesst -- und jeder Start scheitert danach.
if ((Test-Path '.venv') -and -not (Test-Path '.venv\pyvenv.cfg')) {
    Write-Host '    Eine unvollstaendige Arbeitsumgebung wird neu aufgebaut.'
    Remove-Item -Recurse -Force '.venv' -ErrorAction SilentlyContinue
}

# --reinstall-package ist keine Vorsicht, sondern Pflicht: ein Abgleich gegen die
# festgeschriebene Liste sieht nur die Fremdpakete. Die Dateien dieses Werkzeugs
# selbst gelten ihm als unveraendert, auch wenn gerade ein neues Archiv
# darueberkopiert wurde. Ohne diese Angabe liefe nach einer Aktualisierung
# weiter der alte Stand, und zwar lautlos.
#
# Hier und nicht im Einrichten selbst: das Einrichten laeuft in der
# Arbeitsumgebung, die es ersetzen muesste, und Windows gibt eine laufende
# Programmdatei nicht frei. Dieses Skript steht ausserhalb.
& uv sync --locked --no-dev --no-editable --reinstall-package backrec
if ($LASTEXITCODE -ne 0) {
    Write-Schlecht 'Die Arbeitsumgebung liess sich nicht aufbauen.' `
                   'Internetverbindung pruefen und Setup.cmd erneut doppelklicken.'
    exit 1
}
Write-Gut 'Arbeitsumgebung steht'
Write-Host ''
exit 0
