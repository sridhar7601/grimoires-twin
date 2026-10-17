"""
score_vlm.py — score the self-hosted Cosmos Reason 2 NIM against IRA ground truth.

For every Nth frame of every camera in an IRA output folder:
  truth  = people whose tight 2D box is non-empty (visible at all), plus how much of
           each shows (tight box area / loose box area; approximate visibility)
  model  = Cosmos asked for a single-integer people count
Frames are bucketed: empty / all mostly visible (>=50%) / someone mostly hidden (<50%).
Prints accuracy per bucket and writes every answer to a JSON file. Stdlib only.

  python3 sim/score_vlm.py results/ira_warehouse --every 5 --out results/vlm_score_warehouse.json
"""
import argparse
import base64
import concurrent.futures as cf
import glob
import json
import os
import re
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("ira_dir")
ap.add_argument("--every", type=int, default=5, help="score every Nth frame")
ap.add_argument("--hidden", type=float, default=0.5, help="below this visibility a person counts as mostly hidden")
ap.add_argument("--url", default="http://localhost:8000")
ap.add_argument("--workers", type=int, default=4)
ap.add_argument("--out", required=True)
args = ap.parse_args()

PROMPT = ("This is a ceiling security camera frame. How many people are in it, including anyone "
          "partly hidden behind objects? Reply with a single integer only.")

model = json.load(urllib.request.urlopen(args.url + "/v1/models", timeout=30))["data"][0]["id"]


def area(b):
    return max(0, b["x_max"] - b["x_min"]) * max(0, b["y_max"] - b["y_min"])


def truth(det_path):
    people = []
    for a in json.load(open(det_path))["agents"].values():
        t = a["annotators"].get("bounding_box_2d_tight_fast")
        l = a["annotators"].get("bounding_box_2d_loose_fast")
        if t and area(t) > 0:
            people.append(round(area(t) / max(area(l), 1), 2) if l else 1.0)
    return people


def ask(png):
    b64 = base64.b64encode(open(png, "rb").read()).decode()
    body = {"model": model, "max_tokens": 64, "temperature": 0.0,
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": PROMPT}]}]}
    req = urllib.request.Request(args.url + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    text = json.load(urllib.request.urlopen(req, timeout=300))["choices"][0]["message"]["content"]
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"\d+", text)
    return (int(m.group()) if m else None), text.strip()[:200]


jobs = []
for cam in sorted(glob.glob(os.path.join(args.ira_dir, "*", "rgb"))):
    cam_dir = os.path.dirname(cam)
    for png in sorted(glob.glob(os.path.join(cam, "rgb_*.png")))[:: args.every]:
        idx = re.search(r"(\d+)\.png$", png).group(1)
        det = os.path.join(cam_dir, "object_detection", f"object_detection_{idx}.json")
        if os.path.exists(det):
            jobs.append((os.path.basename(cam_dir), idx, png, det))
print(f"[score] model={model}  frames={len(jobs)}  (every {args.every}th, {args.workers} at a time)")


def run(job):
    cam, idx, png, det = job
    vis = truth(det)
    pred, raw = ask(png)
    if not vis:
        bucket = "empty"
    elif min(vis) < args.hidden:
        bucket = "someone mostly hidden"
    else:
        bucket = "all mostly visible"
    return {"camera": cam, "frame": idx, "truth": len(vis), "visibility": vis,
            "pred": pred, "correct": pred == len(vis), "bucket": bucket, "raw": raw}


rows = []
with cf.ThreadPoolExecutor(args.workers) as ex:
    for i, r in enumerate(ex.map(run, jobs), 1):
        rows.append(r)
        if i % 20 == 0:
            print(f"  {i}/{len(jobs)} done")

json.dump(rows, open(args.out, "w"), indent=1)

print(f"\n{'bucket':<24}{'frames':>7}{'exact':>8}{'acc':>7}{'mean |err|':>12}")
for b in ["empty", "all mostly visible", "someone mostly hidden", "ALL"]:
    sel = [r for r in rows if b == "ALL" or r["bucket"] == b]
    if not sel:
        continue
    ok = sum(r["correct"] for r in sel)
    err = [abs((r["pred"] if r["pred"] is not None else 0) - r["truth"]) for r in sel]
    print(f"{b:<24}{len(sel):>7}{ok:>8}{ok / len(sel):>7.0%}{sum(err) / len(sel):>12.2f}")
under = sum(1 for r in rows if r["pred"] is not None and r["pred"] < r["truth"])
over = sum(1 for r in rows if r["pred"] is not None and r["pred"] > r["truth"])
print(f"\nundercounts (missed someone): {under}   overcounts (invented someone): {over}   "
      f"unparseable: {sum(r['pred'] is None for r in rows)}")
print(f"[score] -> {args.out}")
