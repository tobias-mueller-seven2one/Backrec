## ADDED Requirements

### Requirement: Diagnose über die Statuszeile des Fensters

Weil die Anwendung kein Symbol im Infobereich betreibt, MUST das Anwendungsfenster selbst den einen Vorgang tragen, den ein Benutzer ohne Kommandozeile daraus anstoßen können MUST: die Diagnose. Das Fenster MUST dafür kein zusätzliches Bedienelement führen, sondern MUST die ohnehin vorhandene Statuszeile anklickbar machen. Ein Klick auf die Statuszeile MUST denselben Vorgang auslösen wie das gleichnamige Kommando mit Bericht, also den Bericht schreiben und im Standardprogramm für Text öffnen. Ein Hovertext MUST sagen, was ein Klick bewirkt.

Der Vorgang MUST außerhalb des Threads laufen, der das Fenster zeichnet, und MUST NOT im Aufnahme-Thread laufen. Er MUST NOT modal sein und MUST NOT auf eine Antwort warten. Er MUST protokolliert werden. Ein zweiter Klick, während der erste Vorgang noch arbeitet, MUST wirkungslos bleiben und MUST NOT einen zweiten Bericht anstoßen. Ein Fehlschlag MUST protokolliert werden und MUST NOT das Fenster beenden.

Der Klick MUST auch während einer laufenden Aufnahme erlaubt sein, weil die Diagnose ausschließlich liest. Er MUST NOT die Aufnahme unterbrechen, verzögern oder ihr Ergebnis verändern, und er MUST NOT den Text der Statuszeile überschreiben, solange die Statuszeile den Zustand der Aufnahme meldet.

Die Schaltfläche, die bisher ein Menü im Anwendungsfenster geöffnet hat, MUST entfallen. Die Breite des Fensters MUST unverändert bleiben, und die Bedienelemente der Aufnahme MUST NOT verdrängt werden.

#### Scenario: Klick auf die Statuszeile

- **WHEN** der Benutzer die Statuszeile im Fenster anklickt
- **THEN** wird der Diagnosebericht geschrieben und im Standardprogramm für Text geöffnet
- **AND** das Fenster bleibt währenddessen bedienbar
- **AND** die Auswahl steht in der Protokolldatei

#### Scenario: Hovertext der Statuszeile

- **WHEN** der Zeiger über der Statuszeile steht
- **THEN** erscheint ein Hovertext, der sagt, dass ein Klick die Diagnose öffnet

#### Scenario: Klick während einer Aufnahme

- **WHEN** eine Aufnahme läuft und der Benutzer die Statuszeile anklickt
- **THEN** entsteht der Bericht
- **AND** die Aufnahme läuft unverändert weiter und ihr Ergebnis bleibt vollständig
- **AND** die Statuszeile meldet weiterhin den Zustand der Aufnahme

#### Scenario: Zweiter Klick während des ersten Vorgangs

- **WHEN** der Benutzer erneut klickt, während der erste Vorgang noch arbeitet
- **THEN** bleibt der zweite Klick wirkungslos
- **AND** es entsteht kein zweiter Bericht

#### Scenario: Fenster ohne Menü-Schaltfläche

- **WHEN** das Fenster betrachtet wird
- **THEN** trägt es keine Schaltfläche, die ein Menü öffnet
- **AND** die Fensterbreite ist unverändert
- **AND** die Bedienelemente der Aufnahme sind vollständig sichtbar

### Requirement: Auskunft über die Installation

Es MUST ein Kommando geben, das Auskunft über die Installation gibt. Die Auskunft MUST Werkzeugname, Version, Repository-Pfad, Konfigurationspfad, den vollständigen Pfad der Einstiegsanleitung `LIES-MICH-ZUERST.txt` und den Weg zur Deinstallation nennen. Sie MUST dabei sagen, dass Konfiguration, Protokolle und Zustand im benutzerbezogenen Anwendungsdatenverzeichnis liegen und getrennt zu löschen sind.

Dieselben Angaben MUST im Kopf des Diagnoseberichts stehen, soweit sie den Zustand der Installation beschreiben, damit ein Benutzer ohne Kommandozeile sie über den Klick auf die Statuszeile erreicht.

