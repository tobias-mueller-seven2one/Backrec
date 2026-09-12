## Purpose

Die Diagnose beantwortet in einem Lauf die Frage, warum Backrec nicht so arbeitet wie erwartet: sie prüft Laufzeit, Konfiguration, externe Abhängigkeiten, Audiogeräte, Verzeichnisse, Verknüpfung und Zustand und nennt zu jedem Befund die Ursache und den nächsten Schritt.

## ADDED Requirements

### Requirement: Diagnose verändert nichts

Die Diagnose MUST ausschließlich lesen. Sie MUST NOT Verzeichnisse anlegen, Konfiguration schreiben oder ergänzen, Abhängigkeiten installieren, Prozesse starten oder beenden, aufräumen oder Rückfragen stellen. Ein Schreibzugriff MUST auf das eigene Protokollverzeichnis beschränkt bleiben und MUST NUR den eigenen Protokolleintrag und den angeforderten Bericht betreffen. Ob ein Verzeichnis beschreibbar ist, MUST ohne dauerhafte Spur geprüft werden.

#### Scenario: Fehlendes Verzeichnis wird nicht angelegt

- **WHEN** die Diagnose läuft und ein konfiguriertes Verzeichnis fehlt
- **THEN** meldet sie es als Fehler
- **AND** das Verzeichnis existiert danach weiterhin nicht

#### Scenario: Keine Rückfragen

- **WHEN** die Diagnose unbeaufsichtigt läuft
- **THEN** stellt sie keine Rückfrage
- **AND** sie kommt in jedem Fall zu einem Ergebnis

#### Scenario: Prüfung der Beschreibbarkeit

- **WHEN** die Diagnose ein Verzeichnis auf Beschreibbarkeit prüft
- **THEN** hinterlässt sie darin keine Datei

### Requirement: Form des Ergebnisses

Jede Prüfung MUST genau eine der Stufen bestanden, Warnung oder Fehler ergeben und dazu eine Zeile Ursache und eine Zeile nächster Schritt nennen. Die Prüfungen MUST nach Kategorien gruppiert ausgegeben werden. Ohne Fehler MUST der Exit-Code 0 sein, sonst ungleich 0; eine Warnung MUST NOT den Exit-Code ungleich 0 machen. Auf Anforderung MUST das Ergebnis maschinenlesbar ausgegeben werden, mit derselben Menge an Prüfungen und Stufen wie in der lesbaren Ausgabe.

#### Scenario: Alles bestanden

- **WHEN** die Diagnose läuft und keine Prüfung fehlschlägt
- **THEN** ist der Exit-Code 0

#### Scenario: Eine Prüfung schlägt fehl

- **WHEN** mindestens eine Prüfung fehlschlägt
- **THEN** ist der Exit-Code ungleich 0
- **AND** die Ausgabe nennt für diese Prüfung Ursache und nächsten Schritt

#### Scenario: Nur Warnungen

- **WHEN** Prüfungen Warnungen, aber keine Fehler ergeben
- **THEN** ist der Exit-Code 0
- **AND** die Warnungen sind als solche gekennzeichnet

#### Scenario: Maschinenlesbare Ausgabe

- **WHEN** die maschinenlesbare Ausgabe angefordert wird
- **THEN** enthält sie je Prüfung Kennung, Kategorie, Stufe, Ursache und nächsten Schritt
- **AND** sie enthält dieselben Prüfungen wie die lesbare Ausgabe

#### Scenario: Ausgabe ohne Fachjargon

- **WHEN** die lesbare Ausgabe erzeugt wird
- **THEN** nennt sie Ursache und nächsten Schritt in Klartext
- **AND** sie enthält keine Ausnahmeverfolgung

### Requirement: Bericht als weitergebbare Textdatei

