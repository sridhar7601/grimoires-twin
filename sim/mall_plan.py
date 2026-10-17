"""
mall_plan.py — slice a real 3D venue (USD) into the sim's 0.5 m occupancy grid.

The proxy hall (venue_def.py) is described as rectangles. A real building is
just triangles, so this script samples every triangle of the venue mesh and
asks two questions per 0.5 m cell:

  * is there FLOOR here?   a near-horizontal surface within floor_band of floor_z
  * is it BLOCKED?         any surface at body height (body_band above floor_z):
                           walls, counters, planters, trunks, stair sides

walkable = floor and not blocked. Everything else is not walkable.

WHAT THIS IS, AND IS NOT
------------------------
It is: a ground-floor walkability map, derived only from the geometry and two
stated height bands. It is NOT a fire-code floor plan: it knows nothing about
doors that are locked, glass that is a door, or which openings are real exits.
Exits are chosen by a person afterwards and written into the manifest. Upper
floors, stairs and escalators are out of scope (one floor, like the sim).

Needs pxr + numpy, so run inside the Isaac Sim container (no Kit, no GPU):

  bash sim/usdpy.sh sim/mall_plan.py --usd assets/venue_mall.usdc \
      --out results/mall_plan.json --png results/mall_plan.png
"""
import argparse
import json
import math
import os
import re
import struct
import sys
import zlib
from collections import deque

import numpy as np
from pxr import Usd, UsdGeom

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grid import RES  # noqa: E402

DEFAULTS = {
    "floor_z": 0.0,          # height of the ground floor in the venue file (m)
    "floor_band": 0.3,       # a surface within +-this of floor_z counts as floor
    "floor_nz": 0.9,         # ...and only if it is near-horizontal (|normal.z| above this)
    "body_band": [0.3, 2.0], # anything between these heights above the floor blocks a cell
    "sample_m2": 0.01,       # one sample point per this many m^2 of triangle area
}


def world_triangles(stage, ignore_re=None):
    """All mesh triangles in world space, as an (N, 3, 3) float array.

    ignore_re: meshes whose prim path matches are skipped (e.g. door leaves/frames,
    which are openable and must not count as walls).
    """
    xc = UsdGeom.XformCache(Usd.TimeCode.Default())
    # TraverseInstanceProxies: NVIDIA environments (e.g. Hospital) mark walls and
    # props `instanceable`; plain stage.Traverse() skips those prototypes, so only
    # the floors are seen and the map comes out with zero blocked cells.
    for prim in Usd.PrimRange(stage.GetPseudoRoot(), Usd.TraverseInstanceProxies()):
        if not prim.IsA(UsdGeom.Mesh) or UsdGeom.Imageable(prim).ComputeVisibility() != "inherited":
            continue
        if ignore_re is not None and ignore_re.search(prim.GetPath().pathString):
            continue
        mesh = UsdGeom.Mesh(prim)
        pts = mesh.GetPointsAttr().Get()
        counts = mesh.GetFaceVertexCountsAttr().Get()
        idx = mesh.GetFaceVertexIndicesAttr().Get()
        if not pts or not counts or not idx:
            continue
        m = np.array(xc.GetLocalToWorldTransform(prim), dtype=np.float64)   # row-vector convention
        p = np.asarray(pts, dtype=np.float64)
        p = (np.hstack([p, np.ones((len(p), 1))]) @ m)[:, :3]
        idx = np.asarray(idx)
        tris, k = [], 0
        for c in counts:                       # fan-triangulate each polygon
            tris.extend((idx[k], idx[k + t], idx[k + t + 1]) for t in range(1, c - 1))
            k += c
        if tris:
            yield p[np.asarray(tris)]


def sample(tri, per_m2, rng):
    """Random points on each triangle (count ~ area), plus the vertices themselves."""
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    cross = np.cross(b - a, c - a)
    area = 0.5 * np.linalg.norm(cross, axis=1)
    nz = np.abs(cross[:, 2]) / np.maximum(2 * area, 1e-12)
    n = np.ceil(area / per_m2).astype(int) + 1
    rep = np.repeat(np.arange(len(tri)), n)
    r1, r2 = rng.random(len(rep)), rng.random(len(rep))
    s = np.sqrt(r1)
    w0, w1, w2 = 1 - s, s * (1 - r2), s * r2
    pts = w0[:, None] * a[rep] + w1[:, None] * b[rep] + w2[:, None] * c[rep]
    verts = tri.reshape(-1, 3)
    return (np.vstack([pts, verts]),
            np.concatenate([nz[rep], np.repeat(nz, 3)]))


