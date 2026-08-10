# llano-v12ultra-ctrl

*[Deutsche Version](README.de.md)*

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![Platform: Linux (primary) + Windows (device control tested)](https://img.shields.io/badge/platform-Linux%20(primary)%20%2B%20Windows-lightgrey.svg)

> **Primarily developed and maintained for Linux.** The actual device control (`status`/`light`/
> `fan-speed`) is live-tested against real hardware on Windows and works (see
> [Windows Status](#windows-status)) - temperature sensor detection and background service control
> are, on the other hand, only prepared in code so far on Windows, not practically verified.

Native Linux control tool for the **llano V12 Ultra** RGB laptop cooling pad (Holtek USB-HID
`374a:b101`), whose official Windows software is **Myth.Cool**. Instead of running the Windows app
under Wine (broken UI text, non-functional sensor dashboard), `llano-v12ultra-ctrl` talks to the
device directly via `/dev/hidraw*`, reverse-engineered from real USB traffic of the original app
and through systematic live tests on the physical device - including a **real fan speed control
found via live USB capture** (see below).

### Trademark Notice

This project has no connection to, is not endorsed by, and is not authorized by the
manufacturer/distributor of the **llano** brand or the **Myth.Cool** software. It is an
independent, private open-source project by a single user of this hardware. The brand name is
used purely descriptively, to clarify which device this tool is for (nominative use for
recognizability) - not to suggest any affiliation, endorsement, or partnership. All rights to the
mentioned brand names belong to their respective owners.

## Table of Contents

- [Features](#features)
- [Hardware Background](#hardware-background)
- [Installation](#installation)
- [Language](#language)
- [Usage](#usage)
- [Auto Mode (Temperature Indicator)](#auto-mode-temperature-indicator)
- [Fan Curve & Fan Reminder](#fan-curve--fan-reminder)
- [Windows Status](#windows-status)
- [Protocol Documentation](#protocol-documentation)
- [Contributing](#contributing)
- [Authors](#authors)
- [License](#license)

## Features

- **CLI** (`llano-v12ultra-ctrl`): set color, effect, effect speed, brightness **and fan speed**,
  fully power the device on/off, watch live telemetry
- **GUI** (`llano-v12ultra-ctrl-gui`, PyQt6): the same functionality graphically, including a
  compact status table, a separate RPM history, a fan speed slider, control of the auto-mode
  service, and up to five saveable profiles (light + fan speed, one click to apply)
- **Real fan speed control** (100 steps, ~25 RPM per step, 300-2800 RPM total range): found via
  live USB capture against the real manufacturer app (see
  [Hardware Background](#hardware-background)) and live-verified on real hardware - every single
  one of the 100 raw values individually tested, no more physical wheel-turning needed
- **Auto mode**: RGB color (and optionally effect) switches based on CPU/GPU temperature (a visual
  temperature indicator right on the pad), optionally as a background systemd user service
- **Fan curve** (opt-in): maps CPU temperature via linear interpolation between freely
  configurable points onto a fan speed - available in the GUI as an interactive graph
  (drag/add/remove points), precise numeric values optionally via "Advanced Settings", see
  [Fan Curve & Fan Reminder](#fan-curve--fan-reminder)
- **RPM history** in the GUI (a small live sparkline of the last ~2 minutes of fan speed)
- **Fan reminder**: desktop notification when the CPU is hot but the measured speed stays low -
  a stopgap while the fan curve isn't enabled (yet)
- **CSV history log** (temperature/RPM/color over time), opt-in, for later analysis
- **Critical-heat alert**: high temperature thresholds can set a more noticeable effect instead of
  just a different color (e.g. `chase`)
- No external HID libraries needed: direct `HIDIOCGFEATURE`/`HIDIOCSFEATURE` ioctls on
  `/dev/hidraw*`
- Fully documented HID protocol (see [`protocol.py`](src/llano_v12ultra_ctrl/protocol.py)),
  including a diagnostic command for the raw 64-byte input report (`llano-v12ultra-ctrl raw-input`)

## Hardware Background

Software-controllable: fan speed (raw range 1-100, roughly 25 RPM per step, 300-2800 RPM total),
RGB color (5 colors), light effect (5 modes), effect speed, brightness, plus a pure on/off kill
switch for the whole unit (fan + light). The device still accepts values above 100, but the real
speed stays put once it hits the maximum - only the display keeps counting up unbounded. The
physical wheel on the pad keeps working in parallel as a manual override.

Fan speed and light are two completely separate HID commands (see
[`protocol.py`](src/llano_v12ultra_ctrl/protocol.py) for the full byte layout). How the fan command
was found, including every dead end along the way, is in [HISTORY.md](HISTORY.md).

Auto mode (see below) can optionally also control fan speed based on temperature (fan curve,
disabled by default) - see [Fan Curve & Fan Reminder](#fan-curve--fan-reminder).

## Installation

PyQt6 is a **apt/distro package** on many systems (including this one), not a pip package. A
simple `pip install -e .` therefore often fails on PEP 668
(`externally-managed-environment`). Two paths, depending on your system:

<details>
<summary><strong>Path A: system with PyQt6 from the package manager (e.g. Debian/Ubuntu)</strong></summary>

```bash
sudo apt install python3-pyqt6   # if not already present
```

Then either use the bundled shim scripts, or install the package via a venv with
`--system-site-packages`, so the apt package stays visible:

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e ".[gui]"
```

</details>

<details>
<summary><strong>Path B: plain pip/pipx (other systems)</strong></summary>

```bash
pipx install ".[gui]"
# or just the CLI, without the GUI/PyQt6 dependency:
pipx install .
```

</details>

### udev rule

So your own Linux user can access the HID device without root:

```bash
sudo cp packaging/70-llano-v12ultra-ctrl.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

The user also needs to be a member of the `plugdev` group:

```bash
sudo usermod -aG plugdev "$USER"   # log out and back in afterwards
```

## Language

CLI and GUI default to English. German can be selected via:

- the language dropdown at the top of the GUI (writes to the config, takes effect after
  restarting the app)
- `language = "de"` in the `[general]` section of `~/.config/llano-v12ultra-ctrl/config.toml`
- the `LLANO_LANGUAGE=de` environment variable for a single call, without touching the config:
  ```bash
  LLANO_LANGUAGE=de llano-v12ultra-ctrl status
  ```

## Usage

```bash
llano-v12ultra-ctrl status                                      # show current state + live telemetry
llano-v12ultra-ctrl light --color red --effect breathing         # set color/effect
llano-v12ultra-ctrl light --brightness 128                       # only change brightness
llano-v12ultra-ctrl light --off                                  # turn off the light (fan keeps running)
llano-v12ultra-ctrl power off                                    # turn off the whole unit (fan + light)
llano-v12ultra-ctrl monitor                                       # continuously show live telemetry
llano-v12ultra-ctrl raw-input                                      # watch raw 64-byte input report (diagnostic)
llano-v12ultra-ctrl fan-speed 50                                   # set fan speed (1-100, see below)
llano-v12ultra-ctrl-gui                                           # launch the graphical interface
```

`fan-speed` sets the fan speed via a dedicated HID command (range `1`-`100`, every value its own
step of roughly 25 RPM: `raw=1` → 300 RPM, `raw=100` → 2800 RPM). Live-verified, every single one
of the 100 values individually tested (see [Hardware Background](#hardware-background)). Also
available in the GUI as its own fan speed slider.

| Option | Values |
|---|---|
| `--color` | `red`, `lightblue`, `green`, `purple`, `orange` (or 0-4) |
| `--effect` | `solid`, `breathing`, `rainbow`, `chase`, `zones` (or 0-4) |
| `--speed` | `0`-`3` (officially validated range, 0=fast) |
| `--brightness` | `0`-`255` |

Details on all options: `llano-v12ultra-ctrl <command> --help`.

## Auto Mode (Temperature Indicator)

```bash
cp config/config.example.toml ~/.config/llano-v12ultra-ctrl/config.toml   # adjust as needed
llano-v12ultra-ctrl auto
```

Switches the pad color based on CPU temperature (green → orange → red), with an optional GPU
temperature alert (purple/breathing), see the comments in
[`config/config.example.toml`](config/config.example.toml). For continuous operation as a systemd
user service:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/llano-v12ultra-ctrl.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now llano-v12ultra-ctrl.service
```

The GUI shows the auto-mode status and can pause/resume the service for the current session
(`systemctl --user stop/start`). The service stays `enabled` and runs normally again after the
next login/restart.

On Windows, the GUI automatically registers a scheduled task on the first "Resume" click
(`schtasks`, trigger "at logon", no admin needed) instead of a real Windows service - see
[Windows Status](#windows-status). **Prerequisite for temperature detection:**
[LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) must be
running with its WMI export enabled - without it, `auto` aborts immediately with "No CPU
temperature sensor found" (confirmed live).

## Fan Curve & Fan Reminder

All three options live inside `auto` mode (see above) and are disabled by default. Enable them in
`~/.config/llano-v12ultra-ctrl/config.toml`, see the commented examples in
[`config/config.example.toml`](config/config.example.toml) - or in the GUI's "Fan Curve (Auto
Mode)" section (drag points with the mouse to add/move/remove; precise numeric values via
"Advanced Settings").

**Fan curve** (`[auto.fan_curve]`): maps CPU temperature via linear interpolation between
configured `points` (`temp_c`/`raw` pairs) onto a fan speed raw value. `min_change_raw` prevents
constantly re-adjusting on small temperature fluctuations - it only writes when the target value
changes by at least this much. Only takes effect while `auto` is running; the GUI form only saves
the configuration, it doesn't apply it live itself.

**Fan reminder** (`[auto.fan_reminder]`): sends a desktop notification (`notify-send`) when the CPU
temperature reaches `temp_c` but the measured speed stays below `min_rpm`. `cooldown_s` prevents
repeated notifications while the condition persists. A stopgap while the fan curve isn't enabled
(yet).

**History log** (`[auto.log]`): continuously writes a CSV line (timestamp, CPU/GPU temperature,
fan speed, color, effect) to the configured `path` while `auto` mode is active. Useful for later
refining your own fan curve based on real load data.

## Windows Status

| File | Status |
|---|---|
| `device.py` | ✅ Live-tested against real hardware on Windows 10 (`status`/`light`/`fan-speed`), both the read and write path work. Additionally needs the native `hidapi.dll` (not included in the PyPI package `hid`) somewhere in the DLL search path, e.g. next to `python.exe` - download at [github.com/libusb/hidapi/releases](https://github.com/libusb/hidapi/releases) |
| `notify.py` | ✅ Switched to `plyer` (cross-platform), live-tested on Linux |
| `temp.py` | ⚠️ Live-tested - the code works, but correctly aborts with a clear error message without [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) running (WMI export enabled). LibreHardwareMonitor itself wasn't installed on the test machine - the full auto-mode control loop with real temperature values is therefore not yet verified end to end |
| `gui/service_control.py` | ✅ Live-tested - the `schtasks` branch registers the scheduled task automatically when needed (`start()`/`stop()`/`is_active()` confirmed error-free). An encoding bug reading `schtasks` output on a German-language Windows install (cp1252 vs. the actual console codepage) was found and fixed along the way |

Feedback from Windows users, especially with LibreHardwareMonitor running, is welcome (see
[Contributing](#contributing)).

## Protocol Documentation

The complete derivation of the 9-byte HID feature report (which byte means what, what's
software-writable vs. a pure telemetry field, measurement series for edge cases) lives as a
docstring in [`src/llano_v12ultra_ctrl/protocol.py`](src/llano_v12ultra_ctrl/protocol.py). The
complete HID report descriptor was read out and confirmed: the device has exactly three reports,
no further hidden report IDs - 64-byte input, 64-byte output, 8-byte feature (fully
reverse-engineered, including the separate fan speed command). How this derivation came about is
in [HISTORY.md](HISTORY.md). `llano-v12ultra-ctrl raw-input` allows further manual observation of
the input report.

## Contributing

Issues and pull requests are welcome, feedback on other llano V12 variants or additional
effect/color values would especially help. When changing `protocol.py`/`device.py`, please include
measurement series/evidence for new findings, matching the existing documentation style.

**macOS is not planned** - the pad is explicitly not suited for use on Mac devices.

**Linux is the primary maintained platform.** Windows support is an add-on goal, not an equal
platform - feedback/PRs on it are still welcome, but don't carry the same priority as core Linux
operation.

## Authors

- [**@Quahuay**](https://github.com/Quahuay) (Maintainer)

## License

MIT, see [LICENSE](LICENSE).

---

*Independent community project, no connection to the manufacturer/distributor of the llano brand*
*or of Myth.Cool. Mentioned brand names are only for recognizability, see*
*[Trademark Notice](#trademark-notice).*
