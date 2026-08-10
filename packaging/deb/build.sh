#!/bin/bash
# Baut ein .deb-Paket über fpm (dir-basiert, nicht fpm's Python-Sourcetyp -
# der ist über fpm-Versionen hinweg zu inkonsistent, ein manuell gestagtes
# Verzeichnis ist deterministischer). NICHT auf der Dev-Maschine getestet
# (kein fpm/ruby dort installiert, siehe Session-Notizen) - Build+Test
# läuft in der GitHub-Actions-Pipeline (ubuntu-latest), siehe
# .github/workflows/release.yml.
#
# Voraussetzungen im Build-Environment: fpm (`gem install --no-document fpm`).
#
# Nutzung: packaging/deb/build.sh [ziel-verzeichnis, default: dist/]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${1:-$REPO_ROOT/dist}"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

VERSION="$(python3 -c "import sys; sys.path.insert(0, '$REPO_ROOT/src'); from llano_v12ultra_ctrl import __version__; print(__version__)")"

# --- Verzeichnisstruktur ---------------------------------------------------
PYLIB="$STAGE/usr/lib/python3/dist-packages"
mkdir -p "$PYLIB" "$STAGE/usr/bin" "$STAGE/usr/lib/udev/rules.d" "$STAGE/usr/lib/systemd/user"

cp -r "$REPO_ROOT/src/llano_v12ultra_ctrl" "$PYLIB/"
find "$PYLIB/llano_v12ultra_ctrl" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
find "$PYLIB/llano_v12ultra_ctrl" -name '*.pyc' -delete 2>/dev/null || true
cp "$REPO_ROOT/packaging/70-llano-v12ultra-ctrl.rules" "$STAGE/usr/lib/udev/rules.d/"
cp "$REPO_ROOT/systemd/llano-v12ultra-ctrl.service" "$STAGE/usr/lib/systemd/user/"

cat > "$STAGE/usr/bin/llano-v12ultra-ctrl" <<'EOF'
#!/usr/bin/env python3
import sys
from llano_v12ultra_ctrl.cli import main
sys.exit(main())
EOF

cat > "$STAGE/usr/bin/llano-v12ultra-ctrl-gui" <<'EOF'
#!/usr/bin/env python3
import sys
from llano_v12ultra_ctrl.gui.app import main
sys.exit(main())
EOF

chmod +x "$STAGE/usr/bin/llano-v12ultra-ctrl" "$STAGE/usr/bin/llano-v12ultra-ctrl-gui"

# --- Paket bauen -------------------------------------------------------
mkdir -p "$OUT_DIR"
fpm -s dir -t deb \
    -n llano-v12ultra-ctrl \
    -v "$VERSION" \
    -C "$STAGE" \
    -p "$OUT_DIR/llano-v12ultra-ctrl_${VERSION}_all.deb" \
    --license MIT \
    --url "https://github.com/Quahuay/llano-v12ultra-ctrl" \
    --description "Native Linux control tool for the llano V12 Ultra USB-HID cooling pad (Myth.Cool / Holtek 374a:b101) - CLI + PyQt6 GUI" \
    --architecture all \
    --depends python3 \
    --depends python3-pyqt6 \
    --depends python3-plyer \
    --after-install "$REPO_ROOT/packaging/deb/postinst.sh" \
    usr=/

echo "Built: $OUT_DIR/llano-v12ultra-ctrl_${VERSION}_all.deb"
