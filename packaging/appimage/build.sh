#!/bin/bash
# Baut ein AppImage über einen eigenständigen venv statt über
# linuxdeploy-plugin-qt: PyQt6-pip-Wheels bringen bereits eine eigene,
# private Qt6-Kopie mit (deshalb das große Wheel) - linuxdeploy-plugin-qt
# ist auf C++/Qt-Apps ausgelegt und versteht PyQt6s Binärlayout nicht
# zuverlässig. Stattdessen: venv mit pip-PyQt6 bauen, komplett ins AppDir
# kopieren, linuxdeploy nur zum Bündeln der nativen libpython3-Abhängigkeit
# und zur AppImage-Erzeugung selbst nutzen.
#
# NICHT auf der Dev-Maschine getestet (weder python3-venv noch
# linuxdeploy/FUSE dort verfügbar, siehe Session-Notizen) - Build+Test läuft
# in der GitHub-Actions-Pipeline (ubuntu-latest), siehe
# .github/workflows/release.yml.
#
# Nutzung: packaging/appimage/build.sh [ziel-verzeichnis, default: dist/]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${1:-$REPO_ROOT/dist}"
WORK="$(mktemp -d)"
APPDIR="$WORK/AppDir"
mkdir -p "$APPDIR"
trap 'rm -rf "$WORK"' EXIT

VERSION="$(python3 -c "import sys; sys.path.insert(0, '$REPO_ROOT/src'); from llano_v12ultra_ctrl import __version__; print(__version__)")"

# --- Eigenständiger venv mit allen Abhängigkeiten (inkl. PyQt6) --------
python3 -m venv "$APPDIR/usr"
"$APPDIR/usr/bin/pip" install --no-cache-dir "$REPO_ROOT[gui]"

# --- AppDir-Struktur -----------------------------------------------------
mkdir -p "$APPDIR/usr/lib/udev/rules.d" "$APPDIR/usr/lib/systemd/user"
cp "$REPO_ROOT/packaging/70-llano-v12ultra-ctrl.rules" "$APPDIR/usr/lib/udev/rules.d/"
cp "$REPO_ROOT/systemd/llano-v12ultra-ctrl.service" "$APPDIR/usr/lib/systemd/user/"
cp "$REPO_ROOT/packaging/appimage/llano-v12ultra-ctrl.desktop" "$APPDIR/"
cp "$REPO_ROOT/packaging/icons/llano-v12ultra-ctrl.png" "$APPDIR/"
cp "$REPO_ROOT/packaging/appimage/AppRun" "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"

# --- linuxdeploy: native libpython3-Abhängigkeit bündeln + AppImage erzeugen ---
LINUXDEPLOY="$WORK/linuxdeploy-x86_64.AppImage"
curl -L -o "$LINUXDEPLOY" \
    https://github.com/linuxdeploy/linuxdeploy/releases/latest/download/linuxdeploy-x86_64.AppImage
chmod +x "$LINUXDEPLOY"

mkdir -p "$OUT_DIR"
( cd "$OUT_DIR" && "$LINUXDEPLOY" --appdir "$APPDIR" --output appimage )
mv "$OUT_DIR"/llano-v12ultra-ctrl*.AppImage "$OUT_DIR/llano-v12ultra-ctrl-${VERSION}-x86_64.AppImage"

echo "Built: $OUT_DIR/llano-v12ultra-ctrl-${VERSION}-x86_64.AppImage"
