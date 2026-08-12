# llano V12 Ultra: USB-HID Protocol Reference

Complete description of the USB-HID protocol of the **llano V12 Ultra** RGB laptop cooling pad, so
you can talk to the device from your own code in any language, without using this project.

Everything here was reverse-engineered from USB captures of the manufacturer's Windows app
(Myth.Cool) and verified by live tests against real hardware. Where a claim was measured, the
measurement is stated. Where something is an inference, it says so.

> This project is not affiliated with, endorsed by, or authorized by the manufacturer of the llano
> brand or the Myth.Cool software. See the trademark notice in [README.md](README.md).

**Reference implementation:** [`src/llano_v12ultra_ctrl/protocol.py`](src/llano_v12ultra_ctrl/protocol.py)
(byte layout, checksum, parsing) and [`device.py`](src/llano_v12ultra_ctrl/device.py) (transport).
The narrative of how this was found, including the dead ends, is in [HISTORY.md](HISTORY.md).

## Table of Contents

- [Device identification](#device-identification)
- [Report descriptor](#report-descriptor)
- [The 9-byte feature report](#the-9-byte-feature-report)
- [Checksum](#checksum)
- [Command 1: light](#command-1-light)
- [Command 2: fan speed](#command-2-fan-speed)
- [Reading telemetry](#reading-telemetry)
- [Value ranges and limits](#value-ranges-and-limits)
- [Transport: Linux](#transport-linux)
- [Transport: Windows](#transport-windows)
- [Complete minimal examples](#complete-minimal-examples)
- [Behavior notes and pitfalls](#behavior-notes-and-pitfalls)
- [What does not exist](#what-does-not-exist)

## Device identification

| Property | Value |
|---|---|
| Vendor ID | `0x374A` |
| Product ID | `0xB101` |
| Controller | Holtek |
| Interface | USB HID |

The pad enumerates as a plain HID device. No vendor driver, no custom interface, no bulk endpoints.

## Report descriptor

The full HID report descriptor was read out (`/sys/class/hidraw/hidrawN/device/report_descriptor`)
and contains exactly **three** reports, with no report IDs beyond these:

| Report | Size | Direction | Purpose |
|---|---|---|---|
| Feature | 8 bytes + report ID | host to device, device to host | **All control and all telemetry.** This is the only one you need. |
| Input | 64 bytes | device to host | No known content-dependent meaning. See [What does not exist](#what-does-not-exist). |
| Output | 64 bytes | host to device | No known control function. See [What does not exist](#what-does-not-exist). |

Everything useful happens on the **feature report**. The 64-byte input and output reports were
tested extensively and carry no controllable function.

## The 9-byte feature report

On the wire the feature report body is 8 bytes. Both Linux `HIDIOCSFEATURE`/`HIDIOCGFEATURE` and
hidapi expect the **report ID prepended**, so in practice you always work with a 9-byte buffer:

```
Index:  0        1       2       3       4       5       6       7       8
      +--------+-------+-------+-------+-------+-------+-------+-------+--------+
      |report  |byte0  |byte1  |byte2  |byte3  |byte4  |byte5  |byte6  |checksum|
      |id=0x00 |       |       |       |       |       |       |       |        |
      +--------+-------+-------+-------+-------+-------+-------+-------+--------+
                \_________________ body7, feeds the checksum _________________/
```

The naming `byte0..byte6` refers to the **body**, not the buffer index. Body `byteN` sits at buffer
index `N+1`. The checksum covers body bytes 0 to 6 only, never the report ID.

**`byte0` selects the command.** This is the single most important field, and the thing that took
longest to find:

| `byte0` | Command |
|---|---|
| `0x00` | Light (color, effect, brightness, master on/off) |
| `0x01` | Set fan speed |
| `0x80` | Heartbeat, as sent by the original app. Not needed to control the device. |

Two entirely separate commands share one report. Writing a fan speed into the light command does
nothing at all: the device ignores that field there. This is why fan control looked impossible for
so long.

## Checksum

```
checksum = (0xFF - sum(body0..body6)) & 0xFF
```

Python:

```python
def checksum(body7):
    return (0xFF - sum(body7)) & 0xFF
```

The device rejects reports with a wrong checksum. Reports read back from the device carry a valid
checksum, so you can use it to sanity-check your read path.

## Command 1: light

`byte0 = 0x00`

| Body byte | Buffer index | Meaning | Range |
|---|---|---|---|
| `byte0` | 1 | Command tag, always `0x00` | `0x00` |
| `byte1` | 2 | Sent by the original app, **no effect on fan speed**. Read back it is the fan-speed telemetry field. | `0x00` when writing |
| `byte2` | 3 | Master kill switch. `0x00` = unit on, any non-zero = **fan and light both off** | `0x00` / `0x01` |
| `byte3` | 4 | Light effect, or `>= 0x80` to switch the light off | `0x00`-`0x04`, `0x80` |
| `byte4` | 5 | Color | `0x00`-`0x04` |
| `byte5` | 6 | Effect speed | `0x00`-`0x03` validated |
| `byte6` | 7 | Brightness | `0x00`-`0xFF` |

### Colors (`byte4`)

| Value | Color |
|---|---|
| 0 | red |
| 1 | lightblue |
| 2 | green |
| 3 | purple |
| 4 | orange |

### Effects (`byte3`)

| Value | Effect |
|---|---|
| 0 | solid |
| 1 | breathing |
| 2 | rainbow |
| 3 | chase |
| 4 | zones |
| `>= 0x80` | light off (fan keeps running) |

### Effect speed (`byte5`)

`0` = fast to `3` = slow. The original app only ever emits 0 to 3. Values above 3 are accepted but
do **not** behave monotonically, so treat 0-3 as the usable range.

### Master switch (`byte2`)

`byte2 != 0` is a pure kill switch for the **whole unit**: fan motor and lighting both stop. There
are no intermediate levels. Any non-zero value behaves identically; this project uses `0x01`.

Note the difference: `byte3 >= 0x80` turns off **only the light** and leaves the fan running,
whereas `byte2 != 0` stops **everything**.

## Command 2: fan speed

`byte0 = 0x01`

This is the command that actually sets fan speed. It was found by capturing USB traffic while
driving a manually configured custom fan curve in the original app on real (non-virtual) Windows
hardware.

| Body byte | Buffer index | Value | Meaning |
|---|---|---|---|
| `byte0` | 1 | `0x01` | Command tag: set fan speed |
| `byte1` | 2 | `0x01`-`0x64` | **Fan speed, raw scale 1 to 100** |
| `byte2` | 3 | `0x00` | fixed |
| `byte3` | 4 | `0x00` | fixed |
| `byte4` | 5 | `0x02` | Subcommand tag, fixed |
| `byte5` | 6 | `0x00` | fixed |
| `byte6` | 7 | `0xFF` | fixed |

Only `byte1` varies. Everything else is constant.

### Speed scale

| raw | RPM |
|---|---|
| 1 | 300 |
| 48 | 1500 |
| 100 | 2800 |

Roughly **25 RPM per raw step**. All 100 raw values were individually tested against the pad's own
display; each produces a distinct speed. The three reference points above were measured exactly.

The display value can be approximated as:

```python
level = round((raw - 1) * 25 / 99)
rpm   = 300 + level * 100     # coarse, rounded to 100 RPM steps
```

That formula reproduces the pad's own rounded display, not the true speed. The real hardware
responds to every individual raw value in roughly 25 RPM increments.

## Reading telemetry

Read the feature report (`HIDIOCGFEATURE` / `hid_get_feature_report`) with report ID `0x00`. The
9 bytes you get back are the **current device state**, using a different field layout than what you
write:

| Buffer index | Field | Notes |
|---|---|---|
| 0 | report ID | `0x00` |
| 1 | `byte0` | |
| 2 | **fan speed raw** | 1-100 scale, same as the fan command's `byte1` |
| 3 | **kill flag** | `0x00` = unit on |
| 4 | **effect** | `< 0x80` means light is on |
| 5 | **color** | |
| 6 | **effect speed** | |
| 7 | **brightness** | |
| 8 | checksum | |

So one read gives you fan speed, master state, light state, color, effect, speed and brightness at
once. This works regardless of whether the speed was set by software or by the physical wheel on
the pad.

## Value ranges and limits

| Field | Accepted | Actually useful | Behavior outside the useful range |
|---|---|---|---|
| Fan speed raw | 0-255 | **1-100** | Values above 100 are accepted and echoed back, but the real speed stays at maximum. Only the display keeps extrapolating; raw=255 shows a nonsensical 6675 RPM. |
| Color | 0-255 | **0-4** | Undocumented, not tested |
| Effect | 0-255 | **0-4**, `>= 0x80` = off | Values between 5 and 0x7F are undocumented |
| Effect speed | 0-255 | **0-3** | Above 3 is accepted but not monotonic |
| Brightness | 0-255 | **0-255** | 0 is effectively invisible |

**Clamp fan speed to 1-100 in your own code.** The device will not protect you, and values above
100 buy nothing but a wrong display.

## Transport: Linux

Use raw `/dev/hidraw*` ioctls. No library required.

Finding the device via sysfs:

```python
import glob

def find_hidraw():
    for uevent in glob.glob("/sys/class/hidraw/hidraw*/device/uevent"):
        with open(uevent) as f:
            content = f.read().upper()
        if "374A" in content and "B101" in content:
            return "/dev/" + uevent.split("/")[4]
    return None
```

The ioctl numbers, encoded manually so no C headers are needed:

```python
def _ioc(direction, typ, nr, size):
    return (direction << 30) | (ord(typ) << 8) | nr | (size << 16)

HIDIOCGFEATURE = lambda length: _ioc(3, "H", 0x07, length)  # read
HIDIOCSFEATURE = lambda length: _ioc(3, "H", 0x06, length)  # write
```

Both use direction `3` (`_IOC_READ | _IOC_WRITE`).

### Permissions

Without a udev rule you need root. Rule used by this project
([`packaging/70-llano-v12ultra-ctrl.rules`](packaging/70-llano-v12ultra-ctrl.rules)):

```
SUBSYSTEM=="usb", ATTR{idVendor}=="374a", ATTR{idProduct}=="b101", MODE="0660", GROUP="plugdev", TAG+="uaccess"
KERNEL=="hidraw*", ATTRS{idVendor}=="374a", ATTRS{idProduct}=="b101", MODE="0660", GROUP="plugdev", TAG+="uaccess"
```

Install it, reload with `udevadm control --reload-rules && udevadm trigger`, and make sure your
user is in `plugdev`.

### Do not use hidapi on Linux for this device

Measured on this hardware: `hid.device().open()` triggers a **full USB rebind on every call**,
reproducibly, 5 out of 5 cycles. For a tool that opens and closes frequently that is unusable. Raw
hidraw ioctls do not have this problem. On Windows the same library is fine (different backend).

## Transport: Windows

There is no hidraw equivalent, so use hidapi. From Python, the `hid` package (official
libusb/hidapi bindings):

```python
import hid

dev = hid.Device(vid=0x374A, pid=0xB101)
dev.send_feature_report(buffer9)          # write, raw bytes
raw = dev.get_feature_report(0x00, 9)     # read
```

Two traps, both cost real debugging time:

1. **API shape.** It is `hid.Device(vid=, pid=)` with `.read(size, timeout=ms)`. An older
   cython-hidapi exposes `hid.device()` / `.open()` / `timeout_ms=` instead. Code written against
   the wrong one fails immediately.
2. **The native DLL is not bundled.** The PyPI `hid` package is only a ctypes wrapper. You also
   need `hidapi.dll` somewhere in the DLL search path (for example next to `python.exe`).
   Official builds: [github.com/libusb/hidapi/releases](https://github.com/libusb/hidapi/releases).

Pass raw `bytes` to `send_feature_report`, not a `list`.

The USB-rebind problem seen on Linux does **not** occur here.

## Complete minimal examples

Self-contained, no dependency on this project.

### Linux: set fan speed to 50

```python
import fcntl, glob, os, ctypes

def find_hidraw():
    for uevent in glob.glob("/sys/class/hidraw/hidraw*/device/uevent"):
        with open(uevent) as f:
            if "374A" in f.read().upper():
                return "/dev/" + uevent.split("/")[4]

def checksum(body7):
    return (0xFF - sum(body7)) & 0xFF

def build_fan_report(raw):
    assert 1 <= raw <= 100
    body7 = [0x01, raw, 0x00, 0x00, 0x02, 0x00, 0xFF]
    return bytes([0x00] + body7 + [checksum(body7)])

def _ioc(d, t, nr, size):
    return (d << 30) | (ord(t) << 8) | nr | (size << 16)

fd = os.open(find_hidraw(), os.O_RDWR)
buf = ctypes.create_string_buffer(build_fan_report(50), 9)
fcntl.ioctl(fd, _ioc(3, "H", 0x06, 9), buf, True)   # HIDIOCSFEATURE
os.close(fd)
```

### Linux: read current state

```python
buf = ctypes.create_string_buffer(9)
buf[0] = b"\x00"
fcntl.ioctl(fd, _ioc(3, "H", 0x07, 9), buf, True)   # HIDIOCGFEATURE
raw = buf.raw
print("fan raw   :", raw[2])
print("unit on   :", raw[3] == 0x00)
print("light on  :", raw[4] < 0x80)
print("color     :", raw[5])
print("effect    :", raw[4])
print("brightness:", raw[7])
```

### Linux: solid green at full brightness

```python
def build_light_report(color, effect=0, speed=0, brightness=0xFF, light_on=True, power=True):
    body7 = [
        0x00,                                  # command: light
        0x00,                                  # no effect on fan speed
        0x00 if power else 0x01,               # master kill switch
        (0x80 if not light_on else effect),    # effect / light off
        color,
        speed,
        brightness,
    ]
    return bytes([0x00] + body7 + [checksum(body7)])

buf = ctypes.create_string_buffer(build_light_report(color=2), 9)   # 2 = green
fcntl.ioctl(fd, _ioc(3, "H", 0x06, 9), buf, True)
```

### Windows: same three operations

```python
import hid

dev = hid.Device(vid=0x374A, pid=0xB101)
dev.send_feature_report(build_fan_report(50))            # fan speed
dev.send_feature_report(build_light_report(color=2))     # solid green
raw = bytes(dev.get_feature_report(0x00, 9))             # read state
print("fan raw:", raw[2])
```

`build_fan_report`, `build_light_report` and `checksum` are identical on both platforms. Only the
transport differs.

## Behavior notes and pitfalls

**Fan speed telemetry is a setpoint, not a tachometer.** Once settled, `fan_speed_raw` stayed
exactly constant across ten consecutive reads (raw=43) while the pad's **physical display**
oscillated between 1550 and 1375 RPM in the same period. The likely explanation: the field holds
the firmware's stored target value, while the display shows a live, slightly noisy measured speed.
Do not expect the read-back value to track real RPM exactly.

**Motor spin-up takes seconds.** Right after a write, several consecutive reads show changing
values before settling. That is mechanical, not a software bug. Give it a few seconds before
trusting a reading you just caused.

**The physical wheel keeps working.** It is a parallel input, not disabled by software control. The
telemetry field reflects wheel changes too, so you can read the wheel position.

**Light and fan are fully independent.** Turning off the light (`byte3 >= 0x80`) leaves the fan
running. Only `byte2 != 0` stops both.

**Read back to confirm.** The reliable way to verify a write landed is to read the feature report
afterwards and compare. That is what this project's `set_*` methods do: they write, then return a
fresh read.

**Unplugging raises errors mid-sequence.** On Linux you get `OSError` (`Errno 19, No such device`)
from the ioctl. If you write a long-running daemon, wrap **both** reads and writes; a device can
disappear between two calls in the same iteration.

## What does not exist

Things that were specifically tested and found **not** to work, so you do not repeat the search:

- **No fan control via the light command.** Writing a speed value into `byte1` of the `byte0=0x00`
  command is silently ignored. This was the single biggest dead end.
- **No hidden report IDs.** The descriptor was dumped and contains exactly three reports.
- **The 64-byte output report has no control function.** Every one of its 64 byte positions was
  tested individually across the value range, plus patterns like all-zeros and all-`0xFF`. Writing
  to it produces a brief visible flicker but no controllable, persistent effect.
- **The 64-byte input report has no known content-dependent meaning.** You can observe it
  (`llano-v12ultra-ctrl raw-input`) but nothing there decodes into useful state beyond what the
  feature report already gives you.
- **No display control.** There is no known command to write arbitrary content to the pad's
  numeric display. It only ever shows its own derived speed value, including the nonsensical
  extrapolation above raw=100.
- **No per-zone RGB addressing.** `effect=4` is called "zones" but is a preset pattern, not an
  addressable-LED interface. There is no way to set individual LEDs.

## Contributing corrections

If you have a different llano V12 variant, or find behavior that contradicts this document, please
open an issue with your measurements. The documentation style here is deliberately evidence-first:
state what was measured, how, and on which hardware. See [Contributing](README.md#contributing).
