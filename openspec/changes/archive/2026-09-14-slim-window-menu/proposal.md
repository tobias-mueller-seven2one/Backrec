## Why

Das Zahnrad-Menü des Backrec-Fensters trägt heute fünf Einträge — „Aktualisieren…", „Diagnose", „Logs öffnen", „Einstellungen öffnen" und „Info" (`src/backrec/app.py:65-69`, `src/backrec/app.py:308-320`). Es entstand als Ersatz für ein Tray-Menü, das Backrec als einzige interaktive Anwendung der Suite nicht hat. Tobias hat es am 14.09.2026 im Betrieb angesehen und entschieden: für ein Fenster, das 280 px breit ist und drei Knöpfe für eine Aufnahme trägt, sind fünf Menüeinträge zu viel.

Fachlich ist der größere Teil davon redundant. **Aktualisieren** hat mit Weg A bereits einen vollständigen Weg: neues Release-ZIP über den Ordner entpacken und `Setup.cmd` erneut doppelklicken; die Einrichtung erkennt den Versionswechsel selbst, beendet eine laufende Instanz und räumt Altdateien weg. **Einstellungen ändern** hat seit dem letzten Change denselben vollständigen Weg über `Setup.cmd`: ein erneuter Lauf zeigt die Übersicht der aktuellen Werte und fragt „Einstellungen ändern?" — und fragt dabei jeden Schlüssel einzeln ab, was ein im Editor geöffnetes TOML einem Kollegen gerade nicht abnimmt. **Logs, Info und Diagnose** sind für den Adressaten ein einziges Anliegen: „hier stimmt etwas nicht, was schicke ich Tobias?" Der Diagnosebericht beantwortet es vollständig — er nennt in seinem Kopf Version, Repository- und Konfigurationspfad, und er liegt im Logordner neben den Protokollen.

Bleibt genau ein Anliegen, das das Fenster selbst tragen muss, und ein Ort, der es ohne zusätzliches Bedienelement tragen kann: die Statuszeile, die ohnehin sagt, wie es gerade steht.

## What Changes

- **Das Zahnrad-Menü entfällt vollständig.** Die Schaltfläche, ihr Hovertext, das `tk.Menu` mit den fünf Einträgen und die Sperrlogik für eine laufende Aufnahme verschwinden aus dem Fenster. Das Fenster trägt danach REC, STOP, Discard, die beiden Pegelzeilen und die Statuszeile — bei unveränderten 280 px Breite.
- **Die Statuszeile wird klickbar** und öffnet die Diagnose: derselbe Vorgang wie das Kommando `doctor`, also Bericht schreiben und im Standard-Editor öffnen, in einem eigenen Thread und nie im Aufnahme-Thread, ohne modalen Dialog. Ihr Hovertext lautet „Klick öffnet die Diagnose".
- **Der Klick bleibt während einer Aufnahme erlaubt.** Die Diagnose liest nur; der Bericht entsteht, ohne die laufende Aufnahme zu berühren. Damit entfällt auch der Grund für die Sperrlogik, die es im Menü brauchte.
- **BREAKING (Bedienweg, nicht Kommando): Weg B des Aktualisierens entfällt** — ein ZIP lässt sich nicht mehr aus dem Fenster auswählen. Für Kollegen bleibt Weg A der einzige und dokumentierte Weg. `update <zip>` und `update --git` bleiben als Kommandos unverändert.
- **BREAKING (Bedienweg): „Einstellungen öffnen" entfällt aus dem Fenster.** Geändert wird über einen erneuten Lauf von `Setup.cmd`. `control.open_settings` bleibt als Funktion der Control-Surface bestehen und unverändert getestet.
- **CLI unverändert:** `setup`, `start`, `stop`, `status`, `doctor`, `logs`, `shortcut`, `uninstall`, `update`, `release` und `about` behalten Namen, Verhalten und Ausgaben. Kein Kommando kommt hinzu, keines verliert eine Fähigkeit — nur das Fenster verliert Bedienwege.
- **`LIES-MICH-ZUERST.txt`:** die Absätze „Im Alltag", „Wenn etwas rot ist" und „Aktualisieren" beschreiben den neuen Weg — Klick auf die Statuszeile öffnet die Diagnose; Aktualisieren heißt neues Archiv über den Ordner entpacken und `Setup.cmd` erneut; Einstellungen ändern heißt `Setup.cmd` erneut. Grenzen und Abschnittsfolge der Anleitung bleiben unverändert.
- **Abschlusszusammenfassung der Einrichtung:** der Satz über das Zahnrad-Menü wird durch den Satz über die Statuszeile ersetzt. Die Nennung des Konfigurationsorts und beider Änderungswege bleibt, wie sie ist.
- **README** (englisch, Entwicklerdoku): die drei Stellen, die das Zahnrad-Menü beschreiben, beschreiben künftig die klickbare Statuszeile und den Wegfall von Weg B.

Nicht-Ziele: Die vier Tray-Werkzeuge der Suite bleiben unverändert — ihr Tray-Menü und dessen suiteweite Reihenfolge sind von dieser Entscheidung nicht berührt. Aufnahmekern, Ablage, Preflight, Einrichtung, Diagnoseprüfungen und Verknüpfung bleiben ebenfalls unberührt.

## Capabilities

### New Capabilities

Keine. Alle sechs Fähigkeiten bestehen bereits.

### Modified Capabilities

- `run-lifecycle`: „Menü im Anwendungsfenster" wird ersetzt durch „Diagnose über die Statuszeile des Fensters"; „Öffnen der Einstellungen aus dem Menü" entfällt; „Zugang zu den Protokollen" verliert die Forderung nach einem Menüweg.
- `diagnostics`: „Bericht als weitergebbare Textdatei" nennt den Zugangsweg — Klick auf die Statuszeile — und sichert, dass er auch während einer Aufnahme offensteht.
- `tool-setup`: „Aktualisierung über ein neues Release-ZIP" führt für Kollegen nur noch Weg A; „Reihenfolge, Meldungen und Abschluss der Einrichtung" und „Einstiegsanleitung im Wurzelverzeichnis" nennen die Statuszeile statt des Menüs.
- `tool-configuration`: „Einstellungen im Setup ändern" ist der einzige Weg ohne Kommandozeile.

## Impact

- Code: `src/backrec/app.py` (Menü, Zahnrad, Tooltip, Sperrlogik entfallen; Statuszeile wird klickbar), `src/backrec/control.py` (`_closing_note`), `src/backrec/cli.py` (nur prüfen, keine Änderung erwartet).
- Dokumente: `LIES-MICH-ZUERST.txt`, `README.md`, die Handabnahme (seit 15.09.2026 suite-weit geführt, nicht mehr im Repo).
- Tests: `tests/test_app.py` (Menü-Tests entfallen, Tests der Statuszeile kommen hinzu), `tests/test_docs.py` (Anleitungsprüfung), `tests/test_setup.py` (Abschlusssatz).
- Nicht betroffen: Aufnahme, Mischung, Ablage, Diagnoseprüfungen, Verknüpfung, Release-Bau, die vier Nachbarwerkzeuge.
