# audio-recording Specification

## Purpose
Das Ergebnis einer Aufnahme ist die Schnittstelle zum Folgetool: was im Zielverzeichnis liegt, wird transkribiert. Diese Fähigkeit legt fest, was dort ankommt, was im Aufnahmeverzeichnis bleibt und was bei einem Fehler geschieht — damit ein Fehlschlag sichtbar wird, statt sich als doppelte oder unvollständige Verarbeitung im nächsten Werkzeug zu zeigen. Außerdem legt sie fest, dass die Tondauer jeder Spur der Dauer der Aufnahme folgt, damit keine unbrauchbar lange Datei in die Transkription gelangt.

## Requirements

### Requirement: Ergebnis einer erfolgreichen Aufnahme

Eine erfolgreich abgeschlossene Aufnahme MUST genau **eine** gemischte Datei im Zielverzeichnis erzeugen. Ihr Name MUST dem Zeitstempelschema der Aufnahme folgen. Trägt das Zielverzeichnis bereits eine Datei dieses Namens, MUST ein eindeutiger Name durch einen angehängten Zähler gebildet werden, und die vorhandene Datei MUST NOT überschrieben werden. Die Kopie MUST vor der Erfolgsmeldung gegen das Original geprüft werden; weicht sie ab, MUST das als Fehlschlag behandelt werden.

#### Scenario: Aufnahme wird abgeschlossen

- **WHEN** eine Aufnahme regulär beendet wird und die Mischung gelingt
- **THEN** liegt genau eine gemischte Datei im Zielverzeichnis
- **AND** ihr Name trägt den Zeitstempel der Aufnahme

#### Scenario: Namenskollision im Zielverzeichnis

- **WHEN** im Zielverzeichnis bereits eine Datei dieses Namens liegt
- **THEN** entsteht ein eindeutiger Name mit angehängtem Zähler
- **AND** die vorhandene Datei bleibt unverändert

#### Scenario: Kopie weicht ab

- **WHEN** die Kopie im Zielverzeichnis nicht mit dem Original übereinstimmt
- **THEN** wird das als Fehlschlag gemeldet
- **AND** es wird kein Erfolg gemeldet

### Requirement: Rohspuren bleiben im Aufnahmeverzeichnis

Die einzelnen Rohspuren MUST im Aufnahmeverzeichnis verbleiben und MUST NOT in das Zielverzeichnis gelangen. Die gemischte Datei MUST zusätzlich im Aufnahmeverzeichnis verbleiben, damit ein fehlgeschlagener Übernahmeschritt wiederholbar ist.

#### Scenario: Rohspuren nach erfolgreicher Aufnahme

- **WHEN** eine Aufnahme erfolgreich abgeschlossen ist
- **THEN** liegen beide Rohspuren im Aufnahmeverzeichnis
- **AND** im Zielverzeichnis liegt keine Rohspur

#### Scenario: Gemischte Datei bleibt lokal

- **WHEN** die gemischte Datei in das Zielverzeichnis übernommen wurde
- **THEN** liegt sie weiterhin auch im Aufnahmeverzeichnis

### Requirement: Verhalten bei fehlgeschlagener Mischung

Scheitert die Mischung — weil ffmpeg fehlt, mit einem Fehler endet, keine brauchbare Ausgabe erzeugt oder weil eine Rohspur fehlt oder zu klein ist — MUST NOT eine Rohspur in das Zielverzeichnis kopiert werden. Die Rohspuren MUST vollständig im Aufnahmeverzeichnis verbleiben. Der Fehlschlag MUST im Fenster sichtbar gemeldet und protokolliert werden, mit der Ursache und dem Verbleib der Rohspuren. Es MUST NOT eine Erfolgsmeldung erscheinen, und im Zielverzeichnis MUST NOT eine unvollständige oder halbfertige Datei entstehen.

#### Scenario: ffmpeg fehlt beim Abschluss

- **WHEN** eine Aufnahme beendet wird und ffmpeg nicht aufrufbar ist
- **THEN** liegt im Zielverzeichnis keine neue Datei
- **AND** beide Rohspuren liegen im Aufnahmeverzeichnis
- **AND** das Fenster meldet den Fehlschlag und nennt ffmpeg als Ursache

#### Scenario: Mischung endet mit einem Fehler

- **WHEN** die Mischung mit einem Fehler endet
- **THEN** gelangt keine Rohspur in das Zielverzeichnis
- **AND** die Ursache steht mit der Fehlerausgabe des Mischvorgangs im Protokoll

#### Scenario: Eine Rohspur fehlt oder ist zu klein

- **WHEN** eine der beiden Rohspuren fehlt oder unbrauchbar klein ist
- **THEN** wird kein Mischversuch als Erfolg gemeldet
- **AND** die vorhandene Rohspur bleibt im Aufnahmeverzeichnis und gelangt nicht in das Zielverzeichnis

#### Scenario: Folgetool sieht keinen Teilstand

- **WHEN** ein Abschluss fehlgeschlagen ist
- **THEN** enthält das Zielverzeichnis keine zusätzliche Datei aus dieser Aufnahme

### Requirement: Wiederherstellung nach einem fehlgeschlagenen Abschluss

Nach einem fehlgeschlagenen Abschluss MUST die Meldung den Ort der Rohspuren nennen, sodass die Mischung nach Beheben der Ursache nachgeholt werden kann. Die Meldung MUST NOT nur im Protokoll stehen, sondern MUST auch im Fenster erscheinen.

