#!/usr/bin/env bash
# Richtet eine Windows-VM (QEMU/KVM via libvirt) ein, um die echte Myth.Cool-
# App gegen das llano V12 Ultra Pad zu testen - als letzter, schlüssiger Test
# nachdem sowohl eigene Byte-Level-Tests als auch ein Wine-Live-Test
# (Geräteerkennung schlug fehl) keine endgültige Antwort liefern konnten.
# Siehe src/llano_v12ultra_ctrl/protocol.py NACHTRAG 6.
#
# Nutzung:
#   1. Windows-ISO besorgen (siehe unten, "ISO BESCHAFFEN")
#   2. ./setup_windows_vm.sh create /pfad/zur/windows.iso
#   3. VM installieren (virt-viewer öffnet sich automatisch), normale
#      Windows-Installation durchlaufen lassen
#   4. Nach der Installation: ./setup_windows_vm.sh attach-usb
#      (steckt das Pad in die laufende VM durch)
#   5. In der VM: MythCool_Latest.exe installieren (liegt bereits unter
#      ~/Downloads/MythCool_Latest.exe - per virt-manager-Dateifreigabe oder
#      USB-Stick/SMB in die VM kopieren) und starten
#   6. Auf dem HOST parallel: ./setup_windows_vm.sh capture
#      (schneidet USB-Traffic mit, während du in der VM auf "AI Low Mode"
#      klickst - Strg+C zum Beenden)
#   7. ./setup_windows_vm.sh analyze <capture.pcap>
#      (wertet die Aufzeichnung mit den bereits korrekt bekannten
#      tshark-Feldnamen aus, siehe protocol.py NACHTRAG 3 für den Hintergrund)
#
# WICHTIG: Vor jedem Passthrough-Versuch sicherstellen, dass unser eigener
# Dienst NICHT auf das Gerät zugreift:
#   systemctl --user stop llano-v12ultra-ctrl.service

set -euo pipefail

VM_NAME="mythcool-win-test"
VID="0x374a"
PID="0xb101"
DISK_SIZE_GB=40
RAM_MB=4096
VCPUS=2

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<EOF
Verwendung: $0 <befehl> [argumente]

Befehle:
  create <iso-pfad>     Neue Windows-VM erstellen und Installation starten
  attach-usb            Pad (374a:b101) in die laufende VM durchstecken
  detach-usb            Pad wieder vom Host freigeben (VM behält keinen Zugriff mehr)
  capture [ausgabe.pcap] Live-USB-Traffic auf dem Host mitschneiden (Strg+C zum Beenden)
  analyze <capture.pcap> Aufzeichnung auf SET_REPORT/GET_REPORT/Output-Traffic auswerten
  status                 VM- und USB-Status anzeigen
  destroy                VM komplett löschen (inkl. virtueller Festplatte!)

ISO BESCHAFFEN (manuell, kein automatischer Download - Microsoft erfordert
Browser/ToS-Bestätigung):
  Windows 11: https://www.microsoft.com/de-de/software-download/windows11
  Windows 10: https://www.microsoft.com/de-de/software-download/windows10
  ("Installationsmedien erstellen" -> ISO-Datei, ca. 5-6GB)
EOF
}

cmd_create() {
  local iso_path="$1"
  if [ ! -f "$iso_path" ]; then
    echo "Fehler: ISO nicht gefunden: $iso_path" >&2
    exit 1
  fi
  echo "Erstelle VM '$VM_NAME' (${RAM_MB}MB RAM, ${VCPUS} vCPUs, ${DISK_SIZE_GB}GB Disk)..."
  virt-install \
    --name "$VM_NAME" \
    --memory "$RAM_MB" \
    --vcpus "$VCPUS" \
    --disk size="$DISK_SIZE_GB",format=qcow2 \
    --cdrom "$iso_path" \
    --os-variant win10 \
    --network network=default,model=e1000e \
    --graphics spice \
    --video qxl \
    --channel spicevmc \
    --sound ich9 \
    --noautoconsole
  echo "VM erstellt und gestartet. Fenster öffnen mit:"
  echo "  virt-viewer $VM_NAME &"
  echo "(oder virt-manager GUI verwenden)"
}

