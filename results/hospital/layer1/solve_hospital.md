# Solve `hospital` — 24 plans × 1 fire(s), seed 42

Weights: `{'w_t90': 1.0, 'w_exp': 0.5, 'w_trap': 1000.0, 'w_dense': 5.0}`. Score = worst case across fires; lower is better. Base plan `G-E12-a30-s25` → winner `G-E1234-a5-s25`.

## Ranked plans

| rank | plan_id | score_worst | worst_fire | t90_by_fire | trapped_by_fire |
|---|---|---|---|---|---|
| 1 | G-E1234-a5-s25 | 168.6 | hospital_main_entrance | {'hospital_main_entrance': 57.3} | {'hospital_main_entrance': 0} |
| 2 | G-E123-a5-s25 | 182.2 | hospital_main_entrance | {'hospital_main_entrance': 65.5} | {'hospital_main_entrance': 0} |
| 3 | G-E1234-a15-s10 | 206.3 | hospital_main_entrance | {'hospital_main_entrance': 55.0} | {'hospital_main_entrance': 0} |
| 4 | G-E1234-a5-s10 | 216.4 | hospital_main_entrance | {'hospital_main_entrance': 54.9} | {'hospital_main_entrance': 0} |
| 5 | G-E123-a15-s10 | 219.1 | hospital_main_entrance | {'hospital_main_entrance': 67.4} | {'hospital_main_entrance': 0} |
| 6 | G-E124-a5-s25 | 229.3 | hospital_main_entrance | {'hospital_main_entrance': 96.0} | {'hospital_main_entrance': 0} |
| 7 | G-E123-a5-s10 | 234.3 | hospital_main_entrance | {'hospital_main_entrance': 67.6} | {'hospital_main_entrance': 0} |
| 8 | G-E1234-a15-s25 | 245.8 | hospital_main_entrance | {'hospital_main_entrance': 68.6} | {'hospital_main_entrance': 0} |
| 9 | G-E12-a5-s25 | 247.9 | hospital_main_entrance | {'hospital_main_entrance': 109.7} | {'hospital_main_entrance': 0} |
| 10 | G-E124-a15-s10 | 249.0 | hospital_main_entrance | {'hospital_main_entrance': 95.5} | {'hospital_main_entrance': 0} |
| 11 | G-E123-a15-s25 | 256.4 | hospital_main_entrance | {'hospital_main_entrance': 78.8} | {'hospital_main_entrance': 0} |
| 12 | G-E12-a15-s10 | 263.1 | hospital_main_entrance | {'hospital_main_entrance': 109.7} | {'hospital_main_entrance': 0} |
| 13 | G-E124-a5-s10 | 273.2 | hospital_main_entrance | {'hospital_main_entrance': 90.2} | {'hospital_main_entrance': 0} |
| 14 | G-E1234-a30-s10 | 276.5 | hospital_main_entrance | {'hospital_main_entrance': 73.7} | {'hospital_main_entrance': 0} |
| 15 | G-E123-a30-s10 | 286.0 | hospital_main_entrance | {'hospital_main_entrance': 83.0} | {'hospital_main_entrance': 0} |
| 16 | G-E12-a5-s10 | 292.5 | hospital_main_entrance | {'hospital_main_entrance': 104.4} | {'hospital_main_entrance': 0} |
| 17 | G-E124-a15-s25 | 297.8 | hospital_main_entrance | {'hospital_main_entrance': 107.8} | {'hospital_main_entrance': 0} |
| 18 | G-E1234-a30-s25 | 300.1 | hospital_main_entrance | {'hospital_main_entrance': 86.2} | {'hospital_main_entrance': 0} |
| 19 | G-E123-a30-s25 | 307.4 | hospital_main_entrance | {'hospital_main_entrance': 93.5} | {'hospital_main_entrance': 0} |
| 20 | G-E12-a15-s25 | 311.2 | hospital_main_entrance | {'hospital_main_entrance': 121.4} | {'hospital_main_entrance': 0} |
| 21 | G-E124-a30-s10 | 324.9 | hospital_main_entrance | {'hospital_main_entrance': 113.8} | {'hospital_main_entrance': 0} |
| 22 | G-E124-a30-s25 | 338.6 | hospital_main_entrance | {'hospital_main_entrance': 121.4} | {'hospital_main_entrance': 0} |
| 23 | G-E12-a30-s10 | 338.8 | hospital_main_entrance | {'hospital_main_entrance': 127.8} | {'hospital_main_entrance': 0} |
| 24 | G-E12-a30-s25 | 353.0 | hospital_main_entrance | {'hospital_main_entrance': 135.9} | {'hospital_main_entrance': 0} |


## Before → after on fire `hospital_main_entrance` (same seed)

| metric | before (base) | after (winner) |
|---|---|---|
| t50_s | 81.5 | 31.3 |
| t90_s | 135.9 | 57.3 |
| t100_s | 173.7 | 97.1 |
| trapped | 0 | 0 |
| rerouted | 1 | 39 |
| exposure_mean_s | 14.1 | 2.6 |
| exposure_max_s | 57.4 | 54.5 |
| n_over_exposure_threshold | 54 | 6 |
| n_in_dense_smoke | 42 | 22 |
| dense_smoke_max_s | 26.2 | 41.7 |
| exit_throughput_total | {'E1': 23, 'E2': 277} | {'E1': 40, 'E2': 29, 'E3': 105, 'E4': 126} |
| gate_throughput_total | {} | {} |
| exit_peak_rate_ps | {'E1': 1.6, 'E2': 4.2} | {'E1': 2.4, 'E2': 2.2, 'E3': 3.2, 'E4': 4.2} |
| corridor_closed_at_s | {'E1': 21.7, 'E2': None} | {'E1': 21.7, 'E2': None, 'E3': None, 'E4': None} |
| score | 353.0 | 168.6 |


## Disclosure

> dynamic smoke-aware egress on a 0.5 m grid with staggered departures; the route field is recomputed every replan_s, smoky routes cost more and dense smoke is avoided; speed falls with smoke level; positions baked as USD time samples. Routing, throughput, timing and exposure -- people queue at the SFPE door cap but do not collide, so door_crowding is DEMAND at the door (crush-risk flag), never a crush prediction. Smoke is a simplified front model, not fire physics.

> Smoke params: `{'spread_speed_ms': 0.6, 'ramp_s': 20.0, 'reach_m': 45.0, 's_block': 0.7, 'k_slow': 0.6, 'origin_xy': [48.75, 6.25], 'model': 'front model: arrival by shortest walkable path / spread_speed, level ramps over ramp_s, ceiling 1 - d/reach_m'}`
