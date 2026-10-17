"""
render_map_film.py — top-down evacuation film, two plans side by side, same clock.

Draws the venue grid from the manifest, the SAME smoke field the solver used (smoke.SmokeField
on the plan's grid, so what you see is what was scored), every person as a dot coloured by
the exit they are heading for, each dot disappearing when that person is out, exits turning
red when smoke closes them, and a clearance-curve race underneath. Nothing is staged: every
frame is interpolated from recorded tracks.

Sources per panel:
  l1  rehearse.py --tracks JSON   (Python solver; 1 s rows, grid-local metres; has smoke + closures)
  l2  actor_sdg_dump.py JSONL     (Isaac twin; every agent every frame, world metres; no smoke yet)

Needs numpy + cv2 (the Isaac container's python has both):

  /isaac-sim/python.sh sim/render_map_film.py --venue results/hospital_plan.json \
     --fire scenarios/hospital_fire_entrance.json \
     --left-kind l1  --left-src  results/tracks_hospital_winner.json --left-plan  scenarios/hospital_winner_plan.json \
     --left-label "Grimoires plan" \
     --right-kind l1 --right-src results/tracks_hospital_base.json   --right-plan scenarios/hospital_base_plan.json \
     --right-label "Base plan" --out results/films/hospital_map_layer1.mp4
"""
import argparse
import collections
import json
import math
import os
import re
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grid import RES, build_grid  # noqa: E402
from make_exit_targets import inside_points  # noqa: E402
from smoke import DEFAULTS as SMOKE_DEFAULTS  # noqa: E402
from smoke import SmokeField  # noqa: E402

try:
    from rehearse import apply_plan  # noqa: E402  the solver's own plan -> venue step
except Exception:  # pragma: no cover - same semantics, no pxr needed
    def apply_plan(venue, plan):
        v = json.loads(json.dumps(venue))
        for eid in v.get("exits", {}):
            v["exits"][eid]["open"] = eid in plan["exits_open"]
        return v

EXIT_BGR = {"E1": (0, 150, 255), "E2": (70, 190, 70), "E3": (230, 150, 30), "E4": (200, 80, 200)}
CELL_BGR = {"m": (236, 238, 240), ".": (214, 217, 220), "#": (78, 80, 86), " ": (32, 32, 36)}
FONT = cv2.FONT_HERSHEY_SIMPLEX


def clearance(outs, n):
    done = sorted(t for t in outs if t is not None)
    def at(f):
        k = math.ceil(f * n)
        return done[k - 1] if k <= len(done) else None
    return at(0.5), at(0.9), at(1.0), done


