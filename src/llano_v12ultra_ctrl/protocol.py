"""Byte-Layout des 8-Byte HID-Feature-Reports des llano V12 Ultra.

Reverse-engineered aus echtem USB-Traffic der originalen Myth.Cool-App
(Windows, per USB-Capture in einer VM), ergänzt durch systematische
Live-Tests direkt am physischen Gerät UND durch Analyse des App-eigenen
JS-Quellcodes (windows/background/bundle.min.js aus webapp.gpk, sowie
llanoV16.gpk für die geräte-spezifische UI). Die App sendet intern ein
benanntes JSON-Objekt ({light_mode, light_color_mode, light_speed,
light_power, light_on_off, on_off, fan_speed, ...}) über
mythcool.usbcenter.SendInfo an einen internen IPC-Bus; die eigentliche
Übersetzung JSON->8-Byte-Report passiert in kompiliertem/verschlüsseltem
Code (main.jsc), der nicht im Klartext einsehbar ist. Die Feldnamen
bestätigen aber unabhängig unsere empirisch gefundene Struktur:
light_mode<->effect(byte3), light_color_mode<->color(byte4),
light_on_off<->Licht-Aus über byte3, on_off<->kill_flag(byte2) - zwei
getrennte An/Aus-Konzepte, exakt wie empirisch gefunden. Siehe FINDINGS.md
im Projekt-Scratchpad für die vollständige Herleitung.

Report-Aufbau (9 Bytes gesamt, wie sie über HIDIOCGFEATURE/HIDIOCSFEATURE
gelesen/geschrieben werden):

    Index  0: report_id   (immer 0x00)
    Index  1: byte0 = status_marker
              KORRIGIERT: ist KEIN einfaches Konstantenfeld. Systematischer
              Send-vs-Read-Vergleich zeigt: unabhängig vom geschriebenen
              Wert liest GET_FEATURE hier immer 0x88 zurück - reines
              Input-Feld ohne Bezug zum Schreibwert (wie byte1/byte2/
              teilweise byte4, siehe unten). Bedeutung von 0x88 unbekannt.
              llano-v12ultra-ctrl schreibt hier weiterhin 0x00 (wie die echte App),
              da der Schreibwert nachweislich ignoriert wird.
              Zusätzlich getestet: bleibt bei 0x88, auch wenn die Einheit
              über den kill_flag (byte2) komplett ausgeschaltet ist - kein
              Statuswechsel für "an"/"aus" erkennbar in diesem Byte.
    Index  2: byte1 = fan_speed_raw
              LIVE-Telemetrie der aktuellen Raddrehzahl. Ändert sich in
              Echtzeit mit der physischen Radstellung. NICHT per Software
              schreibbar (0 von 15 Testschreibvorgängen wirksam; zusätzlich
              per vollständiger nativer Code-Analyse bestätigt, dass die
              Original-App selbst keinen funktionierenden Schreibpfad dafür
              besitzt - siehe FINDINGS.md).
              Laut Nutzerhandbuch: 300-2800 U/min in 100 U/min-Schritten
              (26 Stufen). ACHTUNG - KORRIGIERT: die ursprüngliche Annahme
              RPM = raw*25 war FALSCH (nur aus dem Handbuch-Text abgeleitet,
              nie gegen die echte Anzeige des Pads geprüft). Das Pad hat
              ein eigenes Display, das die tatsächliche Drehzahl anzeigt -
              damit direkt gegengeprüft: raw=1 -> Pad zeigt 300, raw=48 ->
              Pad zeigt 1500, raw=100 -> Pad zeigt 2800 (raw geht also nur
              von 1 bis 100, nicht wie ursprünglich angenommen 12-112).
              raw ist eine feine ~100-stufige Radposition, die auf die 26
              Handbuch-Stufen gerundet wird. Exakte Formel (3/3 Messpunkte
              treffen exakt): level = round((raw-1) * 25 / 99),
              RPM = 300 + level * 100.
    Index  3: byte2 = kill_flag
              KORRIGIERT (erste Einschätzung "wird ignoriert" war falsch -
              beruhte auf einem Test, bei dem der Auto-Daemon parallel lief
              und den geschriebenen Wert überschrieben hat). Live mit
              gestopptem Daemon neu verifiziert: JEDER Wert ungleich 0x00
              (getestet: 0x01, 0x10, 0x40, 0x55) schaltet SOFORT die
              GESAMTE Einheit aus - Beleuchtung UND LÜFTERMOTOR (per
              Nutzerbeobachtung: "Lüfter ist komplett aus, auch die
              Anzeige"). Das ist ein reiner Ein/Aus-Kill-Switch, keine
              Zwischenstufen (0x01 wirkt identisch zu 0x40/0x55 - komplett
              aus, kein abgestuftes Runterregeln beobachtet). 0x00 = normal
              Betrieb (Lüfter läuft wieder nach Radstellung, Licht wie
              durch effect/color/brightness konfiguriert).
              Beim GET_FEATURE-Rücklesen nach einem Nicht-Null-Schreibwert
              erscheint dort ein eigener Wert (z.B. 0x01), nicht der
              gesendete - vermutlich ein Fehler-/Status-Code, kein Echo.
              Dies ist die einzige gefundene Möglichkeit, den Lüftermotor
              per Software zu beeinflussen (nur an/aus, keine Drehzahl-
              Stufen) - unabhängig von der weiterhin bestehenden Grenze,
              dass die Drehzahl selbst nicht stufenlos einstellbar ist.
              llano-v12ultra-ctrl nutzt dies für den `power`-Befehl.
    Index  4: byte3 = effect
              Bestätigt per Software steuerbar UND mit sichtbarer Wirkung
              (live am Gerät verifiziert). Deckt sich mit den 4 Modi aus
              dem offiziellen Nutzerhandbuch ("single color always on",
              "single color breathing", "breathing gradient",
              "running light mode") plus einem im Handbuch nicht
              aufgeführten Bonus-Wert:
                0   = solid (statische Farbe)              = "single color always on"
                1   = breathing (Farbe pulsiert)            = "single color breathing"
                2   = rainbow breathing (Farbwechsel + Pulsieren) = "breathing gradient"
                3   = chase (Lauflicht, wandert über die LEDs)    = "running light mode"
                4   = vier statische Zonen mit unterschiedlichen Farben
                      (nicht im Handbuch dokumentiert - Bonus-Modus)
                5-0x7F = angenommen (Wert wird übernommen), aber OHNE
                         zusätzlichen sichtbaren Effekt gegenüber dem
                         zuvor aktiven Zustand - an 11 Messpunkten über
                         den gesamten Bereich (5,6,10,16,20,32,64,100,127)
                         einzeln mit gestopptem Daemon bestätigt, keine
                         Ausnahme gefunden
                0x80-0xFF = Beleuchtung AUS
    Index  5: byte4 = color
              Bestätigt per Software steuerbar UND mit sichtbarer Wirkung
              (live am Gerät verifiziert):
                0 = rot   1 = hellblau   2 = grün   3 = lila   4 = orange
              Werte außerhalb 0-4 werden NICHT abgelehnt/geclamped, sondern
              per Modulo 5 gewrappt: tatsächliche Farbe = geschriebener
              Wert % 5 (per Vollscan über 8 Testwerte 6-250 exakt
              bestätigt, u.a. 42 mod 5 = 2 = grün, 255 mod 5 = 0 = rot).
              Laut Handbuch "color switching unavailable" in den Effekten
              "breathing gradient" (2) und "running light" (3) - deckt sich
              mit der Beobachtung, dass diese beiden Effekte selbst durch
              alle Farben durchlaufen und der color-Wert dabei keine
              zusätzliche Wirkung zeigte. color ist also nur bei effect 0
              (solid) und 1 (breathing) tatsächlich relevant.
    Index  6: byte5 = effect_speed
              AUFGEKLÄRT durch Analyse der echten App-JS (bundle.min.js,
              windows/background/bundle.min.js aus webapp.gpk): die
              Original-App validiert/nutzt für "light_speed" NUR die Werte
              0-3 (UI-Slider 0-3, invertiert auf Protokoll gemappt:
              UI 0->3, UI 1->2, UI 2->1, UI 3->0 im Quellcode). Das
              Firmware-Register akzeptiert zwar jeden Byte-Wert 0-255
              (Vollscan bestätigt), aber alles außerhalb 0-3 ist
              UNGETESTETES/UNDEFINIERTES Verhalten seitens des Herstellers.
              Live verifiziert für den offiziell genutzten Bereich:
                0  = schnell
                1  = mittel ("gemütlich, weder schnell noch langsam")
                2  = langsam
                3  = langsam (von 2 kaum unterscheidbar)
              Außerhalb 0-3 (4-255) verhält sich das Tempo nicht monoton
              und teils chaotisch (siehe Testreihe unten) - das ist
              erwartbares Verhalten für einen vom Hersteller nie
              validierten Wertebereich, keine geheime Zusatzfunktion:
                0x08        langsam  (~4s/Schritt)
                0x10        langsam  (~3s/Schritt)
                0x20        SEHR langsam (~5-7s/Schritt)
                0x30        langsam  (~2s/Schritt)
                0x40-0x80   schnell  (wieder wie 0x00)
                0x90-0xFF   langsam
              Empfehlung für llano-v12ultra-ctrl: Standardmäßig nur 0-3 anbieten
              (deckt sich mit der echten App), höhere Werte nur für
              Experimentierzwecke.
    Index  7: byte6 = brightness
              KORRIGIERT (erste Einschätzung "keine sichtbare Wirkung" war
              falsch - beruhte auf demselben Auto-Daemon-Kontaminations-
              problem wie bei byte2, siehe oben). Live mit gestopptem
              Daemon an 11 Messpunkten verifiziert: echter, SAUBER MONOTONER
              Helligkeits-Gradient (anders als effect_speed/byte5 - hier
              keine Anomalien, keine "Dellen" gefunden):
                0x00-0x02  = zu dunkel, wirkt wie ausgeschaltet
                0x04, 0x08 = sehr dunkel, aber sichtbar
                0x10       = dunkel
                0x20       = heller als 0x10
                0x40       = normal hell
                0x60       = heller als 0x40
                0x80       = heller als 0x60
                0xC0       = heller als 0x80
                0xFF       = maximal hell (Standardwert der echten App)
              Genaue Kurve/Stufenzahl zwischen den Messpunkten nicht
              exhaustiv vermessen, aber durchgängig monoton steigend
              bestätigt (11/11 Messpunkte konsistent).
    Index  8: checksum  =  (0xFF - sum(byte0..byte6)) & 0xFF

Send-vs-Read-Klassifikation (systematisch getestet: jedes Byte einzeln mit
einem markanten Testwert 0x2A beschrieben, Rest auf bekanntem Normalwert
gehalten, dann verglichen was zurückgelesen wird):

    byte0   reines Input  (liest immer 0x88, unabhängig vom Schreibwert)
    byte1   reines Input  (Rad-Telemetrie, unabhängig vom Schreibwert)
    byte2   reines Input  (Status-Code 0x00/0x01, kein Echo des Schreibwerts)
    byte3   Echo          (exakt das gelesen, was geschrieben wurde, auch
                           bei "ungültigen" Werten 5-0x7F)
    byte4   Echo mit Modulo-5-Wrap (siehe oben) - kein reines Echo, aber
            auch kein reines Input: der Schreibwert beeinflusst das
            Ergebnis nachweisbar, nur nicht 1:1
    byte5   Echo          (exakt das gelesen, was geschrieben wurde)
    byte6   Echo          (exakt das gelesen, was geschrieben wurde)

Damit bestätigt: es gibt tatsächlich einen Teil der 8 Bytes, der beim
Lesen etwas komplett anderes zeigt als das, was zuletzt geschrieben wurde
(byte0/byte1/byte2) - kein einheitliches Bild "Schreiben und Lesen sind
dasselbe Feld" über den ganzen Report hinweg.

Zusätzlich existiert im HID-Report-Descriptor ein 64-Byte Output-Report
und ein 64-Byte Input-Report (neben dem hier beschriebenen 8-Byte
Feature-Report). Beide wurden getestet (mehrere Schreibversuche mit
unterschiedlichen Mustern auf den Output-Report, u.a. Nullen, 0xFF, die
obige Feature-Struktur gespiegelt) - es wurde kein reproduzierbarer,
inhaltsabhängiger Effekt gefunden (zwei beobachtete kurze "Reset"-Blitze
traten nicht konsistent bei gleichem Inhalt auf). Zusammen mit dem Befund,
dass die reale App diesen Kanal laut vollständiger USB-Traffic-Aufzeichnung
nie benutzt, ist die wahrscheinlichste Erklärung ungenutztes
Boilerplate aus der Holtek-Referenzvorlage. Nicht erschöpfend getestet
(64 Bytes x 256 Werte ist nicht vollständig durchprobierbar) - also keine
100%ige Sicherheit, aber gut belegte Einschätzung.

NACHTRAG (gezielt zur Frage "kann man die Lüfterdrehzahl doch irgendwie
setzen?"): Live gegen echte Hardware zwei weitere, konkret begründete
Hypothesen getestet (device.py: write_output_report()), jeweils mit
Beobachtung von RPM-Anzeige/Displaywert am physischen Gerät durch den
Nutzer:
  1. Das komplette bekannte 8-Byte Feature-Report-Layout (aktuelle Farbe/
     Effekt/Speed/Helligkeit/Power) auf 64 Byte gepolstert auf den
     Output-Report geschrieben - Idee: manche Hersteller nutzen dasselbe
     Kommando-Layout über mehrere Report-Typen hinweg.
  2. Ein Byte aus dem gültigen fan_speed_raw-Wertebereich (hier: 100, das
     höchste Ende der Skala) einzeln an Position 1 und an Position 2
     geschrieben - Idee: symmetrisches Input/Output-Paar zur
     Telemetrie-Position im Feature-Report.
Beide ohne jede Wirkung: weder RPM-Wert im zurückgelesenen Feature-Report
verändert noch vom Nutzer am Display/Lüftergeräusch wahrnehmbar. Zusätzlich
wurde der komplette HID-Report-Descriptor ausgelesen (sysfs
`report_descriptor`) und bestätigt exakt 3 Reports ohne weitere
Report-IDs: 64-Byte Input, 64-Byte Output, 8-Byte Feature - keine
versteckte vierte Schnittstelle. Erhärtet die Einschätzung "Lüfterdrehzahl
ist eine reine Hardware-Grenze" weiter, macht sie aber weiterhin nicht zu
100% beweisbar (Wertebereich nicht erschöpfend durchprobiert). Vermutung:
das Einstellrad ist vermutlich ein rein analoges Poti/Rheostat direkt im
Lüfter-Stromkreis, der Holtek-Chip liest dessen Stellung nur für die
Telemetrie/Anzeige aus, hat aber keinen Aktuator, den er ansteuern könnte -
das würde erklären, warum keine der drei HID-Schnittstellen einen
Schreibpfad dafür hat.

NACHTRAG 2 (systematischer Sweep, 2026-08-10): Auf Wunsch des Nutzers ("gibt
es nicht noch mehr Optionen?") zusätzlich ein begründeter, aber deutlich
breiterer Test: alle 64 Byte-Positionen des Output-Reports EINZELN mit dem
Testwert 100 beschrieben (Rest der 64 Byte auf 0x00), nacheinander, mit
Zurücklesen des Feature-Reports nach jeder Position und Beobachtung von
Display/Lüfter durch den Nutzer. 0 von 64 Positionen zeigten irgendeine
Abweichung - weder im zurückgelesenen Feature-Report (RPM/Farbe/Effekt/
Speed/Helligkeit/Checksum unverändert) noch am physischen Gerät. Damit ist
mit einem einzelnen Testwert (100) an JEDER möglichen Byte-Position
mindestens einmal geprüft worden, ob dort überhaupt irgendeine Reaktion
existiert - kein vollständiger Beweis (andere Werte an derselben Position
oder Mehr-Byte-Kombinationen bleiben ungetestet), aber ein deutlich
stärkeres Indiz als die vorherigen 2 Stichproben. Verbleibende, nicht
verfolgte Option für noch mehr Sicherheit: das Gehäuse physisch öffnen und
nachsehen, ob das Rad tatsächlich ein reines Potentiometer ohne Aktuator
ist.

NACHTRAG 3 (pcap-Neuanalyse + vollständiger Fuzz, 2026-08-10): Die erste
pcap-Analyse (siehe Nachtrag 2) scheiterte an falschen tshark-Feldnamen
(`usb.setup.bRequest` statt des für HID-Class-Requests tatsächlich
genutzten `usbhid.setup.bRequest`). Mit den korrekten Feldnamen wurde die
GESAMTE 460MB-Aufzeichnung sauber ausgewertet: **1306 SET_REPORT- und 1300
GET_REPORT-Aufrufe der echten App**, ausschließlich an die beiden
bestätigten Holtek-USB-Adressen dieser Aufzeichnung, **alle mit
Report-Typ Feature (0x03) und wLength=8** (passt exakt zum bekannten
8-Byte-Body) - **null Aufrufe mit Report-Typ Output oder Input**. Das ist
eine Ganzdatei-Bestätigung über >1300 echte Nutzerinteraktionen hinweg,
nicht nur eine Stichprobe: die Original-App nutzt den Output-Report
nachweislich nie.

Zusätzlich auf ausdrücklichen Wunsch des Nutzers (der dem Risiko bewusst
zugestimmt hat, samt bekannter Recovery-Methode per Replug) ein
VOLLSTÄNDIGER Sweep aller 64 Positionen x aller 256 Werte (16384
Schreib-Lese-Zyklen, device.py/write_output_report()) durchgeführt: **0
anhaltende Abweichungen** im zurückgelesenen Feature-Report, Gerät danach
unverändert im Ausgangszustand, keine USB-Rebinds. Das deckt den
gesamten Wertebereich jeder Einzelposition vollständig ab (Mehr-Byte-
Kombinationen bleiben weiterhin ungetestet, wären aber 256^64 - praktisch
nicht durchprobierbar).

Dabei aber ein echter, reproduzierbarer Nebenbefund: **jeder** Schreib-
vorgang auf den Output-Report löst am Gerät einen kurzen sichtbaren
Blitz/Strobo aus - unabhängig vom geschriebenen Inhalt. Gezielt mit 4
isolierten Einzelschreibvorgängen (alles 0x00, alles 0xFF, wieder alles
0x00, ein einzelnes Byte an Position 5) im Abstand von je 3 Sekunden
nachgetestet: 4 von 4 mal vom Nutzer bestätigt beobachtet. Das klärt die
in Nachtrag 1 erwähnten "zwei beobachteten kurzen Reset-Blitze, die nicht
konsistent bei gleichem Inhalt auftraten" endgültig auf - sie sind gar
nicht inhaltsabhängig, sondern eine reine Empfangs-Nebenwirkung der
Firmware (vermutlich ein interner Reset/Re-Init-Zyklus, der bei jedem
eingehenden Output-Report ausgelöst wird). Kein steuerbarer Lichteffekt,
kein Hinweis auf einen Fan-Speed-Schreibpfad - bestätigt im Gegenteil,
dass der Channel technisch "lebt" (die Firmware reagiert auf den Empfang),
inhaltlich aber weiterhin ohne erkennbare Funktion ist.

Gesamtfazit nach allen bisherigen Tests: Lüfterdrehzahl per Software zu
setzen ist nach aktuellem Kenntnisstand nicht möglich. Einzige verbleibende
Methode für noch mehr Gewissheit wäre die physische Inspektion des Rads
(siehe oben).

NACHTRAG 4 (Original-App zerlegt, 2026-08-10): Auf die Frage "müsste das
nicht mit der Original-Hardware/-Software funktionieren?" wurde die echte
Myth.Cool-App (`MythCool.exe`, ~161MB, CEF-basierte Anwendung) sowie alle
zugehörigen Ressourcen statisch analysiert (rein lesend, keine
Geräte-Interaktion) - `.gpk`-Dateien sind unverschlüsselte, umbenannte
Electron-ASAR-Archive, direkt auslesbar.

Bestätigter Befund: In `windows/background/bundle.min.js` (aus
`webapp.gpk`) existiert echter Code (`setFanSpeed()`, Fan-Curve-
Interpolationstabelle, `checkV16Info()`), der `fan_speed` berechnet und
per `mythcool.usbcenter.SendInfo.promise(1, JSON.stringify({CMD:
"SetLapFanParam", fan_speed: ..., ...}))` verschicken will. Die native
Umsetzung von `mythcool.usbcenter` wurde in KEINEM von rund 15 geprüften
Binaries gefunden (String-Suche ASCII+UTF-16 in `MythCool.exe`,
`MythCoolLauncher.exe`, allen 9 lokal vorhandenen `.node`-Addons sowie
diversen GamePP-DLLs) - auch nicht in `BaseUtils64.node`
("GamePP-Utils-Addon"), obwohl genau dieses Modul als einziges echte
HID/WinUSB/SetupAPI/DeviceIoControl-Importe hat und damit der
architektonisch plausibelste Kandidat für echte USB-I/O wäre. Auch die
Hypothese eines separaten lokalen Server-Prozesses (nahegelegt durch
Namen wie `SparkServerAddon64.node`, `RunClient`) wurde geprüft und
verworfen - keine Websocket/localhost-Strings gefunden.

Zusätzlich in `mainui.gpk` (`Game_Home.js`, Produkt-/Modellauswahl-UI)
bestätigt: "V12 Ultra" ist ein echter, eigenständiger Produktname in der
Lokalisierungstabelle der App (`GreenGiantV12Ultra: "V12 Ultra Cooler"`,
in >10 Sprachen). Ein Name "V12 Pro" existiert dort NICHT - die frühere
Annahme, es gäbe eine separate "V12 Pro"-Variante mit anderem
Funktionsumfang, war ein Irrtum unsererseits, nicht durch die
Original-Software gestützt. Keine VID/PID-zu-Modell-Zuordnungstabelle
gefunden, die Rückschlüsse auf gerätespezifische Fähigkeiten erlauben
würde.

Wichtigster Befund bleibt aber unabhängig von alldem: der bereits in
Nachtrag 3 dokumentierte vollständige Pcap-Re-Analyse zeigt, dass die
Original-App bei 1305 echten Feature-Report-Schreibvorgängen 1304 mal
Byte 1 (die fan_speed-Position) auf 0x00 setzt - nur ein einziger
Ausreißer (0x0c/12) ohne eindeutigen Kontext, könnte ein Echo eines
zuvor gelesenen Telemetriewerts sein statt eine echte Regelabsicht.
Selbst WENN `SendInfo({CMD:"SetLapFanParam"})` bei aktivem Fan-Curve-
Feature tatsächlich einen Wert in Byte 1 schreiben würde: es träfe auf
exakt dasselbe Byte, das durch eigene Tests (15 gezielte Schreibversuche,
vollständiger 64x256-Fuzz) als hart read-only bestätigt ist. Die
Schlussfolgerung "Lüfterdrehzahl per Software setzen funktioniert auf
diesem physischen Gerät nicht" bleibt nach dieser zusätzlichen
Untersuchungsrunde unverändert bestehen - jetzt zusätzlich gestützt durch
die Erkenntnis, dass selbst die eigene App diesen Pfad in der
aufgezeichneten Nutzung praktisch nie mit einem echten Wert befüllt.

NACHTRAG 5 (finale Live-Bestätigung, 2026-08-10): `set_fan_speed()` mit
fünf über den gesamten Wertebereich verteilten Werten (1, 25, 50, 75, 100)
einzeln getestet, mit Nutzer-Beobachtung nach jedem Wert. Byte 1 im
zurückgelesenen Report blieb bei jedem der fünf Werte exakt identisch
(unverändert der reale Telemetriewert), keine Reaktion am Display oder
Lüfter. Damit war die Schlussfolgerung "Lüfterdrehzahl per Software setzen
funktioniert auf diesem Gerät nicht" zu diesem Zeitpunkt auch durch eine
frische, gezielte Live-Kontrolle bestätigt - siehe aber NACHTRAG 6, der
diese Schlussfolgerung wieder relativiert.

NACHTRAG 6 (offizielles Handbuch + echter Handler gefunden, 2026-08-10):
Das offizielle "Download and Usage Instructions"-PDF (von Amazon verlinkt)
zeigt Screenshots der echten Software mit **exakt unserer VID/PID**
(SN Code V162433, PID B101, VID 374A) und einer vollständigen
RPM-Mode-UI: "AI Intelligent Mode" (Low 300-1000rpm, Medium 600-2000rpm,
High 1000-2800rpm), "Custom Mode" (Temperatur-Fan-Curve-Editor), und
"Manual Mode" (explizit als "Roller Adjustment" bezeichnet, also nur das
physische Rad). Das ist ein deutlich stärkerer Beleg als vorher, dass die
Software-Steuerung für genau dieses Gerät gedacht ist, nicht für eine
andere SKU.

Zusätzlich wurde der reale native Handler gefunden: nicht in `MythCool.exe`
selbst, sondern in einem separaten Hilfsprozess `GPP_USB_Center.exe`
(`C:/ProgramData/GamePPPublic/UsbCenter/<version>/`, gestartet als
eigenständiger Prozess mit `/product=usbcenter`). Enthält eine C++-Klasse
`LJN_LAP_FAN` mit einer Methode, die per Disassemblierung (radare2)
bestätigt "SetLapFanParam" und "fan_speed" aus dem eingehenden JSON parst,
sowie echte `HidD_*`/`SetupAPI`/`DeviceIoControl`-Imports für echte
USB-Kommunikation. Der exakte `DeviceIoControl`-Aufrufpfad für das
geparste `fan_speed`-Feld konnte in der verfügbaren Zeit nicht bis zum
Ende zurückverfolgt werden (die Bibliothek ist ein großes, geteiltes
Multi-Geräte-USB-Framework).

Ein Live-Test unter Wine (App + `GPP_USB_Center.exe` tatsächlich
gestartet, USB-Traffic per usbmon/tshark live mitgeschnitten, während der
Nutzer versucht hat, "AI Low Mode" zu klicken) scheiterte an einem
GETRENNTEN Problem: Die App erkennt das Gerät unter Wine gar nicht (nur 8
USB-Pakete am Gerät während der gesamten Sitzung, kein einziger
HID-Kontaktversuch von `GPP_USB_Center.exe`) - vermutlich eine
unvollständige SetupAPI/WinUSB-Geräteerkennung in Wine, unabhängig vom
eigentlichen Fan-Speed-Protokoll.

**Revidiertes Fazit:** Die Aussage "Lüfterdrehzahl per Software setzen ist
nicht möglich" ist nach diesem Fund zu stark. Korrekter: die Original-Software
hat nachweislich echten, funktionsfähig aussehenden Code dafür (nicht nur
UI-Attrappe), spezifisch für dieses Gerät (VID/PID-Übereinstimmung im
Handbuch). Ob er auf der eigenen Hardware tatsächlich wirkt, konnte weder
durch eigene Byte-Level-Tests (die bislang immer wirkungslos blieben) noch
durch einen Live-Test unter Wine (Geräteerkennung schlug fehl) geklärt
werden. **Der einzige verbleibende schlüssige Test ist echtes Windows**
(reale Maschine oder VM mit funktionierendem USB-Passthrough), wo die
Geräteerkennung voraussichtlich funktioniert und der tatsächliche
USB-Traffic beim Klicken von "AI Low/Medium/High Mode" beobachtet werden
könnte.

NACHTRAG 7 (echter Windows-11-VM-Live-Test, 2026-08-10): Windows 11 unter
QEMU/KVM (libvirt, UEFI+TPM2.0, USB-Host-Passthrough des Pads) installiert,
echte `MythCool`-App darin installiert und bedient, USB-Traffic per
usbmon/tshark auf dem Host live mitgeschnitten (siehe `research/`).
Anders als unter Wine wurde das Gerät in der VM erkannt, die App zeigte die
volle RPM-Mode-UI und ließ alle Modi anklicken.

Ergebnis der Aufzeichnung (193 echte HID-Feature-Report-Aufrufe an das
Gerät, `research/analyze_capture.py`): Byte 1 (fan_speed-Position) war in
191 der 193 Aufrufe exakt 0x00. In den übrigen 2 Aufrufen stand dort 0x14
(20) - das sah zunächst nach einem echten Schreibversuch aus, ließ sich
aber durch direkten Hex-Vergleich mit der unmittelbar vorausgehenden
GET_REPORT-Antwort widerlegen: der Wert 0x14 stand bereits in der
*gelesenen* Telemetrie, bevor die App ihn zurückschrieb. Es handelt sich um
ein Echo (die App liest den aktuellen Radstand und schreibt ihn beim
nächsten Report unverändert zurück, z.B. weil Farbe/Power in diesem Moment
geändert wurden - der Nutzer bestätigte, zu diesem Zeitpunkt die Farbe
umgestellt und das Gerät neu gestartet zu haben, nicht einen RPM-Modus
angeklickt). Kein einziger der 193 Aufrufe enthielt einen *neuen*,
gezielten fan_speed-Wert. Output-Report-Traffic (Interrupt-OUT) blieb wie
in allen bisherigen Aufzeichnungen bei 0.

Zusätzliche, vom Nutzer während der Bedienung selbst beobachtete Evidenz:
dreht man am physischen Rad, während in der App ein AI-/Custom-Modus
ausgewählt ist, springt die UI automatisch auf "Manual Mode" zurück. Das
bestätigt unabhängig, dass die App Byte 1 aktiv als Live-Telemetrie liest
und auswertet (nicht nur beim Start abfragt) - der *Lesepfad* funktioniert
also nachweislich und wird von der echten Software genutzt.

Ein geplanter Folgetest (CPU-Stresstest in der VM, um der Fan-Curve-Logik
über "AI Mode" eine Temperaturänderung vorzugaukeln und so einen echten
Schreibversuch zu provozieren) wurde nicht ausgewertet: der Nutzer stellte
fest, dass die Hardware-Status-Anzeige der App in der VM eingefroren war
(kein dynamisches Sensor-Passthrough unter QEMU/KVM) - die Fan-Curve-Logik
bekommt in einer VM also unabhängig von echter CPU-Auslastung nie eine sich
ändernde Temperatur zu sehen, ein Stresstest kann daher keinen Schreib-
versuch auslösen, egal wie stark die virtuelle CPU ausgelastet wird. Das
ist eine grundsätzliche Grenze von VM-basiertem Testen für dieses Feature,
keine Eigenschaft des Geräts oder Protokolls.

**Finales Fazit:** Über drei unabhängige Testebenen (eigene Byte-Level-
Tests am realen Gerät, Wine-Live-Test, echter Windows-11-Live-Test mit
funktionierender Geräteerkennung) wurde nie ein einziger SET_REPORT mit
einem neuen, gezielten fan_speed-Wert beobachtet - weder von unserem
eigenen Code noch von der Original-App. Der Original-App-Code (`LJN_LAP_FAN`,
siehe NACHTRAG 6) parst `fan_speed` zwar nachweislich aus dem JSON, aber ob
dieser Wert auf diesem konkreten Geräte-Modell tatsächlich in einen
USB-Schreibbefehl umgesetzt wird, konnte im Beobachtungszeitraum nie erhärtet
werden - vermutlich weil `GPP_USB_Center.exe` eine geteilte Multi-Geräte-
Bibliothek ist und dieses Board keinen PWM-Aktuator besitzt, den der
Handler ansteuern könnte (das würde auch erklären, warum das Lüfterrad rein
mechanisch/passiv per Hand drehbar ist statt motorisiert). Ein wirklich
abschließender Test bräuchte eine echte physische Windows-Maschine mit
funktionierenden Sensoren, um "AI Mode" unter echter Temperaturänderung zu
beobachten - das war im Rahmen dieser Untersuchung nicht mehr sinnvoll
umsetzbar. `set_fan_speed()` bleibt aus Kompatibilitätsgründen im Code,
ist aber sowohl in der CLI-Hilfe als auch in der GUI klar als "ohne
nachgewiesene Wirkung auf dieser Hardware" gekennzeichnet.

NACHTRAG 8 (DURCHBRUCH - echtes eigenes Fan-Kommando gefunden, 2026-08-10):
NACHTRAG 7 wurde noch am selben Tag widerlegt. Test auf einer ECHTEN
physischen Windows-10-Maschine (nicht VM - kein Sensor-Blocker mehr) via
SSH-Fernsteuerung, USBPcap/Wireshark-Live-Capture auf beiden USB-Root-Hubs,
während der Nutzer in der echten App eigene Lüfterkurven/-drehzahlen
eingestellt hat. Ergebnis: Drehzahl änderte sich nachweislich hör- und
sichtbar (auch auf dem Pad-Display) - UND im Capture erschienen zum ersten
Mal echte SET_REPORT-Aufrufe mit einer Vielzahl unterschiedlicher,
gezielter fan_speed-Werte (1, 14, 18, 21, 25, 36, 50, 57, 71, 98 - passend
zu den vom Nutzer gesetzten Kurvenpunkten).

Der Grund, warum das nie zuvor funktionierte: es ist ein KOMPLETT EIGENES
Kommando, keine Variante des Licht-Kommandos. Byte-Layout (7-Byte-Body vor
der Checksumme, gleiche Position/Formel wie beim Licht-Kommando):
  byte0 = 0x01 ("Lüfterdrehzahl jetzt setzen") bzw. 0x00 (periodische
          Bestätigung des aktuellen Werts, alle ~5s beobachtet) bzw. 0x80
          (reiner Herzschlag/Poll, byte1-6 alle 0)
  byte1 = Lüfterdrehzahl raw 1-100 (identische Skala wie fan_speed_raw
          beim Auslesen)
  byte2 = 0x00 (fest)
  byte3 = 0x00 (fest)
  byte4 = 0x02 (fest - Unterkommando-Kennung)
  byte5 = 0x00 (fest)
  byte6 = 0xff (fest)
  byte7 = Checksumme (gleiche Formel wie beim Licht-Kommando)

Das Licht-Kommando (build_report) nutzt zufällig ebenfalls byte0=0x00
(BYTE0_CONST), aber mit byte4=Farbe(0-4) statt der festen 0x02-Kennung und
byte1 dort komplett wirkungslos - genau DAS haben alle bisherigen Tests
(NACHTRAG 1-7) über Jahre hinweg geschrieben. Byte0=0x01 wird vom
Licht-Kommando nie verwendet und ist damit eindeutig/kollisionsfrei -
`build_fan_report()` nutzt deshalb ausschließlich 0x01 für einmalige
Set-Befehle.

`set_fan_speed()` in device.py wurde auf `build_fan_report()` umgestellt.

**Live auf dem eigenen Linux-Gerät verifiziert (2026-08-10):** Pad zurück an
den Linux-Host gesteckt, `llano-v12ultra-ctrl fan-speed <raw>` mit 50, 1 und
100 getestet. Bei jedem Wert bestätigte der Nutzer eine hör-/sichtbar
tatsächlich veränderte Drehzahl (raw=1 spürbar langsam, raw=100 "Vollgas").
Report-Readback stimmte danach jeweils exakt mit dem gesetzten raw-Wert und
der erwarteten U/min-Umrechnung überein (raw=1->300, raw=50->1500,
raw=100->2800 U/min). Damit ist die Lüfterdrehzahlsteuerung nach monatelanger
Untersuchung **endgültig als funktionierend bestätigt** - plattformunabhängig
über beide Betriebssysteme hinweg nachgewiesen (Protokoll gefunden unter
Windows, Wirkung bestätigt sowohl unter Windows als auch nativ unter Linux
über HIDIOCSFEATURE). Die frühere "nachweislich wirkungslos"-Einschätzung
(NACHTRAG 1-7) war korrekt für das getestete (falsche) Kommando, aber falsch
als Aussage über die Hardware selbst.

NACHTRAG 9 (Auflösung und Wertebereich ausgelotet, 2026-08-10): Zwei
Nachfolgetests direkt im Anschluss.

1. **Feinste nutzbare Auflösung**: alle 100 einzelnen raw-Werte (1-100)
   nacheinander gesetzt (nicht nur die 26 auf 100er-U/min-Stufen gerundeten
   Werte aus dem ersten Test) - der Nutzer bestätigte, dass sich die
   Drehzahl bei jedem einzelnen raw-Schritt tatsächlich änderte, in
   ca. 25 U/min-Schritten (2500 U/min Spanne / 99 Schritte ≈ 25,25). Das ist
   die real feinste ansteuerbare Auflösung - `raw` ist ein einzelnes Byte,
   es gibt keine feinere Zwischenstufe. Die zuvor dokumentierten "26 Stufen à
   100 U/min" waren nur eine Vereinfachung für die grobe RPM-Umrechnung,
   real reagiert die Hardware auf jeden einzelnen raw-Wert.

2. **Wertebereich über die dokumentierten 1-100 hinaus**: raw=0 sowie
   101/110/128/150/200/255 testweise gesetzt. Das Gerät nimmt jeden Wert bis
   255 anstandslos an und spiegelt ihn im Report unverändert zurück (auch im
   Pad-Display, das bei raw=255 einen extrapolierten Wert von ca. 6675 U/min
   anzeigte - `fan_rpm`-Formel in `Report` ist nur für 1-100 kalibriert,
   Werte darüber sind reine Extrapolation, keine echte Messung). Die
   **tatsächliche** Lüfterdrehzahl blieb laut Nutzer ab raw≈100 konstant auf
   dem echten Maximum (2800 U/min) stehen - Werte darüber ändern nur die
   Telemetrie/Anzeige, nicht die reale Drehzahl. `set_fan_speed()` bleibt
   deshalb bei der validierten Grenze 1-100 (siehe device.py), auch wenn das
   Feld selbst technisch bis 255 reicht.

Kurze Nebenfrage des Nutzers: ob sich durch schnelles/gezieltes Ansteuern
auch der Anzeigeinhalt selbst (nicht nur die Zahl) manipulieren ließe.
Unwahrscheinlich mit aktuellem Kenntnisstand - es gibt kein bekanntes
separates "Display-Inhalt setzen"-Kommando, die Anzeige scheint eine reine
Firmware-Berechnung aus dem einen raw-Byte zu sein. Nicht weiter verfolgt,
kein Beleg in irgendeiner Capture bisher.
"""

