## ADDED Requirements

### Requirement: Der Takt einer Aufnahme kommt vom Aufnahmegerät

Eine Aufnahme MUST nur den Ton schreiben, den das Aufnahmegerät liefert, und MUST NOT Ton schneller erzeugen, als er anfällt. Das Fortschreiten der Aufnahme MUST an die Lieferung des Geräts gebunden sein und MUST NOT davon abhängen, dass ein Lesevorgang blockiert.

Liefert das Gerät keinen Ton mehr, MUST die Spur still bleiben oder enden. Sie MUST NOT dadurch wachsen. Der Ausfall MUST protokolliert werden.

#### Scenario: Gerät liefert regulär

- **WHEN** eine Aufnahme über eine bestimmte Zeitspanne läuft und das Gerät durchgehend liefert
- **THEN** entspricht die Tondauer der Spur der verstrichenen Zeit

#### Scenario: Gerät hört auf zu liefern

- **WHEN** das Aufnahmegerät während einer laufenden Aufnahme keinen Ton mehr liefert
- **THEN** wächst die Spur nicht über die verstrichene Zeit hinaus
- **AND** der Ausfall steht im Protokoll

#### Scenario: Aufnahme kann nicht schneller als Echtzeit laufen

- **WHEN** eine Aufnahme beendet wird
- **THEN** ist die Tondauer der Spur nicht größer als die Zeitspanne zwischen Beginn und Ende der Aufnahme

### Requirement: Die geschriebene Tonmenge folgt der verstrichenen Zeit

Jede Spur einer Aufnahme MUST die geschriebene Tonmenge an der seit dem Beginn der Aufnahme verstrichenen Zeit ausrichten. Überschreitet die geschriebene Tonmenge die verstrichene Zeit um mehr als eine festgelegte Toleranz, MUST die Schreibposition auf die der verstrichenen Zeit entsprechende Stelle zurückgesetzt und der überzählige Ton verworfen werden.

Die Aufnahme MUST danach weiterlaufen und MUST brauchbar bleiben: Es MUST NOT die gesamte Aufnahme verworfen werden, und der vor der Störung aufgenommene Ton MUST erhalten bleiben. Der Vorfall MUST protokolliert werden und MUST die betroffene Quelle sowie das Ausmaß der Abweichung nennen.

Diese Ausrichtung MUST für alle Spuren gelten, auch für solche, deren Ton nicht über den Treiber-Rückruf, sondern durch Lesen geholt wird.

Die Toleranz MUST so bemessen sein, dass sie den regulären Taktunterschied zwischen Aufnahmegerät und Systemuhr nicht als Störung wertet.

#### Scenario: Eine Spur läuft der Uhr davon

- **WHEN** eine Spur mehr Ton geschrieben hat, als seit dem Beginn der Aufnahme verstrichen ist, über die Toleranz hinaus
- **THEN** wird die Schreibposition auf die der verstrichenen Zeit entsprechende Stelle zurückgesetzt
- **AND** der überzählige Ton ist aus der Spur entfernt
- **AND** der Vorfall steht mit Quelle und Ausmaß im Protokoll

#### Scenario: Die Aufnahme überlebt die Störung

- **WHEN** eine Störung dieser Art während einer Aufnahme auftritt und danach endet
- **THEN** läuft die Aufnahme weiter und wird regulär abgeschlossen
- **AND** der vor der Störung aufgenommene Ton ist erhalten
- **AND** die Tondauer der fertigen Spur entspricht der Dauer der Aufnahme

#### Scenario: Regulärer Taktunterschied gilt nicht als Störung

- **WHEN** eine Aufnahme regulär läuft und das Aufnahmegerät geringfügig vom Takt der Systemuhr abweicht
- **THEN** wird die Schreibposition nicht zurückgesetzt
- **AND** es entsteht kein Protokolleintrag über eine Störung

#### Scenario: Beide Spuren sind abgesichert

- **WHEN** die Spur, deren Ton durch Lesen geholt wird, der Uhr davonläuft
- **THEN** greift dieselbe Ausrichtung wie bei der über den Treiber-Rückruf versorgten Spur
