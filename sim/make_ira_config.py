"""
make_ira_config.py — from a plan JSON + the venue grid, generate everything one Isaac
rehearsal needs (Phase 2b). Nothing is hand-written per plan.

  stage   assets/hospital/hospital_evac_<plan>.usda
            = hospital.usd (sublayer) + /World/ExitTargets/<E> (all exits, just inside the
              doorway) + /World/NavZones/* NavMeshVolume boxes naming one NavMesh area per
              OPEN exit ("Zone_E3"): every walkable cell goes to its nearest open exit by
              walking distance on the grid — the same routing Layer 1 uses without smoke.
  trees   sim/bt/evacuate_<plan>_<E>.json  (sim/bt/evacuate.json with alarm/stagger/target baked in)
  config  sim/ira/hospital_<plan>.yaml     (one BehaviorTreeCharacterGroup per open exit,
                                            spawned in its zone, size ∝ zone floor area)

Needs pxr, so run inside the Isaac Sim container (no Kit, no GPU):

  bash sim/usdpy.sh sim/make_ira_config.py --plan scenarios/hospital_base_plan.json \
      --venue results/hospital_plan.json --layer1-report results/rehearse_hospital_base.json --people 40
"""
import argparse
import collections
import json
import os
import sys

from pxr import Gf, Sdf, Usd, UsdGeom

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_exit_targets import inside_points  # noqa: E402
from plan import plan_id  # noqa: E402

import re  # noqa: E402

# Top-level prims of the NVIDIA hospital switched off (active = false) in OUR layer; the venue file is untouched.
DOOR_LEAVES = re.compile(r"^(SM_Door|GlassDoor)", re.I)          # leaves only: walls, frames and trims stay
DOLLHOUSE_CUT = re.compile(r"(roof|ceil|Geo_M_Light2|Light_test)", re.I)  # roof, ceilings, fixture + ceiling-panel meshes (none are lights)
DOLLHOUSE_DOME_EXPOSURE = -3.0
# Omniverse Flow fire: the extension's own preset, authored in cm and Y-up. Referenced into this metre,
# Z-up stage it is NOT rescaled, so sizes and accelerations are set here (x0.01 for cm -> m).
# Tuned 2026-10-17 in sim/dev/flow_test*.py: forces x0.1 (x0.01 is lifeless, x1 blows up at 10 cm voxels) and ray-march
# opacity x100 (the preset's 0.05 is per cm). The emitter also emits smoke directly so the plume is dark and readable.
FLOW_FIRE = {"radius": 2.0, "height": 0.6, "cell": 0.1, "gravity": -10.0, "buoyancy_per_temp": 0.6,
             "smoke_per_burn": 10.0, "smoke_fade": 0.05, "emit_smoke": 1.0, "couple_smoke": 2.0,
             "march_attenuation": 5.0, "shadow_attenuation": 4.5}   # the venue's only real light is an untextured 10000-nit dome: with the roof off it floods the floor

CAMERAS = {  # the placement proven on the hospital in Phase 0 (d = h / sin(theta) must overlap distance_range)
    "ceiling_cameras": {"num": 3, "maximum_coverage": {
        "height_range": [2.5, 3.0], "look_down_angle_range": [25.0, 45.0], "focal_length_range": [10.0, 15.0],
        "distance_range": [3.5, 7.0], "grid_resolution": 2.0, "target_coverage_ratio": 0.6}}}


# CCTV demo: six fixed cameras authored in the stage (world metres, Z-up), ceiling height, looking down a little.
# Positions were read off the walkable grid (hospital_plan.json); each one stands on a main-region cell.
CCTV_CAMS = [  # (name, label, (x, y, z), (target x, target y, target z))
    ("CAM01", "LOBBY / MAIN ENTRANCE E1", (8.5, -2.0, 2.7), (-1.25, 0.0, 0.8)),
    ("CAM02", "CENTRAL CORRIDOR",         (-20.0, 10.5, 2.7), (5.0, 9.0, 0.8)),
    ("CAM03", "WEST WING / EXIT E4",      (-36.0, 17.5, 2.7), (-38.25, 9.5, 0.8)),
    ("CAM04", "NORTH-WEST WING / EXIT E2", (-37.0, 25.5, 2.7), (-40.75, 32.5, 0.8)),
    ("CAM05", "EAST WING / EXIT E3",      (24.0, 23.5, 2.7), (21.5, 31.0, 0.8)),
    ("CAM06", "OUTSIDE / MAIN ENTRANCE",  (-1.25, -7.0, 3.2), (-1.25, -1.0, 0.8)),
]
CCTV_FOCAL_MM = 12.0        # ~82 deg horizontal on the 20.955 mm aperture: a wide security lens
CCTV_RESOLUTION = [640, 360]


