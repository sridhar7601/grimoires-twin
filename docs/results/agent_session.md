# Agent session 20261017-201101

Model `nvidia/nemotron-3-super-120b-a12b` (NVIDIA hosted) proposed plans; the Grimoires Layer-1 pipeline scored each against all five fires (300 people), each fire averaged over seeds [42, 43, 44]; robust score = worst fire, lower is better. Plausibility floors: alarm >= 5 s, stagger >= 10 s.

Starting point: the 24-variant grid, best `G-E1234-a15-s10` robust **175.7**.

| round | plan proposed | robust score | worst fire | Nemotron's reasoning |
|---|---|---|---|---|
| 1 | `G-E1234-a5-s20` | 188.1 | entrance | Earlier alarm (5 s) starts evacuation sooner, likely reducing t90 and trapped people; a moderate stagger (20 s) spreads departures to lessen simultaneous surge, lowering exposure and dense‑smoke passage compared with very tight or very loose staggers. |
| 2 | `G-E1234-a15-s20` | 213.8 | e2_north | Keeping the alarm at 15 s maintains a reasonable response time while increasing the stagger to 20 s spreads departures more, reducing simultaneous surge and dense‑smoke exposure that drove the worst case in the current best plan. |
| 3 | `G-E123-a5-s25` | (already tried) | | |
| 4 | `G-E1234-a12-s10` | 186.9 | e4_west | A moderate alarm delay (~12 s) balances early start with avoiding congestion, while a low stagger (10 s) keeps departure spread sufficient to reduce dense‑smoke exposure without causing excessive simultaneous flow. |
| 5 | `G-E1234-a8-s18` | 182.3 | entrance | An alarm around 8 s starts evacuation early enough to cut t90 for the e4_west fire, while a stagger of ~18 s spreads departures to lower simultaneous surge and dense‑smoke exposure, aiming for a lower robust score than the current best. |
| 6 | `G-E1234-a20-s10` | 213.3 | e2_north | The current best uses all four exits with a moderate alarm (15 s) and minimal stagger (10 s). Trying a later alarm (20 s) may reduce simultaneous movement and dense‑smoke exposure while still allowing enough time to exit, potentially lowering the worst‑case robust score. |
| 7 | `G-E1234-a13-s10` | 189.4 | e4_west | A slightly earlier alarm (13 s) starts evacuation a bit sooner than the current best, while a modest increase in stagger (12 s) spreads departures enough to reduce simultaneous surge and dense‑smoke exposure, aiming to lower the worst‑case t90 and exposure for the e4_west fire. |
| 8 | `G-E123-a15-s20` | 239.4 | e2_north | Closing E4 removes the exit most compromised in the e4_west fire, reducing people attempting to use a smoky route; keeping alarm at 15 s and increasing stagger to 20 s spreads departures to lower simultaneous surge and dense‑smoke exposure for the remaining exits. |
| 9 | `G-E1234-a12-s15` | 168.9 | e4_west | A slightly earlier alarm (12 s) starts evacuation sooner than the current best, while a moderate increase in stagger (15 s) spreads departures to reduce simultaneous surge and dense‑smoke exposure, aiming to lower the worst‑case t90 and exposure for the e4_west fire. |
| 10 | `G-E1234-a12-s20` | 181.6 | entrance | Increasing the stagger to 20 s spreads departures further, lowering simultaneous surge and dense‑smoke exposure for the e4_west fire, while a 12 s alarm starts evacuation early enough to keep t90 low. |

**Recommended:** `G-E1234-a12-s15` robust **168.9** (from nemotron round 9). **Approved:** no — PENDING - no terminal; approve with: python3 sim/agent/nemotron_loop.py --approve <session json>.

