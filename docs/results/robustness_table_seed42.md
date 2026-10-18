# Layer 1 — robustness sweep (hospital)

**120 rehearsals** = 24 plan variants × 5 fire origins · 300 people · seed 42 · fps 12.0 · 81.5 s wall-clock · 2026-10-17. Rank = **worst-case** score across the fires (`1.0·t90 + 0.5·exposure_mean + 1000.0·trapped + 5.0·n_dense`). Fire origins (world m): `main_entrance` (-1.25, 1.25); `e2_north` (-39.25, 28.75); `e3_east` (16.25, 31.25); `e4_west` (-42.75, 8.75); `central` (-15.25, 11.75).

## Headline

- The base plan `G-E12-a30-s25` ranks **24 of 24 — last under every fire**; its worst case is the entrance fire (t90 135.9 s).
- Most robust plan among those tried: **`G-E123-a5-s25`** — worst-case score 182.8 (fire `e2_north`), t90 never above 66.6 s.
- The single-fire winner `G-E1234-a5-s25` is **2nd**: best on 4 of 5 fires, but a fire inside E4 is its weak spot (opening E4 routes people toward that fire). Robustness changes the recommendation — say so on the slide.
- No plan traps anyone under any of the five fires.

## t90 (s) by fire, selected plans

| plan | main_entrance | e2_north | e3_east | e4_west | central | worst score (fire) | rank |
|---|---|---|---|---|---|---|---|
| `G-E12-a30-s25` | 135.9 | 104.6 | 94.2 | 96.3 | 90.3 | **353.0** (main_entrance) | 24 |
| `G-E1234-a5-s25` | 57.3 | 45.2 | 49.2 | 56.3 | 44.2 | **202.5** (e4_west) | 2 |
| `G-E123-a5-s25` | 65.5 | 66.6 | 55.1 | 55.6 | 49.8 | **182.8** (e2_north) | 1 |

## Full ranking (worst-case score)

| rank | plan | worst score | worst fire |
|---|---|---|---|
| 1 | `G-E123-a5-s25` | 182.8 | e2_north |
| 2 | `G-E1234-a5-s25` | 202.5 | e4_west |
| 3 | `G-E1234-a15-s10` | 206.3 | main_entrance |
| 4 | `G-E123-a15-s10` | 219.1 | main_entrance |
| 5 | `G-E1234-a5-s10` | 221.9 | e4_west |
| 6 | `G-E124-a5-s25` | 229.3 | main_entrance |
| 7 | `G-E123-a5-s10` | 234.3 | main_entrance |
| 8 | `G-E1234-a15-s25` | 245.8 | main_entrance |
| 9 | `G-E12-a5-s25` | 247.9 | main_entrance |
| 10 | `G-E124-a15-s10` | 249.0 | main_entrance |
| 11 | `G-E123-a15-s25` | 256.4 | main_entrance |
| 12 | `G-E12-a15-s10` | 263.1 | main_entrance |
| 13 | `G-E124-a5-s10` | 273.2 | main_entrance |
| 14 | `G-E1234-a30-s10` | 285.5 | e2_north |
| 15 | `G-E12-a5-s10` | 292.5 | main_entrance |
| 16 | `G-E124-a15-s25` | 297.8 | main_entrance |
| 17 | `G-E1234-a30-s25` | 304.6 | e2_north |
| 18 | `G-E123-a30-s10` | 306.9 | e2_north |
| 19 | `G-E12-a15-s25` | 311.2 | main_entrance |
| 20 | `G-E123-a30-s25` | 321.5 | e2_north |
| 21 | `G-E124-a30-s10` | 324.9 | main_entrance |
| 22 | `G-E124-a30-s25` | 338.6 | main_entrance |
| 23 | `G-E12-a30-s10` | 338.8 | main_entrance |
| 24 | `G-E12-a30-s25` | 353.0 | main_entrance |

## Disclosure

- Same grid smoke model and routing as `layer1_table.md`; only the fire origin varies. Plan knobs only — people, seed, spread speed held fixed.
- *Most robust among those tried* (24 plans, 5 origins), not optimal. No crowd-density figure is quoted.
- The twin (Layer 2) rehearses the **demo-fire** pair (base vs `G-E1234-a5-s25`) — the certificate is per fire; this table is the robustness view on top.

Source: `grimoires-twin/results/solve_hospital_robust.{json,md}`; fires in `grimoires-twin/scenarios/hospital_fire_*.json`.
