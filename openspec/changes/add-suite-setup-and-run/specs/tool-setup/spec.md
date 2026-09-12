## Purpose

Die Einrichtung bringt Backrec auf einem frischen Windows-Rechner von „ZIP entpackt" zu „startbereit", ohne Administratorrechte, ohne Git und ohne Vorwissen: Laufzeit beschaffen, Umgebung reproduzierbar bauen, Konfiguration anlegen, externe Abhängigkeiten prüfen und beschaffen, Ergebnis prüfen, Verknüpfung anbieten. Sie umfasst außerdem das Aktualisieren über ein neues Release-ZIP, das Bauen eines solchen ZIP und das Entfernen derselben Installation.

## ADDED Requirements

### Requirement: Zwei Doppelklick-Dateien und eine Versionsangabe im Wurzelverzeichnis

Das Repository MUST im Wurzelverzeichnis genau zwei Dateien anbieten, die per Doppelklick einen Vorgang starten: `Setup.cmd` für die Einrichtung und `Start.cmd` für den Start. Es MUST NOT weitere Dateien enthalten, die per Doppelklick einen Vorgang starten, insbesondere nicht für Beenden, Aktualisieren, Diagnose oder Deinstallation; diese Vorgänge MUST als Kommandos und über die Bedienoberfläche erreichbar bleiben. Textdateien, die per Doppelklick nur im Editor erscheinen und keinen Vorgang auslösen — die Versionsangabe und die Einstiegsanleitung —, MUST von dieser Beschränkung ausgenommen sein. Jede der beiden Dateien MUST in das Verzeichnis wechseln, in dem sie liegt, und MUST NOT eigene Ablauflogik enthalten, sondern das zugehörige Kommando aufrufen. Wird sie per Doppelklick gestartet oder endet das Kommando mit einem Exit-Code ungleich 0, MUST das Fenster offen bleiben, bis der Benutzer es schließt. Das Wurzelverzeichnis MUST zusätzlich eine Textdatei mit der Version enthalten, die ohne eine eingerichtete Laufzeit lesbar ist und die einzige Quelle der Versionsangabe ist.

#### Scenario: Doppelklick auf Setup

- **WHEN** `Setup.cmd` per Doppelklick gestartet wird
- **THEN** läuft die Einrichtung im geöffneten Fenster ab
- **AND** das Fenster bleibt nach dem Ende offen, bis der Benutzer es schließt

#### Scenario: Aufruf aus einem anderen Arbeitsverzeichnis

- **WHEN** eine der beiden Dateien aus einem beliebigen anderen Arbeitsverzeichnis aufgerufen wird
- **THEN** arbeitet sie auf dem Repository, in dem sie liegt

#### Scenario: Fehler bleibt lesbar

- **WHEN** das aufgerufene Kommando mit einem Exit-Code ungleich 0 endet
- **THEN** bleibt das Fenster offen
- **AND** die Ursache steht als lesbare Meldung im Fenster

#### Scenario: Keine weiteren Doppelklick-Dateien

- **WHEN** das Wurzelverzeichnis betrachtet wird
- **THEN** enthält es außer `Setup.cmd` und `Start.cmd` keine weitere Datei, die einen Vorgang startet
- **AND** Beenden, Aktualisieren, Diagnose und Deinstallation sind dennoch über Kommandos erreichbar
- **AND** die beiden Textdateien mit Version und Einstiegsanleitung lösen bei einem Doppelklick keinen Vorgang aus

#### Scenario: Version ohne Laufzeit lesbar

- **WHEN** die Version aus einem frisch entpackten Ordner ohne eingerichtete Umgebung ermittelt wird
- **THEN** liefert die Textdatei im Wurzelverzeichnis sie
- **AND** keine andere Datei im Repository führt eine abweichende Versionsangabe

### Requirement: Einstiegsanleitung im Wurzelverzeichnis

Das Wurzelverzeichnis MUST eine Einstiegsanleitung mit dem Namen `LIES-MICH-ZUERST.txt` enthalten. Sie MUST reiner Text sein, MUST in UTF-8 mit Bytereihenfolge-Kennung und mit Windows-Zeilenenden gespeichert sein, damit ein Doppelklick sie im Standard-Editor mit korrekten Umlauten und Zeilenumbrüchen zeigt. Sie MUST höchstens 40 Zeilen umfassen, jede Zeile MUST höchstens 80 Zeichen lang sein. Sie MUST NOT Auszeichnungssyntax, Tabellen, ein Kommando, einen Dateipfad außer dem Entpackziel oder einen Fachbegriff der Sperrliste enthalten.

