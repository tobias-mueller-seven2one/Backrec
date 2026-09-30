## Context

Der Fehler ist gemessen, nicht vermutet. Über alle 212 Rohspuren im Aufnahmeverzeichnis wurde die Tondauer aus der Dateigröße gegen die Wanduhrzeit gestellt. Vier Ausreißer, alle die Mikrofonspur, Faktor 94 bis 249. Die Systemspur derselben Sitzungen trifft die Wanduhrzeit jedes Mal auf 1,00 % genau. Einzelheiten in `findings.md`.

Die betroffene Stelle:

```python
# src/backrec/recording.py:123-141 - heute
while self._running:
    data, overflowed = self._read_block(stream, blocksize)   # einziger Taktgeber
    with self._lock:
        if self.file is not None:
            self.file.write(data)
            self.file.flush()
```

Diese Schleife hat keine Uhr. Sie verlässt sich darauf, dass `sd.InputStream.read()` blockiert, bis `blocksize` Frames vorliegen. Blockiert es nicht mehr, schreibt sie mit Plattengeschwindigkeit. Es gibt keine Stelle im Code, die weiß, wie viel Zeit vergangen ist.

Zwei Randbedingungen bestimmen den Entwurf:

- **`soundcard` kennt keinen Rückruf.** Geprüft: `soundcard.mediafoundation._Recorder` bietet `record`, `flush`, `buffersize`, `currentpadding`, `deviceperiod` — kein `callback`. Die Systemspur bleibt damit zwangsläufig beim ziehenden Verfahren. `sounddevice` bietet den Rückruf; die Mikrofonspur kann umgestellt werden.
- **Der Code funktioniert heute.** Gerätewechsel mitten im Call, Mute, COM-Initialisierung pro Thread — alles in täglichem Gebrauch. Der Modul-Docstring hält ausdrücklich fest, dass keine Zeile der Schleife umgeschrieben wurde.

## Goals / Non-Goals

**Goals**

- Die Mikrofonaufnahme kann nicht mehr schneller laufen als das Gerät liefert.
- Läuft eine Spur dennoch der Uhr davon, bleibt die Aufnahme brauchbar statt verloren.
- Beide Spuren sind abgesichert, nicht nur die, bei der der Fehler aufgetreten ist.

**Non-Goals**

- Keine Änderung an Mischung, Übernahme, Dateibenennung oder Ergebnisformat.
- Keine Änderung an der Fenster- oder Ablaufsteuerung in `app.py`.
- Keine Prüfung des Ergebnisses vor der Übergabe (siehe Verworfene Optionen).
- Keine Zeitstempel je Puffer und keine Umstellung der Geräteerkennung auf Windows-Ereignisse.

## Decisions

### D1 — Die Mikrofonaufnahme wird vom Treiber getaktet

**Entscheidung:** `MicRecorder` wird auf `sd.InputStream(callback=...)` umgestellt. Der Treiber ruft auf, sobald ein Block fertig ist; geschrieben wird genau dieser Block. Die ziehende Schleife entfällt für diese Spur.

```python
# Entwurf, nicht umgesetzt
def _callback(self, indata, frames, time_info, status):
    if status:
        self.last_error = str(status)
    with self._lock:
        if self.file is None:
            return
        self.file.write(np.zeros_like(indata) if self.muted else indata)
```

**Warum:** Das ist die einzige Maßnahme, die den Fehler nicht erkennt, sondern ausschließt. Es gibt danach keine Schleife mehr, die schneller laufen könnte als das Gerät liefert. Liefert das Gerät nichts, kommen keine Aufrufe und es entstehen keine Daten — die Spur wird still oder kurz, aber nie zu lang.

**Was mit umziehen muss:** Der Rückruf läuft in einem PortAudio-Thread, nicht im eigenen. Mute, das Setzen von `last_peak` und der Schreibvorgang unter `self._lock` gehören hinein. Die COM-Initialisierung und die Geräteprüfung bleiben in einem eigenen, schlanken Überwachungsfaden, der den Stream bei einem Gerätewechsel neu aufbaut — der Rückruf selbst darf nichts Langsames tun.

**Alternative:** Nur den Uhr-Anker aus D2 bauen und die Schleife lassen. Verworfen als alleinige Maßnahme: Der Defekt bliebe im Code und würde bei jeder Störung erneut Müll erzeugen, den der Anker dann wegräumt. D1 ist die Ursachenbehebung, D2 das Netz darunter.

### D2 — Die Schreibposition wird an die Uhr gebunden

**Entscheidung:** `BaseRecorder` führt einen monotonen Startzeitpunkt. Vor jedem Schreiben gilt: erlaubte Frames = verstrichene Zeit × Abtastrate. Liegt die Schreibposition mehr als eine Toleranz darüber, wird auf die erlaubte Position zurückgespult, abgeschnitten und dort weitergeschrieben. Der Vorfall wird protokolliert.

**Warum für beide Spuren:** `soundcard` bietet keinen Rückruf, die Systemspur bleibt also beim ziehenden Verfahren. Für sie ist D2 die **einzige** Absicherung gegen denselben Fehler. Dass sie bisher nicht betroffen war, ist kein Beleg dafür, dass sie es nicht sein kann.