def largest_region(walk):
    """Mask of the biggest 4-connected walkable region: the space people start in."""
    gy, gx = walk.shape
    lab = -np.ones((gy, gx), int)
    best_n, best_k = 0, -1
    for j0, i0 in zip(*np.nonzero(walk)):
        if lab[j0, i0] >= 0:
            continue
        k = j0 * gx + i0
        lab[j0, i0] = k
        q, n = deque([(i0, j0)]), 0
        while q:
            i, j = q.popleft()
            n += 1
            for a, b in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                if 0 <= a < gx and 0 <= b < gy and walk[b, a] and lab[b, a] < 0:
                    lab[b, a] = k
                    q.append((a, b))
        if n > best_n:
            best_n, best_k = n, k
    return lab == best_k


def cut_doors(blocked, main, spec, width, x0, y0):
    """Turn 'E1:x,y;E2:x,y' into exits: the outer-wall cells within width/2 of the
    wall cell nearest each requested point. Returns {id: {cells, open, centre}}."""
    border = np.zeros_like(blocked)            # wall cells touching the main region
    for dj in (-1, 0, 1):
        for di in (-1, 0, 1):
            border |= blocked & np.roll(np.roll(main, dj, 0), di, 1)
    bj, bi = np.nonzero(border)
    bx, by = x0 + (bi + 0.5) * RES, y0 + (bj + 0.5) * RES
    exits = {}
    for item in spec.split(";"):
        eid, xy = item.split(":")
        tx, ty = (float(v) for v in xy.split(","))
        k = int(np.argmin((bx - tx) ** 2 + (by - ty) ** 2))
        sel = (bx - bx[k]) ** 2 + (by - by[k]) ** 2 <= (width / 2) ** 2
        exits[eid] = {"cells": [[int(i), int(j)] for i, j in zip(bi[sel], bj[sel])], "open": True,
                      "centre": [round(float(bx[k] - x0), 2), round(float(by[k] - y0), 2)],
                      "centre_world": [round(float(bx[k]), 2), round(float(by[k]), 2)]}
        print(f"  door {eid} at world ({bx[k]:.1f},{by[k]:.1f}), {int(sel.sum())} wall cells")
    return exits


