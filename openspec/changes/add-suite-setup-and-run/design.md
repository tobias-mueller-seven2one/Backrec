## Context

Siehe [proposal.md](proposal.md) für die Motivation und die Spec-Dateien unter [specs/](specs/) für die Anforderungen: [tool-setup](specs/tool-setup/spec.md), [tool-configuration](specs/tool-configuration/spec.md), [run-lifecycle](specs/run-lifecycle/spec.md), [diagnostics](specs/diagnostics/spec.md), [desktop-shortcut](specs/desktop-shortcut/spec.md), [audio-recording](specs/audio-recording/spec.md).

Die Randbedingungen, die den Entwurf formen:

- Backrec ist heute **eine Datei**: `main.pyw` mit 907 Zeilen, in der Konfiguration (`main.pyw:35-38`), Logging (`main.pyw:25-30`), Aufnahmekern (`main.pyw:203-400`), Mischung (`main.pyw:107-136`), GUI (`main.pyw:430-903`) und Einstieg (`main.pyw:905-907`) zusammenliegen. Es gibt keine Tests, kein Paketlayout, keine `pyproject.toml`.
- Die Anwendung ist **interaktiv und fensterbasiert**: CustomTkinter, always-on-top, feste Breite 280 px (`main.pyw:63`), Fenstergröße per Polling alle 150 ms verteidigt (`main.pyw:548-565`, `main.pyw:866-902`). Es gibt kein Tray, also auch keinen Ort, an dem ein Problemzustand angezeigt werden könnte — der einzige verfügbare Kanal für einen Startfehler ist ein Dialogfenster.
- Sie ist **Windows-gebunden**: pycaw und comtypes für die Erkennung der Standardgeräte (`main.pyw:18-23`, `main.pyw:139-160`), WASAPI-Loopback über `soundcard`, COM-Initialisierung pro Thread (`main.pyw:277-284`, `main.pyw:568-578`).
- Der Aufnahmekern arbeitet mit **Daemon-Threads** (`main.pyw:347`, `main.pyw:526`). Das ist der Grund, weshalb ein Fenster-X während der Aufnahme alles verliert: der Prozess endet, die Threads werden mitgenommen, `_do_stop` (`main.pyw:664-683`) läuft nie.
- Das Repository ist **öffentlich unter MIT** (`LICENSE`, `README.md:7-8`). Weder Code noch Vorlage noch Dokumentation dürfen Firmen-, Benutzer- oder Cloud-Speicherpfade enthalten. Der README bleibt englisch, alle Planungsartefakte sind deutsch; einzige deutsche Datei im Repository selbst ist die Einstiegsanleitung `LIES-MICH-ZUERST.txt` (D22), weil sie sich ausschließlich an die deutschsprachigen Kollegen richtet, die das Release-ZIP bekommen.
- Die Zielgruppe scheut Terminals. Verteilt wird ein **Release-ZIP**, nicht ein Repository: auf einem Kollegenrechner gibt es kein Git, keinen Klon, keinen `git pull` und kein Verständnis für eine Konsole. Alles, was der Kollege tut, ist entpacken, doppelklicken und Enter drücken. Die Kommandozeile bleibt vollständig erhalten, ist aber Werkzeug des Entwicklers und der Fehlersuche.
- Weil das Fenster nur **280 px breit** ist (`main.pyw:63`) und keinen Platz für eine Menüleiste hat, ist der einzige verfügbare Ort für Dauerfunktionen (Aktualisieren, Diagnose, Info) eine einzelne Schaltfläche in der Kopfzeile.
- Vorbild für das Control-Surface ist `claude_litellm_proxy` (`scripts/proxy_control.py`, `src/runtime/service.py`) im Nachbarrepository. Der Code darf **kopiert** werden; ein gemeinsames Paket ist ausdrücklich nicht gewollt, weil jedes Werkzeug der Suite standalone bleibt.
- Die installierte Umgebung (`.venv/pyvenv.cfg:3`) ist Python 3.11.9 aus pyenv-win, während `README.md:22` „Python 3.10+" verspricht und `requirements.txt:1-7` nur `>=`-Untergrenzen führt. Installiert sind customtkinter 6.0.0 gegen `>=5.2.0` und numpy 2.4.6 gegen `>=1.24.0` — zwei Major-Sprünge, die niemand bewusst vollzogen hat.

## Goals / Non-Goals

**Goals:**

- Ein Paketlayout, das Aufnahmekern, GUI und Betriebsschicht trennt, damit Konfiguration, Preflight, Zustand und Diagnose ohne GUI prüfbar sind.
- Ein Control-Surface, dessen Entscheidungen als Dataclasses vorliegen, sodass CLI-Ausgabe und Fehlerdialog dieselben Ergebnisse verschieden darstellen.
- Der Aufnahmekern wird **verschoben, nicht umgeschrieben**. Aufnahmeschleife, Geräteverfolgung, Mischbefehl und verifizierte Kopie bleiben inhaltlich, wie sie sind.
- Ein Fehlschlag ist an genau drei Orten sichtbar: Dialog oder Fenstermeldung, Protokolldatei, Exit-Code.
- Reproduzierbarkeit: gelockte Abhängigkeiten, festgelegte Python-Version, `uv sync --locked` als einziger Weg zur Umgebung.
- Ein Kollege ohne Vorkenntnisse kommt vom ZIP zum laufenden Fenster, ohne ein Kommando zu tippen, ohne Git und ohne einen Pfad abzuschreiben.
- Aktualisieren und Deinstallieren sind für denselben Kollegen genauso einfach wie das Einrichten und verlieren nichts, was ihm gehört.

**Non-Goals:**

- Kein Tray und kein Autostart. Beides ist für ein Werkzeug, das man aufruft, wenn ein Gespräch beginnt, die falsche Bedienoberfläche — und beides ist in der Suite den unbeaufsichtigten Werkzeugen zugeordnet.
- Keine Änderung am Aufnahmeverfahren: gleiche Abtastrate, gleiche Kanäle, gleicher Mischfilter, gleiches Dateinamensschema.
- Keine Konfigurationsoberfläche im Fenster. Konfiguriert wird über die Einrichtung und die Datei.
- Kein Aufräumen des Aufnahmeverzeichnisses. Es wächst weiter mit ~20 MB pro Minute; die Diagnose warnt beim Speicherplatz, löscht aber nichts.
- Keine Testabdeckung für den Aufnahmekern. Er braucht echte Audiogeräte; geprüft werden Betriebsschicht und reine Funktionen.
- Keine plattformübergreifende Fassung. Die Betriebsschicht wird Windows-spezifisch bleiben, weil der Aufnahmekern es ist.
- Kein Installer, keine Signatur, kein `.exe`-Bundle und keine Selbstaktualisierung über das Netz. Verteilt wird ein ZIP, aktualisiert wird mit einem ZIP, und die Versionsprüfung findet gegen die Datei statt, die der Benutzer auswählt.

## Decisions

### D1: Paketlayout `src/backrec/` statt einer Datei

`main.pyw` wird zu einem Paket unter `src/backrec/` mit einem Konsolen- und einem Fenster-Einstiegspunkt in `pyproject.toml`:

```
src/backrec/
  __main__.py         python -m backrec <cmd> - Control-Surface
  cli.py              Argumentzerlegung, Ausgabe, Exit-Codes
  control.py          Entscheidungen als Dataclasses: setup/start/stop/status/doctor/shortcut/uninstall/update/release
  paths.py            MEMOSUITE_HOME, BACKREC_CONFIG, config/logs/state, Repository-Wurzel
  logging_setup.py    Bootstrap-Log vor allem anderen (D4)
  config.py           Laden, Schichten, Expansion, Validierung, Migration (D3)
  wizard.py           Abfrage von data_root, Ableitung, Bestätigung, Schreiben
  preflight.py        Prüfsequenz vor dem Fenster (D5)
  instance.py         PID-Record, create_time-Prüfung, Fenster nach vorn (D6)
  doctor.py           read-only Prüfungen, Stufen, JSON, Textbericht (D12, D21)
  shortcut.py         Desktop-Verknüpfung über COM (D14)
  external.py         ffmpeg finden, Version, winget-Beschaffung (D13)
  version.py          Lesen der VERSION, Vergleich zweier Versionen (D18)
  update.py           ZIP prüfen, Nachbarordner, Umschalten, Altdateien (D17)
  release.py          Release-ZIP und Manifest bauen, Nutzerpfade prüfen (D18)
  app.py              GUI: Fenster, Bedienung, Statuszeile, Fenster-Menü (D20), Abschlusssequenz
  recording.py        MicRecorder, SystemRecorder, Geräteverfolgung (verschoben)
  merge.py            ffmpeg-Aufruf und Ergebnisprüfung (verschoben)
  delivery.py         Übernahme in target_dir, Namenskollision, Verifikation (D8)
  devices.py          pycaw-Abfragen der Standardgeräte (verschoben)
```

Der Schnitt folgt der Frage „braucht das ein Fenster?": alles außer `app.py` läuft ohne GUI und ist damit aus einem Test oder aus `doctor` aufrufbar. `main.pyw` bleibt als dreizeiliger Aufruf von `backrec.app` erhalten, damit der bisherige manuelle Weg (`README.md:37`) nicht unvermittelt bricht.

Verworfen: **`main.pyw` behalten und nur ergänzen** — die Betriebsschicht braucht Konfiguration, Pfade und Zustand, bevor die GUI existiert; in einer Datei, deren Modulebene bereits Verzeichnisse anlegt (`main.pyw:37-38`), lässt sich das nicht ohne Nebenwirkungen unterbringen. Verworfen: **flaches Layout ohne `src/`** — mit `src/` kann kein Import versehentlich das Arbeitsverzeichnis treffen, und genau diese Klasse von Fehlern ist beim Start aus einer Verknüpfung schwer zu finden.

Preis der Entscheidung: der größte Einzelposten des Changes ist eine Verschiebung ohne funktionalen Gewinn, und jede Zeilenangabe aus der Analyse verliert damit ihre Adresse. Deshalb geschieht die Aufteilung in einem eigenen Abschnitt der Aufgabenliste, vor allen Verhaltensänderungen, mit einem Abnahmekriterium „Aufnahme läuft wie vorher".

### D2: uv, `requires-python >= 3.11`, gepinnte Abhängigkeiten

`pyproject.toml` ersetzt `requirements.txt`, `uv.lock` hält die exakten Versionen, `.python-version` trägt `3.11`. Begründung für 3.11 statt der versprochenen 3.10 (`README.md:22`): `tomllib` ist ab 3.11 eingebaut, die Suite legt 3.11 für alle Python-Werkzeuge fest, und die vorhandene Umgebung ist bereits 3.11.9 (`.venv/pyvenv.cfg:3`) — die Zusage „3.10+" ist ungeprüft.

Gepinnt wird der **heute tatsächlich installierte** Stand, nicht die Untergrenze aus `requirements.txt:1-7`:

