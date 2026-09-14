## 1. Das Fenster: Menü entfernen, Statuszeile aktivieren

- [x] 1.1 In `src/backrec/app.py` die Zahnrad-Schaltfläche samt ihrem Hovertext, das `tk.Menu` und dessen Aufbau entfernen — `GEAR_ICON`, `GEAR_TOOLTIP`, `MENU_UPDATE`, `MENU_DOCTOR`, `MENU_LOGS`, `MENU_SETTINGS`, `MENU_ABOUT`, `RECORDING_SUFFIX`, `menu_entry`, `update_question`, `_build_menu`, `_open_menu`, `_in_background`, `_release_menu`, `_menu_update`, `_menu_doctor`, `_menu_logs`, `_menu_settings`, `_menu_about`, das Merkmal `_menu_busy` und die Schaltfläche `menu_button`. Nachweis: `Grep` auf `menu` in `src/backrec/app.py` findet nichts mehr, und `python -c "import backrec.app"` läuft durch.
- [x] 1.2 Die Statuszeile klickbar machen: `cursor="hand2"`, Bindung auf `<Button-1>`, Hovertext „Klick öffnet die Diagnose" über den beibehaltenen Tooltip-Helfer. Nachweis: neuer Test, dass das Fenster nach dem Aufbau ein `_tooltip` zeigt, wenn die Statuszeile betreten wird, und es beim Verlassen wieder schließt.
- [x] 1.3 `_open_diagnosis` einführen: Guard gegen einen zweiten Lauf und gegen ein schließendes Fenster, Protokolleintrag, Arbeit in einem eigenen Thread über `control.run_doctor(report=True, open_report=True)`, Ausnahmen in das Protokoll statt in das Fenster. Der Text der Statuszeile wird nicht angefasst (design D26). Nachweis: neue Tests aus 4.1 bis 4.4.
- [x] 1.4 Prüfen, dass die Fensterhöhe nach dem Wegfall der Schaltfläche weiterhin über `_lock_window_size` aus dem Inhalt abgeleitet wird und die Breite 280 px bleibt. Nachweis: der bestehende Test `test_the_window_keeps_its_width` bleibt grün.

## 2. Control-Surface und Einrichtung

- [x] 2.1 In `src/backrec/control.py` den Abschlusssatz in `_closing_note` ersetzen: statt des Zahnrad-Menüs der Klick auf die Statuszeile als Weg zur Diagnose. Die Nennung des Konfigurationsorts und beider Änderungswege bleibt unverändert. Nachweis: der Test zum Abschlusssatz in `tests/test_setup.py` auf den neuen Satz umgestellt und grün.
- [x] 2.2 `control.open_settings` und `SETTINGS_RESTART_HINT` unverändert stehen lassen (design D28). In `src/backrec/cli.py` nur den Hinweistext von `update` ohne Archiv anpassen, der bisher Weg B als zweiten Weg nannte; Namen, Rückgabewerte und Verhalten aller Kommandos bleiben unverändert. Nachweis: die bestehenden Tests in `tests/test_control.py` zu `open_settings` bleiben unangetastet grün, und der Test zu `update` ohne Archiv prüft den einen verbliebenen Weg.

## 3. Texte

