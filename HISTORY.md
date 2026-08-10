# Entwicklungsgeschichte: wie die Lüfterdrehzahl-Steuerung gefunden wurde

Diese Datei fasst zusammen, wie das Protokoll für `llano-v12ultra-ctrl` reverse-engineered wurde -
inklusive der Sackgassen unterwegs. Für die reine Nutzung ist das nicht nötig, siehe stattdessen
[README.md](README.md). Die vollständige Byte-für-Byte-Herleitung mit allen Messreihen steht als
Nachtrag-Docstring in [`protocol.py`](src/llano_v12ultra_ctrl/protocol.py).

## Ausgangslage

Das Pad hat keine Dokumentation zum HID-Protokoll. Ausgangspunkt war ein USB-Mitschnitt der
offiziellen Windows-App (Myth.Cool) sowie der HID-Report-Descriptor des Geräts selbst (drei
Reports: 64-Byte Input, 64-Byte Output, 8-Byte Feature).

## Licht, Farbe, Helligkeit: relativ schnell gefunden

Der 9-Byte-Feature-Report ließ sich über gezielte Vergleichstests (App-Einstellung ändern, Report
vorher/nachher vergleichen) für Farbe, Effekt, Effekt-Geschwindigkeit, Helligkeit und einen
Ein/Aus-Kill-Switch vollständig herleiten, inklusive der Checksummenformel.

## Lüfterdrehzahl: die lange Sackgasse

Die App zeigt eine volle RPM-Auswahl-UI (AI Low/Medium/High-Modi, eine Custom-Fan-Curve, Manual
Mode über das physische Rad). Der naheliegende erste Ansatz - ein zusätzliches Byte im
Licht-Report mitschreiben, das in echten App-Mitschnitten mal ungleich 0 war - erwies sich als
konsequent wirkungslos:

- Ein originaler USB-Mitschnitt der echten App enthielt über 1300 reale SET_REPORT-Aufrufe, aber
  keiner davon einen erkennbar gezielten Fan-Speed-Schreibversuch.
- Ein vollständiger Fuzz aller Output-Report-Positionen (alle Byte-Positionen x alle Werte) zeigte
  keine anhaltende Wirkung.
- Eine statische Analyse von `MythCool.exe`/`GPP_USB_Center.exe` fand echten, funktionsfähig
  aussehenden Code (`LJN_LAP_FAN`-Klasse, verarbeitet nachweislich ein `SetLapFanParam`/
  `fan_speed`-Kommando aus dem JSON) - das Feature ist also softwareseitig real angelegt, aber der
  genaue Übersetzungspfad zu USB blieb im Code nicht auffindbar.
- Ein Live-Test unter Wine scheiterte an einem separaten Problem: die App erkennt das Gerät unter
  Wine gar nicht.
- Ein Live-Test in einer Windows-11-VM (echtes USB-Passthrough) erkannte das Gerät zwar korrekt und
  zeigte die volle RPM-UI, aber auch dort kein einziger echter Fan-Speed-Schreibversuch - im
  Nachhinein erklärbar, weil dabei nur die temperaturabhängigen AI-Modi angeklickt wurden (nicht
  der manuelle Custom-Modus) und weil eine VM ohnehin keine echten, sich ändernden Sensorwerte
  liefert, die die AI-Logik zum Nachrechnen bringen würden.

## Der Durchbruch: echte Hardware, echter Klick im Custom-Modus

Ein SSH-fernsteuerbarer, echter (nicht virtueller) Windows-10-Rechner wurde aufgesetzt, USBPcap/
Wireshark installiert und eine Live-Capture parallel zu manueller Bedienung der echten App
mitgeschnitten - diesmal mit einer selbst gesetzten Custom-Lüfterkurve statt der AI-Modi. Ergebnis:
ein bis dahin unbeobachtetes, komplett eigenständiges HID-Kommando, klar unterscheidbar vom
Licht-Kommando (andere Byte-0-Kennung, festes Unterkommando-Tag). Rückblickend war das der Grund,
warum alle früheren Tests wirkungslos blieben: sie schrieben schlicht das falsche Kommando.

Live bestätigt - sowohl auf der Windows-Testmaschine als auch direkt am eigenen Linux-Gerät, über
den gesamten Wertebereich einzeln durchgetestet (jeder der 100 möglichen Rohwerte einzeln, ca.
25 U/min Auflösung pro Schritt).

## Nachträglich geprüft, aber nicht weiterverfolgt

- Werte über den dokumentierten Bereich hinaus (bis 255): Gerät nimmt sie an und zeigt sie an, aber
  die echte Drehzahl bleibt ab dem dokumentierten Maximum stehen - nur die Telemetrie rechnet ohne
  Begrenzung weiter.
- Ob sich der Anzeigeinhalt des Pad-Displays selbst (nicht nur die angezeigte Zahl) gezielt
  manipulieren lässt: kein bekanntes separates Kommando dafür gefunden, nicht weiterverfolgt.
