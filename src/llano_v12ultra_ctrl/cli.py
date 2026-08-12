import argparse
import os
import sys
import time

from . import config as config_mod
from . import device as device_mod
from . import fan_curve as fan_curve_mod
from . import history as history_mod
from . import i18n
from . import notify as notify_mod
from . import protocol
from . import temp as temp_mod
from . import update_check as update_check_mod


def _yn(value):
    return i18n.t("common.on") if value else i18n.t("common.off")


def _maybe_print_update_notice():
    """Einzeiliger, leiser Hinweis bei status/auto, falls eine neuere
    Version existiert (siehe update_check.py - 24h-Cache, kein Netzwerk-Call
    bei jedem Aufruf). Per [general] update_check=false abschaltbar."""
    cfg = config_mod.load_config()
    if not cfg.get("general", {}).get("update_check", True):
        return
    latest = update_check_mod.check_for_update()
    if latest:
        print(i18n.t(
            "update.cli.available", latest=latest, current=update_check_mod.CURRENT_VERSION,
            url=update_check_mod.RELEASES_URL,
        ))


def cmd_status(args):
    _maybe_print_update_notice()
    with device_mod.Device() as dev:
        r = dev.get_report()
    print(i18n.t("cli.status.device", path=dev.path))
    print(i18n.t("cli.status.raw_report", hex=r.raw.hex(" ")))
    print(i18n.t("cli.status.checksum_ok", ok=r.checksum_ok))
    print(i18n.t("cli.status.power", state=_yn(r.power_on)))
    print(i18n.t("cli.status.fan_speed", rpm=r.fan_rpm, raw=r.fan_speed_raw))
    print(i18n.t("cli.status.light", state=_yn(r.light_on)))
    print(i18n.t("cli.status.color", color=r.color, name=r.color_name()))
    print(i18n.t("cli.status.effect", effect=r.effect_raw, name=r.effect_name()))
    print(i18n.t("cli.status.speed", speed=r.speed))
    print(i18n.t("cli.status.brightness", brightness=r.brightness))
    return 0


def _resolve_choice(value, name_map, label):
    if value in name_map:
        return name_map[value]
    try:
        v = int(value)
    except ValueError:
        raise SystemExit(i18n.t("cli.error.invalid_choice", label=label, value=value, names=", ".join(name_map)))
    if not 0 <= v <= 4:
        raise SystemExit(i18n.t("cli.error.choice_range", label=label))
    return v


def cmd_light(args):
    with device_mod.Device() as dev:
        if args.off:
            r = dev.set_light(color=0, light_on=False)
            print(i18n.t("cli.light.off_done", raw=r.raw.hex(" ")))
            return 0
        current = dev.get_report()
        color = _resolve_choice(args.color, protocol.NAME_TO_COLOR, i18n.t("cli.label.color")) if args.color is not None else current.color
        effect = _resolve_choice(args.effect, protocol.NAME_TO_EFFECT, i18n.t("cli.label.effect")) if args.effect is not None else (current.effect_raw if current.light_on else 0)
        speed = args.speed if args.speed is not None else current.speed
        brightness = args.brightness if args.brightness is not None else current.brightness
        r = dev.set_light(color=color, effect=effect, speed=speed, light_on=True, brightness=brightness)
    print(i18n.t(
        "cli.light.set_done",
        color=r.color, cname=r.color_name(), effect=r.effect_raw, ename=r.effect_name(),
        speed=r.speed, brightness=r.brightness, raw=r.raw.hex(" "),
    ))
    return 0


def cmd_power(args):
    with device_mod.Device() as dev:
        r = dev.set_power(power=(args.state == "on"))
    if r.power_on:
        print(i18n.t("cli.power.on_done", raw=r.raw.hex(" ")))
    else:
        print(i18n.t("cli.power.off_done", raw=r.raw.hex(" ")))
    return 0


