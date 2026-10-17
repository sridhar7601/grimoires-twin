"""
smoke.py — a simplified smoke field on the venue grid.

WHAT THIS IS, AND IS NOT
------------------------
A front model, not CFD. Smoke starts at one cell (the fire origin), its front
advances along walkable cells at `spread_speed_ms` (walls stop it, open gates and
exits let it through), and once it has arrived at a cell the level there ramps
0 -> 1 over `ramp_s`. Far from the fire it thins: the ceiling level in a cell
is 1 - distance / reach_m, so only the core near the fire ever becomes
impassable (level > s_block); the rest slows people (speed x (1 - k_slow * s)).

Every number below is a stated parameter, written into every report. Say
"simplified grid smoke model", never "fire simulation". In Isaac Sim the same
origin drives an Omniverse Flow emitter for the pictures — that is the visual of
this field, not a second model.

  python3 sim/smoke.py --origin 44,17 --at 0,20,40,60          # ASCII snapshots
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grid import INF, RES, build_grid, cell_of, dijkstra, nearest_walkable, span_cells  # noqa: E402

DEFAULTS = {
    "spread_speed_ms": 0.6,   # how fast the front advances along the floor
    "ramp_s": 20.0,           # seconds from first arrival to full level in a cell
    "reach_m": 45.0,          # level ceiling falls to 0 this far from the fire
    "s_block": 0.7,           # above this a cell is impassable
    "k_slow": 0.6,            # speed multiplier is 1 - k_slow * level
}


class SmokeField:
    def __init__(self, grid, origin_xy, spread_speed_ms=DEFAULTS["spread_speed_ms"],
                 ramp_s=DEFAULTS["ramp_s"], reach_m=DEFAULTS["reach_m"],
                 s_block=DEFAULTS["s_block"], k_slow=DEFAULTS["k_slow"]):
        self.gx, self.gy = grid["gx"], grid["gy"]
        self.blocked = grid["blocked"]
        self.p = {"spread_speed_ms": spread_speed_ms, "ramp_s": ramp_s, "reach_m": reach_m,
                  "s_block": s_block, "k_slow": k_slow}
        i0, j0 = cell_of(origin_xy[0], origin_xy[1], self.gx, self.gy)
        self.origin_cell = nearest_walkable(self.blocked, self.gx, self.gy, i0, j0)
        self.origin_xy = list(origin_xy)
        dist, _ = dijkstra(self.blocked, self.gx, self.gy, [(*self.origin_cell, "fire")])
        self.t_arr = [[INF] * self.gx for _ in range(self.gy)]
        self.s_max = [[0.0] * self.gx for _ in range(self.gy)]
        self.t_close = [[INF] * self.gx for _ in range(self.gy)]
        for j in range(self.gy):
            for i in range(self.gx):
                d = dist[j][i]
                if d == INF:
                    continue
                m = d * RES
                self.t_arr[j][i] = m / spread_speed_ms if spread_speed_ms > 0 else INF
                self.s_max[j][i] = max(0.0, 1.0 - m / reach_m) if reach_m > 0 else 1.0
                if self.s_max[j][i] > s_block and self.t_arr[j][i] < INF:
                    self.t_close[j][i] = self.t_arr[j][i] + ramp_s * s_block

    def level(self, i, j, t):
        ta = self.t_arr[j][i]
        if ta == INF or t <= ta:
            return 0.0
        s = (t - ta) / self.p["ramp_s"] if self.p["ramp_s"] > 0 else 1.0
        return min(s, 1.0, self.s_max[j][i])

    def is_blocked(self, i, j, t):
        return t >= self.t_close[j][i]

    def span_closed_at(self, cells):
        """When the LAST cell of an opening becomes impassable (INF = never)."""
        # Wall cells (incl. the 0.25 m margin at each end of an opening) never see
        # smoke, so they must not count -- otherwise every span reads "never closes".
        ts = [self.t_close[j][i] for (i, j) in cells
              if 0 <= j < self.gy and 0 <= i < self.gx and not self.blocked[j][i]]
        if not ts:
            return None
        m = max(ts)
        return None if m == INF else round(m, 1)

    def params(self):
        return dict(self.p, origin_xy=self.origin_xy, model="front model: arrival by shortest "
                    "walkable path / spread_speed, level ramps over ramp_s, ceiling 1 - d/reach_m")

    def snapshot_ascii(self, t, step=1):
        """Rows north->south, one char per cell: '#' wall, 'F' fire, ' .:*#' by level."""
        shades = " .:-=+*%@"
        lines = []
        for j in range(self.gy - 1, -1, -step):
            row = []
            for i in range(0, self.gx, step):
                if (i, j) == self.origin_cell:
                    row.append("F")
                elif self.blocked[j][i]:
                    row.append("#")
                else:
                    s = self.level(i, j, t)
                    row.append("X" if self.is_blocked(i, j, t) else shades[min(int(s * (len(shades) - 1)), len(shades) - 1)])
            lines.append("".join(row))
        return "\n".join(lines)


def main():
    from venue_def import VENUE, resolve
    ap = argparse.ArgumentParser(description="print ASCII snapshots of the smoke field")
    ap.add_argument("--venue", help="venue manifest .json (default: venue_def.VENUE)")
    ap.add_argument("--origin", default="44,17", help="fire origin x,y in metres")
    ap.add_argument("--speed", type=float, default=DEFAULTS["spread_speed_ms"])
    ap.add_argument("--ramp", type=float, default=DEFAULTS["ramp_s"])
    ap.add_argument("--reach", type=float, default=DEFAULTS["reach_m"])
    ap.add_argument("--at", default="0,20,40,60", help="comma list of seconds")
    ap.add_argument("--step", type=int, default=1, help="print every Nth cell (2 halves the width)")
    a = ap.parse_args()
    venue = json.load(open(a.venue)) if a.venue else resolve()
    g = build_grid(venue)
    ox, oy = (float(v) for v in a.origin.split(","))
    sf = SmokeField(g, (ox, oy), spread_speed_ms=a.speed, ramp_s=a.ramp, reach_m=a.reach)
    print("params:", json.dumps(sf.params()))
    print("legend: # wall  F fire  X impassable (level > s_block)  ' .:-=+*%@' rising level\n")
    for t in (float(v) for v in a.at.split(",")):
        print(f"--- t = {t:.0f} s ---")
        print(sf.snapshot_ascii(t, step=a.step))
        print()
    for name, d in list(venue["gates"].items()) + list(venue["exits"].items()):
        if d["open"]:
            y = venue["barrier"]["y"] if name.startswith("G") else RES * 1.5
            print(f"{name}: closes at {sf.span_closed_at(span_cells(d['x0'], d['x1'], y))} s")


if __name__ == "__main__":
    main()