#### Scenario: Auskunft über die Kommandozeile

- **WHEN** die Auskunft angefordert wird
- **THEN** nennt sie Werkzeugname, Version, Repository-Pfad und Konfigurationspfad
- **AND** sie nennt den vollständigen Pfad der Einstiegsanleitung `LIES-MICH-ZUERST.txt`
- **AND** sie nennt den Weg zur Deinstallation und den Ort der verbleibenden Daten

#### Scenario: Auskunft ohne Kommandozeile

- **WHEN** ein Benutzer ohne Kommandozeile wissen will, welche Fassung wo installiert ist
- **THEN** nennt der über die Statuszeile erreichbare Bericht Version, Repository-Pfad und Konfigurationspfad

## MODIFIED Requirements

### Requirement: Zugang zu den Protokollen

Es MUST ein Kommando geben, das das Protokollverzeichnis öffnet oder das Protokoll fortlaufend anzeigt. Der Diagnosebericht MUST im selben Verzeichnis liegen wie die Protokolle, damit ein Benutzer ohne Kommandozeile sie über den Klick auf die Statuszeile erreicht. Ein Fehlschlag beim Öffnen MUST protokolliert werden und MUST NOT die Anwendung beenden.

#### Scenario: Protokollverzeichnis öffnen

- **WHEN** das Öffnen der Protokolle angefordert wird
- **THEN** wird das Protokollverzeichnis im Dateimanager angezeigt

#### Scenario: Protokoll fortlaufend anzeigen

- **WHEN** die fortlaufende Anzeige angefordert wird
- **THEN** erscheinen neue Protokollzeilen, während sie geschrieben werden

#### Scenario: Weg zu den Protokollen ohne Kommandozeile

- **WHEN** ein Benutzer ohne Kommandozeile über die Statuszeile die Diagnose auslöst
- **THEN** liegt der geöffnete Bericht im Protokollverzeichnis
- **AND** die Protokolle liegen im selben Verzeichnis

## REMOVED Requirements

### Requirement: Menü im Anwendungsfenster

**Reason**: Fünf Menüeinträge sind für ein Fenster von 280 px Breite mit drei Bedienelementen zu viel, und vier davon sind fachlich redundant: Aktualisieren läuft über ein neues Archiv und einen erneuten Lauf der Einrichtung, Einstellungen ändern über denselben erneuten Lauf, und Protokolle wie Auskunft beantwortet der Diagnosebericht, der im Protokollverzeichnis liegt und Version und Pfade im Kopf führt.

**Migration**: Die Diagnose wird durch einen Klick auf die Statuszeile ausgelöst (neue Anforderung „Diagnose über die Statuszeile des Fensters"). Die Auskunft wandert vollständig in das gleichnamige Kommando (neue Anforderung „Auskunft über die Installation"). Aktualisieren geschieht durch Entpacken eines neueren Release-Archivs über den Ordner und einen erneuten Lauf der Einrichtung; das Kommando zum Aktualisieren mit einem ausgewählten Archiv bleibt unverändert. Die Protokolle bleiben über das gleichnamige Kommando und über das Verzeichnis des Berichts erreichbar.

### Requirement: Öffnen der Einstellungen aus dem Menü

**Reason**: Das Anwendungsfenster ist nicht der Ort, an dem ein Kollege eine Einstellung ändert. Die Einrichtung fragt jeden Schlüssel einzeln, mit Bedeutung und geltendem Wert, und prüft jede Antwort — das nimmt die im Editor geöffnete Datei niemandem ab, für den dieser Weg gedacht war.

**Migration**: Eine Einstellung wird durch einen erneuten Lauf der Einrichtung geändert; sie zeigt die Übersicht der aktuellen Werte und fragt einmal, ob etwas geändert werden soll (`tool-configuration`, „Einstellungen im Setup ändern"). Die Datei lässt sich weiterhin von Hand im Editor öffnen; ihr Ort steht in jeder Abschlussausgabe der Einrichtung und im Kopf des Diagnoseberichts.