| Paket | `requirements.txt` | installiert | Bewertung |
| --- | --- | --- | --- |
| customtkinter | `>=5.2.0` | 6.0.0 | Major-Sprung 5→6; die GUI läuft damit im Alltag, aber ungeprüft gegen die Skalierungs- und Geometrieeingriffe (`main.pyw:53-61`, `main.pyw:531-546`) |
| numpy | `>=1.24.0` | 2.4.6 | Major-Sprung 1→2; berührt `np.zeros_like` und `np.abs(...).max()` im Schreibpfad (`main.pyw:318-322`) |
| sounddevice | `>=0.4.6` | – | unkritisch, API stabil |
| soundcard | `>=0.4.2` | – | unkritisch, aber unbeaufsichtigt gepflegt |
| soundfile | `>=0.12.1` | – | unkritisch |
| pycaw | `>=20240210` | – | Datumsversionen, an comtypes gebunden |
| python-dotenv | `>=1.0.0` | – | entfällt mit D3 |

Neu hinzu: `psutil` für `create_time` im PID-Record (D6) und `pywin32` für Verknüpfung und Fenstervordergrund (D6, D14).

Die beiden Major-Sprünge werden nicht als gegeben verbucht, sondern sind eigene Verifikationsaufgaben: eine vollständige Aufnahme mit Gerätewechsel und eine Mischung, jeweils gegen die gepinnte Umgebung.

Verworfen: **`requirements.txt` mit `==` pinnen** — wäre die kleinere Änderung, liefert aber keine transitiven Pins und passt nicht zum suiteweiten `uv sync --locked`. Verworfen: **auf customtkinter 5.2.x zurückpinnen**, um den Major-Sprung zu vermeiden — das Zurückrollen einer Version, die im Alltag läuft, verlagert das Risiko nur und kostet die inzwischen gefixten Skalierungsfehler.

Preis der Entscheidung: `requires-python >= 3.11` schließt Nutzer mit 3.10 aus, obwohl der README ihnen bisher etwas anderes versprach. Das wird im README ausdrücklich als Änderung genannt.

### D3: Konfiguration als TOML in `%LOCALAPPDATA%`, `.env` als Migrationsquelle

Ort: `%LOCALAPPDATA%\MemoSuite\Backrec\config.toml`, verschiebbar über `MEMOSUITE_HOME`, umlenkbar über `BACKREC_CONFIG`. Schlüssel:

```toml
recording_dir = "<Pfad>"   # Rohspuren und Mischung, bewusst außerhalb der Cloud-Synchronisation
target_dir    = "<Pfad>"   # Eingang des Folgetools - Pflichtwert, keine Bequemlichkeit
```

Schichten, schwächste zuerst: Vorgaben im Code → `config.toml` → `BACKREC_*` → CLI-Flags. Die bestehenden Variablen `BACKREC_RECORDING_DIR` und `BACKREC_TARGET_DIR` (`main.pyw:35-36`) behalten damit genau ihre heutige Wirkung, liegen aber jetzt **über** der Datei statt über einem Default. Das ist eine bewusste Umkehr der heutigen Lage: `load_dotenv(..., override=False)` (`main.pyw:16`) lässt die echte Umgebung gewinnen, `README.md:54-60` suggeriert das Gegenteil. Künftig ist die Reihenfolge in beiden Richtungen dieselbe und in der Diagnose ablesbar (Herkunft je Wert).

Ableitung im Wizard: `data_root` mit Vorgabe `%OneDrive%\Aufnahmen`, sonst `%USERPROFILE%\Aufnahmen`; daraus `target_dir = <data_root>\Input` und `recording_dir = %USERPROFILE%\Aufnahmen\Recording` — letzteres ausdrücklich **nicht** unter `data_root`, weil drei WAV pro Aufnahme mit ~20 MB/min nichts in einer Cloud-Synchronisation zu suchen haben. Beide Werte werden bestätigt und dann **ausdrücklich** in die Datei geschrieben; zur Laufzeit wird nichts erneut abgeleitet, damit das Werkzeug standalone bleibt.

Migration: findet `setup` ein `.env` im Repository (`.gitignore:29-30`, `.env.example:1-3`), übernimmt es `BACKREC_RECORDING_DIR` und `BACKREC_TARGET_DIR` einmalig, meldet Quelle, Ziel und Schlüssel und lässt die alte Datei liegen — als unwirksam gekennzeichnet, nicht gelöscht. Löschen einer Datei, die der Benutzer selbst angelegt hat, ist keine Aufgabe eines Einrichtungslaufs.

Pfadexpansion für `%VAR%`, `$VAR` und `~` schließt die heutige Falle: `%USERPROFILE%` in einer `.env` wirkt nicht, weil kein `expandvars` stattfindet — der Wert landet wörtlich in einem `Path` (`main.pyw:35-36`).

Verworfen: **`.env` beibehalten und nur verschieben** — Backrec startet keine Kindprozesse, die Umgebungsvariablen lesen (anders als MemoBoard und der Proxy, wo `.env` deshalb bleibt), und TOML erlaubt Kommentare in der Vorlage. Verworfen: **JSON** — keine Kommentare, also keine erklärende Vorlage. Verworfen: **`.env` beim Migrieren löschen** — ein Einrichtungslauf, der Dateien des Benutzers entfernt, verliert Vertrauen, das er für den Wizard braucht.

Preis der Entscheidung: für einen Übergangszeitraum existieren zwei Dateien, von denen nur eine wirkt. Deshalb meldet die Diagnose eine vorhandene, unwirksame `.env` ausdrücklich.

### D4: Protokollierung vor allem anderen

Der Bootstrap in `logging_setup.py` läuft als erste Anweisung nach den Importen: `RotatingFileHandler` auf `%LOCALAPPDATA%\MemoSuite\Backrec\logs\backrec.log`, 2 MB × 3 Sicherungen, UTF-8, Format wie heute, aber mit Datum (`main.pyw:27-28` hat `datefmt="%H:%M:%S"` — bei einer Datei ohne Datum unbrauchbar). Der Pfad kommt aus `paths.py` und braucht die Konfiguration nicht; nur `MEMOSUITE_HOME` wird gelesen. Ein Fehler beim Anlegen des Handlers wird abgefangen: die Anwendung läuft ohne Protokoll weiter, denn ein nicht beschreibbares Protokollverzeichnis ist kein Grund, eine Aufnahme zu verhindern.

Der Konsolen-Handler bleibt, wird aber nur bei `sys.stderr` mit `isatty()` gesetzt. Unter `pythonw` ist `sys.stderr` `None`; heute schreibt `basicConfig` (`main.pyw:25-30`) dorthin ins Leere, und rund 60 Logaufrufe samt `exc_info=True` (`main.pyw:125`, `main.pyw:342`, `main.pyw:646`, `main.pyw:681`) gehen verloren. Genau diese Aufrufe sind der Gewinn dieses Changes, ohne dass eine Zeile davon geändert werden muss.

Verworfen: **eine zweite `error.log`** wie bei den unbeaufsichtigten Werkzeugen der Suite — die verlangt sie, weil dort niemand zusieht. Backrec hat ein Fenster, das Fehler zeigt; eine zweite Datei wäre ein weiterer Ort, den niemand liest. Die Konvention lässt `error.log` als Möglichkeit, nicht als Pflicht.

Preis der Entscheidung: wer nur die Fehler sehen will, muss in einer gemischten Datei filtern.

### D5: Prüfende Startsequenz mit Fehlerdialog statt Modulebene

Die Verzeichnisanlage verlässt die Modulebene (`main.pyw:37-38`) und wird Teil von `preflight.py`, aufgerufen aus `app.py` **vor** dem Erzeugen des Fensters. Geprüft wird in dieser Reihenfolge, mit Abbruch beim ersten Fehler:

| Prüfung | Fehlerfall | Meldung nennt |
| --- | --- | --- |
| Konfiguration vorhanden | Datei fehlt | `Setup.cmd` als nächsten Schritt |
| Konfiguration parsebar und vollständig | Syntaxfehler, fehlender Pflichtschlüssel | Datei, Stelle, Schlüssel |
| `recording_dir` anlegbar und beschreibbar | ungültiger Pfad, kein Zugriff | Pfad und Systemursache |
| `target_dir` vorhanden und beschreibbar | fehlt, kein Zugriff | Pfad, Unterbrechung der Kette zum Folgetool |
| ffmpeg aufrufbar | nicht gefunden, Aufruf scheitert | Ursache und `Setup.cmd` |

**Umsetzungsnotiz (12.09.2026):** Die Verzeichnisanlage findet an **zwei** Stellen statt, nicht nur im Preflight. Grund: zwei der drei Wege durch den Einrichtungsschritt „Konfiguration" — vorhandene `config.toml` und migrierte `.env` — laufen nicht durch den Wizard, der die Ordner sonst anlegt. Die Diagnose zwei Schritte später meldete dann beide Ordner als Fehler auf einem Rechner, an dem nichts falsch war, und die Einrichtung endete mit Exit 1. `control._configure` legt sie deshalb nach dem Schreiben der Einstellungen an; der Preflight tut es beim Start weiterhin. Gefunden in der Ende-zu-Ende-Abnahme aus einem Release-ZIP.

Der Fehlerkanal ist ein `tkinter.messagebox.showerror` — ein eigenes Fenster, kein CustomTkinter-Dialog, weil die Meldung auch dann erscheinen muss, wenn die Ursache in der Oberfläche selbst liegt. Danach Exit mit Code ungleich 0 und Protokolleintrag. Das ersetzt den heutigen Zustand, in dem eine Exception auf Modulebene unter `pythonw` zu einem Programm führt, das einfach nicht startet.

ffmpeg wird bewusst **vor** dem Fenster geprüft, nicht wie heute erst beim STOP (`main.pyw:124-126`). Ein fehlendes ffmpeg nach einer halbstündigen Besprechung zu erfahren, ist der teuerste Zeitpunkt, den es dafür gibt.

Verworfen: **ffmpeg nur warnen und die Aufnahme zulassen** — die Rohspuren wären da, die Mischung nicht, und nach D8 gelangt dann nichts ins Zielverzeichnis. Eine Aufnahme, deren Ergebnis vorhersehbar nicht zustande kommt, darf nicht beginnen. Verworfen: **Preflight im Fenster als Statuszeile** — bei fehlender Konfiguration gibt es kein sinnvolles Fenster; die Statuszeile ist 280 px breit und trägt keine Ursache.

Preis der Entscheidung: ein Rechner ohne ffmpeg kann Backrec nicht mehr als Rohspur-Aufnahme missbrauchen.

### D6: Single-Instance über PID-Record mit `create_time`

`state\backrec.pid` als JSON mit `pid`, `create_time`, `started`, `repo`. Gültig nur, wenn der Prozess lebt **und** `psutil.Process(pid).create_time()` mit dem Record übereinstimmt **und** `repo` dem aktuellen Repository entspricht. Die `create_time`-Prüfung ist nicht Zierde: Windows vergibt Prozesskennungen wieder, und ein Datensatz, der auf einen fremden Prozess zeigt, würde den Start dauerhaft blockieren. Jede nicht bestandene Prüfung führt zur Übernahme des Records, nie zu einer Blockade.

Bei gültigem Record bringt der zweite Start das bestehende Fenster nach vorn: Fenstersuche über `EnumWindows` nach der Prozesskennung des Records, dann `ShowWindow` und `SetForegroundWindow` (pywin32). Gelingt das nicht — Windows verweigert den Vordergrundwechsel unter Umständen —, bleibt eine Meldung. In beiden Fällen: Exit-Code 3, Protokolleintrag, laufende Instanz unberührt.

