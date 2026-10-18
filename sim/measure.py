"""
measure.py — Layer 2 numbers from an Isaac rehearsal: per agent, the first time it is within
`--reach` metres of ITS exit target -> exit time -> clearance curve, t50/t90/t100, exits used.
Same report keys as rehearse.py so the certificate can put both layers in one table.

Position source (pick one):
  --positions results/ira_hospital_base/agent_positions.jsonl   (actor_sdg_dump.py: EVERY agent, every
                                                                 frame, timeline seconds)  <- the real thing
  --object-detection results/ira_hospital_base                  (IRA writer: only agents VISIBLE to a camera,
                                                                 union over cameras; partial by construction)
Exit targets = the MoveTo points, recomputed from the venue grid exactly as make_exit_targets.py /
make_ira_config.py place them. An agent's exit = its group (prim path .../evac_E3/...); if it never
reaches that one but reaches another open exit, it counts there and is listed under `redirected`.

  python3 sim/measure.py --venue results/hospital_plan.json --plan scenarios/hospital_base_plan.json \
      --positions results/ira_hospital_base/agent_positions.jsonl --report results/layer2_base.json
"""
import argparse
import collections
import glob
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_exit_targets import inside_points  # noqa: E402
from plan import plan_id  # noqa: E402
from crowding import door_crowding  # noqa: E402

GROUP_RE = re.compile(r"/evac_(E\d+)(?:_to_(E\d+))?/")   # evac_E1 -> E1 ; evac_E1_to_E2 -> E2 (set off after E1 closed)


def load_positions_jsonl(path):
    """{agent: [(t, x, y)]} sorted by t."""
    tracks = collections.defaultdict(list)
    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            tracks[r["agent"]].append((float(r["t"]), float(r["x"]), float(r["y"])))
    return {a: sorted(v) for a, v in tracks.items()}


def load_positions_object_detection(root, fps, start_frame):
    """Union over cameras of metro_agent_data.world_position; t = (frame + start_frame) / fps."""
    tracks = collections.defaultdict(dict)
    for f in sorted(glob.glob(os.path.join(root, "*", "object_detection", "object_detection_*.json"))):
        idx = int(re.search(r"(\d+)\.json$", f).group(1))
        t = (idx + start_frame) / fps
        for prim, a in json.load(open(f)).get("agents", {}).items():
            m = a.get("metro_agent_data") or {}
            if "world_position" in m:
                x, y = m["world_position"][0], m["world_position"][1]
                tracks[prim][round(t, 4)] = (x, y)
    return {a: sorted((t, x, y) for t, (x, y) in d.items()) for a, d in tracks.items()}


def agent_exit(prim_path, open_exits):
    m = GROUP_RE.search(prim_path)
    if not m:
        return None
    target = m.group(2) or m.group(1)
    return target if target in open_exits else None


