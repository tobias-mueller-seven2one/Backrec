## Why

Vier Aufnahmen haben eine unbrauchbar lange Datei erzeugt — zuletzt am 2026-09-22 eine von 20 GB. Eine solche Datei geht ungeprüft in die Transkription und kostet dort mehr, als die verlorene Aufnahme selbst wert war.

Die Messung über alle 212 Rohspuren im Aufnahmeverzeichnis benennt die Ursache eindeutig (Einzelheiten in `findings.md`):

```
start               spur      audio_h  wall_min   faktor
2026-07-13 09:14:57 mic           1.9       1.2      94x
2026-07-23 09:32:26 mic         106.2      26.9     237x
2026-07-31 14:35:08 mic         142.4      34.4     249x
2026-09-22 16:55:15 mic          63.5      19.7     194x

Rohspuren gesamt: 212   Ausreißer: 4   Ausreißer nach Spurtyp: ['mic']
```

**Alle vier Ausreißer sind die Mikrofonspur, keine einzige Systemspur ist betroffen.** Die Systemspur derselben Sitzung trifft die Wanduhrzeit jedes Mal auf 1,00 % genau. Start und Stop haben funktioniert; die Sitzungen waren 19 bis 34 Minuten lang. Die Mikrofonaufnahme hat darin das 94- bis 249-Fache an Ton geschrieben.

Der Grund steht in `src/backrec/recording.py:123-141`: Die Schreibschleife hat keine Uhr. Ihr einziger Taktgeber ist die Annahme, dass `sd.InputStream.read()` blockiert, bis ein Block vorliegt. Dieses blockierende Lesen ist bei PortAudio ein Bequemlichkeits-Wrapper über einen Ringpuffer; gerät der Stream in einen Fehlerzustand, kehrt es sofort zurück. Dann schreibt die Schleife so schnell, wie Platte und `flush()` es zulassen. Nichts im Code vergleicht die geschriebene Tonmenge mit der verstrichenen Zeit.

Die Geräteprüfung fängt das nicht ab: Sie läuft einmal pro Sekunde und vergleicht ausschließlich **Gerätenamen** (`src/backrec/recording.py:146-153`). Bleibt der Name gleich, während der Endpunkt darunter nicht mehr liefert, bricht die Schleife nie ab.

`merge.py` und `delivery.py` sind nicht beteiligt. `amix=duration=longest` übernimmt korrekt die Länge der längeren Spur — die 20-GB-Datei ist Folge, nicht Ursache.

Diese Änderung ersetzt den zurückgezogenen Change `fix-recording-session-isolation`, der von einem Lebenszyklus-Fehler ausging. Die Messdaten widerlegen ihn: Liefe eine Sitzung über Stunden durch, wäre auch die Systemspur zu lang, und 63,5 Stunden Ton passen ohnehin in keinen Arbeitstag.

## What Changes

Zwei Lösungen, beide in `src/backrec/recording.py`.

- **Der Takt der Mikrofonaufnahme kommt vom Aufnahmegerät.** Statt in einer Schleife zu lesen und auf deren Blockieren zu bauen, meldet sich der Audiotreiber, sobald ein Block fertig ist. Geschrieben wird nur, was der Treiber übergibt. Damit wird eine Überproduktion nicht erkannt, sondern unmöglich: Liefert das Gerät nichts, kommen keine Aufrufe und es entstehen keine Daten.

- **Die Schreibposition folgt der Uhr.** Beide Spuren führen einen Anker: wie viel Ton bei der bisher verstrichenen Zeit geschrieben sein darf. Läuft die Datei diesem Anker davon, wird die Schreibposition auf den Anker zurückgesetzt und dort weitergeschrieben. Die Aufnahme bleibt dadurch brauchbar — es fehlt nur der Ton der Störung, die Zeitachse bleibt korrekt. Der Vorfall wird protokolliert.

Die zweite Lösung gilt für **beide** Spuren, nicht nur für das Mikrofon. Grund: `soundcard`, über das die Systemspur läuft, bietet keine Callback-Schnittstelle — nur `record()`, also dasselbe ziehende Verfahren. Für die Systemspur ist der Anker damit die einzige Absicherung gegen denselben Fehler.

Nicht **BREAKING**: Bedienung, Dateibenennung, Mischung und Ergebnisformat bleiben unverändert.

## Capabilities

### New Capabilities

Keine.

### Modified Capabilities

- `audio-recording`: Die Fähigkeit beschreibt bisher nur, was am Ende einer Aufnahme im Zielverzeichnis ankommt, nicht die Aufnahme selbst. Neu: Der Takt einer Aufnahme kommt vom Aufnahmegerät, und die geschriebene Tonmenge folgt der verstrichenen Zeit. Beides ist von außen prüfbar — an der Dauer der entstandenen Datei.

## Impact

- `src/backrec/recording.py` — Träger der gesamten Änderung. `MicRecorder` wird auf den Callback des Treibers umgestellt, `BaseRecorder` bekommt den Uhr-Anker für beide Spuren.
- `tests/test_recording.py` — neu. Bisher gibt es für dieses Modul keine Tests; das ist der Grund, warum der Fehler durchging.
- Keine neuen Abhängigkeiten. `soundfile` 0.14.0 beherrscht `seek` und `truncate` im Schreibmodus, was der Anker braucht; nachgewiesen, siehe `design.md`.
- `app.py`, `merge.py`, `delivery.py`, `instance.py` bleiben unberührt.
