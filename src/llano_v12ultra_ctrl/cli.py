import argparse
import sys
import time

from . import config as config_mod
from . import device as device_mod
from . import history as history_mod
from . import notify as notify_mod
from . import protocol
from . import temp as temp_mod


def cmd_status(args):
    with device_mod.Device() as dev:
        r = dev.get_report()
    print(f"Gerät:        {dev.path}")
    print(f"Raw-Report:   {r.raw.hex(' ')}")
    print(f"Checksum ok:  {r.checksum_ok}")
    print(f"Gesamteinheit (Lüfter+Licht, per 'power'-Befehl):  {'AN' if r.power_on else 'AUS'}")
    print(f"Lüfterdrehzahl (Rad, Stufe nicht per Software steuerbar): {r.fan_rpm} U/min (raw={r.fan_speed_raw})")
    print(f"Beleuchtung:  {'AN' if r.light_on else 'AUS'}")
    print(f"Farbe:        {r.color}  [{r.color_name()}]")
    print(f"Effekt:       {r.effect_raw}  [{r.effect_name()}]")
    print(f"Geschwindigkeit: {r.speed}  (nicht monoton, siehe protocol.py für Details)")
    print(f"Helligkeit:   {r.brightness}  (0=dunkel, 255=maximal hell)")
    return 0


def _resolve_choice(value, name_map, label):
    if value in name_map:
        return name_map[value]
    try:
        v = int(value)
    except ValueError:
        raise SystemExit(f"Ungültiger {label} '{value}'. Erlaubt: 0-4 oder {', '.join(name_map)}")
    if not 0 <= v <= 4:
        raise SystemExit(f"{label} muss zwischen 0 und 4 liegen")
    return v


def cmd_light(args):
    with device_mod.Device() as dev:
        if args.off:
            r = dev.set_light(color=0, light_on=False)
            print(f"Beleuchtung ausgeschaltet, Lüfter unbeeinflusst (raw={r.raw.hex(' ')})")
            return 0
        current = dev.get_report()
        color = _resolve_choice(args.color, protocol.NAME_TO_COLOR, "Farbe") if args.color is not None else current.color
        effect = _resolve_choice(args.effect, protocol.NAME_TO_EFFECT, "Effekt") if args.effect is not None else (current.effect_raw if current.light_on else 0)
        speed = args.speed if args.speed is not None else current.speed
        brightness = args.brightness if args.brightness is not None else current.brightness
        r = dev.set_light(color=color, effect=effect, speed=speed, light_on=True, brightness=brightness)
    print(f"Gesetzt: color={r.color} [{r.color_name()}]  effect={r.effect_raw} [{r.effect_name()}]  speed={r.speed}  brightness={r.brightness}  (raw={r.raw.hex(' ')})")
    return 0


def cmd_power(args):
    with device_mod.Device() as dev:
        r = dev.set_power(power=(args.state == "on"))
    if r.power_on:
        print(f"Gesamteinheit AN (Lüfter + Licht laufen wieder, raw={r.raw.hex(' ')})")
    else:
        print(f"Gesamteinheit AUS (Lüfter UND Licht komplett gestoppt, raw={r.raw.hex(' ')})")
    return 0


def cmd_fan_speed(args):
    print(
        "Hinweis: auf diesem Gerät (llano V12 Ultra, 374a:b101) nachweislich wirkungslos "
        "- siehe protocol.py NACHTRAG 1-4. Forward-kompatibel vorbereitet für andere "
        "Firmware-Revisionen, die dieses Feld eventuell auswerten."
    )
    with device_mod.Device() as dev:
        r = dev.set_fan_speed(args.raw)
    print(f"Byte 1 (fan_speed) auf {args.raw} gesetzt (raw={r.raw.hex(' ')}) - Lüfterdrehzahl laut Report weiterhin {r.fan_rpm} U/min (raw={r.fan_speed_raw})")
    return 0


def cmd_monitor(args):
    print("Beobachte Live-Telemetrie (Strg+C zum Beenden)...")
    last = None
    with device_mod.Device() as dev:
        try:
            while True:
                r = dev.get_report()
                if r.raw != last:
                    ts = time.strftime("%H:%M:%S")
                    print(f"[{ts}] {r.fan_rpm:4d} U/min  color={r.color} [{r.color_name()}]  effect={r.effect_raw} [{r.effect_name()}]  speed={r.speed}  raw={r.raw.hex(' ')}", flush=True)
                    last = r.raw
                time.sleep(args.interval)
        except KeyboardInterrupt:
            pass
    return 0


