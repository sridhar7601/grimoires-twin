# Layer 1 — hospital, base vs winner

**Venue:** `hospital_ground_floor_v1` (NVIDIA Isaac Hospital, ground floor, 0.5 m grid, 4 exits) · **Fire:** `hospital_main_entrance` at grid-local [48.75, 6.25] (~4 m inside main entrance E1) · **People:** 300 · **Seed:** 42 · **fps:** 12.0 · **Search:** 24 plan variants (exits ⊇ base × alarm {30,15,5} s × stagger {25,10} s) · **Date:** 2026-10-17

Score = `1.0·t90 + 0.5·exposure_mean + 1000.0·trapped + 5.0·n_dense` (worst case across fires; one fire here).

| metric | before — base plan | after — winner |
|---|---|---|
| plan | G-E12-a30-s25 | G-E1234-a5-s25 |
| exits open | E1 E2 | E1 E2 E3 E4 |
| alarm / stagger | 30 s / 25 s | 5 s / 25 s |
| t50 / t90 / t100 | 81.5 / **135.9** / 173.7 s | 31.3 / **57.3** / 97.1 s |
| exit closed by smoke | E1 @ 21.7 s | E1 @ 21.7 s |
| exits used (people) | E1 23, E2 277 | E1 40, E2 29, E3 105, E4 126 |
| over 30 s smoke threshold | **54** | **6** |
| through dense smoke (people / worst s) | 42 / 26.2 | 22 / 41.7 |
| exposure mean / max | 14.1 / 57.4 s | 2.6 / 54.5 s |
| rerouted / trapped | 1 / 0 | 39 / 0 |
| score (lower is better) | 353.0 | 168.6 |

**Headline:** the fire closes the main entrance at 21.7 s; the base plan then funnels 277 of 300 people through one door. Opening the two wing exits and alarming at 5 s clears 90 % in **57.3 s instead of 135.9 s (−58 %)** and cuts people over the smoke threshold **54 → 6 (−89 %)**. Same fire, same people, same seed.

> **Seed note (added after a 5-seed check).** These numbers are one seed (42). Over 5 seeds this plan ranks 3rd on the entrance fire (score 186.4); the best plan tried is `G-E1234-a15-s10` (167.3). Both open all four exits; the base plan scores 305.4. See `robustness_table.md`.

## Ranked plans (top 5 of 24)

| rank | plan | score | t90 s |
|---|---|---|---|
| 1 | `G-E1234-a5-s25` | 168.6 | 57.3 |
| 2 | `G-E123-a5-s25` | 182.2 | 65.5 |
| 3 | `G-E1234-a15-s10` | 206.3 | 55.0 |
| 4 | `G-E1234-a5-s10` | 216.4 | 54.9 |
| 5 | `G-E123-a15-s10` | 219.1 | 67.4 |

**Why not the fastest t90?** `G-E1234-a5-s10` clears 90 % in 54.9 s (vs 57.3) but sends 32 people through dense smoke instead of 22 — the disclosed score ranks it 4th. The 25 s stagger spreads arrivals so fewer walk into the smoke at the entrance.

## What Layer 2 must confirm (agreement test)

- same ordering: winner t90 < base t90 in the twin;
- same unusable exit: E1 closed by smoke in both layers;
- expect the twin **faster** at crowded doors — Layer 1 models throughput (SFPE 1.3 p/m/s door cap), IRA has no queuing.

## Disclosure

- dynamic smoke-aware egress on a 0.5 m grid with staggered departures; the route field is recomputed every replan_s, smoky routes cost more and dense smoke is avoided; speed falls with smoke level; positions baked as USD time samples. Routing, throughput, timing and exposure only -- people do not collide, so NO density figure is derived or claimed from this run. Smoke is a simplified front model, not fire physics.
- Smoke: grid front model, `{'spread_speed_ms': 0.6, 'ramp_s': 20.0, 'reach_m': 45.0, 's_block': 0.7, 'k_slow': 0.6, 'origin_xy': [48.75, 6.25], 'model': 'front model: arrival by shortest walkable path / spread_speed, level ramps over ramp_s, ceiling 1 - d/reach_m'}` — Flow in the twin is the visual of this same fire.
- Doors treated as openable; perimeter sealed to the four named exits; proxy venue, not a real hospital.
- *Most robust plan among those tried*, not *optimal*. No crowd-density figure is quoted anywhere.

Sources: `grimoires-twin/results/solve_hospital.{json,md}`, `rehearse_hospital_{base,winner}.json`, `tracks_hospital_{base,winner}.json`.
