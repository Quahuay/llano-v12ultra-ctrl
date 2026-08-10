# Windows-VM-Test: letzter offener Punkt der Fan-Speed-Untersuchung

Hintergrund: [`protocol.py`](../src/llano_v12ultra_ctrl/protocol.py) NACHTRAG 6. Die
Original-Software hat nachweislich echten Code (`GPP_USB_Center.exe`, Klasse `LJN_LAP_FAN`), der
`SetLapFanParam`/`fan_speed` aus dem JSON parst und echte HID/USB-Windows-APIs importiert - aber ob
das auf der eigenen Hardware tatsächlich wirkt, konnte weder durch eigene Byte-Level-Tests noch
durch einen Wine-Live-Test geklärt werden (die App erkennt das Gerät unter Wine gar nicht).

**Einziger verbleibender schlüssiger Test: echtes Windows.**

## Ablauf

```bash
# 1. Windows-ISO besorgen (manuell, siehe setup_windows_vm.sh für Links)
# 2. Eigenen Dienst stoppen, damit er nicht mit der VM ums Gerät konkurriert
systemctl --user stop llano-v12ultra-ctrl.service

# 3. VM erstellen und Windows installieren
./setup_windows_vm.sh create /pfad/zur/windows.iso

# 4. Nach der Windows-Installation: Pad durchstecken
./setup_windows_vm.sh attach-usb

# 5. In der VM: MythCool_Latest.exe installieren (liegt unter ~/Downloads/)
#    und starten, bis zur Geräteseite navigieren

# 6. Auf dem Host, WÄHREND du in der VM klickst:
./setup_windows_vm.sh capture

# 7. In der VM: "AI Low Mode" klicken, ein paar Sekunden warten,
#    dann "AI High Mode", dann "Custom Mode" mit einer Kurve testen.
#    Danach im Terminal Strg+C zum Beenden der Aufzeichnung.

# 8. Auswerten
./setup_windows_vm.sh analyze live_windows_capture.pcap
```

`analyze_capture.py` prüft automatisch:
- Ob Byte 1 (fan_speed-Position) in irgendeinem echten SET_REPORT-Aufruf ungleich 0 ist
- Ob überhaupt jemals Output-Report-Traffic (Interrupt-OUT) zum Gerät auftritt

Beides war in der bisherigen Aufzeichnung (siehe NACHTRAG 3) durchgängig negativ - falls sich das
unter echtem Windows ändert, ist das der gesuchte Beweis, dass es prinzipiell funktioniert (auch
wenn unsere eigenen Byte-1-Schreibversuche bisher wirkungslos blieben - dann bräuchte es vermutlich
eine andere Byte-Kombination oder eine Init-Sequenz, die wir noch nicht nachgebaut haben).

## Aufräumen

```bash
./setup_windows_vm.sh detach-usb   # Pad wieder für den eigenen Dienst freigeben
systemctl --user start llano-v12ultra-ctrl.service
./setup_windows_vm.sh destroy      # optional: VM komplett löschen
```
