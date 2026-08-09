"""CPU-/GPU-Temperatur-Erkennung für den Auto-Modus.

CPU: sucht automatisch den passenden hwmon-Sensor (coretemp "Package id 0"
bei Intel, k10temp "Tctl"/"Tdie" bei AMD) statt einen festen hwmon-Index
anzunehmen - der Index kann sich je nach Kernel/Boot-Reihenfolge ändern.

GPU: es gibt auf NVIDIA-Systemen keinen passenden hwmon-Eintrag für die
GPU-Temperatur (nur CPU/NVMe/Akku etc.), daher über `nvidia-smi` gelesen.
"""

import glob
import subprocess


PREFERRED_LABELS = ("package id 0", "tctl", "tdie")
PREFERRED_CHIPS = ("coretemp", "k10temp")


def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def find_cpu_temp_input():
    """Gibt den Pfad zu einer temp*_input-Datei für die CPU-Paket-Temperatur
    zurück, oder None wenn nichts Passendes gefunden wurde."""
    candidates = []
    for chip_dir in glob.glob("/sys/class/hwmon/hwmon*"):
        name = _read(f"{chip_dir}/name")
        if name not in PREFERRED_CHIPS:
            continue
        for label_path in glob.glob(f"{chip_dir}/temp*_label"):
            label = _read(label_path)
            if label and label.strip().lower() in PREFERRED_LABELS:
                input_path = label_path.replace("_label", "_input")
                candidates.append(input_path)
        if not candidates:
            # kein Label passt exakt - nimm temp1_input dieses Chips als Fallback
            fallback = f"{chip_dir}/temp1_input"
            if _read(fallback) is not None:
                candidates.append(fallback)
    return candidates[0] if candidates else None


def read_temp_c(path):
    raw = _read(path)
    if raw is None:
        return None
    try:
        return int(raw) / 1000.0
    except ValueError:
        return None


_gpu_warned = False


def read_gpu_temp_c():
    """Liest die GPU-Temperatur über `nvidia-smi`, oder None wenn nicht
    verfügbar (kein NVIDIA-Treiber/-Karte, Timeout, Parse-Fehler). Gibt bei
    Nichtverfügbarkeit nur einmalig eine Warnung aus, damit der Daemon bei
    Systemen ohne NVIDIA-GPU nicht bei jedem Poll-Zyklus loggt."""
    global _gpu_warned
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return float(result.stdout.strip().splitlines()[0])
    except (OSError, subprocess.TimeoutExpired, RuntimeError, ValueError, IndexError) as e:
        if not _gpu_warned:
            print(f"Hinweis: GPU-Temperatur nicht lesbar ({e}) - GPU-Alarm bleibt inaktiv.")
            _gpu_warned = True
        return None
