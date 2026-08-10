"""Einstiegspunkt der llano-v12ultra-ctrl GUI (PyQt6).

PyQt6 wird bewusst erst innerhalb von main() importiert, damit die reine
CLI-Nutzung (llano-v12ultra-ctrl status/light/power/monitor/auto, cli.py) niemals
PyQt6 importieren oder installiert haben muss."""

import sys


def main():
    from PyQt6.QtWidgets import QApplication

    from .. import i18n

    # VOR dem Import von main_window, damit dessen Widget-Aufbau (Labels,
    # Button-Texte, ...) von Anfang an die richtige Sprache sieht - siehe
    # cli.py main() für dieselbe Reihenfolge-Überlegung.
    i18n.init_language()

    from .main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("llano-v12ultra-ctrl")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
