#!/usr/bin/env bash
# run_film_queue.sh — run IRA film configs one after another on GPU 0, waiting first for any
# running Isaac container to finish. Each run uses actor_sdg_dump.py (positions come for free)
# and the NavMesh-cap patch bind-mount. Progress -> ~/film_queue.status, logs -> ~/ira_film_<name>.log
#
#   nohup bash ~/Documents/grimoires-twin/sim/ira/run_film_queue.sh winner_film60s base_film60s winner_film base_film \
#       > ~/film_queue.log 2>&1 &
#
# Check:  cat ~/film_queue.status            (which run, when it started, which are done)
#         tail -2 ~/film_queue.log
set -uo pipefail
REPO=/home/nvidia/Documents/grimoires-twin
IMG=nvcr.io/nvidia/isaac-sim:6.0.1
PATCH=/home/nvidia/ira_patch/simulation_util.py
MP=/isaac-sim/extscache/omni.metropolis.pipeline-0.0.9+110.1.2.lx64.cp312/omni/metropolis/pipeline/simulation_util.py
STATUS=$HOME/film_queue.status

status() { echo "$(date +%F\ %T)  $*" | tee -a "$STATUS"; }

: > "$STATUS"
status "queue: $*"
while docker ps -q --filter ancestor=$IMG | grep -q .; do
  status "waiting: another Isaac run is on GPU 0"
  sleep 60
done

for name in "$@"; do
  cfg=$REPO/sim/ira/hospital_${name}.yaml
  out=$REPO/results/ira_hospital_${name}
  if [ ! -f "$cfg" ]; then status "SKIP $name: $cfg missing"; continue; fi
  sudo rm -rf "$out"
  status "START $name  (log ~/ira_film_${name}.log)"
  docker run --rm --gpus '"device=0"' --network=host -e ACCEPT_EULA=Y -e PRIVACY_CONSENT=Y \
    -v /home/nvidia/docker/isaac-sim/cache/main:/isaac-sim/.cache:rw \
    -v /home/nvidia/docker/isaac-sim/cache/ov:/root/.cache/ov:rw \
    -v /home/nvidia/docker/isaac-sim/cache/computecache:/root/.nv/ComputeCache:rw \
    -v $REPO:/workspace:rw \
    -v $PATCH:$MP:ro \
    --entrypoint /isaac-sim/python.sh $IMG \
    /workspace/sim/ira/actor_sdg_dump.py -c /workspace/sim/ira/hospital_${name}.yaml \
    --dump /workspace/results/ira_hospital_${name}/agent_positions.jsonl \
    > "$HOME/ira_film_${name}.log" 2>&1
  rc=$?
  frames=$(sudo find "$out" -path "*/rgb/*.png" 2>/dev/null | wc -l)
  status "DONE  $name  exit=$rc  rgb frames=$frames"
done
status "ALL DONE"