def zone_labels(venue, open_exits):
    """Nearest open exit for every main-region cell, by 4-connected BFS steps (walking distance)."""
    rows = venue["cells"]
    gy, gx = len(rows), max(len(r) for r in rows)
    main = {(i, j) for j, r in enumerate(rows) for i, c in enumerate(r) if c == "m"}
    label, q = {}, collections.deque()
    for eid in open_exits:                                   # seeds = walkable cells touching the door
        door = [tuple(c) for c in venue["exits"][eid]["cells"]]
        for i, j in door:
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                c = (i + di, j + dj)
                if c in main and c not in label:
                    label[c] = eid
                    q.append(c)
    while q:
        i, j = q.popleft()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            c = (i + di, j + dj)
            if c in main and c not in label:
                label[c] = label[(i, j)]
                q.append(c)
    return label, gx, gy


def rectangles(label, gx, gy, min_cells=2):
    """Greedy cover of each zone by axis-aligned rectangles of cells -> [(eid, i, j, w, h)]."""
    covered, out = set(), []
    for j in range(gy):
        for i in range(gx):
            if (i, j) not in label or (i, j) in covered:
                continue
            L = label[(i, j)]
            w = 1
            while (i + w, j) in label and label[(i + w, j)] == L and (i + w, j) not in covered:
                w += 1
            h = 1
            while all((i + k, j + h) in label and label[(i + k, j + h)] == L and (i + k, j + h) not in covered
                      for k in range(w)):
                h += 1
            for jj in range(j, j + h):
                for ii in range(i, i + w):
                    covered.add((ii, jj))
            if w * h >= min_cells:
                out.append((L, i, j, w, h))
    return out


