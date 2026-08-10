"""Lüfterkurve: bildet eine CPU-Temperatur auf einen fan_speed-Rohwert
(1-100, siehe protocol.py NACHTRAG 8/9) ab, per stückweise linearer
Interpolation zwischen konfigurierten Stützpunkten."""


def sorted_points(points):
    return sorted(points, key=lambda p: p["temp_c"])


def raw_for_temp(points, temp_c):
    """points: Liste von {"temp_c": float, "raw": int}, mind. 1 Eintrag.
    Gibt den interpolierten raw-Wert (1-100, gerundet) für temp_c zurück.
    Unterhalb des niedrigsten bzw. oberhalb des höchsten Stützpunkts wird
    der jeweilige Randwert gehalten (kein Extrapolieren)."""
    pts = sorted_points(points)
    if not pts:
        raise ValueError("fan_curve.points ist leer")
    if temp_c <= pts[0]["temp_c"]:
        raw = pts[0]["raw"]
    elif temp_c >= pts[-1]["temp_c"]:
        raw = pts[-1]["raw"]
    else:
        raw = pts[-1]["raw"]
        for a, b in zip(pts, pts[1:]):
            if a["temp_c"] <= temp_c <= b["temp_c"]:
                span = b["temp_c"] - a["temp_c"]
                frac = (temp_c - a["temp_c"]) / span if span else 0
                raw = a["raw"] + frac * (b["raw"] - a["raw"])
                break
    return max(1, min(100, round(raw)))
