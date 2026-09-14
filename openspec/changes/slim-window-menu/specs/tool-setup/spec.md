## MODIFIED Requirements

### Requirement: Zwei Doppelklick-Dateien und eine Versionsangabe im Wurzelverzeichnis

Das Repository MUST im Wurzelverzeichnis genau zwei Dateien anbieten, die per Doppelklick einen Vorgang starten: `Setup.cmd` für die Einrichtung und `Start.cmd` für den Start. Es MUST NOT weitere Dateien enthalten, die per Doppelklick einen Vorgang starten, insbesondere nicht für Beenden, Aktualisieren, Diagnose oder Deinstallation; diese Vorgänge MUST als Kommandos erreichbar bleiben, und die Diagnose MUST zusätzlich aus dem Anwendungsfenster erreichbar sein. Textdateien, die per Doppelklick nur im Editor erscheinen und keinen Vorgang auslösen — die Versionsangabe und die Einstiegsanleitung —, MUST von dieser Beschränkung ausgenommen sein. Jede der beiden Dateien MUST in das Verzeichnis wechseln, in dem sie liegt, und MUST NOT eigene Ablauflogik enthalten, sondern das zugehörige Kommando aufrufen. Wird sie per Doppelklick gestartet oder endet das Kommando mit einem Exit-Code ungleich 0, MUST das Fenster offen bleiben, bis der Benutzer es schließt. Das Wurzelverzeichnis MUST zusätzlich eine Textdatei mit der Version enthalten, die ohne eine eingerichtete Laufzeit lesbar ist und die einzige Quelle der Versionsangabe ist.

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
- **AND** die Diagnose ist zusätzlich aus dem Anwendungsfenster erreichbar
- **AND** die beiden Textdateien mit Version und Einstiegsanleitung lösen bei einem Doppelklick keinen Vorgang aus

#### Scenario: Version ohne Laufzeit lesbar

- **WHEN** die Version aus einem frisch entpackten Ordner ohne eingerichtete Umgebung ermittelt wird
- **THEN** liefert die Textdatei im Wurzelverzeichnis sie
- **AND** keine andere Datei im Repository führt eine abweichende Versionsangabe

### Requirement: Einstiegsanleitung im Wurzelverzeichnis

Das Wurzelverzeichnis MUST eine Einstiegsanleitung mit dem Namen `LIES-MICH-ZUERST.txt` enthalten. Sie MUST reiner Text sein, MUST in UTF-8 mit Bytereihenfolge-Kennung und mit Windows-Zeilenenden gespeichert sein, damit ein Doppelklick sie im Standard-Editor mit korrekten Umlauten und Zeilenumbrüchen zeigt. Sie MUST höchstens 40 Zeilen umfassen, jede Zeile MUST höchstens 80 Zeichen lang sein. Sie MUST NOT Auszeichnungssyntax, Tabellen, ein Kommando, einen Dateipfad außer dem Entpackziel oder einen Fachbegriff der Sperrliste enthalten.

Sie MUST auf Deutsch verfasst sein, auch wenn die Entwicklerdokumentation des Repositorys englisch bleibt.

Sie MUST genau diese acht Abschnitte in dieser Reihenfolge führen: Kopf mit Werkzeugname und je einem Satz zu Zweck und Anlass; „Was du brauchst"; „So richtest du es ein" mit nummerierten Schritten; „Im Alltag"; „Wenn etwas rot ist"; „Aktualisieren"; „Entfernen"; Ansprechpartner mit dem Hinweis, dass alles Technische in der Entwicklerdokumentation steht und nicht gebraucht wird. Der Abschnitt „Was du brauchst" MUST NOT ein Fremdprogramm verlangen, das die Einrichtung selbst beschafft. Die nummerierten Schritte MUST nennen, dass die Verknüpfung auf dem Desktop angelegt wird, und MUST das Symbol auf dem Desktop als Ergebnis nennen; sie MUST NOT einen Autostart-Ordner, ein Ziehen einer Verknüpfung oder ein Symbol im Infobereich nennen. „Im Alltag" MUST die Bedienung der Aufnahme nennen und MUST das erneute Ausführen der Einrichtung als den Weg nennen, auf dem eine Einstellung geändert wird; er MUST NOT ein Menü im Anwendungsfenster nennen. „Wenn etwas rot ist" MUST den Klick auf die Statuszeile als Weg zur Diagnose und das Weiterschicken des erzeugten Berichts nennen. „Aktualisieren" MUST genau einen Weg nennen: das neue Archiv über den Ordner entpacken und die Einrichtung erneut ausführen. „Entfernen" MUST die drei Schritte Fenster schließen, Desktop-Verknüpfung löschen, Ordner löschen nennen.