**Umsetzungsnotiz (12.09.2026):** Der Erfolg des Vordergrundwechsels wird an `ShowWindow` und `BringWindowToTop` gemessen, nicht an `SetForegroundWindow`. Windows verweigert Letzteres immer dann, wenn der rufende Prozess nicht der Vordergrundprozess ist — und das ist hier der Regelfall, weil der Rufer eine gerade doppelgeklickte Verknüpfung ist. Gemessen an diesem Aufruf allein lautete die Antwort in der Abnahme jedes Mal „nein", und vor einem Fenster, das nachweislich sichtbar oben steht (es ist always-on-top), erschien ein Dialog. Nur wenn kein Fenster gefunden wird oder auch die ersten beiden Aufrufe scheitern, bleibt es bei der Meldung. Exit-Code 3 und Protokolleintrag sind in beiden Fällen unverändert.

Verworfen: **Named Mutex** — die kürzeste Lösung für Einmaligkeit, aber sie trägt keine Information: keine Prozesskennung, kein Repository, kein Startzeitpunkt, und damit weder eine Fenstersuche noch eine brauchbare Statusauskunft. Verworfen: **Sperrdatei ohne `create_time`** — genau die Blockade, die nach einem Absturz bleibt. Verworfen: **Loopback-Port als Sperre** — Backrec lauscht auf nichts, ein Port allein zu diesem Zweck wäre ein neuer Angriffspunkt und ein neuer Konfigurationswert.

Preis der Entscheidung: zwei zusätzliche Abhängigkeiten (`psutil`, `pywin32`) für ein Verhalten, das der Benutzer im Erfolgsfall gar nicht bemerkt.

### D7: Fenster-X führt die Abschlusssequenz aus, ohne Rückfrage

`WM_DELETE_WINDOW` wird auf einen Handler gelegt. Läuft keine Aufnahme, endet die Anwendung sofort. Läuft eine Aufnahme, führt der Handler dieselbe Sequenz aus wie der STOP-Knopf (`main.pyw:664-683`): Threads beenden, Dateien schließen, mischen, übernehmen — und beendet danach. Während der Sequenz zeigt das Fenster den Fortschritt wie heute (`main.pyw:592-604`), ein zweites Schließen wird verworfen, das Fenster bleibt bis zum Abschluss stehen.

**Kein Rückfragedialog.** Die Alternative wäre eine Frage „abschließen oder verwerfen?", aber das Fenster hat für das Verwerfen bereits einen eigenen, zweistufig gesicherten Knopf (`main.pyw:762-782`). Wer verwerfen will, drückt ihn; wer das Fenster schließt, will nicht seine Aufnahme wegwerfen. Ein Dialog, der beim Beenden nach dem Offensichtlichen fragt, wird nach dem dritten Mal ungelesen bestätigt.

Der Aufnahmekern bleibt bei Daemon-Threads: sie werden vom Handler ordentlich beendet (`main.pyw:351-360` wartet mit Frist), und `daemon=True` bleibt das Netz für den Fall, dass der Prozess doch hart endet.

Verworfen: **Rückfrage mit drei Wegen** (abschließen, verwerfen, abbrechen) — mehr Bedienfläche für den seltenen Fall, und „abbrechen" bedeutet „Fenster bleibt offen", was ein geschlossenes Fenster nicht mehr hergibt. Verworfen: **Threads auf `daemon=False`** — dann hängt ein hart beendeter Prozess an einem nicht endenden Aufnahmefaden, und der Benutzer hat ein Fenster, das nicht verschwindet.

Preis der Entscheidung: das Schließen des Fensters dauert bei einer laufenden Aufnahme so lange wie eine Mischung, ohne dass der Benutzer es vorher gewählt hat. Deshalb der sichtbare Fortschritt.

### D8: Bei fehlgeschlagener Mischung bleibt alles im Aufnahmeverzeichnis

Heute kopiert `_fallback_copy_raw` (`main.pyw:719-728`) beide Rohspuren einzeln in das Zielverzeichnis. Für Backrec allein ist das großzügig — nichts geht verloren. Für die Kette ist es ein Bruch des Schnittstellenvertrags: AMD-Transcription liest jede Datei im Eingangsordner und transkribiert damit **dasselbe Gespräch zweimal**, einmal aus Mikrofonsicht und einmal aus Systemsicht, und AutoMemo erzeugt daraus zwei Auswertungen desselben Termins. Der Fehler wandert also aus Backrec heraus und wird an einer Stelle sichtbar, an der niemand mehr auf ffmpeg kommt.

Gewählt: **Rohspuren bleiben in `recording_dir`, in `target_dir` landet nichts.** Der Fehlschlag erscheint in der Statuszeile des Fensters mit Ursache, geht mit `exc_info` ins Protokoll und nennt das Aufnahmeverzeichnis als Verbleib. Der Fehler bleibt damit dort, wo er entstanden ist, und ist behebbar: ffmpeg installieren, Mischung nachholen.

| Weg | Nichts geht verloren | Folgetool bleibt korrekt | Fehler sichtbar | Aufwand |
| --- | --- | --- | --- | --- |
| Rohspuren einzeln kopieren (heute) | ja | **nein** — doppelte Transkription | nur im unsichtbaren Log | – |
| Rohspuren in `<target_dir>\..\Error` | ja | ja | mittelbar | Ordner und Konvention nötig |
| Rohspuren mit ignoriertem Präfix kopieren | ja | nur mit Absprache im Folgetool | mittelbar | Kopplung zweier Repos |
| **Rohspuren bleiben, nichts wird kopiert** | ja | ja | Fenster, Protokoll, Exit | keiner |

Verworfen: **`Error`-Unterordner unterhalb von `data_root`** — Backrec müsste einen dritten Pfad kennen, den die Konvention den nachgelagerten Werkzeugen zuordnet, und der Benutzer müsste an einem weiteren Ort nachsehen. Verworfen: **Präfix, das AMD-Transcription ignoriert** — das ist genau die Laufzeitkopplung zwischen zwei standalone-Werkzeugen, die die Konvention ausschließt: eine Absprache, die man in zwei Repositorys gleichzeitig ändern müsste.

Preis der Entscheidung: wer den Fehler übersieht, findet seine Aufnahme nicht an der gewohnten Stelle. Abgefedert durch die Meldung im Fenster, die den Verbleib nennt, und dadurch, dass D5 den häufigsten Grund (fehlendes ffmpeg) schon vor der Aufnahme abfängt.

### D9: Control-Surface als ein Modul, GUI und CLI als zwei Gesichter

`control.py` liefert je Kommando eine Dataclass — etwa `SetupResult`, `PreflightResult`, `DoctorReport`, `InstanceState`, `ShortcutStatus`, `UpdatePlan`, `ReleaseResult` — mit Feldern für Stufe, Ursache und nächsten Schritt. `cli.py` schreibt sie in eine Konsole nach den Assistenten-Regeln (D19), `app.py` in einen Dialog, in die Statuszeile oder in das Fenster-Menü (D20). Damit gibt es genau eine Stelle, die entscheidet, und zwei, die darstellen — das Muster des Proxy (`scripts/proxy_control.py`), von dem der Code kopiert werden darf. Dass `update` und `doctor` aus dem Fenster heraus dieselben Funktionen aufrufen wie aus der Konsole, ist der Grund, weshalb das Fenster-Menü keine eigene Ablauflogik braucht.

