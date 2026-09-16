## Context

Siehe `proposal.md` — Why. Zum Stand, der diesen Entwurf formt:

`control.stop` schreibt die Beenden-Anfrage als Datei und wartet anschließend in einer Schleife auf das Verschwinden des Prozesses (`src/backrec/control.py:862-924`). Die Frist ist eine einzige Zahl, `STOP_TIMEOUT_SECONDS = 30.0` (`src/backrec/control.py:51`), und sie beginnt in dem Moment zu laufen, in dem die Anfrage geschrieben wird.

Auf der anderen Seite liest die 150-ms-Schleife des Fensters die Anfrage (`src/backrec/app.py:630-631`) und ruft `_request_shutdown`. Läuft keine Aufnahme, endet die Anwendung sofort. Läuft eine, startet `_do_stop` in einem eigenen Faden (`src/backrec/app.py:431-455`) und arbeitet drei Schritte ab:

1. `mic_recorder.stop(timeout=5)` und `system_recorder.stop(timeout=5)` — bis zu 10 Sekunden, bevor irgendetwas anderes beginnt.
2. `_merge_and_save()` → `delivery.finish()` → `merge.merge_audio_files()`: ein einzelner blockierender `subprocess.run` mit eigener Frist von `MERGE_TIMEOUT_SECONDS = 120` (`src/backrec/merge.py:21`).
3. `delivery.copy_verified()`: `shutil.copy2` in den Zielordner plus Größenvergleich (`src/backrec/delivery.py:55-86`).

Die 30 Sekunden decken die Summe für lange Aufnahmen nicht. Schon Schritt 2 allein darf viermal so lange dauern wie die Frist darüber.

Zwei Eigenschaften des Bestands sind für die Entscheidung wichtig:

- `instance.clear_recording()` läuft in `_do_stop` **vor** dem Mischen (`src/backrec/app.py:445`). Der Merker `recording.active` beantwortet „wird gerade Ton aufgenommen", nicht „ist die Anwendung noch beschäftigt". Als Signal für die Nachbereitung ist er nachweislich unbrauchbar, weil er genau vor dem längsten Schritt gelöscht wird.
- Ein hartes `instance.terminate_tree` läuft an jedem `finally` vorbei. Es gibt danach kein `delivery._failed()`, keinen Dialog, keinen Protokolleintrag über den Ort der Rohspuren. Die Spuren selbst bleiben liegen (`src/backrec/delivery.py:124-126`) — nur weiß niemand davon.

## Goals / Non-Goals

**Goals:**

- Die Frist deckt die tatsächliche Nachbereitung ab, statt sie abzuschneiden.
- Ein Beenden ohne Nachbereitung ist nach dem Umbau genauso schnell wie vorher.
- Ein hängender Prozess blockiert nie unbegrenzt; es gibt eine harte Obergrenze.
- Die Frist beruht auf einer Beobachtung der Anwendung, nicht auf einer Schätzung der Aufnahmelänge.
- Wird doch hart beendet, steht das unmissverständlich im Protokoll und in der Rückmeldung — mit dem Pfad des Ordners, in dem die Rohspuren liegen.

**Non-Goals:**

- Keine Schätzung aus Aufnahmelänge, Dateigröße oder Datenrate.
- Kein Kommando, das eine Mischung nachträglich anstößt. Dieser Change sorgt dafür, dass der Abschluss durchläuft; ein Nachhol-Weg wäre ein eigener Auftrag.
- Keine Änderung an Aufnahme, Mischung, Ablage, Preflight, Einrichtungsschritten, Diagnose oder Fenstergestaltung.
- Kein Anfassen des offenen Change `remove-update-feature`.
- Keine neue Abhängigkeit, kein neues Modul, kein geändertes Dateiformat.

## Decisions

### D1: Die Frist folgt einem Lebenszeichen der Anwendung

Die Anwendung schreibt während der gesamten Abschlusssequenz in kurzen Abständen einen Taktzähler in `state\finishing.active`. `control.stop` liest diesen Zähler bei jedem Schleifendurchlauf. Ändert er sich, verlängert sich die Frist um `STOP_GRACE_SECONDS`; bleibt er stehen, läuft sie ab.

Drei Zahlen statt einer:

