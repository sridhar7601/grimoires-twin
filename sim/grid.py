"""
grid.py — the one 0.5 m occupancy grid and the one Dijkstra, shared by smoke.py
(where does the smoke get to) and rehearse.py (which way do people go).

Lifted from gameday-twin/sim/bake_egress.py so both use exactly the same cells
and the same obstacle rule. Plain Python, no numpy, no USD: runs anywhere.

Distances come back in CELL units (1.0 straight, 1.4142 diagonal); multiply by
RES for metres.
"""
import heapq
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from venue_def import segments as _segments  # noqa: E402

RES = 0.5
INF = float("inf")
NB = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
      (1, 1, 1.4142), (-1, 1, 1.4142), (1, -1, 1.4142), (-1, -1, 1.4142)]


def build_grid(venue):
    """Occupancy grid for a resolved venue (gates/exits already open or closed).

    Returns dict: blocked[j][i], gx, gy, exit_cells [(i, 0)], exit_of {(i, 0): id}.
    Stands are seating terraces — walkable, so not obstacles (same as the template).
    A venue of kind "grid" (sliced from a real building by mall_plan.py) carries its
    cells directly; its exits are lists of wall cells, opened here if the plan says so.
    """
    if venue.get("kind") == "grid":
        return _build_from_cells(venue)
    W, H = venue["size"]["x"], venue["size"]["y"]
    gx, gy = int(W / RES), int(H / RES)
    wt, bar = venue["wall_thickness"], venue["barrier"]
    rects = []
    for x0, x1 in _segments(0, W, venue["exits"].values()):
        rects.append((x0, 0.0, x1, wt))
    rects += [(0, H - wt, W, H), (0, 0, wt, H), (W - wt, 0, W, H)]
    for x0, x1 in _segments(0, W, venue["gates"].values()):
        rects.append((x0, bar["y"] - bar["thickness"] / 2, x1, bar["y"] + bar["thickness"] / 2))
    for p in venue["pillars"]:
        rects.append((p["x"] - 0.5, p["y"] - 0.5, p["x"] + 0.5, p["y"] + 0.5))

    blocked = [[False] * gx for _ in range(gy)]
    for (x0, y0, x1, y1) in rects:
        for j in range(max(0, int((y0 - 0.25) / RES)), min(gy, int(math.ceil((y1 + 0.25) / RES)))):
            for i in range(max(0, int((x0 - 0.25) / RES)), min(gx, int(math.ceil((x1 + 0.25) / RES)))):
                blocked[j][i] = True

    exit_cells, exit_of = [], {}
    for eid, e in venue["exits"].items():
        if not e["open"]:
            continue
        for i in range(int(e["x0"] / RES), int(e["x1"] / RES)):
            blocked[0][i] = blocked[1][i] = False
            exit_cells.append((i, 0))
            exit_of[(i, 0)] = eid
    return {"blocked": blocked, "gx": gx, "gy": gy, "exit_cells": exit_cells,
            "exit_of": exit_of, "W": W, "H": H}


def _build_from_cells(venue):
    """Grid venue: 'm' / '.' walkable, anything else blocked; open exit cells walkable."""
    gx, gy = venue["gx"], venue["gy"]
    rows = venue["cells"]
    blocked = [[rows[j][i] not in "m." for i in range(gx)] for j in range(gy)]
    exit_cells, exit_of = [], {}
    for eid, e in venue["exits"].items():
        if not e["open"]:
            continue
        for i, j in e["cells"]:
            blocked[j][i] = False
            exit_cells.append((i, j))
            exit_of[(i, j)] = eid
    return {"blocked": blocked, "gx": gx, "gy": gy, "exit_cells": exit_cells,
            "exit_of": exit_of, "W": venue["size"]["x"], "H": venue["size"]["y"]}


def dijkstra(blocked, gx, gy, sources, weight=None):
    """Multi-source distance field. sources: iterable of (i, j, label).

    Returns (dist, owner): dist in cell units, owner = label of the nearest source.
    Diagonal moves may not cut a blocked corner (same rule as the template).
    `weight[j][i]` (optional) multiplies the cost of stepping INTO a cell, so a
    route through smoke is "longer" than one around it.
    """
    dist = [[INF] * gx for _ in range(gy)]
    owner = [[None] * gx for _ in range(gy)]
    pq = []
    for (i, j, lab) in sources:
        if blocked[j][i]:
            continue
        dist[j][i] = 0.0
        owner[j][i] = lab
        heapq.heappush(pq, (0.0, i, j))
    while pq:
        d, i, j = heapq.heappop(pq)
        if d > dist[j][i]:
            continue
        for di, dj, c in NB:
            ni, nj = i + di, j + dj
            if 0 <= ni < gx and 0 <= nj < gy and not blocked[nj][ni]:
                if di and dj and (blocked[j][ni] or blocked[nj][i]):
                    continue
                nd = d + (c * weight[nj][ni] if weight else c)
                if nd < dist[nj][ni] - 1e-9:
                    dist[nj][ni] = nd
                    owner[nj][ni] = owner[j][i]
                    heapq.heappush(pq, (nd, ni, nj))
    return dist, owner


def cell_of(x, y, gx, gy):
    return min(max(int(x / RES), 0), gx - 1), min(max(int(y / RES), 0), gy - 1)


def center(i, j):
    return (i + 0.5) * RES, (j + 0.5) * RES


def span_cells(x0, x1, y):
    """Cells across an opening [x0, x1) on the row containing y."""
    j = int(y / RES)
    return [(i, j) for i in range(int(x0 / RES), int(x1 / RES))]


def nearest_walkable(blocked, gx, gy, i, j):
    """Breadth-first search outwards until a free cell is found."""
    seen, q = {(i, j)}, [(i, j)]
    while q:
        ci, cj = q.pop(0)
        if not blocked[cj][ci]:
            return ci, cj
        for di, dj, _ in NB:
            n = (ci + di, cj + dj)
            if 0 <= n[0] < gx and 0 <= n[1] < gy and n not in seen:
                seen.add(n)
                q.append(n)
    return i, j
