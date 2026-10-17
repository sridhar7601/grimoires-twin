# Agent session 20261017-194108

Model `nvidia/nemotron-3-super-120b-a12b` (NVIDIA hosted) proposed plans; the Grimoires Layer-1 pipeline scored each against all five fires (300 people, seed 42); robust score = worst fire, lower is better.

Starting point: the 24-variant grid, best `G-E123-a5-s25` robust **182.8**.

| round | plan proposed | robust score | worst fire | Nemotron's reasoning |
|---|---|---|---|---|
| 1 | `G-E134-a5-s25` | 401.1 | e4_west | The worst fire for the current best plan is near E2; closing that exit removes exposure to its smoke while still providing three exits for redundancy. Keeping a short alarm delay (5 s) starts evacuation early, and a moderate stagger (25 s) avoids bottlenecks at the remaining exits. |
| 2 | `G-E123-a12-s15` | 195.9 | entrance | Adding E3 gives a third exit that is away from both E2 and E4 fires, providing redundancy when either wing exit is compromised. A modest alarm delay (12 s) lets occupants finish initial activities before moving, reducing early entry into smoke, while a moderate stagger (15 s) limits bottlenecks at the exits. |
| 3 | `G-E123-a0-s15` | 238.9 | entrance | Zero alarm starts evacuation immediately, before smoke from the e2_north fire can heavily impair exit E2; a modest stagger of 15 s avoids bottlenecks at the remaining exits while retaining three‑way redundancy. |
| 4 | `G-E13-a5-s25` | 362.9 | e4_west | Closing E2 and E4 removes exits that are directly vulnerable to the e2_north and e4_west fires, leaving E1 and E3 as opposite‑corner exits that provide redundancy when any single fire blocks one wing. Keeping a short alarm delay (5 s) starts evacuation early, and a moderate stagger (25 s) avoids bottlenecks at the two remaining exits. |
| 5 | `G-E1234-a0-s5` | 150.0 | entrance | An immediate alarm (0 s) and a very tight stagger (5 s) gets occupants moving and out before smoke from any fire can accumulate heavily, while keeping all four exits open provides maximum redundancy so that no single fire can block a major escape route. |
| 6 | `G-E234-a0-s5` | 261.8 | e4_west | Closing the entrance (E1) removes the worst‑case fire location from affecting evacuation, while keeping the three other exits provides redundancy. Zero alarm starts evacuation immediately, and a small stagger of 5 s avoids bottlenecks at the remaining exits. |
| 7 | `G-E1234-a0-s0` | 110.3 | entrance | The entrance fire (E1) drove the worst case in the current best plan. Keeping all exits open provides redundancy, zero alarm starts evacuation immediately, and reducing stagger to zero minimizes the time people spend in the lobby smoke while still avoiding collisions (per the simulator's assumptions). |
| 8 | `G-E1234-a2-s2` | 165.3 | entrance | A tiny alarm delay (2 s) and a minimal stagger (2 s) smooth the initial outflow, lowering peak density in the lobby and thus reducing smoke exposure and traversal of dense smoke while keeping all exits open for redundancy. |

**Recommended:** `G-E1234-a0-s0` robust **110.3** (from nemotron round 7). **Approved:** no — PENDING - no terminal; approve with: python3 sim/agent/nemotron_loop.py --approve <session json>.

