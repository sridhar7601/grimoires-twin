"""
nemotron_loop.py — Phase 7: Nemotron proposes evacuation plans, the Grimoires pipeline scores each one
against all five fires, Nemotron reads the scores and proposes the next, and a human approves the winner.
Optionally the approved plan is sent to the Isaac Sim twin. The whole session is recorded.

  export NVIDIA_API_KEY=nvapi-...      # build.nvidia.com key; read from the environment, never written anywhere
  python3 sim/agent/nemotron_loop.py --list-models
  python3 sim/agent/nemotron_loop.py --rounds 8                     # interactive approval at the end
  python3 sim/agent/nemotron_loop.py --rounds 8 --twin              # ...and send the approved plan to the twin

Starts from the solver's ranking (results/hospital/layer1/solve_hospital_robust.json), so Nemotron's job is
to beat the best plan among the 24 the grid tried — or say it can't.
"""
import argparse
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tools  # noqa: E402

API = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"

SYSTEM = """You are the planning agent of Grimoires, an evacuation-plan stress-tester for a hospital.
You propose evacuation PLANS. A deterministic simulator rehearses each plan against five fire locations and
returns hard numbers. Your goal: a plan with a LOWER robust score (its worst fire) than the best plan so far.

Every score is the MEAN over several random seeds (seating, walking speeds, departure times); differences of a
few points are noise, so prefer clear improvements over tiny ones.
A plan has exactly three knobs:
  exits_open     - non-empty subset of the venue's exits
  alarm_delay_s  - seconds from ignition to the alarm (people start moving)
  stagger_s      - spread of departure times after the alarm (seconds)

Plausibility floors: alarm_delay_s >= 5 and stagger_s >= 10 (detection is never instant; hundreds of people never
start in the same second; the simulator has no crowd collisions, so do not exploit tiny staggers). Plans below the
floors are rejected.
Rules: never repeat a plan already tried; change knobs for a reason you state; trade-offs are real (a very early,
very compressed departure can push more people through dense smoke). Be honest: you rank plans, you do not
predict real fires. Reply with ONE JSON object and nothing else:
  {"reasoning": "<one or two sentences>", "plan": {"exits_open": [...], "alarm_delay_s": <number>, "stagger_s": <number>}}
or, when you believe no tried-or-proposable plan will beat the best:
  {"reasoning": "...", "done": true}"""