def cmd_fan_speed(args):
    with device_mod.Device() as dev:
        r = dev.set_fan_speed(args.raw)
    print(i18n.t("cli.fan_speed.set_done", raw=args.raw, rpm=r.fan_rpm, raw2=r.fan_speed_raw))
    return 0


def cmd_monitor(args):
    print(i18n.t("cli.monitor.watching"))
    last = None
    with device_mod.Device() as dev:
        try:
            while True:
                r = dev.get_report()
                if r.raw != last:
                    ts = time.strftime("%H:%M:%S")
                    print(i18n.t(
                        "cli.monitor.line",
                        ts=ts, rpm=r.fan_rpm, color=r.color, cname=r.color_name(),
                        effect=r.effect_raw, ename=r.effect_name(), speed=r.speed, raw=r.raw.hex(" "),
                    ), flush=True)
                    last = r.raw
                time.sleep(args.interval)
        except KeyboardInterrupt:
            pass
    return 0


def cmd_raw_input(args):
    print(i18n.t("cli.raw_input.intro"))
    with device_mod.Device() as dev:
        try:
            while True:
                raw = dev.read_input_report(timeout_s=args.timeout)
                if raw is not None:
                    ts = time.strftime("%H:%M:%S")
                    print(i18n.t("cli.raw_input.line", ts=ts, raw=raw.hex(" ")), flush=True)
        except KeyboardInterrupt:
            pass
    return 0


def _config_mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _load_auto_settings(auto_cfg):
    """Leitet die für die Laufzeit relevanten Werte aus dem [auto]-Config-Block
    ab - zentral, damit der Erststart und der Hot-Reload weiter unten exakt
    denselben Code benutzen und nicht auseinanderlaufen können. `temp_sensor`
    ist bewusst NICHT Teil davon: der wird nur einmal beim Start aufgelöst
    (siehe cmd_auto) - ein Sensorpfad-Wechsel mitten im Lauf ist weder ein
    erwarteter Anwendungsfall noch gefahrlos (Auto-Erkennung könnte kurzzeitig
    nichts finden und den laufenden Betrieb stören)."""
    thresholds = sorted(auto_cfg["thresholds"], key=lambda t: t["temp_c"])
    gpu_cfg = auto_cfg.get("gpu_alert", {})
    fan_cfg = auto_cfg.get("fan_reminder", {})
    curve_cfg = auto_cfg.get("fan_curve", {})
    log_cfg = auto_cfg.get("log", {})
    return {
        "thresholds": thresholds,
        "hysteresis": auto_cfg.get("hysteresis_c", 3),
        "interval": auto_cfg.get("poll_interval_s", 5),
        "gpu_cfg": gpu_cfg,
        "gpu_enabled": gpu_cfg.get("enabled", False),
        "fan_cfg": fan_cfg,
        "fan_reminder_enabled": fan_cfg.get("enabled", False),
        "curve_cfg": curve_cfg,
        "fan_curve_enabled": curve_cfg.get("enabled", False),
        "curve_min_change": curve_cfg.get("min_change_raw", 3),
        "log_cfg": log_cfg,
        "logger": history_mod.HistoryLogger(log_cfg["path"]) if log_cfg.get("enabled", False) else None,
    }


