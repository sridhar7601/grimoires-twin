# Grimoires — 7-minute demo video script

Written for Sridhar to record. Target length **6:40**, hard cap 7:00 including the code walkthrough.
Every number here is from a results file; none is invented. Say the honest phrases out loud —
*rehearses / finds / ranks*, never *predicts*; *door crowding is demand*, never *crush*.

## Before you hit record
- Record with **QuickTime** (or Cmd-Shift-5) → screen + microphone, 1080p.
- Open these ahead of time, each in its own window/tab so you can switch fast:
  1. The deck (the architecture slide ready): https://claude.ai/artifact/RVsgBDxnE4FpiRT15SuQkm
  2. A terminal `cd`'d into the repo.
  3. The three videos in `renders/`: `grimoires_demo.mp4` (the 50-second reel), `hospital_dollhouse_fire.mp4`, `hospital_cctv.mp4`.
  4. Your editor open on the repo, file tree visible.
  5. `docs/results/certificate.md` open.
- Speak a touch slower than feels natural. Pauses are fine; they cut well.

---

## 0:00–0:30 · Hook + problem   [face cam or title card]
**SAY:** "Hi, I'm Sridhar. This is Grimoires, an evacuation-plan certificate.
Here's the problem: every hospital, mall and venue has an evacuation plan, and it's signed off
without ever being tested under a real fire. Full drills are rare — a hospital runs one a quarter,
per shift — and no drill can put real smoke in a corridor. You cannot drill the fire.
So we rehearse it in simulation, search hundreds of plans, and prove the best one in a physical
NVIDIA twin."

## 0:30–1:10 · Idea + architecture   [SHOW: the architecture slide]
**SAY:** "The system is three stages. **Search** — a fast Python solver rehearses every plan
variant in seconds. **Prove** — NVIDIA Isaac Sim re-runs the base plan and the winner with real
characters path-finding through the building. **Certify** — same fire, same seed, both layers; where
two independent models agree, you have a defensible plan. The only expensive part is the twin, and
it runs on two L40S GPUs. Everything else runs on a laptop."

## 1:10–2:20 · Layer 1, the search   [SHOW: play grimoires_demo.mp4 section 1, then the terminal]
**SAY (over the map film):** "This is the rehearsal, top-down, 300 people, the fire 4 metres inside
the main entrance. Today's plan is on the right. Smoke closes that entrance at 21.7 seconds, and
277 of 300 people funnel through one remaining door. Ninety percent are out at 135.9 seconds."
**SHOW:** run the search live (it takes ~20 s on camera) —
```
python3 sim/solve.py --venue results/hospital/hospital_plan.json --base scenarios/hospital_base_plan.json \
    --fires scenarios/hospital_fire_entrance.json --people 300 --fps 12 --tag demo --results /tmp
```
**SAY:** "Twenty-four plan variants, scored in about twenty seconds. The winner opens all four
exits and alarms earlier: ninety percent out at 57.3 seconds — 58 percent faster, and 89 percent
fewer people caught in smoke. Across five fire locations and five random seeds — 600 rehearsals in
under nine minutes — today's plan ranks last every time."

## 2:20–3:40 · Layer 2, the twin   [SHOW: hospital_dollhouse_fire.mp4, then hospital_cctv.mp4]
**SAY (over the fire film):** "Now we prove it physically. This is Isaac Sim with the roof off,
both plans side by side, with a real Omniverse Flow fire at the entrance. Left is the Grimoires plan,
right is today's. The NVIDIA stack is doing the work: OpenUSD for the building, Isaac Replicator
Agent for the NavMesh and the characters, Omniverse Flow for the fire, and Cosmos Reason narrating
on a second GPU."
**SAY (switch to the CCTV film):** "And because operators think in cameras, here's the same run as
a security-camera wall — four feeds per plan. At 44 seconds the Grimoires plan has 35 of 40 out; the
base plan has 3. The twin and the Python solver agree on the ordering, and all 40 people get out in
both plans."

## 3:40–4:20 · The certificate   [SHOW: docs/results/certificate.md]
**SAY:** "This is the output: the certificate. Two layers, same fire, same seed. They AGREE —
winner faster in both. And we're honest about the limits: neither layer simulates body pressure, so
we report door-crowding *demand* as a risk flag, never a crush prediction. Every row cites the file
it came from."

## 4:20–5:00 · The agent   [SHOW: deck agent slide, or docs/results/agent_session.md]
**SAY:** "We also let an agent drive it. NVIDIA's Nemotron proposes a plan, the pipeline scores it,
Nemotron reads the scores and proposes the next, and a human approves before the twin spends GPU
time. It earned trust the hard way: first session it gamed the simulator with a zero-second alarm —
so we added plausibility floors. Second session it overfit to one random seed — so now every plan is
scored on multiple seeds and must win on held-out ones. Third session, with guardrails, it searched
honestly and stopped on its own, confirming the plan from the grid. It's exposed as an MCP server, so
any agent can drive the whole pipeline."

## 5:00–6:15 · Code walkthrough   [SHOW: the editor, open each file briefly]
**SAY:** "Quickly, the code — it's all real and it all runs."
- `sim/rehearse.py` — "one rehearsal: Dijkstra routing on a grid, a smoke front that closes cells
  over time, a door-capacity cap. People do not collide, so we never quote a density — stated right
  in the file."
- `sim/solve.py` — "the search: enumerate plan variants, score each, rank them. Multi-seed, robust."
- `sim/make_ira_config.py` — "this builds the Isaac Sim scene from a plan: the stage, the NavMesh
  zones, the behaviour trees, the Flow fire, the cameras. One command turns a plan into a twin run."
- `sim/measure.py` + `sim/certificate.py` — "measure reads every character's position every frame
  from Isaac; certificate puts both layers in one table and prints the agreement verdict. Nothing is
  typed by hand."
- `sim/agent/nemotron_loop.py` — "the agent loop and the guardrails, and `grimoires_mcp.py` exposes
  the seven tools over MCP."
**SAY:** "It runs on a laptop for the search, and on NVIDIA LaunchPad — two L40S — for the twin."

## 6:15–6:40 · Value + close
**SAY:** "The value is simple: a quarterly half-day drill tests one plan on one shift. Grimoires
tests twenty-four plans against five fires in under nine minutes, then proves the winner physically.
The buyer is whoever signs the plan and carries the liability — fire-safety officers, operators,
insurers. One building in, a certificate out. Thanks for watching — the code, the certificate and all
the films are in the repository."

---

## If you'd rather not narrate live
Play `renders/grimoires_demo.mp4` (the 50-second captioned reel) as the opener, then do only the
code walkthrough on screen with your voice. The reel already labels sections 1, 2, 3 on screen, so
you don't have to introduce each one.

## Safe things to show live (fast, won't error on camera)
- `cat docs/results/certificate.md` — the whole certificate.
- `python3 sim/solve.py ...` (above) — ~20 s, genuinely impressive to watch rank the plans.
- `cat docs/results/layer1_table.md` — the ranked table, if you'd rather not run it live.
- `ls sim/ sim/agent/` — show the size of the codebase.
