#!/bin/sh
# Nach der .deb-Installation: udev-Regel scharfschalten, damit das Pad ohne
# Neustart ohne root nutzbar wird (siehe packaging/70-llano-v12ultra-ctrl.rules
# und README "udev rule"). "|| true": ein fehlschlagender udevadm-Aufruf
# (z.B. in einem Container ohne echtes udev) darf die Paketinstallation
# nicht abbrechen.
set -e

udevadm control --reload-rules || true
udevadm trigger || true

exit 0
