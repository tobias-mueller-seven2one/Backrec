# run-lifecycle Specification

## Purpose
Der Laufzeitzyklus umfasst alles zwischen Doppelklick und geschlossenem Fenster: die Prüfung der Betriebsvoraussetzungen vor dem Start, den fensterlosen Start genau einer Instanz, die Auskunft über den Zustand, das Beenden von außen und das Beenden durch den Benutzer, auch mitten in einer laufenden Aufnahme.

## Requirements

### Requirement: Fensterloser Start ohne Installationsschritte

Der Start MUST die Anwendung ohne Konsolenfenster starten und MUST den Interpreter der eingerichteten Umgebung ausdrücklich über seinen Pfad verwenden, nicht über die Suchreihenfolge des Systems. Der Start MUST NOT Abhängigkeiten installieren, eine Umgebung erzeugen oder eine Konfiguration schreiben. Fehlt die Umgebung, MUST der Start mit dem Hinweis auf die Einrichtung abbrechen.

#### Scenario: Start bei eingerichteter Installation

- **WHEN** der Start angefordert wird und die Installation eingerichtet ist
- **THEN** erscheint das Anwendungsfenster
- **AND** es öffnet sich kein Konsolenfenster
- **AND** es wird keine Abhängigkeit installiert

#### Scenario: Start ohne Einrichtung

- **WHEN** der Start angefordert wird und die Umgebung fehlt
- **THEN** startet die Anwendung nicht
- **AND** die Meldung nennt die Einrichtung als nächsten Schritt
- **AND** der Exit-Code ist ungleich 0

### Requirement: Protokollierung in eine Datei, bevor Konfiguration gelesen wird

Die Anwendung MUST in eine Datei unterhalb des werkzeugeigenen Protokollverzeichnisses protokollieren, mit Größenbegrenzung und mehreren Sicherungsstufen, in UTF-8 und mit vollständigem Zeitstempel einschließlich Datum. Die Protokollierung MUST eingerichtet werden, **bevor** die Konfiguration gelesen wird, damit ein Konfigurationsfehler protokolliert wird. Ein Fehler beim Schreiben des Protokolls MUST NOT die Anwendung beenden. Eine Ausgabe auf die Konsole MUST NOT erfolgen, wenn kein Terminal angeschlossen ist. Betriebsmeldungen MUST NOT über eine direkte Standardausgabe erfolgen.

#### Scenario: Konfigurationsfehler wird protokolliert

- **WHEN** die Anwendung startet und die Konfiguration nicht gelesen werden kann
- **THEN** steht die Ursache in der Protokolldatei
- **AND** die Protokolldatei wurde vor dem Lesen der Konfiguration angelegt

#### Scenario: Rotation

- **WHEN** die Protokolldatei die festgelegte Größe überschreitet
- **THEN** wird sie umbenannt und eine neue begonnen
- **AND** es bleiben höchstens die festgelegte Anzahl Sicherungen erhalten

#### Scenario: Nicht beschreibbares Protokollverzeichnis

- **WHEN** das Protokollverzeichnis nicht beschreibbar ist
- **THEN** läuft die Anwendung weiter
- **AND** die Aufnahmefähigkeit bleibt unberührt

#### Scenario: Start ohne Terminal

- **WHEN** die Anwendung fensterlos ohne angeschlossenes Terminal läuft
- **THEN** wird kein Konsolen-Handler verwendet
- **AND** alle Meldungen stehen dennoch in der Protokolldatei

### Requirement: Prüfende Startsequenz mit sichtbarem Fehler

Vor dem Öffnen des Fensters MUST geprüft werden: Konfiguration vorhanden und valide, Aufnahme- und Zielverzeichnis anlegbar bzw. vorhanden und beschreibbar, ffmpeg aufrufbar. Das Anlegen von Verzeichnissen MUST NOT beim Laden eines Moduls geschehen, sondern MUST Teil dieser Sequenz sein. Scheitert eine Prüfung, MUST die Anwendung einen Fehlerdialog mit Ursache und nächstem Schritt anzeigen, MUST den Fehler protokollieren und MUST mit einem Exit-Code ungleich 0 enden. Sie MUST NOT still ausbleiben.

#### Scenario: Ungültiges Aufnahmeverzeichnis

- **WHEN** das konfigurierte Aufnahmeverzeichnis nicht angelegt werden kann
- **THEN** erscheint ein Fehlerdialog mit Pfad und Ursache
- **AND** die Ursache steht im Protokoll
- **AND** der Exit-Code ist ungleich 0

