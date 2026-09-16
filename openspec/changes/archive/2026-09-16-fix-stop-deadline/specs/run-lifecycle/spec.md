## MODIFIED Requirements

### Requirement: Beenden von außen

Das Beenden MUST die Anwendung samt aller von ihr gestarteten Prozesse beenden und MUST den Zustandsdatensatz danach entfernen. Der Erfolg MUST daran gemessen werden, dass kein Prozess der Anwendung mehr läuft, nicht daran, dass ein Signal gesendet wurde. Läuft keine Instanz, MUST das Beenden dies melden und ohne Fehler enden. Eine laufende Aufnahme MUST vor dem Beenden abgeschlossen werden, sodass kein Ergebnis verloren geht; erst nach einer Frist MUST der Prozessbaum hart beendet werden.

Die Frist MUST die tatsächliche Nachbereitung abdecken und MUST NOT sie abschneiden. Sie MUST sich dafür daran bemessen, dass die Anwendung nachweislich arbeitet, und MUST NOT aus der Länge der Aufnahme geschätzt werden. Meldet die Anwendung während des Abschlusses fortlaufend, dass sie arbeitet, MUST das Beenden weiter warten; bleibt die Meldung aus, MUST die Frist ablaufen. Eine Grundfrist MUST auch dann gelten, wenn nichts nachbereitet wird; ein Beenden ohne Nachbereitung MUST NOT länger dauern als bisher. Eine Obergrenze MUST das Warten in jedem Fall begrenzen, auch wenn die Meldungen nicht abreißen; das Beenden MUST NOT unbegrenzt blockieren.

Wird der Prozessbaum nach Ablauf der Frist hart beendet, MUST das Protokoll unmissverständlich festhalten, dass die Nachbereitung abgeschnitten wurde, und MUST dabei den Pfad des Aufnahmeordners nennen, in dem die Rohspuren liegen. Dasselbe MUST die Rückmeldung des Vorgangs nennen, damit es nicht nur im Protokoll steht. Ist der Aufnahmeordner nicht ermittelbar, MUST der Vorgang das harte Beenden trotzdem melden.

#### Scenario: Beenden bei laufender Anwendung

- **WHEN** das Beenden angefordert wird und die Anwendung läuft
- **THEN** läuft danach kein Prozess der Anwendung mehr
- **AND** der Zustandsdatensatz ist entfernt

#### Scenario: Beenden während einer Aufnahme

- **WHEN** das Beenden angefordert wird, während eine Aufnahme läuft
- **THEN** wird die Aufnahme zuvor regulär abgeschlossen
- **AND** das Ergebnis der Aufnahme ist danach vorhanden

#### Scenario: Nachbereitung dauert länger als die Grundfrist

- **WHEN** die Anwendung nach dem Beenden-Auftrag länger nachbereitet, als die Grundfrist zulässt, und dabei fortlaufend meldet, dass sie arbeitet
- **THEN** wartet das Beenden weiter, solange die Meldungen kommen
- **AND** der Prozessbaum wird nicht hart beendet
- **AND** das Ergebnis der Aufnahme liegt danach im Zielverzeichnis

#### Scenario: Beenden ohne Nachbereitung

- **WHEN** das Beenden angefordert wird und keine Nachbereitung gemeldet wird
- **THEN** wartet der Vorgang höchstens die Grundfrist
- **AND** er wird dadurch nicht langsamer als ohne die Verlängerung

#### Scenario: Meldungen reißen nicht ab

- **WHEN** die Anwendung dauerhaft meldet, dass sie arbeitet, ohne zu enden
- **THEN** endet das Warten spätestens an der Obergrenze
- **AND** der Prozessbaum wird hart beendet

#### Scenario: Beenden ohne laufende Instanz

- **WHEN** das Beenden angefordert wird und keine Instanz läuft
- **THEN** meldet der Vorgang, dass nichts zu beenden war
- **AND** er endet ohne Fehler

#### Scenario: Nicht reagierender Prozess

- **WHEN** die Anwendung innerhalb der Frist nicht endet
- **THEN** wird ihr Prozessbaum hart beendet
- **AND** der Vorgang protokolliert, dass die Frist überschritten wurde

#### Scenario: Abgeschnittene Nachbereitung wird benannt

- **WHEN** der Prozessbaum hart beendet wird, während die Anwendung eine Aufnahme nachbereitet hat
- **THEN** nennt das Protokoll den Pfad des Aufnahmeordners mit den Rohspuren
- **AND** die Rückmeldung des Vorgangs nennt denselben Ordner
- **AND** die Rohspuren sind unangetastet

### Requirement: Sauberes Beenden durch den Benutzer während einer Aufnahme

Das Schließen des Fensters MUST abgefangen werden. Läuft eine Aufnahme, MUST das Schließen entweder die vollständige Abschlusssequenz ausführen — Aufnahmefäden beenden, Dateien schließen, mischen, Ergebnis in das Zielverzeichnis übernehmen — oder den Benutzer entscheiden lassen, ob abgeschlossen oder verworfen wird. Das Schließen MUST NOT dazu führen, dass eine begonnene Aufnahme ohne Mischung und ohne Übernahme endet. Während der Abschlusssequenz MUST das Fenster einen Fortschritt zeigen und MUST NOT ein zweites Schließen dieselbe Sequenz erneut starten.

Die Abschlusssequenz MUST für die Dauer ihrer Arbeit von außerhalb des Prozesses erkennbar sein und MUST dabei fortlaufend melden, dass sie arbeitet — auch während eines einzelnen langlaufenden Schritts wie dem Mischen. Diese Meldung MUST getrennt von der Auskunft sein, ob gerade Ton aufgenommen wird: Sie MUST auch dann noch laufen, wenn die Aufnahme bereits beendet und nur noch gemischt und übernommen wird. Sie MUST enden, sobald die Sequenz endet, gleich ob mit Erfolg oder mit einem Fehler.

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

#### Scenario: Abschluss ist von außen erkennbar

- **WHEN** die Abschlusssequenz läuft und dabei mischt
- **THEN** meldet die Anwendung fortlaufend, dass sie arbeitet
- **AND** die Meldung läuft weiter, obwohl die Aufnahme selbst bereits beendet ist

#### Scenario: Meldung endet mit der Sequenz

- **WHEN** die Abschlusssequenz endet, mit Erfolg oder mit einem Fehler
- **THEN** endet auch die Meldung, dass gearbeitet wird
- **AND** ein späteres Beenden wartet deswegen nicht länger