Sie MUST auf Deutsch verfasst sein, auch wenn die Entwicklerdokumentation des Repositorys englisch bleibt.

Sie MUST genau diese acht Abschnitte in dieser Reihenfolge führen: Kopf mit Werkzeugname und je einem Satz zu Zweck und Anlass; „Was du brauchst"; „So richtest du es ein" mit nummerierten Schritten; „Im Alltag"; „Wenn etwas rot ist"; „Aktualisieren"; „Entfernen"; Ansprechpartner mit dem Hinweis, dass alles Technische in der Entwicklerdokumentation steht und nicht gebraucht wird. Der Abschnitt „Was du brauchst" MUST NOT ein Fremdprogramm verlangen, das die Einrichtung selbst beschafft. Die nummerierten Schritte MUST nennen, dass die Verknüpfung auf dem Desktop angelegt wird, und MUST das Symbol auf dem Desktop als Ergebnis nennen; sie MUST NOT einen Autostart-Ordner, ein Ziehen einer Verknüpfung oder ein Symbol im Infobereich nennen. „Im Alltag" MUST die Bedienung der Aufnahme und die Schaltfläche nennen, die das Menü im Anwendungsfenster öffnet. Er MUST außerdem beide Wege zum Ändern einer Einstellung nennen: die Einrichtung erneut doppelklicken oder im Menü des Fensters die Einstellungen öffnen. „Wenn etwas rot ist" MUST den Weg über dieses Menü zur Diagnose und das Weiterschicken des erzeugten Berichts nennen. „Entfernen" MUST die drei Schritte Fenster schließen, Desktop-Verknüpfung löschen, Ordner löschen nennen.

Sie MUST die einzige Stelle im Repository sein, an der dieser Text steht. Die Entwicklerdokumentation MUST mit einem Verweis auf diese Datei beginnen und MUST NOT einen eigenen, an Kollegen gerichteten Einrichtungsteil führen. Der Menüpunkt für die Auskunft im Anwendungsfenster MUST den Pfad dieser Datei nennen, und die Beschreibung des Release MUST sie führen.

Das Bauen des Release-Pakets MUST die Datei maschinell prüfen: Name, Zeichenkodierung, Zeilenenden, Zeilenzahl, Zeilenlänge, Sperrliste sowie Vorhandensein und Reihenfolge der acht Abschnitte. Fehlt die Datei oder verletzt sie eine dieser Regeln, MUST der Lauf ohne Paket mit einem Exit-Code ungleich 0 abbrechen und MUST die verletzte Regel samt Fundstelle nennen; eine Warnung MUST NOT genügen.

#### Scenario: Kollege öffnet den entpackten Ordner

- **WHEN** ein Kollege den aus dem Release-ZIP entpackten Ordner im Dateimanager öffnet
- **THEN** enthält der Ordner `LIES-MICH-ZUERST.txt`
- **AND** ein Doppelklick zeigt sie im Standard-Editor mit korrekten Umlauten und Zeilenumbrüchen
- **AND** sie führt ihn ohne weitere Hilfe von der Einrichtung bis zum laufenden Fenster

#### Scenario: Datei fehlt beim Bauen des Pakets

- **WHEN** das Bauen des Release-Pakets angefordert wird und die Einstiegsanleitung im Wurzelverzeichnis fehlt
- **THEN** bricht der Lauf ab, ohne ein Paket zu erzeugen
- **AND** die Meldung nennt die fehlende Datei

#### Scenario: Datei verletzt eine Formregel

- **WHEN** die Einstiegsanleitung mehr Zeilen als erlaubt hat, eine zu lange Zeile führt, in einer falschen Zeichenkodierung vorliegt oder einen Begriff der Sperrliste enthält
- **THEN** bricht das Bauen des Release-Pakets ab, ohne ein Paket zu erzeugen
- **AND** die Meldung nennt die verletzte Regel und die Zeile

#### Scenario: Abschnitt fehlt oder steht an falscher Stelle

