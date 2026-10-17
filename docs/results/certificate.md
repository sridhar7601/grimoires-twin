# Evacuation Plan Certificate — hospital_ground_floor_v1

**Fire:** `hospital_main_entrance` at grid-local [48.75, 6.25] · **Base plan:** `G-E12-a30-s25` · **Recommended plan:** `G-E1234-a5-s25` (winner of 24 variants on this fire; see `layer1_table.md`, robustness in `robustness_table.md`) · **Seed:** 42 · **Date:** 2026-10-17

Layer 1 = Python solver, 300 people, fps 12.0. Layer 2 = Isaac Sim rehearsal, 40 characters, exit = first frame within 1.5 m of the agent's exit target. Same fire origin, same plan knobs, same seed in both layers.

Twin setup: door leaves switched off (doors open), as Layer 1 assumes; 40 characters; same seed and spawn positions in all twin setups

| plan | Layer-1 t90 | Layer-2 t90 | exits used — Layer 1 | exits used — Layer 2 | closed exits — Layer 1 | closed exits — Layer 2 |
|---|---|---|---|---|---|---|
| **base** `G-E12-a30-s25` | 135.9 s | 62.6 s | E1 23, E2 277 | E1 28, E2 12 | E1 | not modelled (Phase 4) |
| **winner** `G-E1234-a5-s25` | 57.3 s | 30.0 s | E1 40, E2 29, E3 105, E4 126 | E1 16, E2 3, E3 8, E4 13 | E1 | not modelled (Phase 4) |

## Agreement

- **Ordering:** Layer 1 says winner faster (57.3 s vs 135.9 s); Layer 2 says winner faster (30.0 s vs 62.6 s). → **AGREE**.
- **Unusable exits:** Layer 1 closes ['E1'] (smoke reaches the opening). In the twin the closure is *scripted from Layer 1's closure time* (characters assigned to that exit are re-assigned at 21.7 s; Flow renders the same fire) — it is not read back from the Flow smoke, so this half of the agreement test is **not independently testable yet** — stated, not assumed. The Flow-fire runs are reported under Sensitivity.
- **Congestion caveat, measured:** Layer-2 / Layer-1 t90 = base 0.46, winner 0.52. Expected direction: the twin is *faster* at crowded doors — Layer 1 models door throughput (SFPE 1.3 p/m/s cap), IRA characters do not queue. A ratio below 1 at the base plan (one door for everyone) is this effect, not a disagreement.

## Supporting numbers

| metric | base L1 | winner L1 | base L2 | winner L2 |
|---|---|---|---|---|
| t50 / t90 / t100 | 81.5 / 135.9 / 173.7 | 31.3 / 57.3 / 97.1 | 55.1 / 62.6 / 74.5 | 23.5 / 30.0 / 34.6 |
| people | 300 | 300 | 40 (40 arrived, 0 never) | 40 (40 arrived, 0 never) |
| over 30 s smoke threshold | 54 | 6 | n/a (no smoke in twin yet) | n/a |
| rerouted / redirected | 1 | 39 | 0 | 0 |
| door crowding, worst door (demand) | 1.3 p/m² at E2 (8 people), 0 s over 4/m² | 2.4 p/m² at E4 (15 people), 0 s over 4/m² | none (no one within 2 m of a door before exit) | 1.0 p/m² at E4 (6 people), 0 s over 4/m² |

Door crowding = people not yet out within 2 m of the door centre over a 6.3 m² half-disc, every sample; 4 p/m² is Fruin's LOS E/F (movement stops), 6 p/m² the crush band. It is **demand** — how many people press on one door at once — a crush-risk flag. Neither layer simulates body pressure (Layer 1 queues at the door cap but bodies overlap; IRA characters avoid each other but are not stopped by contact), so a figure above 6 means *this door is asked to take more people than can physically fit*, not *a crush happens*. In the twin a character counts as out 1.5 m from a target that sits 1.25 m inside the door, i.e. about 2.75 m before the door line, so the twin figure is a lower bound and a sanity check; the operative flag is Layer 1 (300 people, door cap).

## Sensitivity — door leaves closed (NVIDIA asset as shipped)

| plan | Layer-2 t50 / t90 / t100 (headline setup) | Layer-2 t50 / t90 / t100 (this setup) | exits used (this setup) | door crowding (this setup) |
|---|---|---|---|---|
| base `G-E12-a30-s25` | 55.1 / 62.6 / 74.5 | 55.6 / 68.3 / 102.4 | E1 28, E2 12 | 0.5 p/m² at E1 (3 people), 0 s over 4/m² |
| winner `G-E1234-a5-s25` | 23.5 / 30.0 / 34.6 | 23.9 / 31.0 / 36.5 | E1 16, E2 3, E3 8, E4 13 | 1.0 p/m² at E4 (6 people), 0 s over 4/m² |

Winner faster under this setup too: **yes**. Same seed and spawn positions in both setups.

## Sensitivity — Omniverse Flow fire at the origin, E1 closed by smoke at 21.7 s

| plan | Layer-2 t50 / t90 / t100 (headline setup) | Layer-2 t50 / t90 / t100 (this setup) | exits used (this setup) | door crowding (this setup) |
|---|---|---|---|---|
| base `G-E12-a30-s25` | 55.1 / 62.6 / 74.5 | 74.0 / 120.2 / not reached in 193 s | E2 38 | none (no one within 2 m of a door before exit) |
| winner `G-E1234-a5-s25` | 23.5 / 30.0 / 34.6 | 23.7 / 45.1 / 59.6 | E1 11, E2 3, E3 13, E4 13 | 1.0 p/m² at E4 (6 people), 0 s over 4/m² |

Winner faster under this setup too: **yes**. Same seed and spawn positions in both setups.
Caveats: base: 2 never came within 1.5 m of an exit target — they stopped 1.6, 1.8 m short behind characters parked on it; winner: 6 of 40 still reached E1 after its smoke closure (they had already set off; IRA does not re-route mid-walk).

## Door-crowding flag — does it fire when it should?

A deliberately bad plan `G-E1234-a0-s0` (everyone released at once) on the same fire and seed: 5.1 p/m² at E4 (32 people), 6 s over 4/m², t90 24.4 s. Faster on paper, flagged in red — this is the case the agent's alarm/stagger floors exist for, and the flag now catches it from the data rather than from a rule.

## What this certificate claims — and does not

- *Rehearses, finds, ranks* — never *predicts*. *Exit saturated / corridor closed / door crowding (demand)* — never *crush*. The only density-shaped number is door-crowding demand, labelled as a risk flag, not a prediction.
- Fix = plan knobs only (exits opened, alarm earlier, stagger). Fire origin, spread, people count and seed held fixed within each layer.
- Smoke: simplified grid front model in Layer 1; Flow in the twin is the visual of the same fire (Phase 4). Proxy venue, not a real hospital.
- Most robust plan among those tried, not optimal. IRA has no congestion model — stated next to every Layer-2 number.

Sources: `solve_hospital.json`, `layer2_base_doorsopen.json`, `layer2_winner_doorsopen.json`; Layer-2 model: Isaac Sim / IRA characters on a baked NavMesh, behaviour tree Wait(alarm+stagger) -> MoveTo exit; local avoidance but no contact or queuing between characters, so door throughput is not modelled and door_crowding is DEMAND at the door (crush-risk flag), never a crush prediction; exit = first frame within reach_m of the agent's exit target