REPORT_LEN = 9  # report_id + 7 body bytes + checksum

BYTE0_CONST = 0x00

EFFECT_OFF = 0x80  # jeder Wert ab hier schaltet die Beleuchtung aus

COLOR_NAMES = {
    0: "red",
    1: "lightblue",
    2: "green",
    3: "purple",
    4: "orange",
}
NAME_TO_COLOR = {v: k for k, v in COLOR_NAMES.items()}

EFFECT_NAMES = {
    0: "solid",
    1: "breathing",
    2: "rainbow",
    3: "chase",
    4: "zones",
}
NAME_TO_EFFECT = {v: k for k, v in EFFECT_NAMES.items()}


def checksum(body7):
    """body7: 7 Bytes (byte0..byte6). Gibt das Checksum-Byte zurück."""
    return (0xFF - sum(body7)) & 0xFF


KILL_FLAG_OFF = 0x01  # jeder Wert != 0 wirkt identisch (reiner Ein/Aus-Schalter)


def build_report(color, effect=0, speed=0x00, light_on=True, brightness=0xFF, power=True, byte1=0x00):
    """Baut einen vollständigen 9-Byte-Report für HIDIOCSFEATURE.

    color:      0-4, RGB-Farbe (siehe COLOR_NAMES)
    effect:     0-4, Lichteffekt (siehe EFFECT_NAMES) - wird ignoriert wenn
                light_on=False
    speed:      0-255, Effekt-Geschwindigkeit (0=schnell, 255=langsam)
    light_on:   False schaltet NUR die Beleuchtung aus (schreibt EFFECT_OFF
                in byte3), Lüfter läuft unbeeinflusst weiter
    brightness: 0-255, Helligkeit (0=dunkel/unsichtbar, 255=maximal hell)
    power:      False schaltet die GESAMTE Einheit aus - Beleuchtung UND
                Lüftermotor (schreibt byte2/kill_flag). Reiner Ein/Aus-
                Schalter, keine Zwischenstufen.
    byte1:      wird mitgeschickt (wie von der echten App beobachtet), hat
                aber KEINE Wirkung auf die Lüftergeschwindigkeit - dafür gibt
                es ein eigenes Kommando, siehe build_fan_report() (NACHTRAG 8).
    """
    effect_byte = EFFECT_OFF if not light_on else (effect & 0xFF)
    body7 = [
        BYTE0_CONST,
        byte1 & 0xFF,
        KILL_FLAG_OFF if not power else 0x00,
        effect_byte,
        color & 0xFF,
        speed & 0xFF,
        brightness & 0xFF,
    ]
    return bytes([0x00] + body7 + [checksum(body7)])


