"""Einstiegspunkt der v12pro-ctrl GUI (PyQt6).

PyQt6 wird bewusst erst innerhalb von main() importiert, damit die reine
CLI-Nutzung (v12pro-ctrl status/light/power/monitor/auto, cli.py) niemals
PyQt6 importieren oder installiert haben muss."""

import sys


def main():
    from PyQt6.QtWidgets import QApplication

    from .main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("v12pro-ctrl")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
