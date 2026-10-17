"""
tools.py — the Grimoires pipeline as plain functions an agent can call (Phase 7).

Layer 1 (rehearse / evaluate / grid_search) runs locally in plain Python, ~1 s per rehearsal.
Layer 2 (start_twin / twin_status) runs on the GPU box over SSH, minutes per plan.
Everything returns small JSON-able dicts: an LLM reads these, so they are summaries, not raw reports.

  python3 sim/agent/tools.py describe
  python3 sim/agent/tools.py evaluate '{"exits_open": ["E1","E2","E3"], "alarm_delay_s": 5, "stagger_s": 25}'
"""
import glob
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "sim"))
from plan import plan_id  # noqa: E402
from rehearse import run  # noqa: E402
from solve import WEIGHTS, score  # noqa: E402

VENUE = os.path.join(ROOT, "results", "hospital", "hospital_plan.json")
BASE = os.path.join(ROOT, "scenarios", "hospital_base_plan.json")
FIRES = {os.path.basename(p)[len("hospital_fire_"):-5]: p for p in sorted(glob.glob(os.path.join(ROOT, "scenarios", "hospital_fire_*.json")))}
PEOPLE, SEED, FPS = 300, 42, 12.0
LIMITS = {"alarm_delay_s": (0.0, 120.0), "stagger_s": (0.0, 120.0)}

BOX = ["ssh", "-i", os.path.expanduser("~/.ssh/launchpad"), "-p", "12313", "-o", "ConnectTimeout=8",
       "nvidia@global.prd.ga.launchpad.nvidia.com"]
SCP = ["scp", "-q", "-i", os.path.expanduser("~/.ssh/launchpad"), "-P", "12313", "-o", "ConnectTimeout=8"]
BOX_REPO = "/home/nvidia/Documents/grimoires-twin"

_venue = None


def _v():
    global _venue
    if _venue is None:
        _venue = json.load(open(VENUE))
    return _venue


def normalise(plan):
    """Validate an agent-proposed plan; returns a clean plan dict or raises ValueError with a readable reason."""
    exits = list(_v()["exits"])
    p = {"gates_open": [], "route_bias": {}}
    eo = plan.get("exits_open")
    if not isinstance(eo, list) or not eo:
        raise ValueError(f"exits_open must be a non-empty list drawn from {exits}")
    bad = [e for e in eo if e not in exits]
    if bad:
        raise ValueError(f"unknown exits {bad}; this venue has {exits}")
    p["exits_open"] = [e for e in exits if e in eo]                      # canonical order, no duplicates
    for k, (lo, hi) in LIMITS.items():
        try:
            val = float(plan.get(k))
        except (TypeError, ValueError):
            raise ValueError(f"{k} must be a number of seconds in [{lo}, {hi}]")
        if not lo <= val <= hi:
            raise ValueError(f"{k}={val} outside [{lo}, {hi}]")
        p[k] = round(val, 1)
    return p


def _summary(r):
    return {"t50_s": r["t50_s"], "t90_s": r["t90_s"], "t100_s": r["t100_s"], "trapped": r["trapped"],
            "over_30s_smoke": r["n_over_exposure_threshold"], "through_dense_smoke": r["n_in_dense_smoke"],
            "exposure_mean_s": r["exposure_mean_s"], "exits_used": r["exit_throughput_total"],
            "exits_closed_by_smoke_at_s": {k: v for k, v in r["corridor_closed_at_s"].items() if v is not None},
            "score": score(r)}


