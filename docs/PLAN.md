# Grimoires — build plan

**Written:** 2026-10-16 · no fixed deadline · Architecture: [`ARCHITECTURE.md`](ARCHITECTURE.md)

**Ordering rule:** phases are ordered by **risk retired**, not by calendar. Each phase ends with an artifact that stands on its own, so the demo is never hostage to a later phase. Phases 5–7 are the full vision, not stretch.

**Decisions applied (change if wrong):** hospital as primary venue · IRA characters replace the Blender human · Layer 1 stays our Python solver · mall kept only if Phase 0d passes · agent layer is real, last · **(2026-10-17)** hospital doors treated as openable (`mall_plan.py --ignore door`) and the perimeter sealed to the four named exits (`--seal-perimeter`) · IRA cameras use `maximum_coverage` (`aim_at_targets` crashes on some characters) · NavMesh bake cap patched (`sim/ira/patches/simulation_util.py`, bind-mounted).

**Repo layout (2026-10-17):** one repo, `grimoires-twin/`, mirroring `~/Documents/grimoires-twin` on the box. `docs/` is the notebook — this plan, the architecture, `docs/results/*.md` write-ups; everything else runs: `sim/` (scripts, `ira/` configs + `patches/`, `bt/` trees), `assets/hospital/` (fetched, git-ignored), `scenarios/`, `results/`. The older context files this plan cites (`../00-OVERVIEW.md`, `../06-grimoires-build-spec.md`, …) live outside the repo.

**Already done (carry over):** Layer 1 proven on the mall (base vs winner, 800 people) · IRA proven on the warehouse · Cosmos Reason 2 NIM live on GPU 1 · label parsing in `score_vlm.py`.

---

## Phase 0 — probes (half a session, almost no new code)

