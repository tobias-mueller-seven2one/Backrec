## Why

Backrec trägt heute eine vollständige Update-Mechanik: ein Kommando `update <zip>` und `update --git` (`src/backrec/cli.py:66-77`, `src/backrec/cli.py:228-244`), ein Modul `src/backrec/update.py` mit Archivprüfung, Staging, Spiegelung und Altdatei-Entfernung, einen Helfer `scripts/win/apply-update.ps1`, der sich für die Spiegelung eine eigene Konsole holt, ein `release-manifest.json` als Vergleichsmaßstab samt Kopie in `state\`, und eine Update-Erkennung in der Einrichtung, die den Wechsel der Version meldet und entfallene Altdateien wegräumt (`src/backrec/control.py:696-702`, `src/backrec/control.py:775-792`).

Tobias Müller hat am 15.09.2026 entschieden: **Die Anwendungen der MemoSuite haben keine Aktualisierungsfunktion.** Ein neuer Stand wird beschafft, indem das Programm neu heruntergeladen wird und den vorhandenen Stand ersetzt. Fachlich ist das ein vollständiges Löschen mit anschließendem normalem Setup — also genau die beiden Vorgänge, die es ohnehin schon gibt. Ein dritter Vorgang, der beides zusammenfasst, deckt keinen fachlichen Bedarf ab; er verdoppelt nur, was Löschen und Einrichten je für sich bereits leisten, und trägt dabei die Last, die eine Selbstersetzung mit sich bringt: eine zweite Konsole außerhalb des Ordners, ein Manifest als zweite Wahrheit über den Dateibestand, ein Löschpfad, der Dateien im Ordner des Benutzers entfernt.

Der bisherige Auftrag wurde falsch verstanden und hat diese Mechanik eingebaut. Sie ist vollständig zurückzubauen. Das Thema existiert danach nicht mehr — weder als Code noch als Kommando, Menüpunkt, Erkennung, Manifest, Spec-Requirement oder Doku-Abschnitt. Auch kein Ersatztext wie „So kommst du an eine neue Version": ein Kapitel, das erklärt, dass es die Funktion nicht gibt, ist immer noch ein Kapitel über die Funktion.

## What Changes

- **BREAKING: Das Kommando `update` entfällt in jeder Form.** `update <zip>`, `update --git` und `update --force` verschwinden aus dem Parser und aus der Kommandotabelle. Die Kommandozeile kennt danach `setup`, `start`, `stop`, `status`, `doctor`, `shortcut`, `uninstall`, `logs`, `release` und `about` — zehn statt elf.
- **Das Modul `src/backrec/update.py` entfällt ersatzlos**, mit ihm `UpdateError`, `ArchiveInfo`, `UpdatePlan`, `inspect`, `plan`, `stage`, `mirror`, `staging_dir`, `read_installed_manifest`, `write_installed_manifest`, `store_manifest_from_repo`, `stale_files` und `remove_stale`. `tests/test_update.py` entfällt mit ihm.
- **`scripts/win/apply-update.ps1` entfällt ersatzlos.** Damit verschwindet der einzige Vorgang, der sich eine eigene Konsole außerhalb des Ordners holt; die Konstante `CREATE_NEW_CONSOLE` in `control.py` verliert ihren Verwender und geht mit.
- **Die Update-Funktionen der Control-Surface entfallen:** `inspect_archive`, `_refuse_older`, `apply_archive`, `update_from_git` und `_remove_stale_files`. `SetupResult.updated_from` entfällt als Feld.
- **Die Update-Erkennung in der Einrichtung entfällt.** Der Vergleich der zuvor eingerichteten Version mit der vorliegenden, der Zweig „es ist eine neue Fassung da", das Aufräumen entfallener Altdateien und die Kopie des Manifests nach `state\` verschwinden aus `control.setup`. Die Einrichtung weiß danach nichts über Vorgängerstände; sie bleibt idempotent und darf beliebig oft laufen.
- **`release-manifest.json` entfällt als Update-Grundlage.** Der Release-Bau erzeugt es nicht mehr und legt es nicht mehr ins ZIP; `paths.INSTALLED_MANIFEST_NAME`, `paths.installed_manifest_path` und `release.MANIFEST_NAME` entfallen, ebenso `ManifestEntry`, `build_manifest` und `manifest_entries`. `ReleaseResult` führt nur noch Archivpfad und Version.
- **`version.is_newer` entfällt.** Es beantwortet ausschließlich die Frage „ist das neuer als das Eingerichtete", und diese Frage stellt niemand mehr. `read_version` und `parse_version` bleiben: die eine liefert die Versionsauskunft, die andere prüft die Form beim Release-Bau.
- **Die Diagnose verliert die Prüfung auf Ordner einer abgelösten Fassung** (`doctor.stale_update_folders`, `Observations.stale_folders`, Check `state.stale_folders`). Sie prüfte auf `.update`- und `.old-`-Nachbarordner — Rückstände, die es ohne Update-Vorgang nicht mehr geben kann.
- **`LIES-MICH-ZUERST.txt`:** Der Abschnitt „Aktualisieren" entfällt ersatzlos. Die Anleitung führt danach **sieben** Abschnitte statt acht; Form, Grenzen und Reihenfolge der übrigen bleiben unverändert.
- **`README.md`** (englisch, Entwicklerdoku): die Kommandozeile im Tabellenabschnitt, das Kapitel „Release and update" und die beiläufigen Erwähnungen verlieren jede Update-Passage. Das Kapitel heißt danach „Release".
- **Ein Test sichert die Abwesenheit:** die Kommandozeile MUST NOT ein Kommando zum Aktualisieren kennen, und das Wurzelverzeichnis MUST NOT einen Update-Helfer führen.

Nicht-Ziele:

- `VERSION` bleibt als Datei und als Anzeige in `about`, `status`, Diagnose und Einrichtung. Das ist Versionsauskunft, keine Update-Funktion.
- `Setup.cmd` bleibt idempotent und darf mehrfach laufen — nur eben ohne Wissen über Vorgängerstände.
- Der Release-Bau bleibt bestehen, samt aller fünf Prüfungen vor dem Packen. Er verliert nur das Manifest.
- Das Beenden einer laufenden Anwendung bleibt: Die Einrichtung beendet sie unbedingt, bevor sie an der Umgebung arbeitet — ohne Versionserkennung und ohne Vergleich (D5, revidiert). Das ist Setup-Hygiene, keine Aktualisierungsfunktion: Der Bootstrap außerhalb des Ordners ersetzt den Paketinhalt in der Arbeitsumgebung, aus der eine laufende Anwendung ihren Code bezogen hat.
- Die Desktop-Verknüpfung (`shortcut`) bleibt unberührt; Backrec hat statt Autostart eine Verknüpfung, daran ändert sich nichts.
- „Aktualisieren" im Sinn von Oberfläche oder Daten — die Pegelanzeige wird aktualisiert, der Zustand wird aktualisiert, `dict.update` — bleibt unangetastet. Gemeint ist ausschließlich die Aktualisierung des Programms selbst.

## Capabilities

### New Capabilities

Keine. Es kommt nichts hinzu.

### Modified Capabilities

- `tool-setup`: „Aktualisierung über ein neues Release-ZIP" und „Entfernen von Altdateien anhand des Release-Verzeichnisses" entfallen vollständig. „Zwei Doppelklick-Dateien und eine Versionsangabe im Wurzelverzeichnis" nennt das Aktualisieren nicht mehr als Vorgang, der über ein Kommando erreichbar bleibt. „Einstiegsanleitung im Wurzelverzeichnis" führt sieben statt acht Abschnitte, ohne „Aktualisieren". „Bauen eines Release-Pakets" verlangt keine Beschreibung des Release mehr im Paket.
- `diagnostics`: „Prüfung von Verknüpfung und Zustand" entfällt und wird als „Prüfung von Verknüpfung, Zustand und Berichten" ohne die Warnung über den Ordner einer durch eine Aktualisierung abgelösten Fassung neu gefasst. Der Umbenennung liegt kein neuer Bedarf zugrunde: Das Werkzeug lässt eine geänderte Anforderung kein Szenario verlieren, also tritt eine neue an ihre Stelle, und ihr Name nennt den verbliebenen Umfang.

## Impact

- Gelöschte Dateien: `src/backrec/update.py`, `scripts/win/apply-update.ps1`, `tests/test_update.py`.
- Geänderter Code: `src/backrec/cli.py` (Subkommando, Handler, Tabelle), `src/backrec/control.py` (Update-Abschnitt, Setup-Zweig, `SetupResult`, `CREATE_NEW_CONSOLE`, Kommentare), `src/backrec/release.py` (Manifest, `ManifestEntry`, Abschnittsliste der Anleitung), `src/backrec/paths.py` (Manifest-Name und -Pfad), `src/backrec/version.py` (`is_newer`), `src/backrec/doctor.py` (Prüfung auf abgelöste Ordner), `src/backrec/console.py` (Kommentare).
- Dokumente: `LIES-MICH-ZUERST.txt`, `README.md`.
- Tests: `tests/test_cli.py`, `tests/test_control.py`, `tests/test_setup.py`, `tests/test_root_files.py`, `tests/test_docs.py`, `tests/test_release.py`, `tests/test_doctor.py`.
- Nicht betroffen: Aufnahme, Mischung, Ablage, Preflight, Konfiguration, Verknüpfung, Instanzverwaltung, Protokollierung, das Anwendungsfenster.