def call(model, messages, key, temperature=0.4, max_tokens=4096):
    body = json.dumps({"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(f"{API}/chat/completions", data=body,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                msg = json.load(r)["choices"][0]["message"]
                return msg.get("content") or msg.get("reasoning_content") or ""
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="ignore")[:300]
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(10 * (attempt + 1)); continue
            raise SystemExit(f"NVIDIA API error {e.code}: {msg}")
        except (TimeoutError, urllib.error.URLError, ConnectionError) as e:   # slow or dropped hosted call: retry
            if attempt < 3:
                print(f"  (API call failed: {e}; retrying)", flush=True)
                time.sleep(10 * (attempt + 1)); continue
            raise SystemExit(f"NVIDIA API unreachable after retries: {e}")
    raise SystemExit("NVIDIA API: no response")


def parse(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise ValueError("no JSON object in the reply")
    return json.loads(m.group(0))


def compact(e):
    return {"plan_id": e["plan_id"], "robust_score": e["robust_score"], "worst_fire": e["worst_fire"],
            "t90_by_fire": e["t90_by_fire"], "over_30s_smoke_by_fire": e["over_30s_smoke_by_fire"],
            "trapped_total": e["trapped_total"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.environ.get("NEMOTRON_MODEL", DEFAULT_MODEL))
    ap.add_argument("--rounds", type=int, default=8)
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--yes", action="store_true", help="skip the human approval prompt (recorded as NOT human-approved)")
    ap.add_argument("--twin", action="store_true", help="send the approved plan to the Isaac twin (GPU box)")
    ap.add_argument("--approve", help="a saved session JSON: show its recommendation and ask a human to approve it")
    a = ap.parse_args()
    if a.approve:
        sess = json.load(open(a.approve)); b = sess["best"]
        print(f"{sess['model']} recommended {b['plan_id']} robust {b['robust_score']} (worst {b['worst_fire']}, from {b['source']})")
        if input("Approve this plan for the certificate? [y/N] ").strip().lower() == "y":
            sess["approved"], sess["approved_by"] = True, "human at the terminal (--approve)"
            json.dump(b["plan"], open(os.path.join(tools.ROOT, "scenarios", "hospital_agent_plan.json"), "w"), indent=2)
            if a.twin:
                sess["twin_job"] = tools.start_twin(b["plan"], name="agent_" + sess["finished"].replace("-", "_"))
                print(f"twin queued: {sess['twin_job']['job']}")
            json.dump(sess, open(a.approve, "w"), indent=1)
            md = os.path.join(tools.ROOT, "docs", "results", "agent_session.md")
            open(md, "a").write(f"\n**Approved later** by a human at the terminal ({datetime.datetime.now():%Y-%m-%d %H:%M}).\n")
            print("approved; scenarios/hospital_agent_plan.json written")
        return
    key = os.environ.get("NVIDIA_API_KEY")
    if not key:
        raise SystemExit("set NVIDIA_API_KEY (a build.nvidia.com key) in the environment first")

    if a.list_models:
        req = urllib.request.Request(f"{API}/models", headers={"Authorization": f"Bearer {key}"})
        ids = sorted(m["id"] for m in json.load(urllib.request.urlopen(req, timeout=60))["data"])
        print("\n".join(i for i in ids if "nemotron" in i.lower()) or "(no nemotron models visible to this key)")
        return

    ctx = tools.describe()
    ctx["scoring_seeds"] = list(tools.SEEDS)
    cache = os.path.join(tools.ROOT, "results", "hospital", "agent", f"grid_seeds_{'-'.join(map(str, tools.SEEDS))}.json")
    if os.path.exists(cache):
        gs = json.load(open(cache))
    else:
        print("scoring the 24-plan grid over seeds", tools.SEEDS, "(once, ~4 min; cached)", flush=True)
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        gs = tools.grid_search(top=24); json.dump(gs, open(cache, "w"), indent=1)
    rk = gs["top"]
    grid = [{"plan_id": r["plan_id"], "robust_score": r["robust_score"], "worst_fire": r["worst_fire"],
             "t90_by_fire": r["t90_by_fire"]} for r in rk]
    tried = {r["plan_id"]: r for r in grid}
    best = dict(grid[0], plan=tools.normalise(rk[0]["plan"]), source="grid")
    print(f"model {a.model} | seeds {list(tools.SEEDS)} | grid best {best['plan_id']} robust {best['robust_score']} | base {gs['base']['robust_score']}")

    messages = [{"role": "system", "content": "detailed thinking off\n" + SYSTEM},
                {"role": "user", "content": "PROBLEM:\n" + json.dumps(ctx, indent=1) +
                 "\n\nTHE GRID ALREADY TRIED THESE 24 PLANS (best first):\n" + json.dumps(grid[:8], indent=1) +
                 f"\n...and {len(grid) - 8} worse ones. Beat robust score {best['robust_score']}. Propose your first plan."}]
    log = []
    for rnd in range(1, a.rounds + 1):
        reply = call(a.model, messages, key)
        messages.append({"role": "assistant", "content": reply})
        entry = {"round": rnd, "reply": reply}
        try:
            prop = parse(reply)
            if prop.get("done"):
                entry["done"] = True; log.append(entry)
                print(f"[{rnd}] Nemotron stops: {prop.get('reasoning', '')}")
                break
            plan = tools.normalise(prop["plan"])
            pid = tools.plan_id(plan)
            if pid in tried:
                feedback = f"{pid} was already tried (robust {tried[pid]['robust_score']}). Propose a different plan."
                entry.update(plan_id=pid, repeat=True)
            else:
                e = tools.evaluate(plan)
                c = compact(e); tried[pid] = c
                entry.update(plan_id=pid, reasoning=prop.get("reasoning", ""), result=c)
                better = c["robust_score"] < best["robust_score"]
                if better:
                    best = dict(c, plan=plan, source=f"nemotron round {rnd}")
                print(f"[{rnd}] {pid:18s} robust {c['robust_score']:7.1f} worst {c['worst_fire']:13s} {'NEW BEST' if better else ''}  <- {prop.get('reasoning', '')[:90]}")
                feedback = (f"RESULT {json.dumps(c)}\nBest so far: {best['plan_id']} robust {best['robust_score']} ({best['source']}). "
                            "Propose the next plan, or stop with done.")
        except (ValueError, KeyError, json.JSONDecodeError) as err:
            feedback = f"Could not use that reply ({err}). Reply with exactly one JSON object as specified."
            entry["error"] = str(err)
            print(f"[{rnd}] unusable reply: {err}")
        log.append(entry)
        messages.append({"role": "user", "content": feedback})

    # ---- held-out check: an agent pick must beat the grid's best on seeds it never saw, or the grid plan stands
    HELD_OUT = [45, 46, 47, 48, 49]
    validation = None
    if best["source"] != "grid":
        gp = tools.normalise(rk[0]["plan"])
        a_scores = [tools.evaluate(best["plan"], seeds=[sd])["robust_score"] for sd in HELD_OUT]
        g_scores = [tools.evaluate(gp, seeds=[sd])["robust_score"] for sd in HELD_OUT]
        wins = sum(x < y for x, y in zip(a_scores, g_scores))
        a_mean, g_mean = sum(a_scores) / len(a_scores), sum(g_scores) / len(g_scores)
        holds = wins >= 4 and a_mean < g_mean and max(a_scores) <= max(g_scores)
        validation = {"held_out_seeds": HELD_OUT, "agent": best["plan_id"], "agent_scores": a_scores,
                      "grid": grid[0]["plan_id"], "grid_scores": g_scores, "agent_wins": wins,
                      "agent_mean": round(a_mean, 1), "grid_mean": round(g_mean, 1), "agent_pick_holds": holds}
        print(f"\nHELD-OUT CHECK (seeds {HELD_OUT}): {best['plan_id']} mean {a_mean:.1f} vs grid {grid[0]['plan_id']} {g_mean:.1f}; "
              f"better on {wins}/{len(HELD_OUT)} -> {'agent pick holds' if holds else 'NOT a real improvement - recommending the grid plan'}")
        if not holds:
            best = dict(grid[0], plan=gp, source="grid (agent pick failed the held-out check)")
    print(f"\nRECOMMENDED: {best['plan_id']}  robust score {best['robust_score']}  (worst fire {best['worst_fire']}, from {best['source']})")
    print(f"  t90 by fire: {best['t90_by_fire']}")
    approved, who = False, "nobody (--yes)"
    if a.yes:
        approved = True
    else:
        try:
            approved = input("Approve this plan for the certificate? [y/N] ").strip().lower() == "y"
            who = "human at the terminal" if approved else "rejected by the human"
        except EOFError:                                     # no terminal attached: leave it for a human
            approved, who = False, "PENDING - no terminal; approve with: python3 sim/agent/nemotron_loop.py --approve <session json>"

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir = os.path.join(tools.ROOT, "results", "hospital", "agent"); os.makedirs(outdir, exist_ok=True)
    session = {"model": a.model, "rounds": a.rounds, "grid_best": grid[0], "best": best, "validation": validation, "approved": approved,
               "approved_by": who, "log": log, "finished": stamp}
    twin = None
    if approved:
        json.dump(best["plan"], open(os.path.join(tools.ROOT, "scenarios", "hospital_agent_plan.json"), "w"), indent=2)
        if a.twin:
            twin = tools.start_twin(best["plan"], name=f"agent_{stamp.replace('-', '_')}")
            session["twin_job"] = twin
            print(f"twin queued: {twin['job']}  (check: python3 sim/agent/tools.py twin_status {twin['job']})")
    json.dump(session, open(os.path.join(outdir, f"session_{stamp}.json"), "w"), indent=1)

    md = [f"# Agent session {stamp}", "",
          f"Model `{a.model}` (NVIDIA hosted) proposed plans; the Grimoires Layer-1 pipeline scored each against all five fires "
          f"(300 people), each fire averaged over seeds {list(tools.SEEDS)}; robust score = worst fire, lower is better. "
          "Plausibility floors: alarm >= 5 s, stagger >= 10 s.", "",
          f"Starting point: the 24-variant grid, best `{grid[0]['plan_id']}` robust **{grid[0]['robust_score']}**.", "",
          "| round | plan proposed | robust score | worst fire | Nemotron's reasoning |", "|---|---|---|---|---|"]
    for e in log:
        if "result" in e:
            md.append(f"| {e['round']} | `{e['plan_id']}` | {e['result']['robust_score']} | {e['result']['worst_fire']} | {e['reasoning']} |")
        elif e.get("repeat"):
            md.append(f"| {e['round']} | `{e['plan_id']}` | (already tried) | | |")
        elif e.get("done"):
            md.append(f"| {e['round']} | — stopped — | | | |")
        else:
            md.append(f"| {e['round']} | (unusable reply) | | | {e.get('error', '')} |")
    if validation:
        md += ["", f"**Held-out check** (seeds {validation['held_out_seeds']}, never used in the search): agent pick `{validation['agent']}` "
               f"mean {validation['agent_mean']} vs grid `{validation['grid']}` mean {validation['grid_mean']}; agent better on "
               f"{validation['agent_wins']}/{len(validation['held_out_seeds'])} → "
               + ("**the agent's pick holds**." if validation["agent_pick_holds"] else "**not a real improvement — the grid plan stands.**")]
    md += ["", f"**Recommended:** `{best['plan_id']}` robust **{best['robust_score']}** (from {best['source']}). "
           f"**Approved:** {'yes' if approved else 'no'} — {who}.",
           (f"Sent to the Isaac twin as job `{twin['job']}`." if twin else ""), ""]
    open(os.path.join(tools.ROOT, "docs", "results", "agent_session.md"), "w").write("\n".join(md))
    print(f"session -> results/hospital/agent/session_{stamp}.json and docs/results/agent_session.md")


if __name__ == "__main__":
    main()