- **WHEN** einer der acht Abschnitte fehlt oder die Reihenfolge abweicht
- **THEN** bricht das Bauen des Release-Pakets ab, ohne ein Paket zu erzeugen
- **AND** die Meldung nennt den fehlenden oder verschobenen Abschnitt

#### Scenario: Entwicklerdokumentation verweist auf die Anleitung

- **WHEN** die Entwicklerdokumentation gelesen wird
- **THEN** beginnt sie mit einem Verweis auf `LIES-MICH-ZUERST.txt`
- **AND** sie enthält keinen eigenen, an Kollegen gerichteten Einrichtungsteil

### Requirement: Einrichtung aus einem entpackten Release-ZIP

Die Einrichtung MUST aus einem Ordner heraus funktionieren, der durch Entpacken eines Release-ZIP entstanden ist, ohne dass Git, ein Repository-Klon oder eine Netzwerkfreigabe vorhanden ist. Sie MUST beim ersten Lauf die Internet-Zonenkennung der entpackten Dateien entfernen, damit keine weiteren Sicherheitsdialoge erscheinen; scheitert das Entfernen, MUST es als Warnung gemeldet werden und die Einrichtung MUST fortfahren. Sie MUST in einem Ordnerpfad funktionieren, der Leerzeichen, Umlaute oder einen Cloud-synchronisierten Ordner enthält, und MUST ihre Ausgabe in einer Zeichenkodierung erzeugen, in der Umlaute korrekt erscheinen.

#### Scenario: Einrichtung ohne Git

- **WHEN** die Einrichtung in einem entpackten Ordner ohne Versionsverwaltung läuft
- **THEN** läuft sie vollständig durch
- **AND** kein Schritt verlangt Git oder einen Zugriff auf ein Repository

#### Scenario: Zonenkennung wird entfernt

- **WHEN** die Einrichtung zum ersten Mal in einem aus dem Internet bezogenen Ordner läuft
- **THEN** tragen die Dateien des Ordners danach keine Internet-Zonenkennung mehr
- **AND** ein erneuter Start zeigt keinen weiteren Sicherheitsdialog

#### Scenario: Zonenkennung lässt sich nicht entfernen

- **WHEN** das Entfernen der Zonenkennung fehlschlägt
- **THEN** meldet die Einrichtung eine Warnung mit dem Weg über die Dateieigenschaften
- **AND** sie setzt die Einrichtung fort

#### Scenario: Pfad mit Leerzeichen und Umlauten

- **WHEN** der Ordner in einem Pfad mit Leerzeichen und Umlauten liegt
- **THEN** läuft die Einrichtung vollständig durch
- **AND** die Pfade erscheinen in den Meldungen unverfälscht

### Requirement: Assistenten-Ausgabe der Einrichtung

Die Einrichtung MUST ihre Ausgabe für Benutzer ohne Vorwissen gestalten. Jeder Schritt MUST mit laufender Nummer und Gesamtzahl angekündigt und sein Ergebnis mit einem Symbol und einem Satz Klartext gemeldet werden. Jede Rückfrage MUST eine Vorgabe nennen, die mit der Eingabetaste übernommen wird, und es MUST NOT mehr als eine Frage gleichzeitig gestellt werden. Die Ausgabe MUST NOT Fachbegriffe der Umsetzung, eine Ausnahmeverfolgung oder eine unbehandelte Fehlermeldung des Systems enthalten; technische Einzelheiten MUST das Protokoll aufnehmen, dessen Pfad genau einmal am Ende genannt wird. Jeder Fehler MUST in zwei Aussagen erscheinen: was geschehen ist und was zu tun ist, mit einem konkreten nächsten Handgriff. Am Ende MUST eine Zusammenfassung aller Schritte mit ihren Symbolen stehen. Farbige Ausgabe MUST NUR erfolgen, wenn die Konsole sie darstellt; andernfalls MUST die Aussage allein durch Textsymbole getragen werden.

#### Scenario: Schritte sind gezählt

- **WHEN** die Einrichtung läuft
- **THEN** nennt jeder Schritt seine Nummer und die Gesamtzahl
- **AND** jedes Ergebnis erscheint mit Symbol und einem Satz Klartext

#### Scenario: Frage mit Vorgabe

- **WHEN** die Einrichtung eine Frage stellt
- **THEN** nennt sie eine Vorgabe
- **AND** die Eingabetaste allein übernimmt die Vorgabe

