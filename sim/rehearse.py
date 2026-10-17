"""
rehearse.py — one rehearsal: (venue, plan, fire) -> metrics.

Evolved from gameday-twin/sim/bake_egress.py. Same grid, same Dijkstra, same seat
layout, same staggered departures, same USD time-sample output. What changed:
routing is now DYNAMIC. The smoke field (smoke.py) closes cells over time, so
every `replan_s` seconds the distance-to-exit field is recomputed with the
smoke-blocked cells removed, and each person simply steps downhill on the
current field. People slow down in smoke, re-route when a corridor closes, and
are counted as trapped when no route to any open exit remains.

WHAT THIS IS, AND IS NOT
------------------------
It is: routing, throughput, timing, and smoke exposure. Which way people go,
which opening they use, how many clear each opening per second, when each
opening becomes impassable, and how many smoke-seconds each person accumulates.

It is NOT crowd dynamics. People do not push and are not stopped by the person in
front, so they can pass through each other in a queue. The one density-shaped
number it reports, `door_crowding` (crowding.py), is therefore DEMAND -- how many
not-yet-out people stand within 2 m of a door at once -- a crush-RISK flag, never
a crush prediction. Use throughput, timing, exposure and that flag; never read
it as a physical persons-per-square-metre.

The smoke is a simplified front model (see smoke.py), not fire physics.

  python3 sim/rehearse.py --plan base --fire default --seed 42 \
      --report results/rehearse_base.json --tracks results/tracks_base.json
  # add --out results/egress_base.usd inside the Isaac Sim container (needs pxr)
"""
import argparse
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grid import INF, NB, RES, build_grid, cell_of, center, dijkstra, span_cells  # noqa: E402
import smoke as smoke_mod  # noqa: E402
from smoke import SmokeField  # noqa: E402
from plan import load_fire, load_plan, plan_id  # noqa: E402
from crowding import door_crowding  # noqa: E402

MIN_SPEED = 0.3   # m/s floor, as in the template
ALPHA = 4.0       # route cost multiplier is 1 + ALPHA * smoke level: people avoid smoky routes
DENSE_COST = 20.0 # extra multiplier on dense-smoke cells for someone already caught inside


def apply_plan(venue, plan):
    """Deep copy of the venue with gates/exits open exactly as the plan says."""
    v = json.loads(json.dumps(venue))
    for gid in v.get("gates", {}):            # a grid venue (real building) has no gates
        v["gates"][gid]["open"] = gid in plan["gates_open"]
    for eid in v["exits"]:
        v["exits"][eid]["open"] = eid in plan["exits_open"]
    return v


def _seats(venue, n, rng):
    if venue.get("kind") == "grid":
        # Real building: people are spread over the main region ('m' cells), e.g. shoppers.
        seats = [((i + 0.5) * RES, (j + 0.5) * RES)
                 for j, row in enumerate(venue["cells"]) for i, c in enumerate(row) if c == "m"]
        rng.shuffle(seats)
        return seats[:n]
    seats = []
    for s in venue["stands"]:
        x0, x1 = s["x0"] + 1.0, s["x1"] - 1.0
        y0, y1 = venue["stand_y0"] + 1.0, venue["stand_y0"] + venue["stand_depth"] - 1.0
        nx_ = max(1, int((x1 - x0) / 1.1))
        ny_ = max(1, int((y1 - y0) / 1.1))
        for a in range(nx_):
            for b in range(ny_):
                seats.append((x0 + a * 1.1, y0 + b * 1.1))
    rng.shuffle(seats)
    return seats[:n]


def _peak_rate(events, window_s=5.0):
    """Max persons/s through an opening over any `window_s` window."""
    ev = sorted(events)
    best, lo = 0, 0
    for hi in range(len(ev)):
        while ev[hi] - ev[lo] > window_s:
            lo += 1
        best = max(best, hi - lo + 1)
    return round(best / window_s, 2)


