# PATCHED COPY — Grimoires. Source: Isaac Sim 6.0.1 container,
#   /isaac-sim/extscache/omni.metropolis.pipeline-0.0.9+110.1.2.lx64.cp312/omni/metropolis/pipeline/simulation_util.py
# Only change: ensure_navmesh_ready() max_frames 100 -> 5000. The NVIDIA Hospital NavMesh needs >100
# frames to bake; the stock cap aborts IRA with "Navmesh baking failed" and an empty results dir.
# Use: bind-mount over the container path, read-only:
#   -v $PWD/sim/ira/patches/simulation_util.py:/isaac-sim/extscache/omni.metropolis.pipeline-0.0.9+110.1.2.lx64.cp312/omni/metropolis/pipeline/simulation_util.py:ro

import carb
import numpy as np
import omni.anim.navigation.core as nav
import omni.kit.app
import omni.timeline
import omni.usd
from omni.behavior.scripting.core.scripts.script_manager import ScriptManager
from omni.metropolis.utils import simulation_util as omu_simulation_util

# Re-export stage-independent functions from OMU
from omni.metropolis.utils.simulation_util import (  # noqa: F401
    area_idx_to_probability,
    area_name_to_index,
    get_capture_on_play,
    get_original_xformOp_type,
    inav_idx_to_navmesh,
    is_the_same_point,
    is_the_same_point_2d,
    update_xformOp_type,
)
from pxr import Sdf

__all__ = [
    # Stage-dependent functions (defined here)
    "ensure_navmesh_ready",
    "validate_navmesh_point",
    "validate_navmesh_point_2d",
    "get_agent_script_instance_by_path",
    "get_current_timecode",
    "get_navmesh_scope",
    # Re-exported from omni.metropolis.utils.simulation_util
    "is_the_same_point",
    "is_the_same_point_2d",
    "inav_idx_to_navmesh",
    "area_idx_to_probability",
    "area_name_to_index",
    "get_capture_on_play",
    "update_xformOp_type",
    "get_original_xformOp_type",
]


"""
------------------------Utility for Simulation modules such as NavMesh------------------------
Stage-dependent functions that acquire navmesh/stage/timeline
"""


async def ensure_navmesh_ready() -> bool:
    """Try to ensure navmesh is ready and bake it if needed.

    Returns:
        True if navmesh is ready, False otherwise.

    """
    inav = nav.acquire_interface()
    if inav is None:
        carb.log_error("NavMesh interface is not available; cannot ensure navmesh readiness.")
        return False

    if inav.get_navmesh() is not None:
        return True

    can_bake = inav.start_navmesh_baking()
    if not can_bake:
        carb.log_error(
            "Failed to start navmesh baking. Please check whether the stage has a valid NavmeshVolume. "
            "Will not load assets to scene."
        )
        return False

    frame_count = 0
    max_frames = 5000
    while inav.get_navmesh() is None:
        await omni.kit.app.get_app().next_update_async()
        frame_count += 1
        if frame_count > max_frames:
            carb.log_error(
                f"NavMesh building failed after {frame_count} frames (limit {max_frames}). "
                "Please check whether the stage has a valid NavmeshVolume. "
                "Will not load assets to scene."
            )
            return False
    return True


def validate_navmesh_point(point: list[float], tol: float | None = 0.01, agent_radius: float | None = 0.0):
    """Validate if a 3D point is on the navmesh.

    Args:
        point: The 3D point to validate
        tol: Distance tolerance (default: 0.01)

    Returns:
        bool: True if the point is on the navmesh, False otherwise

    """
    point_carb = carb.Float3(point[0], point[1], point[2])
    inav = nav.acquire_interface()
    if inav is None:
        carb.log_error("NavMesh interface is not available; cannot validate NavMesh point.")
        return False
    navmesh = inav.get_navmesh()
    if navmesh is None:
        carb.log_error("Trying to validate a NavMesh point without a valid NavMesh")
        return False
    agent_desc = nav.NavAgentDesc(radius=agent_radius, height=2.0, collision_gap=0.0)
    closest_point = navmesh.query_closest_point(point_carb, agent=agent_desc)[0]
    if closest_point is None or not omu_simulation_util.is_the_same_point(point_carb, closest_point, tol):
        return False
    return True


