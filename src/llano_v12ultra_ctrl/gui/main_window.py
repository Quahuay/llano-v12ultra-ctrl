"""Hauptfenster der llano-v12ultra-ctrl GUI: Live-Status + volle Steuerung des
llano V12 Ultra Kühlpads.

Nutzt device.py/protocol.py exakt wie cli.py - keine eigene Report- oder
HID-Logik. Live-Telemetrie läuft über einen QTimer (ioctls sind
sub-millisecond, ein eigener QThread ist dafür nicht nötig)."""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .. import protocol
from . import device_worker, service_control
from .widgets import Sparkline

POLL_INTERVAL_MS = 300  # wie cmd_monitor-Default (--interval 0.3)
RECONNECT_PROBE_MS = 2000  # langsamere Probe, solange kein Gerät gefunden wird
SERVICE_POLL_MS = 2000  # systemctl-Aufrufe sind teurer als ioctls, seltener pollen
RPM_HISTORY_LEN = 400  # bei 300ms Poll-Intervall ~2 Minuten Verlauf

SPEED_LABELS = {0: "0 (schnell)", 1: "1 (mittel)", 2: "2 (langsam)", 3: "3 (sehr langsam)"}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("llano-v12ultra-ctrl")

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

        self.disconnect_banner = QLabel("⚠ Gerät nicht gefunden. Ist das Pad angeschlossen?")
        self.disconnect_banner.setStyleSheet(
            "background-color: #b00020; color: white; padding: 6px; font-weight: bold;"
        )
        self.disconnect_banner.setVisible(False)
        root.addWidget(self.disconnect_banner)

        root.addWidget(self._build_status_group())
        root.addWidget(self._build_control_group())
        root.addWidget(self._build_fan_speed_group())
        root.addWidget(self._build_auto_group())

        self.statusBar().showMessage("Bereit")

    def _build_status_group(self):
        box = QGroupBox("Status")
        grid = QGridLayout(box)

        self.lbl_path = QLabel("…")
        self.lbl_rpm = QLabel("…")
        self.lbl_power = QLabel("…")
        self.lbl_light = QLabel("…")
        self.lbl_color = QLabel("…")
        self.lbl_effect = QLabel("…")
        self.lbl_speed = QLabel("…")
        self.lbl_brightness = QLabel("…")
        self.lbl_raw = QLabel("…")
        self.lbl_checksum = QLabel("…")

        rows = [
            ("Gerät:", self.lbl_path),
            ("Lüfterdrehzahl:", self.lbl_rpm),
            ("Gesamteinheit:", self.lbl_power),
            ("Beleuchtung:", self.lbl_light),
            ("Farbe:", self.lbl_color),
            ("Effekt:", self.lbl_effect),
            ("Geschwindigkeit:", self.lbl_speed),
            ("Helligkeit:", self.lbl_brightness),
            ("Rohdaten:", self.lbl_raw),
            ("Checksum ok:", self.lbl_checksum),
        ]
        for row, (label_text, value_label) in enumerate(rows):
            grid.addWidget(QLabel(label_text), row, 0)
            grid.addWidget(value_label, row, 1)

        rpm_row = len(rows)
        grid.addWidget(QLabel("RPM-Verlauf:"), rpm_row, 0)
        self.rpm_sparkline = Sparkline(maxlen=RPM_HISTORY_LEN)
        grid.addWidget(self.rpm_sparkline, rpm_row, 1)

        return box

    def _build_control_group(self):
        box = QGroupBox("Steuerung")
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
        self.speed_combo = QComboBox()
        for idx in range(4):
            self.speed_combo.addItem(SPEED_LABELS[idx], idx)
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

        grid.addWidget(QLabel("Farbe:"), 0, 0)
        grid.addWidget(self.color_combo, 0, 1)
        grid.addWidget(QLabel("Effekt:"), 1, 0)
        grid.addWidget(self.effect_combo, 1, 1)
        grid.addWidget(QLabel("Geschwindigkeit:"), 2, 0)
        grid.addWidget(self.speed_combo, 2, 1)

        grid.addWidget(QLabel("Helligkeit:"), 3, 0)
        brightness_row = QHBoxLayout()
        brightness_row.addWidget(self.brightness_slider)
        brightness_row.addWidget(self.lbl_brightness_value)
        grid.addLayout(brightness_row, 3, 1)

        button_row = QHBoxLayout()
        self.light_off_button = QPushButton("Beleuchtung aus")
        self.light_off_button.clicked.connect(lambda: self._write_light(light_on=False))
        self.power_button = QPushButton("Gesamteinheit AUS")
        self.power_button.clicked.connect(self._toggle_power)
        button_row.addWidget(self.light_off_button)
        button_row.addWidget(self.power_button)
        grid.addLayout(button_row, 4, 0, 1, 2)

        self.controls = [
            self.color_combo,
            self.effect_combo,
            self.speed_combo,
            self.brightness_slider,
            self.light_off_button,
            self.power_button,
        ]
        return box

    def _build_fan_speed_group(self):
        box = QGroupBox("Fan-Speed")
        layout = QVBoxLayout(box)

        warning = QLabel(
            "Per Live-USB-Capture gegen die echte App gefundenes Fan-Kommando "
            "(protocol.py NACHTRAG 8) - Wirkung live bestätigt, sowohl unter Windows "
            "als auch hier auf Linux (Drehzahl ändert sich hör-/sichtbar über den "
            "gesamten Bereich 1-100)."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #808080; font-size: 11px;")
        layout.addWidget(warning)

        row = QHBoxLayout()
        self.fan_speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.fan_speed_slider.setMinimum(1)
        self.fan_speed_slider.setMaximum(100)
        self.fan_speed_slider.setValue(1)
        self.lbl_fan_speed_value = QLabel("1")
        self.fan_speed_slider.valueChanged.connect(
            lambda v: self.lbl_fan_speed_value.setText(str(v))
        )
        self.fan_speed_apply_button = QPushButton("Anwenden")
        self.fan_speed_apply_button.clicked.connect(self._apply_fan_speed)
        row.addWidget(self.fan_speed_slider)
        row.addWidget(self.lbl_fan_speed_value)
        row.addWidget(self.fan_speed_apply_button)
        layout.addLayout(row)

        self.controls.append(self.fan_speed_slider)
        self.controls.append(self.fan_speed_apply_button)
        return box

    def _build_auto_group(self):
        box = QGroupBox("Automatikmodus (Temperatur)")
        layout = QVBoxLayout(box)

        self.lbl_auto_status = QLabel("Status: unbekannt")
        self.auto_toggle_button = QPushButton("…")
        self.auto_toggle_button.clicked.connect(self._toggle_auto)
        self.lbl_auto_warning = QLabel(
            "Hinweis: Automatikmodus aktiv. Manuelle Änderungen können innerhalb "
            "weniger Sekunden wieder überschrieben werden."
        )
        self.lbl_auto_warning.setStyleSheet("color: #b8860b;")
        self.lbl_auto_warning.setVisible(False)
        self.lbl_auto_hint = QLabel(
            "Pausieren gilt nur für diese Sitzung. Der Dienst bleibt aktiviert "
            "und läuft nach dem nächsten Login/Neustart normal weiter."
        )
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
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self.statusBar().showMessage("Verbunden")

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
        self.statusBar().showMessage("Getrennt")

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

    def _update_status_labels(self, r):
        self.rpm_sparkline.add_value(r.fan_rpm)
        self.lbl_path.setText(self._device.path if self._device else "…")
        self.lbl_rpm.setText(f"{r.fan_rpm} U/min (raw={r.fan_speed_raw})")
        self.lbl_power.setText("AN" if r.power_on else "AUS")
        self.lbl_light.setText("AN" if r.light_on else "AUS")
        self.lbl_color.setText(f"{r.color} [{r.color_name()}]")
        self.lbl_effect.setText(f"{r.effect_raw} [{r.effect_name()}]")
        self.lbl_speed.setText(str(r.speed))
        self.lbl_brightness.setText(str(r.brightness))
        self.lbl_raw.setText(r.raw.hex(" "))
        self.lbl_checksum.setText("ja" if r.checksum_ok else "NEIN")
        self.power_button.setText("Gesamteinheit AUS" if r.power_on else "Gesamteinheit AN")

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
        self.lbl_auto_status.setText(f"Status: {'aktiv' if active else 'pausiert'}")
        self.auto_toggle_button.setText("Pausieren" if active else "Fortsetzen")
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