def describe():
    """The problem an agent is solving: venue, exits, fires, the base plan, the knobs, the score."""
    v = _v()
    return {
        "venue": v["name"], "people": PEOPLE, "seed": SEED,
        "exits": {e: {"world_xy": d["centre_world"]} for e, d in v["exits"].items()},
        "exit_notes": {"E1": "main entrance (south)", "E2": "west wing, north end", "E3": "east wing, east side", "E4": "west wing, side door"},
        "fires": {k: json.load(open(p)).get("note", "") for k, p in FIRES.items()},
        "base_plan": normalise(json.load(open(BASE))),
        "knobs": {"exits_open": "any non-empty subset of the exits", "alarm_delay_s": list(LIMITS["alarm_delay_s"]),
                  "stagger_s": list(LIMITS["stagger_s"]) + ["spread of departure times after the alarm"]},
        "score": f"{WEIGHTS['w_t90']}*t90 + {WEIGHTS['w_exp']}*exposure_mean + {WEIGHTS['w_trap']}*trapped + "
                 f"{WEIGHTS['w_dense']}*through_dense_smoke; lower is better; a plan's robust score is its WORST fire",
        "honesty": "rehearses/ranks, never predicts; simplified grid smoke; people do not collide; no density figures",
    }


def rehearse(plan, fire="entrance"):
    """One Layer-1 rehearsal of `plan` against one fire. ~1 s."""
    p = normalise(plan)
    f = json.load(open(FIRES[fire]))
    r = run(_v(), p, f, seed=SEED, fps=FPS, people=PEOPLE)
    return dict({"plan_id": plan_id(p), "fire": fire}, **_summary(r))


def evaluate(plan, fires=None):
    """Rehearse `plan` against every fire (default: all five); robust score = worst fire. ~4 s."""
    p = normalise(plan)
    names = fires or list(FIRES)
    per = {n: rehearse(p, n) for n in names}
    worst = max(per, key=lambda n: per[n]["score"])
    return {"plan": p, "plan_id": plan_id(p), "robust_score": per[worst]["score"], "worst_fire": worst,
            "t90_by_fire": {n: per[n]["t90_s"] for n in names},
            "over_30s_smoke_by_fire": {n: per[n]["over_30s_smoke"] for n in names},
            "trapped_total": sum(per[n]["trapped"] for n in names), "per_fire": per}


def grid_search(fires=None, top=5):
    """The fixed 24-variant sweep (exits ⊇ base × alarm {30,15,5} × stagger {25,10}), ranked by worst fire. ~80 s for 5 fires."""
    from plan import enumerate_variants
    base = json.load(open(BASE))
    rows = []
    for p in enumerate_variants(base, _v()):
        e = evaluate(p, fires)
        rows.append({"plan_id": e["plan_id"], "plan": e["plan"], "robust_score": e["robust_score"],
                     "worst_fire": e["worst_fire"], "t90_by_fire": e["t90_by_fire"]})
    rows.sort(key=lambda r: r["robust_score"])
    return {"variants": len(rows), "top": rows[:top], "base": next(r for r in rows if r["plan_id"] == plan_id(normalise(base)))}


def certificate():
    """The current two-layer certificate (Python solver vs Isaac twin), as markdown."""
    return open(os.path.join(ROOT, "docs", "results", "certificate.md")).read()