def write_png(path, rgb):
    """Minimal PNG writer (no PIL needed). rgb: (H, W, 3) uint8, row 0 = top."""
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[r].tobytes() for r in range(h))
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--usd", required=True)
    ap.add_argument("--out", required=True, help="grid manifest .json")
    ap.add_argument("--png", help="top-down picture of the grid")
    ap.add_argument("--name", default="mall_ground_floor_v1")
    ap.add_argument("--scale", type=float, default=1.0,
                    help="uniform scale applied to the venue before slicing; the scene that "
                         "renders the venue must reference it at the same scale")
    ap.add_argument("--floor-z", type=float, default=DEFAULTS["floor_z"])
    ap.add_argument("--body-band", default=",".join(str(v) for v in DEFAULTS["body_band"]))
    ap.add_argument("--doors", default="",
                    help="hand-picked exits as 'E1:x,y;E2:x,y' in scaled world metres; each is cut "
                         "into the main region's outer wall at the nearest wall cell")
    ap.add_argument("--door-width", type=float, default=3.2, help="door width in metres")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--seal-perimeter", action="store_true",
                    help="after slicing, turn main-region cells that touch the void (real exterior "
                         "doorways left open by --ignore) back into wall, so the only ways out are "
                         "the exits named in --doors")
    ap.add_argument("--ignore", default="",
                    help="regex (case-insensitive) on the prim path; matching meshes are skipped, "
                         "e.g. 'door' so openable doors are not sliced as walls")
    a = ap.parse_args()

    prm = dict(DEFAULTS, floor_z=a.floor_z, body_band=[float(v) for v in a.body_band.split(",")])
    stage = Usd.Stage.Open(a.usd)
    rng = np.random.default_rng(a.seed)
    P, NZ = [], []
    ignore_re = re.compile(a.ignore, re.I) if a.ignore else None
    for tri in world_triangles(stage, ignore_re):
        p, nz = sample(tri, prm["sample_m2"], rng)
        P.append(p)
        NZ.append(nz)
    P, NZ = np.vstack(P) * a.scale, np.concatenate(NZ)

    x0, y0 = math.floor(P[:, 0].min()), math.floor(P[:, 1].min())
    x1, y1 = math.ceil(P[:, 0].max()), math.ceil(P[:, 1].max())
    gx, gy = int((x1 - x0) / RES), int((y1 - y0) / RES)
    ii = np.clip(((P[:, 0] - x0) / RES).astype(int), 0, gx - 1)
    jj = np.clip(((P[:, 1] - y0) / RES).astype(int), 0, gy - 1)
    dz = P[:, 2] - prm["floor_z"]

    floor = np.zeros((gy, gx), bool)
    sel = (np.abs(dz) <= prm["floor_band"]) & (NZ >= prm["floor_nz"])
    floor[jj[sel], ii[sel]] = True
    blocked = np.zeros((gy, gx), bool)
    lo, hi = prm["body_band"]
    sel = (dz >= lo) & (dz <= hi)
    blocked[jj[sel], ii[sel]] = True
    walk = floor & ~blocked
    main = largest_region(walk)
    if a.seal_perimeter:
        # void = no floor (outside). A main cell with a void 4-neighbour (or on the grid
        # edge) is an opening in the exterior wall: an un-named way out. Wall it off;
        # cut_doors then re-opens exactly the named exits on those same doorway cells.
        void = ~(floor | blocked)
        edge = np.ones_like(main)
        edge[1:-1, 1:-1] = False
        touch = edge.copy()
        touch[1:, :] |= void[:-1, :]
        touch[:-1, :] |= void[1:, :]
        touch[:, 1:] |= void[:, :-1]
        touch[:, :-1] |= void[:, 1:]
        seal = main & touch
        blocked |= seal
        walk &= ~seal
        main = largest_region(walk)
        print(f"sealed {int(seal.sum())} perimeter opening cells")
    exits = cut_doors(blocked, main, a.doors, a.door_width, x0, y0) if a.doors else {}

    manifest = {
        "name": a.name, "kind": "grid", "source_usd": os.path.basename(a.usd),
        "res": RES, "scale": a.scale, "origin": [x0, y0], "size": {"x": gx * RES, "y": gy * RES}, "gx": gx, "gy": gy,
        # Rows south->north (j = 0 first), one char per cell: 'm' walkable and in the main
        # region (where people start), '.' walkable elsewhere, '#' blocked, ' ' no floor.
        # Door cells stay '#' here; the grid builder opens the ones a plan marks open.
        "cells": ["".join("m" if main[j, i] else "." if walk[j, i] else ("#" if blocked[j, i] else " ")
                          for i in range(gx)) for j in range(gy)],
        "exits": exits,
        "params": dict(prm, door_width_m=a.door_width), "n_samples": int(len(P)),
        "ignore": a.ignore, "seal_perimeter": bool(a.seal_perimeter),
        "note": "ground-floor walkability sliced from geometry at body height"
                + (f"; meshes matching /{a.ignore}/i were skipped (openable doors are not walls)" if a.ignore else "")
                + "; exit positions are chosen by hand and cut into the outer wall; upper floors, "
                  "stairs and escalators are out of scope",
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(manifest, open(a.out, "w"))
    n_w, n_b = int(walk.sum()), int(blocked.sum())
    print(f"grid {gx} x {gy} cells ({gx * RES:.0f} x {gy * RES:.0f} m), origin {x0},{y0}; "
          f"walkable {n_w} cells = {n_w * RES * RES:.0f} m2, blocked {n_b}, samples {len(P)}")
    print(f"wrote {a.out}")

    if a.png:
        S = 4                                   # pixels per cell
        img = np.zeros((gy, gx, 3), np.uint8)   # no floor = black
        img[walk] = (225, 225, 215)
        img[main] = (250, 240, 200)
        img[blocked] = (80, 80, 95)
        for e in exits.values():
            for i, j in e["cells"]:
                img[j, i] = (0, 200, 0)
        img = np.repeat(np.repeat(img[::-1], S, 0), S, 1)   # north up
        for k in range(math.ceil(x0 / 10) * 10, x1 + 1, 10):  # vertical lines at world x = k
            c = int((k - x0) / RES * S)
            if 0 <= c < img.shape[1]:
                img[:, c] = (0, 140, 255) if k == 0 else (60, 110, 160)
        for k in range(math.ceil(y0 / 10) * 10, y1 + 1, 10):  # horizontal lines at world y = k
            r = img.shape[0] - 1 - int((k - y0) / RES * S)
            if 0 <= r < img.shape[0]:
                img[r, :] = (0, 140, 255) if k == 0 else (60, 110, 160)
        write_png(a.png, img)
        print(f"wrote {a.png} ({img.shape[1]}x{img.shape[0]} px, north up, blue lines every 10 m, "
              f"bright blue = world x=0 / y=0)")


if __name__ == "__main__":
    main()