Wird die Diagnose aus der Bedienoberfläche angefordert, MUST ihr Ergebnis zusätzlich als Textdatei im Protokollverzeichnis abgelegt und im Standard-Editor des Benutzers geöffnet werden. Der Bericht MUST in seinem Kopf Werkzeugname, Version, Repository-Pfad, Konfigurationspfad und einen Zeitstempel führen und danach alle Befunde in derselben Form wie die lesbare Ausgabe enthalten. Der Dateiname MUST den Zeitstempel tragen, damit ein früherer Bericht nicht überschrieben wird. Das Schreiben des Berichts MUST die einzige Veränderung sein, die eine Diagnose vornimmt, und MUST NOT den Zustand oder die Anzeige der Anwendung verändern.

#### Scenario: Bericht wird erzeugt und geöffnet

- **WHEN** die Diagnose aus der Bedienoberfläche angefordert wird
- **THEN** liegt danach eine Textdatei mit dem Ergebnis im Protokollverzeichnis
- **AND** sie wird im Standard-Editor angezeigt

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

### Requirement: Prüfung der Laufzeit und der Umgebung

Die Diagnose MUST prüfen, ob der Paket- und Umgebungsmanager verfügbar ist, ob die Umgebung existiert, ob ihre Python-Version der im Repository festgelegten entspricht und ob die installierten Abhängigkeiten zur Lockdatei passen. Eine Abweichung zwischen Umgebung und Lockdatei MUST als Fehler gemeldet werden, mit dem Kommando zur Erneuerung als nächstem Schritt.

#### Scenario: Umgebung fehlt

- **WHEN** die Umgebung nicht existiert
- **THEN** meldet die Diagnose einen Fehler
- **AND** sie nennt die Einrichtung als nächsten Schritt

#### Scenario: Abweichende Python-Version

- **WHEN** die Python-Version der Umgebung von der festgelegten abweicht
- **THEN** meldet die Diagnose einen Fehler mit beiden Versionen

#### Scenario: Umgebung weicht von der Lockdatei ab

- **WHEN** die installierten Versionen nicht zur Lockdatei passen
- **THEN** meldet die Diagnose einen Fehler
- **AND** sie nennt das Kommando zur Erneuerung der Umgebung

### Requirement: Prüfung der Konfiguration

Die Diagnose MUST prüfen, ob die Konfigurationsdatei existiert und parsebar ist, ob alle Pflichtschlüssel vorhanden sind, ob unbekannte Schlüssel enthalten sind und ob die Vorlage Schlüssel führt, die in der lokalen Datei fehlen. Sie MUST für jeden wirksamen Wert die Schicht nennen, aus der er stammt. Sie MUST NOT fehlende Schlüssel selbst ergänzen. Der genannte nächste Schritt MUST NOT Handarbeit an der Datei verlangen, sondern MUST auf das Einrichten verweisen, das neue Vorlagen-Schlüssel selbst ergänzt.

#### Scenario: Fehlender Pflichtschlüssel

- **WHEN** ein Pflichtschlüssel fehlt
- **THEN** meldet die Diagnose einen Fehler mit dem Namen des Schlüssels

#### Scenario: Unbekannter Schlüssel

- **WHEN** die Konfiguration einen unbekannten Schlüssel führt
- **THEN** meldet die Diagnose eine Warnung mit dem Namen des Schlüssels

#### Scenario: Abweichung zur Vorlage

- **WHEN** die Vorlage einen Schlüssel führt, der in der lokalen Datei fehlt
- **THEN** meldet die Diagnose eine Warnung
- **AND** der Schlüssel wird nicht selbsttätig ergänzt
- **AND** der nächste Schritt nennt das Einrichten und nicht das Ergänzen von Hand

#### Scenario: Herkunft der Werte

- **WHEN** ein Wert aus einer Umgebungsvariable stammt
- **THEN** nennt die Diagnose diese Schicht als Herkunft

### Requirement: Prüfung von ffmpeg

