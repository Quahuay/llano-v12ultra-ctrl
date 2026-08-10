"""Thinner Einstieg für cx_Freeze (MSI-Build).

cli.py verwendet relative Importe (`.device`, `.protocol`, ...), die nur
innerhalb des Pakets funktionieren. cx_Freeze führt die Entry-Point-Datei
jedoch als `__main__` aus, wodurch relative Imports scheitern. Diese Datei
importiert absolut und übergibt an die existierende `main()`-Funktion.
"""

import sys
from llano_v12ultra_ctrl.cli import main

sys.exit(main())
