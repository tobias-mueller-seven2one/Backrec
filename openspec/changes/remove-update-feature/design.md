## Context

Backrec ist am 12.09.2026 mit einer Update-Mechanik gebaut worden, die der damalige Auftrag zu verlangen schien: ein Kommando mit Archivauswahl, ein Manifest als Vergleichsmaßstab, ein Helfer außerhalb des Ordners, der das laufende Programm ersetzt, und eine Update-Erkennung in der Einrichtung. Am 14.09.2026 hat der Change `slim-window-menu` den Bedienweg aus dem Fenster genommen, die Mechanik selbst aber stehen gelassen.

Am 15.09.2026 hat Tobias Müller die fachliche Entscheidung getroffen: **Die Anwendungen der MemoSuite haben keine Aktualisierungsfunktion.** Ein neuer Stand wird beschafft, indem das Programm neu heruntergeladen wird und den vorhandenen Stand ersetzt — fachlich ein vollständiges Löschen mit anschließendem normalem Setup. Dieser Vorgang wird nirgendwo beschrieben oder behandelt; er braucht keine Beschreibung, weil er aus zwei Vorgängen besteht, die jeder für sich bereits vollständig dokumentiert sind.

Damit ist der Auftrag dieses Change ein Rückbau, kein Umbau. Die Frage ist nicht, wie Aktualisieren künftig aussieht, sondern wie der letzte Rest davon verschwindet, ohne dass etwas mitgeht, das aus anderen Gründen gebraucht wird.

## Goals / Non-Goals

**Goals**

- Jede Zeile Code, jede Datei, jedes Kommando, jedes Spec-Requirement und jede Doku-Passage zur Aktualisierung des Programms entfernen.
- Die Abwesenheit durch Tests absichern, damit sie nicht beim nächsten Missverständnis zurückkehrt.
- Alles unberührt lassen, was Versionsauskunft, Release-Bau, Einrichtung, Deinstallation oder Verknüpfung für sich selbst brauchen.

**Non-Goals**

- Keinen Ersatzvorgang bauen, auch keinen abgespeckten („Version prüfen", „neuen Stand holen").
- Keinen Ersatztext schreiben, der erklärt, wie man an eine neue Fassung kommt.
- Die Einrichtung nicht anfassen, außer an den Stellen, die vom Vorgängerstand wissen.
- „Aktualisieren" im Sinn von Oberfläche oder Daten nicht anfassen — Pegelanzeige, Statuszeile, `dict.update`, `update_idletasks`.

## Decisions

### D1: Rückbau statt Deaktivierung

Das Kommando bleibt nicht als Platzhalter stehen, der eine Erklärung ausgibt, und das Modul bleibt nicht ungenutzt liegen. Beides wird gelöscht.

**Begründung:** Ein Kommando, das sagt „gibt es nicht mehr", ist ein Kommando über das Aktualisieren — und die Vorgabe lautet, dass das Thema nicht existiert. Ein ungenutztes Modul ist schlimmer: Es erscheint in der Dateiliste, es hat Tests, und der nächste, der es sieht, hält es für einen Bestandteil. Der Rückbau ist nur dann abgeschlossen, wenn eine Volltextsuche nach dem Thema nichts mehr findet.

### D2: `argparse` lässt ein unbekanntes Kommando von selbst scheitern

`update` verschwindet aus dem Parser und aus `_COMMANDS`. Es braucht keine Sonderbehandlung für den Aufruf `backrec update` — Subparser sind in `argparse` eine geschlossene Menge; ein unbekannter Name endet mit `SystemExit(2)` und der Liste der bekannten Kommandos.

**Begründung:** Das ist genau die Antwort, die ein Werkzeug auf ein Kommando geben soll, das es nicht gibt, und sie kostet keine Zeile Code. Ein eigener Zweig würde das Thema wieder in die Kommandozeile holen.

