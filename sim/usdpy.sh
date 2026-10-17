#!/usr/bin/env bash
# Run a plain USD (pxr) script inside the Isaac Sim container without booting Kit.
#
# Isaac Sim ships the USD python bindings inside the omni.usd.libs extension
# cache, which is not on PYTHONPATH by default and whose shared objects live in
# that extension's bin/. Authoring a stage needs neither SimulationApp nor a
# GPU, so this wrapper just points python at those two directories.
#
# Copied from gameday-twin/sim/usdpy.sh. Added: Kit's bundled numpy
# (omni.kit.pip_archive), which mall_plan.py needs.
#
# Usage (inside the container):  bash sim/usdpy.sh sim/build_venue.py --out ...
set -euo pipefail
ISAAC=${ISAAC:-/isaac-sim}
U=$(ls -d "$ISAAC"/extscache/omni.usd.libs-* | head -1)
NP=$(ls -d "$ISAAC"/extscache/omni.kit.pip_archive-*/pip_prebundle | head -1)
export PYTHONPATH="$U:$NP:${PYTHONPATH:-}"
export LD_LIBRARY_PATH="$U/bin:${LD_LIBRARY_PATH:-}"
exec "$ISAAC/kit/python/bin/python3" "$@"