def run(venue, plan, fire, seed=42, fps=4.0, max_t=300.0, people=450, walk_speed=1.25,
        replan_s=5.0, exposure_threshold_s=30.0, smoke_overrides=None, out=None, tracks=None,
        venue_usd_file=None, door_flow_pms=1.3, crowd_proto="characters", char_face_deg=0.0):
    """Rehearse once. Returns the report dict (JSON-serialisable)."""
    rng = random.Random(seed)
    v = apply_plan(venue, plan)
    g = build_grid(v)
    blocked, gx, gy = g["blocked"], g["gx"], g["gy"]
    exit_cells, exit_of = g["exit_cells"], g["exit_of"]

    sp = dict(smoke_mod.DEFAULTS)
    sp.update(fire.get("smoke", {}))
    sp.update(smoke_overrides or {})
    sf = SmokeField(g, fire["origin"], **sp)
    k_slow, s_block = sp["k_slow"], sp["s_block"]

    # ---------------------------------------------------------- seat the crowd
    persons = []
    for (sx, sy) in _seats(v, people, rng):
        i, j = cell_of(sx, sy, gx, gy)
        if blocked[j][i]:
            continue
        persons.append({"x": sx, "y": sy, "v": rng.gauss(walk_speed, 0.14),
                        "t0": plan["alarm_delay_s"] + rng.uniform(0, plan["stagger_s"]),
                        "exit": None, "out": None, "exp": 0.0, "dense": 0.0, "no_route": False,
                        "rerouted": False, "prev_side": None})
    N = len(persons)

    # ------------------------------------------------------- opening closures
    bar_y = v["barrier"]["y"] if "barrier" in v else None
    closed_at = {}
    for gid, gd in v.get("gates", {}).items():
        if gd["open"]:
            closed_at[gid] = sf.span_closed_at(span_cells(gd["x0"], gd["x1"], bar_y))
    for eid, ed in v["exits"].items():
        if ed["open"]:
            cells = ([tuple(c) for c in ed["cells"]] if "cells" in ed
                     else span_cells(ed["x0"], ed["x1"], RES * 1.5))
            closed_at[eid] = sf.span_closed_at(cells)

    # ------------------------------------------------------------ walk the crowd
    dt = 1.0 / fps
    nframes = int(max_t * fps) + 1
    gate_counts = {gid: 0 for gid, gd in v.get("gates", {}).items() if gd["open"]}
    exit_counts = {eid: 0 for eid, ed in v["exits"].items() if ed["open"]}
    gate_events = {gid: [] for gid in gate_counts}
    exit_events = {eid: [] for eid in exit_counts}

    # Door flow cap. A doorway passes only so many people per second (SFPE specific
    # flow ~1.3 persons/m/s), so people queue at it instead of passing through one
    # another. door_flow_pms=0 disables the cap (the old, optimistic behaviour).
    def _exit_width(ed):
        if "cells" in ed:
            return v.get("params", {}).get("door_width_m", 3.2)
        return ed["x1"] - ed["x0"]
    exit_width = {eid: _exit_width(ed) for eid, ed in v["exits"].items() if ed["open"]}
    exit_cap = {eid: max(door_flow_pms * w, 1e-6) for eid, w in exit_width.items()}
    exit_next_free = {eid: -1e9 for eid in exit_cap}

    # Door centres (grid-local metres) for the crowding flag; people still inside, every second.
    def _door_centre(ed):
        if "centre" in ed:
            return tuple(ed["centre"])
        if "cells" in ed:
            cs = [center(i, j) for i, j in ed["cells"]]
            return (sum(c[0] for c in cs) / len(cs), sum(c[1] for c in cs) / len(cs))
        return ((ed["x0"] + ed["x1"]) / 2.0, RES * 1.5)
    door_centre = {eid: _door_centre(ed) for eid, ed in v["exits"].items() if ed["open"]}
    crowd_frames = []
    series, positions_per_frame, track_rows = [], [], [[] for _ in persons]
    last_t0 = max((p["t0"] for p in persons), default=0.0)
    dist = owner = dist_b = owner_b = blocked_now = dense_now = None
    next_replan = -1.0
    n_out = 0
    stopped_reason = "all_out"

    for f in range(nframes):
        t = f / fps
        if t >= next_replan:
            # Field A (planning): dense smoke is impassable, lighter smoke makes a
            # route cost more, so people steer around smoke before it closes.
            # Field B (escape): walls only, dense cells very expensive -- used by
            # someone already inside dense smoke to get out along the cheapest path.
            s_now = [[sf.level(i, j, t) for i in range(gx)] for j in range(gy)]
            dense_now = [[sf.is_blocked(i, j, t) for i in range(gx)] for j in range(gy)]
            blocked_now = [[blocked[j][i] or dense_now[j][i] for i in range(gx)] for j in range(gy)]
            w_avoid = [[1.0 + ALPHA * s_now[j][i] for i in range(gx)] for j in range(gy)]
            w_escape = [[w_avoid[j][i] * (DENSE_COST if dense_now[j][i] else 1.0) for i in range(gx)] for j in range(gy)]
            sources_a = [(i, j, exit_of[(i, j)]) for (i, j) in exit_cells if not blocked_now[j][i]]
            sources_b = [(i, j, exit_of[(i, j)]) for (i, j) in exit_cells]
            dist, owner = dijkstra(blocked_now, gx, gy, sources_a, weight=w_avoid)
            dist_b, owner_b = dijkstra(blocked, gx, gy, sources_b, weight=w_escape)
            next_replan = t + replan_s

        frame, still_in, any_mobile = ([None] * N if out else None), 0, False
        whole_second = (f % max(1, int(round(fps))) == 0)
        if whole_second:
            crowd_frames.append((t, [(p["x"], p["y"]) for p in persons if p["out"] is None]))
        for idx, p in enumerate(persons):
            if p["out"] is not None:
                continue
            still_in += 1
            i, j = cell_of(p["x"], p["y"], gx, gy)
            s = sf.level(i, j, t)
            p["exp"] += s * dt
            if out:
                frame[idx] = (p["x"], p["y"])      # stable slot per person (for orientation)
            if tracks and whole_second:
                track_rows[idx].append([round(t, 1), round(p["x"], 2), round(p["y"], 2)])
            if t < p["t0"]:
                continue
            in_dense = dense_now[j][i]
            if in_dense:
                p["dense"] += dt
            # Normal case: walk the planning field. Caught in dense smoke (no value
            # in field A): escape along field B at the speed floor.
            if dist[j][i] < INF:
                field, fowner, fblocked = dist, owner, blocked_now
            else:
                field, fowner, fblocked = dist_b, owner_b, blocked
            d = field[j][i]
            if d == 0.0:                       # standing in the doorway
                e = fowner[j][i]
                if door_flow_pms > 0 and t < exit_next_free[e]:
                    any_mobile = True          # queued at the door, not stuck
                    continue                   # hold at the doorway until it's our turn
                if door_flow_pms > 0:
                    exit_next_free[e] = max(t, exit_next_free[e]) + 1.0 / exit_cap[e]
                p["out"] = t
                n_out += 1
                still_in -= 1
                exit_counts[e] += 1
                exit_events[e].append(t)
                continue
            best, bd = None, d
            for di, dj, _ in NB:
                ni, nj = i + di, j + dj
                if 0 <= ni < gx and 0 <= nj < gy and field[nj][ni] < bd:
                    if di and dj and (fblocked[j][ni] or fblocked[nj][i]):
                        continue
                    bd, best = field[nj][ni], (ni, nj)
            if best is None:
                p["no_route"] = True
                continue
            e = fowner[best[1]][best[0]]
            if p["exit"] is not None and e != p["exit"]:
                p["rerouted"] = True
            p["exit"] = e
            any_mobile = True
            tx, ty = center(*best)
            step = (MIN_SPEED if in_dense else max(p["v"] * (1.0 - k_slow * s), MIN_SPEED)) * dt
            dx, dy = tx - p["x"], ty - p["y"]
            L = math.hypot(dx, dy)
            if L <= step:
                p["x"], p["y"] = tx, ty
            else:
                p["x"] += dx / L * step
                p["y"] += dy / L * step
            if bar_y is None:                    # no barrier row -> no gate counting
                continue
            side = p["y"] > bar_y                # gate crossing: north -> south
            if p["prev_side"] is True and not side:
                for gid, gd in v["gates"].items():
                    if gd["open"] and gd["x0"] - 0.6 <= p["x"] <= gd["x1"] + 0.6:
                        gate_counts[gid] += 1
                        gate_events[gid].append(t)
                        break
            p["prev_side"] = side

        if out:
            positions_per_frame.append(frame)
        if whole_second:
            series.append([round(t, 1), still_in, n_out])
        if still_in == 0 and f > fps:
            nframes = f + 1
            break
        if t > last_t0 + replan_s and not any_mobile and still_in > 0:
            nframes = f + 1
            stopped_reason = "remaining_have_no_route"
            break
    else:
        stopped_reason = "max_t_reached"

    # ------------------------------------------------------------------ metrics
    times = sorted(p["out"] for p in persons if p["out"] is not None)
    t50 = round(times[int(.5 * N)], 1) if len(times) > N * .5 else None
    t90 = round(times[int(.9 * N)], 1) if len(times) > N * .9 else None
    t100 = round(times[-1], 1) if len(times) == N and N else None
    exps = [p["exp"] for p in persons]
    trapped = sum(1 for p in persons if p["out"] is None)
    report = {
        "venue": v["name"], "scenario": "fire_evacuation", "seed": seed,
        "plan": plan, "plan_id": plan_id(plan),
        "fire": {"name": fire.get("name", "custom"), "origin": fire["origin"]},
        "smoke_params": sf.params(),
        "people": N, "open_gates": sorted(gate_counts), "open_exits": sorted(exit_counts),
        "t50_s": t50, "t90_s": t90, "t100_s": t100,
        "trapped": trapped,
        "ever_without_route": sum(1 for p in persons if p["no_route"]),
        "rerouted": sum(1 for p in persons if p["rerouted"]),
        "exposure_mean_s": round(sum(exps) / N, 1) if N else 0.0,
        "exposure_max_s": round(max(exps), 1) if exps else 0.0,
        "exposure_threshold_s": exposure_threshold_s,
        "n_over_exposure_threshold": sum(1 for e in exps if e > exposure_threshold_s),
        "n_in_dense_smoke": sum(1 for p in persons if p["dense"] > 0),
        "dense_smoke_max_s": round(max((p["dense"] for p in persons), default=0.0), 1),
        "dense_smoke_total_person_s": round(sum(p["dense"] for p in persons), 1),
        "routing": {"alpha_avoid": ALPHA, "dense_cost_factor": DENSE_COST, "min_speed_ms": MIN_SPEED,
                    "note": "route cost x (1 + alpha*s); dense cells impassable for planning; someone "
                            "already inside dense smoke walks out at min_speed along the cheapest path"},
        "door_flow_pms": door_flow_pms,
        "exit_capacity_ps": {k: round(c, 2) for k, c in exit_cap.items()},
        "gate_throughput_total": gate_counts, "exit_throughput_total": exit_counts,
        "door_crowding": door_crowding(crowd_frames, door_centre, 1.0),
        "gate_peak_rate_ps": {k: _peak_rate(ev) for k, ev in gate_events.items()},
        "exit_peak_rate_ps": {k: _peak_rate(ev) for k, ev in exit_events.items()},
        "corridor_closed_at_s": closed_at,
        "sim_span_s": round((nframes - 1) / fps, 1), "fps": fps, "replan_s": replan_s,
        "stopped": stopped_reason,
        "walk_speed_mean_ms": walk_speed,
        "remaining_series_t_in_out": series,
        "model": ("dynamic smoke-aware egress on a 0.5 m grid with staggered departures; the "
                  "route field is recomputed every replan_s, smoky routes cost more and dense "
                  "smoke is avoided; speed falls with smoke level; positions baked as USD time "
                  "samples. Routing, throughput, "
                  "timing and exposure -- people queue at the SFPE door cap but do not collide, so "
                  "door_crowding is DEMAND at the door (crush-risk flag), never a crush prediction. "
                  "Smoke is a simplified front model, not fire physics."),
    }

    # ------------------------------------------------------------------ write USD
    if out:
        # Imported here, not at the top, so the routing and metrics run on any
        # machine with plain Python -- pxr only exists inside Isaac Sim.
        from pxr import Gf, Usd, UsdGeom, UsdLux

        stage = Usd.Stage.CreateNew(out)
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)
        world = UsdGeom.Xform.Define(stage, "/World")
        stage.SetDefaultPrim(world.GetPrim())
        stage.SetStartTimeCode(0)
        stage.SetEndTimeCode(nframes - 1)
        stage.SetTimeCodesPerSecond(fps)
        stage.SetFramesPerSecond(fps)
        venue_usd = os.path.splitext(out)[0] + ".venue.usd"
        if v.get("kind") == "grid" and venue_usd_file:
            # The real building, placed exactly as mall_plan.py sliced it: scaled, then
            # shifted so its grid origin sits at (0, 0) -- the sim's coordinate frame.
            vx = UsdGeom.Xform.Define(stage, "/World/Venue")
            vx.AddTranslateOp().Set(Gf.Vec3d(-v["origin"][0], -v["origin"][1], 0.0))
            vx.AddScaleOp().Set(Gf.Vec3f(v["scale"], v["scale"], v["scale"]))
            vx.GetPrim().GetReferences().AddReference(os.path.abspath(venue_usd_file))
        elif os.path.exists(venue_usd):
            ov = stage.OverridePrim("/World/Venue")
            ov.GetReferences().AddReference(os.path.abspath(venue_usd), "/World/Venue")
        # ---- crowd prototypes: NVIDIA People characters (varied), capsule fallback ----
        UsdGeom.Scope.Define(stage, "/World/Crowd/proto")
        proto_paths = []
        if crowd_proto == "characters":
            root = ("https://omniverse-content-production.s3-us-west-2.amazonaws.com"
                    "/Assets/Isaac/6.0/Isaac/People/Characters")
            chars = ["F_Business_02/F_Business_02.usd",
                     "original_female_adult_business_02/female_adult_business_02.usd",
                     "original_male_adult_medical_01/male_adult_medical_01.usd",
                     "original_female_adult_police_01/female_adult_police_01.usd",
                     "original_male_adult_construction_01/male_adult_construction_01.usd"]
            for k, rel in enumerate(chars):
                px = UsdGeom.Xform.Define(stage, f"/World/Crowd/proto/c{k}")
                px.GetPrim().GetReferences().AddReference(f"{root}/{rel}")
                proto_paths.append(px.GetPath())
        if not proto_paths:                            # capsule (crowd_proto == "capsule")
            body = UsdGeom.Capsule.Define(stage, "/World/Crowd/proto/person")
            body.CreateRadiusAttr(0.22)
            body.CreateHeightAttr(1.25)
            body.CreateAxisAttr("Z")
            body.CreateDisplayColorAttr([Gf.Vec3f(0.90, 0.32, 0.20)])
            UsdGeom.Xformable(body).AddTranslateOp().Set(Gf.Vec3d(0, 0, 0.85))
            proto_paths.append(body.GetPath())

        inst = UsdGeom.PointInstancer.Define(stage, "/World/Crowd")
        inst.CreatePrototypesRel().SetTargets(proto_paths)
        pos_attr = inst.CreatePositionsAttr()
        ori_attr = inst.CreateOrientationsAttr()
        proto_rng = random.Random(seed ^ 0x5151)
        proto_of = [proto_rng.randrange(len(proto_paths)) for _ in range(N)]
        inst.CreateProtoIndicesAttr().Set(proto_of)    # fixed: each person keeps one look
        face = math.radians(char_face_deg)
        last_xy = [None] * N
        last_q = [Gf.Quath(1, 0, 0, 0) for _ in range(N)]
        PARK = Gf.Vec3f(0, 0, -50.0)
        for fi, fr in enumerate(positions_per_frame):
            pts, oris = [], []
            for idx in range(N):
                xy = fr[idx]
                if xy is None:                          # exited / not yet moving -> park, keep facing
                    pts.append(PARK)
                    oris.append(last_q[idx])
                    continue
                pts.append(Gf.Vec3f(xy[0], xy[1], 0.0))
                prev = last_xy[idx]
                if prev is not None:
                    dx, dy = xy[0] - prev[0], xy[1] - prev[1]
                    if dx * dx + dy * dy > 1e-6:         # face the way they walk (forward = +Y)
                        h = (math.atan2(dy, dx) - math.pi / 2 + face) / 2.0
                        last_q[idx] = Gf.Quath(math.cos(h), 0.0, 0.0, math.sin(h))
                last_xy[idx] = xy
                oris.append(last_q[idx])
            pos_attr.Set(pts, Usd.TimeCode(fi))
            ori_attr.Set(oris, Usd.TimeCode(fi))
        UsdLux.DomeLight.Define(stage, "/World/EgressLight").CreateIntensityAttr(900.0)
        fire_ball = UsdGeom.Sphere.Define(stage, "/World/FireOrigin")   # where the smoke starts
        fire_ball.CreateRadiusAttr(1.0)
        fire_ball.CreateDisplayColorAttr([Gf.Vec3f(1.0, 0.15, 0.0)])
        UsdGeom.Xformable(fire_ball).AddTranslateOp().Set(Gf.Vec3d(fire["origin"][0], fire["origin"][1], 1.0))
        stage.GetRootLayer().Save()
        report["usd"] = out

    # ------------------------------------------------------ compact tracks (replay)
    if tracks:
        with open(tracks, "w") as fh:
            json.dump({"venue": v["name"], "seed": seed, "people": N, "plan_id": report["plan_id"],
                       "fire": report["fire"], "fps_tracks": 1,
                       "tracks": [{"t": rows, "exit": p["exit"], "out": p["out"]}
                                  for rows, p in zip(track_rows, persons)]},
                      fh, separators=(",", ":"))
        report["tracks"] = tracks
    return report


