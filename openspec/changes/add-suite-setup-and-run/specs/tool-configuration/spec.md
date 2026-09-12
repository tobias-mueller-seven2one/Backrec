## Purpose

Die Konfiguration legt fest, wohin Backrec seine Aufnahmen schreibt und in welchen Ordner das Ergebnis für das Folgetool gelangt. Sie liegt außerhalb des Repositorys, ist eindeutig geschichtet, wird streng geprüft und macht ein Repository, das man neu klonen oder verschieben kann, ohne Einstellungen zu verlieren.

## ADDED Requirements

### Requirement: Ort der Konfiguration außerhalb des Repositorys

Konfiguration, Protokolle und Zustand MUST unterhalb eines benutzerbezogenen Anwendungsdatenverzeichnisses in einem eigenen Unterverzeichnis für dieses Werkzeug liegen und MUST NOT im Repository liegen. Der Ort des gesamten Suite-Verzeichnisses MUST über eine Umgebungsvariable verschiebbar sein; die Konfigurationsdatei selbst MUST über eine werkzeugeigene Umgebungsvariable auf eine andere Datei umgelenkt werden können. Alle Pfade MUST aus der Lage des Programmcodes bzw. aus dem Benutzerprofil abgeleitet werden und MUST NOT aus dem aktuellen Arbeitsverzeichnis.

#### Scenario: Ort ohne Umgebungsvariablen

- **WHEN** keine der beiden Umgebungsvariablen gesetzt ist
- **THEN** liegen Konfiguration, Protokolle und Zustand im werkzeugeigenen Unterverzeichnis des Suite-Verzeichnisses unter den Anwendungsdaten des Benutzers

#### Scenario: Verschobenes Suite-Verzeichnis

- **WHEN** die Umgebungsvariable für das Suite-Verzeichnis auf ein anderes Verzeichnis zeigt
- **THEN** liegen Konfiguration, Protokolle und Zustand unterhalb dieses Verzeichnisses

#### Scenario: Umgelenkte Konfigurationsdatei

- **WHEN** die werkzeugeigene Umgebungsvariable auf eine andere Konfigurationsdatei zeigt
- **THEN** wird diese Datei gelesen
- **AND** Protokolle und Zustand bleiben an ihrem regulären Ort

#### Scenario: Start aus einem fremden Arbeitsverzeichnis

- **WHEN** die Anwendung mit einem anderen Arbeitsverzeichnis als dem Repository gestartet wird
- **THEN** findet sie dieselbe Konfiguration wie beim Start aus dem Repository

### Requirement: Format und Schlüssel der Konfiguration

Die Konfiguration MUST in einem kommentierbaren Textformat vorliegen und MUST mindestens die Schlüssel für das Aufnahmeverzeichnis und das Zielverzeichnis führen. Beide Schlüssel MUST Pflichtwerte sein. Ein unbekannter Schlüssel MUST NOT stillschweigend ignoriert werden, sondern MUST von der Diagnose gemeldet werden.

#### Scenario: Vollständige Konfiguration

- **WHEN** die Konfigurationsdatei beide Pflichtschlüssel mit gültigen Pfaden führt
- **THEN** startet die Anwendung mit genau diesen Verzeichnissen

#### Scenario: Fehlender Pflichtschlüssel

- **WHEN** einer der beiden Pflichtschlüssel fehlt
- **THEN** startet die Anwendung nicht
- **AND** die Meldung nennt den fehlenden Schlüssel und die Datei, in der er fehlt

#### Scenario: Nicht lesbare Datei

- **WHEN** die Konfigurationsdatei vorhanden, aber nicht parsebar ist
- **THEN** startet die Anwendung nicht
- **AND** die Meldung nennt Datei, Zeile und die Art des Fehlers

### Requirement: Schichtung der Werte

Werte MUST in dieser Reihenfolge zunehmender Stärke gelten: Vorgaben im Programmcode, Konfigurationsdatei, Umgebungsvariablen mit dem werkzeugeigenen Präfix, Kommandozeilenoptionen. Die bestehenden Umgebungsvariablen für Aufnahme- und Zielverzeichnis MUST weiterhin wirken und MUST die Konfigurationsdatei überschreiben. Es MUST NOT eine zweite lokale Konfigurationsdatei im Repository ausgewertet werden.

#### Scenario: Umgebungsvariable überschreibt die Datei

- **WHEN** die Konfigurationsdatei ein Zielverzeichnis führt und die zugehörige Umgebungsvariable ein anderes nennt
- **THEN** verwendet die Anwendung das Verzeichnis aus der Umgebungsvariable

#### Scenario: Kommandozeile überschreibt die Umgebung

- **WHEN** ein Wert sowohl über eine Umgebungsvariable als auch über eine Kommandozeilenoption gesetzt ist
- **THEN** gilt der Wert der Kommandozeilenoption

#### Scenario: Herkunft ist auskunftsfähig