#### Scenario: ffmpeg fehlt beim Start

- **WHEN** ffmpeg beim Start nicht aufrufbar ist
- **THEN** erscheint ein Fehlerdialog, der ffmpeg als Ursache und die Einrichtung als nächsten Schritt nennt
- **AND** es wird keine Aufnahmesitzung begonnen

#### Scenario: Fehlerdialog statt stiller Fehlstart

- **WHEN** eine Betriebsvoraussetzung nicht erfüllt ist und die Anwendung fensterlos gestartet wurde
- **THEN** ist der Fehler auf dem Bildschirm sichtbar
- **AND** kein Fehlerfall endet ohne Fenster und ohne Protokolleintrag

#### Scenario: Alle Prüfungen erfüllt

- **WHEN** alle Prüfungen erfüllt sind
- **THEN** öffnet sich das Anwendungsfenster
- **AND** beide Verzeichnisse existieren danach

### Requirement: Genau eine Instanz je Installation

Die Anwendung MUST einen Zustandsdatensatz über die laufende Instanz führen, der Prozesskennung, Startzeitpunkt des Prozesses, Startzeit und das Repository enthält. Der Datensatz MUST nur als gültig gelten, wenn der Prozess lebt, sein Startzeitpunkt übereinstimmt und das Repository übereinstimmt. Ein Datensatz, der diese Prüfung nicht besteht, MUST übernommen werden und MUST NOT zu einer dauerhaften Blockade führen. Ein zweiter Start bei gültigem Datensatz MUST das bestehende Fenster in den Vordergrund holen oder, wenn das nicht möglich ist, melden, dass die Anwendung bereits läuft; er MUST einen Protokolleintrag schreiben, MUST mit Exit-Code 3 enden und MUST die laufende Instanz unberührt lassen.

#### Scenario: Zweiter Start bei laufender Instanz

- **WHEN** der Start angefordert wird und eine Instanz gültig läuft
- **THEN** wird das bestehende Fenster in den Vordergrund geholt oder das Laufen gemeldet
- **AND** es entsteht kein zweites Fenster
- **AND** der Exit-Code ist 3 und ein Protokolleintrag ist geschrieben

#### Scenario: Verwaister Zustandsdatensatz

- **WHEN** ein Datensatz existiert, aber kein lebender Prozess dazu gehört
- **THEN** wird der Datensatz übernommen und die Anwendung startet

#### Scenario: Wiederverwendete Prozesskennung

- **WHEN** ein Datensatz auf eine Prozesskennung zeigt, die inzwischen ein anderer Prozess trägt
- **THEN** erkennt die Prüfung den abweichenden Startzeitpunkt
- **AND** der Datensatz wird übernommen und die Anwendung startet

#### Scenario: Zweite Installation desselben Werkzeugs

- **WHEN** eine Instanz aus einem anderen Repository läuft
- **THEN** blockiert deren Datensatz diesen Start nicht
- **AND** die Meldung nennt das abweichende Repository

### Requirement: Beenden von außen

Das Beenden MUST die Anwendung samt aller von ihr gestarteten Prozesse beenden und MUST den Zustandsdatensatz danach entfernen. Der Erfolg MUST daran gemessen werden, dass kein Prozess der Anwendung mehr läuft, nicht daran, dass ein Signal gesendet wurde. Läuft keine Instanz, MUST das Beenden dies melden und ohne Fehler enden. Eine laufende Aufnahme MUST vor dem Beenden abgeschlossen werden, sodass kein Ergebnis verloren geht; erst nach einer Frist MUST der Prozessbaum hart beendet werden.

#### Scenario: Beenden bei laufender Anwendung

- **WHEN** das Beenden angefordert wird und die Anwendung läuft
- **THEN** läuft danach kein Prozess der Anwendung mehr
- **AND** der Zustandsdatensatz ist entfernt

#### Scenario: Beenden während einer Aufnahme

- **WHEN** das Beenden angefordert wird, während eine Aufnahme läuft
- **THEN** wird die Aufnahme zuvor regulär abgeschlossen
- **AND** das Ergebnis der Aufnahme ist danach vorhanden

#### Scenario: Beenden ohne laufende Instanz

- **WHEN** das Beenden angefordert wird und keine Instanz läuft
- **THEN** meldet der Vorgang, dass nichts zu beenden war
- **AND** er endet ohne Fehler

