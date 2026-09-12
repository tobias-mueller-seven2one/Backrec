## Purpose

Backrec ist die einzige interaktive Anwendung der Suite: sie wird begonnen, wenn ein Gespräch beginnt, und nicht beim Anmelden. Die Desktop-Verknüpfung ist deshalb ihr Startweg — ein Symbol, das die Anwendung fensterlos startet, von der Einrichtung selbst angelegt, geprüft und entfernt statt von Hand gezogen.

## ADDED Requirements

### Requirement: Automatische Anlage am Ende der Einrichtung

Die Einrichtung MUST am Ende fragen, ob eine Verknüpfung auf dem Desktop angelegt werden soll, mit Zustimmung als Vorgabe. Bei Zustimmung MUST sie die Verknüpfung selbst anlegen; sie MUST NOT einen manuellen Handgriff des Benutzers verlangen, weil der Desktop keine Anmeldepersistenz ist. Bei Ablehnung MUST die Einrichtung ohne Verknüpfung fortfahren und MUST NOT als fehlgeschlagen gelten. Existiert bereits eine gültige Verknüpfung auf dieses Repository, MUST die Frage entfallen und der Schritt als erledigt gemeldet werden. Schlägt das Anlegen fehl, MUST das als Warnung erscheinen und den Abschluss der Einrichtung MUST NOT verhindern.

#### Scenario: Zustimmung mit der Eingabetaste

- **WHEN** die Einrichtung nach der Verknüpfung fragt und der Benutzer die Eingabetaste drückt
- **THEN** wird die Verknüpfung angelegt
- **AND** der Benutzer musste keine Datei kopieren oder ziehen

#### Scenario: Ablehnung

- **WHEN** der Benutzer die Verknüpfung ablehnt
- **THEN** wird keine angelegt
- **AND** die Einrichtung läuft ohne Fehler weiter und nennt das Kommando für einen späteren Aufbau

#### Scenario: Verknüpfung besteht bereits

- **WHEN** die Einrichtung läuft und bereits eine Verknüpfung auf dieses Repository existiert
- **THEN** wird nicht erneut gefragt
- **AND** der Schritt erscheint als erledigt

#### Scenario: Anlegen schlägt fehl

- **WHEN** die Verknüpfung nicht angelegt werden kann
- **THEN** meldet die Einrichtung eine Warnung mit Pfad und Grund
- **AND** sie schließt den übrigen Ablauf ab

### Requirement: Veraltete eigene Verknüpfungen auf dem Desktop

Die Einrichtung und das Kommando für den Aufbau MUST vor der Frage nach dem Zustand die eigenen Verknüpfungen des Desktops entfernen, die nichts mehr starten, und MUST das in **einer** Zeile melden. Als eigen MUST eine Verknüpfung gelten, deren Startziel oder Arbeitsverzeichnis in diesem Repository liegt; die Zuordnung MUST über den Zielpfad laufen und MUST NOT über den Namen, weil eine Verknüpfung den Namen trägt, den der Benutzer ihr gegeben hat. Als veraltet MUST eine eigene Verknüpfung gelten, deren Startziel nicht mehr existiert oder nicht der aktuelle Startweg ist. Fremde Verknüpfungen MUST unberührt bleiben. Nach dem Entfernen MUST der Ablauf wie üblich weiterlaufen und die Verknüpfung neu aufbauen.

#### Scenario: Verknüpfung des abgelösten Startskripts unter eigenem Namen

- **WHEN** auf dem Desktop eine Verknüpfung beliebigen Namens liegt, die das abgelöste Startskript dieses Repositorys startet
- **THEN** ist sie nach der Einrichtung entfernt
- **AND** eine Zeile nennt, wie viele veraltete Verknüpfungen entfernt wurden
- **AND** danach liegt die aktuelle Verknüpfung auf dem Desktop

#### Scenario: Gültige Verknüpfung bleibt