class Panel:
    def __init__(self, venue, plan, fire, kind, src, label, px, reach, smoke_on, report=None):
        self.label, self.kind, self.px = label, kind, px
        self.plan = plan
        self.ox, self.oy = venue["origin"]
        g = build_grid(apply_plan(venue, plan))
        self.gx, self.gy = g["gx"], g["gy"]
        rows = venue["cells"]
        base = np.full((self.gy, self.gx, 3), CELL_BGR[" "], np.uint8)
        for j, r in enumerate(rows):
            for i, c in enumerate(r):
                base[self.gy - 1 - j, i] = CELL_BGR.get(c, CELL_BGR[" "])
        self.base = base
        self.exits = {e: [tuple(c) for c in d["cells"]] for e, d in venue["exits"].items()}
        self.open = set(plan["exits_open"])
        self.smoke_on = smoke_on
        sp = dict(SMOKE_DEFAULTS)
        sp.update(fire.get("smoke", {}))
        sf = SmokeField(g, fire["origin"], **sp)
        self.t_arr = np.flipud(np.array(sf.t_arr, float))
        self.s_max = np.flipud(np.array(sf.s_max, float))
        self.ramp, self.s_block = sp["ramp_s"], sp["s_block"]
        closed = {e: sf.span_closed_at(cells) for e, cells in self.exits.items() if e in self.open} if smoke_on else {}
        self.closed_at = {e: (float("inf") if v is None else v) for e, v in closed.items()}   # None = smoke never closes it
        self.fire_xy = fire["origin"]                                      # grid-local metres
        if kind == "l1":
            self._load_l1(src)
        else:
            self._load_l2(src, venue, reach)
        self.t50, self.t90, self.t100, self.out_sorted = clearance(self.outs, self.n)
        if report:  # show the scored numbers exactly (tracks are 1 s rows, so recomputing differs by ~0.2 s)
            r = json.load(open(report))
            self.t50, self.t90, self.t100 = r.get("t50_s"), r.get("t90_s"), r.get("t100_s")

    def _load_l1(self, path):
        d = json.load(open(path))
        self.people = []
        for p in d["tracks"]:
            rows = np.array(p["t"], float)
            self.people.append((rows[:, 0], rows[:, 1], rows[:, 2], p["exit"]))
        self.outs = [p["out"] for p in d["tracks"]]
        self.n = len(self.people)
        self.source = f"Layer 1 - Python solver, {self.n} people, grid smoke"

    def _load_l2(self, path, venue, reach):
        tr = collections.defaultdict(list)
        grp = {}
        with open(path) as f:
            for line in f:
                r = json.loads(line)
                tr[r["agent"]].append((r["t"], r["x"] - self.ox, r["y"] - self.oy))
                grp[r["agent"]] = r.get("group", "")
        targets = {e: (p[0] - self.ox, p[1] - self.oy) for e, p in inside_points(venue).items()}
        self.people, self.outs = [], []
        for a, pts in tr.items():
            pts.sort()
            arr = np.array(pts, float)
            e = (re.findall(r"E\d+", grp[a]) or [None])[-1]   # evac_E1 -> E1, evac_E1_to_E2 -> E2
            out = None
            if e in targets:
                dist = np.hypot(arr[:, 1] - targets[e][0], arr[:, 2] - targets[e][1])
                hit = np.nonzero(dist <= reach)[0]
                out = float(arr[hit[0], 0]) if len(hit) else None
            self.people.append((arr[:, 0], arr[:, 1], arr[:, 2], e))
            self.outs.append(out)
        self.n = len(self.people)
        self.source = f"Layer 2 - Isaac Sim twin, {self.n} characters, no smoke yet"

    def precompute(self, times):
        self.pos = [(np.interp(times, ts, xs), np.interp(times, ts, ys)) for ts, xs, ys, _ in self.people]

    def to_px(self, x, y):
        return int(x / RES * self.px), int((self.gy - y / RES) * self.px)

    def render(self, k, t, header_h, footer_h):
        img = self.base.astype(np.float32)
        if self.smoke_on:
            lev = np.where(np.isfinite(self.t_arr) & (t > self.t_arr),
                           np.minimum(np.minimum((t - self.t_arr) / self.ramp, 1.0), self.s_max), 0.0)
            a = (lev * 0.85)[..., None]
            dense = (lev > self.s_block)[..., None]
            col = np.where(dense, np.array((40, 40, 150), np.float32), np.array((70, 70, 70), np.float32))
            img = img * (1 - a) + col * a
        img = img.astype(np.uint8)
        for e, cells in self.exits.items():
            if e not in self.open:
                c = (130, 130, 130)
            elif self.smoke_on and t >= self.closed_at.get(e, float("inf")):
                c = (0, 0, 230)
            else:
                c = EXIT_BGR.get(e, (0, 200, 0))
            for i, j in cells:
                img[self.gy - 1 - j, i] = c
        W, H = self.gx * self.px, self.gy * self.px
        m = cv2.resize(img, (W, H), interpolation=cv2.INTER_NEAREST)

        fx, fy = self.to_px(*self.fire_xy)
        pulse = 6 + int(3 * (1 + math.sin(t * 4)))
        cv2.circle(m, (fx, fy), pulse + 4, (0, 90, 255), -1, cv2.LINE_AA)
        cv2.circle(m, (fx, fy), pulse, (0, 220, 255), -1, cv2.LINE_AA)

        r = max(3, self.px // 2 + 1)
        inside = 0
        for (xs, ys), (_, _, _, e), out in zip(self.pos, self.people, self.outs):
            if out is not None and t >= out:
                continue
            inside += 1
            p = self.to_px(xs[k], ys[k])
            cv2.circle(m, p, r, EXIT_BGR.get(e, (40, 40, 40)), -1, cv2.LINE_AA)
            cv2.circle(m, p, r, (20, 20, 20), 1, cv2.LINE_AA)

        for e, cells in self.exits.items():
            ci = sum(i for i, _ in cells) / len(cells)
            cj = sum(j for _, j in cells) / len(cells)
            x, y = int((ci + 0.5) * self.px), int((self.gy - 1 - cj + 0.5) * self.px)
            closed = self.smoke_on and e in self.open and t >= self.closed_at.get(e, float("inf"))
            txt = f"{e} CLOSED" if closed else (e if e in self.open else f"{e} (not used)")
            col = (0, 0, 220) if closed else ((60, 60, 60) if e not in self.open else (20, 20, 20))
            tx = min(max(4, x - 20), W - 150)
            ty = min(max(18, y + (22 if y < H / 2 else -10)), H - 6)
            cv2.putText(m, txt, (tx, ty), FONT, 0.55, (255, 255, 255), 4, cv2.LINE_AA)
            cv2.putText(m, txt, (tx, ty), FONT, 0.55, col, 2, cv2.LINE_AA)

        head = np.full((header_h, W, 3), (24, 24, 28), np.uint8)
        cv2.putText(head, self.label, (12, 30), FONT, 0.85, (255, 255, 255), 2, cv2.LINE_AA)
        knobs = f"exits {'+'.join(sorted(self.open))}  |  alarm {self.plan['alarm_delay_s']:.0f} s  |  stagger {self.plan['stagger_s']:.0f} s"
        cv2.putText(head, knobs, (12, 56), FONT, 0.55, (180, 220, 255), 1, cv2.LINE_AA)
        cv2.putText(head, self.source, (12, 78), FONT, 0.5, (150, 150, 150), 1, cv2.LINE_AA)

        foot = np.full((footer_h, W, 3), (24, 24, 28), np.uint8)
        out_n = self.n - inside
        cv2.putText(foot, f"t = {t:5.1f} s", (12, 32), FONT, 0.8, (0, 255, 140), 2, cv2.LINE_AA)
        cv2.putText(foot, f"out {out_n:3d} / {self.n}", (190, 32), FONT, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
        msg = f"90% out at {self.t90:.1f} s" if (self.t90 is not None and t >= self.t90) else ""
        cv2.putText(foot, msg, (420, 32), FONT, 0.8, (0, 220, 255), 2, cv2.LINE_AA)
        return np.vstack([head, m, foot])


def chart(width, height, t, t_end, panels, colors):
    c = np.full((height, width, 3), (18, 18, 22), np.uint8)
    L, R, T, B = 70, 20, 30, 34
    pw, ph = width - L - R, height - T - B
    cv2.putText(c, "people still inside (%)", (L, 20), FONT, 0.55, (200, 200, 200), 1, cv2.LINE_AA)
    for frac in (0, 0.5, 1.0):
        y = T + int(ph * (1 - frac))
        cv2.line(c, (L, y), (L + pw, y), (55, 55, 60), 1)
        cv2.putText(c, f"{int(frac * 100)}", (L - 40, y + 5), FONT, 0.45, (160, 160, 160), 1, cv2.LINE_AA)
    step = 30 if t_end > 120 else 15
    for s in range(0, int(t_end) + 1, step):
        x = L + int(pw * s / t_end)
        cv2.putText(c, f"{s}s", (x - 10, height - 10), FONT, 0.45, (160, 160, 160), 1, cv2.LINE_AA)
    for p, col in zip(panels, colors):
        outs = np.array(p.out_sorted)
        ts = np.linspace(0, t_end, 400)
        rem = [(p.n - np.searchsorted(outs, x, side="right")) / p.n for x in ts]
        pts_all = np.array([(L + int(pw * x / t_end), T + int(ph * (1 - r))) for x, r in zip(ts, rem)], np.int32)
        cv2.polylines(c, [pts_all], False, tuple(int(v * 0.35) for v in col), 1, cv2.LINE_AA)
        upto = pts_all[ts <= t]
        if len(upto) > 1:
            cv2.polylines(c, [upto], False, col, 3, cv2.LINE_AA)
        if p.t90 is not None:
            x = L + int(pw * p.t90 / t_end)
            cv2.line(c, (x, T), (x, T + ph), tuple(int(v * 0.6) for v in col), 1)
    x = L + int(pw * min(t, t_end) / t_end)
    cv2.line(c, (x, T), (x, T + ph), (255, 255, 255), 1)
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", required=True)
    ap.add_argument("--fire", required=True)
    for side in ("left", "right"):
        ap.add_argument(f"--{side}-kind", choices=["l1", "l2"], required=True)
        ap.add_argument(f"--{side}-src", required=True)
        ap.add_argument(f"--{side}-plan", required=True)
        ap.add_argument(f"--{side}-label", default="")
        ap.add_argument(f"--{side}-report", help="rehearse.py / measure.py report: display its t50/t90/t100 exactly")
    ap.add_argument("--title", default="Hospital fire at the main entrance - same fire, same people, same seed")
    ap.add_argument("--px", type=int, default=6, help="pixels per 0.5 m cell")
    ap.add_argument("--fps", type=float, default=20.0)
    ap.add_argument("--speed", type=float, default=1.0, help="simulation seconds per video second")
    ap.add_argument("--hold", type=float, default=4.0, help="seconds to hold after the last person is out")
    ap.add_argument("--reach", type=float, default=1.5)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    venue, fire = json.load(open(a.venue)), json.load(open(a.fire))
    panels = []
    for side in ("left", "right"):
        kind = getattr(a, f"{side}_kind")
        panels.append(Panel(venue, json.load(open(getattr(a, f"{side}_plan"))), fire, kind,
                            getattr(a, f"{side}_src"), getattr(a, f"{side}_label"), a.px, a.reach, smoke_on=(kind == "l1"),
                            report=getattr(a, f"{side}_report")))
    last = max((p.t100 or max(x for x in p.outs if x is not None)) for p in panels)
    t_end = last + a.hold
    times = np.arange(0.0, t_end, a.speed / a.fps)
    for p in panels:
        p.precompute(times)
        print(f"  {p.label}: n={p.n} t50={p.t50} t90={p.t90} t100={p.t100}  closed={ {k: (round(v, 1) if v != float('inf') else None) for k, v in p.closed_at.items()} }")

    header_h, footer_h, title_h, chart_h, gap = 90, 48, 52, 190, 8
    sample = panels[0].render(0, 0.0, header_h, footer_h)
    PW, PH = sample.shape[1], sample.shape[0]
    W, H = PW * 2 + gap, title_h + PH + chart_h
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    vw = cv2.VideoWriter(a.out, cv2.VideoWriter_fourcc(*"mp4v"), a.fps, (W, H))
    if not vw.isOpened():
        raise SystemExit("VideoWriter failed")
    colors = [(120, 230, 120), (90, 120, 255)]
    for k, t in enumerate(times):
        tl = np.full((title_h, W, 3), (10, 10, 12), np.uint8)
        cv2.putText(tl, a.title, (14, 34), FONT, 0.85, (255, 255, 255), 2, cv2.LINE_AA)
        row = np.hstack([panels[0].render(k, t, header_h, footer_h),
                         np.zeros((PH, gap, 3), np.uint8),
                         panels[1].render(k, t, header_h, footer_h)])
        frame = np.vstack([tl, row, chart(W, chart_h, t, t_end, panels, colors)])
        vw.write(frame)
        if k % 400 == 0:
            print(f"  frame {k}/{len(times)}  t={t:.1f}s")
    vw.release()
    print(f"wrote {a.out}  ({len(times)} frames, {len(times) / a.fps:.1f} s of video, {W}x{H}, {a.speed}x speed)")


if __name__ == "__main__":
    main()