#### Scenario: Nicht reagierender Prozess

- **WHEN** die Anwendung innerhalb der Frist nicht endet
- **THEN** wird ihr Prozessbaum hart beendet
- **AND** der Vorgang protokolliert, dass die Frist überschritten wurde

### Requirement: Sauberes Beenden durch den Benutzer während einer Aufnahme

Das Schließen des Fensters MUST abgefangen werden. Läuft eine Aufnahme, MUST das Schließen entweder die vollständige Abschlusssequenz ausführen — Aufnahmefäden beenden, Dateien schließen, mischen, Ergebnis in das Zielverzeichnis übernehmen — oder den Benutzer entscheiden lassen, ob abgeschlossen oder verworfen wird. Das Schließen MUST NOT dazu führen, dass eine begonnene Aufnahme ohne Mischung und ohne Übernahme endet. Während der Abschlusssequenz MUST das Fenster einen Fortschritt zeigen und MUST NOT ein zweites Schließen dieselbe Sequenz erneut starten.

#### Scenario: Fenster schließen während einer Aufnahme

- **WHEN** der Benutzer das Fenster schließt, während eine Aufnahme läuft
- **THEN** wird die Aufnahme abgeschlossen und das Ergebnis in das Zielverzeichnis übernommen, oder der Benutzer entscheidet zwischen Abschließen und Verwerfen
- **AND** in keinem Fall endet die Aufnahme ohne Mischung und ohne Entscheidung

#### Scenario: Fenster schließen ohne laufende Aufnahme

- **WHEN** der Benutzer das Fenster schließt und keine Aufnahme läuft
- **THEN** endet die Anwendung unmittelbar
- **AND** der Zustandsdatensatz ist danach entfernt

#### Scenario: Zweites Schließen während des Abschlusses

- **WHEN** der Benutzer das Fenster erneut schließt, während die Abschlusssequenz läuft
- **THEN** läuft die Sequenz unverändert weiter
- **AND** sie wird nicht ein zweites Mal begonnen

#### Scenario: Fehler während des Abschlusses

- **WHEN** die Abschlusssequenz beim Schließen fehlschlägt
- **THEN** wird der Fehler sichtbar gemeldet und protokolliert
- **AND** die Rohaufnahmen bleiben erhalten

### Requirement: Statusauskunft

Die Statusauskunft MUST melden, ob die Anwendung läuft, und dazu Prozesskennung, Startzeit, Repository, den Ort der Konfiguration, den Ort der Protokolle, ob eine Aufnahme läuft und ob eine Desktop-Verknüpfung eingerichtet ist. Die Angaben MUST aus dem Zustandsdatensatz und dem Dateisystem gelesen und MUST NOT aus Vorgabewerten abgeleitet werden. Läuft die Anwendung nicht, MUST die Auskunft das melden und ohne Fehler enden.

#### Scenario: Auskunft bei laufender Anwendung

- **WHEN** die Statusauskunft angefordert wird und die Anwendung läuft
- **THEN** nennt sie Prozesskennung, Startzeit und Repository der laufenden Instanz
- **AND** sie nennt Konfigurations- und Protokollort sowie den Zustand der Verknüpfung

#### Scenario: Auskunft ohne laufende Anwendung

- **WHEN** die Statusauskunft angefordert wird und keine Instanz läuft
- **THEN** meldet sie, dass die Anwendung nicht läuft
- **AND** sie endet ohne Fehler

### Requirement: Menü im Anwendungsfenster

Weil die Anwendung kein Symbol im Infobereich betreibt, MUST das Anwendungsfenster selbst die Funktionen tragen, die dort sonst liegen. Das Fenster MUST eine dauerhaft sichtbare Schaltfläche führen, die ein Menü mit diesen fünf Einträgen in dieser Reihenfolge öffnet: Aktualisieren, Diagnose, Protokolle öffnen, Einstellungen öffnen und Auskunft über die Installation. Die Reihenfolge MUST der suiteweiten Reihenfolge entsprechen, in der das Öffnen der Einstellungen zwischen dem Öffnen der Protokolle und der Auskunft steht. Die Schaltfläche MUST NOT die Fensterbreite verändern und MUST NOT die Bedienelemente der Aufnahme verdrängen. Die Auskunft MUST Werkzeugname, Version, Repository-Pfad, Konfigurationspfad, den vollständigen Pfad der Einstiegsanleitung `LIES-MICH-ZUERST.txt` und den Weg zur Deinstallation nennen. Jede Menüauswahl MUST protokolliert werden. Während eine langlaufende Menüaktion arbeitet, MUST das Menü deaktiviert sein und der Vorgang MUST im Fenster sichtbar sein. Während einer laufenden Aufnahme MUST Aktualisieren, Diagnose und das Öffnen der Einstellungen deaktiviert sein. Die Menüeinträge MUST dieselben Vorgänge auslösen wie die gleichnamigen Kommandos.

