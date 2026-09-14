## Context

Siehe `proposal.md` — Why. Zum Stand, der diesen Entwurf formt:

Das Fenster ist 280 px breit und verteidigt diese Breite in einer 150-ms-Schleife (`src/backrec/app.py:38`, `src/backrec/app.py:520-537`). In seiner Kopfzeile liegen heute zwei Dinge nebeneinander: links die Statuszeile, rechts die Zahnrad-Schaltfläche mit Tooltip (`src/backrec/app.py:166-179`). Das Menü selbst ist ein `tk.Menu` mit fünf Einträgen und einer Sperrlogik, die während einer Aufnahme drei davon ausgraut und den Grund in den Beschriftungstext schreibt (`src/backrec/app.py:110-118`, `src/backrec/app.py:322-338`).

Jeder langlaufende Menüpunkt geht durch `_in_background` (`src/backrec/app.py:340-366`): Menü sperren, Statuszeilentext merken, durch einen Arbeitstext ersetzen, Thread starten, danach zurücksetzen. Genau dieser Mechanismus wird durch die Entscheidung entbehrlich — und er darf für den neuen Weg auch nicht wiederverwendet werden (siehe D26).

Die Diagnose selbst ist bereits fertig und geprüft: `control.run_doctor(report=True, open_report=True)` schreibt den Bericht und öffnet ihn (`src/backrec/control.py:978-995`). Sie ist ausdrücklich rein lesend (design D12) — bis auf den Bericht und den eigenen Protokolleintrag. Daran ändert dieser Change nichts; er ändert nur, wovon aus sie ausgelöst wird.

## Goals / Non-Goals

**Goals:**

- Das Fenster trägt nach dem Umbau genau die Elemente, für die es da ist: REC, STOP, Discard, zwei Pegelzeilen, Statuszeile. Kein zusätzliches Bedienelement.
- Der eine Weg, der aus dem Fenster heraus nötig bleibt — „was ist hier los, was schicke ich Tobias?" — bleibt vollständig erhalten und wird kürzer: ein Klick statt Zahnrad, Menü, Eintrag.
- Kein Kommando verliert eine Fähigkeit. Die Control-Surface bleibt unverändert.
- Der Klick ist auch während einer Aufnahme gefahrlos.

**Non-Goals:**

- Kein neues Bedienelement als Ersatz für das Menü (kein Diagnose-Knopf, kein Kontextmenü, keine zweite Zeile).
- Keine Änderung an Aufnahme, Mischung, Ablage, Preflight, Einrichtung, Diagnoseprüfungen, Verknüpfung oder Release-Bau.
- Keine Änderung an den vier Tray-Werkzeugen der Suite und an der suiteweiten Reihenfolge ihrer Tray-Einträge. Backrec war dort schon vorher der Sonderfall ohne Tray; es wird ein stärkerer Sonderfall, kein Präzedenzfall.
- Keine neue Abhängigkeit, keine neue Datei, kein neues Modul.

## Decisions

### D25: Die Statuszeile ist der Knopf — kein Element kommt hinzu

Das Fenster braucht **einen** Zugang zur Diagnose und hat keinen Platz für ein Element, das nur dafür da ist. Die Statuszeile liegt bereits in der Kopfzeile, ist über die volle Breite anklickbar, und sie ist fachlich der richtige Ort: Sie sagt, wie es steht; der Klick darauf sagt, warum.

Das Muster ist im selben Fenster schon zweimal etabliert — die beiden Pegelzeilen sind seit jeher anklickbar und schalten Mikrofon und Systemton stumm (`src/backrec/app.py:193-195`, `src/backrec/app.py:209-211`), jeweils mit `cursor="hand2"` als einzigem Hinweis. Die Statuszeile bekommt dieselbe Behandlung und zusätzlich den Hovertext, den es für das Zahnrad schon gab.

**Verworfen: das Menü behalten und nur kürzen.** Drei Einträge statt fünf hätten das eigentliche Problem nicht angefasst — ein Fenster mit drei Knöpfen trägt weiter eine Schaltfläche, deren Bedeutung man aufklappen muss, um sie zu erfahren. Die Frage ist nicht, wie viele Einträge ein Menü haben darf, sondern ob dieses Fenster ein Menü braucht.

**Verworfen: die Diagnose als eigener Knopf in der Knopfreihe.** Ein vierter Knopf neben REC, STOP und Discard nimmt entweder Breite von den dreien weg oder zwingt das Fenster über 280 px. Beides verliert mehr, als der gewonnene Klickweg wert ist: Die Knopfreihe ist das, wofür das Fenster offen steht, und der Diagnoseknopf wäre der einzige darin, der nichts mit der Aufnahme zu tun hat. Zusätzlich hätte er neben „✕" das zweite ikonische Element ohne Beschriftung im Fenster.

