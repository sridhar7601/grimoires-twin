# Agent session 20261017-202931

Model `nvidia/nemotron-3-super-120b-a12b` (NVIDIA hosted) proposed plans; the Grimoires Layer-1 pipeline scored each against all five fires (300 people), each fire averaged over seeds [42, 43, 44]; robust score = worst fire, lower is better. Plausibility floors: alarm >= 5 s, stagger >= 10 s.

Starting point: the 24-variant grid, best `G-E1234-a15-s10` robust **175.7**.

| round | plan proposed | robust score | worst fire | Nemotron's reasoning |
|---|---|---|---|---|
| 1 | `G-E123-a12-s20` | 209.3 | e2_north | Closing exit E4 removes the doorway nearest the e4_west fire, preventing occupants from entering the dense smoke zone; a modestly increased alarm delay allows occupants to finish preparation before movement, and a larger stagger spreads the outflow to avoid bottlenecks at the remaining exits. |
| 2 | `G-E1234-a15-s30` | 248.2 | e2_north | Increasing the stagger spreads departures, reducing congestion at exits especially for the e4_west fire near E4, while keeping the alarm delay moderate to avoid excessive pre-movement exposure. |
| 3 | `G-E1234-a12-s10` | 186.9 | e4_west | Trying a slightly earlier alarm (12 s) with minimal stagger (10 s) while keeping all exits open may reduce the worst‑case exposure to the e4_west fire without increasing congestion. |
| 4 | `G-E1234-a15-s20` | 213.8 | e2_north | The best score so far uses all exits with a moderate alarm (15 s) and tight stagger (10 s). Increasing the stagger to 20 s may reduce congestion at the exits (especially near the e4_west fire) without excessively delaying the start of evacuation. |
| 5 | `G-E134-a15-s10` | 380.4 | e4_west | Exiting via E2 appears detrimental for the e2_north fire; removing E2 while keeping the other three exits may lower the worst‑case exposure, especially if we keep the alarm delay at the proven effective 15 s and a tight stagger of 10 s. |
| 6 | `G-E1234-a10-s20` | 182.1 | e4_west | A slightly earlier alarm (10 s) cuts pre‑movement smoke exposure, while a moderate stagger (15 s) eases congestion at the exits without overly delaying the evacuation start, aiming to lower the worst‑case t90 (currently e4_west) below the current best robust score. |
| 7 | `G-E1234-a20-s10` | 213.3 | e2_north | A slightly longer alarm delay may reduce the number of occupants moving while smoke is still localized, lowering through‑dense‑smoke exposure; keeping the stagger at the minimum 10 s maintains a steady outflow without excessive congestion. |
| 8 | — stopped — | | | |

**Recommended:** `G-E1234-a15-s10` robust **175.7** (from grid). **Approved:** no — PENDING - no terminal; approve with: python3 sim/agent/nemotron_loop.py --approve <session json>.

**Twin check of the recommended plan (2026-10-18, Isaac Sim, 40 characters, doors open, Flow fire, E1 closed by smoke at 21.7 s):** `G-E1234-a15-s10` — t50 / t90 / t100 = 29.0 / 43.0 / 58.8 s, 40 of 40 out, exits E1 11 · E2 3 · E3 13 · E4 13, door crowding 1.0 p/m² (green). The certified grid winner `G-E1234-a5-s25` under the same twin setup: 23.7 / 45.1 / 59.6 s. Layer 1 on the entrance fire: 54.9 s vs 57.3 s. Both layers agree the agent's pick is as good as or slightly better than the certified plan on this fire, and it is the most robust across the five fires. Source: `results/hospital/layer2/layer2_agent_fire.json`, `results/hospital/layer1/rehearse_hospital_agent.json`.