#### Scenario: Menü öffnen

- **WHEN** der Benutzer die Schaltfläche im Fenster anklickt
- **THEN** erscheint ein Menü mit Aktualisieren, Diagnose, Protokolle öffnen, Einstellungen öffnen und Auskunft in dieser Reihenfolge
- **AND** die Fensterbreite bleibt unverändert

#### Scenario: Auskunft über die Installation

- **WHEN** der Benutzer die Auskunft wählt
- **THEN** nennt sie Werkzeugname, Version, Repository-Pfad und Konfigurationspfad
- **AND** sie nennt den vollständigen Pfad der Einstiegsanleitung `LIES-MICH-ZUERST.txt`
- **AND** sie nennt den Weg zur Deinstallation

#### Scenario: Menü während einer Aufnahme

- **WHEN** eine Aufnahme läuft und der Benutzer das Menü öffnet
- **THEN** sind Aktualisieren, Diagnose und das Öffnen der Einstellungen nicht auswählbar
- **AND** der Grund ist erkennbar

#### Scenario: Langlaufende Menüaktion

- **WHEN** eine über das Menü angestoßene Aktion arbeitet
- **THEN** ist das Menü währenddessen deaktiviert
- **AND** das Fenster zeigt den laufenden Vorgang

#### Scenario: Menüauswahl wird protokolliert

- **WHEN** der Benutzer einen Menüeintrag wählt
- **THEN** steht die Auswahl in der Protokolldatei

### Requirement: Zugang zu den Protokollen

Es MUST ein Kommando geben, das das Protokollverzeichnis öffnet oder das Protokoll fortlaufend anzeigt, und derselbe Vorgang MUST über das Menü im Anwendungsfenster erreichbar sein. Ein Fehlschlag beim Öffnen MUST protokolliert werden und MUST NOT die Anwendung beenden.

#### Scenario: Protokollverzeichnis öffnen

- **WHEN** das Öffnen der Protokolle angefordert wird
- **THEN** wird das Protokollverzeichnis im Dateimanager angezeigt

#### Scenario: Protokoll fortlaufend anzeigen

- **WHEN** die fortlaufende Anzeige angefordert wird
- **THEN** erscheinen neue Protokollzeilen, während sie geschrieben werden

### Requirement: Öffnen der Einstellungen aus dem Menü

Das Menü im Anwendungsfenster MUST die Konfigurationsdatei im Standardprogramm für Text öffnen können, damit ein Benutzer ohne Kommandozeile einen Wert auch dann ändern kann, wenn er die Einrichtung nicht noch einmal laufen lassen will. Der Eintrag MUST zwischen dem Öffnen der Protokolle und der Auskunft über die Installation stehen. Die Auswahl MUST protokolliert werden. Das Öffnen MUST NOT den Hauptthread des Fensters blockieren. Nach dem Öffnen MUST ein Hinweis sagen, dass eine Änderung erst nach dem nächsten Start des Werkzeugs gilt. Existiert noch keine Konfiguration, MUST der Hinweis stattdessen auf die Einrichtung verweisen. Ein fehlgeschlagenes Öffnen MUST den Ort der Datei nennen und MUST NOT das Fenster beenden.

#### Scenario: Einstellungen öffnen

- **WHEN** der Benutzer das Öffnen der Einstellungen wählt
- **THEN** öffnet sich die Konfigurationsdatei im Standardprogramm für Text
- **AND** ein Hinweis sagt, dass die Änderung nach dem nächsten Start gilt
- **AND** das Fenster bleibt währenddessen bedienbar

#### Scenario: Es gibt noch keine Einstellungen

- **WHEN** der Benutzer das Öffnen wählt und keine Konfiguration existiert
- **THEN** nennt der Hinweis die Einrichtung als nächsten Schritt

#### Scenario: Kein Programm für Text vorhanden

- **WHEN** das Öffnen fehlschlägt
- **THEN** nennt die Meldung den Ort der Konfigurationsdatei
- **AND** das Fenster bleibt bestehen