#### Scenario: Fehler ohne Fachjargon

- **WHEN** ein Schritt fehlschlägt
- **THEN** nennt die Ausgabe in zwei Aussagen, was geschehen ist und was zu tun ist
- **AND** sie enthält keine Ausnahmeverfolgung und keinen Fachbegriff der Umsetzung
- **AND** die technischen Einzelheiten stehen im Protokoll

#### Scenario: Abschluss

- **WHEN** die Einrichtung endet
- **THEN** erscheint eine Zusammenfassung aller Schritte mit ihren Symbolen
- **AND** der Pfad des Protokolls wird genau einmal genannt
- **AND** das Fenster bleibt offen, bis der Benutzer es schließt

#### Scenario: Konsole ohne Farbunterstützung

- **WHEN** die Konsole keine farbige Ausgabe darstellt
- **THEN** bleibt jedes Ergebnis an seinem Textsymbol erkennbar

### Requirement: Ablösung des bisherigen Startskripts

`Start_Recorder.bat` MUST NOT weiterhin eine Umgebung bauen, Abhängigkeiten installieren oder die Anwendung starten. Die Datei MUST als Hinweis erhalten bleiben, MUST auf `Setup.cmd` und `Start.cmd` verweisen und MUST mit einem Exit-Code ungleich 0 enden, damit ein Doppelklick nicht wie ein erfolgreicher Start aussieht.

#### Scenario: Doppelklick auf das alte Skript

- **WHEN** `Start_Recorder.bat` per Doppelklick gestartet wird
- **THEN** erscheint ein Hinweis, der `Setup.cmd` für die Einrichtung und `Start.cmd` für den Start nennt
- **AND** es wird keine Umgebung gebaut, nichts installiert und die Anwendung nicht gestartet
- **AND** der Exit-Code ist ungleich 0

### Requirement: Bootstrap der Laufzeit ohne Administratorrechte

Die Einrichtung MUST prüfen, ob der Paket- und Umgebungsmanager `uv` verfügbar ist, und ihn andernfalls in das Benutzerprofil beschaffen, ohne Administratorrechte zu verlangen. Scheitert die Beschaffung über den Paketmanager des Systems, MUST ein zweiter Weg mit einer festgelegten Version versucht werden. Scheitern beide, MUST die Einrichtung mit einer Meldung abbrechen, die den fehlgeschlagenen Weg und die manuelle Alternative nennt. Der Python-Interpreter MUST der im Repository festgelegten Version entsprechen und MUST von `uv` verwaltet werden dürfen; ein Interpreter, der nur ein Platzhalter des Microsoft Store ist, MUST als solcher erkannt und erklärt werden.

#### Scenario: uv fehlt

- **WHEN** die Einrichtung startet und `uv` nicht verfügbar ist
- **THEN** wird `uv` in das Benutzerprofil installiert
- **AND** die Einrichtung fährt anschließend ohne Neustart der Sitzung fort

#### Scenario: Beide Beschaffungswege scheitern

- **WHEN** weder der Paketmanager noch der zweite Weg `uv` bereitstellen können
- **THEN** endet die Einrichtung mit einem Exit-Code ungleich 0
- **AND** die Meldung nennt beide fehlgeschlagenen Wege und den manuellen Installationsweg

#### Scenario: Store-Platzhalter als Python

- **WHEN** der gefundene `python`-Aufruf nur der Platzhalter des Microsoft Store ist
- **THEN** meldet die Einrichtung genau diesen Umstand
- **AND** sie nennt den Weg zu einem echten Interpreter

### Requirement: Reproduzierbare Umgebung

Die Abhängigkeiten MUST mit exakten Versionen in einer Lockdatei festgehalten sein. Die Einrichtung MUST die Umgebung ausschließlich aus dieser Lockdatei erzeugen und MUST abbrechen, wenn die Lockdatei nicht zur Projektdefinition passt. Ein Start MUST NOT Abhängigkeiten installieren oder aktualisieren.

#### Scenario: Umgebung wird aus der Lockdatei erzeugt

- **WHEN** die Einrichtung die Umgebung baut
- **THEN** entstehen genau die in der Lockdatei festgehaltenen Versionen

#### Scenario: Lockdatei passt nicht zur Projektdefinition

