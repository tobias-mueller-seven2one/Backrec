## Why

`control.stop` räumt einer laufenden Anwendung 30 Sekunden ein, sich zu beenden (`src/backrec/control.py:51`). Innerhalb dieser Frist muss eine laufende Aufnahme vollständig nachbereitet werden: beide Aufnahmefäden beenden (je bis zu 5 Sekunden, zusammen bis zu 10), mischen (ffmpeg `amix` mit eigener Frist von 120 Sekunden, `src/backrec/merge.py:21`) und die gemischte Datei verifiziert in den Zielordner kopieren (`src/backrec/delivery.py:55-86`). Bei einer zweistündigen Aufnahme bleiben nach dem ersten Schritt rund 20 Sekunden für das Mischen und das Kopieren einer Datei von etwa 600 MB. Das reicht nicht.

Die Frist reißt dann, `instance.terminate_tree` beendet den Prozessbaum samt ffmpeg hart, und damit läuft kein `delivery._failed()` mehr: es gibt **keine Meldung, kein Fenster, keinen Hinweis**. Die beiden Rohspuren bleiben zwar liegen (`src/backrec/delivery.py:124-126`), aber niemand erfährt davon, und es gibt kein Kommando, die Mischung nachzuholen. Der Schaden ist nicht der Datenverlust, sondern das unbemerkte Verschwinden.

Der Widerspruch steckt in den Zahlen selbst: das Mischen allein darf 120 Sekunden dauern, die Frist darüber liegt bei 30. Der Kommentar bei `STOP_TIMEOUT_SECONDS` beruft sich auf die ursprüngliche Zusage „lang genug für Threadende, Mischung und Kopie einer langen Aufnahme", rechnet die Summe der drei Schritte für lange Aufnahmen aber nicht durch.

**Warum jetzt:** Bisher wurde nur bei `stop`, bei der Deinstallation oder bei einer Aktualisierung gestoppt — allesamt Vorgänge, die jemand bewusst auslöst. Seit dem Change `remove-update-feature` beendet `scripts\win\bootstrap-uv.ps1` bei **jedem** Setup-Lauf unbedingt eine laufende Anwendung. Ein Kollege, der `Setup.cmd` doppelklickt, während eine Aufnahme läuft, trifft den Fall damit im Regelbetrieb.

## What Changes

- **Die Frist folgt der tatsächlichen Nachbereitung statt einer festen Zahl.** Die Anwendung meldet während der Abschlusssequenz in kurzen Abständen, dass sie arbeitet; `control.stop` verlängert die Frist, solange dieses Lebenszeichen weiterläuft, und beendet hart, sobald es ausbleibt.
- **Ein neues Zustandszeichen `state\finishing.active`.** Es sagt „die Anwendung bereitet gerade nach" und ist vom Aufnahme-Merker `recording.active` getrennt: der eine beantwortet „wird gerade Ton aufgenommen", der andere „ist die Anwendung noch beschäftigt". `instance.mark_finishing`, `instance.clear_finishing`, `instance.finishing_mark` und `instance.FinishingBeacon` kommen hinzu.
- **`app._do_stop` schreibt das Lebenszeichen**, über einen eigenen Faden, weil das Mischen ein einzelner blockierender Aufruf von bis zu zwei Minuten ist.
- **Drei Fristen statt einer** in `control.py`: `STOP_TIMEOUT_SECONDS` (unverändert 30 s, die Grundfrist ohne Nachbereitung), `STOP_GRACE_SECONDS` (wie lange nach dem letzten Lebenszeichen weiter gewartet wird) und `STOP_LIMIT_SECONDS` (die Obergrenze, die auch ein endlos schlagendes Lebenszeichen nicht überschreitet).
- **Ein hartes Beenden steht künftig unmissverständlich im Protokoll**, mit dem Pfad des Aufnahmeordners, in dem die Rohspuren liegen. `StopResult` führt dafür das Feld `raw_takes`, und die Meldung des Kommandos nennt den Ordner.
- **Die Einrichtung meldet ein erzwungenes Beenden als Warnung.** Heute zeigt `_stop_running_application` nur einen misslungenen Stopp; ein erzwungener gilt als Erfolg und blieb stumm.
- **`merge.MERGE_TIMEOUT_SECONDS` bleibt bei 120**, bekommt aber einen Test, der die Obergrenze des Stopps dagegen prüft, damit die beiden Zahlen nicht wieder auseinanderlaufen.

Nicht-Ziele:

- Keine Schätzung der Aufnahmelänge und keine von ihr abgeleitete Frist.
- Kein Kommando, das eine Mischung nachträglich anstößt. Der Change sorgt dafür, dass der Abschluss durchläuft; ein Nachhol-Weg wäre ein eigener Auftrag.
- Keine Änderung an Aufnahme, Mischung, Ablage, Preflight, Einrichtungsschritten, Diagnose oder Fenstergestaltung.
- Kein Anfassen des offenen Change `remove-update-feature`. Der Fehler ist älter und unabhängig von ihm.

## Capabilities

### New Capabilities

Keine. Es kommt keine Fähigkeit hinzu.

### Modified Capabilities

- `run-lifecycle`: „Beenden von außen" verlangt künftig, dass die Frist die tatsächliche Nachbereitung abdeckt statt sie abzuschneiden, dass ein Stopp ohne Nachbereitung nicht langsamer wird, dass eine Obergrenze greift und dass ein erzwungenes Beenden den Ort der Rohspuren nennt. „Sauberes Beenden durch den Benutzer während einer Aufnahme" verlangt zusätzlich, dass die Abschlusssequenz ihr Arbeiten nach außen meldet.

## Impact

- Geänderter Code: `src/backrec/paths.py` (Name und Pfad des neuen Zustandszeichens), `src/backrec/instance.py` (Lebenszeichen und sein Faden), `src/backrec/app.py` (`_do_stop` schreibt das Lebenszeichen), `src/backrec/control.py` (`stop`, `StopResult`, `_stop_running_application`, die drei Fristen), `src/backrec/cli.py` (Meldung des Kommandos `stop`).
- Tests: `tests/test_control.py` (Fristverhalten mit gestellter Zeit), `tests/test_instance.py` (Lebenszeichen), `tests/test_app.py` (`_do_stop` meldet), `tests/test_setup.py` (Warnung bei erzwungenem Beenden).
- Dokumente: `README.md` (englisch, Entwicklerdoku) — die Kommandotabelle nennt heute „waits 30 s, then kills the tree".
- Nicht betroffen: Aufnahme, Mischung, Ablage, Konfiguration, Verknüpfung, Diagnose, Release-Bau, `LIES-MICH-ZUERST.txt`. Die Einstiegsanleitung kennt weder Frist noch Kommando; sie bleibt unverändert.
- Keine neue Abhängigkeit, kein neues Modul, kein geändertes Dateiformat.
