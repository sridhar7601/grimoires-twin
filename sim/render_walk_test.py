"""
render_walk_test.py — prove Isaac plays the UsdSkel walk on human_walk.usdc.

Opens the exported human, lights it, frames it, then renders it at three points
in the walk cycle by advancing the Kit timeline. If the legs differ between the
three PNGs, the skeleton + animation survived the Blender->USD export and Isaac
is skinning it (no omni.anim.people involved).

  /isaac-sim/python.sh /workspace/sim/render_walk_test.py \
      --usd /workspace/assets/human_walk.usdc --out /workspace/renders/walk
"""
import argparse
import os

try:
    from isaacsim.simulation_app import SimulationApp
except ImportError:
    from isaacsim import SimulationApp  # type: ignore

ap = argparse.ArgumentParser()
ap.add_argument("--usd", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--res", default="1000x1200")
ap.add_argument("--subframes", type=int, default=48)
args = ap.parse_args()

W, H = (int(v) for v in args.res.split("x"))
simulation_app = SimulationApp({"headless": True, "renderer": "RayTracedLighting", "width": W, "height": H})

from isaacsim.core.utils.extensions import enable_extension  # noqa: E402

enable_extension("omni.replicator.core")
simulation_app.update()

import numpy as np  # noqa: E402
import omni.replicator.core as rep  # noqa: E402
import omni.timeline  # noqa: E402
import omni.usd  # noqa: E402
from PIL import Image  # noqa: E402
from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux  # noqa: E402

omni.usd.get_context().open_stage(args.usd)
for _ in range(60):
    simulation_app.update()
stage = omni.usd.get_context().get_stage()

# timeline / animation range
tcps = stage.GetTimeCodesPerSecond() or 24.0
t_start = stage.GetStartTimeCode()
t_end = stage.GetEndTimeCode()
print(f"[walk] timeCodesPerSecond={tcps} start={t_start} end={t_end}")

# light
UsdLux.DomeLight.Define(stage, Sdf.Path("/World/Lighting/Dome")).CreateIntensityAttr(1200.0)
sun = UsdLux.DistantLight.Define(stage, Sdf.Path("/World/Lighting/Sun"))
sun.CreateIntensityAttr(3000.0)
UsdGeom.Xformable(sun.GetPrim()).AddRotateXYZOp().Set(Gf.Vec3f(315.0, 20.0, 0.0))
for _ in range(10):
    simulation_app.update()

# frame the character from its bbox
cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                          [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy])
rng = cache.ComputeWorldBound(stage.GetPseudoRoot()).ComputeAlignedRange()
mn, mx = rng.GetMin(), rng.GetMax()
center = (mn + mx) * 0.5
size = mx - mn
diag = size.GetLength() or 2.0
print(f"[walk] bbox min={tuple(round(v,2) for v in mn)} max={tuple(round(v,2) for v in mx)} diag={diag:.2f}")
cx, cy, cz = center[0], center[1], center[2]
cam_pos = (cx + diag * 1.1, cy - diag * 1.1, cz + diag * 0.25)
look = (cx, cy, cz)
cam = rep.create.camera(position=cam_pos, look_at=look, focal_length=28.0)
rp = rep.create.render_product(cam, (W, H))
ann = rep.AnnotatorRegistry.get_annotator("rgb")
ann.attach([rp])

tl = omni.timeline.get_timeline_interface()
tl.set_time_codes_per_second(tcps)
tl.play()

# three poses across the cycle
targets = [t_start, t_start + (t_end - t_start) * 0.33, t_start + (t_end - t_start) * 0.66]
os.makedirs(args.out, exist_ok=True)
written = []
for k, tc in enumerate(targets):
    tl.set_current_time(float(tc) / tcps)
    for _ in range(8):                    # let the skeleton evaluate + skin
        simulation_app.update()
    arr = np.asarray([])
    for _ in range(2):
        rep.orchestrator.step(rt_subframes=args.subframes)
        for _ in range(4):
            simulation_app.update()
        arr = np.asarray(ann.get_data())
        if arr.size:
            break
    if arr.size:
        p = os.path.join(args.out, f"walk_{k}_tc{float(tc):.0f}.png")
        Image.fromarray(arr[..., :3]).save(p)
        written.append(p)
        print(f"[walk] wrote {p}")
    else:
        print(f"[walk] WARN empty frame at timecode {tc}")

print(f"[walk] {len(written)} render(s) -> {args.out}")
simulation_app.close()
