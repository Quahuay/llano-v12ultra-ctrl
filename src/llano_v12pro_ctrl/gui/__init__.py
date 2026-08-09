"""PyQt6-Oberfläche für llano-v12pro-ctrl.

Bewusst getrennt vom Rest des Packages gehalten: cli.py/device.py/
protocol.py/config.py/temp.py haben keinerlei Abhängigkeit auf dieses
Unterpaket, sodass die reine CLI-Nutzung nie PyQt6 importieren oder
installiert haben muss. Siehe app.py für den Einstiegspunkt.
"""
