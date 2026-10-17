"""
stitch_film.py — side-by-side MP4 from two IRA film runs (left vs right), one camera each.
Uses OpenCV only (the Isaac container's cv2); no ffmpeg needed.

  /isaac-sim/python.sh sim/stitch_film.py \
     --left  results/ira_hospital_winner_film60s --left-label  "Grimoires plan: 4 exits, alarm 5s" \
     --right results/ira_hospital_base_film60s   --right-label "Base plan: front doors, alarm 30s" \
     --cam cam_E1 --fps 30 --title "Hospital fire at the main entrance - same fire, same seed" \
     --out results/films/hospital_b_sidebyside.mp4
"""
import argparse
import glob
import os
import cv2


def frames(run_dir, cam):
    cams = sorted(d for d in os.listdir(run_dir) if cam in d and os.path.isdir(os.path.join(run_dir, d, "rgb")))
    if not cams:
        raise SystemExit(f"{run_dir}: no camera dir matching {cam!r}")
    return sorted(glob.glob(os.path.join(run_dir, cams[0], "rgb", "*.png")))


def banner(img, title, sub, w):
    cv2.rectangle(img, (0, 0), (w, 70), (20, 20, 20), -1)
    cv2.putText(img, title, (16, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(img, sub, (16, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 220, 255), 1, cv2.LINE_AA)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--left", required=True); ap.add_argument("--left-label", default="")
    ap.add_argument("--right", required=True); ap.add_argument("--right-label", default="")
    ap.add_argument("--cam", default="cam_E1")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--h", type=int, default=540, help="height per panel")
    ap.add_argument("--title", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    L, R = frames(a.left, a.cam), frames(a.right, a.cam)
    n = min(len(L), len(R))
    if n == 0:
        raise SystemExit("no frames")
    sample = cv2.imread(L[0]); H0, W0 = sample.shape[:2]
    scale = a.h / H0; pw = int(W0 * scale)
    gap = 6
    W = pw * 2 + gap
    top = 70 if a.title else 0
    H = a.h + top
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)

    for fourcc_name, ext in (("avc1", ".mp4"), ("mp4v", ".mp4"), ("MJPG", ".avi")):
        out = os.path.splitext(a.out)[0] + ext
        vw = cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*fourcc_name), a.fps, (W, H))
        if vw.isOpened():
            print(f"codec {fourcc_name} -> {out}")
            break
        vw.release()
    else:
        raise SystemExit("no working VideoWriter codec")

    for i in range(n):
        li = cv2.resize(cv2.imread(L[i]), (pw, a.h))
        ri = cv2.resize(cv2.imread(R[i]), (pw, a.h))
        banner(li, a.left_label, "", pw)
        banner(ri, a.right_label, "", pw)
        t = i / a.fps
        cv2.putText(li, f"t = {t:4.1f} s", (pw - 150, a.h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 120), 2, cv2.LINE_AA)
        cv2.putText(ri, f"t = {t:4.1f} s", (pw - 150, a.h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 120), 2, cv2.LINE_AA)
        row = cv2.hconcat([li, cv2.copyMakeBorder(ri, 0, 0, gap, 0, cv2.BORDER_CONSTANT, value=(0, 0, 0))])
        if top:
            canvas = cv2.copyMakeBorder(row, top, 0, 0, 0, cv2.BORDER_CONSTANT, value=(10, 10, 10))
            cv2.putText(canvas, a.title, (16, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
            frame = canvas
        else:
            frame = row
        vw.write(frame)
        if i % 300 == 0:
            print(f"  {i}/{n}")
    vw.release()
    print(f"wrote {out}  ({n} frames, {n / a.fps:.1f} s, {W}x{H})")


if __name__ == "__main__":
    main()
