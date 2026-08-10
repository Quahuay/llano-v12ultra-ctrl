"""Leichte Zusatz-Widgets für die llano-v12ultra-ctrl GUI.

Sparkline und FanCurveEditor nutzen bewusst nur QPainter (kein zusätzliches
Plotting-Package wie pyqtgraph/matplotlib nötig) - reicht für einen
einfachen RPM-Verlauf bzw. einen interaktiven Punkte-Editor."""

from collections import deque

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen
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


class FanCurveEditor(QWidget):
    """Interaktiver Punkte-Editor für eine Temperatur->Lüfterdrehzahl-Kurve.

    - Ziehen eines Punkts: verschiebt ihn (Temperatur + Drehzahl).
    - Klick auf freie Fläche: fügt dort einen neuen Punkt ein.
    - Rechtsklick auf einen Punkt: entfernt ihn (mindestens ein Punkt bleibt
      immer erhalten).

    Emittiert `pointsChanged` nach jeder Änderung (Drag-Ende, Hinzufügen,
    Entfernen) - der Aufrufer liest den aktuellen Zustand über `points()`."""

    pointsChanged = pyqtSignal()

    TEMP_MIN, TEMP_MAX = 0, 110
    RAW_MIN, RAW_MAX = 1, 100
    HIT_RADIUS_PX = 9
    MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM = 36, 12, 10, 22

    def __init__(self, parent=None):
        super().__init__(parent)
        self._points = [{"temp_c": 30, "raw": 1}, {"temp_c": 85, "raw": 100}]
        self._drag_index = None
        self.setMinimumHeight(220)
        self.setMinimumWidth(300)
        self.setMouseTracking(True)
        self._hover_index = None

    # ------------------------------------------------------------- Zustand

    def set_points(self, points):
        self._points = sorted(
            ({"temp_c": int(p["temp_c"]), "raw": int(p["raw"])} for p in points),
            key=lambda p: p["temp_c"],
        ) or [{"temp_c": 50, "raw": 50}]
        self._drag_index = None
        self.update()

    def points(self):
        return [dict(p) for p in sorted(self._points, key=lambda p: p["temp_c"])]

    # ----------------------------------------------------- Koordinaten-Mapping

    def _plot_rect(self):
        return QRectF(
            self.MARGIN_LEFT, self.MARGIN_TOP,
            self.width() - self.MARGIN_LEFT - self.MARGIN_RIGHT,
            self.height() - self.MARGIN_TOP - self.MARGIN_BOTTOM,
        )

    def _value_to_pos(self, temp_c, raw):
        rect = self._plot_rect()
        x = rect.left() + (temp_c - self.TEMP_MIN) / (self.TEMP_MAX - self.TEMP_MIN) * rect.width()
        y = rect.top() + (self.RAW_MAX - raw) / (self.RAW_MAX - self.RAW_MIN) * rect.height()
        return QPointF(x, y)

    def _pos_to_value(self, x, y):
        rect = self._plot_rect()
        temp_c = (x - rect.left()) / rect.width() * (self.TEMP_MAX - self.TEMP_MIN) + self.TEMP_MIN
        raw = self.RAW_MAX - (y - rect.top()) / rect.height() * (self.RAW_MAX - self.RAW_MIN)
        temp_c = max(self.TEMP_MIN, min(self.TEMP_MAX, round(temp_c)))
        raw = max(self.RAW_MIN, min(self.RAW_MAX, round(raw)))
        return temp_c, raw

    def _index_near(self, pos):
        for i, p in enumerate(self._points):
            point_pos = self._value_to_pos(p["temp_c"], p["raw"])
            dx, dy = point_pos.x() - pos.x(), point_pos.y() - pos.y()
            if (dx * dx + dy * dy) ** 0.5 <= self.HIT_RADIUS_PX:
                return i
        return None

    # ----------------------------------------------------------------- Maus

    def mousePressEvent(self, event):
        pos = event.position()
        idx = self._index_near(pos)
        if event.button() == Qt.MouseButton.LeftButton:
            if idx is not None:
                self._drag_index = idx
            else:
                rect = self._plot_rect()
                if rect.contains(pos):
                    temp_c, raw = self._pos_to_value(pos.x(), pos.y())
                    self._points.append({"temp_c": temp_c, "raw": raw})
                    self._drag_index = len(self._points) - 1
                    self.pointsChanged.emit()
            self.update()
        elif event.button() == Qt.MouseButton.RightButton and idx is not None:
            if len(self._points) > 1:
                del self._points[idx]
                self.pointsChanged.emit()
                self.update()

    def mouseMoveEvent(self, event):
        pos = event.position()
        if self._drag_index is not None:
            rect = self._plot_rect()
            x = max(rect.left(), min(rect.right(), pos.x()))
            y = max(rect.top(), min(rect.bottom(), pos.y()))
            temp_c, raw = self._pos_to_value(x, y)
            self._points[self._drag_index]["temp_c"] = temp_c
            self._points[self._drag_index]["raw"] = raw
            self.update()
        else:
            new_hover = self._index_near(pos)
            if new_hover != self._hover_index:
                self._hover_index = new_hover
                self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_index is not None:
            self._drag_index = None
            self._points.sort(key=lambda p: p["temp_c"])
            self.pointsChanged.emit()
            self.update()

    # -------------------------------------------------------------- Zeichnen

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self._plot_rect()

        painter.fillRect(rect, QBrush(QColor(0, 0, 0, 15)))

        grid_pen = QPen(QColor(128, 128, 128, 90))
        painter.setPen(grid_pen)
        for temp_c in range(self.TEMP_MIN, self.TEMP_MAX + 1, 10):
            p1 = self._value_to_pos(temp_c, self.RAW_MIN)
            p2 = self._value_to_pos(temp_c, self.RAW_MAX)
            painter.drawLine(p1, p2)
            painter.drawText(QPointF(p1.x() - 8, rect.bottom() + 16), str(temp_c))
        for raw in range(0, 101, 20):
            raw_clamped = max(self.RAW_MIN, raw)
            p1 = self._value_to_pos(self.TEMP_MIN, raw_clamped)
            p2 = self._value_to_pos(self.TEMP_MAX, raw_clamped)
            painter.drawLine(p1, p2)
            painter.drawText(QPointF(2, p1.y() + 4), str(raw_clamped))

        painter.setPen(QPen(QColor(100, 100, 100)))
        painter.drawText(QPointF(rect.center().x() - 30, self.height() - 4), "Temperatur (°C)")

        pts_sorted = sorted(self._points, key=lambda p: p["temp_c"])
        if len(pts_sorted) >= 2:
            line_pen = QPen(Qt.GlobalColor.darkCyan)
            line_pen.setWidth(2)
            painter.setPen(line_pen)
            poly = [self._value_to_pos(p["temp_c"], p["raw"]) for p in pts_sorted]
            painter.drawPolyline(poly)

        for i, p in enumerate(self._points):
            pos = self._value_to_pos(p["temp_c"], p["raw"])
            is_active = i == self._drag_index or i == self._hover_index
            radius = 7 if is_active else 5
            painter.setPen(QPen(Qt.GlobalColor.darkCyan, 2))
            painter.setBrush(QBrush(QColor(0, 172, 193) if is_active else QColor(0, 150, 170)))
            painter.drawEllipse(pos, radius, radius)
            if is_active:
                painter.setPen(QPen(QColor(60, 60, 60)))
                painter.drawText(
                    QPointF(pos.x() + 10, pos.y() - 6),
                    f"{p['temp_c']}°C -> {p['raw']}",
                )

        painter.end()
