# Grimoires — the Evacuation Plan Certificate

**Written:** 2026-10-16 · **Owner:** Sridhar S K · **Status:** solver proven; twin rehearsal not yet built on the new venue
**Context files:** [`../00-OVERVIEW.md`](../00-OVERVIEW.md) · [`../01-grimories.md`](../01-grimories.md) (background) · [`../06-grimoires-build-spec.md`](../06-grimoires-build-spec.md) (original locked spec — superseded where this file differs) · [`../11-bankai-handoff.md`](../11-bankai-handoff.md) (boundary with Bankai)
**Plan:** [`PLAN.md`](PLAN.md)

---

## One sentence

> Give Grimoires a venue and its evacuation plan; it rehearses a fire, scores the plan with hard numbers, **searches many plan variants and ranks them**, then **proves the winner in a physical twin** — NVIDIA characters path-finding through the real building with real smoke — and hands back a certificate: **where the plan fails, the fix, and before → after on the same fire.**

## The core idea — a fast planner and a physical twin that must agree

A simulation that shows people evacuating is a viewer; Pathfinder does that. The thing nobody else does is **automatic search over plan variants, then physical confirmation in a twin**. The planner is fast and simplified; the twin is slow and physical. Where they agree you have a defensible plan; where they disagree you have found something the planner missed.

| Layer | Question | How it is measured | Who else can do this |
|---|---|---|---|
| 1. **Fast search** | Of N plan variants, which clears the building fastest with least smoke exposure? | Our Python grid solver (`solve.py`): routing + smoke front + SFPE door-flow cap, every variant in seconds | Evac tools score *one* plan at a time by hand — nobody searches |
| 2. **Physical rehearsal** | Does the winner survive real geometry and real smoke? | **Isaac Sim**: IRA characters on a baked NavMesh, `MoveTo` their exit when the alarm fires, Flow smoke at the origin; Replicator per-frame 3D positions → clearance measured in the twin | Nobody — needs GPU path-finding + physics in one scene |
| 3. **The certificate** | Base vs winner, same fire, same seed, in both layers | Side-by-side tables + the film | Nobody |

**Pitch line:** *"Your plan sends everyone to the front doors. The fire kills the east door at 20 s and 800 people queue for 3½ minutes. Open the two side exits and alarm earlier: out in one minute, 85 % less smoke exposure — and the twin confirms it."*

**Proven already (mall, Python layer):** base `E1+E2, alarm 30 s` → t90 **203.6 s**, **188** people over the 30 s smoke threshold, E2 closed at 19.8 s · winner `E1–E4, alarm 5 s` → t90 **61.0 s**, **29** over threshold. Same 800 people, same fire, same seed.

## Pitch scene

**Fire evacuation in a hospital** — NVIDIA's `Isaac/Environments/Hospital/hospital.usd`. Clean mesh (IRA's NavMesh bakes on NVIDIA environments; proven on the warehouse), visually distinct from Bankai's warehouse, and the most consequential setting we have: wards, long corridors, few exits.

The imported mall stays as an optional custom-venue demo *only if* its NavMesh passes the engineer's inspection checklist (PLAN Phase 0d). **No cameras anywhere in this pitch** — one flythrough for the film, nothing else (boundary with Bankai).

## Business hook

Fire safety officers and venue operators must sign off evacuation plans they have never seen tested. Drills with real crowds are expensive, disruptive, rare. The certificate gives them: the weak point, the cheapest fix, and proof — before the day it matters. Honest claim: *the most robust plan among those tried*, never *the optimal plan*.

---

## Architecture