Sie MUST die einzige Stelle im Repository sein, an der dieser Text steht. Die Entwicklerdokumentation MUST mit einem Verweis auf diese Datei beginnen und MUST NOT einen eigenen, an Kollegen gerichteten Einrichtungsteil führen. Die Auskunft über die Installation MUST den Pfad dieser Datei nennen, und die Beschreibung des Release MUST sie führen.

Das Bauen des Release-Pakets MUST die Datei maschinell prüfen: Name, Zeichenkodierung, Zeilenenden, Zeilenzahl, Zeilenlänge, Sperrliste sowie Vorhandensein und Reihenfolge der acht Abschnitte. Fehlt die Datei oder verletzt sie eine dieser Regeln, MUST der Lauf ohne Paket mit einem Exit-Code ungleich 0 abbrechen und MUST die verletzte Regel samt Fundstelle nennen; eine Warnung MUST NOT genügen.

#### Scenario: Kollege öffnet den entpackten Ordner

- **WHEN** ein Kollege den aus dem Release-ZIP entpackten Ordner im Dateimanager öffnet
- **THEN** enthält der Ordner `LIES-MICH-ZUERST.txt`
- **AND** ein Doppelklick zeigt sie im Standard-Editor mit korrekten Umlauten und Zeilenumbrüchen
- **AND** sie führt ihn ohne weitere Hilfe von der Einrichtung bis zum laufenden Fenster

#### Scenario: Der Weg zur Diagnose in der Anleitung

- **WHEN** ein Kollege den Abschnitt „Wenn etwas rot ist" liest
- **THEN** nennt er den Klick auf die Statuszeile als Weg zur Diagnose
- **AND** er nennt das Weiterschicken der erzeugten Datei
- **AND** die Anleitung nennt an keiner Stelle ein Menü im Anwendungsfenster

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

### Requirement: Reihenfolge, Meldungen und Abschluss der Einrichtung

Die Einrichtung MUST in dieser Reihenfolge ablaufen: Laufzeit, Umgebung, Konfiguration, externe Abhängigkeiten, Prüfung durch die Diagnose, Frage nach der Desktop-Verknüpfung, Frage nach dem Start. Jeder Schritt MUST eine lesbare Meldung über Beginn und Ergebnis erzeugen. Ein fehlgeschlagener Schritt MUST die Einrichtung beenden und MUST NOT stillschweigend übersprungen werden. Am Ende MUST die Einrichtung nennen, wo die Anwendung künftig gestartet wird und dass ein Klick auf die Statuszeile des Fensters die Diagnose öffnet; sie MUST NOT ein Menü im Anwendungsfenster nennen. Die Abschlussausgabe MUST in jedem Lauf den Ort der Konfigurationsdatei nennen und beide Wege zum Ändern einer Einstellung: die Einrichtung erneut ausführen oder die Datei im Editor öffnen. Melden die Prüfungen mindestens einen harten Fehler, MUST die Einrichtung mit einem Exit-Code ungleich 0 enden und MUST NOT als „fertig" gemeldet werden.

#### Scenario: Erfolgreiche Einrichtung

- **WHEN** die Einrichtung ohne harten Fehler durchläuft
- **THEN** ist der Exit-Code 0
- **AND** die Ausgabe nennt den künftigen Startweg und den Klick auf die Statuszeile als Weg zur Diagnose
- **AND** sie nennt kein Menü im Anwendungsfenster

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

### Requirement: Aktualisierung über ein neues Release-ZIP

Eine Aktualisierung MUST ohne Versionsverwaltung möglich sein. Der für Kollegen dokumentierte Weg MUST genau einer sein: ein neueres Release-ZIP über den vorhandenen Ordner entpacken und die Einrichtung erneut starten. Dabei MUST die Einrichtung den Wechsel der Version erkennen, eine laufende Instanz zuvor beenden, die Umgebung aus der Lockdatei erneuern, Altdateien entfernen, die Diagnose ausführen und den Start anbieten. Konfiguration, Protokolle und Zustand MUST unberührt bleiben, weil sie außerhalb des Ordners liegen.

