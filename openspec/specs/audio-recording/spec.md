# audio-recording Specification

## Purpose
Das Ergebnis einer Aufnahme ist die Schnittstelle zum Folgetool: was im Zielverzeichnis liegt, wird transkribiert. Diese Fähigkeit legt fest, was dort ankommt, was im Aufnahmeverzeichnis bleibt und was bei einem Fehler geschieht — damit ein Fehlschlag sichtbar wird, statt sich als doppelte oder unvollständige Verarbeitung im nächsten Werkzeug zu zeigen.

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