**Verworfen: Rechtsklick-Kontextmenü auf dem Fenster.** Unsichtbar für den Adressaten; ein Kollege, der nicht weiß, dass es existiert, findet es nie. Der Hovertext der Statuszeile ist der Kompromiss, der sichtbar bleibt, ohne Platz zu kosten.

**Preis:** Ein Klick auf die Statuszeile ist nicht selbsterklärend — er ist nur durch Zeigerform und Hovertext angekündigt. Der Preis ist bewusst: Die Alternative wäre ein sichtbares Element, und genau das soll weg. Die Anleitung nennt den Klick ausdrücklich in „Wenn etwas rot ist", und die Abschlusszusammenfassung der Einrichtung nennt ihn ebenfalls — das sind die beiden Stellen, an denen ein Kollege ihn zum ersten Mal braucht.

### D26: Der Klick ändert die Statuszeile nicht, auch nicht kurz

Der naheliegende Weg wäre, `_in_background` weiterzuverwenden: Statuszeile auf „checking…" setzen, Thread laufen lassen, danach zurücksetzen. Das ist hier falsch, aus zwei Gründen.

Erstens verlangt `diagnostics`, „Zustand bleibt unverändert": Eine Diagnose aus der Bedienoberfläche ändert weder Zustand noch **Anzeige** der Anwendung. Beim Menü war das Überschreiben vertretbar, weil die Zeile dort ein Nebeneffekt des Menüs war; als Reaktion auf einen Klick **auf die Zeile selbst** wäre es genau die verbotene Anzeigeänderung.

Zweitens ist die Zeile während einer Aufnahme die einzige Stelle, die „● recording" in Rot meldet. Sie für die Dauer eines Diagnoselaufs zu überschreiben, hieße: Der Kollege drückt auf die Zeile, die ihm sagt, dass er aufnimmt, und sie hört auf, es zu sagen. Praktisch würde die 150-ms-Schleife sie ohnehin sofort zurückschreiben (`src/backrec/app.py:841-842`), also wäre das Ergebnis ein Flackern statt einer Anzeige — die schlechteste von drei Möglichkeiten.

Der Klick läuft deshalb still: ein Thread, ein Protokolleintrag, der Bericht erscheint im Editor. Das ist die sichtbare Rückmeldung, und sie kommt vom Betriebssystem.

An die Stelle des `_menu_busy`-Riegels tritt ein einzelnes Merkmal, das einen zweiten Klick während eines laufenden Berichts verwirft. Ohne ihn würde ein Doppelklick zwei Berichte im Sekundenabstand schreiben — und die Diagnose warnt selbst, wenn sich zu viele Berichte angesammelt haben (`src/backrec/doctor.py:41`).

### D27: Der Klick bleibt während einer Aufnahme offen — die Sperrlogik entfällt ersatzlos

Das Menü sperrte Aktualisieren, Diagnose und Einstellungen während einer Aufnahme und schrieb den Grund in die Beschriftung (`src/backrec/app.py:110-118`). Für Aktualisieren und Einstellungen war das richtig: Das eine beendet die Anwendung, das andere ändert Ordner, in die gerade geschrieben wird. Beide Wege verschwinden.

Für die Diagnose war die Sperre von Anfang an strenger als nötig — sie liest nur (design D12). Sie stand dort, weil sie einen Menüeintrag teilte, der auch die beiden anderen trug, und weil `_in_background` die Statuszeile angefasst hätte. Mit D26 fällt der zweite Grund weg, mit dem Menü der erste. Damit ist der Zeitpunkt, zu dem die Diagnose am dringendsten gebraucht wird — während einer Aufnahme, die nicht so läuft wie erwartet — auch der Zeitpunkt, zu dem sie erreichbar ist.

Der Diagnoselauf öffnet kein Audiogerät (design D12) und läuft in einem eigenen Thread, nie im Aufnahme-Thread. Er berührt weder die Rohspuren noch die Aufnahmezustände.

### D28: `control.open_settings` bleibt, ohne Aufrufer in der Oberfläche

`control.open_settings` wurde im vorigen Change für den Menüeintrag gebaut und ist vollständig getestet (`tests/test_control.py:580-620`, `tests/test_no_window.py:36`). Mit dem Menü verliert sie ihren einzigen Aufrufer.

Sie bleibt trotzdem stehen. `control.py` ist die Control-Surface — „jedes Kommando einmal, als Funktion mit einem Ergebnis" (`src/backrec/control.py:1-9`); das ist die Ebene, auf der ein Vorgang existiert, unabhängig davon, welche Oberfläche ihn gerade auslöst. Das Löschen hätte nur einen Grund, und der ist Ordnungsliebe: Es nimmt eine geprüfte Funktion samt Tests aus dem Repository, ohne dass irgendetwas dadurch besser funktioniert.

**Verworfen: ein neues Kommando `settings`.** Es hätte der Funktion einen Aufrufer gegeben, aber die Zusage „die Kommandozeile bleibt unverändert" gebrochen — und ein Kommando eingeführt, das niemand angefordert hat, für einen Weg, den die Einrichtung bereits besser bedient.

