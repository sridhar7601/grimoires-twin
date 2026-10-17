"""
navmesh_bake.py — bake an Omniverse NavMesh on the mall venue, and save the stage.

This is the gate for simulating Grimoires' crowd IN Isaac: IRA characters walk a
NavMesh, so we need one baked on venue_mall. We add an INCLUDE NavMeshVolume sized
to the venue, bake it, report whether it succeeded, and save a stage that
references the venue + carries the volume, ready for IRA.

  /isaac-sim/python.sh /workspace/sim/navmesh_bake.py \
      --usd /workspace/assets/venue_mall.usdc --out /workspace/results/mall_navmesh.usd
"""
import argparse

try:
    from isaacsim.simulation_app import SimulationApp
except ImportError:
    from isaacsim import SimulationApp  # type: ignore

ap = argparse.ArgumentParser()
ap.add_argument("--usd", required=True)
ap.add_argument("--out", required=True)
args = ap.parse_args()

simulation_app = SimulationApp({"headless": True})

from isaacsim.core.utils.extensions import enable_extension  # noqa: E402

for ext in ("omni.anim.navigation.core", "omni.anim.navigation.bundle"):
    try:
        enable_extension(ext)
    except Exception as e:  # noqa: BLE001
        print(f"[nav] enable {ext}: {e}")
simulation_app.update()

import carb  # noqa: E402
import omni.anim.navigation.core as navcore  # noqa: E402
import omni.kit.commands  # noqa: E402
import omni.usd  # noqa: E402
from pxr import Gf, Sdf, Usd, UsdGeom  # noqa: E402

# reference the venue into a fresh stage so /World is ours to add to
stage = Usd.Stage.CreateInMemory()
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)
world = UsdGeom.Xform.Define(stage, "/World")
stage.SetDefaultPrim(world.GetPrim())
stage.DefinePrim("/World/Venue").GetReferences().AddReference(args.usd)
stage.Export(args.out)

omni.usd.get_context().open_stage(args.out)
for _ in range(80):
    simulation_app.update()
stage = omni.usd.get_context().get_stage()

# venue bounds -> size the include volume to cover the whole floor
cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                          [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy])
rng = cache.ComputeWorldBound(stage.GetPrimAtPath("/World/Venue")).ComputeAlignedRange()
mn, mx = rng.GetMin(), rng.GetMax()
center = (mn + mx) * 0.5
size = mx - mn
print(f"[nav] venue bbox min={tuple(round(v,2) for v in mn)} max={tuple(round(v,2) for v in mx)}")

# create an INCLUDE NavMeshVolume and size it to the venue (+margin)
omni.kit.commands.execute("CreateNavMeshVolumeCommand",
                          parent_prim_path=Sdf.Path("/World"), volume_type=0)
vol = None
for p in stage.Traverse():
    if "NavMeshVolume" in p.GetName() or p.GetTypeName() == "NavMeshVolume":
        vol = p
if vol is None:
    print("[nav] FAIL: NavMeshVolume prim was not created"); simulation_app.close(); raise SystemExit(1)
print(f"[nav] volume prim: {vol.GetPath()} ({vol.GetTypeName()})")

# A NavMesh only needs a thin slab at floor level -- covering the full 35 m height
# (incl. the tower) makes voxel baking blow IRA's 100-frame budget. Floor is ~mn.z.
floor_z = mn[2]
slab_h = 4.0                       # metres above the floor to include
xf = UsdGeom.Xformable(vol)
xf.ClearXformOpOrder()
xf.AddTranslateOp().Set(Gf.Vec3d(center[0], center[1], floor_z + slab_h / 2))
xf.AddScaleOp().Set(Gf.Vec3f(size[0] * 1.1 + 2, size[1] * 1.1 + 2, slab_h))
for _ in range(20):
    simulation_app.update()

# bake and wait
inav = navcore.acquire_interface()
print("[nav] baking...")
try:
    inav.start_navmesh_baking_and_wait()
except Exception as e:  # noqa: BLE001
    print(f"[nav] baking call raised: {e}")
for _ in range(120):            # let the async bake settle regardless
    simulation_app.update()

navmesh = inav.get_navmesh()
ok = navmesh is not None
print(f"[nav] get_navmesh() -> {'OK (navmesh present)' if ok else 'None (bake FAILED)'}")
if ok:
    for attr in ("get_num_triangles", "get_triangle_count", "get_vertices", "get_triangles"):
        if hasattr(navmesh, attr):
            try:
                print(f"[nav]   {attr}: {len(getattr(navmesh, attr)()) if 'get_' in attr else getattr(navmesh, attr)()}")
            except Exception as e:  # noqa: BLE001
                print(f"[nav]   {attr}: {e}")

stage.GetRootLayer().Save()
print(f"[nav] saved stage -> {args.out}  (navmesh {'baked' if ok else 'NOT baked'})")
simulation_app.close()