# Eigenständiges Lüfterdrehzahl-Kommando, gefunden per Live-USB-Capture gegen
# die echte App auf echtem Windows (NACHTRAG 8). Kollidiert bewusst nie mit
# build_report(): byte0=0x01 wird vom Licht-Kommando (BYTE0_CONST=0x00) nie
# verwendet.
FAN_SET_BYTE0 = 0x01
FAN_SUBCOMMAND_TAG = 0x02  # fester Wert in byte4, unterscheidet vom Licht-Kommando


def build_fan_report(fan_raw):
    """Baut den 9-Byte-Report, der die Lüfterdrehzahl WIRKLICH setzt.

    fan_raw: 1-100, gleiche Skala wie Report.fan_speed_raw/fan_rpm beim
             Auslesen (raw=1 -> 300 U/min, raw=100 -> 2800 U/min).

    Byte-Layout (durch Live-Capture der echten App verifiziert):
      byte0 = 0x01 (Kommando "Lüfterdrehzahl setzen")
      byte1 = fan_raw
      byte2 = 0x00
      byte3 = 0x00
      byte4 = 0x02 (Unterkommando-Kennung)
      byte5 = 0x00
      byte6 = 0xff
      byte7 = Checksumme
    """
    body7 = [FAN_SET_BYTE0, fan_raw & 0xFF, 0x00, 0x00, FAN_SUBCOMMAND_TAG, 0x00, 0xFF]
    return bytes([0x00] + body7 + [checksum(body7)])