| Konstante | Wert | Bedeutung |
| --- | --- | --- |
| `STOP_TIMEOUT_SECONDS` | 30.0 | Grundfrist. Unverändert. Gilt, solange kein Lebenszeichen kommt. |
| `STOP_GRACE_SECONDS` | 10.0 | Wie lange nach dem zuletzt gesehenen Takt weiter gewartet wird. |
| `STOP_LIMIT_SECONDS` | 300.0 | Obergrenze ab dem Schreiben der Anfrage. Auch ein endlos schlagendes Lebenszeichen kommt nicht darüber hinaus. |

Die Frist wird dabei nur nach oben gesetzt und nie unter die Grundfrist gedrückt: `deadline = min(max(deadline, jetzt + STOP_GRACE_SECONDS), limit)`. Ein Takt in der zweiten Sekunde verkürzt also nichts.

Warum das die richtige Größe ist: Die Frage, die `stop` beantworten muss, lautet nicht „wie lange dauert die Nachbereitung", sondern „arbeitet die Anwendung noch". Nur die zweite ist von außen beantwortbar, ohne zu raten, und nur sie gilt gleichermaßen für eine Fünf-Minuten- und eine Fünf-Stunden-Aufnahme.

**Verworfen: (a) eine feste, höhere Frist.** `STOP_TIMEOUT_SECONDS` über `MERGE_TIMEOUT_SECONDS` plus Reserve zu heben — also auf etwa 180 Sekunden — ist eine Änderung von einem Zeichen und löst den Fall, um den es geht. Der Preis fällt aber genau dort an, wo der Change dringlich geworden ist: Seit `remove-update-feature` beendet `scripts\win\bootstrap-uv.ps1` bei **jedem** Setup-Lauf eine laufende Anwendung. Ein Kollege, der `Setup.cmd` doppelklickt, während die Anwendung hängt und gar nichts nachbereitet, säße drei Minuten vor einem Fenster, das nichts sagt — für einen Fall, der mit einer Aufnahme nichts zu tun hat. Die Frist trüge dann eine Zahl, die für den seltenen Fall bemessen ist, und alle anderen Fälle zahlten sie mit.

**Verworfen: (b) die Frist am Zustandszeichen `recording.active` festmachen.** Der naheliegende Weg scheitert am Bestand: `instance.clear_recording()` läuft in `_do_stop` vor dem Mischen (`src/backrec/app.py:445`), also vor dem längsten der drei Schritte. Genau in dem Moment, in dem die lange Frist gebraucht wird, meldet der Merker „keine Aufnahme". Ihn stattdessen später zu löschen wäre die schlechtere Reparatur: Er beantwortet auch `status.recording` und die Anzeige im Fenster, und „● recording" während des Mischens wäre schlicht falsch. Zwei Fragen, zwei Zeichen. Davon abgesehen bliebe auch mit einem korrekten Zeichen nur eine zweite feste Zahl übrig — und damit der gesamte Preis von (a) für jeden Hänger *während* einer Nachbereitung.

**Preis der Entscheidung:** Ein Faden mehr in der Anwendung, eine Datei mehr im Zustandsordner und drei Fristen statt einer. Der Faden ist nicht wegzudiskutieren: Das Mischen ist ein einzelner blockierender Aufruf von bis zu zwei Minuten, in dem der Abschlussfaden selbst keine Zeile schreiben kann (siehe D3). Die drei Zahlen sind der eigentliche Preis — sie müssen zusammenpassen und tun es nur, solange jemand darauf achtet. Dagegen steht der Test aus D6.

### D2: Ein Taktzähler, keine Änderungszeit der Datei

Das Lebenszeichen ist der **Inhalt** der Datei — eine Ganzzahl, die mit jedem Takt um eins wächst —, nicht ihre Änderungszeit. `control.stop` fragt nie „wann war der letzte Takt", sondern nur „ist der Zähler ein anderer als beim letzten Blick".

Der Unterschied ist nicht kosmetisch. Eine Auswertung über `st_mtime` vergleicht zwei Uhren miteinander: die Systemzeit, unter der die Anwendung die Datei geschrieben hat, und die Systemzeit im Moment des Lesens. Eine Zeitumstellung, ein Zeitabgleich oder eine Dateisystem-Auflösung von zwei Sekunden macht daraus eine falsche Antwort — und `instance.py` trägt bereits eine Toleranzkonstante gegen genau dieses Problem (`CREATE_TIME_TOLERANCE_SECONDS`, `src/backrec/instance.py:39`). Der Vergleich „gleich oder nicht gleich" braucht überhaupt keine Uhr. Gemessen wird nur auf der Seite des Beobachters, mit `time.monotonic()`, und das ist eine Uhr, die niemand verstellt.

