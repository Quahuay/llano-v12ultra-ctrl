"""Hauptfenster der llano-v12ultra-ctrl GUI: Live-Status + volle Steuerung des
llano V12 Ultra Kühlpads.

Nutzt device.py/protocol.py exakt wie cli.py - keine eigene Report- oder
HID-Logik. Live-Telemetrie läuft über einen QTimer (ioctls sind
sub-millisecond, ein eigener QThread ist dafür nicht nötig)."""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import config as config_mod
from .. import fan_curve as fan_curve_mod
from .. import i18n
from .. import profiles as profiles_mod
from .. import protocol
from . import device_worker, service_control
from .widgets import FanCurveEditor, Sparkline

POLL_INTERVAL_MS = 300  # wie cmd_monitor-Default (--interval 0.3)
RECONNECT_PROBE_MS = 2000  # langsamere Probe, solange kein Gerät gefunden wird
SERVICE_POLL_MS = 2000  # systemctl-Aufrufe sind teurer als ioctls, seltener pollen
RPM_HISTORY_LEN = 400  # bei 300ms Poll-Intervall ~2 Minuten Verlauf


def _speed_labels():
    # Als Funktion statt Modul-Konstante, damit hier bewusst erst zur
    # Aufrufzeit übersetzt wird (nach i18n.init_language() in app.py) statt
    # beim ersten Import des Moduls, dessen Zeitpunkt relativ zur
    # Spracheinstellung nicht garantiert ist.
    return {
        0: i18n.t("gui.speed_label.0"), 1: i18n.t("gui.speed_label.1"),
        2: i18n.t("gui.speed_label.2"), 3: i18n.t("gui.speed_label.3"),
    }


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(i18n.t("gui.window_title"))

        self._device = None  # device.Device | None (offen solange verbunden)
        self._last_report = None  # zuletzt gelesener protocol.Report
        self._auto_active = None  # bool | None (unbekannt bis erster Poll)

        self._build_ui()

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_device)
        self._poll_timer.start(POLL_INTERVAL_MS)

        self._service_timer = QTimer(self)
        self._service_timer.timeout.connect(self._poll_service)
        self._service_timer.start(SERVICE_POLL_MS)

        self._try_connect()
        self._poll_service()

    # ------------------------------------------------------------- UI-Aufbau

    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        root.addWidget(self._build_language_group())

        self.disconnect_banner = QLabel(i18n.t("gui.disconnect_banner"))
        self.disconnect_banner.setStyleSheet(
            "background-color: #b00020; color: white; padding: 6px; font-weight: bold;"
        )
        self.disconnect_banner.setVisible(False)
        root.addWidget(self.disconnect_banner)

        root.addWidget(self._build_status_group())
        root.addWidget(self._build_rpm_history_group())
        root.addWidget(self._build_control_group())
        root.addWidget(self._build_fan_speed_group())
        root.addWidget(self._build_profiles_group())
        root.addWidget(self._build_fan_curve_group())
        root.addWidget(self._build_auto_group())

        self.statusBar().showMessage(i18n.t("gui.status_bar.ready"))

    def _build_language_group(self):
        row = QHBoxLayout()
        row.addWidget(QLabel(i18n.t("gui.language.title") + ":"))
        self.language_combo = QComboBox()
        for lang in i18n.available_languages():
            self.language_combo.addItem(i18n.t(f"gui.language.{lang}"), lang)
        self.language_combo.blockSignals(True)
        idx = self.language_combo.findData(i18n.get_language())
        if idx >= 0:
            self.language_combo.setCurrentIndex(idx)
        self.language_combo.blockSignals(False)
        self.language_combo.currentIndexChanged.connect(self._change_language)
        row.addWidget(self.language_combo)
        row.addWidget(QLabel(i18n.t("gui.language.restart_hint")))
        row.addStretch()
        wrapper = QWidget()
        wrapper.setLayout(row)
        return wrapper

    def _change_language(self, _index):
        lang = self.language_combo.currentData()
        config_mod.save_language(lang)
        self.statusBar().showMessage(i18n.t("gui.language.restart_hint"), 8000)

    # Reihenfolge hier bestimmt die Zeilenreihenfolge in der Statustabelle.
    def _status_fields(self):
        return [
            (i18n.t("gui.status.field.device"), "lbl_path"),
            (i18n.t("gui.status.field.fan_speed"), "lbl_rpm"),
            (i18n.t("gui.status.field.power"), "lbl_power"),
            (i18n.t("gui.status.field.light"), "lbl_light"),
            (i18n.t("gui.status.field.color"), "lbl_color"),
            (i18n.t("gui.status.field.effect"), "lbl_effect"),
            (i18n.t("gui.status.field.speed"), "lbl_speed"),
            (i18n.t("gui.status.field.brightness"), "lbl_brightness"),
            (i18n.t("gui.status.field.raw"), "lbl_raw"),
            (i18n.t("gui.status.field.checksum"), "lbl_checksum"),
        ]

    def _build_status_group(self):
        box = QGroupBox(i18n.t("gui.status.title"))
        layout = QVBoxLayout(box)

        status_fields = self._status_fields()
        table = QTableWidget(len(status_fields), 2)
        table.horizontalHeader().hide()
        table.verticalHeader().hide()
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self._status_value_items = {}
        for row, (label_text, attr) in enumerate(status_fields):
            field_item = QTableWidgetItem(label_text)
            field_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            value_item = QTableWidgetItem("…")
            value_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            table.setItem(row, 0, field_item)
            table.setItem(row, 1, value_item)
            self._status_value_items[attr] = value_item

        table.resizeRowsToContents()
        total_height = table.horizontalHeader().height() + sum(
            table.rowHeight(r) for r in range(table.rowCount())
        ) + 4
        table.setFixedHeight(total_height)

        layout.addWidget(table)
        self.status_table = table
        return box

    def _build_rpm_history_group(self):
        box = QGroupBox(i18n.t("gui.rpm_history.title"))
        layout = QVBoxLayout(box)
        self.rpm_sparkline = Sparkline(maxlen=RPM_HISTORY_LEN)
        layout.addWidget(self.rpm_sparkline)
        return box

    def _build_control_group(self):
        box = QGroupBox(i18n.t("gui.control.title"))
        grid = QGridLayout(box)

        self.color_combo = QComboBox()
        for idx, name in protocol.COLOR_NAMES.items():
            self.color_combo.addItem(name, idx)
        self.color_combo.currentIndexChanged.connect(lambda _: self._write_light(light_on=True))

        self.effect_combo = QComboBox()
        for idx, name in protocol.EFFECT_NAMES.items():
            self.effect_combo.addItem(name, idx)
        self.effect_combo.currentIndexChanged.connect(lambda _: self._write_light(light_on=True))

        # Nur 0-3 anbieten: das ist der offiziell von der Original-App
        # validierte Bereich (siehe protocol.py) - höhere Werte verhalten
        # sich nicht monoton und sind hier bewusst nicht wählbar.
        speed_labels = _speed_labels()
        self.speed_combo = QComboBox()
        for idx in range(4):
            self.speed_combo.addItem(speed_labels[idx], idx)
        self.speed_combo.currentIndexChanged.connect(lambda _: self._write_light(light_on=True))

        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(255)
        self.brightness_slider.setValue(255)
        self.lbl_brightness_value = QLabel("255")
        self.brightness_slider.valueChanged.connect(
            lambda v: self.lbl_brightness_value.setText(str(v))
        )
        # Erst beim Loslassen schreiben, nicht bei jedem Pixel des Drags.
        self.brightness_slider.sliderReleased.connect(lambda: self._write_light(light_on=True))

        grid.addWidget(QLabel(i18n.t("gui.control.color")), 0, 0)
        grid.addWidget(self.color_combo, 0, 1)
        grid.addWidget(QLabel(i18n.t("gui.control.effect")), 1, 0)
        grid.addWidget(self.effect_combo, 1, 1)
        grid.addWidget(QLabel(i18n.t("gui.control.speed")), 2, 0)
        grid.addWidget(self.speed_combo, 2, 1)

        grid.addWidget(QLabel(i18n.t("gui.control.brightness")), 3, 0)
        brightness_row = QHBoxLayout()
        brightness_row.addWidget(self.brightness_slider)
        brightness_row.addWidget(self.lbl_brightness_value)
        grid.addLayout(brightness_row, 3, 1)

        button_row = QHBoxLayout()
        self.light_toggle_button = QPushButton(i18n.t("gui.control.light_on"))
        self.light_toggle_button.clicked.connect(self._toggle_light)
        self.power_button = QPushButton(i18n.t("gui.control.power_on"))
        self.power_button.clicked.connect(self._toggle_power)
        button_row.addWidget(self.light_toggle_button)
        button_row.addWidget(self.power_button)
        grid.addLayout(button_row, 4, 0, 1, 2)

        self.controls = [
            self.color_combo,
            self.effect_combo,
            self.speed_combo,
            self.brightness_slider,
            self.light_toggle_button,
            self.power_button,
        ]
        return box

    def _build_fan_speed_group(self):
        box = QGroupBox(i18n.t("gui.fan_speed.title"))
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        self.fan_speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.fan_speed_slider.setMinimum(1)
        self.fan_speed_slider.setMaximum(100)
        self.fan_speed_slider.setValue(1)
        self.lbl_fan_speed_value = QLabel("1")
        self.fan_speed_slider.valueChanged.connect(
            lambda v: self.lbl_fan_speed_value.setText(str(v))
        )
        self.fan_speed_apply_button = QPushButton(i18n.t("gui.fan_speed.apply"))
        self.fan_speed_apply_button.clicked.connect(self._apply_fan_speed)
        row.addWidget(self.fan_speed_slider)
        row.addWidget(self.lbl_fan_speed_value)
        row.addWidget(self.fan_speed_apply_button)
        layout.addLayout(row)

        self.controls.append(self.fan_speed_slider)
        self.controls.append(self.fan_speed_apply_button)
        return box

    def _build_profiles_group(self):
        box = QGroupBox(i18n.t("gui.profiles.title"))
        grid = QGridLayout(box)

        self.profile_name_labels = []
        self.profile_apply_buttons = []
        self.profile_save_buttons = []
        self.profile_delete_buttons = []

        for slot in range(profiles_mod.MAX_PROFILES):
            name_label = QLabel(i18n.t("gui.profiles.empty"))
            apply_button = QPushButton(i18n.t("gui.profiles.apply"))
            apply_button.clicked.connect(lambda _checked, s=slot: self._apply_profile(s))
            save_button = QPushButton(i18n.t("gui.profiles.save"))
            save_button.clicked.connect(lambda _checked, s=slot: self._save_profile(s))
            delete_button = QPushButton(i18n.t("gui.profiles.delete"))
            delete_button.clicked.connect(lambda _checked, s=slot: self._delete_profile(s))

            grid.addWidget(name_label, slot, 0)
            grid.addWidget(apply_button, slot, 1)
            grid.addWidget(save_button, slot, 2)
            grid.addWidget(delete_button, slot, 3)

            self.profile_name_labels.append(name_label)
            self.profile_apply_buttons.append(apply_button)
            self.profile_save_buttons.append(save_button)
            self.profile_delete_buttons.append(delete_button)

            # Anwenden/Speichern brauchen ein verbundenes Gerät (Anwenden
            # schreibt, Speichern liest den aktuellen Live-Zustand aus) -
            # Löschen ist reine Dateiverwaltung und bleibt immer bedienbar.
            self.controls.append(apply_button)
            self.controls.append(save_button)

        self._refresh_profile_labels()
        return box

    def _refresh_profile_labels(self):
        slots = profiles_mod.load_profiles()
        for slot, entry in enumerate(slots):
            has_entry = entry is not None
            self.profile_name_labels[slot].setText(entry["name"] if has_entry else i18n.t("gui.profiles.empty"))
            self.profile_delete_buttons[slot].setEnabled(has_entry)
            # Anwenden zusätzlich vom Slot-Inhalt abhängig machen, nicht nur
            # vom Verbindungsstatus (self.controls regelt Letzteres).
            self.profile_apply_buttons[slot].setProperty("has_entry", has_entry)
        self._sync_profile_apply_enabled()

    def _sync_profile_apply_enabled(self):
        connected = self._device is not None
        for slot, button in enumerate(self.profile_apply_buttons):
            has_entry = bool(button.property("has_entry"))
            button.setEnabled(connected and has_entry)

    def _apply_profile(self, slot):
        if self._device is None:
            return
        slots = profiles_mod.load_profiles()
        entry = slots[slot]
        if entry is None:
            return
        # Nochmal klemmen statt nur beim Speichern (siehe _save_profile):
        # set_light/set_fan_speed werfen sonst ein ValueError, das
        # device_worker.safe_call NICHT abfängt (nur DeviceNotFoundError/
        # OSError) - das würde unbehandelt aus diesem Button-Handler
        # rausfallen, z.B. bei einem profiles.json aus einer älteren
        # Version ohne diese Klemmung.
        color = max(0, min(4, entry["color"]))
        effect = max(0, min(4, entry["effect"]))
        fan_raw = max(1, min(100, entry["fan_raw"]))
        report, err = device_worker.safe_call(
            self._device,
            lambda dev: dev.set_light(
                color=color, effect=effect, speed=entry["speed"],
                light_on=entry["light_on"], brightness=entry["brightness"], power=entry["power"],
            ),
        )
        if report is None:
            self._set_disconnected(err)
            return
        report, err = device_worker.safe_call(
            self._device, lambda dev: dev.set_fan_speed(fan_raw)
        )
        if report is None:
            self._set_disconnected(err)
            return
        self._last_report = report
        self._update_status_labels(report)
        self._sync_controls(report)
        self.statusBar().showMessage(i18n.t("gui.profiles.apply_done", name=entry["name"]), 5000)

    def _save_profile(self, slot):
        if self._device is None or self._last_report is None:
            return
        slots = profiles_mod.load_profiles()
        existing_name = slots[slot]["name"] if slots[slot] else i18n.t("gui.profiles.default_name", n=slot + 1)
        name, ok = QInputDialog.getText(
            self, i18n.t("gui.profiles.save_dialog.title"), i18n.t("gui.profiles.save_dialog.label"),
            QLineEdit.EchoMode.Normal, existing_name,
        )
        if not ok or not name.strip():
            return
        r = self._last_report
        # Auf gültige Bereiche klemmen, BEVOR gespeichert wird: der Report
        # kann z.B. effect_raw außerhalb 0-4 zeigen, während die Beleuchtung
        # aus ist (siehe _sync_controls), und fan_speed_raw kann >100 sein,
        # wenn zuvor testweise ein Wert außerhalb 1-100 gesetzt wurde (siehe
        # protocol.py NACHTRAG 9). _apply_profile reicht diese Werte direkt
        # an set_light/set_fan_speed weiter, deren Validierung sonst ein
        # ValueError aus dem Button-Handler werfen würde - device_worker.
        # safe_call fängt nur DeviceNotFoundError/OSError ab, kein ValueError.
        settings = {
            "color": max(0, min(4, r.color)),
            "effect": max(0, min(4, r.effect_raw)),
            "speed": r.speed,
            "brightness": r.brightness,
            "light_on": r.light_on,
            "power": r.power_on,
            "fan_raw": max(1, min(100, r.fan_speed_raw)),
        }
        profiles_mod.save_profile(slot, name.strip(), settings)
        self._refresh_profile_labels()
        self.statusBar().showMessage(i18n.t("gui.profiles.save_done", name=name.strip()), 5000)

    def _delete_profile(self, slot):
        slots = profiles_mod.load_profiles()
        if slots[slot] is None:
            return
        reply = QMessageBox.question(
            self, i18n.t("gui.profiles.delete_dialog.title"),
            i18n.t("gui.profiles.delete_dialog.text", name=slots[slot]["name"]),
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        profiles_mod.delete_profile(slot)
        self._refresh_profile_labels()

    def _build_fan_curve_group(self):
        box = QGroupBox(i18n.t("gui.fan_curve.title"))
        layout = QVBoxLayout(box)

        self.fan_curve_enabled_checkbox = QCheckBox(i18n.t("gui.fan_curve.enable"))
        layout.addWidget(self.fan_curve_enabled_checkbox)

        hint = QLabel(i18n.t("gui.fan_curve.hint"))
        hint.setStyleSheet("color: #808080; font-size: 11px;")
        layout.addWidget(hint)

        self.fan_curve_graph = FanCurveEditor()
        self.fan_curve_graph.pointsChanged.connect(self._on_curve_graph_changed)
        layout.addWidget(self.fan_curve_graph)

        self.fan_curve_advanced_toggle = QPushButton(i18n.t("gui.fan_curve.advanced_collapsed"))
        self.fan_curve_advanced_toggle.setCheckable(True)
        self.fan_curve_advanced_toggle.toggled.connect(self._toggle_curve_advanced)
        layout.addWidget(self.fan_curve_advanced_toggle)

        self.fan_curve_advanced_box = QWidget()
        adv_layout = QVBoxLayout(self.fan_curve_advanced_box)
        adv_layout.setContentsMargins(0, 0, 0, 0)

        self.fan_curve_table = QTableWidget(0, 2)
        self.fan_curve_table.setHorizontalHeaderLabels(
            [i18n.t("gui.fan_curve.table.temp"), i18n.t("gui.fan_curve.table.raw")]
        )
        self.fan_curve_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.fan_curve_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.fan_curve_table.setMaximumHeight(160)
        adv_layout.addWidget(self.fan_curve_table)

        button_row = QHBoxLayout()
        self.fan_curve_add_button = QPushButton(i18n.t("gui.fan_curve.add_point"))
        self.fan_curve_add_button.clicked.connect(self._add_curve_point)
        self.fan_curve_remove_button = QPushButton(i18n.t("gui.fan_curve.remove_point"))
        self.fan_curve_remove_button.clicked.connect(self._remove_curve_point)
        button_row.addWidget(self.fan_curve_add_button)
        button_row.addWidget(self.fan_curve_remove_button)
        adv_layout.addLayout(button_row)

        self.fan_curve_advanced_box.setVisible(False)
        layout.addWidget(self.fan_curve_advanced_box)

        self.fan_curve_save_button = QPushButton(i18n.t("gui.fan_curve.save"))
        self.fan_curve_save_button.clicked.connect(self._save_fan_curve)
        layout.addWidget(self.fan_curve_save_button)

        self._loading_fan_curve = False
        self._load_fan_curve()

        # Bewusst NICHT in self.controls: die Kurve ist reine Konfiguration
        # (config.toml), kein Live-Gerätezugriff - bleibt auch ohne
        # verbundenes Pad bedienbar.
        return box

    def _toggle_curve_advanced(self, checked):
        self.fan_curve_advanced_box.setVisible(checked)
        self.fan_curve_advanced_toggle.setText(
            i18n.t("gui.fan_curve.advanced_expanded") if checked else i18n.t("gui.fan_curve.advanced_collapsed")
        )

    def _load_fan_curve(self):
        cfg = config_mod.load_config()
        curve_cfg = cfg["auto"]["fan_curve"]
        self.fan_curve_enabled_checkbox.setChecked(curve_cfg.get("enabled", False))
        points = fan_curve_mod.sorted_points(curve_cfg.get("points", []))
        self.fan_curve_graph.set_points(points)
        self._rebuild_curve_table(points)

    def _rebuild_curve_table(self, points):
        """Baut die erweiterte Tabelle aus `points` neu auf - wird sowohl
        beim Laden als auch nach jeder Grafik-Änderung aufgerufen, damit
        beide Ansichten synchron bleiben."""
        self._loading_fan_curve = True
        self.fan_curve_table.setRowCount(0)
        for p in points:
            self._append_curve_row(p["temp_c"], p["raw"])
        self._loading_fan_curve = False

    def _append_curve_row(self, temp_c=50, raw=50):
        row = self.fan_curve_table.rowCount()
        self.fan_curve_table.insertRow(row)

        temp_spin = QSpinBox()
        temp_spin.setRange(0, 110)
        temp_spin.setValue(int(temp_c))
        temp_spin.valueChanged.connect(self._on_curve_table_changed)
        self.fan_curve_table.setCellWidget(row, 0, temp_spin)

        raw_spin = QSpinBox()
        raw_spin.setRange(1, 100)
        raw_spin.setValue(int(raw))
        raw_spin.valueChanged.connect(self._on_curve_table_changed)
        self.fan_curve_table.setCellWidget(row, 1, raw_spin)

    def _add_curve_point(self):
        self._append_curve_row()
        self._on_curve_table_changed()

    def _remove_curve_point(self):
        # Mindestens ein Punkt bleibt immer erhalten (analog zum
        # Rechtsklick-Entfernen in FanCurveEditor) - sonst würde
        # _on_curve_table_changed() bei 0 Zeilen die Tabelle einfach
        # überspringen und die Grafik zeigt beim nächsten Speichern
        # scheinbar unverändert die alte Kurve weiter an.
        row = self.fan_curve_table.currentRow()
        if row >= 0 and self.fan_curve_table.rowCount() > 1:
            self.fan_curve_table.removeRow(row)
            self._on_curve_table_changed()

    def _current_curve_points_from_table(self):
        points = []
        for row in range(self.fan_curve_table.rowCount()):
            temp_spin = self.fan_curve_table.cellWidget(row, 0)
            raw_spin = self.fan_curve_table.cellWidget(row, 1)
            points.append({"temp_c": temp_spin.value(), "raw": raw_spin.value()})
        return points

    def _on_curve_table_changed(self, *_args):
        """Tabelle -> Grafik. `_loading_fan_curve` verhindert eine
        Rückkopplungsschleife, während die Tabelle selbst gerade neu
        aufgebaut wird (z.B. nachdem die Grafik geändert wurde)."""
        if self._loading_fan_curve:
            return
        points = self._current_curve_points_from_table()
        if points:
            self.fan_curve_graph.set_points(points)

    def _on_curve_graph_changed(self):
        """Grafik -> Tabelle."""
        self._rebuild_curve_table(self.fan_curve_graph.points())

    def _save_fan_curve(self):
        points = self.fan_curve_graph.points()
        if not points:
            QMessageBox.warning(self, i18n.t("gui.fan_curve.save_error_title"), i18n.t("gui.fan_curve.save_error_text"))
            return
        config_mod.save_fan_curve(
            self.fan_curve_enabled_checkbox.isChecked(), points, min_change_raw=3
        )
        self._load_fan_curve()  # sortiert neu geladen anzeigen
        self.statusBar().showMessage(i18n.t("gui.fan_curve.save_done"), 5000)

    def _build_auto_group(self):
        box = QGroupBox(i18n.t("gui.auto.title"))
        layout = QVBoxLayout(box)

        self.lbl_auto_status = QLabel(i18n.t("gui.auto.status.unknown"))
        self.auto_toggle_button = QPushButton("…")
        self.auto_toggle_button.clicked.connect(self._toggle_auto)
        self.lbl_auto_warning = QLabel(i18n.t("gui.auto.warning"))
        self.lbl_auto_warning.setStyleSheet("color: #b8860b;")
        self.lbl_auto_warning.setVisible(False)
        self.lbl_auto_hint = QLabel(i18n.t("gui.auto.hint"))
        self.lbl_auto_hint.setStyleSheet("color: gray; font-size: 11px;")

        layout.addWidget(self.lbl_auto_status)
        layout.addWidget(self.auto_toggle_button)
        layout.addWidget(self.lbl_auto_warning)
        layout.addWidget(self.lbl_auto_hint)
        return box

    # ------------------------------------------------------------------ Gerät

    def _try_connect(self):
        dev, err = device_worker.try_open()
        if dev is None:
            self._set_disconnected(err)
            return
        self._device = dev
        self._set_connected()

    def _set_connected(self):
        self.disconnect_banner.setVisible(False)
        for w in self.controls:
            w.setEnabled(True)
        self._sync_profile_apply_enabled()  # leere Slots trotz Verbindung deaktiviert lassen
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self.statusBar().showMessage(i18n.t("gui.status_bar.connected"))

    def _set_disconnected(self, message=None):
        if self._device is not None:
            self._device.close()
        self._device = None
        self._last_report = None
        self.rpm_sparkline.clear()
        self.disconnect_banner.setVisible(True)
        if message:
            self.disconnect_banner.setText(f"⚠ {message}")
        for w in self.controls:
            w.setEnabled(False)
        self._poll_timer.setInterval(RECONNECT_PROBE_MS)
        self.statusBar().showMessage(i18n.t("gui.status_bar.disconnected"))

    def _poll_device(self):
        if self._device is None:
            self._try_connect()
            return
        report, err = device_worker.safe_call(self._device, lambda dev: dev.get_report())
        if report is None:
            self._set_disconnected(err)
            return
        self._last_report = report
        self._update_status_labels(report)
        self._sync_controls(report)

    def _set_status_value(self, attr, text):
        self._status_value_items[attr].setText(text)

    def _update_status_labels(self, r):
        self.rpm_sparkline.add_value(r.fan_rpm)
        self._set_status_value("lbl_path", self._device.path if self._device else "…")
        self._set_status_value("lbl_rpm", f"{r.fan_rpm} RPM (raw={r.fan_speed_raw})")
        self._set_status_value("lbl_power", i18n.t("common.on") if r.power_on else i18n.t("common.off"))
        self._set_status_value("lbl_light", i18n.t("common.on") if r.light_on else i18n.t("common.off"))
        self._set_status_value("lbl_color", f"{r.color} [{r.color_name()}]")
        self._set_status_value("lbl_effect", f"{r.effect_raw} [{r.effect_name()}]")
        self._set_status_value("lbl_speed", str(r.speed))
        self._set_status_value("lbl_brightness", str(r.brightness))
        self._set_status_value("lbl_raw", r.raw.hex(" "))
        self._set_status_value("lbl_checksum", i18n.t("common.yes") if r.checksum_ok else i18n.t("common.no"))
        self.power_button.setText(i18n.t("gui.control.power_on") if r.power_on else i18n.t("gui.control.power_off"))
        self.light_toggle_button.setText(i18n.t("gui.control.light_on") if r.light_on else i18n.t("gui.control.light_off"))

    def _sync_controls(self, r):
        """Zieht die Bedienelemente auf den zuletzt gelesenen Zustand nach
        (z.B. wenn der Auto-Modus-Daemon parallel die Farbe geändert hat),
        ohne laufende Nutzer-Interaktionen zu stören und ohne durch das
        Nachziehen selbst wieder einen Schreibvorgang auszulösen
        (blockSignals)."""
        if 0 <= r.color <= 4:
            self.color_combo.blockSignals(True)
            self.color_combo.setCurrentIndex(r.color)
            self.color_combo.blockSignals(False)
        if r.light_on and 0 <= r.effect_raw <= 4:
            self.effect_combo.blockSignals(True)
            self.effect_combo.setCurrentIndex(r.effect_raw)
            self.effect_combo.blockSignals(False)
        if 0 <= r.speed <= 3:
            self.speed_combo.blockSignals(True)
            self.speed_combo.setCurrentIndex(r.speed)
            self.speed_combo.blockSignals(False)
        if not self.brightness_slider.isSliderDown():
            self.brightness_slider.blockSignals(True)
            self.brightness_slider.setValue(r.brightness)
            self.brightness_slider.blockSignals(False)
            self.lbl_brightness_value.setText(str(r.brightness))

    def _write_light(self, *, light_on):
        if self._device is None:
            return
        color = self.color_combo.currentData()
        effect = self.effect_combo.currentData()
        speed = self.speed_combo.currentData()
        brightness = self.brightness_slider.value()
        power = self._last_report.power_on if self._last_report else True
        report, err = device_worker.safe_call(
            self._device,
            lambda dev: dev.set_light(
                color=color,
                effect=effect,
                speed=speed,
                light_on=light_on,
                brightness=brightness,
                power=power,
            ),
        )
        if report is None:
            self._set_disconnected(err)
            return
        self._last_report = report
        self._update_status_labels(report)

    def _toggle_light(self):
        if self._device is None or self._last_report is None:
            return
        self._write_light(light_on=not self._last_report.light_on)

    def _toggle_power(self):
        if self._device is None or self._last_report is None:
            return
        new_state = not self._last_report.power_on
        report, err = device_worker.safe_call(
            self._device, lambda dev: dev.set_power(power=new_state)
        )
        if report is None:
            self._set_disconnected(err)
            return
        self._last_report = report
        self._update_status_labels(report)

    def _apply_fan_speed(self):
        """Setzt die Lüfterdrehzahl über das eigene Fan-Kommando, siehe
        protocol.py NACHTRAG 8."""
        if self._device is None:
            return
        raw = self.fan_speed_slider.value()
        report, err = device_worker.safe_call(
            self._device, lambda dev: dev.set_fan_speed(raw)
        )
        if report is None:
            self._set_disconnected(err)
            return
        self._last_report = report
        self._update_status_labels(report)

    # ------------------------------------------------------- Automatikmodus

    def _poll_service(self):
        active = service_control.is_active()
        self._auto_active = active
        self.lbl_auto_status.setText(i18n.t("gui.auto.status.active") if active else i18n.t("gui.auto.status.paused"))
        self.auto_toggle_button.setText(i18n.t("gui.auto.pause") if active else i18n.t("gui.auto.resume"))
        self.lbl_auto_warning.setVisible(active)

    def _toggle_auto(self):
        if self._auto_active:
            service_control.stop()
        else:
            service_control.start()
        self._poll_service()

    # ---------------------------------------------------------------- Ende

    def closeEvent(self, event):
        if self._device is not None:
            self._device.close()
        super().closeEvent(event)
