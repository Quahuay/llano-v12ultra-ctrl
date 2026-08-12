"""Steuerung des Auto-Modus-Hintergrunddienstes aus der GUI heraus.

Linux: systemd --user Unit `llano-v12ultra-ctrl.service`. Live getestet.
Windows: KEIN systemd-Äquivalent - stattdessen eine geplante Aufgabe
(Scheduled Task, `schtasks`), die bei Anmeldung `llano-v12ultra-ctrl auto`
startet. Live gegen echte Hardware getestet - dabei fiel auf, dass die
GUI die geplante Aufgabe zuvor NIRGENDS selbst anlegte ("Fortsetzen" rief
nur `schtasks /run` auf eine nie registrierte Aufgabe, was still fehlschlug
- das war der Bug hinter "Automatikmodus funktioniert nicht"). Behoben:
`_start_windows()` registriert die Aufgabe jetzt bei Bedarf automatisch
(idempotent, kein Admin/Installer nötig, Trigger "bei Anmeldung", läuft im
Kontext des angemeldeten Nutzers).

Die GUI schaltet den Daemon nur für die laufende Sitzung pausiert/fortgesetzt
(kein dauerhaftes Deaktivieren der Registrierung) - siehe README.
"""

import shutil
import subprocess
import sys

SERVICE_NAME = "llano-v12ultra-ctrl.service"
WINDOWS_TASK_NAME = "llano-v12ultra-ctrl-auto"

# `_poll_service()` in der GUI ruft die *_active_* Funktionen alle 2s auf dem
# Qt-Event-Loop-Thread auf (main_window.py, kein eigener QThread dafür - siehe
# dortiger Moduldokstring: ioctls sind sub-millisecond, das gilt aber NICHT für
# Subprozessaufrufe). Ohne Timeout würde ein hängender systemd-User-Session-
# oder schtasks-Aufruf die komplette GUI (inkl. RPM-Anzeige) unbegrenzt
# einfrieren. Zwei Stufen: kurz für reine Statusabfragen (müssen die GUI am
# Leben halten), großzügiger für nutzerinitiierte, mutierende Aktionen.
STATUS_TIMEOUT_S = 3
ACTION_TIMEOUT_S = 10


def _is_active_linux() -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet", SERVICE_NAME],
            capture_output=True, timeout=STATUS_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def _stop_linux() -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "--user", "stop", SERVICE_NAME],
            capture_output=True, timeout=ACTION_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def _start_linux() -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "--user", "start", SERVICE_NAME],
            capture_output=True, timeout=ACTION_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def _task_exists_windows() -> bool:
    try:
        result = subprocess.run(
            ["schtasks", "/query", "/tn", WINDOWS_TASK_NAME],
            capture_output=True, text=True, errors="replace", timeout=STATUS_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def _find_cli_command() -> str:
    """Ermittelt den Aufrufbefehl für `llano-v12ultra-ctrl auto`, den die
    geplante Aufgabe verwenden soll.

    `sys.executable` ist hier NICHT verlässlich `python.exe` - wenn dieser
    Code aus der GUI heraus läuft, ist es der Pfad zu
    `llano-v12ultra-ctrl-gui.exe` selbst (Scripts\\llano-v12ultra-ctrl-gui.exe).
    Ein einzelner `.parent / "Scripts"`-Versuch (frühere, live als kaputt
    entdeckte Version) landet dann bei einem nicht existierenden doppelten
    `Scripts\\Scripts\\...` und die `-m`-Rückfalloption ruft am Ende den
    GUI-Wrapper selbst mit `-m ...` auf (der das Argument ignoriert und
    einfach die GUI nochmal startet, statt `auto` auszuführen) - deshalb
    hier mehrere plausible Fundorte durchprobieren, bevor auf `-m`
    zurückgefallen wird."""
    from pathlib import Path

    candidates = []
    which_result = shutil.which("llano-v12ultra-ctrl")
    if which_result:
        candidates.append(Path(which_result))

    exe_dir = Path(sys.executable).parent
    candidates += [
        exe_dir / "llano-v12ultra-ctrl.exe",  # sys.executable ist bereits ein Scripts-Exe (z.B. die GUI selbst)
        exe_dir / "Scripts" / "llano-v12ultra-ctrl.exe",  # sys.executable ist z.B. python.exe im venv-Root
        Path(sys.prefix) / "Scripts" / "llano-v12ultra-ctrl.exe",  # zur Sicherheit zusätzlich über sys.prefix
    ]
    for candidate in candidates:
        if candidate.exists():
            return f'"{candidate}" auto'

    return f'"{sys.executable}" -m llano_v12ultra_ctrl.cli auto'


def _register_task_windows() -> bool:
    """Registriert die geplante Aufgabe einmalig (idempotent, `/f` überschreibt
    eine evtl. kaputte Altregistrierung). Kein Admin nötig: Trigger "bei
    Anmeldung" (`/sc onlogon`), läuft mit den Rechten des angemeldeten
    Nutzers (`/rl limited`), kein SYSTEM/Scheduled-Task-Elevation-Ärger wie
    beim einmaligen Windows-Setup (siehe HISTORY.md)."""
    command = _find_cli_command()
    try:
        result = subprocess.run(
            [
                "schtasks", "/create", "/tn", WINDOWS_TASK_NAME,
                "/tr", command, "/sc", "onlogon", "/rl", "limited", "/f",
            ],
            capture_output=True, text=True, errors="replace", timeout=ACTION_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def _is_active_windows() -> bool:
    """`schtasks /query .../v` liefert im "Status"-Feld u.a. "Running" oder
    "Ready" zurück. Liefert False (statt Fehler), solange die Aufgabe noch
    nicht registriert ist - dafür ist `_register_task_windows()` da."""
    try:
        result = subprocess.run(
            ["schtasks", "/query", "/tn", WINDOWS_TASK_NAME, "/fo", "list", "/v"],
            capture_output=True, text=True, errors="replace", timeout=STATUS_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0 and "Running" in result.stdout


def _stop_windows() -> bool:
    """Beendet die laufende Instanz; die Registrierung der geplanten Aufgabe
    selbst bleibt bestehen (kommt beim nächsten Login normal wieder, analog
    zum `enabled`-Zustand unter systemd)."""
    try:
        result = subprocess.run(
            ["schtasks", "/end", "/tn", WINDOWS_TASK_NAME],
            capture_output=True, timeout=ACTION_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def _start_windows() -> bool:
    """Startet die geplante Aufgabe sofort (statt auf den nächsten Login zu
    warten). Registriert sie zuerst automatisch, falls sie noch nicht
    existiert - das war der Bug hinter "Automatikmodus funktioniert nicht",
    siehe Moduldokstring."""
    if not _task_exists_windows() and not _register_task_windows():
        return False
    try:
        result = subprocess.run(
            ["schtasks", "/run", "/tn", WINDOWS_TASK_NAME],
            capture_output=True, timeout=ACTION_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def is_active() -> bool:
    """True wenn der Auto-Modus-Daemon gerade läuft."""
    if sys.platform == "win32":
        return _is_active_windows()
    return _is_active_linux()


def stop() -> bool:
    """Pausiert den Auto-Modus für diese Sitzung. Gibt True bei Erfolg zurück."""
    if sys.platform == "win32":
        return _stop_windows()
    return _stop_linux()


def start() -> bool:
    """Setzt den Auto-Modus fort. Gibt True bei Erfolg zurück."""
    if sys.platform == "win32":
        return _start_windows()
    return _start_linux()
