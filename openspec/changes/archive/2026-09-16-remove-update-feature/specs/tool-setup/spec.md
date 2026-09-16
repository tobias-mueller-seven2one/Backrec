## REMOVED Requirements

### Requirement: Aktualisierung über ein neues Release-ZIP

**Reason**: Die Anwendungen der MemoSuite haben keine Aktualisierungsfunktion (Entscheidung Tobias Müller, 15.09.2026). Ein neuer Stand wird beschafft, indem das Programm neu heruntergeladen wird und den vorhandenen Stand ersetzt — fachlich ein vollständiges Löschen mit anschließendem normalem Setup. Beide Vorgänge sind bereits vollständig spezifiziert („Deinstallation", „Einrichtung aus einem entpackten Release-ZIP"). Eine dritte Anforderung, die beides zusammenfasst, deckt keinen fachlichen Bedarf ab und trägt Lasten, die keinem Nutzen gegenüberstehen: eine Selbstersetzung des laufenden Programms, ein Vergleichsmaßstab über den Dateibestand und ein Löschpfad im Ordner des Benutzers.

**Migration**: Keine. Der Vorgang „Programm aktualisieren" existiert nicht mehr und wird nirgendwo beschrieben — weder als Kommando noch als Bedienweg, Erkennung oder Doku-Abschnitt. Die Einrichtung bleibt idempotent und darf beliebig oft laufen; sie kennt dabei keinen Vorgängerstand und vergleicht keine Versionen.

### Requirement: Entfernen von Altdateien anhand des Release-Verzeichnisses

**Reason**: Die Anforderung existierte ausschließlich, um bei einer Aktualisierung die Dateien des Vorgängerstands zu entfernen, die im neuen Stand fehlen. Ohne Aktualisierungsvorgang gibt es keinen Vorgängerstand im selben Ordner, gegen den verglichen werden könnte. Die Beschreibung des Release war allein dafür da, dieser Vergleich zu ermöglichen; sie wird von nichts anderem gebraucht.

**Migration**: Keine. Die Beschreibung des Release (`release-manifest.json`) wird nicht mehr erzeugt, nicht mehr ins Paket gelegt und nicht mehr außerhalb des Ordners abgelegt; eine bestehende Datei dieses Namens wird weder gelesen noch gelöscht.

## MODIFIED Requirements

### Requirement: Zwei Doppelklick-Dateien und eine Versionsangabe im Wurzelverzeichnis

Das Repository MUST im Wurzelverzeichnis genau zwei Dateien anbieten, die per Doppelklick einen Vorgang starten: `Setup.cmd` für die Einrichtung und `Start.cmd` für den Start. Es MUST NOT weitere Dateien enthalten, die per Doppelklick einen Vorgang starten, insbesondere nicht für Beenden, Diagnose oder Deinstallation; diese Vorgänge MUST als Kommandos erreichbar bleiben, und die Diagnose MUST zusätzlich aus dem Anwendungsfenster erreichbar sein. Textdateien, die per Doppelklick nur im Editor erscheinen und keinen Vorgang auslösen — die Versionsangabe und die Einstiegsanleitung —, MUST von dieser Beschränkung ausgenommen sein. Jede der beiden Dateien MUST in das Verzeichnis wechseln, in dem sie liegt, und MUST NOT eigene Ablauflogik enthalten, sondern das zugehörige Kommando aufrufen. Wird sie per Doppelklick gestartet oder endet das Kommando mit einem Exit-Code ungleich 0, MUST das Fenster offen bleiben, bis der Benutzer es schließt. Das Wurzelverzeichnis MUST zusätzlich eine Textdatei mit der Version enthalten, die ohne eine eingerichtete Laufzeit lesbar ist und die einzige Quelle der Versionsangabe ist.

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
- **AND** Beenden, Diagnose und Deinstallation sind dennoch über Kommandos erreichbar
- **AND** die Diagnose ist zusätzlich aus dem Anwendungsfenster erreichbar
- **AND** die beiden Textdateien mit Version und Einstiegsanleitung lösen bei einem Doppelklick keinen Vorgang aus

#### Scenario: Version ohne Laufzeit lesbar

- **WHEN** die Version aus einem frisch entpackten Ordner ohne eingerichtete Umgebung ermittelt wird
- **THEN** liefert die Textdatei im Wurzelverzeichnis sie
- **AND** keine andere Datei im Repository führt eine abweichende Versionsangabe

#### Scenario: Kein Weg zum Aktualisieren des Programms