def author_stage(out_usda, venue_usd, venue, open_exits, rects, zone_h=3.0, cut=(), film_target=None, fire_world=None, cctv=None):
    stage = Usd.Stage.CreateNew(out_usda)
    rel = os.path.relpath(os.path.abspath(venue_usd), os.path.dirname(os.path.abspath(out_usda)))
    stage.GetRootLayer().subLayerPaths.append(rel if rel.startswith(".") else "./" + rel)
    src = Usd.Stage.Open(venue_usd)
    if src.GetDefaultPrim():
        stage.GetRootLayer().defaultPrim = src.GetDefaultPrim().GetName()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.GetStageUpAxis(src))
    UsdGeom.SetStageMetersPerUnit(stage, UsdGeom.GetStageMetersPerUnit(src))

    # Switch off top-level venue prims (door leaves, roof...) with `over` prims in this layer.
    root = src.GetDefaultPrim()
    off = {}
    for rx in cut:
        hits = [c for c in root.GetChildren() if rx.search(c.GetName())]
        for c in hits:
            stage.OverridePrim(c.GetPath()).SetActive(False)
        off[rx.pattern] = len(hits)
    author_stage.switched_off = off
    if fire_world is not None:
        import glob as _glob
        presets = sorted(_glob.glob("/isaac-sim/extscache/omni.flowusd-*/data/presets/Fire/Fire.usda"))
        if not presets:
            raise SystemExit("--flow: Fire preset not found (run inside the Isaac Sim container)")
        fire = stage.DefinePrim("/World/Fire", "Xform")
        fire.GetReferences().AddReference(presets[-1])
        F, V = Sdf.ValueTypeNames.Float, Sdf.ValueTypeNames.Float3
        em = stage.OverridePrim("/World/Fire/flowEmitterSphere")
        em.CreateAttribute("position", V).Set((fire_world[0], fire_world[1], FLOW_FIRE["height"]))
        em.CreateAttribute("radius", F).Set(FLOW_FIRE["radius"])
        em.CreateAttribute("smoke", F).Set(FLOW_FIRE["emit_smoke"])
        em.CreateAttribute("coupleRateSmoke", F).Set(FLOW_FIRE["couple_smoke"])
        stage.OverridePrim("/World/Fire/flowRender/rayMarch").CreateAttribute("attenuation", F).Set(FLOW_FIRE["march_attenuation"])
        stage.OverridePrim("/World/Fire/flowOffscreen/shadow").CreateAttribute("attenuation", F).Set(FLOW_FIRE["shadow_attenuation"])
        stage.OverridePrim("/World/Fire/flowSimulate").CreateAttribute("densityCellSize", F).Set(FLOW_FIRE["cell"])
        adv = stage.OverridePrim("/World/Fire/flowSimulate/advection")
        adv.CreateAttribute("gravity", V).Set((0.0, 0.0, FLOW_FIRE["gravity"]))          # Y-up preset -> Z-up stage
        adv.CreateAttribute("buoyancyPerTemp", F).Set(FLOW_FIRE["buoyancy_per_temp"])
        adv.CreateAttribute("smokePerBurn", F).Set(FLOW_FIRE["smoke_per_burn"])
        stage.OverridePrim("/World/Fire/flowSimulate/advection/smoke").CreateAttribute("fade", F).Set(FLOW_FIRE["smoke_fade"])
    if film_target is not None:
        # IRA's aim_at_targets rejects poses this high, so the overhead camera is authored here and
        # handed to the writer via sensor_prim_list. A USD camera with identity rotation looks down -Z
        # with +Y up: straight down, north at the top of the frame, the building's long (x) axis across.
        h, focal = film_target
        rng = UsdGeom.Imageable(root).ComputeWorldBound(Usd.TimeCode.Default(), "default").ComputeAlignedRange()
        x, y = (rng.GetMin()[0] + rng.GetMax()[0]) / 2.0, (rng.GetMin()[1] + rng.GetMax()[1]) / 2.0   # centre of the whole building
        dome = src.GetPrimAtPath(root.GetPath().AppendChild("DomeLight"))
        if dome and dome.IsValid():
            stage.OverridePrim(dome.GetPath()).CreateAttribute("inputs:exposure", Sdf.ValueTypeNames.Float).Set(DOLLHOUSE_DOME_EXPOSURE)
        UsdGeom.Scope.Define(stage, "/World/FilmCams")
        cam = UsdGeom.Camera.Define(stage, "/World/FilmCams/Overhead")
        cam.AddTranslateOp().Set((x, y, h))
        cam.CreateFocalLengthAttr(focal)
        cam.CreateHorizontalApertureAttr(20.955)
        cam.CreateVerticalApertureAttr(20.955 * 9.0 / 16.0)
        cam.CreateClippingRangeAttr((0.5, 1000.0))

    if cctv:
        # Fixed cameras. A USD camera looks down -Z with +Y up; rotateXYZ (90 - pitch, 0, yaw) makes it look
        # horizontally along +Y (north) for yaw 0, tilted down by `pitch`; yaw is CCW from north.
        import math as _m
        UsdGeom.Scope.Define(stage, "/World/FilmCams")
        for name, _label, (cx, cy, cz), (tx, ty, tz) in cctv:
            dx, dy, dz = tx - cx, ty - cy, tz - cz
            yaw = _m.degrees(_m.atan2(dy, dx)) - 90.0
            pitch = _m.degrees(_m.atan2(-dz, _m.hypot(dx, dy)))
            cam = UsdGeom.Camera.Define(stage, f"/World/FilmCams/{name}")
            cam.AddTranslateOp().Set((cx, cy, cz))
            cam.AddRotateXYZOp().Set((90.0 - pitch, 0.0, yaw))
            cam.CreateFocalLengthAttr(CCTV_FOCAL_MM)
            cam.CreateHorizontalApertureAttr(20.955)
            cam.CreateVerticalApertureAttr(20.955 * 9.0 / 16.0)
            cam.CreateClippingRangeAttr((0.2, 500.0))

    # NavMesh areas must be registered in the stage's navmesh settings as well as named on volumes.
    # values must be typed for the usda text format: float3 colour, double cost (plain tuples do not round-trip)
    areas = {"0": {"areaName": "Walkable", "color": Gf.Vec3f(0.2, 0.8, 1.0), "defaultCost": 1.0},
             "1": {"areaName": "NotWalkable", "color": Gf.Vec3f(1.0, 0.0, 0.0), "defaultCost": -1.0}}
    palette = [(0.9, 0.6, 0.1), (0.1, 0.7, 0.3), (0.6, 0.2, 0.8), (0.1, 0.4, 0.9), (0.8, 0.2, 0.4), (0.3, 0.8, 0.8)]
    for k, eid in enumerate(open_exits):
        areas[str(2 + k)] = {"areaName": f"Zone_{eid}", "color": Gf.Vec3f(*palette[k % len(palette)]), "defaultCost": 1.0}
    cld = stage.GetRootLayer().customLayerData
    cld["navmeshSettings"] = {"areas": areas}
    stage.GetRootLayer().customLayerData = cld

    UsdGeom.Scope.Define(stage, "/World/ExitTargets")
    for eid, (x, y, z) in inside_points(venue).items():
        xf = UsdGeom.Xform.Define(stage, f"/World/ExitTargets/{eid}")
        xf.AddTranslateOp().Set((x, y, z))
        xf.GetPrim().CreateAttribute("grimoires:exit_id", Sdf.ValueTypeNames.String).Set(eid)
        xf.GetPrim().CreateAttribute("grimoires:open", Sdf.ValueTypeNames.Bool).Set(eid in open_exits)

    res, (ox, oy) = venue["res"], venue["origin"]
    UsdGeom.Scope.Define(stage, "/World/NavZones")
    for n, (eid, i, j, w, h) in enumerate(rects):
        prim = stage.DefinePrim(f"/World/NavZones/{eid}_{n:03d}", "NavMeshVolume")
        prim.AddAppliedSchema("NavMeshAreaAPI")
        prim.CreateAttribute("extent", Sdf.ValueTypeNames.Float3Array).Set([(-0.5, -0.5, -0.5), (0.5, 0.5, 0.5)])
        prim.CreateAttribute("nav:area", Sdf.ValueTypeNames.String).Set(f"Zone_{eid}")
        xf = UsdGeom.Xformable(prim)
        xf.AddTranslateOp().Set((ox + (i + w / 2.0) * res, oy + (j + h / 2.0) * res, zone_h / 2.0 - 0.5))
        xf.AddRotateXYZOp().Set((0.0, 0.0, 0.0))
        xf.AddScaleOp().Set((w * res, h * res, zone_h))
    stage.GetRootLayer().Save()


