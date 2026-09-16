## 1. Kommandozeile

- [x] 1.1 `update` aus `build_parser` und aus `_COMMANDS` entfernen, `_command_update` löschen (`src/backrec/cli.py`).
      *Verifikation:* `backrec --help` listet zehn Kommandos ohne `update`; `backrec update` endet mit Exit-Code 2 und nennt die bekannten Kommandos. (tool-setup — „Zwei Doppelklick-Dateien und eine Versionsangabe im Wurzelverzeichnis")

- [x] 1.2 In `tests/test_cli.py` `update` aus der Kommandoliste nehmen, `test_update_takes_an_archive_or_the_developer_route` und `test_update_without_an_archive_names_the_one_way` löschen, einen Test ergänzen, der `parse(["update", ...])` als `SystemExit` erwartet und `update` in keiner Kommandotabelle findet.
      *Verifikation:* `uv run pytest tests/test_cli.py` ist grün und enthält den neuen Abwesenheitstest. (tool-setup — „Zwei Doppelklick-Dateien …", Szenario „Kein Weg zum Aktualisieren des Programms")

## 2. Update-Modul und Helfer

- [x] 2.1 `src/backrec/update.py` und `tests/test_update.py` löschen.
      *Verifikation:* Beide Dateien existieren nicht mehr; `uv run python -c "import backrec.cli"` läuft ohne `ModuleNotFoundError`. (tool-setup — REMOVED „Aktualisierung über ein neues Release-ZIP")

- [x] 2.2 `scripts/win/apply-update.ps1` löschen.
      *Verifikation:* `scripts/win` enthält nur noch `bootstrap-uv.ps1`. (tool-setup — REMOVED „Aktualisierung über ein neues Release-ZIP")

- [x] 2.3 In `tests/test_root_files.py` alle Tests des Update-Helfers entfernen (`test_the_update_helper_*`), `apply-update.ps1` aus `HELFER` und aus den PowerShell-5- und Umlaut-Prüfungen nehmen, `Update.cmd` aus der Liste der verbotenen Doppelklick-Dateien belassen und einen Test ergänzen, der die Abwesenheit eines Update-Helfers unter `scripts/win` sichert.
      *Verifikation:* `uv run pytest tests/test_root_files.py` ist grün; der neue Test schlägt fehl, wenn eine Datei mit `update` im Namen unter `scripts/win` angelegt wird. (tool-setup — „Zwei Doppelklick-Dateien …", Szenario „Kein Weg zum Aktualisieren des Programms")

## 3. Control-Surface und Einrichtung

- [x] 3.1 Aus `src/backrec/control.py` den Abschnitt „Update" entfernen: `inspect_archive`, `_refuse_older`, `apply_archive`, `update_from_git`, `_remove_stale_files`, den Import von `update as update_module`, die Konstante `CREATE_NEW_CONSOLE` samt Kommentar und das Feld `SetupResult.updated_from`.
      *Verifikation:* `Grep` nach `update` in `control.py` findet nur noch `dict.update`-artige Treffer; `uv run pytest tests/test_control.py` läuft. (tool-setup — REMOVED „Aktualisierung über ein neues Release-ZIP")

- [x] 3.2 In `control.setup` den Zweig `updating` entfernen: Vergleich mit `read_installed_version`, die Meldung „Es ist eine neue Fassung da", den Aufruf von `_remove_stale_files` und `store_manifest_from_repo`. `write_installed_version` bleibt; das Beenden einer laufenden Anwendung bleibt ebenfalls und wird in 3.5 von der Versionserkennung entkoppelt.
      *Verifikation:* Ein zweiter Lauf der Einrichtung mit erhöhter `VERSION` erzeugt keine Zeile über einen Versionswechsel und entfernt keine Datei. (tool-setup — REMOVED „Entfernen von Altdateien anhand des Release-Verzeichnisses")

- [x] 3.3 In `tests/test_control.py` den Abschnitt „Update" löschen (`test_update_from_git_*`, `test_a_broken_archive_*`, `_archive`, `FakeProcess`-Nutzung im Update-Kontext, `test_updating_*`, `test_an_older_archive_*`, `test_inspect_*`).
      *Verifikation:* `uv run pytest tests/test_control.py` ist grün und nennt kein Archiv mehr. (tool-setup — REMOVED „Aktualisierung über ein neues Release-ZIP")

- [x] 3.4 In `tests/test_setup.py` den Import von `update`, den Abschnitt „Removing files of the previous release" (`write_manifest`, `test_a_file_of_the_previous_release_is_removed`, `test_the_clean_up_never_touches_*`) und den Test auf `result.updated_from` entfernen; den verbleibenden Idempotenz-Test so fassen, dass ein zweiter Lauf mit erhöhter Version Konfiguration und Protokolle unverändert lässt, ohne einen Versionswechsel zu melden.
      *Verifikation:* `uv run pytest tests/test_setup.py` ist grün. (tool-setup — REMOVED „Entfernen von Altdateien …", „Idempotenz der Einrichtung")

- [x] 3.5 Den unbedingten Stopp in `control.setup` einsetzen (D5, revidiert): `_stop_running_application` beendet eine laufende Anwendung als erste Handlung von Schritt 2, vor `_ensure_environment`, mit der Meldung „Die laufende Anwendung wird vorher beendet." Kein `read_installed_version`, kein Versionsvergleich, kein Text über eine neue Fassung; läuft nichts, bleibt die Ausgabe still.
      *Verifikation:* `Grep` nach `read_installed_version` in `control.py` findet nur Definition und Doku, keinen Aufruf in `setup`; eine Einrichtung neben einer laufenden Anwendung beendet sie bei unveränderter Version und bietet in Schritt 7 den Start wieder an. (tool-setup — MODIFIED „Reihenfolge, Meldungen und Abschluss der Einrichtung", Szenario „Laufende Anwendung beim Einrichten")

- [x] 3.6 In `tests/test_setup.py` einen Test ergänzen, der belegt, dass die Einrichtung eine laufende Anwendung bei **unveränderter** Version beendet, und zwar vor dem Aufbau der Umgebung; bestehende Tests, die die Abwesenheit des Stopps festschreiben würden, entsprechend fassen.
      *Verifikation:* `uv run pytest tests/test_setup.py` ist grün; der neue Test schlägt fehl, sobald der Stopp entfällt oder an eine Versionserkennung gebunden wird. (tool-setup — MODIFIED „Reihenfolge, Meldungen und Abschluss der Einrichtung")

## 4. Release und Pfade

- [x] 4.1 Aus `src/backrec/release.py` `MANIFEST_NAME`, `ManifestEntry`, `build_manifest`, `manifest_entries`, den Manifest-Eintrag in `EXCLUDED_PATTERNS`, das `writestr` des Manifests in `build` und das Feld `ReleaseResult.entries` entfernen; den Modul-Docstring auf die erzeugte Datei statt „die beiden erzeugten Dateien" anpassen.
      *Verifikation:* Ein gebautes ZIP enthält kein `release-manifest.json`. (tool-setup — MODIFIED „Bauen eines Release-Pakets", Szenario „Keine Beschreibung des Release im Paket")

- [x] 4.2 `"Aktualisieren"` aus `GUIDE_SECTIONS` entfernen und die Zahl acht im umgebenden Kommentar auf sieben korrigieren.
      *Verifikation:* `release.check_guide` läuft gegen die bereinigte Anleitung durch und bricht ab, wenn ein Abschnitt fehlt. (tool-setup — MODIFIED „Einstiegsanleitung im Wurzelverzeichnis")

- [x] 4.3 Aus `src/backrec/paths.py` `INSTALLED_MANIFEST_NAME`, `installed_manifest_path` und `is_newer` samt ihrer `__all__`-Einträge entfernen; `is_newer` aus `src/backrec/version.py` löschen und dessen Docstring vom Aktualisieren befreien.
      *Verifikation:* `uv run python -c "from backrec import paths, version"` läuft; `Grep` nach `is_newer` und `manifest` in `src/` findet nichts mehr. (tool-setup — REMOVED „Entfernen von Altdateien …")

- [x] 4.4 In `tests/test_release.py` die Manifest-Prüfungen entfernen und durch eine Prüfung ersetzen, dass das Paket kein `release-manifest.json` führt; in `tests/test_paths.py` die `is_newer`-Zusicherungen streichen und `parse_version` und `read_version` stehen lassen.
      *Verifikation:* `uv run pytest tests/test_release.py tests/test_paths.py` ist grün. (tool-setup — MODIFIED „Bauen eines Release-Pakets")

## 5. Diagnose

- [x] 5.1 Aus `src/backrec/doctor.py` `stale_update_folders`, das Feld `Observations.stale_folders`, den Check `state.stale_folders` und die Zuweisung in `observe` entfernen.
      *Verifikation:* `backrec doctor --json` enthält keinen Eintrag `state.stale_folders`. (diagnostics — MODIFIED „Prüfung von Verknüpfung und Zustand")

- [x] 5.2 In `tests/test_doctor.py` `test_a_left_over_folder_of_a_superseded_version_warns_without_removing` löschen und jeden `stale_folders`-Parameter aus den Hilfsfunktionen nehmen.
      *Verifikation:* `uv run pytest tests/test_doctor.py` ist grün. (diagnostics — MODIFIED „Prüfung von Verknüpfung und Zustand")

## 6. Dokumentation

- [x] 6.1 In `LIES-MICH-ZUERST.txt` den Abschnitt „Aktualisieren" samt seiner Zeile ersatzlos streichen; UTF-8 mit Bytereihenfolge-Kennung, CRLF, höchstens 40 Zeilen und höchstens 80 Zeichen je Zeile beibehalten, die Abschnittsfolge der übrigen sieben unverändert lassen.
      *Verifikation:* `release.check_guide` läuft ohne Fehler; die Datei beginnt mit `EF BB BF`, jede Zeile endet mit CRLF, und auf „Wenn etwas rot ist" folgt „Entfernen". (tool-setup — MODIFIED „Einstiegsanleitung im Wurzelverzeichnis")

- [x] 6.2 In `README.md` (englisch) die Zeile `update` aus der Kommandotabelle nehmen, `update` aus der Aufzählung der reinen Kommandos und aus dem Satz über `Update.cmd` streichen, das Kapitel „Release and update" zu „Release" kürzen (die drei Absätze über Weg A, `update <zip>` und `update --git` entfallen), den Satz über die Konfiguration außerhalb des Repositorys ohne Update-Begründung formulieren und den Satz im Projektstatus ohne „auto-update" fassen.
      *Verifikation:* `Grep` nach `(?i)update` in `README.md` findet keinen Treffer mehr, der das Programm selbst meint. (tool-setup — MODIFIED „Einstiegsanleitung im Wurzelverzeichnis", „Bauen eines Release-Pakets")

- [x] 6.3 In `tests/test_docs.py` `update --git` aus `DEVELOPER_ONLY` nehmen, `test_the_guide_names_one_way_to_change_a_setting_and_one_to_update` auf die Einstellung allein zurückführen und einen Test ergänzen, der sichert, dass weder Anleitung noch README einen Weg zum Aktualisieren des Programms nennen.
      *Verifikation:* `uv run pytest tests/test_docs.py` ist grün und enthält den neuen Abwesenheitstest. (tool-setup — MODIFIED „Einstiegsanleitung im Wurzelverzeichnis")

- [x] 6.4 Die verbliebenen Kommentare und Docstrings in `src/backrec/control.py`, `src/backrec/console.py` und `src/backrec/release.py` vom Update-Bezug befreien, ohne die technisch notwendige Begründung zu verlieren (etwa den Grund, warum `SYNC_COMMAND` ohne `--reinstall-package` auskommt).
      *Verifikation:* `Grep` nach `(?i)update|aktualisier` in `src/` liefert nur noch Treffer, die Oberfläche oder Daten meinen. (tool-setup — REMOVED „Aktualisierung über ein neues Release-ZIP")

- [x] 6.5 Die Nebenwirkung des unbedingten Stopps dokumentieren: in `LIES-MICH-ZUERST.txt` im Abschnitt „Im Alltag" nennen, dass eine laufende Anwendung beim erneuten Einrichten beendet und am Ende wieder angeboten wird; in `README.md` (englisch) den Ablauf der Einrichtung um den Stopp ergänzen. Das Wort „Aktualisieren" kehrt dabei nicht zurück.
      *Verifikation:* `release.check_guide` läuft ohne Fehler (BOM, CRLF, höchstens 40 Zeilen, höchstens 80 Zeichen je Zeile, sieben Abschnitte in Reihenfolge); `Grep` nach `(?i)aktualisier|update` findet in beiden Dateien keinen Treffer, der das Programm selbst meint. (tool-setup — MODIFIED „Einstiegsanleitung im Wurzelverzeichnis")

## 7. Stopp auf dem Doppelklick-Weg

- [x] 7.1 In `scripts/win/bootstrap-uv.ps1` den Stopp als erste Handlung des Abschnitts „Arbeitsumgebung" einsetzen (D10): existiert `.venv\Scripts\backrec.exe`, wird er mit `stop` aufgerufen, das Skript wartet auf sein Ende und erbt dessen Ausgabe. Keine eigene Frist, keine eigene Anforderungsdatei, keine Prozesserkennung. Fehlt die Umgebung oder der Einstiegspunkt, passiert nichts; scheitert der Aufruf oder endet er mit einem Fehlercode, folgt eine lesbare Zeile und das Bootstrap läuft weiter. Die Datei bleibt UTF-8 mit Bytereihenfolge-Kennung, PowerShell-5.1-tauglich und ohne ausgeschriebene Umlaute in sichtbaren Zeilen.
      *Verifikation:* Der Aufruf steht vor `& uv sync`; der Block enthält kein `exit 1`. (tool-setup — MODIFIED „Reihenfolge, Meldungen und Abschluss der Einrichtung", Szenario „Laufende Anwendung beim Doppelklick auf die Einrichtung")

- [x] 7.2 `_stop_running_application` in `control.setup` unverändert lassen (D10, Verworfenes): Er sichert den Entwicklerweg `backrec setup` ohne Bootstrap ab und bleibt auf dem Doppelklick-Weg still, weil der Zustandsdatensatz dann bereits entfernt ist.
      *Verifikation:* Nach einem erfolgreichen Stopp im Bootstrap liefert `instance.running_instance` `None`, und die Einrichtung erzeugt keine zweite Zeile über ein Beenden. (tool-setup — MODIFIED „Reihenfolge, Meldungen und Abschluss der Einrichtung", Szenario „Laufende Anwendung beim Aufruf des Kommandos")

- [x] 7.3 In `tests/test_root_files.py` drei Prüfungen ergänzen: der Stopp-Aufruf steht vor dem Sync-Aufruf, das Skript bringt keine eigene Stopp-Mechanik mit (`Stop-Process`, `Get-Process`, `Wait-Process`, `Start-Sleep`), und ein fehlgeschlagener Stopp beendet das Bootstrap nicht.
      *Verifikation:* `uv run pytest tests/test_root_files.py` ist grün; die Prüfungen schlagen fehl, sobald der Aufruf hinter den Sync rutscht oder das Skript den Abbruch einbaut. (tool-setup — MODIFIED „Reihenfolge, Meldungen und Abschluss der Einrichtung")

## 8. Abnahme

- [x] 8.1 Die Testsuite vollständig ausführen.
      *Verifikation:* `uv run pytest` endet ohne Fehlschlag; das Ergebnis wird im Klartext berichtet, auch wenn es rot ist.

- [x] 8.2 Abschließende Volltextsuche über das Repository nach `aktualisier`, `update`, `manifest` und `apply-update`.
      *Verifikation:* Jeder verbleibende Treffer meint entweder die Oberfläche bzw. Daten, gehört zu den archivierten Changes oder zum Werkzeugkasten unter `.claude`; kein Treffer beschreibt eine Aktualisierung des Programms.

- [x] 8.3 Die Delta-Specs in die Hauptspecs unter `openspec/specs/` übernehmen.
      *Verifikation:* `openspec/specs/tool-setup/spec.md` führt die beiden entfallenen Requirements nicht mehr, nennt sieben Abschnitte und fordert in „Reihenfolge, Meldungen und Abschluss der Einrichtung" den unbedingten Stopp auf beiden Wegen samt aller zugehörigen Szenarien; `openspec/specs/diagnostics/spec.md` nennt keine abgelöste Fassung mehr. Der Change bleibt unarchiviert.
