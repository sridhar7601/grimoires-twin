"""
crowding.py — door-crowding DEMAND, the same definition in both layers.

For every door, every second: how many people who have NOT yet exited stand within
RADIUS_M of the door centre, divided by the half-disc in front of a wall-mounted door.
Fruin's pedestrian levels of service put 4 p/m² at the edge of free movement (LOS E/F)
and ~6 p/m² where bodies touch and pressure can build — the crowd-crush literature's
danger band.

What this IS: a crush-RISK flag — how many people press on one door at once.
What this is NOT: a crush prediction. Neither layer simulates body pressure. Layer 1
queues people at the doorway but lets them overlap; IRA characters avoid each other
locally but are not stopped by contact. A figure above 6 p/m² therefore means "this
door is asked to take more people than real bodies could fit", not "a crush happens".
Say it that way, every time.
"""
import math

RADIUS_M = 2.0
AREA_M2 = math.pi * RADIUS_M ** 2 / 2.0   # half disc in front of a door in a wall
DANGER_PPM2 = 4.0                         # Fruin LOS E/F: movement stops
CRUSH_PPM2 = 6.0                          # bodies in contact, pressure can build

NOTE = (f"people not yet out within {RADIUS_M} m of the door centre / {AREA_M2:.1f} m² half-disc, sampled every dt; "
        f"thresholds {DANGER_PPM2:.0f} p/m² (Fruin LOS E/F) and {CRUSH_PPM2:.0f} p/m² (crush band). Demand, not pressure: "
        "neither layer simulates body contact, so this flags crush RISK and never predicts a crush.")


def door_crowding(frames, doors, dt):
    """frames: iterable of (t, [(x, y), ...]) for people NOT yet out; doors: {id: (x, y)}; dt: seconds per frame.
    Returns {"per_door": {id: {...}}, "worst_door": id, "worst_peak_ppm2": float, "s_over_4ppm2_total": float, ...}."""
    per = {e: {"peak_people": 0, "peak_ppm2": 0.0, "peak_t_s": None, "s_over_4ppm2": 0.0, "s_over_6ppm2": 0.0}
           for e in doors}
    r2 = RADIUS_M ** 2
    for t, pts in frames:
        for e, (dx, dy) in doors.items():
            n = sum(1 for x, y in pts if (x - dx) ** 2 + (y - dy) ** 2 <= r2)
            d = per[e]
            if n > d["peak_people"]:
                d["peak_people"], d["peak_t_s"] = n, round(t, 1)
            ppm2 = n / AREA_M2
            if ppm2 >= DANGER_PPM2:
                d["s_over_4ppm2"] += dt
            if ppm2 >= CRUSH_PPM2:
                d["s_over_6ppm2"] += dt
    for d in per.values():
        d["peak_ppm2"] = round(d["peak_people"] / AREA_M2, 1)
        d["s_over_4ppm2"] = round(d["s_over_4ppm2"], 1)
        d["s_over_6ppm2"] = round(d["s_over_6ppm2"], 1)
    worst = max(per, key=lambda e: (per[e]["peak_ppm2"], per[e]["s_over_4ppm2"])) if per else None
    return {
        "radius_m": RADIUS_M, "area_m2": round(AREA_M2, 2), "sample_dt_s": dt,
        "per_door": per,
        "worst_door": worst,
        "worst_peak_people": per[worst]["peak_people"] if worst else 0,
        "worst_peak_ppm2": per[worst]["peak_ppm2"] if worst else 0.0,
        "s_over_4ppm2_total": round(sum(d["s_over_4ppm2"] for d in per.values()), 1),
        "s_over_6ppm2_total": round(sum(d["s_over_6ppm2"] for d in per.values()), 1),
        "note": NOTE,
    }


def summary(dc):
    """One cell for a table: '7.2 p/m² at E1 (45 people), 138 s over 4/m²'."""
    if not dc or not dc.get("worst_door"):
        return "—"
    if dc["worst_peak_people"] == 0:
        return "none (no one within 2 m of a door before exit)"
    return (f"{dc['worst_peak_ppm2']:.1f} p/m² at {dc['worst_door']} ({dc['worst_peak_people']} people), "
            f"{dc['s_over_4ppm2_total']:.0f} s over 4/m²")
