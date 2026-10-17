# Grimoires — the Evacuation Plan Certificate

Give Grimoires a building and its evacuation plan. It rehearses a fire, scores the plan with
hard numbers, **searches many plan variants and ranks them**, then **proves the winner in a
physical twin** — NVIDIA Isaac Sim characters path-finding through the real building — and
hands back a certificate: *where the plan fails, the fix, and before → after on the same fire.*

Venue: NVIDIA's Isaac **Hospital** environment (ground floor, 4 exits). Every number below
comes from files in `results/` and is reproduced by the commands in this README.

## The result so far (hospital, fire 4 m inside the main entrance, seed 42)

| | base plan `E1+E2, alarm 30 s` | recommended `E1–E4, alarm 5 s` |
|---|---|---|
| **Layer 1** — Python solver, 300 people: t90 | **135.9 s** | **57.3 s** (−58 %) |
| people over the 30 s smoke threshold | 54 | 6 (−89 %) |
| main entrance closed by smoke at | 21.7 s | 21.7 s |
| **Layer 2** — Isaac Sim twin, 40 characters (doors open): t90 | **62.6 s** | **30.0 s** — 40/40 out in both |

The base plan sends everyone to the front doors; the fire kills the main entrance at 22 s and
277 of 300 people queue through one door. Opening the two wing exits and alarming earlier
clears 90 % in under a minute. Across **five fire origins × 24 plans** the base plan ranks
**last under every fire** (`docs/results/robustness_table.md`).

The twin agrees on the ordering with doors open (headline, as Layer 1 assumes) and with the
asset's door leaves closed (base 68.3 s vs winner 31.0 s) — see `docs/results/certificate.md`.

Videos (in `renders/`, not in git): `hospital_map_layer1.mp4` (top-down, 300 people, smoke),
`hospital_map_layer2_twin.mp4` (top-down, the twin's 40 characters), `hospital_dollhouse_overlay.mp4`
(real Isaac render, roof off, rings on every character from the recorded positions).

Honest framing, kept exact: *rehearses / finds / ranks* — never *predicts*; *exit saturated*
— never *crush*; no crowd-density figure anywhere; simplified grid smoke model; the twin has
no door queuing (so it clears faster — stated next to every Layer-2 number); proxy venue;
*most robust plan among those tried*, not optimal.

## How it works

```
venue USD ─► sim/mall_plan.py ──► 0.5 m walkable grid + named exits (results/hospital_plan.json)
plan knobs: exits_open, alarm_delay_s, stagger_s                 (scenarios/*.json)

LAYER 1  sim/solve.py → sim/rehearse.py per variant: Dijkstra routing, smoke front,
         SFPE door cap, exposure → ranked variants, base vs winner        (seconds, CPU)

LAYER 2  sim/make_ira_config.py: plan → Isaac stage (exit targets + NavMesh spawn zones,
         nearest exit by walking distance) + one behaviour tree per exit
         (Wait alarm+stagger → MoveTo exit) + Isaac Replicator Agent config
         sim/ira/actor_sdg_dump.py runs it and records every character's position per frame
         sim/measure.py → t50/t90/t100, exits used, in the twin               (GPU, minutes)

LAYER 3  sim/certificate.py → docs/results/certificate.md: both layers, same fire, agree?
```

NVIDIA pieces: OpenUSD · Isaac Sim 6.0.1 · Isaac Replicator Agent (NavMesh, behaviour trees,
Replicator writers) · Isaac People characters · Hospital environment · Cosmos Reason 2 NIM
(narration, Phase 6) · Nemotron / NemoClaw (agent loop, Phase 7).

## Run it

**Layer 1 — any machine with Python 3 + numpy, no GPU** (the slicer needs `pxr`; see below):

```bash
python3 sim/rehearse.py --venue results/hospital_plan.json --plan scenarios/hospital_base_plan.json \
    --fire scenarios/hospital_fire_entrance.json --seed 42 --fps 12 --people 300 --report /tmp/base.json
python3 sim/solve.py --venue results/hospital_plan.json --base scenarios/hospital_base_plan.json \
    --fires scenarios/hospital_fire_entrance.json --people 300 --fps 12 --tag hospital          # 24 variants, ~20 s
python3 sim/solve.py ... --fires scenarios/hospital_fire_entrance.json,scenarios/hospital_fire_e2_north.json,scenarios/hospital_fire_e3_east.json,scenarios/hospital_fire_e4_west.json,scenarios/hospital_fire_central.json --tag hospital_robust
```

**Venue slicing and Layer 2 — Isaac Sim 6.0.1 container** (pxr + numpy come from the container;
`sim/usdpy.sh` runs plain USD scripts without booting Kit):

```bash
# hospital geometry: copy Isaac/Environments/Hospital/ from the Isaac assets root to assets/hospital/
bash sim/usdpy.sh sim/mall_plan.py --usd assets/hospital/hospital.usd --name hospital_ground_floor_v1 \
    --ignore door --seal-perimeter --doors "E1:-1.25,-2.75;E2:-40.5,33.25;E3:20.75,31.25;E4:-38.25,8.75" \
    --out results/hospital_plan.json --png results/hospital_plan.png
bash sim/usdpy.sh sim/make_ira_config.py --plan scenarios/hospital_winner_plan.json --venue results/hospital_plan.json \
    --layer1-report results/rehearse_hospital_winner.json --people 40 --measure-only
# then, with the container's python and GPU — note the NavMesh-cap patch bind-mount (sim/ira/patches/):
/isaac-sim/python.sh /workspace/sim/ira/actor_sdg_dump.py -c /workspace/sim/ira/hospital_winner_measure.yaml \
    --dump /workspace/results/ira_hospital_winner_measure/agent_positions.jsonl
python3 sim/measure.py --venue results/hospital_plan.json --plan scenarios/hospital_winner_plan.json \
    --positions results/ira_hospital_winner_measure/agent_positions.jsonl --report results/layer2_winner.json
python3 sim/certificate.py --layer1 results/solve_hospital.json --layer2-base results/layer2_base.json \
    --layer2-winner results/layer2_winner.json --out docs/results/certificate.md
```

Three things that were not obvious and are handled in code: NVIDIA environments mark walls
and props `instanceable` (the slicer traverses instance proxies); the hospital's closed door
meshes seal every ward (`--ignore door`) while its exterior doorways must not be unregistered
leaks (`--seal-perimeter`); and Isaac characters move in Fabric, not USD, so positions are
read from IRA's agent objects, never from USD transforms.

## Layout

```
docs/              PLAN.md (phases, outcomes, decisions) · ARCHITECTURE.md · results/*.md (the tables)
sim/               all code; sim/ira/ = Isaac configs, behaviour-tree generator inputs, NavMesh patch; sim/bt/ = trees
scenarios/         plans and fire origins (JSON)
results/           walkable maps, Layer-1 reports and tracks, Layer-2 reports (run outputs with frames are git-ignored)
assets/            venue USDs; the 1 GB hospital textures/props are fetched, not committed (see .gitignore)
```

The mall venue from the first iteration (`assets/venue_mall.usdc`, `scenarios/mall_*.json`,
`results/mall_*`) still works with the same commands; the hospital is the primary venue.