Die Diagnose MUST prüfen, ob ffmpeg im Suchpfad gefunden wird **und** ob es sich tatsächlich ausführen lässt. Ein gefundenes, aber nicht ausführbares ffmpeg MUST als Fehler gemeldet werden, unterschieden vom Fall „nicht gefunden". Bei Erfolg MUST die gemeldete Version genannt werden.

#### Scenario: ffmpeg fehlt

- **WHEN** ffmpeg nicht im Suchpfad liegt
- **THEN** meldet die Diagnose einen Fehler
- **AND** sie nennt die Beschaffung über die Einrichtung als nächsten Schritt

#### Scenario: ffmpeg vorhanden und ausführbar

- **WHEN** ffmpeg gefunden wird und sich ausführen lässt
- **THEN** meldet die Diagnose bestanden und nennt die Version

#### Scenario: ffmpeg gefunden, aber nicht ausführbar

- **WHEN** ffmpeg im Suchpfad liegt, der Aufruf aber scheitert
- **THEN** meldet die Diagnose einen Fehler, der den Aufruf und nicht das Fehlen als Ursache nennt

### Requirement: Prüfung der Audiogeräte

Die Diagnose MUST prüfen, ob ein Standard-Aufnahmegerät und ein Standard-Wiedergabegerät vorhanden sind, und deren Namen nennen. Fehlt ein Gerät, MUST das als Fehler gemeldet werden, weil ohne beide Geräte keine vollständige Aufnahme entsteht. Ist die Geräteerkennung selbst nicht verfügbar, MUST das als eigener Befund gemeldet werden und MUST NOT als „kein Gerät vorhanden" erscheinen.

#### Scenario: Beide Geräte vorhanden

- **WHEN** Standard-Aufnahme- und Standard-Wiedergabegerät vorhanden sind
- **THEN** meldet die Diagnose bestanden und nennt beide Gerätenamen

#### Scenario: Kein Wiedergabegerät

- **WHEN** kein Standard-Wiedergabegerät vorhanden ist
- **THEN** meldet die Diagnose einen Fehler
- **AND** sie nennt, dass die Systemaufnahme darauf aufsetzt

#### Scenario: Geräteerkennung nicht verfügbar

- **WHEN** die Geräteerkennung selbst nicht verfügbar ist
- **THEN** meldet die Diagnose diesen Umstand als eigene Ursache
- **AND** sie behauptet nicht, dass Geräte fehlen

### Requirement: Prüfung der Verzeichnisse und des Speicherplatzes

Die Diagnose MUST für Aufnahme- und Zielverzeichnis prüfen, ob sie existieren und beschreibbar sind. Sie MUST für beide Ablageorte den freien Speicherplatz nennen und bei Unterschreiten einer festgelegten Reserve eine Warnung melden. Sie MUST melden, wenn das Aufnahmeverzeichnis unterhalb eines Cloud-synchronisierten Ordners liegt.

#### Scenario: Zielverzeichnis fehlt

- **WHEN** das Zielverzeichnis nicht existiert
- **THEN** meldet die Diagnose einen Fehler
- **AND** sie nennt, dass das Folgetool aus diesem Verzeichnis liest

#### Scenario: Wenig freier Speicherplatz

- **WHEN** der freie Speicherplatz eines Ablageorts unter der Reserve liegt
- **THEN** meldet die Diagnose eine Warnung mit dem verbleibenden Platz
- **AND** sie nennt den Platzbedarf einer Aufnahme je Minute

#### Scenario: Aufnahmeverzeichnis im Cloud-Ordner

- **WHEN** das Aufnahmeverzeichnis unterhalb eines Cloud-synchronisierten Ordners liegt
- **THEN** meldet die Diagnose eine Warnung mit diesem Umstand als Ursache

### Requirement: Prüfung von Verknüpfung und Zustand