- [x] 3.1 `LIES-MICH-ZUERST.txt` anpassen: „Im Alltag" nennt REC und STOP und das erneute Ausführen von `Setup.cmd` als Weg zu den Einstellungen; „Wenn etwas rot ist" nennt den Klick auf die Statuszeile und das Weiterschicken der Datei; „Aktualisieren" nennt nur noch das Entpacken über den Ordner und `Setup.cmd`. Kodierung (UTF-8 mit BOM), CRLF, höchstens 40 Zeilen und 80 Zeichen je Zeile bleiben eingehalten. Nachweis: `tests/test_docs.py` grün, einschließlich der auf die Statuszeile umgestellten Prüfung, und die Anleitungsprüfung des Release-Kommandos in `tests/test_release.py` grün.
- [x] 3.2 `README.md` (englisch) an den drei Stellen anpassen, die das Zahnrad-Menü beschreiben: die Übersicht des Fensters, der Abschnitt über die Wege zu den Kommandos und der Abschnitt über die beiden Aktualisierungswege. Nachweis: `Grep` auf `gear` in `README.md` findet nichts mehr, und `tests/test_docs.py` bleibt grün.
- [x] 3.3 `ABNAHME.md` anpassen: den Abschnitt zum Zahnrad-Menü durch einen Punkt „Klick auf die Statuszeile öffnet die Diagnose" ersetzen, im Punkt zum Aktualisieren Weg B streichen und Weg A allein stehen lassen, im Punkt „Einstellungen auf beiden Wegen ändern" den Menüteil entfernen, im Punkt zur Neueinrichtung und im Kollegenweg das Zahnrad durch die Statuszeile ersetzen. Nichts streichen, was weiterhin gilt. Nachweis: `Grep` auf `Zahnrad` in `ABNAHME.md` findet nichts mehr, jeder verbliebene Punkt nennt weiterhin eine existierende Spec.

## 4. Tests

- [x] 4.1 In `tests/test_app.py` die Menü-Tests entfernen: die fünf Einträge, die Position der Einstellungen in der Suite-Reihenfolge, der Weg des Menüeintrags zu `control.open_settings`, die beiden Tests zu `menu_entry` und die beiden zu `update_question`. Nachweis: `pytest -q tests/test_app.py` läuft ohne Sammelfehler.
- [x] 4.2 Neuer Test: Ein Klick auf die Statuszeile ruft die Diagnose in einem eigenen Thread auf, mit `report=True` und `open_report=True`. Nachweis: der Test ersetzt `control.run_doctor` und `threading.Thread` und prüft beides.
- [x] 4.3 Neuer Test: Der Bericht wird geschrieben und das Öffnen läuft gegen ein ersetztes `os.startfile`, also ohne einen Editor auf dem Prüfrechner. Nachweis: nach dem Lauf liegt eine Berichtsdatei im Protokollverzeichnis und das Ersatz-`os.startfile` wurde genau einmal mit deren Pfad gerufen.
- [x] 4.4 Neuer Test: Ein zweiter Klick während eines laufenden Berichts bleibt wirkungslos, und der Text der Statuszeile bleibt unverändert — auch wenn eine Aufnahme läuft. Nachweis: der Test zählt die Aufrufe von `control.run_doctor` und vergleicht den Text der Statuszeile vor und nach dem Klick.
- [x] 4.5 Neuer Test: Das Fenster trägt keine Menü-Schaltfläche mehr, und REC, STOP und Discard sind sichtbar. Nachweis: der Test prüft, dass `RecorderApp` kein Merkmal `menu_button` führt, und dass die drei Bedienelemente abgebildet sind.
- [x] 4.6 In `tests/test_docs.py` die Prüfung auf „Zahnrad" in der Anleitung durch eine Prüfung auf die Statuszeile und die Diagnose ersetzen, und sicherstellen, dass die Anleitung kein Menü mehr nennt. Nachweis: `pytest -q tests/test_docs.py` grün.

## 5. Abschluss

- [x] 5.1 Vollständiger Lauf der Testsuite. Nachweis: kein Fehlschlag; die Gesamtzahl weicht gegenüber dem Ausgangsstand von 432 nur um die entfernten und die neu hinzugekommenen Tests ab, und die Abweichung ist im Ergebnisbericht benannt.
- [x] 5.2 `openspec validate slim-window-menu --strict` und nach dem Archivieren `openspec validate --specs --strict` mit 6 von 6 gültigen Fähigkeiten. Nachweis: beide Kommandos melden gültig.
- [x] 5.3 Change archivieren und Schlusscommit setzen; `git status` ist danach sauber. Nachweis: `openspec archive slim-window-menu --yes` meldet Erfolg, `git status --short` gibt nichts aus.