- **WHEN** Projektdefinition und Lockdatei auseinanderlaufen
- **THEN** bricht die Einrichtung mit einem Exit-Code ungleich 0 ab
- **AND** die Meldung nennt das Kommando, mit dem die Lockdatei erneuert wird

#### Scenario: Start installiert nichts

- **WHEN** die Anwendung gestartet wird
- **THEN** wird keine Abhängigkeit installiert oder verändert

### Requirement: Beschaffung von ffmpeg

Die Einrichtung MUST prüfen, ob ffmpeg aufrufbar ist. Fehlt es, MUST es ohne Administratorrechte in das Benutzerprofil beschafft werden. Scheitert das, MUST die Einrichtung eine Anleitung zur manuellen Installation ausgeben und mit einem Exit-Code ungleich 0 enden, weil ohne ffmpeg keine Aufnahme gemischt werden kann. Ein bereits vorhandenes ffmpeg MUST NOT erneut installiert werden.

#### Scenario: ffmpeg fehlt und wird beschafft

- **WHEN** die Einrichtung läuft und ffmpeg nicht aufrufbar ist
- **THEN** wird ffmpeg in das Benutzerprofil installiert
- **AND** die Einrichtung prüft danach erneut, ob es aufrufbar ist

#### Scenario: Beschaffung scheitert

- **WHEN** die Beschaffung von ffmpeg fehlschlägt
- **THEN** nennt die Ausgabe die manuelle Installation und den Umstand, dass ohne ffmpeg keine Mischung entsteht
- **AND** die Einrichtung endet mit einem Exit-Code ungleich 0

#### Scenario: ffmpeg ist vorhanden

- **WHEN** ffmpeg bereits aufrufbar ist
- **THEN** wird nichts installiert
- **AND** die gefundene Version wird gemeldet

### Requirement: Reihenfolge, Meldungen und Abschluss der Einrichtung

Die Einrichtung MUST in dieser Reihenfolge ablaufen: Laufzeit, Umgebung, Konfiguration, externe Abhängigkeiten, Prüfung durch die Diagnose, Frage nach der Desktop-Verknüpfung, Frage nach dem Start. Jeder Schritt MUST eine lesbare Meldung über Beginn und Ergebnis erzeugen. Ein fehlgeschlagener Schritt MUST die Einrichtung beenden und MUST NOT stillschweigend übersprungen werden. Am Ende MUST die Einrichtung nennen, wo die Anwendung künftig gestartet wird und wo die Funktionen für Aktualisieren, Diagnose und Info im Anwendungsfenster liegen. Die Abschlussausgabe MUST in jedem Lauf den Ort der Konfigurationsdatei nennen und beide Wege zum Ändern einer Einstellung: die Einrichtung erneut ausführen oder die Datei im Editor öffnen. Melden die Prüfungen mindestens einen harten Fehler, MUST die Einrichtung mit einem Exit-Code ungleich 0 enden und MUST NOT als „fertig" gemeldet werden.

#### Scenario: Erfolgreiche Einrichtung

- **WHEN** die Einrichtung ohne harten Fehler durchläuft
- **THEN** ist der Exit-Code 0
- **AND** die Ausgabe nennt den künftigen Startweg und das Menü im Anwendungsfenster

#### Scenario: Der Weg zu den Einstellungen

- **WHEN** ein Lauf der Einrichtung endet
- **THEN** nennt die Abschlussausgabe den Ort der Konfigurationsdatei
- **AND** sie nennt beide Wege zum Ändern: erneut einrichten oder die Datei im Editor öffnen

#### Scenario: Diagnose meldet einen harten Fehler

- **WHEN** die abschließende Diagnose mindestens einen harten Fehler meldet
- **THEN** endet die Einrichtung mit einem Exit-Code ungleich 0
- **AND** die Ausgabe nennt die betroffene Prüfung und den nächsten Schritt

#### Scenario: Frage nach dem Start

- **WHEN** die Einrichtung ohne harten Fehler durchgelaufen ist
- **THEN** fragt sie, ob die Anwendung jetzt gestartet werden soll, mit Zustimmung als Vorgabe
- **AND** bei Zustimmung startet sie die Anwendung
- **AND** bei Ablehnung endet sie, ohne zu starten

#### Scenario: Der Start öffnet das Fenster

