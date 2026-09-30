# Befund aus Block 1 (Beweis sichern)

Erhoben am 2026-09-30 aus `C:\Users\tobias.mueller\Aufnahmen\Recording` (212 Rohspuren) und
`%LOCALAPPDATA%\MemoSuite\Backrec\logs\backrec.log`.

## Messung

Je Rohspur wurde die **Audiodauer** aus der Dateigröße berechnet (Mikrofon: 44100 Hz × 1 Kanal ×
2 Byte = 88.200 B/s; System: 44100 Hz × 2 Kanäle × 2 Byte = 176.400 B/s) und gegen die
**Wanduhrzeit** gestellt (Änderungszeit minus Startzeitstempel im Dateinamen).

```
--- Ausreißer (Audiodauer / Wanduhrzeit > 1,5) ---
start               spur      audio_h  wall_min   faktor
2026-07-13 09:14:57 mic           1.9       1.2      94x
2026-07-23 09:32:26 mic         106.2      26.9     237x
2026-07-31 14:35:08 mic         142.4      34.4     249x
2026-09-22 16:55:15 mic          63.5      19.7     194x

Rohspuren gesamt: 212   Ausreißer: 4
Ausreißer nach Spurtyp: ['mic']
```

## Was daraus folgt

**Alle vier Ausreißer sind die Mikrofonspur. Keine einzige Systemspur ist betroffen.** Die
Systemspur derselben Sitzung trifft die Wanduhrzeit jedes Mal auf 1,00× genau.

Der belastbarste Fall ist der vom 2026-09-22:

| Datei | Größe | Audiodauer | Wanduhrzeit |
|---|---|---|---|
| `system_2026-09-22_16-55-15.wav` | 208 MB | 19,7 min | 19,7 min |
| `mic_2026-09-22_16-55-15.wav` | 20,2 GB | **63,5 h** | 19,7 min |
| `2026-09-22_16-55-15.wav` (Mischung) | 20,2 GB | 63,5 h | — |

Beide Spuren tragen denselben Startzeitstempel, gehören also **derselben Sitzung** an, und beide
wurden zur selben Minute geschlossen. Start und Stop haben funktioniert. Die Sitzung hat 19,7
Minuten gedauert.

Die Mikrofonschleife hat in diesen 19,7 Minuten 63,5 Stunden Ton geschrieben — rund **194-mal
schneller als Echtzeit**. `merge.py` mischt mit `amix=duration=longest` und übernimmt damit
korrekt die Länge der längeren Spur. Die 20-GB-Datei ist die Folge, nicht die Ursache.

## Das widerlegt die Ursachenanalyse in `design.md`

`design.md` nimmt an, die lange Datei entstehe, weil eine Aufnahmesitzung nicht beendet wurde und
über Stunden weiterlief (fehlende Invariante zwischen gemeldetem und tatsächlichem Zustand). Das
ist **nicht** der Fall:

- Liefe eine Sitzung durch, wäre **auch die Systemspur** zu lang. Sie ist es in keinem einzigen
  Fall.
- Liefe eine Sitzung durch, entspräche die Audiodauer der verstrichenen Wanduhrzeit. Sie
  übersteigt sie um das 94- bis 249-Fache.
- 63,5 Stunden Ton lassen sich ohnehin nicht an einem Tag aufnehmen.

Die Wahrnehmung „lief seit der ersten Aufnahme" war ein naheliegender Schluss aus einer absurd
langen Datei, trifft die Ursache aber nicht.

## Die tatsächliche Ursache

`sd.InputStream.read(blocksize)` in `src/backrec/recording.py:209` blockiert normalerweise, bis
`blocksize` Frames vorliegen — das ist der einzige Taktgeber der Schleife in
`_recording_loop_body` (`src/backrec/recording.py:106-161`). Hört der Stream auf zu blockieren,
schreibt die Schleife so schnell, wie Platte und `flush()` es zulassen. Nichts im Code begrenzt
die Schreibrate, und nichts vergleicht die geschriebene Menge mit der verstrichenen Zeit.

Die Geräteprüfung greift hier nicht: Sie läuft nur einmal pro Sekunde und vergleicht ausschließlich
**Gerätenamen** (`src/backrec/recording.py:146-153`). Bleibt der Name gleich, während der Stream
darunter nicht mehr liefert, bricht die Schleife nie ab.

Die Systemspur ist nicht betroffen, weil sie über `soundcard`/WASAPI-Loopback läuft
(`src/backrec/recording.py:242-244`) — ein anderer Weg mit anderem Blockierverhalten.

## Zweiter Befund: es gibt keine Forensik

`backrec.log` endet am 2026-09-15, obwohl bis zum 2026-09-30 aufgenommen wurde. Rotationsdateien
existieren nicht. Die Zeichenkette `>>> REC gedrueckt` (`src/backrec/app.py:375`) kommt im Protokoll
**überhaupt nicht** vor, auch nicht für die Aufnahmen vom 8. bis 15. September.

Das heißt: Die im täglichen Einsatz laufende Fassung ist nicht der Stand in `src/backrec/`. Wo die
Korrektur landen muss, ist damit zu klären, bevor gebaut wird.

## Bewertung des geplanten Umbaus

Von den dreizehn Blöcken in `tasks.md` hätte **keiner** diesen Fehler verhindert. Zwei hätten ihn
begrenzt:

- **Block 6** (Plausibilitätsprüfung des Ergebnisses) hätte alle vier Fälle erkannt und die
  Erfolgsmeldung verweigert — die Rohspuren wären erhalten geblieben, die 20-GB-Datei wäre nicht
  ins Zielverzeichnis gelangt.
- **Block 9** (Höchstdauer) hätte nicht gegriffen: Die Sitzungen waren mit 19 bis 34 Minuten kurz;
  zu lang war nur der geschriebene Ton.

Die übrige Härtung ist für sich genommen sinnvoll, behebt aber den berichteten Fehler nicht.
