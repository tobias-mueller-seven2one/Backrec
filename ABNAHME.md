# Handabnahme Backrec

Diese Liste gehört Tobias. Sie enthält die Punkte aus dem Change
`add-suite-setup-and-run`, die keine Maschine abnehmen kann: eine echte Aufnahme
mit Mikrofon und Systemton, ein Blick in ein Fenster, das sich öffnet, ein
Rechner ohne uv und ohne ffmpeg, und der Durchlauf mit einem Kollegen. Alles
maschinell Prüfbare ist erledigt und committet; der Change ist archiviert.

**Ein abgehakter Punkt hier ist die Freigabe zum Merge des Branches
`feat/suite-setup-and-run`.**

Vorbereitung für die meisten Punkte: `Setup.cmd` wurde mindestens einmal
durchlaufen, das Symbol liegt auf dem Desktop, und der Aufnahmeordner liegt
außerhalb eines Cloud-Ordners. Wo ein Punkt eine ältere Fassung oder einen
fremden Rechner braucht, steht es dabei.

## Einrichten

- [ ] **Beschaffung von uv auf einer Maschine ohne uv** (Aufgabe 10.1)
  - Schritte: Auf einer Maschine ohne uv `Setup.cmd` doppelklicken und danach
    `uv --version` aufrufen. Zusätzlich beide Fehlwege ansehen: die Beschaffung
    über den Paketmanager scheitern lassen und den Platzhalter aus dem Microsoft
    Store vorfinden.
  - Erwartung: Nach dem Lauf antwortet `uv --version`. Der Platzhalter aus dem
    Store wird als solcher erkannt und nicht für uv gehalten. Sind beide
    Beschaffungswege gescheitert, nennt **eine** Meldung beide Wege einzeln und
    den Weg von Hand.
  - Spec: `tool-setup`, „Bootstrap der Laufzeit ohne Administratorrechte".

- [ ] **Neueinrichtung auf einem Rechner ohne uv und ohne ffmpeg** (Aufgabe 13.1)
  - Schritte: Auf einer Maschine ohne uv und ohne ffmpeg das Release-Archiv
    entpacken und `Setup.cmd` doppelklicken.
  - Erwartung: uv und ffmpeg werden beschafft, die Arbeitsumgebung entsteht, die
    Konfiguration wird angelegt, die Diagnose meldet grün, die Verknüpfung liegt
    auf dem Desktop, und die Schlussworte nennen den Startweg und das Zahnrad.
  - Spec: `tool-setup`, „Reihenfolge, Meldungen und Abschluss der Einrichtung".

- [ ] **Einstellungen auf beiden Wegen ändern** (Aufgabe 15.10)
  - Schritte: `Setup.cmd` doppelklicken. In Schritt 3 die Übersicht der
    aktuellen Werte lesen, „Einstellungen ändern?" mit der Eingabetaste
    beantworten und prüfen, dass die Datei unverändert bleibt. Danach noch
    einmal doppelklicken, diesmal mit „j" antworten, bei `log_level` absichtlich
    einen unsinnigen Wert eingeben, danach einen gültigen setzen und den Lauf zu
    Ende führen. Zuletzt im Fenster das Zahnrad öffnen und „Einstellungen
    öffnen" wählen.
  - Erwartung: Die Übersicht nennt jeden Wert in einer Zeile. Die Eingabetaste
    lässt alles stehen. Der unsinnige Wert wird in einem Satz ohne Fachbegriffe
    zurückgewiesen, die erlaubten Werte werden genannt, und die Frage kommt
    erneut. Der neue Wert steht danach in der Datei, alle Kommentare stehen noch
    darin. Die Schlussworte nennen den Ort der Datei und beide Wege zum Ändern.
    Der Menüeintrag öffnet die Datei im Editor, das Fenster bleibt bedienbar,
    und danach erscheint der Hinweis, dass die Änderung nach dem nächsten Start
    gilt.
  - Spec: `tool-configuration`, „Einstellungen im Setup ändern";
    `run-lifecycle`, „Öffnen der Einstellungen aus dem Menü".

- [ ] **Migration einer vorhandenen `.env`** (Aufgabe 13.2)
  - Schritte: Eine `.env` mit beiden Werten im Repository ablegen und
    `Setup.cmd` doppelklicken. Danach die Diagnose ansehen.
  - Erwartung: Beide Werte stehen in `config.toml`, die Meldung nennt Quelle,
    Ziel und die übernommenen Schlüssel, die `.env` bleibt liegen, und die
    Diagnose warnt, dass sie ab jetzt unwirksam ist.
  - Spec: `tool-configuration`, „Migration einer vorhandenen Konfiguration aus
    dem Repository".

