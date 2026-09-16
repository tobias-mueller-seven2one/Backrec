## REMOVED Requirements

### Requirement: Prüfung von Verknüpfung und Zustand

**Reason**: Die Anforderung verlangte unter anderem eine Warnung über „einen Ordner einer abgelösten Version aus einer Aktualisierung". Dieses Szenario setzt einen Aktualisierungsvorgang voraus, den es nicht mehr gibt (Entscheidung Tobias Müller, 15.09.2026): Die Nachbarordner `<Name>.update` und `<Name>.old-*` entstanden ausschließlich beim Staging und beim früheren Ordnertausch. Ohne den Vorgang gibt es kein Muster, nach dem gesucht werden könnte, und jeder Ordner neben dem Werkzeug ist eine legitime Sache des Benutzers. Die Anforderung wird ohne diesen Teil neu gefasst und dabei so benannt, dass ihr Umfang — Verknüpfung, Zustand und angesammelte Berichte — im Namen steht.

**Migration**: Alles außer der Prüfung auf Nachbarordner bleibt unverändert und steht in der neuen Anforderung „Prüfung von Verknüpfung, Zustand und Berichten". Ein auf einem Rechner liegen gebliebener Ordner einer früheren Fassung stört nichts; die Diagnose hätte ihn ohnehin nur genannt und nie angefasst. Er verschwindet, wenn der Installationsordner gelöscht wird.

## ADDED Requirements

### Requirement: Prüfung von Verknüpfung, Zustand und Berichten

Die Diagnose MUST melden, ob eine Desktop-Verknüpfung vorhanden ist, ob sie auf dieses Repository zeigt und ob ihr Ziel existiert. Sie MUST melden, ob das Protokollverzeichnis beschreibbar ist und ob verwaiste Zustandsdatensätze vorliegen. Ein verwaister Zustandsdatensatz MUST als Warnung gemeldet werden, nicht als Fehler. Sie MUST die eingerichtete Fassung nennen und als Warnung melden, wenn sich Diagnose-Berichte über eine festgelegte Anzahl hinaus angesammelt haben; sie MUST dabei den Weg zum Aufräumen nennen und MUST NOT selbst aufräumen. Sie MUST NOT die Nachbarordner des Repositorys prüfen.

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

#### Scenario: Nachbarordner werden nicht betrachtet

- **WHEN** neben dem Repository ein beliebiger weiterer Ordner liegt
- **THEN** erzeugt die Diagnose dazu keine Prüfung und keine Meldung

#### Scenario: Angesammelte Diagnose-Berichte

- **WHEN** im Protokollverzeichnis mehr Diagnose-Berichte liegen als die festgelegte Anzahl
- **THEN** meldet die Diagnose eine Warnung mit der Anzahl
- **AND** sie nennt das Löschen als nächsten Schritt

#### Scenario: Eingerichtete Fassung wird genannt

- **WHEN** die Diagnose läuft
- **THEN** nennt sie die eingerichtete Fassung als Auskunft
- **AND** sie vergleicht sie mit keiner anderen Fassung