**Verworfen: die Funktion löschen.** Siehe oben; zusätzlich wäre damit der Ort verschwunden, an dem der Hinweis „Änderungen gelten nach dem nächsten Start" formuliert ist.

### D29: Die Auskunft wandert vollständig in das Kommando

„Info" war der einzige Menüeintrag ohne Entsprechung in einem sichtbaren Kommandoweg für Kollegen — er nannte Version, Pfade, den Pfad der Anleitung und den Deinstallationsweg. Das Kommando `about` gibt es bereits und es liefert dieselben Zeilen aus derselben Funktion (`src/backrec/control.py:1377-1401`).

Für den Adressaten ist die Auskunft damit nicht verloren, sondern verlagert: Alles, was er daraus tatsächlich braucht — welche Fassung wo installiert ist —, steht im Kopf des Diagnoseberichts, den er mit demselben Klick erreicht. Der Deinstallationsweg steht in der Anleitung, die er ohnehin hat.

### D30: Aktualisieren hat für Kollegen künftig genau einen Weg

Zwei gleichwertige Wege waren eine Zusage an den Fall, dass jemand das ZIP schon geladen hat und das Fenster offen ist. In der Praxis kostet die Zusage mehr, als sie einbringt: Weg B braucht einen Dateiauswahldialog, zwei Meldungsdialoge, eine Bestätigungsfrage, einen Helfer außerhalb des Ordners und eine Abbruchbehandlung für den Fall, dass der Ordner sich nicht ersetzen lässt (`src/backrec/app.py:368-418`, `src/backrec/control.py:1110-1207`).

Der Code dafür bleibt bestehen — `control.apply_archive` samt Helfer und Manifestlogik ist der Kern auch von `update <zip>` auf der Kommandozeile und von der Erkennung eines Versionswechsels in der Einrichtung. Was entfällt, ist ausschließlich der Bedienweg im Fenster.

**Preis:** Backrec hat damit keinen Aktualisierungsweg mehr, der ohne Dateimanager auskommt. Für den Adressaten ist das kein Verlust — er bekommt ohnehin ein ZIP geschickt und entpackt es; er wird nur nicht mehr zusätzlich gefragt, ob er es stattdessen im Fenster auswählen will. Für die vier Nachbarwerkzeuge bleibt die Zusage unberührt; sie haben ein Tray und dort ihren eigenen Weg.

## Risks / Trade-offs

- **Der Klick auf die Statuszeile wird nicht gefunden** → Hovertext auf der Zeile, Zeigerform „Hand" wie bei den beiden Pegelzeilen, ausdrückliche Nennung in „Wenn etwas rot ist" der Anleitung und in der Abschlusszusammenfassung der Einrichtung. Der Abnahmepunkt „Abnahme des Kollegenwegs" prüft genau das am lebenden Objekt; bisher hieß Punkt (d) dort „sie findet das Zahnrad-Menü ohne Hilfe" und heißt künftig „sie findet den Weg zur Diagnose ohne Hilfe".
- **Ein versehentlicher Klick löst eine Diagnose aus** → Folgenlos: Die Diagnose liest, schreibt einen Bericht und öffnet ihn. Der geöffnete Editor ist die Rückmeldung; der Bericht lässt sich schließen und löschen. Die Diagnose warnt selbst, wenn sich Berichte ansammeln.
- **Ein Doppelklick schreibt zwei Berichte** → Ein Merkmal verwirft den zweiten Klick, solange der erste Lauf arbeitet (D26).
- **Ein Kollege sucht das Zahnrad, das er aus der alten Fassung kennt** → Betrifft genau die Personen, die Backrec bereits benutzen; Tobias' eigener Rechner und höchstens eine Handvoll weitere. Die Anleitung liegt im Ordner und ist nach dem Entpacken der neuen Fassung aktuell. Kein Migrationsschritt nötig.
- **Die Diagnose während einer Aufnahme verzögert die Aufnahme** → Sie läuft in einem eigenen Thread und öffnet kein Audiogerät. Die Prüfung der Lockdatei hat ein Zeitlimit (`src/backrec/doctor.py:44`); sie belegt weder CPU noch Gerät in einem Maß, das eine laufende Aufnahme spürt. Der Abnahmepunkt zur Aufnahme prüft es zusammen mit einem Klick währenddessen.

## Migration Plan

Keine Datenmigration, kein Zustand, kein Format ändert sich. Der Umbau wirkt mit der nächsten Fassung, die ein Kollege entpackt und einrichtet; eine laufende ältere Fassung behält ihr Menü, bis sie ersetzt wird.

Rückweg: Der Change ist eine Entfernung aus einer einzigen Datei plus Text in drei Dokumenten. Ein Zurücknehmen wäre die Umkehrung desselben Commits; nichts außerhalb des Repositorys müsste dafür angefasst werden.
