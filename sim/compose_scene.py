"""
compose_scene.py — build the mall evacuation scene USD you open in Isaac Sim.

Composes one stage that REFERENCES the venue and a walking human per person,
drives each human along its escape path from the solver tracks (position +
heading as USD time samples), and adds named cameras + lights so you can pick an
angle from the GUI dropdown instead of flying by hand.

Coordinates: tracks are in local grid metres; world = local + grid origin, floor
at z = 0 (the grid was sliced from the venue at scale 1.0). Up axis Z, 1 unit = 1 m.

Pure USD (pxr) -- run inside the container, no Kit, no GPU:
  bash sim/usdpy.sh sim/compose_scene.py \
      --venue-usd /workspace/assets/venue_mall.usdc \
      --human    /workspace/assets/human_walk_loop.usdc \
      --tracks   /workspace/results/tracks_mall_base.json \
      --grid     /workspace/results/mall_plan.json \
      --out      /workspace/results/mall_evac_base.usd \
      --max-people 300
"""
import argparse
import json
import math
import random

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux

ap = argparse.ArgumentParser()
ap.add_argument("--venue-usd", required=True, help="building USD to reference (absolute container path)")
ap.add_argument("--human", required=True, help="looped walking human USD to reference")
ap.add_argument("--tracks", required=True, help="tracks_*.json from rehearse.py")
ap.add_argument("--grid", required=True, help="mall_plan.json (for the grid origin)")
ap.add_argument("--out", required=True)
ap.add_argument("--max-people", type=int, default=300, help="cap crowd size for viewport performance")
ap.add_argument("--fps-scene", type=float, default=24.0, help="stage timeCodesPerSecond")
ap.add_argument("--face-offset-deg", type=float, default=0.0, help="rotate humans if they face the wrong way")
args = ap.parse_args()

tracks_doc = json.load(open(args.tracks))
grid = json.load(open(args.grid))
ox, oy = grid["origin"]
tcps = args.fps_scene

stage = Usd.Stage.CreateInMemory()        # Export at the end so re-runs overwrite cleanly
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)
stage.SetTimeCodesPerSecond(tcps)
stage.SetInterpolationType(Usd.InterpolationTypeLinear)   # smooth motion between 1 Hz samples

world = UsdGeom.Xform.Define(stage, "/World")
stage.SetDefaultPrim(world.GetPrim())

# ---- venue -----------------------------------------------------------------
venue = stage.DefinePrim("/World/Venue")
venue.GetReferences().AddReference(args.venue_usd)

# ---- lights ----------------------------------------------------------------
UsdLux.DomeLight.Define(stage, "/World/Lights/Dome").CreateIntensityAttr(1000.0)
sun = UsdLux.DistantLight.Define(stage, "/World/Lights/Sun")
sun.CreateIntensityAttr(3000.0)
UsdGeom.Xformable(sun.GetPrim()).AddRotateXYZOp().Set(Gf.Vec3f(315.0, 20.0, 0.0))

# ---- crowd -----------------------------------------------------------------
people = tracks_doc["tracks"][: args.max_people]
rng = random.Random(0)
max_tc = 0.0
xs, ys = [], []
placed = 0
for i, tr in enumerate(people):
    rows = tr.get("t") or []
    if not rows:
        continue
    prim = stage.DefinePrim(f"/World/Crowd/Person_{i:04d}")
    # per-person phase offset so the walks don't march in lockstep
    phase = rng.uniform(0.0, tcps)
    prim.GetReferences().AddReference(args.human, layerOffset=Sdf.LayerOffset(phase, 1.0))
    xf = UsdGeom.Xformable(prim)
    t_op = xf.AddTranslateOp()
    r_op = xf.AddRotateZOp()
    yaw = 0.0
    for k, row in enumerate(rows):
        t, x, y = row[0], row[1], row[2]
        tc = t * tcps
        wx, wy = x + ox, y + oy
        t_op.Set(Gf.Vec3d(float(wx), float(wy), 0.0), tc)
        if k + 1 < len(rows):
            nx, ny = rows[k + 1][1], rows[k + 1][2]
            if (nx - x) or (ny - y):
                yaw = math.degrees(math.atan2(ny - y, nx - x))
        r_op.Set(float(yaw + args.face_offset_deg), tc)
        max_tc = max(max_tc, tc)
        xs.append(wx)
        ys.append(wy)
    # vanish once this person is out of the building
    out_t = tr.get("out")
    if out_t is not None:
        vis = UsdGeom.Imageable(prim).CreateVisibilityAttr()
        vis.Set(UsdGeom.Tokens.inherited, 0.0)
        vis.Set(UsdGeom.Tokens.invisible, float(out_t) * tcps + 1.0)
    placed += 1

# ---- cameras (pick these from the GUI dropdown) ----------------------------
cx = (min(xs) + max(xs)) / 2 if xs else ox + 30
cy = (min(ys) + max(ys)) / 2 if ys else oy + 40
span = max(max(xs) - min(xs), max(ys) - min(ys)) if xs else 60.0
fire_wx, fire_wy = 37.0 + ox, 43.0 + oy   # E2 fire origin in world


def add_camera(name, pos, look, flen=24.0):
    cam = UsdGeom.Camera.Define(stage, f"/World/Cameras/{name}")
    cam.CreateFocalLengthAttr(flen)
    cam.CreateClippingRangeAttr(Gf.Vec2f(0.1, 10000.0))
    # aim: build a look-at basis (Z-up world)
    eye = Gf.Vec3d(*pos)
    tgt = Gf.Vec3d(*look)
    fwd = (tgt - eye).GetNormalized()
    up = Gf.Vec3d(0, 0, 1)
    right = Gf.Cross(fwd, up).GetNormalized()
    trueup = Gf.Cross(right, fwd)
    m = Gf.Matrix4d(
        right[0], right[1], right[2], 0,
        trueup[0], trueup[1], trueup[2], 0,
        -fwd[0], -fwd[1], -fwd[2], 0,
        eye[0], eye[1], eye[2], 1,
    )
    UsdGeom.Xformable(cam.GetPrim()).AddTransformOp().Set(m)
    return cam


add_camera("Overview", (cx, cy - span * 1.1, span * 0.9), (cx, cy, 0.0), flen=20.0)
add_camera("EastDoor_Fire", (fire_wx + 18, fire_wy - 18, 14.0), (fire_wx, fire_wy, 1.5), flen=28.0)
add_camera("TopDown", (cx + 0.01, cy, span * 1.4), (cx, cy, 0.0), flen=18.0)
add_camera("GroundEye", (cx, cy - span * 0.55, 2.0), (cx, cy, 1.5), flen=24.0)

stage.SetStartTimeCode(0.0)
stage.SetEndTimeCode(max_tc)
stage.Export(args.out)
print(f"[compose] {placed} people, end_tc={max_tc:.0f} (~{max_tc/tcps:.0f}s), "
      f"origin=({ox},{oy}) -> {args.out}")
print("[compose] cameras: Overview, EastDoor_Fire, TopDown, GroundEye")
