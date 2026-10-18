# Solve `demo` — 24 plans × 1 fire(s), seed 42

Weights: `{'w_t90': 1.0, 'w_exp': 0.5, 'w_trap': 1000.0, 'w_dense': 5.0}`. Score = worst case across fires; lower is better. Base plan `G12-E123-a30-s25` → winner `G123-E1234-a5-s10`.

## Ranked plans

| rank | plan_id | score_worst | worst_fire | t90_by_fire | trapped_by_fire |
|---|---|---|---|---|---|
| 1 | G123-E1234-a5-s10 | 146.0 | ne_concourse | {'ne_concourse': 124.8} | {'ne_concourse': 0} |
| 2 | G123-E123-a5-s10 | 146.4 | ne_concourse | {'ne_concourse': 125.2} | {'ne_concourse': 0} |
| 3 | G123-E123-a5-s25 | 178.9 | ne_concourse | {'ne_concourse': 173.8} | {'ne_concourse': 0} |
| 4 | G123-E1234-a5-s25 | 178.9 | ne_concourse | {'ne_concourse': 173.8} | {'ne_concourse': 0} |
| 5 | G123-E123-a15-s10 | 202.2 | ne_concourse | {'ne_concourse': 196.5} | {'ne_concourse': 0} |
| 6 | G123-E1234-a15-s10 | 202.2 | ne_concourse | {'ne_concourse': 196.5} | {'ne_concourse': 0} |
| 7 | G12-E123-a15-s10 | 235.8 | ne_concourse | {'ne_concourse': 205.5} | {'ne_concourse': 0} |
| 8 | G12-E1234-a15-s10 | 235.8 | ne_concourse | {'ne_concourse': 205.5} | {'ne_concourse': 0} |
| 9 | G123-E123-a15-s25 | 241.8 | ne_concourse | {'ne_concourse': 220.2} | {'ne_concourse': 0} |
| 10 | G123-E1234-a15-s25 | 241.8 | ne_concourse | {'ne_concourse': 220.2} | {'ne_concourse': 0} |
| 11 | G12-E123-a15-s25 | 257.3 | ne_concourse | {'ne_concourse': 225.8} | {'ne_concourse': 0} |
| 12 | G12-E1234-a15-s25 | 257.3 | ne_concourse | {'ne_concourse': 225.8} | {'ne_concourse': 0} |
| 13 | G123-E123-a30-s10 | 296.2 | ne_concourse | {'ne_concourse': 243.0} | {'ne_concourse': 0} |
| 14 | G123-E1234-a30-s10 | 296.2 | ne_concourse | {'ne_concourse': 243.0} | {'ne_concourse': 0} |
| 15 | G12-E123-a30-s10 | 300.2 | ne_concourse | {'ne_concourse': 247.0} | {'ne_concourse': 0} |
| 16 | G12-E1234-a30-s10 | 300.2 | ne_concourse | {'ne_concourse': 247.0} | {'ne_concourse': 0} |
| 17 | G123-E123-a30-s25 | 301.5 | ne_concourse | {'ne_concourse': 226.2} | {'ne_concourse': 0} |
| 18 | G123-E1234-a30-s25 | 301.5 | ne_concourse | {'ne_concourse': 226.2} | {'ne_concourse': 0} |
| 19 | G12-E123-a30-s25 | 324.4 | ne_concourse | {'ne_concourse': 249.2} | {'ne_concourse': 0} |
| 20 | G12-E1234-a30-s25 | 324.4 | ne_concourse | {'ne_concourse': 249.2} | {'ne_concourse': 0} |
| 21 | G12-E123-a5-s25 | 362.4 | ne_concourse | {'ne_concourse': 176.8} | {'ne_concourse': 0} |
| 22 | G12-E1234-a5-s25 | 363.5 | ne_concourse | {'ne_concourse': 177.8} | {'ne_concourse': 0} |
| 23 | G12-E123-a5-s10 | 602.5 | ne_concourse | {'ne_concourse': 129.0} | {'ne_concourse': 0} |
| 24 | G12-E1234-a5-s10 | 619.0 | ne_concourse | {'ne_concourse': 130.5} | {'ne_concourse': 0} |


## Before → after on fire `ne_concourse` (same seed)

| metric | before (base) | after (winner) |
|---|---|---|
| t50_s | 163.8 | 82.0 |
| t90_s | 249.2 | 124.8 |
| t100_s | 270.2 | 145.0 |
| trapped | 0 | 0 |
| rerouted | 108 | 149 |
| exposure_mean_s | 20.5 | 12.4 |
| exposure_max_s | 55.7 | 55.5 |
| n_over_exposure_threshold | 105 | 49 |
| n_in_dense_smoke | 13 | 3 |
| dense_smoke_max_s | 8.8 | 21.2 |
| exit_throughput_total | {'E1': 428, 'E2': 0, 'E3': 0} | {'E1': 228, 'E2': 198, 'E3': 0, 'E4': 2} |
| gate_throughput_total | {'G1': 428, 'G2': 0} | {'G1': 182, 'G2': 20, 'G3': 226} |
| exit_peak_rate_ps | {'E1': 2.2, 'E2': 0.0, 'E3': 0.0} | {'E1': 2.2, 'E2': 2.2, 'E3': 0.0, 'E4': 0.4} |
| corridor_closed_at_s | {'G1': None, 'G2': 23.6, 'E1': None, 'E2': None, 'E3': None} | {'G1': None, 'G2': 23.6, 'G3': None, 'E1': None, 'E2': None, 'E3': None, 'E4': None} |
| score | 324.4 | 146.0 |


## Disclosure

> dynamic smoke-aware egress on a 0.5 m grid with staggered departures; the route field is recomputed every replan_s, smoky routes cost more and dense smoke is avoided; speed falls with smoke level; positions baked as USD time samples. Routing, throughput, timing and exposure only -- people do not collide, so NO density figure is derived or claimed from this run. Smoke is a simplified front model, not fire physics.

> Smoke params: `{'spread_speed_ms': 0.6, 'ramp_s': 20.0, 'reach_m': 45.0, 's_block': 0.7, 'k_slow': 0.6, 'origin_xy': [44.0, 17.0], 'model': 'front model: arrival by shortest walkable path / spread_speed, level ramps over ramp_s, ceiling 1 - d/reach_m'}`
