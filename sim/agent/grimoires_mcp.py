"""
grimoires_mcp.py — the Grimoires pipeline as an MCP server, so any MCP agent (Hermes, NemoClaw, Claude...)
can drive it: describe the problem, rehearse/evaluate plans, run the grid, read the certificate, and send a
plan to the Isaac Sim twin.

  uv run --with "mcp<2" python sim/agent/grimoires_mcp.py        # stdio server (pinned: SDK 2.x renamed FastMCP)

Hermes config.yaml (mcp_servers section):
  grimoires:
    command: uv
    args: ["run", "--with", "mcp<2", "python", "<repo>/sim/agent/grimoires_mcp.py"]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp.server.fastmcp import FastMCP  # noqa: E402

import tools  # noqa: E402

mcp = FastMCP("grimoires")


@mcp.tool()
def describe() -> str:
    """The evacuation problem: venue, exits, fire scenarios, the base plan, the knobs and the score."""
    return json.dumps(tools.describe())


@mcp.tool()
def rehearse_plan(exits_open: list[str], alarm_delay_s: float, stagger_s: float, fire: str = "entrance") -> str:
    """Rehearse one plan against one fire (Layer 1, ~1 s): clearance times, smoke exposure, exits used, score."""
    return json.dumps(tools.rehearse({"exits_open": exits_open, "alarm_delay_s": alarm_delay_s, "stagger_s": stagger_s}, fire))


@mcp.tool()
def evaluate_plan(exits_open: list[str], alarm_delay_s: float, stagger_s: float) -> str:
    """Rehearse one plan against all five fires (~4 s). Robust score = the worst fire; lower is better."""
    e = tools.evaluate({"exits_open": exits_open, "alarm_delay_s": alarm_delay_s, "stagger_s": stagger_s})
    e.pop("per_fire", None)
    return json.dumps(e)


@mcp.tool()
def grid_search(top: int = 5) -> str:
    """The fixed 24-variant sweep under all five fires (~80 s), ranked by worst fire."""
    return json.dumps(tools.grid_search(top=top))


@mcp.tool()
def certificate() -> str:
    """The current two-layer certificate (Python solver vs Isaac twin), markdown."""
    return tools.certificate()


@mcp.tool()
def rehearse_in_twin(exits_open: list[str], alarm_delay_s: float, stagger_s: float) -> str:
    """Queue an Isaac Sim rehearsal of a plan on the GPU box (40 characters, doors open, smoke closure).
    Takes 30-50 minutes; returns a job name to poll with twin_status."""
    return json.dumps(tools.start_twin({"exits_open": exits_open, "alarm_delay_s": alarm_delay_s, "stagger_s": stagger_s}))


@mcp.tool()
def twin_status(job: str) -> str:
    """Progress of a twin rehearsal; when finished, its measured Layer-2 numbers."""
    return json.dumps(tools.twin_status(job))


if __name__ == "__main__":
    mcp.run()