## Betrieb

- [ ] **Aufnahme nach der Verschiebung des Aufnahmekerns** (Aufgabe 2.3)
  - Schritte: Eine vollständige Aufnahme mit Gerätewechsel durchführen und die
    drei entstandenen Dateien mit denen aus dem Stand vor der Aufteilung
    vergleichen.
  - Erwartung: Dieselben drei Dateien mit denselben Namensbestandteilen; keine
    Verhaltensänderung gegenüber dem Stand vor der Aufteilung.
  - Spec: design D1 (Aufteilung ohne Verhaltensänderung).

- [ ] **Vollständige und verworfene Aufnahme** (Aufgabe 2.6)
  - Schritte: Eine Aufnahme mit REC, Gerätewechsel, Mute beider Quellen und STOP
    durchführen; danach eine zweite Aufnahme verwerfen.
  - Erwartung: Dateinamen, Verbleib der Rohspuren und die Kopie im Zielordner
    sind identisch zum Stand vor der Aufteilung. Die verworfene Aufnahme
    hinterlässt nichts im Zielordner.
  - Spec: `audio-recording`.

- [ ] **Aufnahme gegen die gepinnte Umgebung** (Aufgabe 13.3)
  - Schritte: Mit customtkinter 6 und numpy 2 eine vollständige Aufnahme mit
    Gerätewechsel, Mute beider Quellen und STOP durchführen und dabei auf das
    Fenster achten.
  - Erwartung: Mischung und Zielkopie entstehen; Fenstergröße und Skalierung
    sind unverändert gegenüber der alten Fassung, auch auf einem Bildschirm mit
    anderer Skalierung.
  - Spec: design D2; `run-lifecycle`.

- [ ] **Fehlgeschlagene Mischung** (Aufgabe 6.5)
  - Schritte: ffmpeg umbenennen und eine Aufnahme durchführen.
  - Erwartung: Im Zielordner entsteht keine neue Datei, beide Rohspuren liegen
    im Aufnahmeordner, und die Statuszeile nennt ffmpeg als Ursache und den
    Verbleib der Spuren.
  - Spec: `audio-recording`, „Verhalten bei fehlgeschlagener Mischung".

- [ ] **Lebenszyklus von Hand** (Aufgabe 13.4)
  - Schritte: Über die Verknüpfung starten; bei laufender Anwendung ein zweites
    Mal starten; während einer Aufnahme `status` aufrufen; während einer
    Aufnahme `stop` aufrufen; eine weitere Aufnahme über das Fenster-X beenden.
  - Erwartung: Der zweite Start holt das Fenster nach vorn, endet mit Code 3 und
    öffnet kein zweites Fenster. `status` nennt die laufende Aufnahme. `stop`
    und das Fenster-X erzeugen jeweils das fertige Ergebnis, danach läuft kein
    Prozess mehr.
  - Spec: `run-lifecycle`, „Genau eine Instanz je Installation", „Beenden von
    außen", „Sauberes Beenden durch den Benutzer während einer Aufnahme".

- [ ] **Sichtbare Fehler ohne Konsole** (Aufgabe 13.5)
  - Schritte: Nacheinander starten mit fehlender Konfiguration, mit ungültigem
    `recording_dir`, mit nicht beschreibbarem `target_dir` und mit umbenanntem
    ffmpeg.
  - Erwartung: Jedes Mal erscheint ein Fenster mit Ursache und nächstem Schritt,
    der Fehler steht in der Protokolldatei, und der Rückgabewert ist ungleich 0.
    Keine Ausnahmeverfolgung auf dem Bildschirm.
  - Spec: `run-lifecycle`, „Prüfende Startsequenz mit sichtbarem Fehler".

## Fenster-Menü

- [ ] **Alle fünf Einträge des Zahnrad-Menüs** (Aufgabe 13.9)
  - Schritte: Nacheinander „Aktualisieren…", „Diagnose", „Logs öffnen",
    „Einstellungen öffnen" und „Info" auslösen. Danach eine Aufnahme starten und
    das Menü erneut öffnen. Zum Schluss in die Protokolldatei sehen.
  - Erwartung: „Diagnose" erzeugt einen Bericht mit vollständigem Kopf und
    öffnet ihn; „Info" nennt Version, den Pfad zu `LIES-MICH-ZUERST.txt` und den
    Weg zum Entfernen; während der Aufnahme sind „Aktualisieren…", „Diagnose"
    und „Einstellungen öffnen" gesperrt und der Grund ist lesbar; jede Auswahl
    steht im Protokoll.
  - Spec: `run-lifecycle`, „Menü im Anwendungsfenster", „Öffnen der Einstellungen
    aus dem Menü"; `diagnostics`, „Bericht als weitergebbare Textdatei".

