# Evacuation Plan Certificate — hospital_ground_floor_v1

**Fire:** `hospital_main_entrance` at grid-local [48.75, 6.25] · **Base plan:** `G-E12-a30-s25` · **Recommended plan:** `G-E1234-a5-s25` (winner of 24 variants on this fire; see `layer1_table.md`, robustness in `robustness_table.md`) · **Seed:** 42 · **Date:** 2026-10-17

Layer 1 = Python solver, 300 people, fps 12.0. Layer 2 = Isaac Sim rehearsal, 40 characters, exit = first frame within 1.5 m of the agent's exit target. Same fire origin, same plan knobs, same seed in both layers.

Twin setup: door leaves switched off (doors open), as Layer 1 assumes; 40 characters; same seed and spawn positions as the doors-closed runs

| plan | Layer-1 t90 | Layer-2 t90 | exits used — Layer 1 | exits used — Layer 2 | closed exits — Layer 1 | closed exits — Layer 2 |
|---|---|---|---|---|---|---|
| **base** `G-E12-a30-s25` | 135.9 s | 62.6 s | E1 23, E2 277 | E1 28, E2 12 | E1 | not modelled (Phase 4) |
| **winner** `G-E1234-a5-s25` | 57.3 s | 30.0 s | E1 40, E2 29, E3 105, E4 126 | E1 16, E2 3, E3 8, E4 13 | E1 | not modelled (Phase 4) |

## Agreement

- **Ordering:** Layer 1 says winner faster (57.3 s vs 135.9 s); Layer 2 says winner faster (30.0 s vs 62.6 s). → **AGREE**.
- **Unusable exits:** Layer 1 closes ['E1'] (smoke reaches the opening). The twin has no smoke yet (Phase 4), so this half of the agreement test is **not yet testable** — stated, not assumed.
- **Congestion caveat, measured:** Layer-2 / Layer-1 t90 = base 0.46, winner 0.52. Expected direction: the twin is *faster* at crowded doors — Layer 1 models door throughput (SFPE 1.3 p/m/s cap), IRA characters do not queue. A ratio below 1 at the base plan (one door for everyone) is this effect, not a disagreement.

## Supporting numbers

| metric | base L1 | winner L1 | base L2 | winner L2 |
|---|---|---|---|---|
| t50 / t90 / t100 | 81.5 / 135.9 / 173.7 | 31.3 / 57.3 / 97.1 | 55.1 / 62.6 / 74.5 | 23.5 / 30.0 / 34.6 |
| people | 300 | 300 | 40 (40 arrived, 0 never) | 40 (40 arrived, 0 never) |
| over 30 s smoke threshold | 54 | 6 | n/a (no smoke in twin yet) | n/a |
| rerouted / redirected | 1 | 39 | 0 | 0 |

## Sensitivity — door leaves closed (NVIDIA asset as shipped)

| plan | Layer-2 t50 / t90 / t100 (headline setup) | Layer-2 t50 / t90 / t100 (door leaves closed (NVIDIA asset as shipped)) |
|---|---|---|
| base `G-E12-a30-s25` | 55.1 / 62.6 / 74.5 | 55.6 / 68.3 / 102.4 |
| winner `G-E1234-a5-s25` | 23.5 / 30.0 / 34.6 | 23.9 / 31.0 / 36.5 |

Winner faster under this setup too: **yes**. Same seed and spawn positions in both setups.


## What this certificate claims — and does not

- *Rehearses, finds, ranks* — never *predicts*. *Exit saturated / corridor closed* — never *crush*. No crowd-density figure anywhere.
- Fix = plan knobs only (exits opened, alarm earlier, stagger). Fire origin, spread, people count and seed held fixed within each layer.
- Smoke: simplified grid front model in Layer 1; Flow in the twin is the visual of the same fire (Phase 4). Proxy venue, not a real hospital.
- Most robust plan among those tried, not optimal. IRA has no congestion model — stated next to every Layer-2 number.

Sources: `solve_hospital.json`, `layer2_base_doorsopen.json`, `layer2_winner_doorsopen.json`; Layer-2 model: Isaac Sim / IRA characters on a baked NavMesh, behaviour tree Wait(alarm+stagger) -> MoveTo exit; no collision or queuing between characters, so door throughput is not modelled here; exit = first frame within reach_m of the agent's exit target