- **WHEN** die Kommandos, das Wurzelverzeichnis und das Anwendungsfenster betrachtet werden
- **THEN** gibt es kein Kommando, keine Datei und kein Bedienelement, das das Programm selbst aktualisiert
- **AND** es gibt keinen Helfer, der dafür einen eigenen Vorgang außerhalb des Ordners startet

### Requirement: Einstiegsanleitung im Wurzelverzeichnis

Das Wurzelverzeichnis MUST eine Einstiegsanleitung mit dem Namen `LIES-MICH-ZUERST.txt` enthalten. Sie MUST reiner Text sein, MUST in UTF-8 mit Bytereihenfolge-Kennung und mit Windows-Zeilenenden gespeichert sein, damit ein Doppelklick sie im Standard-Editor mit korrekten Umlauten und Zeilenumbrüchen zeigt. Sie MUST höchstens 40 Zeilen umfassen, jede Zeile MUST höchstens 80 Zeichen lang sein. Sie MUST NOT Auszeichnungssyntax, Tabellen, ein Kommando, einen Dateipfad außer dem Entpackziel oder einen Fachbegriff der Sperrliste enthalten.

Sie MUST auf Deutsch verfasst sein, auch wenn die Entwicklerdokumentation des Repositorys englisch bleibt.

Sie MUST genau diese sieben Abschnitte in dieser Reihenfolge führen: Kopf mit Werkzeugname und je einem Satz zu Zweck und Anlass; „Was du brauchst"; „So richtest du es ein" mit nummerierten Schritten; „Im Alltag"; „Wenn etwas rot ist"; „Entfernen"; Ansprechpartner mit dem Hinweis, dass alles Technische in der Entwicklerdokumentation steht und nicht gebraucht wird. Der Abschnitt „Was du brauchst" MUST NOT ein Fremdprogramm verlangen, das die Einrichtung selbst beschafft. Die nummerierten Schritte MUST nennen, dass die Verknüpfung auf dem Desktop angelegt wird, und MUST das Symbol auf dem Desktop als Ergebnis nennen; sie MUST NOT einen Autostart-Ordner, ein Ziehen einer Verknüpfung oder ein Symbol im Infobereich nennen. „Im Alltag" MUST die Bedienung der Aufnahme nennen und MUST das erneute Ausführen der Einrichtung als den Weg nennen, auf dem eine Einstellung geändert wird; er MUST NOT ein Menü im Anwendungsfenster nennen. „Wenn etwas rot ist" MUST den Klick auf die Statuszeile als Weg zur Diagnose und das Weiterschicken des erzeugten Berichts nennen. „Entfernen" MUST die drei Schritte Fenster schließen, Desktop-Verknüpfung löschen, Ordner löschen nennen. Die Anleitung MUST NOT einen Abschnitt oder einen Satz zum Aktualisieren des Programms führen.

Sie MUST die einzige Stelle im Repository sein, an der dieser Text steht. Die Entwicklerdokumentation MUST mit einem Verweis auf diese Datei beginnen und MUST NOT einen eigenen, an Kollegen gerichteten Einrichtungsteil führen. Die Auskunft über die Installation MUST den Pfad dieser Datei nennen, und der Release-Bau MUST sie in das Paket aufnehmen.

Das Bauen des Release-Pakets MUST die Datei maschinell prüfen: Name, Zeichenkodierung, Zeilenenden, Zeilenzahl, Zeilenlänge, Sperrliste sowie Vorhandensein und Reihenfolge der sieben Abschnitte. Fehlt die Datei oder verletzt sie eine dieser Regeln, MUST der Lauf ohne Paket mit einem Exit-Code ungleich 0 abbrechen und MUST die verletzte Regel samt Fundstelle nennen; eine Warnung MUST NOT genügen.

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

#### Scenario: Kein Abschnitt zum Aktualisieren

- **WHEN** die Einstiegsanleitung gelesen wird
- **THEN** führt sie sieben Abschnitte, und keiner davon handelt vom Aktualisieren des Programms
- **AND** auf „Wenn etwas rot ist" folgt unmittelbar „Entfernen"

#### Scenario: Datei fehlt beim Bauen des Pakets

- **WHEN** das Bauen des Release-Pakets angefordert wird und die Einstiegsanleitung im Wurzelverzeichnis fehlt
- **THEN** bricht der Lauf ab, ohne ein Paket zu erzeugen
- **AND** die Meldung nennt die fehlende Datei