Eine unlesbare oder leere Datei zählt als „kein Takt" und verlängert nichts. Eine liegengebliebene Datei aus einem Absturz ebenfalls: Sie steht still, also verlängert sie nicht. Damit ist das Zeichen selbstheilend, ohne dass irgendwo ein Aufräumschritt nötig wäre.

**Verworfen: das Lebenszeichen über die Änderungszeit.** Siehe oben — es hätte eine Toleranz gebraucht und wäre auf einem Dateisystem mit grober Auflösung zwischen zwei Takten nicht unterscheidbar gewesen.

**Verworfen: den Fortschritt über einen Zustand im Zustandsdatensatz `backrec.pid` führen.** Der Datensatz ist eine Identität und wird einmal geschrieben; ihn im Sekundentakt neu zu schreiben, hieße, die Datei, an der `stop` die Instanz wiedererkennt, genau währenddessen dauernd anzufassen.

### D3: Das Lebenszeichen läuft in einem eigenen Faden

`app._do_stop` klammert seine gesamte Arbeit in `instance.FinishingBeacon()`. Der Beacon startet einen Faden, der den Zähler alle `FINISHING_BEAT_SECONDS` (1.0) erhöht, und räumt die Datei beim Verlassen wieder weg — mit Erfolg wie mit Fehler, weil der Kontextmanager das erzwingt.

Der Faden ist nötig, nicht bequem. Das Mischen ist **ein** Aufruf von `subprocess.run` mit bis zu 120 Sekunden Laufzeit; der Abschlussfaden hat währenddessen keinen Punkt, an dem er etwas schreiben könnte. Ein Takt zwischen den drei Schritten hätte genau drei Takte ergeben, und die längste Lücke wäre die gewesen, die überbrückt werden muss.

Dass der Faden während `subprocess.run` und `shutil.copy2` überhaupt zum Zug kommt, ist keine Annahme: Beide geben die GIL für die Dauer ihrer Ein-/Ausgabe frei.

Ein fehlgeschlagener Schreibversuch — voller Datenträger, Ordner weg — wird protokolliert und sonst verschluckt. Das Lebenszeichen darf eine laufende Nachbereitung unter keinen Umständen abbrechen; es ist die Beschreibung der Arbeit, nicht die Arbeit.

Auf dem Weg ohne Aufnahme wird der Beacon nie angefasst: `_request_shutdown` ruft bei `not self._recording` direkt `_finalize_exit()` (`src/backrec/app.py:280-282`). Damit ist die Zusage „ein Stopp ohne Nachbereitung wird nicht langsamer" nicht bloß eine Absicht, sondern eine Eigenschaft des Kontrollflusses: Es gibt keinen Takt, also keine Verlängerung, also die unveränderte Grundfrist.

### D4: `STOP_GRACE_SECONDS` ist zehnmal der Takt, `STOP_LIMIT_SECONDS` deckt die drei Schritte

**Nachfrist 10 s bei 1 s Takt.** Der Beobachter pollt alle 0.5 Sekunden; bei 1 Sekunde Takt sieht er im Normalbetrieb jeden Takt. Zehn verpasste Takte hintereinander sind kein Aussetzer mehr, sondern ein Stillstand. Nach unten ist die Grenze die Belastung des Rechners — auf einem Notebook, das gerade eine 600-MB-Datei über ein Netzlaufwerk kopiert, ist eine Sekunde Verzug für einen Faden nichts Besonderes. Nach oben ist die Grenze das, was ein Kollege vor einem hängenden Fenster zusätzlich wartet; zehn Sekunden fallen neben der Grundfrist von dreißig nicht auf.

**Obergrenze 300 s.** Sie muss den schlimmsten *rechtmäßigen* Fall abdecken, nicht den wahrscheinlichen: 10 Sekunden für die beiden Aufnahmefäden, 120 für das Mischen (die eigene Frist von ffmpeg, D5), bleiben rund 170 für das verifizierte Kopieren. Bei den etwa 600 MB einer zweistündigen Aufnahme entspricht das gut 3,5 MB/s — langsamer als jede lokale Platte und langsam genug für ein Ziel in einem synchronisierten Ordner.

Die Obergrenze greift ausschließlich in einem Fall: Die Anwendung schlägt weiter Takte, wird aber nicht fertig. Das ist ein Fehler in der Anwendung, kein Betriebszustand — und dafür ist die Antwort ein hartes Beenden mit einem deutlichen Protokolleintrag, nicht unbegrenztes Warten.