def main():
    from venue_def import VENUE
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", help="venue manifest .json (default: venue_def.VENUE)")
    ap.add_argument("--plan", default="base", help="'base' or a plan .json")
    ap.add_argument("--fire", default="default", help="a FIRES name or a fire .json")
    ap.add_argument("--origin", help="override fire origin x,y (metres)")
    ap.add_argument("--speed", type=float, help="override smoke spread speed m/s (0 = no smoke)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--fps", type=float, default=12.0)
    ap.add_argument("--max-t", type=float, default=300.0)
    ap.add_argument("--people", type=int, default=450)
    ap.add_argument("--replan", type=float, default=5.0)
    ap.add_argument("--exposure-threshold", type=float, default=30.0)
    ap.add_argument("--out", help="output .usd (needs pxr; omit to skip)")
    ap.add_argument("--tracks")
    ap.add_argument("--venue-usd", help="grid venues only: the building USD to render under the crowd")
    ap.add_argument("--door-flow", type=float, default=1.3,
                    help="max persons per metre of door per second (SFPE ~1.3); 0 = unlimited (old behaviour)")
    ap.add_argument("--crowd", choices=["characters","capsule"], default="characters",
                    help="what to draw per person in the USD: NVIDIA People characters or a capsule")
    ap.add_argument("--char-face", type=float, default=0.0, help="degrees to rotate characters if they face the wrong way")
    ap.add_argument("--report", required=True)
    a = ap.parse_args()

    venue = json.load(open(a.venue)) if a.venue else json.loads(json.dumps(VENUE))
    plan, fire = load_plan(a.plan), load_fire(a.fire)
    if a.origin:
        fire["origin"] = [float(x) for x in a.origin.split(",")]
    overrides = {"spread_speed_ms": a.speed} if a.speed is not None else None
    r = run(venue, plan, fire, seed=a.seed, fps=a.fps, max_t=a.max_t, people=a.people,
            replan_s=a.replan, exposure_threshold_s=a.exposure_threshold,
            smoke_overrides=overrides, out=a.out, tracks=a.tracks, venue_usd_file=a.venue_usd,
            door_flow_pms=a.door_flow, crowd_proto=a.crowd, char_face_deg=a.char_face)
    os.makedirs(os.path.dirname(os.path.abspath(a.report)), exist_ok=True)
    json.dump(r, open(a.report, "w"), indent=1)
    print(f"plan {r['plan_id']}  fire {r['fire']['name']}@{r['fire']['origin']}  people {r['people']}  "
          f"({r['sim_span_s']} s simulated, stopped: {r['stopped']})")
    sec = lambda v: "—" if v is None else f"{v}s"  # noqa: E731
    print(f"  cleared: 50% {sec(r['t50_s'])} | 90% {sec(r['t90_s'])} | 100% {sec(r['t100_s'])}   "
          f"trapped {r['trapped']}   through dense smoke {r['n_in_dense_smoke']} (max {r['dense_smoke_max_s']}s)")
    print(f"  gates {r['gate_throughput_total']}  peak/s {r['gate_peak_rate_ps']}")
    print(f"  exits {r['exit_throughput_total']}  peak/s {r['exit_peak_rate_ps']}")
    print(f"  closed at: {r['corridor_closed_at_s']}   rerouted {r['rerouted']}")
    print(f"  exposure mean {r['exposure_mean_s']}s max {r['exposure_max_s']}s  "
          f"over {r['exposure_threshold_s']}s: {r['n_over_exposure_threshold']}")
    print(f"  report -> {a.report}" + (f"   tracks -> {a.tracks}" if a.tracks else "")
          + (f"   usd -> {a.out}" if a.out else ""))


if __name__ == "__main__":
    main()
