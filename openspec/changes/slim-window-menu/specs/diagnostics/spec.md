## MODIFIED Requirements

### Requirement: Bericht als weitergebbare Textdatei

Wird die Diagnose aus der Bedienoberfläche angefordert, MUST ihr Ergebnis zusätzlich als Textdatei im Protokollverzeichnis abgelegt und im Standard-Editor des Benutzers geöffnet werden. Der Zugangsweg aus der Bedienoberfläche MUST der Klick auf die Statuszeile des Anwendungsfensters sein; es MUST keinen zweiten Zugangsweg aus dem Fenster geben. Der Bericht MUST in seinem Kopf Werkzeugname, Version, Repository-Pfad, Konfigurationspfad und einen Zeitstempel führen und danach alle Befunde in derselben Form wie die lesbare Ausgabe enthalten. Der Dateiname MUST den Zeitstempel tragen, damit ein früherer Bericht nicht überschrieben wird. Das Schreiben des Berichts MUST die einzige Veränderung sein, die eine Diagnose vornimmt, und MUST NOT den Zustand oder die Anzeige der Anwendung verändern.

Weil die Diagnose ausschließlich liest, MUST dieser Zugangsweg auch während einer laufenden Aufnahme offenstehen. Der Bericht MUST dabei vollständig entstehen, und die laufende Aufnahme MUST unberührt bleiben — weder unterbrochen noch verzögert, und ihr Ergebnis MUST unverändert sein.

#### Scenario: Bericht wird erzeugt und geöffnet

- **WHEN** die Diagnose aus der Bedienoberfläche angefordert wird
- **THEN** liegt danach eine Textdatei mit dem Ergebnis im Protokollverzeichnis
- **AND** sie wird im Standard-Editor angezeigt

#### Scenario: Zugang aus dem Fenster

- **WHEN** ein Benutzer im Anwendungsfenster die Diagnose auslösen will
- **THEN** tut er das durch einen Klick auf die Statuszeile
- **AND** das Fenster bietet keinen zweiten Weg dorthin an

#### Scenario: Kopf des Berichts

- **WHEN** der Bericht gelesen wird
- **THEN** nennt sein Kopf Werkzeugname, Version, Repository-Pfad, Konfigurationspfad und Zeitstempel

#### Scenario: Früherer Bericht bleibt erhalten

- **WHEN** die Diagnose ein zweites Mal angefordert wird
- **THEN** entsteht eine zweite Datei
- **AND** der frühere Bericht bleibt unverändert

#### Scenario: Zustand bleibt unverändert

- **WHEN** die Diagnose aus der Bedienoberfläche läuft
- **THEN** ändert sich weder die Anzeige der Anwendung noch ihr Zustand
- **AND** außer dem Bericht und dem Protokolleintrag entsteht keine Schreibwirkung

#### Scenario: Bericht während einer laufenden Aufnahme

- **WHEN** die Diagnose aus der Bedienoberfläche angefordert wird, während eine Aufnahme läuft
- **THEN** entsteht der Bericht vollständig und wird geöffnet
- **AND** die Aufnahme läuft unverändert weiter
- **AND** ihr Ergebnis ist nach dem Ende der Aufnahme unverändert vollständig
