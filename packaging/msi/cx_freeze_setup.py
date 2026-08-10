"""cx_Freeze-Setup für den Windows-.msi-Build von llano-v12ultra-ctrl.

NICHT auf der Dev-Maschine getestet (kein Windows dort verfügbar, siehe
Session-Notizen) - Build + Live-Test läuft auf der Windows-Testmaschine
bzw. in der GitHub-Actions-Pipeline (windows-latest), siehe
.github/workflows/release.yml.

Voraussetzungen (nur für den Build, nicht für den fertigen Installer):
- `pip install ".[gui]" cx_Freeze`
- Python 3.13+: zusätzlich `pip install python-msilib` - msilib wurde aus
  der Standardbibliothek entfernt, cx_Freezes bdist_msi-Befehl braucht den
  Nachfolger (siehe https://github.com/marcelotduarte/python-msilib).
  Live in dieser Session bestätigt: das Windows-Testsystem läuft Python
  3.14, cx_Freeze 8.6.4 verweist bei fehlendem msilib explizit darauf.
- `hidapi.dll` muss VOR dem Build als packaging/msi/hidapi.dll vorliegen
  (wird von der CI-Pipeline heruntergeladen, nicht committed - siehe
  README Windows-Status: die native DLL ist nicht im PyPI-Paket `hid`
  enthalten, device.py lädt sie zur Laufzeit über den DLL-Suchpfad, hier
  also direkt neben die gebauten .exe-Dateien gelegt).

Aufruf: python packaging/msi/cx_freeze_setup.py bdist_msi
"""

import sys
from pathlib import Path

from cx_Freeze import Executable, setup

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
from llano_v12ultra_ctrl import __version__  # noqa: E402

HIDAPI_DLL = Path(__file__).parent / "hidapi.dll"
ICON = REPO_ROOT / "packaging" / "icons" / "llano-v12ultra-ctrl.ico"

if not HIDAPI_DLL.exists():
    print(f"WARNING: {HIDAPI_DLL} not found - MSI will NOT have USB HID support.", file=sys.stderr)

build_exe_options = {
    "packages": ["llano_v12ultra_ctrl"],
    "include_files": [(str(HIDAPI_DLL), "hidapi.dll")] if HIDAPI_DLL.exists() else [],
    "excludes": ["tkinter", "unittest"],
    "include_msvcr": True,
}

bdist_msi_options = {
    # Stabile GUID, absichtlich fest einprogrammiert statt bei jedem Build
    # neu generiert - NICHT zwischen Releases ändern, sonst erkennt der
    # Windows Installer ein neues .msi nicht als Upgrade der alten
    # Installation, sondern als komplett neues, parallel installierbares
    # Produkt.
    "upgrade_code": "{B29171D1-EB96-4F8F-AA96-D6EF3DA31526}",
    "add_to_path": True,
    "initial_target_dir": r"[ProgramFilesFolder]\llano-v12ultra-ctrl",
}

executables = [
    Executable(
        str(REPO_ROOT / "src" / "llano_v12ultra_ctrl" / "_cli_entry.py"),
        target_name="llano-v12ultra-ctrl.exe",
        base=None,  # Konsolen-App
    ),
    Executable(
        str(REPO_ROOT / "src" / "llano_v12ultra_ctrl" / "_gui_entry.py"),
        target_name="llano-v12ultra-ctrl-gui.exe",
        base="Win32GUI",  # kein Konsolenfenster
        icon=str(ICON) if ICON.exists() else None,
        shortcut_name="llano-v12ultra-ctrl",
        shortcut_dir="DesktopFolder",
    ),
]

setup(
    name="llano-v12ultra-ctrl",
    version=__version__,
    description="Native control tool for the llano V12 Ultra USB-HID cooling pad (Myth.Cool / Holtek 374a:b101)",
    options={"build_exe": build_exe_options, "bdist_msi": bdist_msi_options},
    executables=executables,
)
