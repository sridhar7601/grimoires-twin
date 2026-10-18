"""flow_test.py — minimal headless Omniverse Flow test: does the Fire preset render, and with which scaling?"""
import os, sys, glob
from isaacsim import SimulationApp
app = SimulationApp({"headless": True, "width": 960, "height": 540})
import carb, omni.usd, omni.timeline, omni.kit.app
from isaacsim.core.utils.extensions import enable_extension
enable_extension("omni.flowusd"); enable_extension("omni.replicator.core")
for _ in range(10): app.update()
s = carb.settings.get_settings()
for k in ("enabled", "rayTracedTranslucencyEnabled", "rayTracedReflectionsEnabled", "pathTracingEnabled"):
    s.set(f"/rtx/flow/{k}", True)
import omni.replicator.core as rep, cv2, numpy as np
from pxr import Usd, UsdGeom, UsdLux, Sdf, Gf
PRESET = sorted(glob.glob("/isaac-sim/extscache/omni.flowusd-*/data/presets/Fire/Fire.usda"))[-1]
OUT = "/workspace/results/flow_test"; os.makedirs(OUT, exist_ok=True)
F, V = Sdf.ValueTypeNames.Float, Sdf.ValueTypeNames.Float3

def run(tag, metres, overrides, cam_pos, look_at, seconds=3.0, dome=(1000.0, 0.0)):
    omni.usd.get_context().new_stage(); app.update()
    st = omni.usd.get_context().get_stage()
    UsdGeom.SetStageUpAxis(st, UsdGeom.Tokens.z if metres else UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(st, 1.0 if metres else 0.01)
    d = UsdLux.DomeLight.Define(st, "/World/Dome"); d.CreateIntensityAttr(dome[0]); d.CreateExposureAttr(dome[1])
    g = UsdGeom.Mesh.Define(st, "/World/Ground"); L = 20 if metres else 2000
    pts = [(-L, -L, 0), (L, -L, 0), (L, L, 0), (-L, L, 0)] if metres else [(-L, 0, -L), (L, 0, -L), (L, 0, L), (-L, 0, L)]
    g.CreatePointsAttr(pts); g.CreateFaceVertexCountsAttr([4]); g.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    fire = st.DefinePrim("/World/Fire", "Xform"); fire.GetReferences().AddReference(PRESET)
    for path, attrs in overrides.items():
        p = st.OverridePrim(f"/World/Fire/{path}")
        for name, (typ, val) in attrs.items():
            p.CreateAttribute(name, typ).Set(val)
    cam = UsdGeom.Camera.Define(st, "/World/Cam"); cam.CreateFocalLengthAttr(18.0)
    xf = UsdGeom.Xformable(cam); m = Gf.Matrix4d().SetLookAt(Gf.Vec3d(*cam_pos), Gf.Vec3d(*look_at), Gf.Vec3d(0, 0, 1) if metres else Gf.Vec3d(0, 1, 0)).GetInverse()
    xf.AddTransformOp().Set(m)
    for _ in range(20): app.update()
    rp = rep.create.render_product("/World/Cam", (960, 540)); ann = rep.AnnotatorRegistry.get_annotator("rgb"); ann.attach([rp])
    tl = omni.timeline.get_timeline_interface(); tl.set_end_time(1e6); tl.play()
    n = int(seconds * 60)
    for i in range(n): app.update()
    rep.orchestrator.step(rt_subframes=4)
    img = ann.get_data()
    tl.stop()
    arr = np.asarray(img)[..., :3][..., ::-1]
    path = f"{OUT}/{tag}.png"; cv2.imwrite(path, arr)
    print(f"[flow_test] {tag}: saved {path} mean={arr.mean():.1f} max={arr.max()} (coloured px={int((np.abs(arr.astype(int) - arr.mean(axis=2, keepdims=True)).max(axis=2) > 25).sum())}, dark px={int((arr.mean(axis=2) < 90).sum())})", flush=True)
    ann.detach(); rp.destroy()

import copy
D = {"flowEmitterSphere": {"position": (V, (0.0, 0.0, 0.6)), "radius": (F, 0.75)},
     "flowSimulate": {"densityCellSize": (F, 0.08)},
     "flowSimulate/advection": {"gravity": (V, (0.0, 0.0, -10.0)), "buoyancyPerTemp": (F, 0.6), "smokePerBurn": (F, 6.0)},
     "flowSimulate/advection/smoke": {"fade": (F, 0.15)}}
def plus(**extra):
    v = copy.deepcopy(D)
    for path, attrs in extra.items():
        v.setdefault(path.replace("__", "/"), {}).update(attrs)
    return v
CAM = dict(cam_pos=(0, -7, 3), look_at=(0, 0, 2), seconds=4.0)
run("V1_D_again",       True, D, **CAM)
run("V2_D_opacity5",    True, plus(flowRender__rayMarch={"attenuation": (F, 5.0)}, flowOffscreen__shadow={"attenuation": (F, 4.5)}), **CAM)
run("V3_D_directsmoke", True, plus(flowEmitterSphere={"smoke": (F, 1.0), "coupleRateSmoke": (F, 2.0)}), **CAM)
run("V4_D_dimdome",     True, D, dome=(10000.0, -3.0), **CAM)
run("V5_D_opacity1",    True, plus(flowRender__rayMarch={"attenuation": (F, 1.0)}, flowOffscreen__shadow={"attenuation": (F, 0.9)}), **CAM)
app.close()