class Report:
    """Geparste Sicht auf einen 9-Byte-Feature-Report."""

    __slots__ = ("raw", "fan_speed_raw", "kill_flag_raw", "effect_raw", "color", "speed", "brightness", "checksum_ok")

    def __init__(self, raw: bytes):
        if len(raw) < REPORT_LEN:
            raise ValueError(f"Report zu kurz: {len(raw)} Bytes, erwarte {REPORT_LEN}")
        self.raw = bytes(raw[:REPORT_LEN])
        body7 = list(self.raw[1:8])
        self.fan_speed_raw = self.raw[2]
        self.kill_flag_raw = self.raw[3]
        self.effect_raw = self.raw[4]
        self.color = self.raw[5]
        self.speed = self.raw[6]
        self.brightness = self.raw[7]
        self.checksum_ok = self.raw[8] == checksum(body7)

    @property
    def light_on(self):
        return self.effect_raw < EFFECT_OFF

    @property
    def power_on(self):
        """False = gesamte Einheit (Lüfter + Licht) per kill_flag (byte2)
        ausgeschaltet."""
        return self.kill_flag_raw == 0x00

    @property
    def fan_rpm(self):
        """Grob auf 100er-Schritte gerundete U/min-Anzeige (300-2800), raw-Bereich
        1-100. Gegen die eigene Pad-Anzeige verifiziert (raw=1->300, raw=48->1500,
        raw=100->2800, alle 3 exakt getroffen). ACHTUNG: das ist nur eine grobe
        Rundung für die Anzeige - die tatsächliche Hardware reagiert auf jeden
        einzelnen raw-Wert mit ca. 25 U/min Schritt (siehe protocol.py NACHTRAG 9,
        Feinstufen-Test über alle 100 raw-Werte)."""
        level = round((self.fan_speed_raw - 1) * 25 / 99)
        return 300 + level * 100

    def color_name(self):
        return COLOR_NAMES.get(self.color, f"unbekannt({self.color})")

    def effect_name(self):
        if not self.light_on:
            return "off"
        return EFFECT_NAMES.get(self.effect_raw, f"unbekannt({self.effect_raw})")

    def __repr__(self):
        return (
            f"Report(raw={self.raw.hex(' ')}, fan_rpm={self.fan_rpm}, "
            f"color={self.color} [{self.color_name()}], "
            f"effect={self.effect_raw} [{self.effect_name()}], speed={self.speed}, "
            f"brightness={self.brightness}, checksum_ok={self.checksum_ok})"
        )
