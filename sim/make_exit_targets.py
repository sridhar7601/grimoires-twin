"""
make_exit_targets.py — author the evacuation stage: the venue USD as a sublayer plus
one Xform per exit, /World/ExitTargets/<E>, placed just INSIDE the doorway on the
walkable floor (an IRA MoveTo target must be reachable on the NavMesh; the exit
cells themselves are wall cells in the grid).

Needs pxr, so run inside the Isaac Sim container (no Kit, no GPU):

  bash sim/usdpy.sh sim/make_exit_targets.py --venue results/hospital_plan.json \
      --usd assets/hospital/hospital.usd --out assets/hospital/hospital_evac.usda
"""
import argparse
import json
import math
import os


def inside_points(venue, inset_m=1.0):
    """Per exit: the walkable main-region point `inset_m` inside the doorway, world metres."""
    res, (ox, oy) = venue["res"], venue["origin"]
    rows = venue["cells"]
    gy, gx = len(rows), max(len(r) for r in rows)
    main = {(i, j) for j, r in enumerate(rows) for i, c in enumerate(r) if c == "m"}
    out = {}
    for eid, e in venue["exits"].items():
        door = [tuple(c) for c in e["cells"]]
        adj = {(i + di, j + dj) for i, j in door for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1))} & main
        if not adj:
            raise SystemExit(f"{eid}: no walkable cell touches the door")
        dx, dy = (sum(i for i, _ in door) / len(door), sum(j for _, j in door) / len(door))
        ax, ay = (sum(i for i, _ in adj) / len(adj), sum(j for _, j in adj) / len(adj))
        vx, vy = ax - dx, ay - dy                       # inward direction (cells)
        n = math.hypot(vx, vy) or 1.0
        tx, ty = ax + vx / n * inset_m / res, ay + vy / n * inset_m / res
        i, j = min(main, key=lambda c: (c[0] - tx) ** 2 + (c[1] - ty) ** 2)   # snap to walkable
        out[eid] = (ox + (i + 0.5) * res, oy + (j + 0.5) * res, 0.0)
    return out


def main():
    from pxr import Sdf, Usd, UsdGeom   # only stage authoring needs USD; inside_points() stays importable anywhere

    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", required=True, help="grid manifest from mall_plan.py (needs exits)")
    ap.add_argument("--usd", required=True, help="the venue USD; sublayered, paths unchanged")
    ap.add_argument("--out", required=True, help="output .usda (same folder as --usd keeps relative refs valid)")
    ap.add_argument("--inset", type=float, default=1.0, help="metres inside the doorway")
    a = ap.parse_args()

    venue = json.load(open(a.venue))
    pts = inside_points(venue, a.inset)

    stage = Usd.Stage.CreateNew(a.out)
    rel = os.path.relpath(os.path.abspath(a.usd), os.path.dirname(os.path.abspath(a.out)))
    stage.GetRootLayer().subLayerPaths.append("./" + rel if not rel.startswith(".") else rel)
    venue_layer = Sdf.Layer.FindOrOpen(a.usd)
    if venue_layer and venue_layer.defaultPrim:
        stage.GetRootLayer().defaultPrim = venue_layer.defaultPrim
    UsdGeom.SetStageUpAxis(stage, UsdGeom.GetStageUpAxis(Usd.Stage.Open(a.usd)))
    UsdGeom.SetStageMetersPerUnit(stage, UsdGeom.GetStageMetersPerUnit(Usd.Stage.Open(a.usd)))

    scope = UsdGeom.Scope.Define(stage, "/World/ExitTargets")
    for eid, (x, y, z) in pts.items():
        xf = UsdGeom.Xform.Define(stage, f"/World/ExitTargets/{eid}")
        xf.AddTranslateOp().Set((x, y, z))
        xf.GetPrim().CreateAttribute("grimoires:exit_id", Sdf.ValueTypeNames.String).Set(eid)
        xf.GetPrim().CreateAttribute("grimoires:door_world", Sdf.ValueTypeNames.Float2).Set(tuple(venue["exits"][eid]["centre_world"]))
    stage.GetRootLayer().Save()

    print(f"wrote {a.out}  (sublayer {rel}, defaultPrim {stage.GetRootLayer().defaultPrim!r})")
    for eid, p in pts.items():
        print(f"  /World/ExitTargets/{eid}  at world ({p[0]:.2f}, {p[1]:.2f}, {p[2]:.1f})   door {venue['exits'][eid]['centre_world']}")


if __name__ == "__main__":
    main()