def make_tree(template, out_path, wait_min, wait_max, seed, exit_id):
    """Wait a seeded random time in [wait_min, wait_max] (the departure window), then MoveTo the exit."""
    t = json.loads(json.dumps(template))
    wait, move = t["root"]["children"][0], t["root"]["children"][1]
    wait["modifiers"][0]["portOverrides"].update({"min": float(wait_min), "max": float(max(wait_max, wait_min)), "seed": int(seed)})
    move["portOverrides"]["target"]["value"] = f"/World/ExitTargets/{exit_id}"
    json.dump(t, open(out_path, "w"), indent=4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--venue", required=True, help="grid manifest with exits (mall_plan.py)")
    ap.add_argument("--venue-usd", default="assets/hospital/hospital.usd")
    ap.add_argument("--template", default="sim/bt/evacuate.json")
    ap.add_argument("--layer1-report", help="rehearse.py report of this plan: duration = t100 + margin")
    ap.add_argument("--people", type=int, default=40, help="characters in the twin (IRA has no queuing; ordering is what we compare)")
    ap.add_argument("--duration", type=float, help="simulation seconds (default: Layer-1 t100 + margin, else 180)")
    ap.add_argument("--margin", type=float, default=20.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--min-rect-cells", type=int, default=2)
    ap.add_argument("--measure-only", action="store_true",
                    help="numbers run: one tiny camera, no RGB/boxes (clearance comes from actor_sdg_dump.py's "
                         "position dump); the film gets its own full-camera run")
    ap.add_argument("--fire", default="scenarios/hospital_fire_entrance.json", help="fire scenario (grid-local origin)")
    ap.add_argument("--flow", action="store_true", help="Omniverse Flow fire + smoke at the fire origin (the visual of the same fire)")
    ap.add_argument("--fire-tag", default="_fire", help="name suffix for fire runs (stage, trees, config, output)")
    ap.add_argument("--smoke-closure", action="store_true",
                    help="honour Layer-1 exit closures (corridor_closed_at_s in --layer1-report): people who set off after an "
                         "exit closes go to the nearest other open exit instead")
    ap.add_argument("--keep-doors", action="store_true",
                    help="keep the venue's door leaves (default: switch them off = doors open, as Layer 1 assumes)")
    ap.add_argument("--dollhouse", action="store_true",
                    help="film run: roof/ceilings off, ONE 1280x720 camera ~38-40 m above the building centre looking almost straight down")
    ap.add_argument("--cctv", action="store_true",
                    help="film run: six fixed 640x360 security cameras inside the building (CCTV_CAMS), roof on, doors off")
    ap.add_argument("--film", action="store_true",
                    help="film run: two 1280x720 RGB cameras aimed at exit prims (main entrance + busiest other open exit); "
                         "combine with --duration 60 for a short cut")
    ap.add_argument("--container-root", default="/workspace", help="where the repo is mounted inside the Isaac container")
    ap.add_argument("--root", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    R = lambda *p: os.path.join(root, *p)
    C = lambda *p: "/".join([a.container_root, *p])

    plan = json.load(open(a.plan))
    venue = json.load(open(a.venue))
    pid = plan_id(plan)
    tag = os.path.splitext(os.path.basename(a.plan))[0].replace("hospital_", "").replace("_plan", "")   # base / winner
    open_exits = [e for e in plan["exits_open"] if e in venue["exits"]]
    if not open_exits:
        raise SystemExit("plan opens no exit that exists in the venue")

    label, gx, gy = zone_labels(venue, open_exits)
    share = collections.Counter(label.values())
    rects = rectangles(label, gx, gy, a.min_rect_cells)
    total = sum(share.values())
    nums = {e: int(a.people * share[e] / total) for e in open_exits}
    nums[max(open_exits, key=lambda e: share[e])] += a.people - sum(nums.values())

    fire_tag = a.fire_tag if (a.flow or a.smoke_closure) else ""        # keeps fire runs apart from the certified ones
    suffix_bt = "_smoke" if a.smoke_closure else ""
    cut = ([] if a.keep_doors else [DOOR_LEAVES]) + ([DOLLHOUSE_CUT] if a.dollhouse else [])
    main_cells = [(i, j) for j, r in enumerate(venue["cells"]) for i, ch in enumerate(r) if ch == "m"]
    res_, (ox_, oy_) = venue["res"], venue["origin"]
    centre = (ox_ + (sum(i for i, _ in main_cells) / len(main_cells) + 0.5) * res_,
              oy_ + (sum(j for _, j in main_cells) / len(main_cells) + 0.5) * res_, 0.0)
    stage_rel = f"assets/hospital/hospital_evac_{tag}{'_dollhouse' if a.dollhouse else '_cctv' if a.cctv else ''}{fire_tag}.usda"
    fire = json.load(open(R(a.fire)))
    fire_world = (fire["origin"][0] + ox_, fire["origin"][1] + oy_)
    author_stage(R(stage_rel), R(a.venue_usd), venue, open_exits, rects, cut=cut,
                 film_target=(46.0, 10.0) if a.dollhouse else None,   # 46 m, 10 mm: ~96 x 54 m in 16:9 for a 75 x 47 m building
                 fire_world=fire_world if a.flow else None, cctv=CCTV_CAMS if a.cctv else None)

    # ---- departure groups: (group name, people, spawn zone, wait_min, wait_max, target exit)
    alarm, stagger = float(plan["alarm_delay_s"]), float(plan["stagger_s"])
    closures = {}
    if a.smoke_closure:
        if not a.layer1_report:
            raise SystemExit("--smoke-closure needs --layer1-report (it carries corridor_closed_at_s)")
        closures = {e: t for e, t in json.load(open(R(a.layer1_report))).get("corridor_closed_at_s", {}).items()
                    if t is not None and e in open_exits}
    alt = {}
    for e in closures:
        others = [x for x in open_exits if x != e and x not in closures] or [x for x in open_exits if x != e]
        lab2, _, _ = zone_labels(venue, others)                     # where this zone's people go if e is gone
        votes = collections.Counter(lab2[c] for c, l in label.items() if l == e and c in lab2)
        alt[e] = votes.most_common(1)[0][0]
    specs = []
    for e in open_exits:
        n, lo, hi = nums[e], alarm, alarm + stagger
        if n <= 0:
            continue
        if e in closures:
            tc = closures[e]
            f = min(max((tc - lo) / stagger, 0.0), 1.0) if stagger > 0 else (1.0 if lo < tc else 0.0)
            n_early = int(round(f * n))
            if n_early:
                specs.append((f"evac_{e}", n_early, e, lo, min(tc, hi), e))
            if n - n_early:
                specs.append((f"evac_{e}_to_{alt[e]}", n - n_early, e, max(tc, lo), hi, alt[e]))
        else:
            specs.append((f"evac_{e}", n, e, lo, hi, e))

    template = json.load(open(R(a.template)))
    trees = {}
    for g, n, zone, wmin, wmax, target in specs:
        trees[g] = f"sim/bt/evacuate_{tag}{suffix_bt}_{g.replace('evac_', '')}.json"
        make_tree(template, R(trees[g]), wmin, wmax, a.seed, target)

    duration = a.duration
    if duration is None:
        duration = (json.load(open(a.layer1_report))["t100_s"] + a.margin) if a.layer1_report else 180.0
    if a.measure_only and a.film:
        raise SystemExit("--measure-only and --film are different runs; pick one")
    if a.dollhouse and (a.measure_only or a.film):
        raise SystemExit("--dollhouse is its own film mode; do not combine with --film / --measure-only")
    if a.cctv and (a.measure_only or a.film or a.dollhouse):
        raise SystemExit("--cctv is its own film mode; do not combine with --film / --measure-only / --dollhouse")
    dur_tag = f"{int(a.duration)}s" if a.duration else ""
    suffix = ("_measure" if a.measure_only else "_film" + dur_tag if a.film
              else "_dollhouse" + dur_tag if a.dollhouse else "_cctv" + dur_tag if a.cctv else "") + fire_tag
    out_dir = f"results/ira_hospital_{tag}{suffix}"
    aim = {"height_range": [2.5, 3.0], "look_down_angle_range": [25.0, 45.0],
           "focal_length_range": [10.0, 15.0], "distance_range": [3.5, 7.0]}
    if a.measure_only:
        cameras = {"ceiling_cameras": dict(CAMERAS["ceiling_cameras"], num=1)}
    elif a.dollhouse or a.cctv:
        cameras = None   # camera(s) authored in the stage (author_stage); writer renders them via sensor_prim_list
    elif False:  # previous IRA-placed overhead attempt, kept for reference: aim_at_targets fails at 38 m
        # 74 x 40 m footprint: 10 mm lens (~93 deg horizontal) at ~38-40 m covers it in 16:9.
        # d = h / sin(theta): h 38-40, theta 84-88 -> d 38.0-40.2.  yaw picks which side the camera sits on.
        cameras = {"cam_overhead": {"num": 1, "aim_at_targets": {
            "height_range": [38.0, 40.0], "look_down_angle_range": [84.0, 88.0], "focal_length_range": [10.0, 10.0],
            "distance_range": [38.0, 40.5], "yaw_range": [265.0, 275.0], "targets": ["/World/FilmTargets/Centre"]}}}
    elif a.film:
        # Aim at exit *prims* (Xforms): IRA uses the prim position directly, which sidesteps the
        # character-bbox crash in aim_at_targets. Main entrance first, then the busiest other open exit.
        film_exits = ([e for e in open_exits if e == "E1"] or open_exits[:1])
        others = [e for e in open_exits if e not in film_exits]
        if others:
            film_exits.append(max(others, key=lambda e: nums[e]))
        cameras = {f"cam_{e}": {"num": 1, "aim_at_targets": dict(aim, targets=[f"/World/ExitTargets/{e}"])} for e in film_exits}
    else:
        cameras = CAMERAS
    common = {"output_dir": C(out_dir), "semantic_filter_predicate": "class:character|robot;id:*",
              "camera_params": True, "object_info_bounding_box_3d": True, "start_frame": 20}
    writer = (dict(common, resolution=[320, 180], rgb=False, object_info_bounding_box_2d_tight=False) if a.measure_only   # 3D boxes: cheap cross-check of the dump
              else dict(common, resolution=[1920, 1080], rgb=True, object_info_bounding_box_2d_tight=False,
                        sensor_prim_list=["/World/FilmCams/Overhead"]) if a.dollhouse
              else dict(common, resolution=CCTV_RESOLUTION, rgb=True, object_info_bounding_box_2d_tight=False,
                        object_info_bounding_box_3d=False, sensor_prim_list=[f"/World/FilmCams/{n}" for n, *_ in CCTV_CAMS]) if a.cctv
              else dict(common, resolution=[1280, 720], rgb=True, object_info_bounding_box_2d_tight=not a.film))
    groups = {g: {"num": n, "asset_path": "Isaac/People/Characters/", "spawn_areas": [f"Zone_{zone}"],
                  "behavior_tree": C(trees[g])} for g, n, zone, _, _, _ in specs}
    cfg = {"isaacsim.replicator.agent": {
        "version": "1.6.0", "seed": a.seed, "simulation_duration": float(round(duration, 1)),
        "environment": {"base_stage_asset_path": C(stage_rel)},
        **({"sensor": {"groups": cameras}} if cameras else {}),
        "character": {"groups": groups},
        "replicator": {"writers": {"IRABasicWriter": writer}}}}
    yaml_rel = f"sim/ira/hospital_{tag}{suffix}.yaml"
    _write_yaml(R(yaml_rel), cfg, header=[
        f"# generated by sim/make_ira_config.py — plan {pid} ({os.path.basename(a.plan)}), venue {venue['name']}",
        f"# exits open {open_exits}; alarm {plan['alarm_delay_s']} s + stagger {plan['stagger_s']} s baked into the trees",
        f"# zones (nearest open exit, walking distance): " + ", ".join(f"{e} {share[e] * venue['res'] ** 2:.0f} m2 -> {nums[e]} people" for e in open_exits),
        f"# run: /isaac-sim/python.sh {C('sim/ira/actor_sdg_dump.py')} -c {C(yaml_rel)} --dump {C(out_dir, 'agent_positions.jsonl')}",
        "#      (bind-mount sim/ira/patches/simulation_util.py over the IRA NavMesh util; see that file's header)"])

    print(f"plan {pid}  open exits {open_exits}  people {nums}  duration {duration:.0f} s")
    print(f"zones: {len(label)} cells -> {len(rects)} NavMeshVolume boxes (min {a.min_rect_cells} cells); "
          + ", ".join(f"{e}: {share[e]} cells" for e in open_exits))
    print(f"switched off (top-level prims): {getattr(author_stage, 'switched_off', {})}")
    print(f"wrote {stage_rel}\nwrote {', '.join(trees.values())}\nwrote {yaml_rel}")


def _write_yaml(path, cfg, header):
    """Minimal YAML writer (no PyYAML in the container's bundled python): dicts, lists, scalars."""
    def dump(v, ind):
        pad = "  " * ind
        if isinstance(v, dict):
            return "".join(f"{pad}{k}:" + (f" {scalar(x)}\n" if not isinstance(x, (dict, list)) else "\n" + dump(x, ind + 1))
                           for k, x in v.items())
        if isinstance(v, list):
            if all(not isinstance(x, (dict, list)) for x in v):
                return f"{pad}[{', '.join(scalar(x) for x in v)}]\n"
            return "".join(f"{pad}-\n" + dump(x, ind + 1) for x in v)
        return f"{pad}{scalar(v)}\n"
    def scalar(x):
        if isinstance(x, bool): return "true" if x else "false"
        if isinstance(x, (int, float)): return repr(x)
        s = str(x)
        return f"'{s}'" if any(ch in s for ch in ":#{}[],&*?|<>=!%@`") or s != s.strip() else s
    text = dump(cfg, 0)
    # inline lists inside dict values render on the same line; fix "key:\n  [a, b]" -> "key: [a, b]"
    import re
    text = re.sub(r":\n\s+\[", ": [", text)
    open(path, "w").write("\n".join(header) + "\n" + text)


if __name__ == "__main__":
    main()