### D5: `MERGE_TIMEOUT_SECONDS` bleibt bei 120

Geprüft, nicht übernommen. Drei Gründe, die Zahl stehen zu lassen:

Erstens ist sie nicht knapp. ffmpeg dekodiert hier PCM, resampelt und mischt — keine Kodierarbeit. Zwei Stunden Material in 120 Sekunden sind etwa 60-fache Echtzeit, und die tatsächliche Rate für diese Filterkette liegt um ein Vielfaches darüber.

Zweitens ist ihr Reißen harmlos. `subprocess.run` wirft `TimeoutExpired`, `merge_audio_files` fängt es und gibt `(False, ...)` zurück, `delivery.finish` macht daraus ein `_failed(...)` — mit sichtbarer Meldung, Protokolleintrag und beiden Rohspuren an Ort und Stelle. Eine zu niedrige Mischfrist kostet einen benannten Fehlschlag mit Rückweg. Eine zu hohe kostet in jedem Fehlerfall Wartezeit unter der Frist von `stop`. Die Asymmetrie spricht gegen das Anheben.

Drittens gibt es keine Messung. Sie ohne eine anzuheben hieße, eine geratene Zahl durch eine andere zu ersetzen — und genau das ist der Fehler, den dieser Change behebt.

Was sich ändert, ist nicht die Zahl, sondern ihr Verhältnis: Die Obergrenze des Stopps liegt jetzt darüber statt darunter. Ein Test hält das fest (D6).

### D6: Ein Test bindet die Obergrenze an die Mischfrist

Der eigentliche Fehler war nie eine falsche Zahl, sondern dass zwei Zahlen in zwei Modulen unabhängig voneinander gepflegt wurden und niemandem auffiel, als sie sich widersprachen. Ein Kommentar hätte das nicht verhindert — der Kommentar bei `STOP_TIMEOUT_SECONDS` behauptete die Deckung sogar ausdrücklich.

Deshalb steht die Beziehung als Test da: `STOP_LIMIT_SECONDS` MUSS `MERGE_TIMEOUT_SECONDS` plus die Zeit der beiden Aufnahmefäden plus eine Reserve für das Kopieren überschreiten. Wer künftig eine der beiden Zahlen anfasst, ohne die andere anzusehen, bekommt einen roten Test statt eines abgeschnittenen Abschlusses bei einem Kollegen.

### D7: Ein hartes Beenden nennt immer den Aufnahmeordner

`StopResult` bekommt das Feld `raw_takes: str | None`. Es wird nur im erzwungenen Fall gefüllt, und zwar aus `config.recording_dir` — dem Ordner, in dem die Rohspuren nach Bauart liegen (`src/backrec/delivery.py:124-126`).

Genannt wird der Ordner bei **jedem** harten Beenden, nicht nur bei einem mit beobachtetem Lebenszeichen. Das ist Absicht: Eine Anwendung, die hängt, *ohne* je mit der Nachbereitung begonnen zu haben, kann mitten in einer laufenden Aufnahme hängen — und dann liegen dort ebenfalls zwei angefangene Spuren. Die Meldung unterscheidet nur im Ton, nicht im Ordner:

- mit gesehenem Lebenszeichen: die Nachbereitung wurde abgeschnitten, die Rohspuren liegen in `<Ordner>`.
- ohne: nach Ablauf der Frist beendet; falls eine Aufnahme lief, liegen ihre Rohspuren in `<Ordner>`.

Lässt sich die Einstellungsdatei nicht lesen, bleibt `raw_takes` leer und die Meldung nennt das harte Beenden trotzdem. Ein `stop`, das an einer unlesbaren Konfiguration scheitert, wäre die schlechteste denkbare Verschlimmbesserung.

Der Protokolleintrag steht auf `ERROR`, nicht auf `WARNING`. Ein abgeschnittener Abschluss ist kein Schönheitsfehler: Es ist der Fall, in dem ein Ergebnis fehlt, das der Kollege erwartet hat.

### D8: Die Einrichtung meldet ein erzwungenes Beenden

`_stop_running_application` prüft heute nur `outcome.stopped` (`src/backrec/control.py:346-348`). Ein erzwungenes Beenden gilt dort als Erfolg und bleibt stumm — genau auf dem Weg, der diesen Change dringlich gemacht hat: `Setup.cmd` neben einer laufenden Aufnahme.