def cmd_auto(args):
    _maybe_print_update_notice()
    config_path = args.config or config_mod.DEFAULT_CONFIG_PATH
    cfg = config_mod.load_config(args.config)
    auto_cfg = cfg["auto"]

    sensor_path = auto_cfg.get("temp_sensor") or temp_mod.find_cpu_temp_input()
    if not sensor_path:
        print(i18n.t("cli.auto.no_sensor"), file=sys.stderr)
        return 1
    print(i18n.t("cli.auto.sensor", path=sensor_path))

    settings = _load_auto_settings(auto_cfg)
    thresholds, hysteresis, interval = settings["thresholds"], settings["hysteresis"], settings["interval"]
    gpu_cfg, gpu_enabled = settings["gpu_cfg"], settings["gpu_enabled"]
    fan_cfg, fan_reminder_enabled = settings["fan_cfg"], settings["fan_reminder_enabled"]
    curve_cfg, fan_curve_enabled, curve_min_change = (
        settings["curve_cfg"], settings["fan_curve_enabled"], settings["curve_min_change"],
    )
    log_cfg, logger = settings["log_cfg"], settings["logger"]
    last_config_mtime = _config_mtime(config_path)

    print(i18n.t("cli.auto.thresholds", thresholds=thresholds, hysteresis=hysteresis, interval=interval))
    if gpu_enabled:
        print(i18n.t(
            "cli.auto.gpu_alert",
            temp_c=gpu_cfg["temp_c"], off_temp_c=gpu_cfg["temp_c"] - gpu_cfg["hysteresis_c"],
            color=gpu_cfg["color"], effect=gpu_cfg["effect"],
        ))
    if fan_reminder_enabled:
        print(i18n.t(
            "cli.auto.fan_reminder",
            temp_c=fan_cfg["temp_c"], min_rpm=fan_cfg["min_rpm"], cooldown_s=fan_cfg.get("cooldown_s", 300),
        ))
    if fan_curve_enabled:
        pts = fan_curve_mod.sorted_points(curve_cfg["points"])
        pts_str = ", ".join(f"{p['temp_c']}°C->{p['raw']}" for p in pts)
        print(i18n.t("cli.auto.fan_curve", points=pts_str, min_change=curve_min_change))
    if logger:
        print(i18n.t("cli.auto.log_path", path=logger.path))

    current_color = None
    current_effect = 0
    current_temp = None  # Temperatur der aktuell aktiven Schwelle (für Hysterese)
    gpu_alert_active = False
    last_reminder_ts = 0.0
    current_fan_raw = None
    current_speed = None  # zuletzt geschriebene Effekt-Geschwindigkeit
    try:
        with device_mod.Device() as dev:
            while True:
                # Der GESAMTE Zyklus liegt im try, nicht nur die Lesezugriffe:
                # set_light/set_fan_speed können genauso ein OSError werfen,
                # wenn das Pad mitten im Durchlauf abgezogen wird. Lag der
                # Schreibpfad außerhalb, ist der Daemon dabei mit einem
                # Traceback gestorben, statt es wie einen Lesefehler zu
                # behandeln und beim Wiedereinstecken weiterzulaufen.
                try:
                    # Config-Hot-Reload (seit v0.1.3): die Schleife wacht
                    # ohnehin alle `interval`s Sekunden auf, ein zusätzlicher
                    # mtime-Stat ist praktisch gratis. Vorher wirkte z.B.
                    # "Lüfterkurve speichern" in der GUI erst beim nächsten
                    # Neustart des Daemons - siehe README, "Fan Curve & Fan
                    # Reminder".
                    current_mtime = _config_mtime(config_path)
                    if current_mtime is not None and current_mtime != last_config_mtime:
                        last_config_mtime = current_mtime
                        try:
                            reloaded_auto_cfg = config_mod.load_config(args.config)["auto"]
                            settings = _load_auto_settings(reloaded_auto_cfg)
                        except Exception as e:
                            # z.B. TOML noch halb geschrieben/kaputt bearbeitet -
                            # alte Einstellungen behalten statt abzustürzen, beim
                            # nächsten echten Speichern (neue mtime) erneut versuchen.
                            print(
                                f"[{time.strftime('%H:%M:%S')}] "
                                f"{i18n.t('cli.auto.config_reload_error', error=e)}",
                                flush=True,
                            )
                        else:
                            thresholds, hysteresis, interval = (
                                settings["thresholds"], settings["hysteresis"], settings["interval"],
                            )
                            gpu_cfg, gpu_enabled = settings["gpu_cfg"], settings["gpu_enabled"]
                            fan_cfg, fan_reminder_enabled = settings["fan_cfg"], settings["fan_reminder_enabled"]
                            curve_cfg, fan_curve_enabled, curve_min_change = (
                                settings["curve_cfg"], settings["fan_curve_enabled"], settings["curve_min_change"],
                            )
                            log_cfg, logger = settings["log_cfg"], settings["logger"]
                            print(f"[{time.strftime('%H:%M:%S')}] {i18n.t('cli.auto.config_reloaded')}", flush=True)

                    t = temp_mod.read_temp_c(sensor_path)
                    gpu_t = temp_mod.read_gpu_temp_c() if gpu_enabled else None
                    report = dev.get_report()

                    cpu_color, cpu_effect, cpu_speed = current_color, current_effect, 0
                    active_temp = None
                    if t is not None:
                        cpu_color = thresholds[0]["color"]
                        cpu_effect = thresholds[0].get("effect", 0)
                        cpu_speed = thresholds[0].get("speed", 0)
                        active_temp = thresholds[0]["temp_c"]
                        for th in thresholds:
                            limit = th["temp_c"]
                            # Kühlt die CPU ab (aktuell aktive Schwelle liegt
                            # oberhalb dieser Schwelle), verschiebe den Grenzwert
                            # um die Hysterese nach unten.
                            if current_temp is not None and th["temp_c"] <= current_temp:
                                limit -= hysteresis
                            if t >= limit:
                                cpu_color = th["color"]
                                cpu_effect = th.get("effect", 0)
                                cpu_speed = th.get("speed", 0)
                                active_temp = th["temp_c"]

                    if gpu_enabled and gpu_t is not None:
                        if not gpu_alert_active and gpu_t >= gpu_cfg["temp_c"]:
                            gpu_alert_active = True
                        elif gpu_alert_active and gpu_t < gpu_cfg["temp_c"] - gpu_cfg["hysteresis_c"]:
                            gpu_alert_active = False

                    # "whichever is hotter wins": GPU alert only kicks in when
                    # active AND the GPU is at least as hot as the CPU -
                    # otherwise the normal CPU color logic still wins.
                    if gpu_alert_active and gpu_t is not None and (t is None or gpu_t >= t):
                        target_color, target_effect, target_speed = gpu_cfg["color"], gpu_cfg["effect"], gpu_cfg.get("speed", 0)
                    else:
                        target_color, target_effect, target_speed = cpu_color, cpu_effect, cpu_speed

                    if target_color is not None and (target_color, target_effect, target_speed) != (current_color, current_effect, current_speed):
                        r = dev.set_light(color=target_color, effect=target_effect, speed=target_speed, power=True)
                        ts = time.strftime("%H:%M:%S")
                        gpu_info = f"  GPU={gpu_t:.1f}°C" if gpu_t is not None else ""
                        cpu_info = f"{t:.1f}°C" if t is not None else "?"
                        print(i18n.t(
                            "cli.auto.color_change", ts=ts, cpu_info=cpu_info, gpu_info=gpu_info,
                            color_name=r.color_name(), effect_name=r.effect_name(),
                        ), flush=True)
                        current_color, current_effect, current_speed = target_color, target_effect, target_speed
                    if target_color is not None:
                        current_temp = active_temp if t is not None else current_temp

                    if fan_curve_enabled and t is not None:
                        target_fan_raw = fan_curve_mod.raw_for_temp(curve_cfg["points"], t)
                        if current_fan_raw is None or abs(target_fan_raw - current_fan_raw) >= curve_min_change:
                            report = dev.set_fan_speed(target_fan_raw)
                            ts = time.strftime("%H:%M:%S")
                            print(i18n.t(
                                "cli.auto.fan_curve_change", ts=ts, temp=t, raw=target_fan_raw, rpm=report.fan_rpm,
                            ), flush=True)
                            current_fan_raw = target_fan_raw

                    # Reminder: CPU hot, but measured speed stays low - e.g.
                    # useful while fan_curve (above) isn't enabled.
                    if fan_reminder_enabled and t is not None and t >= fan_cfg["temp_c"] and report.fan_rpm < fan_cfg["min_rpm"]:
                        now = time.time()
                        if now - last_reminder_ts >= fan_cfg.get("cooldown_s", 300):
                            notify_mod.send(
                                i18n.t("cli.auto.notify_title"),
                                i18n.t("cli.auto.notify_body", temp=t, rpm=report.fan_rpm),
                            )
                            last_reminder_ts = now

                    if logger:
                        log_color = current_color if current_color is not None else report.color
                        log_effect = current_effect
                        logger.log(t, gpu_t, report.fan_rpm, log_color, log_effect)
                except (OSError, ValueError) as e:
                    print(f"[{time.strftime('%H:%M:%S')}] {i18n.t('cli.auto.device_error', error=e, interval=interval)}", flush=True)

                time.sleep(interval)
    except KeyboardInterrupt:
        pass
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="llano-v12ultra-ctrl", description=i18n.t("cli.parser.description"))
    sub = p.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help=i18n.t("cli.parser.status.help"))
    p_status.set_defaults(func=cmd_status)

    p_light = sub.add_parser("light", help=i18n.t("cli.parser.light.help"))
    p_light.add_argument("--color", default=None, help=i18n.t("cli.parser.light.color.help"))
    p_light.add_argument("--effect", default=None, help=i18n.t("cli.parser.light.effect.help"))
    p_light.add_argument("--speed", type=int, default=None, help=i18n.t("cli.parser.light.speed.help"))
    p_light.add_argument("--brightness", type=int, default=None, help=i18n.t("cli.parser.light.brightness.help"))
    p_light.add_argument("--off", action="store_true", help=i18n.t("cli.parser.light.off.help"))
    p_light.set_defaults(func=cmd_light)

    p_power = sub.add_parser("power", help=i18n.t("cli.parser.power.help"))
    p_power.add_argument("state", choices=["on", "off"])
    p_power.set_defaults(func=cmd_power)

    p_fan_speed = sub.add_parser("fan-speed", help=i18n.t("cli.parser.fan_speed.help"))
    p_fan_speed.add_argument("raw", type=int, help=i18n.t("cli.parser.fan_speed.raw.help"))
    p_fan_speed.set_defaults(func=cmd_fan_speed)

    p_monitor = sub.add_parser("monitor", help=i18n.t("cli.parser.monitor.help"))
    p_monitor.add_argument("--interval", type=float, default=0.3, help=i18n.t("cli.parser.monitor.interval.help"))
    p_monitor.set_defaults(func=cmd_monitor)

    p_raw_input = sub.add_parser("raw-input", help=i18n.t("cli.parser.raw_input.help"))
    p_raw_input.add_argument("--timeout", type=float, default=0.2, help=i18n.t("cli.parser.raw_input.timeout.help"))
    p_raw_input.set_defaults(func=cmd_raw_input)

    p_auto = sub.add_parser("auto", help=i18n.t("cli.parser.auto.help"))
    p_auto.add_argument("--config", default=None, help=i18n.t("cli.parser.auto.config.help"))
    p_auto.set_defaults(func=cmd_auto)

    return p


def main(argv=None):
    # Sprache VOR dem Parser-Bau festlegen (dessen Hilfetexte werden
    # einmalig bei Aufruf von build_parser() übersetzt) - siehe i18n.py:
    # LLANO_LANGUAGE-Env-Var > config.toml > Englisch. Ein `--lang`-Argument
    # auf dem Parser selbst wäre ein Henne-Ei-Problem (der Parser müsste
    # erst geparst werden, um zu wissen, in welcher Sprache er seine eigene
    # Hilfe anzeigen soll).
    i18n.init_language()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except device_mod.DeviceNotFoundError as e:
        print(i18n.t("cli.error.generic", error=e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
