"""QThread-Wrapper um update_check.check_for_update() für die GUI.

update_check.py selbst ist bewusst Qt-unabhängig (auch von der CLI
genutzt) - ein rohes `threading.Thread` + Callback aus diesem Modul heraus
wäre aber unsicher, sobald der Callback GUI-Elemente anfasst (Qt-Widgets
dürfen nur aus dem GUI-Thread verändert werden). Deshalb hier ein
QThread mit einem pyqtSignal: Qt macht Signal-Emits über Thread-Grenzen
hinweg automatisch sicher (queued connection), solange der Empfänger ein
QObject im GUI-Thread ist - das ist hier MainWindow selbst."""

from PyQt6.QtCore import QThread, pyqtSignal

from .. import update_check


class UpdateCheckThread(QThread):
    finished_with_result = pyqtSignal(object)  # str (neue Version) oder None

    def run(self):
        result = update_check.check_for_update()
        self.finished_with_result.emit(result)