- **WHEN** die vorhandene Verknüpfung auf den aktuellen Startweg zeigt
- **THEN** wird sie nicht entfernt

#### Scenario: Fremde Verknüpfung bleibt

- **WHEN** auf dem Desktop eine Verknüpfung einer anderen Einrichtung oder eines fremden Programms liegt
- **THEN** bleibt sie liegen, auch wenn ihr Ziel nicht mehr existiert

#### Scenario: Unlesbare Verknüpfung bleibt

- **WHEN** eine Verknüpfung auf dem Desktop nicht gelesen werden kann
- **THEN** bleibt sie liegen, weil nichts sie diesem Repository zuordnet

### Requirement: Kein Autostart, kein Symbol im Infobereich

Die Anwendung MUST NOT einen Eintrag im Autostart-Ordner des Benutzers, einen Ausführungsschlüssel in der Registry oder eine geplante Aufgabe anlegen. Sie MUST NOT ein Symbol im Infobereich betreiben. Das Kommando für die Verknüpfung MUST ausschließlich eine Verknüpfung erzeugen und MUST NOT Anmeldepersistenz einrichten.

#### Scenario: Aufbau richtet keine Anmeldepersistenz ein

- **WHEN** die Verknüpfung aufgebaut wird
- **THEN** existiert danach kein Eintrag im Autostart-Ordner
- **AND** es existiert kein Ausführungsschlüssel in der Registry und keine geplante Aufgabe

#### Scenario: Kein Symbol im Infobereich

- **WHEN** die Anwendung läuft
- **THEN** erscheint kein Symbol im Infobereich
- **AND** die Bedienung erfolgt ausschließlich über das Anwendungsfenster

### Requirement: Aufbau der Desktop-Verknüpfung

Das Kommando MUST eine Verknüpfung auf dem Desktop des Benutzers erzeugen, die die Anwendung fensterlos startet und das Repository als Arbeitsverzeichnis führt. Der Aufbau MUST wiederholbar sein und eine vorhandene Verknüpfung überschreiben, ohne fehlzuschlagen. Die Verknüpfung MUST denselben Startweg verwenden wie das Start-Kommando im Repository, damit beide nicht auseinanderlaufen. Der Desktop-Ordner MUST einem umgeleiteten Benutzerprofil folgen. Die Ausgabe MUST Pfad und Namen der erzeugten Verknüpfung nennen.

#### Scenario: Verknüpfung wird aufgebaut

- **WHEN** der Aufbau angefordert wird
- **THEN** liegt danach eine Verknüpfung auf dem Desktop des Benutzers
- **AND** ihr Arbeitsverzeichnis ist das Repository
- **AND** die Ausgabe nennt Pfad und Namen

#### Scenario: Doppelklick startet ohne Konsole

- **WHEN** die Verknüpfung doppelt angeklickt wird
- **THEN** erscheint das Anwendungsfenster
- **AND** es öffnet sich kein Konsolenfenster

#### Scenario: Wiederholter Aufbau

- **WHEN** der Aufbau angefordert wird und bereits eine Verknüpfung existiert
- **THEN** wird sie überschrieben, ohne dass der Vorgang fehlschlägt

#### Scenario: Umgeleiteter Desktop-Ordner

- **WHEN** der Desktop-Ordner des Benutzers an einen anderen Ort umgeleitet ist
- **THEN** wird die Verknüpfung an diesem Ort erzeugt und dieser Ort genannt

#### Scenario: Aufbau ohne eingerichtete Installation

- **WHEN** der Aufbau angefordert wird und die Umgebung fehlt
- **THEN** meldet der Vorgang die Einrichtung als Voraussetzung
- **AND** er endet mit einem Exit-Code ungleich 0

### Requirement: Feste Pfade in der Verknüpfung

Die Verknüpfung MUST absolute Pfade auf das aktuelle Repository und die dort eingerichtete Umgebung enthalten. Dieser Umstand MUST beim Aufbau ausdrücklich benannt werden, zusammen mit dem Hinweis, sie nach einem Verschieben oder Umbenennen des Repositorys erneut aufzubauen.

