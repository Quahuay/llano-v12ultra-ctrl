"""Leichte Zusatz-Widgets für die llano-v12ultra-ctrl GUI.

Sparkline nutzt bewusst nur QPainter (kein zusätzliches Plotting-Package
wie pyqtgraph/matplotlib nötig) - reicht für einen einfachen RPM-Verlauf."""

from collections import deque

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QPainter, QPen
from PyQt6.QtWidgets import QWidget


class Sparkline(QWidget):
    """Minimalistischer Linienverlauf der letzten `maxlen` Werte."""

    def __init__(self, maxlen=400, parent=None):
        super().__init__(parent)
        self._values = deque(maxlen=maxlen)
        self.setMinimumHeight(50)
        self.setMinimumWidth(150)

    def add_value(self, value):
        self._values.append(value)
        self.update()

    def clear(self):
        self._values.clear()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.width(), self.height()

        if len(self._values) < 2:
            painter.end()
            return

        vmin, vmax = min(self._values), max(self._values)
        if vmax == vmin:
            vmax = vmin + 1  # Division durch 0 vermeiden bei konstantem Wert

        n = len(self._values)
        pen = QPen(Qt.GlobalColor.darkCyan)
        pen.setWidth(2)
        painter.setPen(pen)

        points = []
        for i, v in enumerate(self._values):
            x = i / (n - 1) * (width - 4) + 2
            y = height - 2 - (v - vmin) / (vmax - vmin) * (height - 4)
            points.append(QPointF(x, y))
        painter.drawPolyline(points)
        painter.end()
