"""llano-v12ultra-ctrl: natives Linux-Steuerungstool für das llano V12 Ultra Kühlpad
(Myth.Cool / Holtek USB-HID 374a:b101).

Siehe protocol.py für die Beschreibung des HID-Feature-Report-Layouts und
device.py für die Low-Level hidraw-Ansteuerung. gui/ enthält die optionale
PyQt6-Oberfläche (siehe gui/app.py), cli.py das Kommandozeilen-Interface.
"""

__version__ = "0.1.4"