**Warum Zurückspulen statt Abbrechen:** Ein Wächter, der nur deckelt, lässt den bereits geschriebenen Müll in der Datei — die Aufnahme wäre trotzdem verloren, nur kleiner. Zurückspulen hält die Zeitachse korrekt; es fehlt der Ton der Störung, der Rest bleibt brauchbar. Das ist der Unterschied zwischen einer geretteten und einer verlorenen Besprechung.

**Nachgewiesen, nicht angenommen.** Ob eine offene WAV-Datei im Schreibmodus zurückgespult und gekürzt werden kann, wurde gemessen (`soundfile` 0.14.0):

```
nach Ueberproduktion : frames = 441000 (10.0 s)
nach seek            : frames =  88200 (2.0 s)
nach truncate        : frames =  88200 (2.0 s)
nach Weiterschreiben : frames =  97020 (2.2 s)

Datei danach         : 97020 frames = 2.2 s
ERGEBNIS             : OK
```

**Zur Toleranz:** Der reguläre Taktunterschied zwischen Aufnahmegerät und Systemuhr liegt bei einigen hundert Teilen je Million. Die beobachteten Störungen liegen bei 9400 % bis 24 800 %. Zwischen beiden liegen vier Größenordnungen; die Toleranz ist deshalb unkritisch zu wählen. Vorschlag: 20 % Vorsprung, frühestens nach einigen Sekunden Laufzeit, damit der Anlauf nicht als Störung zählt.

## Risks / Trade-offs

- **D1 fasst Code an, der heute zuverlässig arbeitet.** Der Gerätewechsel mitten im Call ist eine Funktion, auf die das Modul ausdrücklich zielt. Wird sie beim Umbau beschädigt, fällt das erst im nächsten Termin auf. Gegenmaßnahme: Der Gerätewechsel bekommt einen eigenen Test mit einem ersetzten Stream, bevor der Umbau gilt.
- **Der Rückruf läuft in einem fremden Thread.** Alles darin muss kurz sein. Ein `flush()` je Block bleibt (es ist der Grund, warum ein hart beendeter Prozess eine abspielbare Datei hinterlässt), aber Geräteabfragen und COM-Aufrufe gehören nicht hinein.
- **D2 kann bei einer echten, dauerhaften Taktabweichung wiederholt zurückspulen** und damit laufend Ton verwerfen. Gegenmaßnahme: Wiederholte Vorfälle innerhalb kurzer Zeit werden als Gerätestörung protokolliert, damit der Grund im Protokoll steht statt nur die Wirkung.
- **Es gibt für `recording.py` bisher keinen einzigen Test.** Das ist der Grund, warum der Fehler durchging. Ein Stream, der sofort zurückkehrt, ist als Testdoppel zwei Zeilen — dieser Test fehlt und wird nachgezogen.
- **Wir haben kein Protokoll zu den vier Vorfällen.** Damit ist belegt, *dass* die Mikrofonschleife raste, nicht *warum* das Lesen aufhörte zu blockieren. D1 setzt am wahrscheinlichsten Mechanismus an; D2 greift unabhängig davon, weil es nicht am Mechanismus ansetzt, sondern am Ergebnis. Diese Aufteilung ist bewusst gewählt.

## Verworfene Optionen

| Option | Warum nicht |
|---|---|
| Ergebnisdauer vor der Übergabe prüfen | Vom Auftraggeber verworfen: Eine Prüfung, die die Sitzungsdauer falsch herleitet, wirft gute Aufnahmen weg. Das Risiko wiegt schwerer als der Nutzen. |
| Protokollierung reparieren | Die Rückwärtssuche hat keinen Defekt gefunden — Protokollierung über CLI und unter `pythonw` nachweislich funktionsfähig. Ohne gezielte Korrektur laut Vorgabe nicht Teil dieser Änderung. Offene Frage siehe unten. |
| Zeitstempel je Puffer (PTS) | Verbessert die Lückenbehandlung, betrifft diesen Fehler nicht. |
| Geräteerkennung per Windows-Ereignis statt Namensvergleich | Mit D1 weitgehend gegenstandslos; der Namensvergleich bleibt als grobe Ergänzung bestehen. |
| ffmpeg als Aufnahmeprozess | Würde die Zeitachse an ffmpeg abgeben und den Gerätewechsel mitten im Call opfern, der bewusst gebaut wurde. |
| Der zurückgezogene Change `fix-recording-session-isolation` | Zielte auf einen Lebenszyklus-Fehler. Die Messdaten widerlegen ihn: Bei einer durchlaufenden Sitzung wäre auch die Systemspur zu lang. |

## Migration Plan

Nicht erforderlich. Kein gespeichertes Format ändert sich, keine Einstellung kommt hinzu, keine Abhängigkeit wird neu.

## Open Questions

- **Wie wird Backrec im Alltag gestartet?** Das Protokoll enthält für den 14.09. null Zeilen, obwohl an diesem Tag zwei Aufnahmen entstanden; insgesamt hat das Fenster nie eine Aufnahme protokolliert. Die Protokollierung selbst funktioniert (dreimal geprüft), es existiert nur eine Installation, und der Einstieg `pythonw -m backrec` richtet sie vor jeder Verzweigung ein. Die Antwort entscheidet, ob daraus eine eigene Änderung wird. Sie blockiert diese hier nicht.
- Soll der Uhr-Anker bei wiederholtem Zurückspulen die Aufnahme abbrechen statt endlos zu korrigieren? Der Entwurf korrigiert weiter und protokolliert, weil eine abgebrochene Besprechung schlechter ist als eine lückenhafte.
