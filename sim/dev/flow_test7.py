"""flow_test6.py — ONE fresh stage (as in an IRA run): does Flow draw after a warm-up, and how does the plume look from 46 m?"""
import os, glob, sys
STRAT = sys.argv[1] if len(sys.argv) > 1 else "launchargs"
from isaacsim import SimulationApp
FLOW_ARGS = ["--enable", "omni.flowusd"] + [f"--/rtx/flow/{k}=true" for k in ("enabled", "rayTracedTranslucencyEnabled", "rayTracedReflectionsEnabled", "pathTracingEnabled")]
app = SimulationApp({"headless": True, "width": 960, "height": 540, "extra_args": FLOW_ARGS if STRAT == "launchargs" else []})
print(f"[flow_test] strategy={STRAT}", flush=True)
import carb, omni.usd, omni.timeline
from isaacsim.core.utils.extensions import enable_extension
enable_extension("omni.flowusd"); enable_extension("omni.replicator.core")
for _ in range(10): app.update()
s = carb.settings.get_settings()
for k in ("enabled", "rayTracedTranslucencyEnabled", "rayTracedReflectionsEnabled", "pathTracingEnabled"):
    s.set(f"/rtx/flow/{k}", True)
import omni.replicator.core as rep, cv2, numpy as np
from pxr import UsdGeom, UsdLux, Sdf, Gf
PRESET = sorted(glob.glob("/isaac-sim/extscache/omni.flowusd-*/data/presets/Fire/Fire.usda"))[-1]
OUT = "/workspace/results/flow_test"; os.makedirs(OUT, exist_ok=True)
F, V = Sdf.ValueTypeNames.Float, Sdf.ValueTypeNames.Float3
st = omni.usd.get_context().get_stage()
UsdGeom.SetStageUpAxis(st, UsdGeom.Tokens.z); UsdGeom.SetStageMetersPerUnit(st, 1.0)
d = UsdLux.DomeLight.Define(st, "/World/Dome"); d.CreateIntensityAttr(10000); d.CreateExposureAttr(-3.0)
g = UsdGeom.Mesh.Define(st, "/World/Ground"); L = 40
g.CreatePointsAttr([(-L, -L, 0), (L, -L, 0), (L, L, 0), (-L, L, 0)]); g.CreateFaceVertexCountsAttr([4]); g.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
fire = st.DefinePrim("/World/Fire", "Xform"); fire.GetReferences().AddReference(PRESET)
OV = {"flowEmitterSphere": {"position": (V, (0.0, 0.0, 0.6)), "radius": (F, 1.5), "smoke": (F, 1.0), "coupleRateSmoke": (F, 2.0)},
      "flowSimulate": {"densityCellSize": (F, 0.1)},
      "flowSimulate/advection": {"gravity": (V, (0.0, 0.0, -10.0)), "buoyancyPerTemp": (F, 0.6), "smokePerBurn": (F, 10.0)},
      "flowSimulate/advection/smoke": {"fade": (F, 0.08)},
      "flowRender/rayMarch": {"attenuation": (F, 5.0)}, "flowOffscreen/shadow": {"attenuation": (F, 4.5)}}
for path, attrs in OV.items():
    p = st.OverridePrim(f"/World/Fire/{path}")
    for name, (typ, val) in attrs.items():
        p.CreateAttribute(name, typ).Set(val)
def cam(path, pos, look, focal):
    c = UsdGeom.Camera.Define(st, path); c.CreateFocalLengthAttr(focal)
    c.CreateHorizontalApertureAttr(20.955); c.CreateVerticalApertureAttr(20.955 * 9 / 16)
    UsdGeom.Xformable(c).AddTransformOp().Set(Gf.Matrix4d().SetLookAt(Gf.Vec3d(*pos), Gf.Vec3d(*look), Gf.Vec3d(0, 0, 1)).GetInverse())
cam("/World/Close", (0, -12, 4), (0, 0, 3), 18.0)
cam("/World/Over", (0.0, 0.0, 46.0), (0.0, 0.01, 0.0), 10.0)
for _ in range(20): app.update()
if STRAT == "toggle":                                   # make the renderer re-read Flow's settings after the stage exists
    for v in (False, True):
        s.set("/rtx/flow/enabled", v)
        for _ in range(10): app.update()
rps = {n: rep.create.render_product(p, (960, 540)) for n, p in (("close", "/World/Close"), ("over46m", "/World/Over"))}
anns = {}
for n, rp in rps.items():
    a = rep.AnnotatorRegistry.get_annotator("rgb"); a.attach([rp]); anns[n] = a
tl = omni.timeline.get_timeline_interface(); tl.set_end_time(1e6); tl.play()
t, step = 0.0, 1.0 / 60
for target in (10, 20):
    while t < target:
        app.update(); t += step
    rep.orchestrator.step(rt_subframes=2)
    for n, a in anns.items():
        arr = np.asarray(a.get_data())[..., :3][..., ::-1]
        cv2.imwrite(f"{OUT}/S_{STRAT}_{n}_{target:02d}s.png", arr)
        col = int((np.abs(arr.astype(int) - arr.mean(axis=2, keepdims=True)).max(axis=2) > 25).sum()); dark = int((arr.mean(axis=2) < 90).sum())
        print(f"[flow_test] t={target:2d}s {n:8s} coloured px={col:6d} dark px={dark:6d}", flush=True)
app.close()
