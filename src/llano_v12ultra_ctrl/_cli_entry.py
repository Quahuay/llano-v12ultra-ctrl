"""Thinner Einstieg für cx_Freeze (MSI-Build).

cli.py verwendet relative Importe (`.device`, `.protocol`, ...), die nur
innerhalb des Pakets funktionieren. cx_Freeze führt die Entry-Point-Datei
jedoch als `__main__` aus, wodurch relative Imports scheitern. Diese Datei
importiert absolut und übergibt an die existierende `main()`-Funktion.
"""

import sys

try:
    from llano_v12ultra_ctrl.cli import main
except ImportError:
    # Im Repo ohne installiertes Paket: PYTHONPATH auf src/ setzen und
    # direkt python -m llano_v12ultra_ctrl.cli verwenden.
    print("Error: llano_v12ultra_ctrl not found. Is the package installed?", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    sys.exit(main())
