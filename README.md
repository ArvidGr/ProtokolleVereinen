# ZOPF Protokoll-Generator

Erzeugt aus den XML-Reports des Teststands automatisch PDF-Prüfprotokolle im
ZOPF-Layout („TEST PROTOCOL“).

Das Programm läuft im Hintergrund, durchsucht regelmäßig den Messdaten-Ordner
und legt für jede fertig geschriebene Test-XML, zu der es noch kein PDF gibt,
das passende Protokoll an. Das PDF landet direkt neben der XML.

## Inhalt

- [Was steht im Protokoll?](#was-steht-im-protokoll)
- [Wo liegen die Dateien?](#wo-liegen-die-dateien)
- [Installation](#installation)
- [Benutzung](#benutzung)
- [Einstellungen](#einstellungen)
- [Wie der Scanner arbeitet](#wie-der-scanner-arbeitet)
- [Fehlersuche](#fehlersuche)
- [Projektaufbau](#projektaufbau)

## Was steht im Protokoll?

Ein PDF (A4) mit:

- **General Information** – Datum, DUT, Artikelnummer, Seriennummer, Bediener
- **Overall Result** – PASSED (grün) oder FAILED (rot, mit Fehlermeldung aus der XML)
- **Parameters** – Zyklenzahl, Vlink, Schalt- und Ausgangsfrequenz, Dauer und Strom
  für High/Low Load (aus den Modulen `TimeCycle` und `Preparation`)
- **Temperature Data** – maximal zulässige Temperatur (max. Umgebungstemperatur
  + 20 K) und gemessene Maximaltemperatur des DUT
- **Measurement Data** – Diagramm mit Zwischenkreisspannung, DUT-Temperatur,
  Umgebungstemperatur und Phasenstrom über die Zeit

Abschnitte, für die in der XML keine Daten vorhanden sind, werden weggelassen.

## Wo liegen die Dateien?

### Eingabe: Test-XMLs

Der Teststand legt seine Reports unter einem Wurzelordner (`ROOT_DIR`) in dieser
Struktur ab:

```
<ROOT_DIR>\<Jahr>\KW<nn>\<Testordner>\<Name>@<JJJJ-MM-TT_hh-mm-ss>.xml
```

Standardmäßig ist `ROOT_DIR`:

```
\\192.168.91.11\zeag\E-Werkstatt\Messprotokolle_Test\Wickede\EC300KW\Phase
```

Andere Ordner unterhalb von `ROOT_DIR` (z. B. „Änderungen“) werden ignoriert.

### Ausgabe: PDFs

Das PDF wird **im selben Ordner wie die XML** gespeichert. Der Dateiname ist der
XML-Name mit der Endung `_TestProtocol.pdf`:

```
...\2026\KW39\Test_0815\EC300@2026-09-21_14-07-48.xml
...\2026\KW39\Test_0815\EC300@2026-09-21_14-07-48_TestProtocol.pdf
```

Während der Erzeugung entsteht kurz eine Datei `..._TestProtocol.pdf.tmp`, die
anschließend umbenannt wird. So gibt es nie halb geschriebene PDFs.

Ausnahme: Beim Befehl `file ... --out <Ordner>` (siehe unten) landet das PDF im
angegebenen Ordner.

### Programmdateien

Diese Dateien liegen im **Programmordner** – das ist der Ordner der
`ProtokollGenerator.exe` bzw. bei der Python-Variante dieses Projektverzeichnis:

| Datei                   | Zweck                                                                                     |
|-------------------------|-------------------------------------------------------------------------------------------|
| `protokoll.log`         | Protokoll aller Aktionen und Fehler. Wird bei 2 MB rotiert (`protokoll.log.1` … `.3`).     |
| `skipped.json`          | Liste der XMLs, die absichtlich nicht (mehr) verarbeitet werden – siehe [unten](#wie-der-scanner-arbeitet). |
| `protokoll_config.json` | *Optional.* Überschreibt Einstellungen, siehe [Einstellungen](#einstellungen).            |

Beim Build entstehen außerdem `build\`, `dist\` und `ProtokollGenerator.spec`.
Die fertige Exe liegt in `dist\ProtokollGenerator.exe`.

## Installation

Es gibt zwei Varianten: die eigenständige **Exe** (für den Teststand-PC, dort
wird kein Python benötigt) oder direkt mit **Python** (für Entwicklung).

### Variante A: Exe (empfohlen für den Teststand-PC)

1. Auf einem Rechner mit Python (3.10 oder neuer) die Exe bauen:

   ```powershell
   .\build_exe.ps1
   ```

   Das Skript legt bei Bedarf die virtuelle Umgebung `.venv` an, installiert die
   Abhängigkeiten und PyInstaller und erzeugt `dist\ProtokollGenerator.exe`.

2. Die Exe auf den Teststand-PC kopieren, z. B. nach `C:\Protokoll\`.
   Optional eine `protokoll_config.json` daneben legen.

3. Dort als Hintergrund-Aufgabe einrichten:

   ```powershell
   .\install_task.ps1 -Exe C:\Protokoll\ProtokollGenerator.exe
   ```

### Variante B: Python

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Als Hintergrund-Aufgabe einrichten (nutzt `.venv\Scripts\pythonw.exe`, also
ohne Konsolenfenster):

```powershell
.\install_task.ps1
```

### Die Windows-Aufgabe

`install_task.ps1` legt in der Aufgabenplanung die Aufgabe
**„ZOPF Protokoll-Generator“** an und startet sie sofort. Die Aufgabe

- startet bei der Anmeldung des aktuellen Benutzers,
- läuft unbegrenzt im Hintergrund (kein Fenster),
- wird nach einem Absturz nach 1 Minute neu gestartet,
- läuft nie doppelt.

Entfernen:

```powershell
.\install_task.ps1 -Remove
```

> Der Benutzer, unter dem die Aufgabe läuft, braucht Lese- und Schreibrechte auf
> dem Netzlaufwerk `ROOT_DIR`.

## Benutzung

Im Normalfall ist nichts zu tun: Die Aufgabe läuft im Hintergrund und PDFs
erscheinen automatisch etwa 30–60 Sekunden nach Testende neben der XML.

Für manuelle Aufrufe gibt es drei Befehle. Bei der Exe statt
`python -m protokoll.main` einfach `ProtokollGenerator.exe` schreiben.

```powershell
# Dauerbetrieb (das macht auch die Windows-Aufgabe)
python -m protokoll.main run

# Einmal die aktuellen Wochen scannen und fehlende PDFs erzeugen
python -m protokoll.main once

# Einmal den kompletten Wurzelordner scannen (alle Jahre/KWs)
python -m protokoll.main once --full

# PDF für eine einzelne XML erzeugen (neben der XML)
python -m protokoll.main file "\\server\...\Test_0815\EC300@2026-09-21_14-07-48.xml"

# ... oder in einen anderen Ordner
python -m protokoll.main file "C:\temp\test.xml" --out C:\temp\pdfs
```

Globale Optionen stehen **vor** dem Befehl:

| Option               | Bedeutung                                                     |
|----------------------|---------------------------------------------------------------|
| `--root <Ordner>`    | anderen Wurzelordner verwenden (statt `ROOT_DIR`)             |
| `--since JJJJ-MM-TT` | nur XMLs berücksichtigen, die ab diesem Datum geändert wurden |

Beispiel: Alle fehlenden PDFs seit dem 1. September nachholen:

```powershell
python -m protokoll.main --since 2026-09-01 once --full
```

> Die Exe ist ohne Konsole gebaut und gibt deshalb nichts im Terminal aus.
> Ergebnisse und Fehler stehen in `protokoll.log`.

### Ein PDF neu erzeugen

PDF löschen – beim nächsten Scan wird es neu angelegt. Liegt die XML nicht in
der aktuellen oder der vorigen Kalenderwoche, passiert das beim nächsten
Komplett-Scan (spätestens nach einer Stunde) oder sofort mit
`once --full` bzw. `file <xml>`.

## Einstellungen

Die Standardwerte stehen in [protokoll/config.py](protokoll/config.py). Ohne
neu zu bauen lassen sie sich über eine Datei `protokoll_config.json` im
Programmordner überschreiben. Es zählen nur die Schlüssel, die es in
`config.py` gibt (Großbuchstaben). Backslashes in Pfaden müssen in JSON
verdoppelt werden:

```json
{
  "ROOT_DIR": "D:\\Messdaten\\Phase",
  "GENERATE_FOR_FAILED": false,
  "POLL_SECONDS": 60
}
```

Die Datei wird beim Programmstart gelesen – nach Änderungen die Aufgabe neu
starten (in der Aufgabenplanung „Beenden“ und „Ausführen“).

| Einstellung           | Standard              | Bedeutung                                                                       |
|-----------------------|-----------------------|---------------------------------------------------------------------------------|
| `ROOT_DIR`            | Netzlaufwerk (s. o.)  | Wurzelordner der Testdaten                                                      |
| `GENERATE_FOR_FAILED` | `true`                | `false` = für fehlgeschlagene/abgebrochene Tests kein PDF erzeugen              |
| `POLL_SECONDS`        | `30`                  | Abstand zwischen zwei Scans in Sekunden                                         |
| `SETTLE_SECONDS`      | `30`                  | so lange muss die XML unverändert sein, bevor sie verarbeitet wird              |
| `FULL_SCAN_MINUTES`   | `60`                  | Abstand der Komplett-Scans über den ganzen `ROOT_DIR`                           |
| `GIVE_UP_HOURS`       | `24`                  | unvollständige XMLs werden nach dieser Zeit nicht mehr geprüft                  |
| `PDF_SUFFIX`          | `_TestProtocol.pdf`   | Endung des PDF-Dateinamens                                                      |
| `TEMP_MARGIN_K`       | `20`                  | Max Temp = max. Umgebungstemperatur + dieser Wert (K)                           |
| `CH_VLINK`            | `REF Vlink`           | Messkanal Zwischenkreisspannung                                                 |
| `CH_TEMP_DUT`         | `DUT Temp1`           | Messkanal DUT-Temperatur                                                        |
| `CH_TEMP_AMBIENT`     | `REF Temp3`           | Messkanal Umgebungstemperatur                                                   |
| `CH_CURRENT`          | `DUT I1`              | Messkanal Phasenstrom                                                           |
| `FOOTER_LINES`        | ZOPF-Adresse          | Zeilen in der Fußzeile des PDFs (Liste von Texten)                              |

> Achtung: Wird `PDF_SUFFIX` geändert, erkennt das Programm vorhandene PDFs mit
> der alten Endung nicht mehr und erzeugt alle Protokolle neu.

## Wie der Scanner arbeitet

1. Alle `POLL_SECONDS` werden die Ordner der **aktuellen und der vorigen
   Kalenderwoche** (`<Jahr>\KW<nn>\*\*.xml`) durchsucht.
2. Beim Start und danach alle `FULL_SCAN_MINUTES` wird der **komplette**
   `ROOT_DIR` durchsucht, damit auch ältere XMLs ohne PDF nachgeholt werden.
3. Für jede XML ohne PDF:
   - Ist sie jünger als `SETTLE_SECONDS`, wird gewartet (Teststand schreibt evtl. noch).
   - Ist sie unvollständig (kein abschließendes `</Report>`, kein `Posttest`
     oder kein Testergebnis), wird gewartet. Nach `GIVE_UP_HOURS` wird sie
     aufgegeben und in `skipped.json` eingetragen.
   - Ist der Test fehlgeschlagen und `GENERATE_FOR_FAILED` ist `false`, wird sie
     übersprungen und in `skipped.json` eingetragen.
   - Sonst wird das PDF erzeugt. Schlägt das fehl, wird der Fehler geloggt und
     die XML ebenfalls in `skipped.json` eingetragen – der Dienst läuft weiter.

### skipped.json

Einträge in `skipped.json` merken sich den Änderungszeitpunkt der XML. Eine XML
wird automatisch wieder geprüft, wenn

- sie sich ändert (neuer Zeitstempel), oder
- sie wegen `FAILED` übersprungen wurde und `GENERATE_FOR_FAILED` wieder auf
  `true` steht.

Um eine aufgegebene XML manuell erneut zu versuchen: den Eintrag aus
`skipped.json` löschen (oder die ganze Datei) und die Aufgabe neu starten –
oder direkt `file <xml>` aufrufen.

## Fehlersuche

Erste Anlaufstelle ist immer `protokoll.log` im Programmordner.

| Meldung im Log                          | Ursache / Lösung                                                                                   |
|-----------------------------------------|-----------------------------------------------------------------------------------------------------|
| `Wurzelordner nicht erreichbar`         | Netzlaufwerk nicht verbunden oder keine Rechte. Der Scanner versucht es automatisch weiter.        |
| `Warte auf vollständige XML`            | Normal während ein Test läuft. Bleibt es dauerhaft, ist die XML defekt oder unvollständig.         |
| `Aufgegeben (seit >24h unvollständig)`  | XML war nie vollständig. Siehe [skipped.json](#skippedjson).                                       |
| `PDF-Erzeugung fehlgeschlagen`          | Unerwarteter Inhalt in der XML. Traceback im Log prüfen, ggf. mit `file <xml>` nachstellen.        |
| `Zugriffsfehler bei ...`                | Datei gesperrt oder Netzwerkfehler. Wird beim nächsten Scan erneut versucht.                       |

Läuft die Aufgabe überhaupt? In der Aufgabenplanung nach
„ZOPF Protokoll-Generator“ suchen oder:

```powershell
Get-ScheduledTask -TaskName "ZOPF Protokoll-Generator" | Get-ScheduledTaskInfo
```

## Projektaufbau

```
run_protokoll.py        Einstiegspunkt (für PyInstaller bzw. direkten Start)
protokoll/
  main.py               Kommandozeile (run / once / file), Logging
  config.py             Einstellungen + Laden von protokoll_config.json
  scanner.py            Suche nach XMLs ohne PDF, Dauerbetrieb, skipped.json
  parser.py             Einlesen der Teststand-XML
  report.py             PDF-Layout und Diagramm (reportlab + matplotlib)
  assets/zopf_logo.png  Logo im PDF-Kopf
build_exe.ps1           baut dist\ProtokollGenerator.exe
install_task.ps1        richtet die Windows-Aufgabe ein / entfernt sie
requirements.txt        Python-Abhängigkeiten
```
