# Layer 1 — robustness sweep (hospital), 5 seeds

**600 rehearsals** = 24 plan variants × 5 fire origins × 5 seeds (42–46) · 300 people · fps 12 · 2026-10-17. Per fire, a plan's score is the **mean over the 5 seeds**; its robust score is its **worst fire**. Score = `1·t90 + 0.5·exposure_mean + 1000·trapped + 5·through_dense_smoke`, lower is better.

> **Correction.** The first version of this table (kept as `robustness_table_seed42.md`) scored one seed and named `G-E123-a5-s25` most robust. Over 5 seeds that plan ranks 4th; the single-seed ranking among the top plans was noise. What did not change: the base plan is last, by about 2×, and every top plan opens E3 (the east-wing exit the base plan leaves shut); the best open all four.

## Headline

- Base plan `G-E12-a30-s25`: robust score **331.7**, rank **24/24** — last.
- Most robust plan among those tried: **`G-E1234-a15-s10`** (all four exits, alarm 15 s, stagger 10 s) — **167.3**, about **2.0× better** than base on its worst fire.
- The plan certified in the Isaac twin, `G-E1234-a5-s25`, ranks **3** (186.4) — same exits, different alarm/stagger; the twin comparison (base vs this plan) still holds.
- Every plan in the top 4 opens E3; the top 1 and 3 open all four exits. Alarm and stagger are second-order: differences of ~10–20 points between the top plans are within seed spread.
- No plan traps anyone under any fire or seed.

## t90 (s, mean of 5 seeds) by fire — top 6 and base

| rank | plan | central | e2_north | e3_east | e4_west | entrance | robust score (worst fire) |
|---|---|---|---|---|---|---|---|
| 1 | `G-E1234-a15-s10` | 46.6 | 47.4 | 53.6 | 58.0 | 55.1 | **167.3** (entrance) |
| 2 | `G-E123-a15-s10` | 52.9 | 71.3 | 62.1 | 60.6 | 63.9 | **182.5** (e2_north) |
| 3 | `G-E1234-a5-s25` | 44.7 | 45.4 | 50.5 | 54.9 | 57.0 | **186.4** (entrance) |
| 4 | `G-E123-a5-s25` | 50.2 | 66.0 | 56.7 | 54.9 | 65.4 | **198.2** (entrance) |
| 5 | `G-E124-a15-s10` | 60.8 | 60.6 | 58.6 | 72.3 | 96.1 | **212.7** (entrance) |
| 6 | `G-E12-a15-s10` | 67.2 | 86.5 | 67.2 | 74.3 | 110.6 | **227.0** (entrance) |
| 24 | `G-E12-a30-s25` (base) | 91.0 | 105.9 | 95.3 | 97.8 | 138.3 | **331.7** (e2_north) |

## Entrance fire only (the certificate's fire), 5 seeds

| rank | plan | t90 s | score |
|---|---|---|---|
| 1 | `G-E1234-a15-s10` | 55.1 | 167.3 |
| 2 | `G-E123-a15-s10` | 63.9 | 176.3 |
| 3 | `G-E1234-a5-s25` | 57.0 | 186.4 |
| 4 | `G-E123-a5-s25` | 65.4 | 198.2 |
| 23 | `G-E12-a30-s25` (base) | 138.3 | 305.4 |

## Disclosure

- Same grid smoke model and routing as `layer1_table.md`; only fire origin and seed vary. Plan knobs only.
- *Most robust among those tried* (24 plans × 5 fires × 5 seeds), not optimal. No crowd-density figure is quoted.

Source: `results/hospital/layer1/solve_hospital_multiseed.json` (`sim/agent/tools.py grid_search`, seeds 42–46).