#### Scenario: Datei verletzt eine Formregel

- **WHEN** die Einstiegsanleitung mehr Zeilen als erlaubt hat, eine zu lange Zeile führt, in einer falschen Zeichenkodierung vorliegt oder einen Begriff der Sperrliste enthält
- **THEN** bricht das Bauen des Release-Pakets ab, ohne ein Paket zu erzeugen
- **AND** die Meldung nennt die verletzte Regel und die Zeile

#### Scenario: Abschnitt fehlt oder steht an falscher Stelle

- **WHEN** einer der sieben Abschnitte fehlt oder die Reihenfolge abweicht
- **THEN** bricht das Bauen des Release-Pakets ab, ohne ein Paket zu erzeugen
- **AND** die Meldung nennt den fehlenden oder verschobenen Abschnitt

#### Scenario: Entwicklerdokumentation verweist auf die Anleitung

- **WHEN** die Entwicklerdokumentation gelesen wird
- **THEN** beginnt sie mit einem Verweis auf `LIES-MICH-ZUERST.txt`
- **AND** sie enthält keinen eigenen, an Kollegen gerichteten Einrichtungsteil

### Requirement: Reihenfolge, Meldungen und Abschluss der Einrichtung

Die Einrichtung MUST in dieser Reihenfolge ablaufen: Laufzeit, Umgebung, Konfiguration, externe Abhängigkeiten, Prüfung durch die Diagnose, Frage nach der Desktop-Verknüpfung, Frage nach dem Start. Bevor die Einrichtung an der Umgebung arbeitet, MUST sie eine laufende Anwendung beenden. Dieses Beenden MUST unbedingt geschehen: Es MUST NOT von einem Versionsstand, einem Vergleich zweier Versionen oder einer sonstigen Erkennung eines Wechsels abhängen, und die zugehörige Meldung MUST NOT einen Versionswechsel nennen. Läuft keine Anwendung, MUST die Einrichtung ohne eine Meldung über ein Beenden fortfahren.

Das Beenden MUST auf beiden Wegen in die Einrichtung greifen: beim Doppelklick auf die Einrichtungsdatei ebenso wie beim Aufruf des Einrichtungskommandos. Wird die Arbeitsumgebung vorgelagert von außerhalb aufgebaut — also von einem Vorgang, der vor dem Einrichtungskommando läuft und dabei den Paketinhalt der Umgebung ersetzt —, MUST dieser Vorgang eine laufende Anwendung beenden, bevor er die Umgebung anfasst. Er MUST dafür das vorhandene Beenden-Kommando des Werkzeugs aufrufen und dessen Ende abwarten; er MUST NOT eine eigene Frist, eine eigene Anforderungsdatei oder eine eigene Prozesserkennung mitbringen. Gibt es noch keine eingerichtete Umgebung oder keinen Einstiegspunkt darin, MUST er ohne Beenden fortfahren. Scheitert der Aufruf oder endet er mit einem Fehler, MUST der Vorgang mit einer lesbaren Zeile fortfahren und MUST NOT abbrechen. Seine Ausgabe MUST im sichtbaren Fenster der Einrichtung erscheinen und MUST NOT unterdrückt werden. Wurde die Anwendung dabei bereits beendet, MUST die Einrichtung selbst keine zweite Meldung über ein Beenden erzeugen.

Jeder Schritt MUST eine lesbare Meldung über Beginn und Ergebnis erzeugen. Ein fehlgeschlagener Schritt MUST die Einrichtung beenden und MUST NOT stillschweigend übersprungen werden. Am Ende MUST die Einrichtung nennen, wo die Anwendung künftig gestartet wird und dass ein Klick auf die Statuszeile des Fensters die Diagnose öffnet; sie MUST NOT ein Menü im Anwendungsfenster nennen. Die Abschlussausgabe MUST in jedem Lauf den Ort der Konfigurationsdatei nennen und beide Wege zum Ändern einer Einstellung: die Einrichtung erneut ausführen oder die Datei im Editor öffnen. Melden die Prüfungen mindestens einen harten Fehler, MUST die Einrichtung mit einem Exit-Code ungleich 0 enden und MUST NOT als „fertig" gemeldet werden.

#### Scenario: Erfolgreiche Einrichtung

- **WHEN** die Einrichtung ohne harten Fehler durchläuft
- **THEN** ist der Exit-Code 0
- **AND** die Ausgabe nennt den künftigen Startweg und den Klick auf die Statuszeile als Weg zur Diagnose
- **AND** sie nennt kein Menü im Anwendungsfenster

