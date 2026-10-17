"""
stitch_dollhouse.py — dollhouse side-by-side with data overlays: a ring on every character
(colour = the exit it is heading for) projected from the twin's own position dump through the
known overhead camera, ring dropped once the character is out, exits marked and labelled, and a
live `out N / M` counter per side. Every mark comes from recorded data; nothing is staged.

  /isaac-sim/python.sh sim/stitch_dollhouse.py --venue results/hospital_plan.json \
     --left  winner --left-plan  scenarios/hospital_winner_plan.json --left-label  "Grimoires plan: 4 exits, alarm 5 s" \
     --right base   --right-plan scenarios/hospital_base_plan.json   --right-label "Base plan: front doors, alarm 30 s" \
     --out results/films/hospital_dollhouse_overlay.mp4
(--left/--right = the plan tag: reads results/ira_hospital_<tag>_dollhouse/ and assets/hospital/hospital_evac_<tag>_dollhouse.usda)
"""
import argparse, collections, glob, json, math, os, re, sys
import cv2
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_exit_targets import inside_points  # noqa: E402

EXIT_BGR = {"E1": (0, 150, 255), "E2": (70, 190, 70), "E3": (230, 150, 30), "E4": (200, 80, 200)}
FONT = cv2.FONT_HERSHEY_SIMPLEX
H_AP = 20.955


def camera(stage_usda):
    txt = open(stage_usda).read()
    blk = txt[txt.index('def Camera "Overhead"'):]
    x, y, h = map(float, re.search(r"xformOp:translate = \(([^)]*)\)", blk).group(1).split(","))
    focal = float(re.search(r"focalLength = ([0-9.]+)", blk).group(1))
    return x, y, h, focal


