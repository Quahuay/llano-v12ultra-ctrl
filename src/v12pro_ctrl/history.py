"""CSV-Verlaufsprotokoll für den Auto-Modus (cli.py: cmd_auto).

Opt-in über [auto.log] in config.toml. Nützlich, um im Nachhinein zu sehen,
welche Radstellung (Lüfterdrehzahl) bei welcher Last/Temperatur tatsächlich
ausreicht - da die Drehzahl selbst nicht per Software steuerbar ist (siehe
protocol.py), ist das reine Beobachtung, kein Regelkreis.
"""

import csv
import os
import time

FIELDS = ["timestamp", "cpu_temp_c", "gpu_temp_c", "fan_rpm", "color", "effect"]


class HistoryLogger:
    def __init__(self, path):
        self.path = os.path.expanduser(path)
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._write_header = not os.path.exists(self.path) or os.path.getsize(self.path) == 0

    def log(self, cpu_temp_c, gpu_temp_c, fan_rpm, color, effect):
        with open(self.path, "a", newline="") as f:
            writer = csv.writer(f)
            if self._write_header:
                writer.writerow(FIELDS)
                self._write_header = False
            writer.writerow(
                [
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                    f"{cpu_temp_c:.1f}" if cpu_temp_c is not None else "",
                    f"{gpu_temp_c:.1f}" if gpu_temp_c is not None else "",
                    fan_rpm,
                    color,
                    effect,
                ]
            )