- **WHEN** die Diagnose die Konfiguration prüft
- **THEN** nennt sie für jeden wirksamen Wert die Schicht, aus der er stammt

### Requirement: Vorlage im Repository ohne Nutzerpfade

Das Repository MUST eine vollständige, kommentierte Vorlage der Konfiguration enthalten. Die Vorlage MUST NOT Nutzerpfade, Firmennamen, Namen von Cloud-Speicherorten oder sonstige Angaben zu einer konkreten Installation enthalten, sondern MUST Platzhalter und die Ableitung aus dem Basisordner beschreiben. Das Repository MUST NOT eine gefüllte Konfiguration enthalten, und eine gefüllte Konfiguration MUST von der Versionsverwaltung ignoriert werden.

#### Scenario: Vorlage enthält keine Installationsangaben

- **WHEN** die Vorlage gelesen wird
- **THEN** enthält sie ausschließlich Platzhalter und Kommentare
- **AND** sie nennt keinen konkreten Benutzer-, Firmen- oder Cloud-Speicherort

#### Scenario: Gefüllte Konfiguration wird nicht versioniert

- **WHEN** eine gefüllte Konfigurationsdatei im Repository angelegt wird
- **THEN** wird sie von der Versionsverwaltung ignoriert

### Requirement: Neue Schlüssel der Vorlage ergänzt das Einrichten

Das Einrichten MUST Schlüssel, die die Vorlage führt und die lokale Datei nicht hat, mit dem Wert und dem Kommentar der Vorlage in die lokale Datei schreiben und MUST das in einer Zeile melden. Vorhandene Werte MUST NOT dabei überschrieben, verschoben oder entfernt werden. Die ergänzte Datei MUST danach lesbar bleiben, und ein neuer Schlüssel MUST NOT hinter einem Abschnittskopf landen, weil er dort zu einem anderen Namen würde. Ein zweiter Lauf MUST die Datei unverändert lassen. Ein Kollege MUST NOT einen Schlüssel von Hand anlegen müssen. Fehlt die lokale Datei, MUST das Ergänzen nichts anlegen; dafür ist das Anlegen aus der Vorlage zuständig.

#### Scenario: Vorlage führt einen neuen Schlüssel

- **WHEN** das Einrichten läuft und die Vorlage einen Schlüssel führt, den die lokale Datei nicht hat
- **THEN** steht der Schlüssel danach mit dem Wert der Vorlage in der lokalen Datei
- **AND** über ihm steht der Kommentar aus der Vorlage
- **AND** die Ausgabe meldet die Anzahl der ergänzten Einstellungen in einer Zeile

#### Scenario: Vorhandener Wert bleibt

- **WHEN** die lokale Datei einen Schlüssel führt, dessen Wert von der Vorlage abweicht
- **THEN** bleibt dieser Wert unverändert

#### Scenario: Zweiter Lauf

- **WHEN** das Einrichten ein zweites Mal läuft und nichts fehlt
- **THEN** bleibt die Datei unverändert
- **AND** es wird nichts gemeldet

#### Scenario: Lokale Datei mit eigenem Abschnitt

- **WHEN** die lokale Datei einen Abschnittskopf enthält
- **THEN** steht der ergänzte Schlüssel vor dem ersten Abschnittskopf
- **AND** die Datei bleibt lesbar

### Requirement: Ableitung der Verzeichnisse aus einem Basisordner

Die Einrichtung MUST einen Basisordner für die Datenkette erfragen und daraus beide Verzeichnisse vorschlagen: das Zielverzeichnis als Eingangsordner unterhalb des Basisordners, das Aufnahmeverzeichnis ausdrücklich **außerhalb** eines Cloud-synchronisierten Ordners im Benutzerprofil. Der Vorschlag MUST vor dem Schreiben zur Bestätigung angezeigt werden. Beide Werte MUST anschließend ausdrücklich in der eigenen Konfiguration stehen; die Anwendung MUST NOT sie zur Laufzeit erneut aus dem Basisordner ableiten.

#### Scenario: Ableitung wird vorgeschlagen

- **WHEN** die Einrichtung den Basisordner kennt
- **THEN** zeigt sie beide abgeleiteten Verzeichnisse zur Bestätigung an
- **AND** das Aufnahmeverzeichnis liegt nicht unterhalb eines Cloud-synchronisierten Ordners

#### Scenario: Werte stehen ausdrücklich in der Konfiguration

- **WHEN** die Einrichtung die Konfiguration geschrieben hat
- **THEN** enthält die Datei beide Verzeichnisse als ausdrückliche Werte
- **AND** ein späterer Start funktioniert ohne Kenntnis des Basisordners

#### Scenario: Abweichende Bestätigung

- **WHEN** der Benutzer einen der Vorschläge durch einen eigenen Pfad ersetzt
- **THEN** wird der eigene Pfad geschrieben
- **AND** der Basisordner bleibt für den anderen Wert wirksam