```
Venue USD  ──► mall_plan.py (slice to 0.5 m grid, pick exits)  ──► venue grid JSON
                                                                        │
Plan knobs (plan.py): exits_open, alarm_delay_s, stagger_s, route_bias  │
                                                                        ▼
LAYER 1  FAST SEARCH (CPU; Warp port optional)
   solve.py → rehearse.py per variant: Dijkstra routing, smoke front, door cap, exposure
   → ranked variants → BASE + WINNER                                    (seconds)
                                                                        │
                                                                        ▼
LAYER 2  PHYSICAL REHEARSAL — Isaac Sim 6.0.1, GPU 0            (minutes, 2 runs)
   IRA: N characters spawn on the NavMesh; behaviour tree = Idle → (alarm time_trigger) → MoveTo <exit>
        exit assignment per zone comes from the winning plan
   Omniverse Flow: smoke volume at the fire origin (visual; density read-back tested in Phase 4)
   PhysX: optional debris / blocked corridor (second hazard)
   Replicator: 3D box centre per agent per frame  →  "reached exit" when within 1.5 m of its exit prim
   → clearance curve, exits used, smoke-blocked routes — measured IN THE TWIN
                                                                        │
                                                                        ▼
LAYER 3  CERTIFICATE
   base vs winner: Layer-1 numbers | Layer-2 numbers | agreement
   RTX flythrough → MP4 · Cosmos Reason 2 narrates · Nemotron proposes the next variant
   Phase 7: NemoClaw / Hermes drives solve → rehearse → score autonomously
```

### NVIDIA tool per stage (name these on the slide)

| Stage | NVIDIA tool |
|---|---|
| World | OpenUSD, Isaac Sim 6.0.1 container, NVIDIA Hospital environment |
| People | Isaac Replicator Agent — NavMesh (`omni.anim.navigation`) + behaviour tree (`omni.anim.behavior.tree`: `MoveTo`, time trigger) |
| Hazard | Omniverse Flow (`omni.flowusd`) smoke; PhysX for debris |
| Measurement | Replicator `object_detection_*.json` (3D boxes per agent per frame) |
| Speed (optional) | Warp (`omni.warp.core`) port of the grid sweep for thousands of fire origins × plans |
| Narration | Cosmos Reason 2 8B NIM (already running on GPU 1) |
| Planner / agent | Nemotron (hosted) proposes variants; NemoClaw / Hermes drives the loop |
| Film | RTX path-traced flythrough → MP4 |

### Hazard & people modelling — the honest version

| Piece | How | Confidence | Phase |
|---|---|---|---|
| Smoke for the **numbers** | Our grid front model (`smoke.py`): spread speed, ramp, reach, block threshold, all parameters printed in every report | ✅ done | — |
| Smoke in the **twin** (visual) | Flow volume at the same origin, same start time | High — extension is in the container | 4 |
| Smoke **driving** the twin | Sample Flow density at agent positions → raise NavMesh area cost / close exits | **Unknown** — engineer question went unasked; `omni.flowusd` Python nodes logged a registration failure | 4 (test; fallback = grid smoke drives, Flow is the visual) |
| People path-finding | IRA NavMesh + `MoveTo` — real geometry, doorways, obstacles | ✅ hospital verified 2026-10-17 (needs the NavMesh-cap patch in `sim/ira/patches/`, see PLAN Phase 0 outcome) | 0, 2 |
| **Crowd congestion** | Python has the SFPE door cap (1.3 p/m/s); **IRA has no collision or queuing** | Known gap — stated on the slide | — |
| Debris / blocked corridor | PhysX bodies dropped at alarm time | High | 4 (optional) |
| Multi-origin robustness | Sweep fire origins × plans in Python; Warp if time | Python high; Warp medium | 5 |

**The congestion caveat, said plainly:** Layer 1 models *throughput* (doors as bottlenecks); Layer 2 models *routing and geometry* (do paths exist, how long, what smoke closes). They are complementary. Expect Layer 2 clearance to be *faster* than Layer 1 at crowded doors, and say why.

### Measurement definitions (keep these exact in the pitch)

