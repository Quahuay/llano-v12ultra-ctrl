# Development history: how fan speed control was found

This file summarizes how the protocol for `llano-v12ultra-ctrl` was reverse-engineered, including
the dead ends along the way. It's not needed for plain usage, see [README.md](README.md) instead.
The full byte-by-byte derivation with all measurement series lives as an addendum docstring in
[`protocol.py`](../src/llano_v12ultra_ctrl/protocol.py).

## Starting point

The pad has no documentation for its HID protocol. The starting point was a USB capture of the
official Windows app (Myth.Cool), plus the device's own HID report descriptor (three reports:
64-byte input, 64-byte output, 8-byte feature).

## Light, color, brightness: found relatively quickly

The 9-byte feature report could be fully derived through targeted comparison tests (change an app
setting, compare the report before/after) for color, effect, effect speed, brightness, and an
on/off kill switch, including the checksum formula.

## Fan speed: the long dead end

The app shows a full RPM selection UI (AI Low/Medium/High modes, a custom fan curve, manual mode
via the physical wheel). The obvious first approach was writing along an extra byte in the light
report that was sometimes non-zero in real app captures. At the time this was recorded as
consistently ineffective:

- An original USB capture of the real app contained over 1300 real SET_REPORT calls, but none of
  them a recognizably targeted fan speed write attempt.
- A full fuzz of all output report positions (every byte position x every value) showed no lasting
  effect.
- A static analysis of `MythCool.exe`/`GPP_USB_Center.exe` found real, functional-looking code (an
  `LJN_LAP_FAN` class, demonstrably processing a `SetLapFanParam`/`fan_speed` command from JSON).
  So the feature is genuinely implemented in software, but the exact translation path to USB
  couldn't be found in the code.
- A live test under Wine failed on a separate problem: the app doesn't detect the device at all
  under Wine.
- A live test in a Windows 11 VM (real USB passthrough) correctly detected the device and showed
  the full RPM UI, but there too, not a single real fan speed write attempt. Explainable in
  hindsight, since only the temperature-dependent AI modes were clicked (not manual custom mode),
  and because a VM doesn't provide real, changing sensor values that would prompt the AI logic to
  recompute anyway.

## The breakthrough: real hardware, a real click in custom mode

An SSH-remotable, real (not virtual) Windows 10 machine was set up, USBPcap/Wireshark installed,
and a live capture recorded alongside manually operating the real app, this time using a self-set
custom fan curve instead of the AI modes. Result: a previously unobserved, completely standalone
HID command, clearly distinguishable from the light command (a different byte-0 tag, a fixed
subcommand tag). In hindsight, that's why every earlier test stayed ineffective: they simply wrote
the wrong command.

Confirmed live, both on the Windows test machine and directly on the Linux device itself,
individually tested across the entire value range (each of the 100 possible raw values on its own,
roughly 25 RPM resolution per step).

## Correction: the first approach was not wrong after all

Measured on 2026-08-12, months after the above was written: **that extra byte in the light report
is the fan speed field.** Writing a value there sets the fan speed, and writing zero stops the fan.
The original conclusion was wrong.

What went wrong at the time is worth recording, because it is a general trap. The early tests
wrote that byte and then checked whether the fan changed. It did change, but every one of those
tests ran with the auto-mode daemon active in the background, and that daemon issued its own light
commands every few seconds with the byte left at zero. Each test write was undone within seconds
by a process nobody was thinking about. The measurement was not of the device, it was of the
device plus an unnoticed second writer.

The finding resurfaced only because the same interference produced a symptom that could not be
explained away: fan speed readings intermittently dropping to zero during unrelated work. Stopping
the daemon and repeating the measurement made the effect disappear, which pointed straight at the
real mechanism.

Two lessons, both now reflected in the documentation:

- A measurement against shared hardware is only valid with exclusive access. `PROTOCOL.md` states
  this as a device property, because any implementation faces the same hazard.
- "Tested and does not work" deserves the same scepticism as any other claim. It was recorded here
  as settled fact and stood unchallenged for months.

The practical consequence for this project was a real bug: every color change stopped the fan,
which made the fan curve unusable in combination with the temperature indicator. Fixed by carrying
the current fan speed in that byte on every light command.

## Checked afterwards, but not pursued further

- Values beyond the documented range (up to 255): the device accepts and displays them, but the
  real speed stays put once it reaches the documented maximum. Only the telemetry keeps counting up
  unbounded.
- Whether the pad display's content itself (not just the displayed number) can be deliberately
  manipulated: no known separate command found for this, not pursued further.
