"""Thinner Einstieg für cx_Freeze GUI (MSI-Build).

app.py verwendet relative Importe (``from .. import i18n``), die nur
innerhalb des Pakets funktionieren. cx_Freeze führt die Entry-Point-Datei
jedoch anders aus, wodurch relative Imports scheitern können.
"""

import sys
from llano_v12ultra_ctrl.gui.app import main

sys.exit(main())
