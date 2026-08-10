"""Thinner Einstieg für cx_Freeze GUI (MSI-Build).

app.py verwendet relative Importe (``from .. import i18n``), die nur
innerhalb des Pakets funktionieren. cx_Freeze führt die Entry-Point-Datei
jedoch anders aus, wodurch relative Imports scheitern können.
"""

import sys

try:
    from llano_v12ultra_ctrl.gui.app import main
except ImportError:
    print("Error: llano_v12ultra_ctrl not found. Is the package installed?", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    sys.exit(main())
