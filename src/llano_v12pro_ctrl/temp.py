"""CPU-/GPU-Temperatur-Erkennung für den Auto-Modus.

Linux: sucht automatisch den passenden hwmon-Sensor (coretemp "Package id 0"
bei Intel, k10temp "Tctl"/"Tdie" bei AMD) statt einen festen hwmon-Index
anzunehmen - der Index kann sich je nach Kernel/Boot-Reihenfolge ändern.
Live gegen echte Hardware getestet.

Windows: KEIN hwmon-Äquivalent vorhanden, CPU-Paket-Temperatur ist ohne
Kernel-Treiber nicht auslesbar. Anbindung an LibreHardwareMonitor
(https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) über dessen
WMI-Namespace `root\\LibreHardwareMonitor` - Voraussetzung: LibreHardwareMonitor
läuft und hat WMI-Export aktiviert (Standard). Analoges Muster zu
`read_gpu_temp_c()` unten: externe Abhängigkeit, einmalige Warnung bei
Nichtverfügbarkeit statt Absturz. **UNGETESTET** - keine Windows-Maschine in
dieser Entwicklungsumgebung verfügbar, nur code-seitig vorbereitet.

GPU: es gibt auf NVIDIA-Systemen keinen passenden hwmon-Eintrag für die
GPU-Temperatur (nur CPU/NVMe/Akku etc.), daher über `nvidia-smi` gelesen -
funktioniert plattformunabhängig, da `nvidia-smi` auch unter Windows
existiert (Teil des NVIDIA-Treibers), hier aber nur unter Linux getestet.
"""

import glob
import subprocess
import sys

PREFERRED_LABELS = ("package id 0", "tctl", "tdie")
PREFERRED_CHIPS = ("coretemp", "k10temp")

WINDOWS_SENSOR_SOURCE = "librehardwaremonitor"  # Sentinel-Rückgabewert von find_cpu_temp_input() unter Windows


def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _find_cpu_temp_input_linux():
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


_windows_wmi_warned = False


def _find_cpu_temp_input_windows():
    """Prüft, ob LibreHardwareMonitor per WMI erreichbar ist. UNGETESTET."""
    global _windows_wmi_warned
    try:
        import wmi

        w = wmi.WMI(namespace="root\\LibreHardwareMonitor")
        sensors = w.Sensor()
        if any(s.SensorType == "Temperature" for s in sensors):
            return WINDOWS_SENSOR_SOURCE
        return None
    except Exception as e:
        if not _windows_wmi_warned:
            print(
                f"Hinweis: LibreHardwareMonitor per WMI nicht erreichbar ({e}). "
                "CPU-Temperatur-Erkennung unter Windows benötigt LibreHardwareMonitor "
                "(muss laufen, WMI-Export aktiviert - Standardeinstellung)."
            )
            _windows_wmi_warned = True
        return None


def find_cpu_temp_input():
    """Gibt eine Sensor-Quelle für die CPU-Paket-Temperatur zurück (Linux:
    Pfad zu einer temp*_input-Datei; Windows: Sentinel-String für
    LibreHardwareMonitor), oder None wenn nichts Passendes gefunden wurde."""
    if sys.platform == "win32":
        return _find_cpu_temp_input_windows()
    return _find_cpu_temp_input_linux()


def _read_temp_c_windows(source):
    """UNGETESTET - siehe Modul-Docstring."""
    try:
        import wmi

        w = wmi.WMI(namespace="root\\LibreHardwareMonitor")
        for s in w.Sensor():
            if s.SensorType == "Temperature" and "cpu package" in s.Name.lower():
                return float(s.Value)
        # Fallback: erster verfügbare CPU-Temperatursensor, falls "Package" nicht existiert
        for s in w.Sensor():
            if s.SensorType == "Temperature" and "cpu" in s.Name.lower():
                return float(s.Value)
        return None
    except Exception:
        return None


def read_temp_c(source):
    if sys.platform == "win32":
        return _read_temp_c_windows(source)
    raw = _read(source)
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
