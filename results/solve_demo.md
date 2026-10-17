# Solve `demo` — 24 plans × 1 fire(s), seed 42

Weights: `{'w_t90': 1.0, 'w_exp': 0.5, 'w_trap': 1000.0, 'w_dense': 5.0}`. Score = worst case across fires; lower is better. Base plan `G12-E123-a30-s25` → winner `G123-E123-a5-s10`.

## Ranked plans

| rank | plan_id | score_worst | worst_fire | t90_by_fire | trapped_by_fire |
|---|---|---|---|---|---|
| 1 | G123-E123-a5-s10 | 84.6 | ne_concourse | {'ne_concourse': 67.5} | {'ne_concourse': 0} |
| 2 | G123-E1234-a5-s10 | 84.7 | ne_concourse | {'ne_concourse': 67.5} | {'ne_concourse': 0} |
| 3 | G123-E123-a5-s25 | 94.2 | ne_concourse | {'ne_concourse': 91.0} | {'ne_concourse': 0} |
| 4 | G123-E1234-a5-s25 | 94.4 | ne_concourse | {'ne_concourse': 91.2} | {'ne_concourse': 0} |
| 5 | G123-E123-a15-s10 | 94.7 | ne_concourse | {'ne_concourse': 91.0} | {'ne_concourse': 0} |
| 6 | G123-E1234-a15-s10 | 94.7 | ne_concourse | {'ne_concourse': 91.0} | {'ne_concourse': 0} |
| 7 | G12-E123-a15-s10 | 120.0 | ne_concourse | {'ne_concourse': 91.8} | {'ne_concourse': 0} |
| 8 | G12-E1234-a15-s10 | 120.0 | ne_concourse | {'ne_concourse': 91.8} | {'ne_concourse': 0} |
| 9 | G123-E123-a15-s25 | 125.9 | ne_concourse | {'ne_concourse': 106.2} | {'ne_concourse': 0} |
| 10 | G123-E1234-a15-s25 | 125.9 | ne_concourse | {'ne_concourse': 106.2} | {'ne_concourse': 0} |
| 11 | G12-E123-a15-s25 | 135.6 | ne_concourse | {'ne_concourse': 106.2} | {'ne_concourse': 0} |
| 12 | G12-E1234-a15-s25 | 135.6 | ne_concourse | {'ne_concourse': 106.2} | {'ne_concourse': 0} |
| 13 | G123-E123-a30-s10 | 162.2 | ne_concourse | {'ne_concourse': 111.2} | {'ne_concourse': 0} |
| 14 | G123-E1234-a30-s10 | 162.2 | ne_concourse | {'ne_concourse': 111.2} | {'ne_concourse': 0} |
| 15 | G12-E123-a30-s10 | 162.3 | ne_concourse | {'ne_concourse': 111.5} | {'ne_concourse': 0} |
| 16 | G12-E1234-a30-s10 | 162.3 | ne_concourse | {'ne_concourse': 111.5} | {'ne_concourse': 0} |
| 17 | G123-E123-a30-s25 | 189.1 | ne_concourse | {'ne_concourse': 115.2} | {'ne_concourse': 0} |
| 18 | G123-E1234-a30-s25 | 189.1 | ne_concourse | {'ne_concourse': 115.2} | {'ne_concourse': 0} |
| 19 | G12-E123-a30-s25 | 193.3 | ne_concourse | {'ne_concourse': 119.8} | {'ne_concourse': 0} |
| 20 | G12-E1234-a30-s25 | 193.3 | ne_concourse | {'ne_concourse': 119.8} | {'ne_concourse': 0} |
| 21 | G12-E123-a5-s25 | 279.5 | ne_concourse | {'ne_concourse': 95.5} | {'ne_concourse': 0} |
| 22 | G12-E1234-a5-s25 | 279.6 | ne_concourse | {'ne_concourse': 95.5} | {'ne_concourse': 0} |
| 23 | G12-E123-a5-s10 | 552.0 | ne_concourse | {'ne_concourse': 81.8} | {'ne_concourse': 0} |
| 24 | G12-E1234-a5-s10 | 567.2 | ne_concourse | {'ne_concourse': 81.8} | {'ne_concourse': 0} |


## Before → after on fire `ne_concourse` (same seed)

| metric | before (base) | after (winner) |
|---|---|---|
| t50_s | 90.8 | 42.8 |
| t90_s | 119.8 | 67.5 |
| t100_s | 148.5 | 111.8 |
| trapped | 0 | 0 |
| rerouted | 108 | 129 |
| exposure_mean_s | 17.0 | 4.2 |
| exposure_max_s | 52.6 | 39.4 |
| n_over_exposure_threshold | 85 | 2 |
| n_in_dense_smoke | 13 | 3 |
| dense_smoke_max_s | 8.8 | 21.2 |
| exit_throughput_total | {'E1': 428, 'E2': 0, 'E3': 0} | {'E1': 229, 'E2': 199, 'E3': 0} |
| gate_throughput_total | {'G1': 428, 'G2': 0} | {'G1': 182, 'G2': 15, 'G3': 231} |
| exit_peak_rate_ps | {'E1': 10.8, 'E2': 0.0, 'E3': 0.0} | {'E1': 11.0, 'E2': 12.4, 'E3': 0.0} |
| corridor_closed_at_s | {'G1': None, 'G2': 23.6, 'E1': None, 'E2': None, 'E3': None} | {'G1': None, 'G2': 23.6, 'G3': None, 'E1': None, 'E2': None, 'E3': None} |
| score | 193.3 | 84.6 |


## Disclosure

> dynamic smoke-aware egress on a 0.5 m grid with staggered departures; the route field is recomputed every replan_s, smoky routes cost more and dense smoke is avoided; speed falls with smoke level; positions baked as USD time samples. Routing, throughput, timing and exposure only -- people do not collide, so NO density figure is derived or claimed from this run. Smoke is a simplified front model, not fire physics.

> Smoke params: `{'spread_speed_ms': 0.6, 'ramp_s': 20.0, 'reach_m': 45.0, 's_block': 0.7, 'k_slow': 0.6, 'origin_xy': [44.0, 17.0], 'model': 'front model: arrival by shortest walkable path / spread_speed, level ramps over ramp_s, ceiling 1 - d/reach_m'}`