def cmd_raw_input(args):
    print(
        "Beobachte rohen 64-Byte Input-Report (Strg+C zum Beenden).\n"
        "Diagnose-Befehl: laut bisheriger Analyse (siehe protocol.py) ohne "
        "bekannten inhaltsabhängigen Effekt/Bedeutung - rein zum manuellen "
        "Explorieren, es wird nichts geschrieben."
    )
    with device_mod.Device() as dev:
        try:
            while True:
                raw = dev.read_input_report(timeout_s=args.timeout)
                if raw is not None:
                    ts = time.strftime("%H:%M:%S")
                    print(f"[{ts}] {raw.hex(' ')}", flush=True)
        except KeyboardInterrupt:
            pass
    return 0


def cmd_auto(args):
    cfg = config_mod.load_config(args.config)
    auto_cfg = cfg["auto"]

    sensor_path = auto_cfg.get("temp_sensor") or temp_mod.find_cpu_temp_input()
    if not sensor_path:
        print("Kein CPU-Temperatursensor gefunden (coretemp/k10temp). Abbruch.", file=sys.stderr)
        return 1
    print(f"Temperatursensor: {sensor_path}")

    thresholds = sorted(auto_cfg["thresholds"], key=lambda t: t["temp_c"])
    hysteresis = auto_cfg.get("hysteresis_c", 3)
    interval = auto_cfg.get("poll_interval_s", 5)
    gpu_cfg = auto_cfg.get("gpu_alert", {})
    gpu_enabled = gpu_cfg.get("enabled", False)
    print(f"Schwellen: {thresholds}  Hysterese: {hysteresis}°C  Intervall: {interval}s")
    if gpu_enabled:
        print(
            f"GPU-Alarm: ab {gpu_cfg['temp_c']}°C (aus bei {gpu_cfg['temp_c'] - gpu_cfg['hysteresis_c']}°C) "
            f"-> color={gpu_cfg['color']} effect={gpu_cfg['effect']} (nur wenn GPU >= CPU, 'wer wärmer ist gewinnt')"
        )

    fan_cfg = auto_cfg.get("fan_reminder", {})
    fan_reminder_enabled = fan_cfg.get("enabled", False)
    if fan_reminder_enabled:
        print(
            f"Lüfter-Erinnerung: ab {fan_cfg['temp_c']}°C wenn Drehzahl < {fan_cfg['min_rpm']} U/min "
            f"(Cooldown {fan_cfg.get('cooldown_s', 300)}s) - die Software kann die Drehzahl nicht selbst "
            "setzen, nur ans Rad-Hochdrehen erinnern."
        )

    log_cfg = auto_cfg.get("log", {})
    logger = history_mod.HistoryLogger(log_cfg["path"]) if log_cfg.get("enabled", False) else None
    if logger:
        print(f"Verlaufsprotokoll: {logger.path}")

    current_color = None
    current_effect = 0
    gpu_alert_active = False
    last_reminder_ts = 0.0
    try:
        with device_mod.Device() as dev:
            while True:
                t = temp_mod.read_temp_c(sensor_path)
                gpu_t = temp_mod.read_gpu_temp_c() if gpu_enabled else None
                report = dev.get_report()  # v.a. für die Live-Lüftertelemetrie (fan_rpm)

                cpu_color, cpu_effect, cpu_speed = current_color, current_effect, 0
                if t is not None:
                    cpu_color = thresholds[0]["color"]
                    cpu_effect = thresholds[0].get("effect", 0)
                    cpu_speed = thresholds[0].get("speed", 0)
                    for th in thresholds:
                        limit = th["temp_c"]
                        if current_color is not None and th["color"] < current_color:
                            limit -= hysteresis
                        if t >= limit:
                            cpu_color = th["color"]
                            cpu_effect = th.get("effect", 0)
                            cpu_speed = th.get("speed", 0)

                if gpu_enabled and gpu_t is not None:
                    if not gpu_alert_active and gpu_t >= gpu_cfg["temp_c"]:
                        gpu_alert_active = True
                    elif gpu_alert_active and gpu_t < gpu_cfg["temp_c"] - gpu_cfg["hysteresis_c"]:
                        gpu_alert_active = False

                # "wer wärmer ist gewinnt": GPU-Alarm nur, wenn er aktiv ist
                # UND die GPU mindestens so heiß wie die CPU ist - sonst
                # gewinnt weiterhin die normale CPU-Farblogik.
                if gpu_alert_active and gpu_t is not None and (t is None or gpu_t >= t):
                    target_color, target_effect, target_speed = gpu_cfg["color"], gpu_cfg["effect"], gpu_cfg.get("speed", 0)
                else:
                    target_color, target_effect, target_speed = cpu_color, cpu_effect, cpu_speed

                if target_color is not None and (target_color, target_effect) != (current_color, current_effect):
                    r = dev.set_light(color=target_color, effect=target_effect, speed=target_speed, power=True)
                    ts = time.strftime("%H:%M:%S")
                    gpu_info = f"  GPU={gpu_t:.1f}°C" if gpu_t is not None else ""
                    cpu_info = f"{t:.1f}°C" if t is not None else "?"
                    print(f"[{ts}] CPU={cpu_info}{gpu_info} -> {r.color_name()} [{r.effect_name()}]", flush=True)
                    current_color, current_effect = target_color, target_effect

                # Erinnerung: CPU heiß, aber gemessene Drehzahl (Rad-Telemetrie,
                # nicht per Software steuerbar) bleibt niedrig - einzig
                # möglicher "Regelkreis" ist hier der Mensch am physischen Rad.
                if fan_reminder_enabled and t is not None and t >= fan_cfg["temp_c"] and report.fan_rpm < fan_cfg["min_rpm"]:
                    now = time.time()
                    if now - last_reminder_ts >= fan_cfg.get("cooldown_s", 300):
                        notify_mod.send(
                            "llano-v12ultra-ctrl: Lüfter zu langsam",
                            f"CPU {t:.0f}°C, aber nur {report.fan_rpm} U/min. Rad am Pad manuell hochdrehen?",
                        )
                        last_reminder_ts = now

                if logger:
                    log_color = current_color if current_color is not None else report.color
                    log_effect = current_effect
                    logger.log(t, gpu_t, report.fan_rpm, log_color, log_effect)

                time.sleep(interval)
    except KeyboardInterrupt:
        pass
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="llano-v12ultra-ctrl", description="Steuerung für das llano V12 Ultra Kühlpad (Myth.Cool / Holtek 374a:b101)")
    sub = p.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="aktuellen Gerätezustand anzeigen (Farbe/Effekt/Geschwindigkeit + Live-Telemetrie)")
    p_status.set_defaults(func=cmd_status)

    p_light = sub.add_parser("light", help="Beleuchtung steuern (Farbe/Effekt/Geschwindigkeit/Aus)")
    p_light.add_argument("--color", default=None, help="0-4 oder red/lightblue/green/purple/orange")
    p_light.add_argument("--effect", default=None, help="0-4 oder solid/breathing/rainbow/chase/zones")
    p_light.add_argument("--speed", type=int, default=None, help="0-3 offiziell genutzt (0=schnell..3=langsam). Werte 4-255 technisch möglich, aber von der Original-App nie validiert und nicht monoton (siehe protocol.py)")
    p_light.add_argument("--brightness", type=int, default=None, help="0-255 (0=dunkel, 255=maximal hell)")
    p_light.add_argument("--off", action="store_true", help="Beleuchtung ausschalten")
    p_light.set_defaults(func=cmd_light)

    p_power = sub.add_parser("power", help="Gesamte Einheit (Lüfter+Licht) komplett an/aus schalten - reiner Kill-Switch, keine Zwischenstufen")
    p_power.add_argument("state", choices=["on", "off"])
    p_power.set_defaults(func=cmd_power)

    p_fan_speed = sub.add_parser("fan-speed", help="Byte 1 (fan_speed) des Feature-Reports schreiben - auf diesem Gerät nachweislich wirkungslos, forward-kompatibel vorbereitet (siehe protocol.py)")
    p_fan_speed.add_argument("raw", type=int, help="1-100")
    p_fan_speed.set_defaults(func=cmd_fan_speed)

    p_monitor = sub.add_parser("monitor", help="Live-Telemetrie laufend anzeigen")
    p_monitor.add_argument("--interval", type=float, default=0.3, help="Poll-Intervall in Sekunden (default 0.3)")
    p_monitor.set_defaults(func=cmd_monitor)

    p_raw_input = sub.add_parser("raw-input", help="Rohen 64-Byte Input-Report beobachten (Diagnose/Exploration, nur Lesen)")
    p_raw_input.add_argument("--timeout", type=float, default=0.2, help="Timeout pro Lesevorgang in Sekunden (default 0.2)")
    p_raw_input.set_defaults(func=cmd_raw_input)

    p_auto = sub.add_parser("auto", help="Temperaturbasierten Auto-Farb-Daemon starten (visueller Temperatur-Indikator)")
    p_auto.add_argument("--config", default=None, help="Pfad zur config.toml (default ~/.config/llano-v12ultra-ctrl/config.toml)")
    p_auto.set_defaults(func=cmd_auto)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except device_mod.DeviceNotFoundError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