Die Diagnose MUST melden, ob eine Desktop-Verknüpfung vorhanden ist, ob sie auf dieses Repository zeigt und ob ihr Ziel existiert. Sie MUST melden, ob das Protokollverzeichnis beschreibbar ist und ob verwaiste Zustandsdatensätze vorliegen. Ein verwaister Zustandsdatensatz MUST als Warnung gemeldet werden, nicht als Fehler. Sie MUST die eingerichtete Version nennen und als Warnung melden, wenn ein Ordner einer abgelösten Version aus einer Aktualisierung liegen geblieben ist oder wenn sich Diagnose-Berichte über eine festgelegte Anzahl hinaus angesammelt haben; in beiden Fällen MUST sie den Weg zum Aufräumen nennen und MUST NOT selbst aufräumen.

#### Scenario: Verknüpfung zeigt auf ein anderes Repository

- **WHEN** eine Verknüpfung existiert und auf ein anderes Repository zeigt
- **THEN** meldet die Diagnose diesen Umstand ausdrücklich

#### Scenario: Verwaister Zustandsdatensatz

- **WHEN** ein Zustandsdatensatz existiert, zu dem kein lebender Prozess gehört
- **THEN** meldet die Diagnose eine Warnung
- **AND** sie nennt, dass der nächste Start den Datensatz übernimmt

#### Scenario: Protokollverzeichnis nicht beschreibbar

- **WHEN** das Protokollverzeichnis nicht beschreibbar ist
- **THEN** meldet die Diagnose einen Fehler mit dem Pfad

#### Scenario: Ordner einer abgelösten Version

- **WHEN** neben dem Repository der Ordner einer durch eine Aktualisierung abgelösten Version liegt
- **THEN** meldet die Diagnose eine Warnung mit dem Pfad
- **AND** sie entfernt ihn nicht selbst

#### Scenario: Angesammelte Diagnose-Berichte

- **WHEN** im Protokollverzeichnis mehr Diagnose-Berichte liegen als die festgelegte Anzahl
- **THEN** meldet die Diagnose eine Warnung mit der Anzahl
- **AND** sie nennt das Löschen als nächsten Schritt

### Requirement: Prüfung auf veraltete Verknüpfungen auf dem Desktop

Die Diagnose MUST alle Verknüpfungen des Desktops lesen und die als eigene erkennen, deren Startziel oder Arbeitsverzeichnis in diesem Repository liegt — über den Zielpfad, MUST NOT über den Namen. Eine eigene Verknüpfung, deren Startziel nicht mehr existiert oder nicht der aktuelle Startweg ist, MUST sie als `fail` mit der Ursache „zeigt auf eine Datei, die es nicht mehr gibt" melden. Fremde Verknüpfungen MUST unberührt und ungemeldet bleiben. Diese Prüfung MUST NOT in den zyklischen Abläufen des Fensters stattfinden, weil das Zurücklesen je Verknüpfung einen Systemaufruf kostet.

#### Scenario: Verwaiste eigene Verknüpfung unter anderem Namen

- **WHEN** auf dem Desktop eine Verknüpfung beliebigen Namens liegt, deren Ziel in diesem Repository liegt und nicht mehr existiert
- **THEN** meldet die Diagnose sie als Fehler mit der Ursache, dass das Ziel nicht mehr existiert
- **AND** sie nennt das Einrichten als nächsten Schritt

#### Scenario: Verknüpfung auf einen abgelösten Startweg

- **WHEN** eine eigene Verknüpfung auf eine vorhandene, aber abgelöste Startdatei zeigt
- **THEN** meldet die Diagnose sie als Fehler

#### Scenario: Verwaiste Verknüpfung neben einer gültigen

- **WHEN** neben der gültigen Verknüpfung eine verwaiste eigene Verknüpfung liegt
- **THEN** meldet die Diagnose die gültige als bestanden und die verwaiste als Fehler

#### Scenario: Fremde Verknüpfung

- **WHEN** auf dem Desktop eine Verknüpfung liegt, deren Ziel außerhalb dieses Repositorys liegt
- **THEN** meldet die Diagnose sie nicht
