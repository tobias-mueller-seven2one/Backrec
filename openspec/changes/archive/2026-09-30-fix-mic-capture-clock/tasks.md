## 1. Beweis (erledigt, aus dem zurückgezogenen Change übernommen)

- [x] 1.1 Messung über alle Rohspuren: Tondauer aus der Dateigröße gegen die Wanduhrzeit. Ergebnis: 4 Ausreißer unter 212 Spuren, alle die Mikrofonspur, Faktor 94 bis 249. Systemspur immer 1,00. Festgehalten in `findings.md`.
- [x] 1.2 Nachgewiesen, dass `soundfile` 0.14.0 eine offene WAV-Datei im Schreibmodus zurückspulen und kürzen kann. Ergebnis in `design.md`, Entscheidung D2.
- [x] 1.3 Nachgewiesen, dass `soundcard` keine Rückruf-Schnittstelle bietet — nur `record`, `flush`, `buffersize`, `currentpadding`, `deviceperiod`. Daraus folgt: D1 gilt nur für das Mikrofon, D2 für beide Spuren.

## 2. Absicherung vor dem Umbau

- [x] 2.1 `tests/test_recording.py` neu anlegen. Für dieses Modul gibt es bisher keinen Test; das ist der Grund, warum der Fehler durchging.
- [x] 2.2 Test für den Gerätewechsel mitten in der Aufnahme schreiben, der gegen den **heutigen** Stand grün ist. Ohne diesen Test wird nicht umgebaut — er ist die einzige Absicherung der Funktion, die der Umbau gefährdet.
- [x] 2.3 Testdoppel anlegen: ein Stream, dessen Lesevorgang sofort zurückkehrt, statt zu blockieren — der gemessene Fehlerfall in zwei Zeilen. Test dagegen zeigt heute den Fehler.

## 3. Ursache beheben: die Mikrofonaufnahme vom Treiber takten lassen (D1)

- [x] 3.1 `MicRecorder` auf `sd.InputStream(callback=...)` umstellen. Im Rückruf: Mute beachten, `last_peak` setzen, Block unter `self._lock` schreiben und flushen.
- [x] 3.2 Der Rückruf bleibt kurz: keine Geräteabfrage, kein COM-Aufruf, keine Wartezeit darin.
- [x] 3.3 Geräteprüfung und COM-Initialisierung in einen schlanken Überwachungsfaden verlagern, der den Stream bei einem Gerätewechsel neu aufbaut.
- [x] 3.4 `start()` und `stop()` für `MicRecorder` an das neue Verfahren anpassen; die Signaturen für den Aufrufer in `app.py` unverändert lassen.
- [x] 3.5 Ein Statuswert des Treibers (Overflow, Fehler) wird in `last_error` festgehalten und protokolliert, nicht verschluckt.
- [x] 3.6 Test aus 2.2 erneut laufen lassen: Der Gerätewechsel muss weiterhin funktionieren.
- [x] 3.7 Test: Liefert der Treiber keine Aufrufe mehr, wächst die Spur nicht; die Datei bleibt so lang wie die Aufnahme.

## 4. Netz darunter: die Schreibposition an die Uhr binden (D2)

- [x] 4.1 `BaseRecorder` hält einen monotonen Startzeitpunkt, der beim Start der Aufnahme gesetzt wird, und zählt die geschriebenen Frames mit.
- [x] 4.2 Eine Methode berechnet die bei der bisher verstrichenen Zeit erlaubte Framezahl und meldet, ob die Schreibposition sie um mehr als die Toleranz überschreitet.
- [x] 4.3 Toleranz als Modulkonstante: Vorsprung 20 %, Prüfung frühestens nach einigen Sekunden Laufzeit, damit der Anlauf nicht als Störung zählt. Beide Werte mit einem Satz begründen.
- [x] 4.4 Beim Überschreiten: auf die erlaubte Position zurückspulen, kürzen, dort weiterschreiben. Alles unter dem bestehenden `self._lock`, damit es sich nicht mit `close_file()` überschneidet.
- [x] 4.5 Vorfall auf WARNING protokollieren, mit Quelle, geschriebener Tondauer, verstrichener Zeit und dem verworfenen Anteil. Ab der Gerätestörung aus 4.6 gehen weitere Vorfälle derselben Episode nur auf DEBUG, damit eine dauerhaft rasende Spur das Protokoll nicht flutet; nach einer ruhigen Phase gilt wieder WARNING je Vorfall.
- [x] 4.6 Wiederholte Vorfälle innerhalb kurzer Zeit zusätzlich als Gerätestörung protokollieren, damit im Protokoll der Grund steht und nicht nur die Wirkung.
- [x] 4.7 Die Prüfung greift für **beide** Spuren, also in `BaseRecorder`, nicht in `MicRecorder`. Für die Systemspur ist sie die einzige Absicherung, weil `soundcard` keinen Rückruf bietet.

## 5. Tests für das Netz

- [x] 5.1 Test: Mit dem Stream aus 2.3 überschreitet die Spur die verstrichene Zeit nicht; die fertige Datei ist so lang wie die Aufnahme.
- [x] 5.2 Test: Der vor der Störung aufgenommene Ton bleibt erhalten und wird nicht mitverworfen.
- [x] 5.3 Test: Eine reguläre Aufnahme mit geringfügiger Taktabweichung löst kein Zurückspulen und keinen Protokolleintrag aus.
- [x] 5.4 Test: Die Prüfung greift auch für die Systemspur, nicht nur für das Mikrofon.

## 6. Abschluss

- [x] 6.1 `pytest` vollständig laufen lassen; kein bestehender Test darf brechen.
- [x] 6.2 Von Hand aufnehmen, dabei das Mikrofon wechseln (Headset ein- und ausstecken), und prüfen, dass Tondauer und Wanduhrzeit übereinstimmen.
- [x] 6.3 Dasselbe mit einer Aufnahme über 20 Minuten, damit die Prüfung aus Block 4 auch über eine realistische Dauer nicht fälschlich anschlägt.
- [x] 6.4 Das Messskript aus Block 1 erneut über das Aufnahmeverzeichnis laufen lassen: Die neuen Aufnahmen dürfen keine Ausreißer sein.
- [x] 6.5 `openspec validate fix-mic-capture-clock --strict`.