# ------------------------------------------------------------------- Layer 2: the Isaac twin on the GPU box
def start_twin(plan, name=None, people=40):
    """Queue an Isaac Sim rehearsal of `plan` on the GPU box (doors open, smoke closure from Layer 1, entrance fire).
    Returns a job name for twin_status. Takes ~30-50 min of GPU; one run at a time on GPU 0."""
    p = normalise(plan)
    job = name or "agent_" + plan_id(p).replace("-", "_").replace(".", "p").lower()
    l1 = run(_v(), p, json.load(open(FIRES["entrance"])), seed=SEED, fps=FPS, people=PEOPLE)
    tmp = f"/tmp/{job}"
    os.makedirs(tmp, exist_ok=True)
    json.dump(p, open(f"{tmp}/hospital_{job}_plan.json", "w"), indent=2)
    json.dump(l1, open(f"{tmp}/rehearse_hospital_{job}.json", "w"))
    subprocess.run(SCP + [f"{tmp}/hospital_{job}_plan.json", f"{tmp}/rehearse_hospital_{job}.json",
                          "nvidia@global.prd.ga.launchpad.nvidia.com:/tmp/"], check=True)
    remote = f"""
set -e; cd {BOX_REPO}
sudo cp /tmp/hospital_{job}_plan.json scenarios/ && sudo cp /tmp/rehearse_hospital_{job}.json results/
sudo chown 1234:1234 scenarios/hospital_{job}_plan.json results/rehearse_hospital_{job}.json
docker run --rm --network=host -v {BOX_REPO}:/workspace:rw --entrypoint bash nvcr.io/nvidia/isaac-sim:6.0.1 -c \
  "cd /workspace && bash sim/usdpy.sh sim/make_ira_config.py --plan scenarios/hospital_{job}_plan.json --venue results/hospital_plan.json \
   --layer1-report results/rehearse_hospital_{job}.json --people {people} --measure-only --smoke-closure" | grep -E "wrote sim/ira"
FILM_QUEUE_STATUS=$HOME/{job}.status nohup bash sim/ira/run_film_queue.sh {job}_measure_fire > $HOME/{job}.queue.log 2>&1 &
sleep 1; tail -2 $HOME/{job}.status
"""
    out = subprocess.run(BOX + ["bash", "-s"], input=remote, capture_output=True, text=True)
    return {"job": job, "plan_id": plan_id(p), "layer1_entrance_t90_s": l1["t90_s"],
            "queued": out.returncode == 0, "box": (out.stdout + out.stderr).strip()[-600:],
            "note": "GPU runs are sequential; if another Isaac run is active this one waits. Poll twin_status every few minutes."}


def twin_status(job):
    """Where the twin run is; when finished, its Layer-2 numbers (measured from every character's recorded position)."""
    remote = f"""
cd {BOX_REPO}
S=$HOME/{job}.status; [ -f $S ] || {{ echo "STATE unknown-job"; exit 0; }}
tail -1 $S | sed 's/^/LAST /'
D=results/ira_hospital_{job}_measure_fire/agent_positions.jsonl
sudo test -s $D && echo "SIMT $(sudo tail -1 $D | python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["t"])')"
if grep -q "ALL DONE" $S; then
  sudo python3 sim/measure.py --venue results/hospital_plan.json --plan scenarios/hospital_{job}_plan.json \
    --positions $D --closures-from results/rehearse_hospital_{job}.json --report results/layer2_{job}.json > /dev/null
  echo "REPORT $(sudo cat results/layer2_{job}.json | python3 -c 'import json,sys; d=json.load(sys.stdin); print(json.dumps({{k: d[k] for k in ("t50_s","t90_s","t100_s","arrived","never_arrived","exit_throughput_total","arrived_after_closure")}}))')"
fi
"""
    out = subprocess.run(BOX + ["bash", "-s"], input=remote, capture_output=True, text=True).stdout
    res = {"job": job}
    for line in out.splitlines():
        if line.startswith("LAST "):
            res["last_status"] = line[5:]
        elif line.startswith("SIMT "):
            res["sim_time_reached_s"] = float(line[5:])
        elif line.startswith("REPORT "):
            res["layer2"] = json.loads(line[7:])
        elif line.startswith("STATE "):
            res["state"] = line[6:]
    res.setdefault("state", "done" if "layer2" in res else "running")
    return res


if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["describe"]
    fn = {"describe": describe, "rehearse": rehearse, "evaluate": evaluate, "grid_search": grid_search,
          "certificate": certificate, "start_twin": start_twin, "twin_status": twin_status}[cmd]
    t0 = time.time()
    out = fn(*[json.loads(x) if x[:1] in "{[" else x for x in args])
    print(json.dumps(out, indent=1) if not isinstance(out, str) else out)
    print(f"({time.time() - t0:.1f} s)", file=sys.stderr)
