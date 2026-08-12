# Roadmap

*[Deutsche Version](../de/ROADMAP.md)*

As of v0.1.3, every dimension the hardware protocol actually exposes (color, effect, effect
speed, brightness, fan speed, power) is already wired into both the CLI and the GUI - see
[PROTOCOL.md](PROTOCOL.md) for the full byte-level reference and its "Unsupported operations"
section for what was tried against the device and doesn't work (arbitrary RGB, per-LED
addressing, display content manipulation). This roadmap is therefore not about catching up with
the hardware, it's about what's worth building on top of a complete protocol mapping.

Only the next milestone gets a version number. Everything after that is grouped by theme, not by
release, on purpose - this is a young, solo-maintained project and a dated multi-version roadmap
would over-promise. See [Contributing](README.md#contributing) for how to weigh in: GitHub issues
and PRs are how items here get picked up, refined, or reprioritized. Matching
[GitHub Milestones](https://github.com/Quahuay/llano-v12ultra-ctrl/milestones) exist for the
sections below so issues can attach to them.

## v0.2.0

- **Finish the auto-mode GUI** - `[auto.gpu_alert]` and `[auto.log]` currently only exist as
  config.toml sections with no GUI form (unlike the fan curve and fan reminder, which got theirs
  in v0.1.3). The config hot-reload built in v0.1.3 already covers whatever gets added here, so
  this is the cheapest remaining piece of that work.
- **`--json` output for `status` and `monitor`** - smallest possible diff, and the honest
  prerequisite for any scripting integration (see "Integration & Scripting" below) rather than
  jumping straight to a broker or API layer.
- **System tray icon** - there is currently zero tray code in the GUI. The auto-mode daemon
  already runs headless (systemd user service / Windows scheduled task), but the GUI window
  itself has no minimize-to-tray or quick-access story at all. Largest gap between what the app
  is and how it behaves.
- **Predefined fan curve presets** ("ramp-up programs", e.g. silent/balanced/performance),
  possibly differentiated by regulation characteristic (how aggressively they react to
  temperature change) rather than just different point sets. Scope/detail still open.
- **Profiles covering auto-mode/fan-curve config, not just manual values** - `profiles.py`
  currently saves color/effect/speed/brightness/power/fan_raw as static values. Extending a
  profile to also capture (and switch between) full auto-mode configurations is a natural
  follow-up once curve presets exist.
- **Portable Windows build (no installer)** - today there's only the `.msi`. cx_Freeze already
  produces a self-contained `build/exe.win-*/` folder as an intermediate step before wrapping it
  into the MSI (`packaging/msi/cx_freeze_setup.py`); zipping that folder as an additional release
  asset needs no new build tooling, just one more step in the existing `msi` job in
  [`release.yml`](../.github/workflows/release.yml).

## Later (no version attached)

### Integration & Scripting
Builds on `--json` above rather than skipping ahead to it.
- MQTT publish (temperature/fan/RPM telemetry + a command topic) for Home Assistant and similar
- Shell completion (bash/zsh/fish) for the CLI
- Example Waybar/Polybar/i3status module using `--json`
- Connecting to open RGB ecosystem standards (e.g. OpenRGB) so the pad can be coordinated
  alongside other RGB peripherals instead of only standalone
- Music/audio-reactive lighting (coupling color/effect to audio analysis)

### Desktop Integration
- Autostart of the GUI itself on login (distinct from the auto-mode background daemon, which
  already autostarts today)
- Minimize-to-tray behavior building on the v0.2.0 tray icon

### Quality & Maintenance
- Additional languages beyond the current English/German
- Linting (e.g. ruff) as a CI job, not just the existing test matrix
- Accessibility pass on the GUI (screen reader labels, keyboard navigation)

## Carried over from v0.1.x

Not new features - open work items from the previous cycle that are still open:
- **AUR submission** - needs the maintainer's AUR account, not a code task. Self-compile via
  `makepkg` already works and is documented ([Arch Instructions](README.md#arch-linux-self-compile)).
- **Windows auto-mode end-to-end verification** - `temp.py` correctly errors out without
  [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) running,
  but the full temperature-driven control loop with real values hasn't been verified against it
  yet (see [Windows Status](README.md#windows-status)). Needs a Windows machine with
  LibreHardwareMonitor actually running, i.e. community feedback - see
  [Contributing](README.md#contributing).

## Explicitly out of scope

- **macOS** - not planned, see [README](README.md#contributing): the pad isn't suited for Mac
  hardware.
- **Multi-device support** (distinguishing several connected pads, or supporting other llano V12
  hardware variants beyond the Ultra) - not implementable without that additional hardware on
  hand to test against. Would touch `device.py`'s device-selection logic on both platforms and
  the config schema (no device identifier exists anywhere today), so it's a cross-cutting change
  even before the hardware-access question. Feedback on other variants is still welcome per
  [Contributing](README.md#contributing) - it's excluded from active planning, not from interest.
- **Custom/arbitrary RGB values, per-LED addressing, display content manipulation** - not a
  software gap, the device itself doesn't support these; see PROTOCOL.md's
  ["Unsupported operations"](PROTOCOL.md) and HISTORY.md's "Checked afterwards, but not pursued
  further" for what was actually tried.
