"""
render_venue.py — first RTX render of the venue out of Isaac Sim.

Stage 0 of the Isaac/Omniverse track: prove the box actually renders. It opens
the venue USD, lights it (the asset may ship unlit, which renders black), frames
it from its own world bounding box (so it works whatever the model's scale or
up-axis), and writes a top-down plan view plus an oblique view as PNGs.

Boot sequence and the replicator render path are copied from
gameday-twin/sim/render_views.py (omni.replicator.core must be enabled
explicitly -- in a bare SimulationApp rep.orchestrator is otherwise None).

  # inside the Isaac Sim container, project mounted at /workspace:
  /isaac-sim/python.sh /workspace/sim/render_venue.py \
      --usd /workspace/assets/venue_mall.usdc --out /workspace/renders
"""
import argparse
import os

try:
    from isaacsim.simulation_app import SimulationApp
except ImportError:
    from isaacsim import SimulationApp  # type: ignore

ap = argparse.ArgumentParser()
ap.add_argument("--usd", required=True, help="venue USD to render")
ap.add_argument("--out", required=True, help="output directory for PNGs")
ap.add_argument("--res", default="1600x900")
ap.add_argument("--subframes", type=int, default=48, help="RTX accumulation per frame")
args = ap.parse_args()

W, H = (int(v) for v in args.res.split("x"))
simulation_app = SimulationApp({"headless": True, "renderer": "RayTracedLighting", "width": W, "height": H})

from isaacsim.core.utils.extensions import enable_extension  # noqa: E402

enable_extension("omni.replicator.core")
simulation_app.update()

import numpy as np  # noqa: E402
import omni.replicator.core as rep  # noqa: E402
import omni.usd  # noqa: E402
from PIL import Image  # noqa: E402
from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux  # noqa: E402

# --- open the stage ---------------------------------------------------------
omni.usd.get_context().open_stage(args.usd)
for _ in range(60):                       # let the stage + materials settle
    simulation_app.update()
stage = omni.usd.get_context().get_stage()

# --- light it (the mall asset ships no lights -> otherwise a black frame) ----
UsdLux.DomeLight.Define(stage, Sdf.Path("/World/Lighting/Dome")).CreateIntensityAttr(1000.0)
sun = UsdLux.DistantLight.Define(stage, Sdf.Path("/World/Lighting/Sun"))
sun.CreateIntensityAttr(3000.0)
sun.CreateAngleAttr(0.53)
UsdGeom.Xformable(sun.GetPrim()).AddRotateXYZOp().Set(Gf.Vec3f(315.0, 15.0, 0.0))
for _ in range(10):
    simulation_app.update()

# --- frame the scene from its own world bounding box ------------------------
cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                          [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy])
rng = cache.ComputeWorldBound(stage.GetPseudoRoot()).ComputeAlignedRange()
mn, mx = rng.GetMin(), rng.GetMax()
center = (mn + mx) * 0.5
size = mx - mn
diag = size.GetLength() or 10.0
print(f"[render_venue] bbox min={tuple(round(v,2) for v in mn)} "
      f"max={tuple(round(v,2) for v in mx)} center={tuple(round(v,2) for v in center)} diag={diag:.2f}")

up = UsdGeom.GetStageUpAxis(stage)        # 'Y' or 'Z'
cx, cy, cz = center[0], center[1], center[2]
if up == UsdGeom.Tokens.y:                # Y-up asset (common for imported models)
    plan = (cx + diag * 0.05, cy + diag * 0.9, cz)   # slight offset: a dead-vertical cam is degenerate
    obliq = (cx - diag * 0.7, cy + diag * 0.5, cz - diag * 0.7)
else:                                     # Z-up (Omniverse/Isaac default)
    plan = (cx + diag * 0.05, cy, cz + diag * 0.9)   # slight offset: a dead-vertical cam is degenerate
    obliq = (cx - diag * 0.7, cy - diag * 0.7, cz + diag * 0.5)
look = (cx, cy, cz)

views = [("plan", plan, 16.0), ("oblique", obliq, 20.0)]

# --- render each view -------------------------------------------------------
os.makedirs(args.out, exist_ok=True)
written = []
for name, pos, flen in views:
    cam = rep.create.camera(position=pos, look_at=look, focal_length=flen)
    rp = rep.create.render_product(cam, (W, H))
    ann = rep.AnnotatorRegistry.get_annotator("rgb")
    ann.attach([rp])
    arr = np.asarray([])
    for attempt in range(2):              # the first render product often needs a warm-up step
        rep.orchestrator.step(rt_subframes=args.subframes)
        for _ in range(4):                # drain so the annotator holds a full frame
            simulation_app.update()
        arr = np.asarray(ann.get_data())
        if arr.size:
            break
    if arr.size:
        path = os.path.join(args.out, f"venue_{name}.png")
        Image.fromarray(arr[..., :3]).save(path)
        written.append(path)
        print(f"[render_venue] wrote {path}")
    else:
        print(f"[render_venue] WARN empty frame for {name}")
    ann.detach()
    rp.destroy()

print(f"[render_venue] {len(written)} render(s) -> {args.out}")
simulation_app.close()