Das Anwendungsfenster MUST NOT einen eigenen Bedienweg zum Aktualisieren anbieten; es MUST NOT ein Archiv zur Auswahl stellen.

Als Kommando MUST eine Aktualisierung mit einem ausgewählten ZIP erhalten bleiben. Dabei MUST vor jeder Veränderung geprüft werden, dass das ZIP zu diesem Werkzeug gehört und eine neuere Version trägt; die bisherige und die neue Version MUST genannt werden, und eine ältere oder gleiche Version MUST nur nach ausdrücklicher Zustimmung eingespielt werden. Das ZIP MUST zuerst in einen Nachbarordner entpackt und der vorhandene Ordner MUST erst nach erfolgreicher Entpackung ersetzt werden, damit ein Abbruch nie einen unvollständigen Ordner hinterlässt. Die eingerichtete Umgebung MUST übernommen und MUST NOT neu aufgebaut werden. Scheitert ein Schritt, MUST der bisherige Stand lauffähig bleiben und der Rückweg MUST genannt werden.

Eine Aktualisierung über die Versionsverwaltung MUST als Entwicklerweg erhalten bleiben, MUST nur bei vorhandener Versionsverwaltung angeboten werden und MUST NOT der für Kollegen dokumentierte Weg sein.

#### Scenario: Neues ZIP über den Ordner entpackt

- **WHEN** ein neueres Release-ZIP über den vorhandenen Ordner entpackt und die Einrichtung erneut gestartet wird
- **THEN** erkennt sie den Wechsel der Version und nennt beide Versionen
- **AND** eine laufende Instanz wird zuvor beendet
- **AND** Konfiguration, Protokolle und Zustand bleiben unverändert

#### Scenario: Aktualisierung aus der Bedienoberfläche

- **WHEN** ein Benutzer im Anwendungsfenster nach einem Weg zum Aktualisieren sucht
- **THEN** bietet das Fenster keinen an und stellt kein Archiv zur Auswahl
- **AND** die Einstiegsanleitung nennt das Entpacken über den Ordner und den erneuten Lauf der Einrichtung

#### Scenario: Aktualisierung über das Kommando

- **WHEN** die Aktualisierung als Kommando mit einem ausgewählten ZIP angefordert wird
- **THEN** nennt die Ausgabe die bisherige und die neue Version
- **AND** der Ordner wird erst nach erfolgreicher Entpackung ersetzt

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

### Requirement: Deinstallation

Die Deinstallation MUST ohne ein Kommando möglich sein: Fenster schließen, Desktop-Verknüpfung löschen, Ordner löschen. Die Einstiegsanleitung und die Auskunft über die Installation MUST diesen Weg in dieser Form nennen; die Auskunft MUST dabei sagen, dass Konfiguration, Protokolle und Zustand im benutzerbezogenen Anwendungsdatenverzeichnis liegen und getrennt zu löschen sind.

Zusätzlich MUST es ein Kommando geben. Es MUST die Desktop-Verknüpfung und die erzeugte Umgebung entfernen und eine laufende Instanz zuvor beenden. Ohne ausdrückliche Anforderung MUST es Konfiguration, Protokolle und Zustand erhalten; wird es ausdrücklich angefordert, MUST es zusätzlich das Verzeichnis mit Konfiguration, Protokollen und Zustand entfernen. Es MUST NOT Aufnahmen und Zieldateien im Datenbereich löschen, MUST NOT extern installierte Programme entfernen und MUST NOT die suiteweite Handshake-Datei antasten. Am Ende MUST es benennen, was absichtlich nicht entfernt wurde, und wie es entfernt werden kann.

#### Scenario: Deinstallation ohne Kommando

- **WHEN** ein Benutzer die Anwendung ohne Kommando entfernen will
- **THEN** nennen die Einstiegsanleitung und die Auskunft über die Installation drei Schritte: Fenster schließen, Verknüpfung löschen, Ordner löschen
- **AND** die Auskunft nennt den Ort, an dem Konfiguration, Protokolle und Zustand verbleiben

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