Der Start ist `pythonw.exe` aus `.venv\Scripts\` mit **absolutem Pfad**, abgekoppelt gestartet. Heute läuft `start "" pythonw main.pyw` nach `call .venv\Scripts\activate` (`Start_Recorder.bat:19`, `Start_Recorder.bat:28`), also über den Suchpfad; welcher Interpreter das trifft, hängt an der Reihenfolge in `PATH`.

Verworfen: **`[project.gui-scripts]`** mit einer erzeugten `backrec.exe` — funktioniert, verlangt aber, dass die Verknüpfung auf eine Datei in `.venv\Scripts\` zeigt, die bei jedem `uv sync` neu entsteht. Der direkte Weg über `pythonw.exe` mit `-m backrec` ist eine Abhängigkeit weniger.

**Umsetzungsnotiz (12.09.2026):** `pyproject.toml` führte zwischenzeitlich einen `[project.gui-scripts]`-Eintrag `backrec-gui`. Er ist wieder entfernt, weil ihn nichts benutzt und sein Kommentar dieser Entscheidung widersprach. Der Konsolen-Einstiegspunkt `[project.scripts] backrec` bleibt: `Setup.cmd` und `Start.cmd` rufen ihn auf, die Verknüpfung dagegen `pythonw.exe -m backrec`.

Preis der Entscheidung: der Startpfad ist an das Layout von `.venv` gebunden, und ein gelöschtes `.venv` macht die Verknüpfung unbrauchbar. Die Diagnose prüft deshalb das Ziel der Verknüpfung.

### D10: Stop von außen über eine Sentinel-Datei

Windows-Konsolensignale erreichen einen `pythonw`-Prozess nicht. `stop` legt daher `state\stop.request` ab; die GUI prüft die Datei in ihrer bestehenden Schleife (`main.pyw:866-902`, alle 150 ms) und führt dann die Abschlusssequenz aus D7 aus. Nach einer Frist von 30 s — genug für Threadende, Mischung und Kopie einer langen Aufnahme — folgt die harte Beendigung des Prozessbaums. Der Erfolg wird an lebenden Prozessen gemessen, nicht am geschriebenen Sentinel. Danach wird der PID-Record entfernt.

Die 150-ms-Schleife wird dafür nicht verändert, nur erweitert. Sie existiert bereits, um die Fenstergröße zu verteidigen (`main.pyw:548-565`) — sie ist damit der einzige Taktgeber, den die Anwendung ohnehin hat.

Verworfen: **`taskkill` allein** — verliert bei laufender Aufnahme genau das, was D7 rettet. Verworfen: **ein Loopback-Port für Steuerbefehle** — ein Netzwerkdienst in einem Werkzeug, das keinen braucht. Verworfen: **Windows-Nachricht an das Fenster** — würde funktionieren, verlangt aber die Fenstersuche aus D6 auch für den Stopp und scheitert, sobald das Fenster noch nicht existiert.

Preis der Entscheidung: das Beenden dauert bis zu 150 ms länger als nötig, und ein liegengebliebener Sentinel würde einen späteren Start sofort wieder beenden — deshalb löscht der Preflight einen vorgefundenen Sentinel vor dem Fensteraufbau.

### D11: `Start_Recorder.bat` bleibt als Hinweis, statt zu verschwinden

Die Datei wird auf `echo`, den Verweis auf `Setup.cmd` und `Start.cmd`, `pause` und `exit /b 1` reduziert. Sie ist der Weg, den `README.md:29` bewirbt, und sie steht in der Verlaufsgeschichte des öffentlichen Repositorys; ein Doppelklick auf eine Datei, die es nicht mehr gibt, erklärt nichts. Der Exit-Code 1 verhindert, dass ein Wrapper oder eine alte Verknüpfung den Aufruf für erfolgreich hält.

Verworfen: **die Datei löschen** — sauberer im Verzeichnis, aber der Benutzer mit der alten Verknüpfung auf dem Desktop bekommt „Datei nicht gefunden" statt einer Anleitung. Verworfen: **auf `Start.cmd` weiterleiten** — dann startet die Anwendung auch ohne Einrichtung, und der alte Name überlebt still weiter, statt abzulösen.

Preis der Entscheidung: eine Datei mehr im Repo-Wurzelverzeichnis, die nichts tut, in einem Wurzelverzeichnis, das nach D16 sonst nur noch vier Einträge führt. Sie darf mit dem nächsten größeren Schnitt verschwinden. Suiteweit ist der Übergang alter Skripte damit uneinheitlich — AMD-Transcription und AutoMemo löschen ihre `setup.bat`/`start.bat` ersatzlos —; die Konvention führt das als offene Abweichung, und dieser Change hält an D11 fest, bis eine einheitliche Linie entschieden ist (siehe Open Questions).

### D12: Diagnose als reine Beobachtung, Audiogeräte ohne Stream

`doctor.py` liefert eine Liste von Befunden `(id, category, level, cause, next_step)`. Die Backrec-eigenen Prüfungen:

| Prüfung | Weg | Stufe im Fehlerfall |
| --- | --- | --- |
| ffmpeg im Suchpfad | `shutil.which` | Fehler |
| ffmpeg ausführbar | `ffmpeg -version`, Frist 5 s | Fehler, unterschieden von „nicht gefunden" |
| Standard-Aufnahmegerät | pycaw, wie `main.pyw:139-160` | Fehler |
| Standard-Wiedergabegerät | pycaw, wie die Loopback-Auswahl | Fehler |
| Geräteerkennung selbst verfügbar | Importprüfung wie `main.pyw:18-23` | eigener Befund, nicht „kein Gerät" |
| `recording_dir`, `target_dir` beschreibbar | Öffnen und Verwerfen einer temporären Datei im Zielordner | Fehler |
| Restplatz je Ablageort | `shutil.disk_usage`, Reserve 2 GB | Warnung, mit Angabe ~20 MB/min |
| `recording_dir` in Cloud-Synchronisation | Präfixvergleich mit `%OneDrive%` | Warnung |
| unwirksame `.env` im Repository | Existenzprüfung | Warnung |
| verwaister PID-Record, Sentinel | Prüfung wie D6 | Warnung |

Die Audiogeräte werden **nur benannt**, es wird kein Stream geöffnet. Ein Öffnen wäre die aussagekräftigere Prüfung, ist aber kein Lesezugriff: es belegt ein Gerät, das gerade in einer Besprechung benutzt wird. Read-only heißt hier auch: keine Nebenwirkung auf Geräte.

Verworfen: **kurze Probeaufnahme als Prüfung** — beweist mehr, kann aber eine laufende Besprechung stören. Verworfen: **Gerätezählung über `sounddevice.query_devices()`** — nennt alle Geräte, aber nicht das Standardgerät, und genau das benutzt die Aufnahme.

Preis der Entscheidung: die Diagnose kann „Gerät vorhanden" melden und die Aufnahme scheitert trotzdem, etwa weil ein anderes Programm exklusiv zugreift. Der Fall bleibt dem Protokoll überlassen.

**Umsetzungsnotiz (12.09.2026):** Anders als das Nachbarwerkzeug räumt Backrecs Diagnose ihre eigenen Berichte **nicht** ab einer Schwelle weg, sondern warnt nur. Das Löschen eines Berichts wäre eine Veränderung, und die Spec `diagnostics` verlangt ausdrücklich, dass außer Bericht und Protokolleintrag keine Schreibwirkung entsteht. Ein noch nicht angelegtes Protokollverzeichnis ist aus demselben Grund eine Warnung und kein Fehler: vor dem ersten Lauf gibt es den Ordner schlicht nicht, und ihn als Fehler zu melden ließe eine frische Einrichtung in dem einen Moment kaputt aussehen, in dem jemand genau hinsieht.

### D13: ffmpeg über `winget --scope user`, mit Anleitung als Rückfallweg

`winget install Gyan.FFmpeg -e --scope user --accept-package-agreements --accept-source-agreements`. Kein Administrator, keine eigene Auslieferung. Danach prüft die Einrichtung erneut mit `shutil.which` und einem Versionsaufruf, weil eine erfolgreiche Installation den `PATH` der laufenden Sitzung nicht zwingend erreicht — in diesem Fall nennt die Meldung, dass eine neue Konsole oder eine Neuanmeldung nötig ist. Scheitert die Installation, folgt eine Anleitung samt Hinweis, dass Fremd-Installer eine SmartScreen-Warnung auslösen können, und die Einrichtung endet mit Exit-Code ungleich 0.

Verworfen: **`imageio-ffmpeg` als Python-Abhängigkeit** — bringt eine ffmpeg-Binärdatei ins Wheel und wäre der bequemste Weg, koppelt aber die Version des Mischwerkzeugs an ein Python-Paket und weicht von der suiteweiten Festlegung ab, dass Fremdprogramme über `winget --scope user` kommen. Verworfen: **ffmpeg ins Repository legen** — ein öffentliches MIT-Repository mit einer mitgelieferten GPL-Binärdatei ist eine lizenzrechtliche Aussage, die niemand treffen will.

Preis der Entscheidung: die Einrichtung hängt von `winget` und der Verfügbarkeit des Pakets ab. Deshalb der dokumentierte manuelle Weg.

### D14: Desktop-Verknüpfung über COM, Ziel ist `pythonw.exe`

`shortcut.py` erzeugt `<Desktop>\Backrec.lnk` über `WScript.Shell` (pywin32) mit `TargetPath = <repo>\.venv\Scripts\pythonw.exe`, `Arguments = -m backrec`, `WorkingDirectory = <repo>`, Symbol aus dem Repository. Der Desktop-Ordner kommt aus `HKCU\...\Shell Folders\Desktop`, mit `%USERPROFILE%\Desktop` als Rückfallweg — nur die Registry kennt ein umgeleitetes Profil. Zurückgelesen wird über denselben COM-Weg, weil nur Windows sagen kann, worauf eine `.lnk` inzwischen zeigt.

Ein Startmenü-Eintrag entsteht nicht. Ein Autostart-Eintrag entsteht nicht — Backrec ist das interaktive Werkzeug der Suite, und ein Programm, das sich selbst in den Anmeldevorgang einträgt, ist genau das Verhalten, auf das Endpunktschutz reagiert (im Nachbarrepository hat Bitdefender das blockiert). Für Backrec entfällt die Frage, weil es beim Anmelden nichts zu tun hat.

Genau deshalb darf die Einrichtung die Verknüpfung **selbst** anlegen, und tut das nach einer Frage mit Enter als Zustimmung (D19). Die anderen Werkzeuge der Suite verlangen an dieser Stelle einen manuellen Handgriff des Benutzers, weil ihr Ziel der Autostart-Ordner ist; Backrec hat diesen Grund nicht und erspart dem Kollegen den einzigen Schritt des gesamten Ablaufs, der ohne Erklärung nicht funktioniert.

**Umsetzungsnotiz (12.09.2026), zwei Punkte:**

1. **Kein Symbol im Repository.** Das Repository führt keine `.ico`-Datei, und eine Binärdatei in ein öffentliches Repository zu legen, damit ein Symbol hübscher aussieht, ist kein hinreichender Grund. `shortcut.icon_location()` nimmt `Backrec.ico` oder `assets\Backrec.ico`, wenn eine davon auftaucht; sonst bleibt `IconLocation` ungesetzt und die Verknüpfung trägt das Symbol ihres Ziels.
2. **Eine Verknüpfung auf den abgelösten Startweg gilt als neu aufzubauen.** In der Abnahme lag auf dem Desktop noch eine Verknüpfung auf `Start_Recorder.bat`. Sie erfüllte jede Bedingung — vorhanden, lesbar, Arbeitsordner dieses Repositorys, Ziel existiert — und die Einrichtung meldete den Schritt als erledigt. Der Kollege hätte ein Symbol behalten, das nach D11 nur noch einen Hinweis ausgibt. `ShortcutStatus.installed` verlangt deshalb zusätzlich, dass das Ziel der aktuelle Startweg ist; die Diagnose meldet den Fall als Warnung.

Verworfen: **`.lnk` im Repository und Kopieren von Hand**, wie es der Autostart der anderen Werkzeuge verlangt — dort ist der Handgriff nötig, weil das Ziel der Startup-Ordner ist. Der Desktop ist kein Persistenzmechanismus; dort darf ein Programm ein Symbol ablegen. Verworfen: **`.bat` als Verknüpfungsziel** — würde ein Konsolenfenster aufblitzen lassen.

Preis der Entscheidung: absolute Pfade in der Verknüpfung. Wird beim Aufbau benannt, die Statusauskunft nennt ein abweichendes Arbeitsverzeichnis, und die Diagnose prüft, ob das Ziel noch existiert.

### D15: Warum `audio-recording` eine eigene Fähigkeit ist

Die Konvention nennt fünf Fähigkeiten. Der Merge-Fallback (D8) passt in keine davon: er beschreibt nicht, wann ein Prozess endet, sondern was danach im Zielverzeichnis liegt — ein Vertrag mit dem Folgetool, unabhängig davon, ob der Abschluss durch STOP, durch `stop` oder durch das Fenster-X angestoßen wurde. Der Schnitt lautet deshalb: `run-lifecycle` beantwortet „wann und wie endet der Prozess", `audio-recording` beantwortet „welche Dateien existieren danach und wo". Die Abschlusssequenz erscheint in beiden Specs, aber unter verschiedenen Fragen — in `run-lifecycle` als Anforderung, dass Schließen nichts verliert, in `audio-recording` als Anforderung, dass genau eine gemischte Datei ankommt.

Verworfen: **alles in `run-lifecycle`** — dann steht der Schnittstellenvertrag zum Folgetool in einer Fähigkeit, die suiteweit Start und Stopp beschreibt, und wäre beim Vergleich der fünf Repos die eine Spec, die aus dem Rahmen fällt.

Preis der Entscheidung: eine Fähigkeit mehr als die Konvention vorsieht, und die Suite-Vergleichbarkeit hat für Backrec einen zusätzlichen Eintrag. Begründet, weil Backrec das einzige Werkzeug ist, das Nutzdaten **erzeugt**.

### D16: Nur `Setup.cmd`, `Start.cmd`, `VERSION` und `LIES-MICH-ZUERST.txt` im Wurzelverzeichnis

Im Repo-Root liegen genau zwei Dateien, die einen Vorgang starten, und zwei Textdateien, die nur gelesen werden: die Version (D18) und die Einstiegsanleitung (D22). Die beiden Textdateien konkurrieren nicht mit den beiden Kommandodateien, weil ein Doppelklick auf sie nichts tut, als einen Editor zu öffnen — das ist bei `LIES-MICH-ZUERST.txt` sogar der gewünschte Ausgang. `Stop.cmd` und `Update.cmd` entstehen nicht, obwohl die erste Fassung dieses Changes sie vorsah. Der Grund ist der Adressat: wer eine Datei im Explorer sieht, probiert sie irgendwann aus. `Stop.cmd` ist für Backrec sinnlos — die Anwendung wird über das Fenster-X beendet, und ein Doppelklick auf `Stop.cmd` bei nicht laufender Anwendung erzeugt eine Meldung, die nur verwirrt. `Update.cmd` wäre schlimmer: es würde einen Ablauf anbieten, der ohne ein neues ZIP überhaupt nichts tun kann.

Die Kommandos bleiben vollständig: `stop`, `update`, `uninstall`, `doctor`, `release` sind über `python -m backrec <cmd>` erreichbar und in der Entwickler-Dokumentation beschrieben. Ein Kollege braucht sie nie: Beenden ist das X, Aktualisieren ist `Setup.cmd` nach dem Entpacken oder der Menüpunkt, Diagnose und Info liegen im Fenster-Menü (D20), Deinstallieren ist das Löschen des Ordners (Abschnitt „Uninstall" der Konvention) — und genau diese vier Wege stehen in `LIES-MICH-ZUERST.txt` (D22), sodass er im Wurzelverzeichnis nur eine Datei öffnen und eine anklicken muss.

Verworfen: **`Stop.cmd` und `Update.cmd` als dünne Wrapper behalten**, wie in der ersten Fassung — sie kosten nichts in der Umsetzung, aber jede zusätzliche Datei im Wurzelverzeichnis ist eine Frage, die ein Kollege stellt, und das Wurzelverzeichnis ist die erste Oberfläche, die er sieht. Verworfen: **einen einzigen `Backrec.cmd`-Starter mit Menü** — ein Konsolenmenü ist genau die Konsole, die die Zielgruppe abschreckt, und der Einstiegspunkt darf keine zwei Fragen stellen, bevor etwas passiert.

Preis der Entscheidung: wer die Anwendung ohne Fenster beenden will — etwa weil sie hängt —, muss die Kommandozeile bemühen oder den Task-Manager. Das wird im Entwickler-Teil des README genannt und ist für die Zielgruppe kein Verlust, weil sie den Weg über `Stop.cmd` ohnehin nicht gefunden hätte.

### D17: Update per ZIP über einen Nachbarordner, mit Umschalten und Manifest

Es gibt zwei Wege, beide ohne Git.

**Weg A (ohne laufende Anwendung):** Der Kollege entpackt das neue ZIP über den vorhandenen Ordner und bestätigt das Überschreiben, dann doppelklickt er `Setup.cmd`. Die Einrichtung vergleicht die `VERSION` im Ordner mit der Kopie unter `state\`, erkennt den Wechsel, beendet eine laufende Instanz, führt `uv sync --locked` aus, räumt Altdateien anhand der Manifeste auf und schließt mit Diagnose und Startangebot. Das ist derselbe Ablauf wie eine Ersteinrichtung, nur mit anderen Meldungen — ein Update ist nach D-Logik dieses Changes kein eigener Mechanismus, sondern ein idempotenter zweiter Lauf mit erkanntem Versionswechsel.

**Weg B (aus dem Fenster, D20):** „Aktualisieren…" öffnet eine Dateiauswahl, prüft Toolname und Version aus `release-manifest.json`, zeigt „von 2026.09.1 auf 2026.10.1" und fragt einmal. Danach entpackt die Anwendung das ZIP **nicht** über sich selbst, sondern in den Nachbarordner `<repo>.new-<version>`, beendet sich, und ein abgekoppelter Aktualisierungsprozess **aus dem Nachbarordner** wartet auf das Ende der alten Instanz, benennt `<repo>` in `<repo>.old-<altversion>` um, benennt den Nachbarordner in `<repo>` um, verschiebt `.venv` aus dem alten in den neuen Ordner, führt `uv sync --locked` aus und startet die Anwendung. Der Aktualisierungsprozess läuft aus dem Nachbarordner, weil kein Prozess den Ordner ersetzen kann, aus dem sein eigener Code geladen ist. Scheitert ein Schritt vor dem Umbenennen, bleibt der alte Ordner unberührt lauffähig; scheitert `uv sync` danach, bleibt `<repo>.old-<altversion>` als Rückweg stehen und wird in der Zusammenfassung genannt.

**Umsetzungsnotiz (12.09.2026) — Weg B folgt der Konvention, nicht diesem Absatz.** Abschnitt 9 der `SETUP-RUN-KONVENTION.md` legt nach dem Review der fünf Changes eine suiteweit gleiche Mechanik fest: ZIP in einen **Staging-Ordner** `<repo>.update` neben dem Repository entpacken, jede Datei gegen ihren Hash im Manifest prüfen, die Anwendung stoppen, die Dateien **per Manifest in den bestehenden Ordner spiegeln**, `.venv` liegen lassen und mit `uv sync --locked` nachziehen, und das Ganze von einem abgekoppelten PowerShell-5.1-Helfer außerhalb des Ordners (`scripts\win\apply-update.ps1`) ausführen lassen. Umgesetzt ist diese Fassung.

Die Gründe gelten für Backrec unverändert und teilweise stärker als anderswo: Der Pfad des Ordners steckt in der Desktop-Verknüpfung (D14) — ein Ordner, der seinen Namen behält, übersteht die Aktualisierung, ohne dass die Verknüpfung neu aufgebaut werden muss. Es wird kein Ordner umbenannt, der noch ein offenes Handle tragen könnte, also entfällt der Fehlerfall aus dem Risikoabschnitt weitgehend. Und `.venv` muss nicht verschoben werden, weil es sich nicht bewegt.

**Umsetzungsnotiz (12.09.2026) — drei Fehler, die erst der echte Lauf zeigte.** Weg B wurde an einer Kopie unter `%TEMP%` von Ende zu Ende durchgespielt (ZIP bauen, einspielen, Neustart). Dabei fiel dreierlei auf, jedes für sich still:

1. **Das Manifest wird mitgespiegelt.** Die Dateiliste führt sich nicht selbst auf, also blieb beim Spiegeln „nach Liste" die Liste der **vorherigen** Fassung im Ordner liegen. Die Einrichtung unmittelbar danach vergleicht die Kopie unter `state\` gegen die Liste im Ordner — und hielt damit jede Datei, die neu in dieser Fassung war, für eine Altlast der vorherigen und löschte sie, Sekunden nach dem Einspielen. Der Helfer und `update.mirror` kopieren die Liste jetzt ausdrücklich mit.
2. **Der Helfer ruft `Setup.cmd` über den vollen Pfad auf.** `Push-Location` setzt den Ort der PowerShell-Sitzung, nicht das Arbeitsverzeichnis, das ein Kindprozess erbt; `cmd /c Setup.cmd` suchte die Datei deshalb dort, wo Backrec gestartet worden war. Das Aktualisieren endete mit gespiegelten Dateien, ohne nachgezogene Umgebung und ohne Neustart.
3. **Der Helfer wartet nur auf die Einrichtung, nicht auf Backrec.** `Start-Process -Wait` wartet auf den Vorgang *und alle seine Nachkommen* — und der letzte Schritt der Einrichtung startet Backrec. Das Fenster des Helfers blieb offen, solange Backrec lief. Gewartet wird jetzt über `WaitForExit()`; das Abfragen von `.Handle` davor ist nötig, weil `.ExitCode` sonst leer bleibt und die Abschlussmeldung nach jedem gelungenen Lauf „noch etwas offen" sagte.

Dazu die Einrichtung selbst: ein `--start`, das ausdrücklich verlangt wurde, wird jetzt auch dann ausgeführt, wenn die Diagnose einen offenen Punkt meldet. Andernfalls nimmt eine einzelne Warnung einem Kollegen nach dem Aktualisieren das Fenster weg, ohne ihm zu sagen, warum.

Was dadurch entfällt: `<repo>.old-<version>` entsteht nicht mehr, und damit auch die offene Frage, wann er verschwindet. Der Rückweg ist stattdessen der Staging-Ordner, der bis zum letzten Schritt stehen bleibt. Die Diagnose meldet einen liegengebliebenen `<repo>.update` — und weiterhin auch einen `<repo>.old-*` aus einer früheren Fassung — als Warnung mit dem Weg zum Aufräumen.

`.venv` wird **verschoben, nicht neu gebaut**: Ein Neuaufbau lädt Hunderte Megabyte erneut und dauert Minuten, obwohl sich in der Regel keine Abhängigkeit ändert. `uv sync --locked` bringt die verschobene Umgebung auf den Stand der neuen Lockdatei und ist bei unveränderter Lockdatei ein Nullvorgang. Weil `.venv` absolute Pfade in `pyvenv.cfg` und den Startskripten führt und der Zielordner denselben Namen trägt wie vorher, bleiben diese Pfade gültig.

**Manifest:** Das ZIP enthält `release-manifest.json` mit Toolname, Version, Datum und Dateiliste samt Hashes. Nach einer erfolgreichen Einrichtung legt das Setup eine Kopie unter `state\installed-manifest.json` ab — bewusst **außerhalb** des Repositorys, weil ein Entpacken über den Ordner jede Kopie im Ordner überschreiben würde und der Vergleich dann nichts mehr hergäbe. Beim nächsten Lauf ist die Differenz „im alten Manifest, nicht im neuen" die Liste der zu löschenden Altdateien. Gelöscht wird nur, was in der alten Liste steht; `.venv`, `logs`, `*.lnk`, `config*` und alles, was der Benutzer selbst angelegt hat, kommen dort nie vor und bleiben unangetastet.

Verworfen: **`git pull` auch für Kollegen** — verlangt Git, ein Konto, Zugriff auf ein privates Repository und eine Konsole; alle vier fallen für die Zielgruppe aus. Bleibt als `update --git` für den Entwicklerweg erhalten. Verworfen: **ZIP direkt über den laufenden Ordner entpacken** — eine abgebrochene Entpackung hinterlässt einen halben Ordner, und zwar genau den, aus dem die Anwendung startet. Verworfen: **den kompletten Ordner löschen und neu entpacken** — nimmt `.venv` mit und macht aus einem Update einen Neuaufbau von Minuten. Verworfen: **eine Selbstaktualisierung über das Netz** (Versionsprüfung gegen eine Freigabe) — verlangt einen erreichbaren Ort, Berechtigungen und eine Fehlerbehandlung für den Offline-Fall, für einen Vorgang, der ein- bis zweimal im Jahr stattfindet.

Preis der Entscheidung: während des Umschaltens existieren der Ordner zweimal (ohne `.venv`, also wenige Megabyte), und es bleibt ein `<repo>.old-<version>` stehen, bis der nächste erfolgreiche Start ihn entfernt. Ein Aktualisierungsprozess, der mitten im Umbenennen abstürzt, hinterlässt einen Zustand, den nur ein Mensch auflösen kann — deshalb protokolliert jeder Schritt seinen Namen, und die Zusammenfassung nennt beide Ordner.

### D18: `VERSION` als einzige Versionsquelle, `release` baut das ZIP

Die Version steht in **einer** Datei: `VERSION` im Wurzelverzeichnis, eine Zeile im Format `JJJJ.MM.N`. `pyproject.toml` führt keine eigene Versionszeile, sondern `dynamic = ["version"]` und liest die Datei über das Build-Backend. Die Richtung ist bewusst so und nicht umgekehrt: `Setup.cmd` und das Bootstrap-Skript müssen die Version lesen können, **bevor** eine Python-Umgebung existiert — beim ersten Lauf aus einem frisch entpackten ZIP gibt es weder `.venv` noch uv. Eine Zeile aus einer Textdatei liest jede Batch- und PowerShell-Zeile; ein Wert aus `pyproject.toml` verlangt einen TOML-Leser und damit genau die Laufzeit, die noch nicht da ist.

`release` führt aus: Version setzen oder aus `VERSION` übernehmen, Arbeitsbaum auf Sauberkeit prüfen, versionierte Dateien gegen Nutzerpfade prüfen (Muster `C:\Users\`, `OneDrive -`, Firmenname), `uv.lock` gegen `pyproject.toml` prüfen, `LIES-MICH-ZUERST.txt` gegen die Formregeln aus D22 prüfen, ZIP mit dem Ordner `Backrec\` als oberster Ebene bauen, `VERSION` und `release-manifest.json` hineinlegen, das Ergebnis nach `%LOCALAPPDATA%\MemoSuite\releases\` schreiben und den Pfad ausgeben. Ausgeschlossen sind `.git`, `.venv`, `__pycache__`, `*.pyc`, `logs`, `.env`, `config*.json`, `config.toml`, `*.lnk` und `openspec/changes/`. Die Ausschlussliste ist eine **Erlaubnisliste über `git ls-files`** plus die beiden erzeugten Dateien: was nicht versioniert ist, kommt nicht ins ZIP. Damit kann keine lokal entstandene Datei versehentlich mitgehen, und die Liste muss nicht jedem neuen Artefakt hinterherlaufen.

**Umsetzungsnotiz (12.09.2026):** Die Sauberkeitsprüfung des Arbeitsbaums ist als **harter Abbruch ohne Ausweichschalter** umgesetzt (`release.check_worktree`). Die Dateiauswahl läuft zwar über `git ls-files`, liest die Dateien aber von der Platte: eine Änderung, die nirgends festgehalten ist, ginge im Archiv mit und existierte auf keinem Zweig. Ohne `.git` — also beim Bauen aus einem entpackten Archiv — entfällt die Prüfung, weil es nichts zum Vergleichen gibt.

Die Nutzerpfad-Prüfung ist ein harter Abbruch, keine Warnung. Ein ZIP, das an Kollegen geht und den Benutzernamen des Entwicklers enthält, ist nicht ärgerlich, sondern ein Vorfall — und das Repository ist zusätzlich öffentlich.

Verworfen: **`pyproject.toml` als Quelle** und `VERSION` daraus erzeugt — üblicher in Python-Projekten, scheitert aber am Bootstrap ohne Laufzeit. Verworfen: **Git-Tags als Quelle** (`setuptools-scm` und Verwandte) — im ZIP gibt es kein `.git`, die Version wäre auf dem Kollegenrechner nicht mehr ermittelbar. Verworfen: **das ZIP von Hand im Explorer packen** — genau hier entstehen `.venv` im Archiv, eine vergessene `.env` und ein ZIP ohne oberste Ordnerebene.

Preis der Entscheidung: die Version steht an einem Ort, den Python-Werkzeuge nicht von sich aus kennen; ein Build-Backend muss sie lesen, und wer `pyproject.toml` liest, findet dort keine Zahl. Der Verweis auf `VERSION` steht deshalb als Kommentar in `pyproject.toml`.

### D19: Die Einrichtung redet wie ein Assistent, nicht wie ein Werkzeug

Die Konsole bleibt, ihr Auftreten ändert sich. Festgelegt sind:

| Regel | Umsetzung |
| --- | --- |
| Fenstertitel und Kopf | `title Backrec einrichten`, Bildschirm leeren, Kopfzeile mit Name und Version aus `VERSION` |
| Schritte | „Schritt 3 von 7: Konfiguration", Ergebnis als `[OK]` / `[!]` / `[X]` und ein Satz Klartext |
| Fragen | genau eine gleichzeitig, Vorgabe in Klammern, Enter übernimmt sie, Pfadfragen zeigen den Vorschlag |
| Sprache | kein „venv", „lock", „stdout", „Exit-Code"; keine Ausnahmeverfolgung, nie |
| Fehler | zwei Zeilen: „Was ist passiert" und „Was tun", mit dem konkreten nächsten Handgriff |
| Abschluss | Zusammenfassung aller Schritte mit Symbolen, Logpfad genau einmal, „Zum Schließen Enter drücken" |
| Farbe | nur bei Konsolenunterstützung; sonst tragen die Symbole die Aussage allein |
| Zeichensatz | Codepage 65001 und UTF-8-Ausgabe, damit Umlaute in Pfaden und Meldungen stimmen |
| Zonenkennung | das Bootstrap-Skript entfernt beim ersten Lauf die Internet-Zonenkennung aller Dateien im Ordner |

**Umsetzungsnotiz (12.09.2026), zwei Punkte:**

1. **Die beiden PowerShell-Skripte tragen eine Bytereihenfolge-Kennung.** Ohne sie liest Windows PowerShell 5.1 eine UTF-8-Datei als ANSI, und jeder Umlaut zerfällt in zwei Zeichen — der Grund, weshalb ihre Sätze zwischenzeitlich „fuer" und „laeuft" schrieben. Die ersten Zeilen, die ein Kollege überhaupt zu sehen bekommt, kommen aus dem Bootstrap; ein Werkzeug, das dort sein eigenes Alphabet nicht beherrscht, hat den Ton verloren, bevor es angefangen hat. Ein Test prüft Kennung und Schreibweise.
2. **Ein unerwarteter Fehler endet nicht mehr still.** `app.main` fängt ab, was unterhalb des Preflight niemand vorhergesehen hat, und zeigt denselben Dialog mit „Was ist passiert" und „Was tun"; die Anzeigeschleife überlebt ihren eigenen Fehler, statt die Uhr der Anwendung anzuhalten; Ausnahmen aus Hintergrundfäden und aus Fenster-Rückrufen landen im Protokoll statt in einem `stderr`, das unter `pythonw` nicht existiert. Ohne das blieb genau der Fall übrig, den dieser Change abschaffen wollte: kein Fenster, keine Meldung, keine Spur.

Die Ausgabe ist damit eine **zweite Darstellung** der Dataclasses aus D9, nicht eine zweite Wahrheit: `cli.py` bekommt einen Assistenten-Ausgabekanal, der Stufe, Ursache und nächsten Schritt in dieses Format bringt. Die technische Fassung derselben Befunde steht im Protokoll, und `doctor --json` bleibt unverändert maschinenlesbar.

Die Zonenkennung ist der einzige Punkt, der etwas verändert statt nur anzuzeigen. Er ist nötig, weil Windows jede Datei aus einem heruntergeladenen ZIP markiert und sonst bei `Setup.cmd`, bei den PowerShell-Skripten und teils bei den entpackten Python-Dateien ein Sicherheitsdialog erscheint. Der **erste** Dialog beim Doppelklick auf `Setup.cmd` selbst lässt sich damit nicht verhindern und wird in der Anleitung mit dem Wortlaut der Schaltflächen erklärt.

Verworfen: **eine grafische Einrichtung** (ein eigenes Fenster für den Wizard) — wäre für die Zielgruppe am freundlichsten, verdoppelt aber die Oberfläche, braucht die GUI-Abhängigkeiten, bevor die Umgebung existiert, und macht `--unattended` zu einem Sonderweg. Verworfen: **die technische Ausgabe beibehalten und nur ein README schreiben** — die Erfahrung mit den bestehenden Skripten ist, dass niemand ein README liest, während ein Fenster mit rotem Text offen ist. Verworfen: **Fehlermeldungen mit Ausnahmeverfolgung im Fenster** — für die Fehlersuche bequem, für den Adressaten der Moment, in dem er aufhört zu lesen; die Verfolgung steht vollständig im Protokoll, dessen Pfad die Zusammenfassung nennt.

Preis der Entscheidung: der Entwickler sieht in der Konsole weniger als heute und muss für die Details ins Protokoll sehen. Abgefedert durch `--verbose`, das die technische Fassung zusätzlich ausgibt, und dadurch, dass der Logpfad am Ende jedes Laufs steht.

### D20: Fenster-Menü hinter einer Zahnrad-Schaltfläche

Das Fenster bekommt in seiner Kopfzeile eine Schaltfläche `⚙` von der Höhe der Statuszeile. Ein Klick öffnet ein natives Kontextmenü (`tkinter.Menu` mit `tearoff=0`, geöffnet über `tk_popup` an der Position der Schaltfläche) mit vier Einträgen: „Aktualisieren…", „Diagnose", „Logs öffnen", „Info". Die Reihenfolge folgt dem Tray-Menü der Konvention, ohne die Einträge, die Backrec nicht hat (Statuszeile ist im Fenster ohnehin sichtbar, „Beim Anmelden starten" entfällt mit D14, „Beenden" ist das Fenster-X).

Ein Kontextmenü statt eingebauter Bedienelemente, weil die Fensterbreite mit 280 px (`main.pyw:63`) festliegt und per Polling verteidigt wird (`main.pyw:548-565`): jedes zusätzliche sichtbare Element ginge auf Kosten der Aufnahmebedienung, die der eigentliche Zweck des Fensters ist. Das Menü selbst kostet die Breite einer Schaltfläche und öffnet sich über dem Fenster hinaus.

Während eine langlaufende Aktion arbeitet — „Aktualisieren…" und „Diagnose" —, ist das Menü deaktiviert und die Statuszeile zeigt den Vorgang. Während einer **laufenden Aufnahme** sind „Aktualisieren…" und „Diagnose" deaktiviert: eine Aktualisierung würde die Anwendung mitten in der Aufnahme beenden, und die Diagnose würde in einem Moment Auskunft geben, in dem alles belegt ist. Jede Menüauswahl wird protokolliert.

Verworfen: **eine Menüleiste am oberen Fensterrand** (`tk.Menu` als `menu=`-Attribut) — kostet eine Zeile Höhe, wirkt an einem 280 px breiten Always-on-top-Werkzeug wie ein Fremdkörper und verschiebt die Geometrie, die das Fenster aktiv verteidigt. Verworfen: **ein Rechtsklick-Menü auf dem Fensterhintergrund** — unsichtbar; was man nicht sieht, existiert für die Zielgruppe nicht. Verworfen: **ein eigenes Einstellungsfenster** — ein zweites Fenster für vier Einträge, von denen drei sofort etwas tun und nichts anzeigen. Verworfen: **ein Tray-Symbol nur für dieses Menü** — widerspricht der Festlegung „Backrec hat kein Tray" und brächte ein Symbol, das ohne laufende Anwendung nicht da ist.

**Umsetzungsnotiz (12.09.2026):** „Aktualisieren…" fragt zwischen Dateiauswahl und erster Veränderung **einmal** nach und nennt dabei beide Fassungen. Der Grund ist die Reihenfolge, nicht die Höflichkeit: Aus dem Archiv wird für diese Frage nur die kleine Dateiliste gelesen; das Entpacken und die Prüfsummen kommen erst nach dem Ja. Eine Fassung, die nicht neuer ist, wird abgewiesen, solange der Benutzer ihr nicht ausdrücklich zustimmt — die Frage sagt dann, dass sie nicht neuer ist, statt es zu verschweigen. Auf der Kommandozeile trägt `update --force` dieselbe Zustimmung.

Der Eintrag „Info" nennt Werkzeugname, Version, Repo-Pfad, Konfigurationspfad, den **vollständigen Pfad zu `LIES-MICH-ZUERST.txt`** (D22), den Deinstallationsweg und — als einzige Stelle, die dafür Platz hat — den Ort, an dem Einstellungen, Aufzeichnungen und Zustand nach dem Löschen des Ordners liegen bleiben. Der Pfad zur Anleitung steht dort, weil ein Kollege, der die Anwendung seit Monaten über das Desktop-Symbol startet, den entpackten Ordner nicht mehr im Kopf hat — die Auskunft führt ihn zurück zu dem Text, der alle vier Wege beschreibt.

Preis der Entscheidung: die Funktionen sind einen Klick tiefer versteckt als in einem Tray-Menü, und ein Kollege muss wissen, dass hinter dem Zahnrad etwas liegt. Deshalb nennt `LIES-MICH-ZUERST.txt` (D22) das Zahnrad in ihrem Abschnitt „Im Alltag" ausdrücklich, und die Einrichtung nennt es in ihrer Abschlusszusammenfassung.

### D21: Die Diagnose gibt es zusätzlich als Textdatei zum Weiterschicken

`doctor` hat drei Ausgaben aus **einer** Befundliste: die Konsolenfassung nach D19, die maschinenlesbare Fassung (`--json`) und einen Textbericht. Der Menüpunkt „Diagnose" (D20) schreibt den Bericht nach `%LOCALAPPDATA%\MemoSuite\Backrec\logs\diagnose-<Zeitstempel>.txt` und öffnet ihn mit dem Standard-Editor (`os.startfile`). Der Bericht trägt in seiner Kopfzeile Toolname, Version, Repo-Pfad, Konfigurationspfad und Zeitstempel und listet danach alle Befunde in Klartext.

Der Zweck ist nicht die Diagnose selbst, sondern der Weg dorthin: ein Kollege, bei dem etwas nicht funktioniert, soll etwas haben, das er per Teams verschicken kann, ohne einen Screenshot zu machen, einen Pfad abzutippen oder eine Konsole zu öffnen. Die Kopfzeile ist genau deshalb so ausführlich — sie beantwortet die drei Rückfragen, die sonst folgen.

Die Diagnose bleibt auch aus dem Fenster heraus streng read-only (D12). Sie ändert weder den Zustand des Fensters noch eine Anzeige; das Schreiben des Berichts in das Protokollverzeichnis ist die einzige Nebenwirkung und dort erlaubt.

Verworfen: **den Bericht in einem eigenen Fenster anzeigen** — Backrec müsste eine Textanzeige mit Bildlauf bauen, aus der der Kollege den Inhalt herauskopieren müsste; eine Datei kann er anhängen. Verworfen: **den Bericht in die Zwischenablage legen** — unsichtbar, und ein Klick auf etwas anderes ist er wieder weg. Verworfen: **den Bericht automatisch an Tobias senden** — verlangt einen Versandweg, Berechtigungen und eine Zustimmung des Benutzers zu dem, was darin steht.

Preis der Entscheidung: das Protokollverzeichnis sammelt mit jeder Diagnose eine weitere Datei. Sie unterliegen nicht der Rotation der Protokolldatei, sind aber wenige Kilobyte groß; die Diagnose meldet ab zwanzig Berichten eine Warnung mit dem Hinweis, sie zu löschen.

### D22: `LIES-MICH-ZUERST.txt` im Wurzelverzeichnis ist der gesamte Kollegen-Text

Die Lage, die diese Datei löst, liegt vor jedem Schritt, den D19 und D20 regeln: Der Kollege hat das ZIP entpackt, der Explorer zeigt einen Ordner mit rund einem Dutzend Einträgen, und nichts darin sagt ihm, was er anklicken soll. Bis er `Setup.cmd` gefunden hat, hat die Assistenten-Ausgabe noch keine Zeile geschrieben.

**Name und Ort:** `LIES-MICH-ZUERST.txt`, direkt im Wurzelverzeichnis. Der Name ist Anweisung und Reihenfolge in einem, steht in der alphabetischen Sortierung des Explorers vor `README.md`, `Setup.cmd` und `Start.cmd`, und die Endung `.txt` ist auf jedem Windows-Rechner mit einem Editor verknüpft.

**Form:** reiner Text, UTF-8 **mit** BOM und CRLF — beides, damit ein Doppelklick die Datei im Editor mit korrekten Umlauten und korrekten Zeilenumbrüchen zeigt. Höchstens 40 Zeilen, Zeilen höchstens 80 Zeichen, damit sie ohne Bildlauf und ohne Umbruch lesbar bleibt. Keine Markdown-Syntax, keine Tabellen, kein Kommando, kein Dateipfad außer den Dateinamen `Setup.cmd` und dem Entpackziel, kein Fachbegriff der Sperrliste aus D19.

**Sprache: deutsch, obwohl die README englisch bleibt.** Das ist der einzige bewusste Sprachbruch im Repository und die Auflösung der bisherigen offenen Frage nach der Sprache des Kollegen-Teils. Die README ist Entwicklerdoku eines öffentlichen MIT-Repositorys (`LICENSE`, `README.md:7-8`) und richtet sich an ein englischsprachiges Publikum; `LIES-MICH-ZUERST.txt` richtet sich an genau eine Gruppe — die deutschsprachigen Kollegen, die das interne Release-ZIP bekommen. Ein Text, der für seinen einzigen Adressaten in der falschen Sprache steht, verfehlt seinen Zweck vollständig; die Konvention verlangt die Datei deshalb in **allen fünf** Repos auf Deutsch, auch in Backrec.

**Einzige Quelle:** Der Kollegen-Text steht ab jetzt nur hier. Die README verliert ihren Teil „For colleagues" und beginnt stattdessen mit einem Satz, der auf die Datei verweist; der Menüpunkt „Info" (D20) nennt ihren Pfad; das Release-Manifest (D18) führt sie. Damit gibt es eine Stelle, an der der Kollegen-Text gepflegt wird, statt zweier, die auseinanderlaufen.

**Die acht Pflichtabschnitte, in dieser Reihenfolge:**

| # | Abschnitt | Backrec-Inhalt |
| --- | --- | --- |
| 1 | Kopf | Name, ein Satz „nimmt Mikrofon und Systemton eines Gesprächs auf", ein Satz, wann man es braucht |
| 2 | „Was du brauchst" | Windows 11, Internet beim Einrichten, ein Mikrofon. **Kein Fremdprogramm**, weil ffmpeg die Einrichtung selbst beschafft (D13) |
| 3 | „So richtest du es ein" | 1 `Setup.cmd` doppelklicken · 2 bei der Windows-Warnung „Weitere Informationen", dann „Trotzdem ausführen" · 3 Fragen mit Enter bestätigen, es dauert ein paar Minuten · 4 **die Verknüpfung auf dem Desktop wird angelegt** · 5 fertig, **das Symbol liegt auf dem Desktop** |
| 4 | „Im Alltag" | REC startet, STOP beendet und legt die Aufnahme ab; das Zahnrad öffnet das Menü (D20) |
| 5 | „Wenn etwas rot ist" | Zahnrad, „Diagnose", die Datei, die sich öffnet, an Tobias schicken (D21) |
| 6 | „Aktualisieren" | neues ZIP über den Ordner entpacken und `Setup.cmd` erneut doppelklicken, oder im Zahnrad-Menü „Aktualisieren…" (D17) |
| 7 | „Entfernen" | Fenster schließen, Verknüpfung vom Desktop löschen, Ordner löschen |
| 8 | Ansprechpartner | Tobias Müller und der Satz „Alles Technische steht in README.md, das brauchst du nicht." |

Die Abschnitte 3, 4 und 7 weichen von der suiteweiten Vorlage ab, weil Backrec weder Autostart noch Symbol im Infobereich hat (D14, D20): Schritt 4 ist „wird angelegt" statt des Drag-and-drop in den Autostart-Ordner, Schritt 5 nennt den Desktop statt der Uhr, und „Entfernen" nennt die Desktop-Verknüpfung statt des Autostart-Hakens.

**Maschinelle Prüfung im Release-Bau (D18), harter Abbruch:** Dateiname exakt, Zeichenkodierung UTF-8 mit BOM und CRLF, höchstens 40 Zeilen, jede Zeile höchstens 80 Zeichen, keine Zeile mit einem Begriff der Sperrliste, alle acht Abschnittsüberschriften vorhanden und in der festgelegten Reihenfolge. Die Prüfung ist deshalb hart und keine Warnung, weil ein ZIP ohne diese Datei — oder mit einer, die auf halber Strecke abbricht — den Kollegen genau in die Lage zurückwirft, für die es sie gibt, und weil ein Release nicht zurückgerufen werden kann, wenn es einmal in einem Teams-Kanal liegt.

Verworfen: **die README als Einstieg**, wie es die erste Fassung dieses Changes mit dem Teil „For colleagues" vorsah — ein Doppelklick auf `README.md` öffnet bei einem Laien entweder gar kein Programm oder einen Editor voller Rauten, Sternchen und Backticks, und der erste Eindruck ist dann eine Datei, die kaputt aussieht. Verworfen: **`.html`** — öffnet zuverlässig und sähe besser aus, ist aber eine Datei, die im Browser landet, wo der Ordner mit `Setup.cmd` aus dem Blick gerät, und sie lädt zum Formatieren ein, bis niemand mehr weiß, wo der Text gepflegt wird. Verworfen: **`.pdf`** — verlangt einen Betrachter, ist nicht diffbar, nicht prüfbar und nicht ohne Werkzeug änderbar. Verworfen: **`.docx`** — dasselbe, dazu eine Binärdatei in einem öffentlichen Quellrepository. Verworfen: **die Anleitung vom Setup selbst anzeigen lassen** — sie muss gelesen werden, **bevor** der Kollege weiß, dass es ein Setup gibt; ein Text, den nur das Programm zeigt, das man erst finden muss, löst das Problem nicht.

Preis der Entscheidung: eine fünfte Datei im Wurzelverzeichnis, das D16 gerade erst auf das Nötigste zusammengestrichen hat, und ein Sprachbruch in einem sonst englischen öffentlichen Repository, der jedem Fremden auffällt. Dazu ein Text, der doppelt gepflegt werden **will**, sobald sich Abläufe ändern — die maschinelle Prüfung fängt Formfehler, aber keine inhaltliche Veralterung. Abgefedert dadurch, dass die Datei keinen Vorgang startet und deshalb nicht mit `Setup.cmd` und `Start.cmd` konkurriert, und dass die Abnahme des Kollegenwegs (Aufgabe 13.1a) sie als einzige zugelassene Anleitung benutzt: veraltet sie, fällt es dort auf.

## Risks / Trade-offs

- **Die Verschiebung von 907 Zeilen bricht den Aufnahmekern, ohne dass Tests es merken** → die Aufteilung (D1) geschieht als erster Abschnitt der Aufgabenliste, ohne jede Verhaltensänderung, mit einer vollständigen Aufnahme als Abnahme; alle Verhaltensänderungen folgen danach in eigenen Aufgaben.
- **customtkinter 5→6 und numpy 1→2 werden mit dem Pinnen offiziell** → eigene Verifikationsaufgaben: Aufnahme mit Gerätewechsel und Mute, Mischung, Fenstergeometrie über die Skalierungseingriffe (`main.pyw:53-61`). Schlägt eine fehl, ist das Zurückpinnen eine Zeile in `pyproject.toml` und ein `uv lock`.
- **`pywin32` bringt COM in einen Prozess, der COM schon für pycaw benutzt** (`main.pyw:277-284`, `main.pyw:568-578`) → Verknüpfung und Fenstervordergrund laufen im Hauptthread der CLI oder vor dem Fensteraufbau, nie in einem Aufnahmefaden; die bestehende Initialisierung pro Thread bleibt unverändert.
- **`SetForegroundWindow` kann von Windows verweigert werden** → der zweite Start meldet dann, dass die Anwendung läuft, statt das Fenster zu holen; Exit-Code 3 und Protokolleintrag sind in beiden Fällen gleich, die Spec verlangt genau diese Wahl.
- **Der Stop-Sentinel wird erst nach bis zu 150 ms bemerkt und könnte liegen bleiben** → der Preflight löscht einen vorgefundenen Sentinel vor dem Fensteraufbau; die Diagnose meldet ihn als Warnung.
- **`winget` fehlt oder das ffmpeg-Paket ist nicht verfügbar** → dokumentierter manueller Weg, Einrichtung endet mit Exit-Code ungleich 0, Diagnose bleibt rot, bis ffmpeg aufrufbar ist.
- **D8 ändert das Verhalten im Fehlerfall gegen die Erwartung von Bestandsnutzern**: bisher lagen im Zielverzeichnis nach einem Merge-Fehler zwei Rohspuren, künftig nichts → die Statuszeile nennt den Verbleib, der README beschreibt den Fall, und die häufigste Ursache wird von D5 vor der Aufnahme abgefangen.
- **Zwei Konfigurationsdateien während des Übergangs** → die Diagnose meldet eine vorhandene, unwirksame `.env` im Repository als Warnung mit dem Hinweis auf die Migration.
- **`requires-python >= 3.11` schließt 3.10 aus**, das der README bisher versprach (`README.md:22`) → im README als Änderung ausgewiesen; `uv` beschafft einen passenden Interpreter selbst, der Ausschluss trifft in der Praxis nur, wer bewusst ohne `uv` arbeitet.
- **Das Aufnahmeverzeichnis wächst weiter unbegrenzt** → bewusst nicht im Umfang; die Diagnose warnt beim Speicherplatz und nennt den Bedarf je Minute, damit die Ursache benennbar bleibt.
- **Das Umbenennen der Ordner beim Update (D17) scheitert, weil eine Datei noch offen ist** — ein Virenscanner, ein offener Explorer, ein hängender Kindprozess → der Aktualisierungsprozess wartet auf das Ende der alten Instanz, versucht das Umbenennen mit Frist und mehreren Anläufen und bricht **vor** dem ersten Umbenennen ab, wenn es nicht gelingt; der alte Ordner bleibt dann unverändert lauffähig, und die Zusammenfassung nennt Weg A als Alternative.
- **Die Manifest-Kopie unter `state\` fehlt** — erste Einrichtung aus einem ZIP ohne Vorgänger, gelöschtes Zustandsverzeichnis, Einrichtung aus einem Git-Klon ohne Release → das Aufräumen der Altdateien entfällt dann ersatzlos und wird als übersprungener Schritt gemeldet; ein Update bleibt ohne Aufräumen vollständig funktionsfähig, es bleiben nur Dateien liegen, die niemand mehr liest.
- **Die Nutzerpfad-Prüfung im Release (D18) übersieht einen Pfad**, weil er anders geschrieben ist (Kurzform `C:\Users\TOBIAS~1`, UNC-Pfad, Umlaut im Firmennamen) → geprüft wird gegen mehrere Muster, und die Prüfung läuft über `git ls-files`, also über eine überschaubare, vollständig bekannte Dateimenge; ein zusätzlicher Blick in das gebaute ZIP bleibt Teil der Abnahme.
- **Das Entfernen der Zonenkennung (D19) wird von einer Sicherheitsrichtlinie unterbunden** oder trifft nicht alle Dateien → die Einrichtung behandelt einen Fehlschlag als Warnung, nicht als Abbruch, und nennt den Weg über die Dateieigenschaften („Zulassen"); der Ablauf funktioniert auch mit Zonenkennung, er zeigt dann nur weitere Dialoge.
- **Die Assistenten-Ausgabe (D19) verbirgt eine Ursache, die der Entwickler gebraucht hätte** → jede Meldung existiert zusätzlich in technischer Fassung im Protokoll, der Logpfad steht am Ende jedes Laufs, und `--verbose` gibt die technische Fassung zusätzlich in die Konsole.
- **Das Fenster-Menü (D20) wird nicht gefunden**, weil ein Zahnrad ohne Beschriftung für die Zielgruppe nicht selbsterklärend ist → Hovertext an der Schaltfläche, ausdrückliche Nennung im Abschnitt „Im Alltag" von `LIES-MICH-ZUERST.txt` (D22) und in der Abschlusszusammenfassung der Einrichtung.
- **`LIES-MICH-ZUERST.txt` veraltet inhaltlich**, weil die maschinelle Prüfung (D22) nur Form, Sperrliste und Abschnittsbestand kennt, nicht die Richtigkeit der beschriebenen Schritte → jede Aufgabe, die einen für den Kollegen sichtbaren Ablauf ändert, führt die Datei als mitzuziehendes Artefakt; die Abnahme des Kollegenwegs (13.1a) lässt ausdrücklich **nur** diese Datei als Anleitung zu, sodass eine Abweichung dort auffällt.
- **Die 40-Zeilen-Grenze zwingt zum Weglassen**, und der weggelassene Satz ist genau der, den ein Kollege gebraucht hätte → die acht Abschnitte sind vorgegeben, der Kürzungsdruck trifft also nur die Länge je Abschnitt; was nicht hineinpasst, gehört in die Assistenten-Ausgabe der Einrichtung (D19), die den Benutzer ohnehin durch den Ablauf führt, statt in einen längeren Text, den er vorher lesen müsste.
- **Die deutsche Datei fällt in einem englischen öffentlichen Repository auf** und wirkt auf Fremde wie ein Versehen → die README nennt sie in ihrem einleitenden Verweis ausdrücklich als deutschsprachige Anleitung für interne Nutzer; ein Beitragender ist damit nach einem Satz im Bilde.

## Migration Plan

**Für den Entwickler, aus dem vorhandenen Klon:**

1. **Einrichten**: `Setup.cmd` ausführen. Der Lauf beschafft uv und ffmpeg, baut die Umgebung aus `uv.lock`, übernimmt eine vorhandene `.env` in `%LOCALAPPDATA%\MemoSuite\Backrec\config.toml` (D3), fragt fehlende Werte ab, schließt mit der Diagnose und fragt nach Desktop-Verknüpfung und Start.
2. **Prüfen**: `python -m backrec doctor` muss ohne Fehler durchlaufen. Bestehende Aufnahmen und Zieldateien werden nicht berührt.
3. **Startweg umstellen**: Die Einrichtung hat das Desktop-Symbol bereits angelegt (D14); andernfalls `python -m backrec shortcut`. Eine alte Verknüpfung auf `Start_Recorder.bat` löschen; ein Doppelklick darauf nennt ab jetzt den neuen Weg (D11).
4. **Abnehmen**: eine vollständige Aufnahme mit Gerätewechsel, Mute und STOP; eine Aufnahme, die über das Fenster-X beendet wird (D7); eine Aufnahme mit umbenanntem ffmpeg, um D8 und D5 zu sehen.
5. **Verteilen**: `python -m backrec release` baut das erste ZIP (D18). Das ZIP wird vor der Verteilung einmal in einem leeren Ordner entpackt und dort eingerichtet — das ist zugleich die Abnahme des Kollegenwegs.

**Für den Kollegen, aus dem ZIP:** entpacken nach `%USERPROFILE%\MemoSuite\Backrec\`, `LIES-MICH-ZUERST.txt` öffnen und den fünf Schritten folgen (D22), also `Setup.cmd` doppelklicken und Fragen mit Enter beantworten, fertig. Ein Update ist dasselbe ZIP-Entpacken über den Ordner und ein erneuter Doppelklick (D17, Weg A) oder der Menüpunkt „Aktualisieren…" (Weg B).

**Rücknahme**: Der Aufnahmekern ist unverändert, deshalb ist die Rücknahme ein Auschecken des vorherigen Stands plus `pip install -r requirements.txt` in einer eigenen venv. Konfiguration und Protokolle in `%LOCALAPPDATA%\MemoSuite\Backrec\` bleiben liegen und stören den alten Stand nicht; die `.env` im Repository wirkt nach der Rücknahme wieder, weil die Migration sie nicht gelöscht hat. Nach einem ZIP-Update ist die Rücknahme zusätzlich das Umbenennen von `<repo>.old-<version>` zurück, solange der Ordner noch steht.

## Open Questions

- Wie viel Speicherplatz die Diagnose als Reserve verlangen soll, ist mit 2 GB (rund 100 Minuten Aufnahme) angesetzt. Der Wert lässt sich nach den ersten Wochen ohne Änderung an Spec, Ansatz oder Aufgabenschnitt anpassen.
- Ob die Frist für das harte Beenden nach dem Stop-Sentinel (30 s) für sehr lange Aufnahmen ausreicht, wird die Praxis zeigen; auch das ist ein Zahlenwert innerhalb einer bereits festgelegten Anforderung.
- **Sprache des Kollegen-Textes — entschieden (12.09.2026), nicht mehr offen.** Die frühere Frage, ob der Kollegen-Teil des README englisch oder deutsch sein soll, ist mit D22 beantwortet: Der Kollegen-Text verlässt die README und wird `LIES-MICH-ZUERST.txt` auf Deutsch, während die README als englische Entwicklerdoku bleibt. Offen bleibt nur der ursprüngliche Anlass der Frage — ob das Repository öffentlich bleibt (`LICENSE`, `README.md:7-8`). Fällt die Entscheidung auf „privat", ändert das an D22 nichts; fällt sie auf „öffentlich bleiben", ebenfalls nicht, weil die Datei keinen Nutzer-, Firmen- oder Cloud-Speicherpfad enthält und damit unbedenklich veröffentlichbar ist.
- **Übergang der alten Skripte, suiteweit.** Backrec behält `Start_Recorder.bat` als Hinweis-Wrapper (D11), AMD-Transcription und AutoMemo löschen ihre `setup.bat`/`start.bat` ersatzlos. Die Konvention führt das als bekannte Abweichung; die einheitliche Linie entscheidet Tobias. Bis dahin gilt D11 unverändert. Eine spätere Vereinheitlichung in beide Richtungen kostet in Backrec eine Datei und eine Spec-Anforderung.
- **Ab wie vielen Diagnose-Berichten (D21) die Warnung kommt**, ist mit zwanzig angesetzt, und ob die Berichte stattdessen automatisch nach einer Frist verfallen sollen, bleibt offen. Ein Zahlenwert innerhalb einer festgelegten Anforderung.
- **Wann `<repo>.old-<version>` verschwindet** (D17): vorgesehen ist der nächste erfolgreiche Start nach dem Update. Ob stattdessen ein ausdrücklicher Menüpunkt oder die Diagnose mit einem Hinweis besser ist, zeigt der erste echte Updatelauf.