### D3: `VERSION`, `read_version` und `parse_version` bleiben — `is_newer` geht

Die drei Bausteine der Versionsverarbeitung werden getrennt betrachtet, nicht als Block.

- `read_version` liefert die Versionsauskunft für `about`, `status`, die Diagnose und die Kopfzeile der Einrichtung. Bleibt.
- `parse_version` prüft beim Release-Bau, ob die Version die Form `JJJJ.MM.N` hat. Bleibt.
- `is_newer` vergleicht zwei Versionen und beantwortet damit ausschließlich die Frage „ist dieses Archiv neuer als das Eingerichtete". Geht.

**Begründung:** Versionsauskunft ist keine Update-Funktion — das steht so in der Vorgabe. Ein Vergleich zweier Versionsstände dagegen hat nur einen denkbaren Zweck, und der entfällt. Der Modul-Docstring von `version.py` nennt heute das Aktualisieren als zweiten Grund für die Importfreiheit; der erste Grund — die Einrichtung liest die Version, bevor eine Laufzeit existiert — trägt allein.

### D4: `installed.json` bleibt, die Update-Erkennung darauf geht

`state\installed.json` hält fest, welche Version zuletzt erfolgreich eingerichtet wurde. Der Datensatz bleibt; was entfällt, ist der Vergleich mit der vorliegenden Version und der Zweig, der daraus „es ist ein Update" schließt.

**Begründung:** Der Datensatz ist eine Tatsache über die Installation und wird von der Auskunft mitgeführt. Die Auswertung „vorher war X, jetzt ist Y, also ist das ein Update" ist dagegen genau die Update-Erkennung, die die Vorgabe ausschließt. `read_installed_version` und `write_installed_version` bleiben deshalb bestehen; `control.setup` schreibt weiter, liest aber nicht mehr zum Vergleich.

### D5 (revidiert am 15.09.2026): Der Stopp bleibt, unbedingt und ohne Versionserkennung

**Ursprünglicher Wortlaut (überholt, nicht umgesetzt zu lassen):**

> **D5: Das Beenden einer laufenden Instanz verschwindet mit dem Update-Zweig**
>
> Heute beendet die Einrichtung eine laufende Instanz genau dann, wenn sie einen Versionswechsel erkennt (`control.setup`, Zweig `updating`). Mit dem Zweig geht auch dieser Aufruf.
>
> **Begründung:** Die Vorgabe erlaubt das Stoppen, „soweit das Setup es für sich selbst braucht" — und die Einrichtung braucht es nicht: sie baut die Umgebung über `uv sync` und den Bootstrap, und beide arbeiten, während Backrec läuft; das Fenster wird am Ende ohnehin nur angeboten, nicht erzwungen. Der Stopp war ausschließlich der erste Schritt der Selbstersetzung. Er bleibt vollständig erhalten, wo er hingehört: im Kommando `stop` und in der Deinstallation, die ihn ausdrücklich braucht und behält.

**Geltende Entscheidung:** Die Versionserkennung entfällt wie beschrieben — der Vergleich mit `read_installed_version`, der Zweig `updating` und die Meldung über eine neue Fassung. Der Stopp einer laufenden Anwendung bleibt und wird von der Versionserkennung entkoppelt: `control.setup` beendet eine laufende Anwendung **immer**, bevor an der Umgebung gearbeitet wird, unabhängig davon, ob sich die Version geändert hat.

**Begründung:** Die ursprüngliche Begründung stützte sich darauf, dass `SYNC_COMMAND` in `control.py` bewusst ohne `--reinstall-package backrec` arbeitet. Das ist technisch richtig und trotzdem nicht ausreichend:

