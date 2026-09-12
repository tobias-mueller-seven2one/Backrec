# Bootstrap for Setup.cmd.
#
# Why a script at all before the actual setup: the setup itself runs in the
# working environment that only comes into being here. And the zone mark has to
# go before Windows blocks the next helper script.
#
# PowerShell 5.1 compatible: no ternary operator, no ?? and no
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

# --- Zone mark ---------------------------------------------------------------
# An archive fetched from the internet passes a zone mark on to every file it
# unpacks. The one security dialog on the very first double click of Setup.cmd
# cannot be avoided that way -- every further one can.
try {
    Get-ChildItem -Path $repo -Recurse -File -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch '\\\.git\\' -and $_.FullName -notmatch '\\\.venv\\' } |
        Unblock-File -ErrorAction SilentlyContinue
} catch {
    # Not fatal: at worst one more security dialog appears.
    Write-Host '    [!] Die Kennzeichnung aus dem Internet ließ sich nicht entfernen.'
    Write-Host '        Es kann daher ein weiterer Sicherheitsdialog erscheinen; dort'
    Write-Host '        in den Eigenschaften der Datei auf Zulassen klicken.'
}

# --- Helper program ----------------------------------------------------------
Write-Schritt 'Vorbereitung: Hilfsprogramme'

$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Host '    Das Hilfsprogramm für die Einrichtung fehlt und wird jetzt geholt.'
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
    Write-Schlecht 'Das Hilfsprogramm für die Einrichtung ließ sich nicht holen.' `
                   'Internetverbindung prüfen und Setup.cmd erneut doppelklicken.'
    exit 1
}
Write-Gut 'Hilfsprogramm vorhanden'

# --- Working environment -----------------------------------------------------
Write-Schritt 'Vorbereitung: Arbeitsumgebung'

# An uninstall that ran from inside the working environment cannot remove it
# completely: Windows does not release the running executable. What stays behind
# is a folder without pyvenv.cfg that a rebuild leaves standing without a word
# -- and every start fails from then on.
if ((Test-Path '.venv') -and -not (Test-Path '.venv\pyvenv.cfg')) {
    Write-Host '    Eine unvollständige Arbeitsumgebung wird neu aufgebaut.'
    Remove-Item -Recurse -Force '.venv' -ErrorAction SilentlyContinue
}

# --reinstall-package is not caution but duty: a sync against the locked list
# only looks at the third-party packages. The files of this tool itself count as
# unchanged to it, even when a new archive has just been copied over them.
# Without this switch the old state would keep running after an update, and
# silently at that.
#
# Here and not in the setup itself: the setup runs in the working environment it
# would have to replace, and Windows does not release a running executable. This
# script stands outside of it.
& uv sync --locked --no-dev --no-editable --reinstall-package backrec
if ($LASTEXITCODE -ne 0) {
    Write-Schlecht 'Die Arbeitsumgebung ließ sich nicht aufbauen.' `
                   'Internetverbindung prüfen und Setup.cmd erneut doppelklicken.'
    exit 1
}
Write-Gut 'Arbeitsumgebung steht'
Write-Host ''
exit 0