#### Scenario: Hinweis beim Aufbau

- **WHEN** die Verknüpfung aufgebaut wird
- **THEN** nennt die Ausgabe, dass sie feste Pfade enthält
- **AND** sie nennt den erneuten Aufbau als Schritt nach einem Verschieben des Repositorys

#### Scenario: Verschobenes Repository

- **WHEN** das Repository verschoben wurde und die alte Verknüpfung benutzt wird
- **THEN** meldet die Statusauskunft das nicht mehr existierende Ziel

### Requirement: Statusauskunft zur Verknüpfung

Die Statusauskunft MUST melden, ob eine Verknüpfung existiert, und dazu Pfad, Startziel, Argumente und Arbeitsverzeichnis der vorhandenen Verknüpfung ausgeben. Die Angaben MUST aus der vorhandenen Verknüpfung gelesen und MUST NOT aus dem erwarteten Aufbau abgeleitet werden. Zeigt die Verknüpfung auf ein anderes Repository, MUST das ausdrücklich benannt werden. Existiert keine Verknüpfung oder ist sie nicht lesbar, MUST das gemeldet werden und der Vorgang ohne Fehler enden.

#### Scenario: Verknüpfung vorhanden

- **WHEN** der Status abgefragt wird und eine Verknüpfung existiert
- **THEN** nennt die Ausgabe Pfad, Startziel, Argumente und Arbeitsverzeichnis

#### Scenario: Verknüpfung zeigt auf ein anderes Repository

- **WHEN** die vorhandene Verknüpfung ein anderes Arbeitsverzeichnis führt als das aktuelle Repository
- **THEN** weist die Ausgabe darauf hin, dass sie zu einer anderen Installation gehört

#### Scenario: Keine Verknüpfung vorhanden

- **WHEN** der Status abgefragt wird und keine Verknüpfung existiert
- **THEN** meldet die Ausgabe, dass keine gefunden wurde
- **AND** der Vorgang endet ohne Fehler

#### Scenario: Unlesbare Verknüpfung

- **WHEN** eine Verknüpfung existiert, aber nicht gelesen werden kann
- **THEN** meldet die Ausgabe die Verknüpfung als vorhanden und das Lesen als fehlgeschlagen

### Requirement: Entfernen der Verknüpfung

Das Entfernen MUST ausschließlich die Verknüpfung auf dem Desktop löschen und MUST NOT Konfiguration, Protokolle, Zustand, Umgebung oder Aufnahmen antasten. Existiert keine Verknüpfung, MUST der Vorgang das melden und ohne Fehler enden. Eine laufende Anwendung MUST unberührt bleiben. Schlägt das Löschen fehl, MUST der Vorgang Pfad und Grund nennen.

#### Scenario: Verknüpfung wird entfernt

- **WHEN** das Entfernen angefordert wird und eine Verknüpfung existiert
- **THEN** ist sie danach gelöscht
- **AND** Konfiguration, Protokolle, Zustand und Umgebung sind unverändert

#### Scenario: Keine Verknüpfung vorhanden

- **WHEN** das Entfernen angefordert wird und keine Verknüpfung existiert
- **THEN** meldet der Vorgang, dass keine gefunden wurde
- **AND** er endet ohne Fehler

#### Scenario: Laufende Anwendung bleibt unberührt

- **WHEN** das Entfernen angefordert wird, während die Anwendung läuft
- **THEN** läuft sie weiter
- **AND** die Ausgabe nennt das Schließen des Fensters als Weg, sie zu beenden

#### Scenario: Löschen schlägt fehl

- **WHEN** die Verknüpfung nicht gelöscht werden kann
- **THEN** nennt die Ausgabe Pfad und Grund
- **AND** der Vorgang endet mit einem Exit-Code ungleich 0
