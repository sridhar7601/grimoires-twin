"""
stitch_cctv.py — the security-monitor cut: six fixed cameras inside the hospital (CCTV_CAMS in
make_ira_config.py), base plan and Grimoires plan side by side, each as a 2 x 3 wall of feeds with
camera name, REC dot, wall-clock since alarm, and a red banner on the feeds that watch an exit once
smoke has closed it. The `out N / M` counter per side comes from the twin's own position dump.
Nothing is staged: every frame is an Isaac render, every number is recorded data.

  /isaac-sim/python.sh sim/stitch_cctv.py --venue results/hospital_plan.json \
     --left  winner --left-plan  scenarios/hospital_winner_plan.json --left-label  "Grimoires plan: 4 exits, alarm 5 s" \
     --right base   --right-plan scenarios/hospital_base_plan.json   --right-label "Base plan: front doors, alarm 30 s" \
     --left-variant cctv60s_fire --right-variant cctv120s_fire --closures-from results/rehearse_hospital_base.json --step 2 \
     --out results/films/hospital_cctv.mp4
(--left/--right = the plan tag: reads results/ira_hospital_<tag>_<variant>/_World_FilmCams_CAM0x/rgb/; whichever CAM dirs exist are shown)
"""
import argparse, collections, glob, json, os, re, sys
import cv2
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_exit_targets import inside_points  # noqa: E402

FONT = cv2.FONT_HERSHEY_SIMPLEX
# camera labels + the exit each one watches (None = none); feeds present on disk decide which appear
CAM_INFO = {"CAM01": ("LOBBY / MAIN ENTRANCE E1", "E1"), "CAM02": ("CENTRAL CORRIDOR", None),
            "CAM03": ("WEST WING / EXIT E4", "E4"), "CAM04": ("NORTH-WEST WING / EXIT E2", "E2"),
            "CAM05": ("EAST WING / EXIT E3", "E3"), "CAM06": ("WEST WING WARDS", None)}
TILE_W, TILE_H, COLS = 640, 360, 2
BG = (18, 18, 22)