- **WHEN** die Einrichtung im letzten Schritt startet
- **THEN** startet sie denselben Weg, den die Desktop-Verknüpfung startet
- **AND** es erscheint das Anwendungsfenster und nicht nur ein Prozess ohne Fenster

#### Scenario: Unbeaufsichtigte Einrichtung

- **WHEN** die Einrichtung unbeaufsichtigt angefordert wird
- **THEN** stellt sie keine Rückfragen und verwendet die Vorgabewerte
- **AND** sie startet die Anwendung nicht von sich aus
- **AND** sie meldet am Ende dasselbe Ergebnis wie der geführte Weg

### Requirement: Idempotenz der Einrichtung

Ein zweiter Lauf der Einrichtung auf einer bereits eingerichteten Installation MUST NOT eine vorhandene Konfiguration ungefragt überschreiben, MUST NOT eine bereits vorhandene externe Abhängigkeit erneut installieren und MUST NOT die Umgebung ohne Anlass neu bauen. Die Konfiguration ändert sich nur dort, wo der Benutzer im Einrichten ausdrücklich einen neuen Wert angibt, und um Schlüssel, die die Vorlage neu führt. Er MUST melden, welche Schritte übersprungen wurden.

#### Scenario: Zweiter Lauf

- **WHEN** die Einrichtung auf einer eingerichteten Installation erneut läuft und der Benutzer keine Änderung verlangt
- **THEN** bleibt die bestehende Konfiguration unverändert
- **AND** die Ausgabe nennt die übersprungenen Schritte
- **AND** der Exit-Code ist 0, sofern die Diagnose keinen harten Fehler meldet

### Requirement: Aktualisierung über ein neues Release-ZIP

Eine Aktualisierung MUST ohne Versionsverwaltung möglich sein und MUST zwei gleichwertige Wege anbieten.

Wird ein neueres Release-ZIP über den vorhandenen Ordner entpackt und die Einrichtung erneut gestartet, MUST die Einrichtung den Wechsel der Version erkennen, eine laufende Instanz zuvor beenden, die Umgebung aus der Lockdatei erneuern, Altdateien entfernen, die Diagnose ausführen und den Start anbieten. Konfiguration, Protokolle und Zustand MUST unberührt bleiben, weil sie außerhalb des Ordners liegen.

Wird die Aktualisierung aus der Bedienoberfläche mit einem ausgewählten ZIP angefordert, MUST vor jeder Veränderung geprüft werden, dass das ZIP zu diesem Werkzeug gehört und eine neuere Version trägt; die bisherige und die neue Version MUST genannt und einmal bestätigt werden. Das ZIP MUST zuerst in einen Nachbarordner entpackt und der vorhandene Ordner MUST erst nach erfolgreicher Entpackung ersetzt werden, damit ein Abbruch nie einen unvollständigen Ordner hinterlässt. Die eingerichtete Umgebung MUST übernommen und MUST NOT neu aufgebaut werden. Scheitert ein Schritt, MUST der bisherige Stand lauffähig bleiben und der Rückweg MUST genannt werden.

Eine Aktualisierung über die Versionsverwaltung MUST als Entwicklerweg erhalten bleiben, MUST nur bei vorhandener Versionsverwaltung angeboten werden und MUST NOT der für Kollegen dokumentierte Weg sein.

#### Scenario: Neues ZIP über den Ordner entpackt

- **WHEN** ein neueres Release-ZIP über den vorhandenen Ordner entpackt und die Einrichtung erneut gestartet wird
- **THEN** erkennt sie den Wechsel der Version und nennt beide Versionen
- **AND** eine laufende Instanz wird zuvor beendet
- **AND** Konfiguration, Protokolle und Zustand bleiben unverändert

#### Scenario: Aktualisierung aus der Bedienoberfläche

- **WHEN** die Aktualisierung mit einem ausgewählten ZIP angefordert wird
- **THEN** nennt die Anwendung die bisherige und die neue Version und fragt einmal nach
- **AND** nach Bestätigung beendet sie sich, ersetzt den Ordner und startet neu

#### Scenario: ZIP gehört nicht zu diesem Werkzeug

- **WHEN** das ausgewählte ZIP zu einem anderen Werkzeug gehört oder keine gültige Beschreibung enthält
- **THEN** wird nichts verändert
- **AND** die Meldung nennt die Ursache

#### Scenario: ZIP ist nicht neuer