## Aktualisieren und Entfernen

- [ ] **Verknüpfung und Deinstallation** (Aufgabe 13.6)
  - Schritte: `shortcut`, `shortcut --status` und `shortcut --remove` ausführen,
    danach `uninstall` und `uninstall --purge`.
  - Erwartung: Jeder Schritt meldet, was er getan hat; die Aufnahmen im
    Aufnahme- und im Zielordner bleiben in allen Schritten unangetastet.
  - Spec: `desktop-shortcut`; `tool-setup`, „Deinstallation".

- [ ] **Release bauen und beide Wege der Aktualisierung** (Aufgabe 13.7)
  - Schritte: `release` bauen, das Archiv in einem leeren Ordner entpacken und
    dort einrichten. Danach eine neue Fassung bauen und beide Wege prüfen: Weg A
    (Archiv über den Ordner entpacken, `Setup.cmd` erneut) und Weg B (Menüpunkt
    „Aktualisieren…").
  - Erwartung: In beiden Fällen bleiben Konfiguration, Protokolle, Zustand und
    die Aufnahmen unberührt, die Arbeitsumgebung wird nicht neu aufgebaut, eine
    Altdatei des vorherigen Release verschwindet, und eine selbst angelegte
    Datei im Ordner bleibt liegen.
  - Spec: `tool-setup`, „Aktualisierung über ein neues Release-ZIP", „Entfernen
    von Altdateien anhand des Release-Verzeichnisses", „Bauen eines
    Release-Pakets".

- [ ] **Fehlgeschlagene Aktualisierung** (Aufgabe 13.8)
  - Schritte: Während Weg B eine Datei des Ordners offen halten, sodass das
    Spiegeln scheitert. Danach denselben Weg mit einer Anwendung versuchen, die
    sich nicht beenden lässt.
  - Erwartung: Der bisherige Stand bleibt vollständig und lauffähig, der Rückweg
    wird genannt, und es bleibt kein halb entpackter Ordner zurück. Im zweiten
    Fall bricht der Helfer **vor** dem ersten Spiegeln ab.
  - Spec: `tool-setup`, „Aktualisierung über ein neues Release-ZIP"; design D17.

## Der eigentliche Beweis

- [ ] **Abnahme des Kollegenwegs** (Aufgabe 13.1a)
  - Schritte: Eine Person ohne Vorkenntnisse bekommt **nur das Release-Archiv**
    — keine mündliche Erklärung, keinen Verweis, keine README. Sie entpackt,
    öffnet `LIES-MICH-ZUERST.txt`, doppelklickt `Setup.cmd`, bestätigt den
    Sicherheitsdialog, beantwortet jede Frage mit der Eingabetaste und startet
    die Anwendung über das Symbol auf dem Desktop.
  - Erwartung: (a) Sie öffnet die Anleitung von sich aus und weiß danach, was
    sie anklicken muss; (b) sie kommt vom Archiv zum laufenden Fenster, ohne ein
    Kommando zu tippen; (c) jede Frage lässt sich mit der Eingabetaste
    beantworten; (d) sie findet das Zahnrad-Menü ohne Hilfe; (e) keine Meldung
    enthält einen Fachbegriff, einen Pfad zum Abschreiben oder eine
    Ausnahmeverfolgung; (f) nach dem ersten Lauf erscheint kein
    Sicherheitsdialog mehr; (g) sie benennt am Ende richtig, wo die Anwendung
    liegt, wie sie einen Fehler meldet und wie sie sie wieder loswird; (h) keine
    Stelle der Anleitung beschreibt einen Ablauf, den es in Backrec nicht gibt
    (Autostart-Ordner, Symbol neben der Uhr).
  - Nacharbeit: Jede Stelle, an der sie stockt, wird notiert und als Zeile in
    `LIES-MICH-ZUERST.txt` nachgebessert — die Grenze von 40 Zeilen gilt, eine
    Ergänzung verdrängt dort eine bestehende Zeile.
  - Spec: `tool-setup`, „Einstiegsanleitung im Wurzelverzeichnis", „Einrichtung
    aus einem entpackten Release-ZIP", „Assistenten-Ausgabe der Einrichtung";
    `desktop-shortcut`, „Automatische Anlage am Ende der Einrichtung".