class Side:
    closures = {}

    def __init__(self, root, tag, venue, plan, label, reach, start_frame, fps, variant):
        self.label, self.start_frame, self.fps = label, start_frame, fps
        run = os.path.join(root, "results", f"ira_hospital_{tag}_{variant}")
        self.feeds = []
        for name in sorted(CAM_INFO):
            d = [p for p in glob.glob(os.path.join(run, f"*{name}*")) if os.path.isdir(p)]
            if not d:
                continue
            cam_label, watches = CAM_INFO[name]
            self.feeds.append((name, cam_label, watches, sorted(glob.glob(os.path.join(d[0], "rgb", "*.png")))))
        if len(self.feeds) % COLS:
            self.feeds.append(("", "", None, []))                      # pad the wall with a NO SIGNAL tile
        self.nframes = min((len(f[3]) for f in self.feeds if f[3]), default=0)
        targets = inside_points(venue)
        self.open = [e for e in plan["exits_open"] if e in targets]
        tr, grp = collections.defaultdict(list), {}
        for line in open(os.path.join(run, "agent_positions.jsonl")):
            r = json.loads(line); tr[r["agent"]].append((r["t"], r["x"], r["y"])); grp[r["agent"]] = r.get("group", "")
        self.t_out = []
        for a, pts in tr.items():
            pts.sort(); arr = np.array(pts)
            e = re.findall(r"E\d+", grp[a])[-1]
            tx, ty = targets[e][0], targets[e][1]
            hit = np.nonzero(np.hypot(arr[:, 1] - tx, arr[:, 2] - ty) <= reach)[0]
            self.t_out.append(float(arr[hit[0], 0]) if len(hit) else None)
        self.n = len(self.t_out)

    def t_of(self, i):
        return (i + self.start_frame) / self.fps

    def tile(self, feed, i, t):
        name, cam_label, watches, frames = feed
        i = min(i, len(frames) - 1)                                     # a side that finished early holds its last frame
        img = cv2.imread(frames[i]) if frames else None
        if img is None:
            img = np.full((TILE_H, TILE_W, 3), (40, 40, 40), np.uint8)
            cv2.putText(img, "NO SIGNAL", (230, 190), FONT, 1.0, (120, 120, 120), 2, cv2.LINE_AA)
        elif img.shape[:2] != (TILE_H, TILE_W):
            img = cv2.resize(img, (TILE_W, TILE_H), interpolation=cv2.INTER_AREA)
        # top strip: camera id + label, REC dot, clock since alarm start of sim
        if not name:
            return img
        cv2.rectangle(img, (0, 0), (TILE_W, 30), (0, 0, 0), -1)
        cv2.putText(img, f"{name}  {cam_label}", (8, 21), FONT, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        if int(t * 2) % 2 == 0:
            cv2.circle(img, (TILE_W - 118, 15), 6, (0, 0, 255), -1, cv2.LINE_AA)
        cv2.putText(img, "REC", (TILE_W - 108, 21), FONT, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(img, f"{int(t // 60):02d}:{t % 60:04.1f}", (TILE_W - 66, 21), FONT, 0.55, (0, 255, 140), 1, cv2.LINE_AA)
        if watches and watches in self.open and t >= self.closures.get(watches, float("inf")):
            cv2.rectangle(img, (0, TILE_H - 34), (TILE_W, TILE_H), (0, 0, 200), -1)
            cv2.putText(img, f"EXIT {watches} CLOSED - SMOKE", (8, TILE_H - 10), FONT, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        elif watches and watches not in self.open:
            cv2.rectangle(img, (0, TILE_H - 34), (TILE_W, TILE_H), (60, 60, 60), -1)
            cv2.putText(img, f"EXIT {watches} NOT IN PLAN", (8, TILE_H - 10), FONT, 0.7, (200, 200, 200), 2, cv2.LINE_AA)
        cv2.rectangle(img, (0, 0), (TILE_W - 1, TILE_H - 1), (70, 70, 70), 1)
        return img

    def render(self, i):
        t = self.t_of(i)
        tiles = [self.tile(f, i, t) for f in self.feeds]
        rows = [np.hstack(tiles[r * COLS:(r + 1) * COLS]) for r in range(len(tiles) // COLS)]
        wall = np.vstack(rows)
        W = wall.shape[1]
        out = sum(1 for v in self.t_out if v is not None and t >= v)
        head = np.full((54, W, 3), BG, np.uint8)
        cv2.putText(head, self.label, (12, 36), FONT, 0.85, (255, 255, 255), 2, cv2.LINE_AA)
        foot = np.full((46, W, 3), BG, np.uint8)
        cv2.putText(foot, f"t = {t:5.1f} s", (12, 32), FONT, 0.8, (0, 255, 140), 2, cv2.LINE_AA)
        cv2.putText(foot, f"out {out:2d} / {self.n}", (200, 32), FONT, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
        if out == self.n:
            cv2.putText(foot, "everyone out", (400, 32), FONT, 0.8, (0, 220, 255), 2, cv2.LINE_AA)
        return np.vstack([head, wall, foot])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", required=True)
    ap.add_argument("--root", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    for s in ("left", "right"):
        ap.add_argument(f"--{s}", required=True); ap.add_argument(f"--{s}-plan", required=True); ap.add_argument(f"--{s}-label", default="")
    ap.add_argument("--title", default="Security cameras, Isaac Sim twin: same hospital, same 40 people, same seed, Omniverse Flow fire at the main entrance")
    ap.add_argument("--fps", type=float, default=30.0, help="render frame rate (writer)")
    ap.add_argument("--step", type=int, default=2, help="use every k-th frame -> k x speed at --fps playback")
    ap.add_argument("--start-frame", type=int, default=20); ap.add_argument("--reach", type=float, default=1.5)
    ap.add_argument("--variant", default="cctv_fire")
    ap.add_argument("--left-variant"); ap.add_argument("--right-variant")
    ap.add_argument("--closures-from", help="Layer-1 report: exits CLOSED at their smoke closure time")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    venue = json.load(open(a.venue))
    if a.closures_from:
        Side.closures = {e: t for e, t in json.load(open(a.closures_from)).get("corridor_closed_at_s", {}).items() if t is not None}
    L = Side(a.root, a.left, venue, json.load(open(a.left_plan)), a.left_label, a.reach, a.start_frame, a.fps, a.left_variant or a.variant)
    R = Side(a.root, a.right, venue, json.load(open(a.right_plan)), a.right_label, a.reach, a.start_frame, a.fps, a.right_variant or a.variant)
    n = max(L.nframes, R.nframes)                                      # the longer side sets the length; the other holds
    if n == 0:
        raise SystemExit("no frames found for one side")
    first = np.hstack([L.render(0), np.full((L.render(0).shape[0], 6, 3), BG, np.uint8), R.render(0)])
    title = np.full((44, first.shape[1], 3), BG, np.uint8)
    cv2.putText(title, a.title, (12, 30), FONT, 0.75, (230, 230, 230), 2, cv2.LINE_AA)
    H, W = title.shape[0] + first.shape[0], first.shape[1]
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    vw = cv2.VideoWriter(a.out, cv2.VideoWriter_fourcc(*"mp4v"), a.fps, (W, H))
    for k, i in enumerate(range(0, n, a.step)):
        l, r = L.render(i), R.render(i)
        vw.write(np.vstack([title, np.hstack([l, np.full((l.shape[0], 6, 3), BG, np.uint8), r])]))
        if k % 200 == 0:
            print(f"  frame {i}/{n}  t={L.t_of(i):.1f}s", flush=True)
    vw.release()
    print(f"wrote {a.out}  {W}x{H}  {len(range(0, n, a.step))} frames at {a.fps:.0f} fps ({a.step}x speed)")


if __name__ == "__main__":
    main()