#### Scenario: Meldung nennt den Verbleib

- **WHEN** ein Abschluss fehlschlägt
- **THEN** nennt die Meldung im Fenster das Aufnahmeverzeichnis als Verbleib der Rohspuren
- **AND** dieselbe Angabe steht im Protokoll

### Requirement: Verwerfen einer Aufnahme

Wird eine Aufnahme ausdrücklich verworfen, MUST NOT eine Datei in das Zielverzeichnis gelangen, und die Rohspuren dieser Aufnahme MUST aus dem Aufnahmeverzeichnis entfernt werden. Scheitert das Entfernen, MUST das gemeldet werden; das Zielverzeichnis MUST in jedem Fall unberührt bleiben.

#### Scenario: Aufnahme wird verworfen

- **WHEN** eine laufende Aufnahme verworfen wird
- **THEN** liegt keine neue Datei im Zielverzeichnis
- **AND** die Rohspuren dieser Aufnahme sind aus dem Aufnahmeverzeichnis entfernt

#### Scenario: Entfernen der Rohspuren scheitert

- **WHEN** das Entfernen der Rohspuren fehlschlägt
- **THEN** wird das im Fenster und im Protokoll gemeldet
- **AND** das Zielverzeichnis bleibt unverändert

### Requirement: Der Takt einer Aufnahme kommt vom Aufnahmegerät

Eine Aufnahme MUST nur den Ton schreiben, den das Aufnahmegerät liefert, und MUST NOT Ton schneller erzeugen, als er anfällt. Das Fortschreiten der Aufnahme MUST an die Lieferung des Geräts gebunden sein und MUST NOT davon abhängen, dass ein Lesevorgang blockiert.

Liefert das Gerät keinen Ton mehr, MUST die Spur still bleiben oder enden. Sie MUST NOT dadurch wachsen. Der Ausfall MUST protokolliert werden.

#### Scenario: Gerät liefert regulär

- **WHEN** eine Aufnahme über eine bestimmte Zeitspanne läuft und das Gerät durchgehend liefert
- **THEN** entspricht die Tondauer der Spur der verstrichenen Zeit

#### Scenario: Gerät hört auf zu liefern

- **WHEN** das Aufnahmegerät während einer laufenden Aufnahme keinen Ton mehr liefert
- **THEN** wächst die Spur nicht über die verstrichene Zeit hinaus
- **AND** der Ausfall steht im Protokoll

#### Scenario: Aufnahme kann nicht schneller als Echtzeit laufen

- **WHEN** eine Aufnahme beendet wird
- **THEN** ist die Tondauer der Spur nicht größer als die Zeitspanne zwischen Beginn und Ende der Aufnahme

### Requirement: Die geschriebene Tonmenge folgt der verstrichenen Zeit

Jede Spur einer Aufnahme MUST die geschriebene Tonmenge an der seit dem Beginn der Aufnahme verstrichenen Zeit ausrichten. Überschreitet die geschriebene Tonmenge die verstrichene Zeit um mehr als eine festgelegte Toleranz, MUST die Schreibposition auf die der verstrichenen Zeit entsprechende Stelle zurückgesetzt und der überzählige Ton verworfen werden.

Die Aufnahme MUST danach weiterlaufen und MUST brauchbar bleiben: Es MUST NOT die gesamte Aufnahme verworfen werden, und der vor der Störung aufgenommene Ton MUST erhalten bleiben. Der Vorfall MUST protokolliert werden und MUST die betroffene Quelle sowie das Ausmaß der Abweichung nennen.

Diese Ausrichtung MUST für alle Spuren gelten, auch für solche, deren Ton nicht über den Treiber-Rückruf, sondern durch Lesen geholt wird.

Die Toleranz MUST so bemessen sein, dass sie den regulären Taktunterschied zwischen Aufnahmegerät und Systemuhr nicht als Störung wertet.

#### Scenario: Eine Spur läuft der Uhr davon

- **WHEN** eine Spur mehr Ton geschrieben hat, als seit dem Beginn der Aufnahme verstrichen ist, über die Toleranz hinaus
- **THEN** wird die Schreibposition auf die der verstrichenen Zeit entsprechende Stelle zurückgesetzt
- **AND** der überzählige Ton ist aus der Spur entfernt
- **AND** der Vorfall steht mit Quelle und Ausmaß im Protokoll

#### Scenario: Die Aufnahme überlebt die Störung

- **WHEN** eine Störung dieser Art während einer Aufnahme auftritt und danach endet
- **THEN** läuft die Aufnahme weiter und wird regulär abgeschlossen
- **AND** der vor der Störung aufgenommene Ton ist erhalten
- **AND** die Tondauer der fertigen Spur entspricht der Dauer der Aufnahme

#### Scenario: Regulärer Taktunterschied gilt nicht als Störung

- **WHEN** eine Aufnahme regulär läuft und das Aufnahmegerät geringfügig vom Takt der Systemuhr abweicht
- **THEN** wird die Schreibposition nicht zurückgesetzt
- **AND** es entsteht kein Protokolleintrag über eine Störung

#### Scenario: Beide Spuren sind abgesichert

- **WHEN** die Spur, deren Ton durch Lesen geholt wird, der Uhr davonläuft
- **THEN** greift dieselbe Ausrichtung wie bei der über den Treiber-Rückruf versorgten Spur