def validate_navmesh_point_2d(point: list[float], tol: float | None = 0.01, agent_radius: float | None = 0.0):
    """Given a 3d point, check whether its 2d projection is on navmesh.

    Args:
        point: The 3D point to validate
        tol: Distance tolerance (default: 0.01)
        agent_radius: Radius of the agent (default: 0.0)

    Returns:
        bool: True if the point is on the navmesh, False otherwise

    """
    point_carb = carb.Float3(point[0], point[1], point[2])
    inav = nav.acquire_interface()
    if inav is None:
        carb.log_error("NavMesh interface is not available; cannot validate NavMesh point.")
        return False
    navmesh = inav.get_navmesh()
    if navmesh is None:
        carb.log_error("Trying to validate a NavMesh point without a valid NavMesh")
        return False
    agent_desc = nav.NavAgentDesc(radius=agent_radius, height=2.0, collision_gap=0.0)
    closest_point = navmesh.query_closest_point(point_carb, agent=agent_desc)[0]
    if closest_point is None or not omu_simulation_util.is_the_same_point_2d(point, closest_point, tol):
        return False
    return True


def get_agent_script_instance_by_path(agent_prim_path: str | Sdf.Path):
    """Get the agent BehaviorScript instance by the agent prim path.

    Args:
        agent_prim_path: The path to the agent prim

    Returns:
        The agent BehaviorScript instance
        None if the agent BehaviorScript instance is not found

    """
    sm = ScriptManager.get_instance()
    for scripts in sm._prim_to_scripts.values():
        # Traverse the script inst list, find the target agent's inst
        for _, inst in scripts.items():
            if inst is not None:
                if str(inst.prim_path) == str(agent_prim_path):
                    return inst
    return None


def get_current_timecode() -> float:
    """Get current simulation timecode.

    Returns:
        The current simulation timecode

    Note:
        The timecode value is bounded by the stage timecode range.

    """
    stage = omni.usd.get_context().get_stage()
    timeline_interface = omni.timeline.get_timeline_interface()
    current_time = timeline_interface.get_current_time()
    current_time_code = stage.GetTimeCodesPerSecond() * current_time
    return current_time_code


def get_navmesh_scope() -> list[tuple[float, float]]:
    """Compute axis-aligned bounds of the current NavMesh in world coordinates.

    Returns:
        List[Tuple[float, float]]: [(x_min, x_max), (y_min, y_max), (z_min, z_max)]

    Notes:
        - Callers commonly use only the first two pairs (XY). The Z range is
            provided for completeness and is currently unused by most callers.
        - Handles missing/empty navmesh gracefully with a minimal zero-sized scope.

    """
    inav = nav.acquire_interface()
    if inav is None:
        carb.log_warn("NavMesh interface not available; returning zero scope around origin.")
        return [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0)]
    navmesh = inav.get_navmesh()
    if navmesh is None:
        carb.log_warn("NavMesh is not available, try to bake it.")
        inav.start_navmesh_baking_and_wait()
        navmesh = inav.get_navmesh()
        if navmesh is None:
            carb.log_warn("NavMesh is not available; returning zero scope around origin.")
            return [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0)]

    try:
        vertices = navmesh.get_draw_triangles(0)
    except Exception as exc:
        carb.log_error(f"Failed to retrieve NavMesh triangles: {exc}")
        return [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0)]

    if not vertices:
        carb.log_warn("NavMesh has no triangles; returning zero scope around origin.")
        return [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0)]

    # Convert to a dense (N, 3) float array robustly (supports carb.Float3 or tuple-like)
    coords = np.empty((len(vertices), 3), dtype=float)
    for idx, v in enumerate(vertices):
        try:
            coords[idx, 0] = float(v[0])
            coords[idx, 1] = float(v[1])
            coords[idx, 2] = float(v[2])
        except Exception:
            coords[idx, 0] = float(getattr(v, "x", 0.0))
            coords[idx, 1] = float(getattr(v, "y", 0.0))
            coords[idx, 2] = float(getattr(v, "z", 0.0))

    x_min, x_max = float(np.min(coords[:, 0])), float(np.max(coords[:, 0]))
    y_min, y_max = float(np.min(coords[:, 1])), float(np.max(coords[:, 1]))
    z_min, z_max = float(np.min(coords[:, 2])), float(np.max(coords[:, 2]))

    # Validate finiteness
    if not np.all(np.isfinite([x_min, x_max, y_min, y_max, z_min, z_max])):
        carb.log_error("Computed non-finite NavMesh bounds; returning zero scope.")
        return [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0)]

    return [(x_min, x_max), (y_min, y_max), (z_min, z_max)]
