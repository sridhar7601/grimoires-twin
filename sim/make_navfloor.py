"""
make_navfloor.py — a clean low-poly navigation floor from the walkability grid.

The Sketchfab mall is a lovely render mesh but a terrible navigation mesh (slow to
bake, sparse/unnavigable). So we build a separate, clean floor: one flat quad per
WALKABLE cell of mall_plan.json (holes where planters/walls are), plus lights, the
exits as green markers, named exit prims to target later, and a thin NavMeshVolume.
IRA bakes a perfect NavMesh on this in seconds and characters walk the real layout.

World coords match the grid: world = (ox + i*res, oy + j*res), floor at z=0.
Pure USD (pxr) -- run via usdpy.sh, no Kit, no GPU:
  bash sim/usdpy.sh sim/make_navfloor.py --grid results/mall_plan.json \
       --out results/mall_navfloor.usd
"""
import argparse
import json

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux

ap = argparse.ArgumentParser()
ap.add_argument("--grid", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--z", type=float, default=0.0, help="floor height")
args = ap.parse_args()

g = json.load(open(args.grid))
ox, oy = g["origin"]
res = g["res"]
gx, gy = g["gx"], g["gy"]
cells = g["cells"]           # rows south->north: 'm' main-walkable, '.' walkable, '#' blocked, ' ' no floor
exits = g.get("exits", {})
Z = args.z

stage = Usd.Stage.CreateInMemory()
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)
world = UsdGeom.Xform.Define(stage, "/World")
stage.SetDefaultPrim(world.GetPrim())


def quad_mesh(path, cell_list, rgb):
    """One Mesh made of a flat quad per (i, j) cell."""
    pts, counts, idx = [], [], []
    for i, j in cell_list:
        x0, y0 = ox + i * res, oy + j * res
        x1, y1 = x0 + res, y0 + res
        b = len(pts)
        pts += [Gf.Vec3f(x0, y0, Z), Gf.Vec3f(x1, y0, Z), Gf.Vec3f(x1, y1, Z), Gf.Vec3f(x0, y1, Z)]
        idx += [b, b + 1, b + 2, b + 3]
        counts.append(4)
    m = UsdGeom.Mesh.Define(stage, path)
    m.CreatePointsAttr(pts)
    m.CreateFaceVertexCountsAttr(counts)
    m.CreateFaceVertexIndicesAttr(idx)
    m.CreateDisplayColorAttr([Gf.Vec3f(*rgb)])
    m.CreateDoubleSidedAttr(True)
    return m


# walkable cells -> floor ; exit cells collected separately for a green overlay
exit_cells = {tuple(c) for e in exits.values() for c in e.get("cells", [])}
floor, green = [], []
for j, row in enumerate(cells):
    for i, ch in enumerate(row):
        if ch in ("m", "."):
            (green if (i, j) in exit_cells else floor).append((i, j))
for i, j in exit_cells:            # make sure exit wall-cells show even if blocked
    if (i, j) not in green:
        green.append((i, j))

quad_mesh("/World/NavFloor", floor, (0.82, 0.82, 0.78))
if green:
    quad_mesh("/World/Exits", green, (0.1, 0.8, 0.2))
print(f"[navfloor] floor cells={len(floor)}  exit cells={len(green)}  grid={gx}x{gy}  origin=({ox},{oy})")

# named exit prims (targets for evacuation later)
for eid, e in exits.items():
    cw = e.get("centre_world") or [ox, oy]
    x = UsdGeom.Xform.Define(stage, f"/World/ExitTargets/{eid}")
    x.AddTranslateOp().Set(Gf.Vec3d(float(cw[0]), float(cw[1]), Z))

# lights
UsdLux.DomeLight.Define(stage, "/World/Lights/Dome").CreateIntensityAttr(1200.0)
sun = UsdLux.DistantLight.Define(stage, "/World/Lights/Sun")
sun.CreateIntensityAttr(3000.0)
UsdGeom.Xformable(sun.GetPrim()).AddRotateXYZOp().Set(Gf.Vec3f(315.0, 20.0, 0.0))

# thin NavMeshVolume slab over the floor
cx, cy = ox + gx * res / 2, oy + gy * res / 2
vol = stage.DefinePrim("/World/NavMeshVolume", "NavMeshVolume")
xf = UsdGeom.Xformable(vol)
xf.AddTranslateOp().Set(Gf.Vec3d(cx, cy, Z + 2.0))
xf.AddScaleOp().Set(Gf.Vec3f(gx * res + 4, gy * res + 4, 4.0))

stage.SetStartTimeCode(0)
stage.SetEndTimeCode(0)
stage.Export(args.out)
print(f"[navfloor] wrote {args.out}")