1. **Der Stopp gehört zu dem, was `scripts\win\bootstrap-uv.ps1` tut, nicht zu dem, was `control.py` tut.** Der Bootstrap steht außerhalb der Umgebung, läuft vor jeder Einrichtung und ersetzt mit `--reinstall-package backrec` genau den Paketinhalt in der `.venv`, aus der eine laufende Anwendung ihren Code bezogen hat. Sie läuft danach mit altem Code weiter, ohne dass irgendwer es merkt. Wer die Umgebung ersetzt, darf nichts daraus laufen lassen.
2. **Einheitlichkeit über die Suite.** AutoMemo und der Proxy haben den Stopp behalten und lediglich von der Versionserkennung entkoppelt; AMD-Transcription und MemoBoard ziehen nach. Die Konvention lebt davon, dass die fünf Werkzeuge sich gleich verhalten; Backrec als einziges ohne Stopp wäre eine Abweichung ohne fachlichen Gewinn.

Der Stopp ist damit Setup-Hygiene und keine Aktualisierungsfunktion. Er liest keine Version, vergleicht keine und meldet keinen Versionswechsel; die Meldung lautet schlicht „Die laufende Anwendung wird vorher beendet."

**Ort im Ablauf:** als erste Handlung von Schritt 2 („Arbeitsumgebung"), vor `_ensure_environment`. Damit steht er vor jedem Zugriff auf die Umgebung und bleibt zugleich innerhalb der gezählten Schritte — eine Assistentenzeile zwischen zwei Schritten widerspräche der Ausgabekonvention der Einrichtung.

**Bewusst getragene Nebenwirkung (wie im Proxy, dort D8):** Wer `Setup.cmd` neben einer laufenden Anwendung startet — etwa um eine Einstellung zu ändern —, verliert das Fenster immer. Schritt 7 bietet den Start danach wieder an; die Einstiegsanleitung nennt die Nebenwirkung in „Im Alltag".

**Unberührt:** Der Stopp bleibt zusätzlich, wo er ohnehin hingehört — im Kommando `stop` und in der Deinstallation.

### D6: Das Manifest geht ganz, nicht nur seine Auswertung

`release-manifest.json` verschwindet aus dem Release-ZIP, aus `state\`, aus `paths`, aus `release` und aus der Ausschlussliste des Release-Baus.

**Begründung:** Das Manifest hatte genau zwei Verwender: den Abgleich entfallener Altdateien und die Prüfsummenkontrolle beim Einspielen eines Archivs. Beide entfallen. Ein Manifest ohne Leser ist eine zweite Wahrheit über den Dateibestand, die niemand pflegt und die beim nächsten Lesen falsch ist. Der Eintrag `MANIFEST_NAME` in `EXCLUDED_PATTERNS` geht mit: er hielt eine Datei aus dem Paket, die nicht mehr entsteht — der Release-Bau legte sie gesondert hinein.

**Risiko, bewusst getragen:** Ein Release-ZIP führt danach keine Prüfsummen mehr. Wer prüfen will, ob ein Download unverfälscht ist, hat dafür im ZIP-Format die CRC-Prüfung jedes Eintrags, und ein beschädigtes Archiv scheitert beim Entpacken. Eine kryptographische Zusicherung leistete das Manifest ohnehin nicht — es lag im selben Archiv wie die Dateien, die es beschrieb.

### D7: Die Diagnose-Prüfung auf Nachbarordner entfällt

`doctor.stale_update_folders` sucht neben dem Repository nach `<Name>.update` und `<Name>.old-*`. Die Funktion, das Feld `Observations.stale_folders` und der Check `state.stale_folders` entfallen.

**Begründung:** Beide Namensmuster entstanden ausschließlich im Update-Vorgang — `.update` als Staging-Ordner, `.old-*` aus dem früheren Ordnertausch. Ohne den Vorgang gibt es sie auf keinem Rechner mehr, der neu eingerichtet wird. Auf einem Rechner, der eine solche Fassung gesehen hat, bleibt ein Ordner im Dateimanager sichtbar liegen und stört nichts; die Diagnose hätte ihn ohnehin nur genannt und nicht angefasst.

**Verworfen:** die Prüfung als allgemeine „Nachbarordner mit ähnlichem Namen"-Warnung zu behalten. Sie hätte kein Muster mehr, nach dem sie suchen könnte, und jeder Ordner neben dem Werkzeug ist eine legitime Sache des Benutzers.

### D8: Die Anleitung führt sieben Abschnitte, nicht acht mit einem leeren

`LIES-MICH-ZUERST.txt` verliert den Abschnitt „Aktualisieren"; `GUIDE_SECTIONS` in `release.py` verliert den Eintrag, und die Spec spricht von sieben Abschnitten.

**Begründung:** Die Abschnittsliste ist eine maschinell geprüfte Reihenfolge; ein Eintrag, der auf keinen Text mehr zeigt, ließe den Release-Bau bei jedem Lauf scheitern. Ein ersatzweiser Abschnitt — „So kommst du an eine neue Version" — ist durch die Vorgabe ausdrücklich ausgeschlossen. Die Anleitung wird dadurch zwei Zeilen kürzer und bleibt unter allen Grenzen.

### D9: Zwei Tests sichern die Abwesenheit

Ergänzt werden: die Kommandozeile kennt kein Kommando zum Aktualisieren (Aufruf endet mit `SystemExit`, und `update` steht in keiner Kommandotabelle), und unter `scripts/win` liegt kein Update-Helfer.

**Begründung:** Ein Rückbau, den nichts absichert, kommt zurück — das ist hier bereits einmal passiert. Ein Test, der eine Abwesenheit prüft, ist der einzige Ort, an dem die Entscheidung vom 15.09.2026 im Code selbst steht.

### D10: Der Stopp gehört zusätzlich in das Bootstrap — als Aufruf des vorhandenen Kommandos

D5 setzt den Stopp als erste Handlung von Schritt 2 in `control.setup`. Auf dem Doppelklick-Weg ist das zu spät: `Setup.cmd` ruft zuerst `scripts\win\bootstrap-uv.ps1` auf, und dieses Skript führt selbst ein `uv sync --locked --no-dev --no-editable --reinstall-package backrec` aus. Der Kollegenweg trifft die laufende Anwendung also vor jedem Stopp. Das Bootstrap beendet deshalb künftig selbst, als erste Handlung seines Abschnitts „Arbeitsumgebung", vor dem Aufräumen einer halben `.venv` und vor dem Sync.

**Mechanik:** Das Skript baut nichts nach. Es prüft, ob `.venv\Scripts\backrec.exe` existiert — der Einstiegspunkt aus `[project.scripts]`, der einzige, den dieses Repository hat —, ruft ihn mit `stop` auf und wartet auf sein Ende. Frist, Anforderungsdatei und Prozessidentität bleiben vollständig in `control.stop`; das Skript kennt weder eine PID noch eine Sekundenzahl.

**Begründung:**

1. **Ein Stopp, eine Wahrheit.** Eine zweite Stopp-Mechanik in PowerShell wäre ein zweiter Ort mit einer eigenen Frist, die niemand mit `STOP_TIMEOUT_SECONDS` abgleicht. Sie würde zudem an der Aufnahme-Eigenheit dieses Werkzeugs vorbeigehen: `stop` fordert das Beenden über eine Datei an, die Anwendung schließt eine laufende Aufnahme sauber ab (stoppen, mischen, kopieren) und beendet sich erst danach. Ein `Stop-Process` aus dem Skript würde genau diesen Abschluss abschneiden.
2. **Der Sync ersetzt den Paketinhalt.** `--reinstall-package backrec` tauscht die Dateien in der `.venv`, aus der eine offene Anwendung ihren Code bezogen hat. Sie läuft danach mit Code weiter, den es auf der Platte nicht mehr gibt — ohne Fehler, ohne Hinweis. Dass Backrec als einziges Werkzeug der Suite kein `[project.gui-scripts]` führt und daher keine `.exe` der Anwendung in `.venv\Scripts\` liegt, entschärft nur die Dateisperre, nicht den stillen Altstand.
3. **Einheitlichkeit über die Suite.** AMD-Transcription und AutoMemo ziehen denselben Schritt gerade nach.

**Kein Abbruch:** Ein fehlgeschlagener oder mit Fehlercode endender Aufruf beendet das Bootstrap nicht. Eine nicht aufgebaute Arbeitsumgebung ist das schlechtere Ergebnis, und `control.setup` versucht den Stopp ohnehin ein zweites Mal. Fehlt die `.venv` oder der Einstiegspunkt, passiert nichts — ein erstes Einrichten hat nichts zu stoppen.

**Ausgabe:** Der Aufruf erbt die Konsole des Setups, wird also nicht umgeleitet. Der Kollege liest zuerst „Eine laufende Anwendung wird zuerst beendet." und darunter die Antwort des Kommandos selbst („Beendet." oder „Es läuft nichts.").

**Verworfen:**

- **Den Stopp aus `control.setup` herausnehmen, weil das Bootstrap ihn jetzt macht.** Dann wäre der Entwicklerweg — `backrec setup` ohne `Setup.cmd` — ohne jede Absicherung. Der Aufruf in `control.setup` bleibt und ist auf dem Doppelklick-Weg folgenlos: das Bootstrap hat den Zustandsdatensatz bereits entfernt, `instance.running_instance` liefert `None`, und `_stop_running_application` kehrt ohne Meldung zurück. Eine doppelte Zeile entsteht nur, wenn der erste Stopp wirklich nicht gegriffen hat — und dann ist sie richtig.
- **Das Bootstrap den Sync erst nach dem Setup ausführen lassen.** Der Sync muss vor dem Setup laufen: das Setup läuft in der Umgebung, die der Sync aufbaut.
- **Ein eigenes `Stop-Process` im Skript, damit auch eine hängende Anwendung sicher weg ist.** Siehe Begründung 1: Es würde eine laufende Aufnahme abschneiden. Das Erzwingen nach Ablauf der Frist gehört in `control.stop`, wo es bereits steht.

**Preis:** Auf dem Doppelklick-Weg kann die Einrichtung jetzt bis zu einer halben Minute stillstehen, bevor die erste Zeile über die Arbeitsumgebung kommt — die Frist, die `control.stop` einer laufenden Aufnahme für Mischen und Kopieren einräumt. Das Skript kennt diese Frist nicht und wartet einfach; Fortschrittszeilen des Kommandos erscheinen dabei im selben Fenster.

## Risiken

- **Ein Kollege mit einer laufenden alten Fassung erwartet das Kommando.** Getragen: `update` erschien nie in der Einstiegsanleitung, war nur über die Kommandozeile erreichbar und richtete sich an Tobias. Der Aufruf endet mit der Liste der bekannten Kommandos.
- **Ein Rechner trägt noch `state\release-manifest.json` und einen `.update`-Ordner.** Getragen: Beides ist nach dem Rückbau eine Datei bzw. ein Ordner ohne Leser. Sie stören nichts und werden beim Löschen des Installationsordners bzw. des Zustandsverzeichnisses mit entfernt.
- **Der Rückbau übersieht eine Stelle.** Begegnet: Die Verifikation schließt mit einer Volltextsuche über das ganze Repository nach `aktualisier`, `update`, `manifest` und `apply-update` ab; jeder verbliebene Treffer wird einzeln begründet oder entfernt.
- **Ein Test prüft weiterhin gegen ein Manifest im Paket.** Begegnet: `tests/test_release.py`, `tests/test_setup.py`, `tests/test_root_files.py` und `tests/test_control.py` werden vollständig auf Update-Bezug durchgesehen, nicht nur an den Stellen, die der Compiler bemängelt.