def first_arrival(track, target, reach):
    tx, ty = target[0], target[1]
    for t, x, y in track:
        if math.hypot(x - tx, y - ty) <= reach:
            return t
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", required=True)
    ap.add_argument("--plan", required=True)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--positions", help="agent_positions.jsonl from actor_sdg_dump.py")
    src.add_argument("--object-detection", help="IRA writer output dir (camera-visible agents only)")
    ap.add_argument("--fps", type=float, default=30.0, help="writer frame rate (object-detection source)")
    ap.add_argument("--start-frame", type=int, default=20, help="writer start_frame (object-detection source)")
    ap.add_argument("--reach", type=float, default=1.5, help="metres from the exit target that counts as out")
    ap.add_argument("--closures-from", help="Layer-1 report: count arrivals at an exit after its smoke closure time")
    ap.add_argument("--report", required=True)
    a = ap.parse_args()

    venue, plan = json.load(open(a.venue)), json.load(open(a.plan))
    open_exits = [e for e in plan["exits_open"] if e in venue["exits"]]
    targets = {e: p for e, p in inside_points(venue).items()}

    if a.positions:
        tracks, source = load_positions_jsonl(a.positions), "agent_positions.jsonl (all agents, every frame)"
    else:
        tracks, source = load_positions_object_detection(a.object_detection, a.fps, a.start_frame), \
            "object_detection (camera-visible agents only — PARTIAL)"
    if not tracks:
        raise SystemExit("no agent positions found")

    t_end = max(tr[-1][0] for tr in tracks.values())
    arrivals, used, redirected, never = {}, collections.Counter(), {}, []
    for prim, tr in tracks.items():
        own = agent_exit(prim, open_exits)
        t_own = first_arrival(tr, targets[own], a.reach) if own else None
        if t_own is not None:
            arrivals[prim], used[own] = t_own, used[own] + 1
            continue
        other = sorted((first_arrival(tr, targets[e], a.reach), e) for e in open_exits if e != own)
        other = [(t, e) for t, e in other if t is not None]
        if other:
            t_o, e_o = other[0]
            arrivals[prim], used[e_o], redirected[prim] = t_o, used[e_o] + 1, {"assigned": own, "used": e_o, "t": round(t_o, 2)}
        else:
            never.append(prim)

    n = len(tracks)
    ts = sorted(arrivals.values())
    def t_at(frac):
        k = math.ceil(frac * n)
        return round(ts[k - 1], 1) if k <= len(ts) else None
    t50, t90, t100 = t_at(0.5), t_at(0.9), t_at(1.0)
    curve = []
    step = 1.0
    t = 0.0
    while t <= t_end + 1e-9:
        out = sum(1 for v in ts if v <= t)
        curve.append([round(t, 1), n - out, out])
        t += step
    straggler_dist = {p: round(min(math.hypot(x - targets[agent_exit(p, open_exits) or open_exits[0]][0],
                                             y - targets[agent_exit(p, open_exits) or open_exits[0]][1]) for _, x, y in tr), 1)
                      for p, tr in tracks.items() if p in never}

    # Door-crowding demand: people NOT yet arrived within 2 m of each open door, every 0.1 s.
    # Arrived characters stand still on their exit target (MoveTo ends there), so they are dropped
    # from the count once they are out -- otherwise the doorway looks crowded by people who left.
    snap = collections.defaultdict(list)
    for prim, tr in tracks.items():
        t_out = arrivals.get(prim, float("inf"))
        for t, x, y in tr:
            if t < t_out:
                snap[round(t, 1)].append((x, y))
    door_centre = {e: tuple(venue["exits"][e].get("centre_world") or targets[e][:2]) for e in open_exits}
    crowding = door_crowding(sorted(snap.items()), door_centre, 0.1)

    after_closure = {}
    if a.closures_from:
        cl = {e: t for e, t in json.load(open(a.closures_from)).get("corridor_closed_at_s", {}).items() if t is not None}
        for prim, tr in tracks.items():
            for e, tc in cl.items():
                ta = first_arrival(tr, targets[e], a.reach)
                if ta is not None and ta > tc and prim in arrivals and abs(arrivals[prim] - ta) < 1e-6:
                    after_closure[e] = after_closure.get(e, 0) + 1
    report = {
        "layer": 2, "venue": venue["name"], "plan": plan, "plan_id": plan_id(plan), "open_exits": open_exits,
        "source": source, "reach_m": a.reach, "people": n, "sim_span_s": round(t_end, 1),
        "t50_s": t50, "t90_s": t90, "t100_s": t100,
        "exit_throughput_total": dict(used), "arrived": len(arrivals), "never_arrived": len(never),
        "arrived_after_closure": after_closure,
        "door_crowding": crowding,
        "redirected": redirected, "never_arrived_agents": {p.split('/')[-1]: straggler_dist[p] for p in never},
        "remaining_series_t_in_out": curve,
        "exit_targets_world": {e: [round(v, 2) for v in p] for e, p in targets.items()},
        "model": "Isaac Sim / IRA characters on a baked NavMesh, behaviour tree Wait(alarm+stagger) -> MoveTo exit; "
                 "local avoidance but no contact or queuing between characters, so door throughput is not modelled "
                 "and door_crowding is DEMAND at the door (crush-risk flag), never a crush prediction; "
                 "exit = first frame within reach_m of the agent's exit target",
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.report)), exist_ok=True)
    json.dump(report, open(a.report, "w"), indent=1)
    print(f"  source: {source}")
    print(f"  people {n}  arrived {len(arrivals)}  never {len(never)}  | t50 {t50}  t90 {t90}  t100 {t100}  (sim span {t_end:.1f} s)")
    print(f"  exits used {dict(used)}  redirected {len(redirected)}  never-arrived min dist to own exit {straggler_dist}")
    print(f"  door crowding: worst {crowding['worst_door']} {crowding['worst_peak_ppm2']} p/m2 ({crowding['worst_peak_people']} people), "
          f"{crowding['s_over_4ppm2_total']} s over 4/m2, {crowding['s_over_6ppm2_total']} s over 6/m2")
    print(f"  report -> {a.report}")


if __name__ == "__main__":
    main()