- **WHEN** das ausgewählte ZIP dieselbe oder eine ältere Version trägt
- **THEN** wird nichts verändert, sofern der Benutzer dem nicht ausdrücklich zustimmt
- **AND** die Meldung nennt beide Versionen

#### Scenario: Aktualisierung scheitert

- **WHEN** das Entpacken oder das Ersetzen des Ordners fehlschlägt
- **THEN** bleibt der bisherige Stand vollständig und lauffähig
- **AND** die Meldung nennt den Rückweg

#### Scenario: Umgebung wird übernommen

- **WHEN** eine Aktualisierung den Ordner ersetzt hat
- **THEN** wird die vorhandene Umgebung übernommen und nur gegen die Lockdatei abgeglichen
- **AND** sie wird nicht vollständig neu aufgebaut

#### Scenario: Entwicklerweg über die Versionsverwaltung

- **WHEN** die Aktualisierung über die Versionsverwaltung angefordert wird und keine Versionsverwaltung vorhanden ist
- **THEN** bricht sie mit einer Erklärung ab
- **AND** sie nennt den Weg über das Release-ZIP

### Requirement: Entfernen von Altdateien anhand des Release-Verzeichnisses

Ein Release MUST eine Beschreibung mitführen, die Werkzeugname, Version, Datum und die enthaltenen Dateien mit ihren Prüfsummen nennt. Nach einer erfolgreichen Einrichtung MUST eine Kopie dieser Beschreibung außerhalb des Ordners abgelegt werden. Eine Aktualisierung MUST anhand der beiden Beschreibungen genau die Dateien entfernen, die zum vorherigen Release gehörten und im neuen nicht mehr enthalten sind. Sie MUST NOT die eingerichtete Umgebung, Protokolle, Verknüpfungen, Konfigurationsdateien oder Dateien entfernen, die in keiner der beiden Beschreibungen stehen. Fehlt die Kopie der vorherigen Beschreibung, MUST das Entfernen entfallen und als übersprungener Schritt gemeldet werden.

#### Scenario: Altdatei wird entfernt

- **WHEN** eine Aktualisierung läuft und eine Datei des vorherigen Release im neuen nicht mehr enthalten ist
- **THEN** wird sie entfernt
- **AND** die Ausgabe nennt die Anzahl der entfernten Dateien

#### Scenario: Fremde Datei bleibt

- **WHEN** im Ordner eine Datei liegt, die in keiner der beiden Beschreibungen steht
- **THEN** bleibt sie unangetastet

#### Scenario: Umgebung bleibt

- **WHEN** eine Aktualisierung Altdateien entfernt
- **THEN** bleiben die eingerichtete Umgebung und die Protokolle unangetastet

#### Scenario: Keine vorherige Beschreibung

- **WHEN** die Kopie der vorherigen Beschreibung fehlt
- **THEN** entfällt das Entfernen von Altdateien
- **AND** die Ausgabe nennt den Schritt als übersprungen

### Requirement: Bauen eines Release-Pakets

Es MUST ein Kommando geben, das ein Release-Paket baut. Es MUST ein ZIP erzeugen, dessen oberste Ebene ein einzelner Ordner mit dem Werkzeugnamen ist, MUST die Versionsdatei und die Beschreibung des Release darin ablegen und MUST den Dateinamen aus Werkzeugname und Version bilden. Aufgenommen MUST ausschließlich werden, was in der Versionsverwaltung geführt ist, zuzüglich der beiden erzeugten Dateien; die eingerichtete Umgebung, Zwischenstände des Interpreters, Protokolle, Konfigurationsdateien, Verknüpfungen und Dateien mit Zugangsdaten MUST NOT enthalten sein. Die Einstiegsanleitung MUST im Paket enthalten sein und in der Beschreibung des Release geführt werden. Vor dem Bauen MUST geprüft werden, dass die Lockdatei zur Projektdefinition passt, dass keine versionierte Datei einen Benutzer-, Firmen- oder Cloud-Speicherpfad enthält und dass die Einstiegsanleitung alle Regeln der Anforderung „Einstiegsanleitung im Wurzelverzeichnis" erfüllt; ein Treffer MUST den Lauf mit einem Exit-Code ungleich 0 abbrechen. Das Paket MUST außerhalb des Repositorys abgelegt und sein Pfad MUST ausgegeben werden. Das Kommando MUST NOT in der Einstiegsanleitung erscheinen.

