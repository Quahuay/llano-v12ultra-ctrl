#!/usr/bin/env python3
"""Analysiert eine usbmon-Aufzeichnung (pcap) auf HID-Traffic zum llano V12
Ultra Pad (374a:b101) - insbesondere ob SET_REPORT/GET_REPORT mit
Report-Typ Output vorkommt (bisher: nie beobachtet) und ob sich Byte 1
(fan_speed-Position) im Feature-Report jemals von 0x00 unterscheidet.

Nutzt die tshark-Feldnamen für HID-Class-Requests korrekt von Anfang an
(usbhid.setup.* statt der generischen usb.setup.*, siehe
src/llano_v12ultra_ctrl/protocol.py NACHTRAG 3 fuer den Hintergrund, warum
das beim ersten Versuch nicht auffiel).

Nutzung: analyze_capture.py <capture.pcap>
"""

import subprocess
import sys


def run_tshark(pcap_path, display_filter, fields):
    cmd = ["tshark", "-r", "-", "-T", "fields", "-E", "separator=;"]
    for f in fields:
        cmd += ["-e", f]
    if display_filter:
        cmd += ["-Y", display_filter]
    with open(pcap_path, "rb") as f:
        proc = subprocess.run(cmd, stdin=f, capture_output=True, text=True, timeout=600)
    if proc.returncode not in (0, None) and not proc.stdout:
        print("tshark stderr:", proc.stderr[:2000], file=sys.stderr)
    return [
        line.split(";")
        for line in proc.stdout.splitlines()
        if "cut short" not in line and line.strip()
    ]


REPORT_TYPE_NAMES = {1: "Input", 2: "Output", 3: "Feature"}


def main():
    if len(sys.argv) != 2:
        print(f"Nutzung: {sys.argv[0]} <capture.pcap>", file=sys.stderr)
        sys.exit(1)
    pcap = sys.argv[1]

    print("Schritt 1: Holtek-Sichtungen (idVendor==0x374a)...")
    sightings = run_tshark(pcap, "usb.idVendor==0x374a", ["frame.number", "usb.device_address"])
    print(f"  {len(sightings)} Treffer.")
    addrs = sorted({row[1] for row in sightings if len(row) > 1 and row[1]})
    print(f"  Beteiligte Geraete-Adressen: {addrs}")

    print("\nSchritt 2: alle SET_REPORT/GET_REPORT Aufrufe (usbhid.setup.bRequest 1 oder 9)...")
    hid_rows = run_tshark(
        pcap,
        "usbhid.setup.bRequest==1 || usbhid.setup.bRequest==9",
        ["frame.number", "usb.device_address", "usbhid.setup.bRequest", "usbhid.setup.wValue", "usbhid.setup.wLength", "usb.data_fragment"],
    )
    our_rows = [r for r in hid_rows if len(r) > 1 and r[1] in addrs]
    print(f"  {len(hid_rows)} HID-Class-Requests insgesamt, davon {len(our_rows)} an unser Geraet.")

    by_type = {}
    byte1_values = set()
    for r in our_rows:
        if len(r) < 4 or not r[3]:
            continue
        try:
            report_type = int(r[3], 16) >> 8
        except ValueError:
            continue
        by_type[report_type] = by_type.get(report_type, 0) + 1
        if r[2] in ("9", "0x09") and len(r) > 5 and r[5]:
            payload = bytes.fromhex(r[5])
            if len(payload) > 1:
                byte1_values.add(payload[1])

    print("\n  Verteilung nach Report-Typ:")
    for t, count in sorted(by_type.items()):
        print(f"    {REPORT_TYPE_NAMES.get(t, f'? ({t})')}: {count}")

    print(f"\n  Byte 1 (fan_speed-Position) Werte in SET_REPORT-Aufrufen: {sorted(byte1_values)}")
    if not byte1_values:
        print("  Keine SET_REPORT-Aufrufe mit auswertbarer Payload gefunden - keine Aussage moeglich.")
    elif byte1_values - {0}:
        print("  ACHTUNG: Byte 1 war mindestens einmal ungleich 0 - naeher untersuchen!")
    else:
        print("  Byte 1 war in allen gefundenen Aufrufen 0x00 (wie in der alten Aufzeichnung).")

    print("\nSchritt 3: Interrupt-OUT-Traffic (Output-Report-Kanal, sollte bisher immer 0 sein)...")
    intr_out = run_tshark(
        pcap,
        "usb.transfer_type==0x01 && usb.endpoint_address.direction==0",
        ["frame.number", "usb.device_address"],
    )
    our_intr_out = [r for r in intr_out if len(r) > 1 and r[1] in addrs]
    print(f"  {len(our_intr_out)} Interrupt-OUT-Pakete an unser Geraet.")
    if our_intr_out:
        print("  ACHTUNG: Output-Report-Traffic gefunden - das waere neu! Frames:", [r[0] for r in our_intr_out])
    else:
        print("  Keine Output-Report-Nutzung gefunden (wie bisher immer).")


if __name__ == "__main__":
    main()
