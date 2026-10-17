#!/usr/bin/env bash
# Track A, exact command order. Plain python3, no Isaac Sim, no GPU.
# Usage: cd grimoires-twin && bash sim/run_solve.sh
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p results

echo "== 0. variants + fires =="
python3 sim/plan.py

echo "== 1. venue manifest (base plan) =="
python3 sim/venue_def.py --out results/venue_base.venue.json

echo "== 2. smoke field — eyeball it (walls stop it, gates let it through) =="
python3 sim/smoke.py --origin 44,17 --at 0,20,40,60 --step 2

echo "== 3a. regression: no smoke, should match the template's routing numbers =="
python3 sim/rehearse.py --plan base --fire default --speed 0 --seed 42 --fps 12 \
        --report results/rehearse_base_nosmoke.json

echo "== 3b. base plan with the demo fire =="
python3 sim/rehearse.py --plan base --fire default --seed 42 --fps 12 \
        --report results/rehearse_base.json --tracks results/tracks_base.json

echo "== 4. solve: demo fire (24 runs) =="
python3 sim/solve.py --fires 1 --seed 42 --tag demo

echo "== 5. solve: all fires (96 runs) =="
python3 sim/solve.py --fires all --seed 42 --tag robust

echo "== done =="
ls -la results