| # | Task | Done when | If it fails |
|---|---|---|---|
| 0a | Copy `ira_warehouse_test.yaml` → `grimoires/sim/ira/hospital_wander.yaml`, `base_stage_asset_path: Isaac/Environments/Hospital/hospital.usd`, 10 characters `wander`, 15 s. Run on GPU 0. Pull 2 frames. | Characters **walk** in the hospital; frames + `object_detection_*.json` written | Try `Office/office.usd`; if both fail, fall back to `Simple_Warehouse/warehouse_multiple_shelves.usd` (not Bankai's `full_warehouse`) |
| 0b | Get the hospital geometry local: inside Kit, `omni.client.copy` the `Hospital/` folder (usd + Props + Materials) to `/workspace/assets/hospital/`. Run `mall_plan.py --usd hospital.usd --png` → walkable map. | A clean walkable map; main region is one connected blob | If `mall_plan.py` can't read the materials, strip to geometry (it only needs meshes) |
| 0c | Pick 3–4 exits on the hospital map (real doorways on the perimeter); `mall_plan.py --doors "E1:x,y;…"` | `hospital_plan.json` with exits; door map reviewed | Move the points; the slicer snaps to the nearest wall |
| 0d | **Mall, 20 min max, GUI only:** open `results/mall_navmesh.usd`, Navigation window → bake → NavMesh overlay on. Try agent radius/height/step/slope. | Overlay covers the floor and connects through doorways → mall stays as a custom-venue option | Screenshot it for the record and **drop the mall from the pitch**. No proxy work |

**Artifact:** hospital walkable map with exits + proof IRA walks the hospital.

**Outcome (2026-10-17):** 0a ✅ — run 4: 3 cameras × 430 frames + `object_detection_*.json`, characters walk (7.3 m tracked). Took three fixes in sequence: NavMesh 100-frame cap (patched), `aim_at_targets` unpack crash (→ `maximum_coverage`), then camera ranges that must satisfy `d = h / sin θ`. 0b ✅ — `results/hospital_plan.json`: 1219 m² walkable, main region 98 % connected; needed `TraverseInstanceProxies` (walls are instanceable → blocked was 0) and `--ignore door` (closed doors sealed 29 % of floor into 54 wards). 0c ✅ — four exits on real perimeter doorways: E1 main entrance (−1.25, −2.75), E2 west-wing north (−40.75, 33.25), E3 east-wing east (20.75, 31.25), E4 west-wing side (−38.25, 8.75); `--seal-perimeter` so these are the only ways out. 0d ⬜ — GUI only, not yet done. **Finding for Phase 2:** `object_detection` lists only agents *visible to that camera* — 3 of 10 walkers were ever seen across 3 cameras — so 2d must read every agent's `metro_agent_data.world_position` camera-independently; cameras are for the film.

---

## Phase 1 — Layer 1 on the hospital (fast search)

Copy `scenarios/mall_*.json` → `scenarios/hospital_base_plan.json`, `hospital_fire_*.json` (fire origin a few metres inside the busiest exit, in **grid-local** metres — world = local + origin).

| # | Task | Done when |
|---|---|---|
| 1a | `rehearse.py --venue results/hospital_plan.json --plan base --people N --fps 12 --tracks … --report …` | Base is **dramatic**: an exit closes, long tail, exposure > 0. Tune people / `--speed` until it is — then freeze |
| 1b | Add `--venue` to `solve.py` (today it is hard-wired to `venue_def.VENUE`) and run the full variant sweep on the hospital | `solve_hospital.json`: ranked variants, `before` / `after` blocks |
| 1c | Write `grimoires/results/layer1_table.md`: base vs winner — t50/t90/t100, over-threshold, exits used, closed-at | The Layer-1 half of the certificate |

**Artifact:** the hospital before → after, Python layer. Demo-able alone (it is the mall result, re-done on the hero venue).

**Outcome (2026-10-17):** 1a ✅ frozen at **300 people, seed 42, fps 12**, fire 4 m inside E1 (`scenarios/hospital_fire_entrance.json`); base `G-E12-a30-s25` is dramatic on the first try — E1 closes at 21.7 s, 277/300 through E2, t90 135.9 s, 54 over threshold. 1b ✅ `solve.py --venue/--base` added (exit variants derive from the venue: 24 plans, 20.9 s); winner `G-E1234-a5-s25` — t90 57.3 s (−58 %), over-threshold 6 (−89 %); the solver beat the hand-pick `a5-s10` (faster t90 but 10 more people in dense smoke). 1c ✅ `grimoires/results/layer1_table.md`.

---

## Phase 2 — Layer 2: the twin rehearses base and winner

| # | Task | Done when |
|---|---|---|
| 2a | `grimoires/sim/bt/evacuate.json` — behaviour tree: `Idle` (duration = alarm_delay + per-agent stagger) → `MoveTo` target `/World/ExitTargets/<E>` → `Idle`. Start from the container's `patrol.json`. | One character walks to one exit on the alarm |
| 2b | `grimoires/sim/make_ira_config.py` — from a plan JSON + `hospital_plan.json`: spawn groups by zone, each group's `MoveTo` target = the exit the plan sends that zone to; exits not in `exits_open` get no group; alarm/stagger from the plan. Emits `hospital_base.yaml`, `hospital_winner.yaml`. Also authors `/World/ExitTargets/*` into the stage. | Two configs generated, not hand-written |
| 2c | Run both (same `seed`), ~N characters, duration ≥ Layer-1 t100 + margin. | Frames + labels for both |
| 2d | `grimoires/sim/measure.py` — per agent per frame: 3D-box centre → first frame within 1.5 m of its exit prim → exit time. Clearance curve, t50/t90/t100, exits used. Frame→seconds from the writer step. | `layer2_base.json`, `layer2_winner.json` |

**Artifact:** base vs winner **measured in Isaac**. This is the slide that answers "why NVIDIA".

**Progress (2026-10-17):** 2a ✅ `sim/bt/evacuate.json` = `Wait(alarm…alarm+stagger, seeded RandomFloat) → MoveTo /World/ExitTargets/<E> → Wait`; probe showed a character in `MoveTo` at 1.5 m/s heading for E1 right after the alarm window. Exit targets are authored 1–1.5 m inside each doorway by `sim/make_exit_targets.py`. 2b ✅ `sim/make_ira_config.py --plan … --venue …` writes, per plan: a stage (`hospital.usd` sublayer + ExitTargets + `NavMeshVolume` zone boxes, one NavMesh area per OPEN exit = nearest exit by grid walking distance), one tree per exit with alarm/stagger/target baked in (the BT override string is an opaque Kit-side format, so trees are generated instead), and the IRA yaml with one `behavior_tree` group per exit spawning in its zone, size ∝ zone area. `--measure-only` makes the *numbers* run cheap (one 320×180 camera, no RGB); the film gets its own full-camera run. 2c 🟡 winner (117 s, 40 people) running first, base (194 s) next. Cost: ~7 min NavMesh bake, then in `--measure-only` mode ~6 s of simulation per wall-clock minute (full-camera runs are ~5× slower: ~1.5 s per 30-fps frame). 2d ✅ script: `sim/ira/actor_sdg_dump.py` (stock driver + per-frame dump of EVERY agent's world position, timeline seconds) and `sim/measure.py` (first time within 1.5 m of the agent's exit target → t50/t90/t100, exits used, redirected, never-arrived; same keys as `rehearse.py`). Twin uses 40 characters, not 300: IRA has no queuing, so the agreement test is about ordering and closed exits, not absolute counts.

**Gotcha found in the first winner run:** characters move in Fabric, not USD — a dump that reads `UsdGeom` xforms records the spawn pose forever. The dumper now reads IRA's agent objects (`AgentsManager.get_runtime_agent_instances()[i].get_world_position()`), the same source as `metro_agent_data`; that run was discarded and relaunched. Phase 3 tooling is ready: `sim/certificate.py` builds the certificate table + agreement verdict from `solve_hospital.json` and the two `measure.py` reports (tested on synthetic Layer-2 input only).

---

## Phase 3 — Agreement (the certificate, v1)

| # | Task | Done when |
|---|---|---|
| 3a | `grimoires/results/certificate.md`: one table, rows = base / winner, columns = Layer-1 t90 · Layer-2 t90 · exits used (both) · closed exits (both) · **agree?** | Written |
| 3b | State the congestion caveat under the table, with the expected direction (Layer 2 faster at crowded doors) | Written |

**Artifact:** the two-layer certificate. Everything after this adds depth, not validity.

**Outcome (2026-10-17):** ✅ `docs/results/certificate.md` — base vs winner, same fire/seed, both layers. **They AGREE on ordering:** Layer 1 winner t90 57.3 s vs base 135.9 s; Layer 2 (Isaac twin, 40 characters, 40/40 reached their exit in both runs) winner 31.0 s vs base 68.3 s. Unusable-exit agreement is *not yet testable* — no smoke in the twin until Phase 4 — and the certificate says so rather than claiming it. The congestion caveat showed up as predicted: Layer-2/Layer-1 t90 ratio 0.50 (base) and 0.54 (winner), i.e. the twin clears ~2× faster at both plans because IRA has no door queuing while Layer 1 holds the SFPE 1.3 p/m/s cap — same direction, a known modelling difference, not a disagreement. `sim/certificate.py` reads the two `measure.py` reports + `solve_hospital.json`; nothing hand-typed.

**Update (later, 2026-10-17):** the certified twin runs used the hospital as shipped, door leaves closed. The dollhouse film runs switch the 38 door leaves off (doors open, matching Layer 1's assumption) with the same seed and identical spawn positions, and they record every character every frame — so they are full Layer-2 runs. Measured: winner t90 **30.0 s** (t100 34.6), base **62.6 s** (t100 74.5); closed doors only lengthen the base plan's tail (t100 102.4 → 74.5 s). The certificate now uses doors open as the headline and doors closed as a sensitivity row; the winner is faster under both. Dollhouse film: roof/ceilings/panels off, the untextured 10 000-nit dome dimmed to exposure −3, an authored overhead camera at 46 m (IRA's `aim_at_targets` rejects poses that high), and `sim/stitch_dollhouse.py` draws a ring on every character from the recorded positions.

---

## Phase 4 — the hazard inside the twin

| # | Task | Done when | If it fails |
|---|---|---|---|
| 4a | Author a Flow smoke emitter at the fire origin in the IRA stage; same start time as Layer 1. Re-render base/winner. | Smoke visible in the film at the right place and time | Flow prims not rendering → RTX volumetric fog as the visual, say so |
| 4b | **Density read-back test:** from a Kit script, try sampling Flow density at 3 points per frame (Flow Python API / OmniGraph read node / attribute on the Flow prim). | Numbers come back and rise after ignition | Record the failure → Flow stays visual; grid smoke keeps driving the numbers. Honesty line stays as is |
| 4c | If 4b works: close an exit in the behaviour tree when density at its prim > threshold (`navigation_areas` cost or a trigger) → agents re-route in Isaac | Agents divert from the smoky exit | — |
| 4d | Optional: PhysX debris (fallen shelf / cart) blocking a corridor at alarm time | Agents path around it | Skip |

**Artifact:** the twin reacts to the hazard, or an honest record of why not.

---

## Phase 5 — robustness sweep

- Layer 1: fire origins × plan variants (Python). Rank by **worst-case** t90 → "most robust plan among those tried".
- Warp port of the sweep inner loop if time allows (smoke front + scoring parallelise; Dijkstra stays CPU or becomes a GPU BFS). Report seconds-per-1000-variants before/after.

**Artifact:** robustness table + (optional) speed-up number.

**Outcome (2026-10-17):** Python sweep done — 5 fires × 24 plans = 120 runs in 81.5 s. Base ranks 24/24 under every fire; most robust = `G-E123-a5-s25` (worst 182.8); the demo-fire winner `G-E1234-a5-s25` is 2nd (weak spot: a fire inside E4). `grimoires/results/robustness_table.md`. Warp port not attempted — at 20 s per fire there is no speed problem to solve yet.

---

## Phase 6 — the film and the narration

- `grimoires/sim/render_flythrough.py`: one scripted camera path, same for base and winner, headless RTX → PNG sequence → MP4 (ffmpeg). Overlay t and exits-used.
- Cosmos Reason 2: feed 3 key frames per run, ask for a plain-language description; use the text as captions. Never as a number.

**Artifact:** two MP4s, side by side.

---

## Phase 7 — the agent

- Expose `run_variant(plan) → scores` (Layer 1) and `rehearse_in_twin(plan)` (Layer 2) as MCP tools.
- Nemotron (hosted) proposes the next variant from the ranking; NemoClaw / Hermes runs the loop with a human approving the final plan.

**Artifact:** a recorded agent session producing the certificate end-to-end.

---

## Open questions we can no longer ask

| Question | How we answer it ourselves |
|---|---|
| Does Flow expose density at points? | Phase 4b test |
| Why does the mall NavMesh fail? | Phase 0d GUI inspection per the engineer's checklist; then stop |
| IRA frame → simulation time mapping | Read `camera_params_*.json` / writer step in Phase 2d |