class Side:
    closures = {}
    def __init__(self, root, tag, venue, plan, label, reach, start_frame, fps, variant="dollhouse"):
        self.label, self.plan = label, plan
        run = os.path.join(root, "results", f"ira_hospital_{tag}_{variant}")
        cams = [d for d in os.listdir(run) if "Overhead" in d]
        self.frames = sorted(glob.glob(os.path.join(run, cams[0], "rgb", "*.png")))
        self.cx, self.cy, self.ch, self.focal = camera(os.path.join(root, "assets", "hospital", f"hospital_evac_{tag}_{variant}.usda"))
        self.start_frame, self.fps = start_frame, fps
        tr, grp = collections.defaultdict(list), {}
        for line in open(os.path.join(run, "agent_positions.jsonl")):
            r = json.loads(line); tr[r["agent"]].append((r["t"], r["x"], r["y"])); grp[r["agent"]] = r.get("group", "")
        self.targets = inside_points(venue)
        self.open = [e for e in plan["exits_open"] if e in self.targets]
        self.agents = []
        for a, pts in tr.items():
            pts.sort(); arr = np.array(pts)
            e = re.findall(r"E\d+", grp[a])[-1]   # evac_E1 -> E1, evac_E1_to_E2 -> E2
            tx, ty = self.targets[e][0], self.targets[e][1]
            hit = np.nonzero(np.hypot(arr[:, 1] - tx, arr[:, 2] - ty) <= reach)[0]
            self.agents.append((arr, e, float(arr[hit[0], 0]) if len(hit) else None))
        self.n = len(self.agents)

    def t_of(self, i):
        return (i + self.start_frame) / self.fps

    def project(self, x, y, W, H, z=0.9):
        f = self.focal / H_AP * W                       # square pixels: fx == fy
        d = self.ch - z
        return int(W / 2 + f * (x - self.cx) / d), int(H / 2 - f * (y - self.cy) / d)

    def render(self, i, ph):
        img = cv2.imread(self.frames[i]); H0, W0 = img.shape[:2]
        pw = int(W0 * ph / H0); img = cv2.resize(img, (pw, ph), interpolation=cv2.INTER_AREA)
        t = self.t_of(i)
        for e, (x, y, _) in self.targets.items():                       # exits
            u, v = self.project(x, y, pw, ph)
            used = e in self.open
            closed = used and t >= self.closures.get(e, float("inf"))
            col = (0, 0, 230) if closed else (EXIT_BGR[e] if used else (150, 150, 150))
            cv2.circle(img, (u, v), 16, col, 3, cv2.LINE_AA)
            txt = f"{e} CLOSED (smoke)" if closed else (e if used else f"{e} not used")
            cv2.putText(img, txt, (u + 18, v + 6), FONT, 0.6, (255, 255, 255), 4, cv2.LINE_AA)
            cv2.putText(img, txt, (u + 18, v + 6), FONT, 0.6, col, 2, cv2.LINE_AA)
        out = 0
        for arr, e, t_out in self.agents:                               # characters
            if t_out is not None and t >= t_out:
                out += 1; continue
            x = np.interp(t, arr[:, 0], arr[:, 1]); y = np.interp(t, arr[:, 0], arr[:, 2])
            u, v = self.project(x, y, pw, ph)
            cv2.circle(img, (u, v), 9, (20, 20, 20), 4, cv2.LINE_AA)
            cv2.circle(img, (u, v), 9, EXIT_BGR.get(e, (255, 255, 255)), 2, cv2.LINE_AA)
        head = np.full((54, pw, 3), (24, 24, 28), np.uint8)
        cv2.putText(head, self.label, (12, 36), FONT, 0.85, (255, 255, 255), 2, cv2.LINE_AA)
        foot = np.full((46, pw, 3), (24, 24, 28), np.uint8)
        cv2.putText(foot, f"t = {t:5.1f} s", (12, 32), FONT, 0.8, (0, 255, 140), 2, cv2.LINE_AA)
        cv2.putText(foot, f"out {out:2d} / {self.n}", (200, 32), FONT, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
        if out == self.n:
            cv2.putText(foot, "everyone out", (400, 32), FONT, 0.8, (0, 220, 255), 2, cv2.LINE_AA)
        return np.vstack([head, img, foot])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", required=True)
    ap.add_argument("--root", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    for s in ("left", "right"):
        ap.add_argument(f"--{s}", required=True); ap.add_argument(f"--{s}-plan", required=True); ap.add_argument(f"--{s}-label", default="")
    ap.add_argument("--title", default="Isaac Sim twin, roof off: same hospital, same 40 people, same seed  (rings = recorded positions, colour = assigned exit)")
    ap.add_argument("--h", type=int, default=720); ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--start-frame", type=int, default=20); ap.add_argument("--reach", type=float, default=1.5)
    ap.add_argument("--hold", type=float, default=3.0, help="extra seconds after the slower side is all out")
    ap.add_argument("--variant", default="dollhouse", help="run/stage suffix, e.g. dollhouse or dollhouse_fire")
    ap.add_argument("--closures-from", help="Layer-1 report: mark exits CLOSED at their smoke closure time")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    venue = json.load(open(a.venue))
    Side.closures = {e: t for e, t in json.load(open(a.closures_from)).get("corridor_closed_at_s", {}).items()
                     if t is not None} if a.closures_from else {}
    L = Side(a.root, a.left, venue, json.load(open(a.left_plan)), a.left_label, a.reach, a.start_frame, a.fps, a.variant)
    R = Side(a.root, a.right, venue, json.load(open(a.right_plan)), a.right_label, a.reach, a.start_frame, a.fps, a.variant)
    last_out = max(max(t for _, _, t in S.agents if t is not None) for S in (L, R))
    n = min(len(L.frames), len(R.frames), int((last_out + a.hold) * a.fps) - a.start_frame)
    s0 = L.render(0, a.h); PW, PH = s0.shape[1], s0.shape[0]; gap = 6
    W, Ht = PW * 2 + gap, PH + 52
    vw = cv2.VideoWriter(a.out, cv2.VideoWriter_fourcc(*"mp4v"), a.fps, (W, Ht))
    assert vw.isOpened()
    for i in range(n):
        tl = np.full((52, W, 3), (10, 10, 12), np.uint8)
        cv2.putText(tl, a.title, (14, 34), FONT, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        vw.write(np.vstack([tl, np.hstack([L.render(i, a.h), np.zeros((PH, gap, 3), np.uint8), R.render(i, a.h)])]))
        if i % 600 == 0: print(f"  {i}/{n}")
    vw.release()
    print(f"wrote {a.out} ({n} frames, {n / a.fps:.1f} s, {W}x{Ht}) | out-times: left last {max(t for _,_,t in L.agents if t)}, right last {max(t for _,_,t in R.agents if t)}")


if __name__ == "__main__":
    main()