cmd_attach_usb() {
  echo "Hinweis: falls unser eigener Dienst noch läuft, jetzt stoppen:"
  echo "  systemctl --user stop llano-v12ultra-ctrl.service"
  read -p "Fortfahren? [j/N] " confirm
  if [[ "$confirm" != "j" && "$confirm" != "J" ]]; then
    exit 0
  fi
  local xml_file
  xml_file=$(mktemp --suffix=.xml)
  cat > "$xml_file" <<EOF
<hostdev mode='subsystem' type='usb' managed='yes'>
  <source>
    <vendor id='$VID'/>
    <product id='$PID'/>
  </source>
</hostdev>
EOF
  virsh attach-device "$VM_NAME" "$xml_file" --live
  rm -f "$xml_file"
  echo "Pad an VM '$VM_NAME' durchgesteckt. In der VM sollte es jetzt als USB-Gerät erscheinen."
}

cmd_detach_usb() {
  local xml_file
  xml_file=$(mktemp --suffix=.xml)
  cat > "$xml_file" <<EOF
<hostdev mode='subsystem' type='usb' managed='yes'>
  <source>
    <vendor id='$VID'/>
    <product id='$PID'/>
  </source>
</hostdev>
EOF
  virsh detach-device "$VM_NAME" "$xml_file" --live
  rm -f "$xml_file"
  echo "Pad wieder vom Host freigegeben."
}

cmd_capture() {
  local out="${1:-$SCRIPT_DIR/live_windows_capture.pcap}"
  echo "Lade usbmon-Kernelmodul (falls nötig)..."
  sudo modprobe usbmon 2>/dev/null || true
  local bus
  bus=$(lsusb | grep -i "374a:b101" | awk '{print $2}' || true)
  if [ -z "$bus" ]; then
    echo "WARNUNG: Pad aktuell nicht auf dem Host sichtbar (evtl. schon an VM durchgereicht - das ist ok, usbmon sieht trotzdem den Bus-Traffic)."
    bus="1"
  fi
  echo "Schneide USB-Bus $bus mit (usbmon${bus}) mit, Ausgabe: $out"
  echo "Jetzt in der Windows-VM die App bedienen (AI Low/Medium/High Mode klicken)."
  echo "Strg+C zum Beenden der Aufzeichnung."
  sudo tcpdump -i "usbmon${bus}" -w "$out"
  sudo chown "$(id -u):$(id -g)" "$out"
  echo "Aufzeichnung gespeichert: $out"
  echo "Auswerten mit: $0 analyze $out"
}

cmd_analyze() {
  local pcap="$1"
  if [ ! -f "$pcap" ]; then
    echo "Fehler: Datei nicht gefunden: $pcap" >&2
    exit 1
  fi
  python3 "$SCRIPT_DIR/analyze_capture.py" "$pcap"
}

cmd_status() {
  echo "=== VM-Status ==="
  virsh list --all | grep "$VM_NAME" || echo "VM '$VM_NAME' existiert nicht"
  echo "=== USB-Gerät (Host-Sicht) ==="
  lsusb | grep -i "374a:b101" || echo "Pad nicht auf dem Host sichtbar (evtl. an VM durchgereicht)"
}

cmd_destroy() {
  read -p "VM '$VM_NAME' WIRKLICH komplett löschen inkl. Festplatte? [j/N] " confirm
  if [[ "$confirm" == "j" || "$confirm" == "J" ]]; then
    virsh destroy "$VM_NAME" 2>/dev/null || true
    virsh undefine "$VM_NAME" --remove-all-storage
  fi
}

case "${1:-}" in
  create) cmd_create "${2:?ISO-Pfad fehlt}" ;;
  attach-usb) cmd_attach_usb ;;
  detach-usb) cmd_detach_usb ;;
  capture) cmd_capture "${2:-}" ;;
  analyze) cmd_analyze "${2:?Pcap-Pfad fehlt}" ;;
  status) cmd_status ;;
  destroy) cmd_destroy ;;
  *) usage; exit 1 ;;
esac