### Requirement: Optionaler Handshake über den Basisordner

Existiert eine suiteweite Handshake-Datei mit einem Basisordner, MUST die Einrichtung diesen Wert vorschlagen. Existiert sie nicht, MUST die Einrichtung nach der Abfrage anbieten, sie zu schreiben. Die Anwendung MUST NOT diese Datei zur Laufzeit lesen und MUST NOT ihre Existenz voraussetzen.

#### Scenario: Handshake-Datei ist vorhanden

- **WHEN** die Einrichtung läuft und die Handshake-Datei einen Basisordner führt
- **THEN** wird dieser Wert als Vorgabe vorgeschlagen
- **AND** der Benutzer kann ihn bestätigen oder ersetzen

#### Scenario: Handshake-Datei fehlt

- **WHEN** die Einrichtung läuft und die Handshake-Datei nicht existiert
- **THEN** bietet sie nach der Abfrage an, sie mit dem gewählten Basisordner zu schreiben
- **AND** eine Ablehnung beeinträchtigt die Einrichtung nicht

#### Scenario: Laufzeit ohne Handshake

- **WHEN** die Anwendung startet und die Handshake-Datei nicht existiert
- **THEN** startet sie unverändert

### Requirement: Migration einer vorhandenen Konfiguration aus dem Repository

Findet die Einrichtung im Repository eine Konfiguration des bisherigen Formats, MUST sie deren Werte einmalig in die neue Konfigurationsdatei übernehmen und die Übernahme melden, einschließlich Quell- und Zielpfad und der übernommenen Schlüssel. Eine bereits vorhandene neue Konfigurationsdatei MUST NOT überschrieben werden. Die alte Datei MUST NOT gelöscht werden; die Meldung MUST sagen, dass sie ab jetzt unwirksam ist.

#### Scenario: Übernahme aus der alten Datei

- **WHEN** die Einrichtung läuft, im Repository eine alte Konfiguration liegt und noch keine neue existiert
- **THEN** enthält die neue Datei danach die Werte der alten
- **AND** die Ausgabe nennt Quelle, Ziel und die übernommenen Schlüssel
- **AND** die alte Datei bleibt liegen und wird als unwirksam gekennzeichnet

#### Scenario: Neue Datei existiert bereits

- **WHEN** die Einrichtung läuft und beide Dateien existieren
- **THEN** bleibt die neue Datei unverändert
- **AND** die Ausgabe meldet, dass keine Übernahme stattgefunden hat

#### Scenario: Alte Datei ist unvollständig

- **WHEN** die alte Datei nur einen der beiden Werte führt
- **THEN** wird dieser Wert übernommen und der fehlende aus dem Basisordner abgeleitet und zur Bestätigung angezeigt

### Requirement: Expansion und Prüfung von Pfadwerten

Pfadwerte MUST vor der Verwendung expandiert werden: Umgebungsvariablen in Windows- und in Unix-Schreibweise sowie die Kurzform für das Benutzerverzeichnis. Nach der Expansion MUST jeder Pfadwert absolut sein. Ein relativer, leerer oder nach der Expansion unauflösbarer Pfad MUST als Konfigurationsfehler behandelt werden.

#### Scenario: Variable im Pfadwert

- **WHEN** ein Pfadwert eine Umgebungsvariable enthält
- **THEN** wird sie vor der Verwendung ersetzt
- **AND** die Anwendung arbeitet mit dem expandierten, absoluten Pfad

#### Scenario: Unauflösbare Variable

- **WHEN** ein Pfadwert eine Variable enthält, die nicht gesetzt ist
- **THEN** wird der Wert als Konfigurationsfehler gemeldet
- **AND** die Meldung nennt Schlüssel und unaufgelösten Namen

#### Scenario: Relativer Pfad

- **WHEN** ein Pfadwert nach der Expansion relativ ist
- **THEN** wird er als Konfigurationsfehler gemeldet

### Requirement: Zielverzeichnis als Schnittstelle zum Folgetool

Die Konfiguration MUST das Zielverzeichnis als Pflichtwert und als Schnittstelle zum Folgetool ausweisen. Die Dokumentation MUST NOT es als optionalen Komfortwert darstellen. Zeigt das Zielverzeichnis nach der Prüfung nicht auf einen vorhandenen, beschreibbaren Ordner, MUST das als Fehler behandelt werden, nicht als Warnung.

#### Scenario: Zielverzeichnis ist nicht beschreibbar

- **WHEN** das konfigurierte Zielverzeichnis existiert, aber nicht beschreibbar ist
- **THEN** wird das als Fehler gemeldet
- **AND** die Meldung nennt den Pfad und dass die Kette zum Folgetool damit unterbrochen ist

#### Scenario: Dokumentation weist den Pflichtcharakter aus

- **WHEN** die Dokumentation zur Konfiguration gelesen wird
- **THEN** ist das Zielverzeichnis als Pflichtwert und als Eingang des Folgetools beschrieben