Künftig gibt ein `forced` eine Warnung mit derselben Meldung aus, die auch `stop` selbst liefert. Der Kollege liest zwischen Schritt 1 und Schritt 2 der Einrichtung, dass seine Aufnahme abgeschnitten wurde und wo die Spuren liegen. Ohne diesen Satz ist genau er der Adressat, der nie erfährt, was passiert ist.

Ein Abbruch der Einrichtung ist es nicht. Die Anwendung ist beendet, die Umgebung kann ersetzt werden, und ein Stehenbleiben würde die Lage nicht verbessern.

## Risks / Trade-offs

- **Das Lebenszeichen schlägt weiter, obwohl die Anwendung nicht mehr vorankommt** → Die Obergrenze aus D4 begrenzt den Schaden auf 300 Sekunden, und das harte Beenden wird protokolliert und gemeldet. Weiter kommt man von außen nicht: Ob ein Prozess arbeitet oder sich im Kreis dreht, ist ohne Kenntnis seines Inneren nicht entscheidbar.
- **Der Beacon-Faden stirbt, die Nachbereitung läuft weiter** → Dann gilt die Grundfrist und es wird nach 30 Sekunden hart beendet — also genau das heutige Verhalten, plus die neue Meldung mit dem Ordner. Der Faden schreibt nur und fängt jeden `OSError` ab; ein Absturz setzt eine Ausnahme voraus, die er selbst nicht auslöst.
- **Ein Stopp ohne Aufnahme wird langsamer** → Kann nicht passieren: Der Weg ohne Aufnahme erzeugt keinen Takt (D3), und die Frist wird ohne Takt nie verlängert. Ein Test hält beides fest.
- **Die drei Zahlen laufen wieder auseinander** → Der Test aus D6 bindet Obergrenze und Mischfrist aneinander. Für das Verhältnis von Grundfrist und Nachfrist genügt der Kommentar: Beide stehen in derselben Datei nebeneinander.
- **Eine zusätzliche Datei im Zustandsordner verwirrt bei der Fehlersuche** → Sie heißt `finishing.active`, liegt neben `recording.active` und `stop.request`, und `uninstall --purge` räumt den Ordner ohnehin vollständig ab. Der Diagnosebericht bekommt sie nicht — er nennt keinen der beiden anderen Merker.
- **Der Kollege wartet bei einer langen Aufnahme länger als bisher** → Er wartet, bis seine Aufnahme fertig ist. Genau das ist der Zweck; bisher wartete er kürzer und verlor das Ergebnis.

## Migration Plan

Keine Datenmigration. Das neue Zustandszeichen entsteht zur Laufzeit und verschwindet mit der Sequenz, die es geschrieben hat; eine Fassung ohne es liest es nie, eine Fassung mit ihm findet es einfach nicht vor.

Der Mischfall zweier Fassungen ist gutartig: Beendet eine neue `stop`-Fassung eine alte Anwendung, die kein Lebenszeichen schreibt, gilt die Grundfrist — das heutige Verhalten. Umgekehrt schreibt eine neue Anwendung ein Zeichen, das eine alte `stop`-Fassung nicht liest und das mit der Sequenz wieder verschwindet.

Rückweg: Der Change betrifft fünf Quelldateien und ein Dokument, legt keine Datei an, die liegen bleibt, und ändert kein Format. Ein Zurücknehmen wäre die Umkehrung desselben Commits; außerhalb des Repositorys müsste nichts angefasst werden.

## Open Questions

- Sollte `status` ausweisen, dass eine Nachbereitung läuft? Das Zeichen liegt dafür bereit und die Auskunft nennt heute nur `recording`. Bewusst nicht in diesem Change: `status` ist eine Fähigkeit mit eigener Anforderung, und der Fehler, um den es hier geht, wird davon nicht berührt.
- Ein Kommando, das aus zwei liegengebliebenen Rohspuren nachträglich eine Mischung baut, wäre die vollständige Antwort auf „und was mache ich jetzt mit dem Ordner". Der Change nennt den Ordner; er baut den Weg nicht. Eigener Auftrag.
- Ob `MERGE_TIMEOUT_SECONDS = 120` für eine sehr lange Aufnahme über ein langsames Netzlaufwerk reicht, ist aus dem Code nicht zu beantworten (D5). Eine Messung an einer echten Zweistundenaufnahme würde es klären; bis dahin bleibt die Zahl.