#### Scenario: Laufende Anwendung beim Einrichten

- **WHEN** die Einrichtung läuft, während die Anwendung geöffnet ist
- **THEN** beendet sie die laufende Anwendung, bevor sie an der Umgebung arbeitet
- **AND** sie tut das auch dann, wenn sich die Version nicht geändert hat
- **AND** die Meldung nennt das Beenden und keinen Versionswechsel
- **AND** der letzte Schritt bietet den Start wieder an

#### Scenario: Keine laufende Anwendung beim Einrichten

- **WHEN** die Einrichtung läuft und keine Anwendung geöffnet ist
- **THEN** arbeitet sie ohne eine Meldung über ein Beenden weiter

#### Scenario: Laufende Anwendung beim Doppelklick auf die Einrichtung

- **WHEN** die Einrichtung per Doppelklick gestartet wird, während die Anwendung läuft
- **THEN** beendet der vorgelagerte Aufbau der Arbeitsumgebung die Anwendung, bevor er den Paketinhalt ersetzt
- **AND** er ruft dafür das Beenden-Kommando des Werkzeugs auf und wartet auf dessen Ende
- **AND** seine Meldung erscheint im sichtbaren Fenster der Einrichtung
- **AND** die Einrichtung selbst meldet danach kein zweites Beenden

#### Scenario: Laufende Anwendung beim Aufruf des Kommandos

- **WHEN** das Einrichtungskommando ohne vorgelagerten Aufbau der Arbeitsumgebung aufgerufen wird, während die Anwendung läuft
- **THEN** beendet die Einrichtung selbst die laufende Anwendung, bevor sie an der Umgebung arbeitet

#### Scenario: Kein Beenden ohne eingerichtete Umgebung

- **WHEN** die Einrichtung in einem frisch entpackten Ordner ohne eingerichtete Umgebung startet
- **THEN** wird nichts beendet
- **AND** es entsteht keine Meldung über ein Beenden

#### Scenario: Das Beenden vor dem Aufbau der Umgebung scheitert

- **WHEN** der vorgelagerte Aufruf zum Beenden scheitert oder mit einem Fehler endet
- **THEN** bricht die Einrichtung nicht ab
- **AND** eine lesbare Zeile nennt, dass das Beenden nicht geklappt hat
- **AND** der Aufbau der Arbeitsumgebung läuft weiter

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

### Requirement: Bauen eines Release-Pakets

Es MUST ein Kommando geben, das ein Release-Paket baut. Es MUST ein ZIP erzeugen, dessen oberste Ebene ein einzelner Ordner mit dem Werkzeugnamen ist, MUST die Versionsdatei darin ablegen und MUST den Dateinamen aus Werkzeugname und Version bilden. Aufgenommen MUST ausschließlich werden, was in der Versionsverwaltung geführt ist; die eingerichtete Umgebung, Zwischenstände des Interpreters, Protokolle, Konfigurationsdateien, Verknüpfungen und Dateien mit Zugangsdaten MUST NOT enthalten sein. Die Einstiegsanleitung MUST im Paket enthalten sein. Das Paket MUST NOT eine Beschreibung des Release mit Prüfsummen der enthaltenen Dateien führen. Vor dem Bauen MUST geprüft werden, dass die Lockdatei zur Projektdefinition passt, dass keine versionierte Datei einen Benutzer-, Firmen- oder Cloud-Speicherpfad enthält und dass die Einstiegsanleitung alle Regeln der Anforderung „Einstiegsanleitung im Wurzelverzeichnis" erfüllt; ein Treffer MUST den Lauf mit einem Exit-Code ungleich 0 abbrechen. Das Paket MUST außerhalb des Repositorys abgelegt und sein Pfad MUST ausgegeben werden. Das Kommando MUST NOT in der Einstiegsanleitung erscheinen.

#### Scenario: Paket wird gebaut

- **WHEN** das Bauen des Release-Pakets angefordert wird
- **THEN** entsteht ein ZIP mit einem einzelnen Ordner als oberster Ebene
- **AND** es enthält die Versionsdatei und die Einstiegsanleitung
- **AND** die Ausgabe nennt den Pfad des Pakets außerhalb des Repositorys

#### Scenario: Keine Beschreibung des Release im Paket

- **WHEN** das gebaute Paket betrachtet wird
- **THEN** enthält es keine Datei, die die enthaltenen Dateien mit ihren Prüfsummen auflistet

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
