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
                aber nachweislich keine Wirkung auf die Lüftergeschwindigkeit.
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
        """300-2800 U/min in 100er-Schritten (26 Stufen), raw-Bereich 1-100.
        Gegen die eigene Pad-Anzeige verifiziert (raw=1->300, raw=48->1500,
        raw=100->2800, alle 3 exakt getroffen)."""
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