#### Scenario: Paket wird gebaut

- **WHEN** das Bauen des Release-Pakets angefordert wird
- **THEN** entsteht ein ZIP mit einem einzelnen Ordner als oberster Ebene
- **AND** es enthält die Versionsdatei, die Einstiegsanleitung und die Beschreibung des Release
- **AND** die Ausgabe nennt den Pfad des Pakets außerhalb des Repositorys

#### Scenario: Nutzerpfad in einer versionierten Datei

- **WHEN** eine versionierte Datei einen Benutzer-, Firmen- oder Cloud-Speicherpfad enthält
- **THEN** bricht der Lauf ab, ohne ein Paket zu erzeugen
- **AND** die Meldung nennt Datei und Fundstelle

#### Scenario: Nicht versionierte Inhalte bleiben draußen

- **WHEN** das Paket gebaut wird
- **THEN** enthält es weder die eingerichtete Umgebung noch Protokolle, Konfigurationsdateien, Verknüpfungen oder Dateien mit Zugangsdaten

#### Scenario: Lockdatei passt nicht

- **WHEN** die Lockdatei nicht zur Projektdefinition passt
- **THEN** bricht der Lauf ab, ohne ein Paket zu erzeugen
- **AND** die Meldung nennt das Kommando zur Erneuerung der Lockdatei

### Requirement: Deinstallation

Die Deinstallation MUST ohne ein Kommando möglich sein: Fenster schließen, Desktop-Verknüpfung löschen, Ordner löschen. Die Einstiegsanleitung und der Menüpunkt „Info" MUST diesen Weg in dieser Form nennen; die Auskunft im Anwendungsfenster MUST dabei sagen, dass Konfiguration, Protokolle und Zustand im benutzerbezogenen Anwendungsdatenverzeichnis liegen und getrennt zu löschen sind.

Zusätzlich MUST es ein Kommando geben. Es MUST die Desktop-Verknüpfung und die erzeugte Umgebung entfernen und eine laufende Instanz zuvor beenden. Ohne ausdrückliche Anforderung MUST es Konfiguration, Protokolle und Zustand erhalten; wird es ausdrücklich angefordert, MUST es zusätzlich das Verzeichnis mit Konfiguration, Protokollen und Zustand entfernen. Es MUST NOT Aufnahmen und Zieldateien im Datenbereich löschen, MUST NOT extern installierte Programme entfernen und MUST NOT die suiteweite Handshake-Datei antasten. Am Ende MUST es benennen, was absichtlich nicht entfernt wurde, und wie es entfernt werden kann.

#### Scenario: Deinstallation ohne Kommando

- **WHEN** ein Benutzer die Anwendung ohne Kommando entfernen will
- **THEN** nennen die Einstiegsanleitung und der Menüpunkt „Info" drei Schritte: Fenster schließen, Verknüpfung löschen, Ordner löschen
- **AND** der Menüpunkt „Info" nennt den Ort, an dem Konfiguration, Protokolle und Zustand verbleiben

#### Scenario: Deinstallation ohne Datenlöschung

- **WHEN** die Deinstallation ohne ausdrückliche Anforderung zur Datenlöschung angefordert wird
- **THEN** sind Verknüpfung und Umgebung entfernt
- **AND** Konfiguration, Protokolle und Zustand bestehen weiter
- **AND** die Ausgabe nennt das Kommando für die vollständige Entfernung

#### Scenario: Vollständige Deinstallation

- **WHEN** die Deinstallation mit ausdrücklicher Datenlöschung angefordert wird
- **THEN** ist zusätzlich das Verzeichnis mit Konfiguration, Protokollen und Zustand entfernt
- **AND** die Aufnahmen und Zieldateien im Datenbereich bestehen weiter

#### Scenario: Laufende Instanz beim Deinstallieren

- **WHEN** die Deinstallation angefordert wird, während die Anwendung läuft
- **THEN** wird die Anwendung zuvor beendet
- **AND** die Deinstallation beginnt erst danach

#### Scenario: Extern installierte Programme bleiben

- **WHEN** die Deinstallation läuft
- **THEN** bleiben ffmpeg und der Paket- und Umgebungsmanager installiert
- **AND** die Ausgabe nennt sie als absichtlich nicht entfernt
