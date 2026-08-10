#!/bin/bash
# Baut ein AppImage über einen eigenständigen venv. appimagetool packt den
# AppDir ohne weitere Dependency-Auflösung - PyQt6 (pip wheel) bringt seine
# eigene private Qt6-Kopie bereits mit.
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
ARCH="$(uname -m)"

# --- Eigenständiger venv mit allen Abhängigkeiten (inkl. PyQt6) --------
python3 -m venv "$APPDIR/usr"
"$APPDIR/usr/bin/pip" install --no-cache-dir "$REPO_ROOT[gui]"

# --- AppDir-Struktur -----------------------------------------------------
mkdir -p "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp "$REPO_ROOT/packaging/appimage/llano-v12ultra-ctrl.desktop" "$APPDIR/"
cp "$REPO_ROOT/packaging/appimage/llano-v12ultra-ctrl.desktop" "$APPDIR/usr/share/applications/"
cp "$REPO_ROOT/packaging/icons/llano-v12ultra-ctrl.png" "$APPDIR/"
cp "$REPO_ROOT/packaging/icons/llano-v12ultra-ctrl.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/"
cp "$REPO_ROOT/packaging/appimage/AppRun" "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"

# --- AppImage via appimagetool (gepinnter Release-Tag) --------------------
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"
APPIMAGETOOL="$WORK/appimagetool-${ARCH}.AppImage"
curl -fsSL -o "$APPIMAGETOOL" "$APPIMAGETOOL_URL"
chmod +x "$APPIMAGETOOL"

mkdir -p "$OUT_DIR"
ARCH="$ARCH" "$APPIMAGETOOL" "$APPDIR" "$OUT_DIR/llano-v12ultra-ctrl-${VERSION}-${ARCH}.AppImage"

echo "Built: $OUT_DIR/llano-v12ultra-ctrl-${VERSION}-${ARCH}.AppImage"
