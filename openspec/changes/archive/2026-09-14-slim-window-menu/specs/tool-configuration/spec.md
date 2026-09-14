## MODIFIED Requirements

### Requirement: Einstellungen im Setup ändern

Das Einrichten MUST der Weg sein, auf dem jede Einstellung ohne Kommandozeile und ohne Handarbeit an der Datei gesetzt werden kann. Es MUST dafür jeden Schlüssel der Vorlage anbieten, nicht nur die Pflichtwerte. Es MUST der einzige solche Weg sein: Das Anwendungsfenster MUST NOT einen eigenen Bedienweg zum Ändern oder zum Öffnen der Einstellungen anbieten. Der Ort der Datei MUST in jeder Abschlussausgabe des Einrichtens und im Kopf des Diagnoseberichts stehen, damit sie auch von Hand auffindbar bleibt.

Im **ersten Lauf** MUST es nach den Pflichtwerten in **einer** Frage anbieten, die übrigen Einstellungen anzupassen. Bei Zustimmung MUST es jeden übrigen Schlüssel der Vorlage einzeln abfragen, dabei je Schlüssel eine Zeile Bedeutung aus dem Kommentar der Vorlage nennen und den geltenden Wert als Vorgabe in Klammern zeigen; die Eingabetaste MUST diesen Wert behalten. Bei Ablehnung MUST die Vorlage gelten. Die beiden Verzeichnisse, die aus dem Basisordner abgeleitet werden, MUST NOT im ersten Lauf ein zweites Mal gefragt werden.

In einem **erneuten Lauf** MUST es zuerst eine kompakte Übersicht der aktuellen Werte zeigen — je Zeile Schlüssel und Wert — und danach in **einer** Frage anbieten, etwas zu ändern. Die Eingabetaste MUST alles lassen, wie es ist. Bei Zustimmung MUST es dieselben Fragen stellen, mit den aktuellen Werten als Vorgabe, und dabei auch die beiden Verzeichnisse einzeln anbieten. Ein Wert, dessen Schlüssel wie ein Geheimnis heißt, MUST in der Übersicht und in der Vorgabe nur als „gesetzt" oder „nicht gesetzt" erscheinen und MUST NOT im Klartext auf dem Bildschirm stehen. Ist die vorhandene Datei nicht lesbar, MUST der Lauf ohne Übersicht und ohne Frage weiterlaufen.

Jede Antwort MUST gegen die Art des Wertes geprüft werden — Zahl, Ja/Nein, Aufzählung, Liste, Pfad —, und eine unpassende Antwort MUST in einem Satz ohne Fachbegriffe erklärt und erneut gefragt werden; bleibt sie unpassend, MUST der bisherige Wert stehen bleiben. Pfadangaben MUST expandiert werden. Die Arten MUST aus der Vorlage abgeleitet werden, und eine Aufzählung MUST genau die Werte anbieten, die das Werkzeug beim Start versteht, damit kein hier angenommener Wert später wirkungslos bleibt.

Die unbeaufsichtigte Einrichtung MUST nichts davon fragen. Das Ergänzen neuer Vorlagen-Schlüssel MUST unabhängig davon in jedem Lauf geschehen. Eine Änderung MUST jeden Kommentar der Datei erhalten.

#### Scenario: Erster Lauf mit weiteren Einstellungen

- **WHEN** das Einrichten die Pflichtwerte erfragt hat und der Benutzer die weiteren Einstellungen anpassen will
- **THEN** wird jeder übrige Schlüssel der Vorlage einzeln gefragt, mit einer Zeile Bedeutung und dem Vorgabewert in Klammern
- **AND** die Eingabetaste behält den jeweiligen Wert
- **AND** die geschriebene Datei enthält die geänderten Werte

#### Scenario: Erster Lauf ohne weitere Einstellungen

- **WHEN** der Benutzer die Frage nach den weiteren Einstellungen ablehnt
- **THEN** gelten für sie die Werte der Vorlage
- **AND** es wird keine weitere Frage gestellt

#### Scenario: Erneuter Lauf zeigt die Werte

- **WHEN** das Einrichten läuft und eine Konfiguration existiert
- **THEN** zeigt es eine kompakte Übersicht der aktuellen Werte
- **AND** ein Wert, dessen Schlüssel wie ein Geheimnis heißt, erscheint nur als „gesetzt" oder „nicht gesetzt"
- **AND** danach folgt genau eine Frage, ob etwas geändert werden soll

#### Scenario: Erneuter Lauf ohne Änderung

- **WHEN** der Benutzer die Frage nach einer Änderung mit der Eingabetaste beantwortet
- **THEN** bleibt die Datei Byte für Byte unverändert

#### Scenario: Erneuter Lauf mit Änderung

- **WHEN** der Benutzer eine Änderung verlangt und einen neuen Wert eingibt
- **THEN** steht dieser Wert danach in der Datei
- **AND** alle Kommentare und alle übrigen Werte der Datei bleiben erhalten

#### Scenario: Antwort passt nicht zur Art des Wertes

- **WHEN** auf eine Zahl ein Wort geantwortet wird
- **THEN** erklärt ein Satz ohne Fachbegriffe, was hier hineingehört, und die Frage kommt erneut
- **AND** bleibt die Antwort unpassend, bleibt der bisherige Wert stehen

#### Scenario: Unbeaufsichtigte Einrichtung

- **WHEN** das Einrichten unbeaufsichtigt läuft
- **THEN** wird weder die Übersicht noch eine Frage nach Einstellungen gezeigt
- **AND** die vorhandenen Werte bleiben unverändert

#### Scenario: Kein Weg zu den Einstellungen im Fenster

- **WHEN** ein Benutzer im Anwendungsfenster nach einem Weg zu den Einstellungen sucht
- **THEN** bietet das Fenster keinen an
- **AND** der Ort der Datei steht in der Abschlussausgabe des Einrichtens und im Kopf des Diagnoseberichts