- **t50 / t90 / t100** = time when 50 / 90 / 100 % of people have exited. Layer 1: from `rehearse.py`. Layer 2: first frame each agent's position is within **1.5 m** of its exit prim; frame → seconds via the writer's fixed step.
- **Layer-2 position source (decided 2026-10-17):** IRA's per-agent `metro_agent_data.world_position` (exact, with `speed`), **not** camera 3D boxes — `object_detection_*.json` only lists agents visible to that camera (3 of 10 walkers across 3 cameras in Phase 0). Phase 2d needs a camera-independent per-frame dump of every agent's position; the RGB cameras serve the film only.
- **Exit saturated** (never "crush"): Layer 1 door queue length > 0 for > 10 s. No density figure is ever quoted — people do not collide in either layer.
- **Exposure** (Layer 1 only) = ∫ smoke level at the person's cell dt; **over threshold** = exposure > 30 s.
- **Corridor / exit closed** = smoke level above `s_block` on the opening's cells (Layer 1) · Flow density above threshold at the exit prim (Layer 2, if read-back works).
- **Agreement** = same ordering of base vs winner on t90 in both layers, and both layers report the same exits as unusable.
- **Fix** = a plan-knob change only (exits opened, alarm earlier, stagger shorter, route bias). Fire origin, spread, people count and seed are **held fixed**.

---

## Compute

- NVIDIA LaunchPad, **2× L40S 46 GB, 1 TB host RAM**. SSH: `ssh -i ~/.ssh/launchpad -p 12313 nvidia@global.prd.ga.launchpad.nvidia.com`.
- **GPU 0 = Isaac (IRA, render), GPU 1 = Cosmos Reason 2 NIM** (`--gpus '"device=1"'`, `:8000`). One Kit process at a time.
- Project on box: `~/Documents/grimoires-twin`. `scp` for multi-file copies.
- Container uid 1234: write to `chmod 777` dirs or `chown -R 1234:1234`. `sudo` strips env — pass `-e NGC_API_KEY="$NGC_API_KEY"`.
- IRA's NavMesh bake has a **hardcoded 100-frame limit** (`omni.metropolis.pipeline/simulation_util.py:74`); the hospital needs it — patched copy versioned at `grimoires/sim/ira/patches/simulation_util.py`, bind-mount per its header.

## Reusable code

| File | Reuse for |
|---|---|
| `../grimoires-twin/sim/plan.py`, `solve.py`, `rehearse.py`, `smoke.py`, `grid.py` | Layer 1 as-is |
| `../grimoires-twin/sim/mall_plan.py` | Slice **any** venue USD into the grid + cut exits (`--doors`) |
| `../grimoires-twin/sim/ira/ira_warehouse_test.yaml` | Template for the hospital IRA configs |
| container `sample_behavior_tree/patrol.json` | Template for the Idle → MoveTo evacuation tree |
| `../grimoires-twin/sim/score_vlm.py` (label parsing) | Base of `measure.py` — reads `object_detection_*.json` 3D boxes |
| `../grimoires-twin/sim/render_venue.py`, `ask_vlm.py` | Film stills; Cosmos narration |
| `../grimoires-twin/sim/make_navfloor.py` | Only if the mall is kept and needs a floor proxy |

## Honesty rules

- Say *rehearses / finds / ranks*. Never *predicts*. Say *exit saturated / corridor closed*. Never *crush*. **No crowd-density number, ever.**
- *Simplified grid smoke model; Flow is the visual of that same fire* — unless Phase 4 proves read-back, in which case say exactly what Flow drives.
- *Proxy venue, not a real hospital.* *Most robust plan among those tried*, not *optimal*.
- IRA has no congestion model — state it next to every Layer-2 number.
- Rotate the NGC / build.nvidia.com key after the event.

## Deliberately out of scope

Camera placement, coverage, detectors (Bankai). Incident reconstruction (Akiramenai). Validated fire physics (FDS) — Layer 1's smoke interface could ingest an FDS slice later; that is roadmap. Stampede / crush modelling.
