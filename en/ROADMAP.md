# Roadmap

*[Deutsche Version](../de/ROADMAP.md)*

As of v0.1.3, every dimension the hardware protocol actually exposes (color, effect, effect
speed, brightness, fan speed, power) is already wired into both the CLI and the GUI. See
[PROTOCOL.md](PROTOCOL.md) for the full byte-level reference, and its "Unsupported operations"
section for what was tried against the device and doesn't work (arbitrary RGB, per-LED
addressing, display content manipulation). This roadmap isn't about catching up with the
hardware. It's about what's worth building on top of a complete protocol mapping.

Only the next milestone gets a version number. Everything after that is grouped by theme, not by
release. That's deliberate: this is a young, solo-maintained project, and a dated multi-version
roadmap would over-promise. See [Contributing](README.md#contributing) for how to weigh in.
GitHub issues and PRs are how items here get picked up, refined, or reprioritized. Matching
[GitHub Milestones](https://github.com/Quahuay/llano-v12ultra-ctrl/milestones) exist for the
sections below so issues can attach to them.

## v0.2.0

- **Finish the auto-mode GUI.** `[auto.gpu_alert]` and `[auto.log]` currently only exist as
  config.toml sections with no GUI form, unlike the fan curve and fan reminder, which got theirs
  in v0.1.3. The config hot-reload built in v0.1.3 already covers whatever gets added here, so
  this is the cheapest remaining piece of that work.
- **`--json` output for `status` and `monitor`.** The smallest possible diff, and the honest
  prerequisite for any scripting integration (see "Integration & Scripting" below) instead of
  jumping straight to a broker or API layer.
- **System tray icon.** There is currently zero tray code in the GUI. The auto-mode daemon
  already runs headless as a systemd user service or Windows scheduled task, but the GUI window
  itself has no minimize-to-tray or quick-access option at all. This is the largest gap between
  what the app is and how it behaves.
- **Predefined fan curve presets** such as silent, balanced, and performance "ramp-up programs,"
  possibly differentiated by regulation characteristic (how aggressively they react to
  temperature change) rather than just different point sets. Scope and detail are still open.
- **Profiles that cover auto-mode and fan-curve config, not just manual values.** `profiles.py`
  currently saves color, effect, speed, brightness, power, and fan_raw as static values.
  Extending a profile to also capture and switch between full auto-mode configurations is a
  natural follow-up once curve presets exist.
- **Portable Windows build with no installer.** Today there's only the `.msi`. cx_Freeze already
  produces a self-contained `build/exe.win-*/` folder as an intermediate step before wrapping it
  into the MSI (`packaging/msi/cx_freeze_setup.py`). Zipping that folder as an additional release
  asset needs no new build tooling, just one more step in the existing `msi` job in
  [`release.yml`](../.github/workflows/release.yml).

## Later, no version attached

### Integration & Scripting
Builds on `--json` above instead of skipping ahead to it.
- MQTT publish (temperature, fan, and RPM telemetry, plus a command topic) for Home Assistant and
  similar
- Shell completion (bash/zsh/fish) for the CLI
- An example Waybar/Polybar/i3status module using `--json`
- Connecting to open RGB ecosystem standards such as OpenRGB, so the pad can be coordinated
  alongside other RGB peripherals instead of only standalone
- Music- and audio-reactive lighting, coupling color and effect to audio analysis

### Desktop Integration
- Autostart of the GUI itself on login, distinct from the auto-mode background daemon, which
  already autostarts today
- Minimize-to-tray behavior, building on the v0.2.0 tray icon

### Quality & Maintenance
- Additional languages beyond the current English and German
- Linting, such as ruff, as a CI job, not just the existing test matrix
- An accessibility pass on the GUI: screen reader labels, keyboard navigation

## Carried over from v0.1.x

These aren't new features. They're open work items from the previous cycle that are still open.

- **AUR submission.** Needs the maintainer's AUR account, not a code task. Self-compiling via
  `makepkg` already works and is documented ([Arch Instructions](README.md#arch-linux-self-compile)).
- **Windows auto-mode end-to-end verification.** `temp.py` correctly errors out without
  [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) running,
  but the full temperature-driven control loop hasn't been verified against real values yet (see
  [Windows Status](README.md#windows-status)). This needs a Windows machine with
  LibreHardwareMonitor actually running: community feedback, in other words. See
  [Contributing](README.md#contributing).

## Explicitly out of scope

- **macOS.** Not planned, see [README](README.md#contributing): the pad isn't suited for Mac
  hardware.
- **Multi-device support**, meaning distinguishing several connected pads or supporting other
  llano V12 hardware variants beyond the Ultra. Not implementable without that additional
  hardware on hand to test against. It would also touch `device.py`'s device-selection logic on
  both platforms and the config schema, since no device identifier exists anywhere today, so it's
  a cross-cutting change even before the hardware-access question. Feedback on other variants is
  still welcome per [Contributing](README.md#contributing); this is excluded from active
  planning, not from interest.
- **Custom or arbitrary RGB values, per-LED addressing, display content manipulation.** Not a
  software gap: the device itself doesn't support these. See PROTOCOL.md's
  ["Unsupported operations"](PROTOCOL.md) and HISTORY.md's "Checked afterwards, but not pursued
  further" for what was actually tried.
