"""
solve.py — the solver: try every plan variant against the fire(s), score, rank,
and print the base plan against the winner.

Layer 1 of the spec: deterministic enumeration, no agent needed. Layer 2 (an
agent choosing what to try next) calls the same `run_variant` through an MCP
server; nothing here changes for that.

Score (lower is better; weights disclosed in every output):
    score = w_t90 * t90_s + w_exp * exposure_mean_s + w_trap * trapped + w_dense * n_in_dense_smoke
A plan's score is its WORST case across the fires it was tried against. A plan
that never reaches 90 % cleared gets t90 = 2 x sim span, so it ranks below any
plan that did.

  python3 sim/solve.py --fires 1   --seed 42 --tag demo     # 24 runs
  python3 sim/solve.py --fires all --seed 42 --tag robust   # 96 runs
  # a real building (grid venue): exits and the base plan come from files
  python3 sim/solve.py --venue results/hospital_plan.json --base scenarios/hospital_base_plan.json \
      --fires scenarios/hospital_fire_entrance.json --people 300 --fps 12 --tag hospital
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plan import BASE_PLAN, enumerate_variants, fire_scenarios, load_plan, plan_id  # noqa: E402
from rehearse import run  # noqa: E402
from venue_def import VENUE  # noqa: E402

WEIGHTS = {"w_t90": 1.0, "w_exp": 0.5, "w_trap": 1000.0, "w_dense": 5.0}
ROW_KEYS = ["t50_s", "t90_s", "t100_s", "trapped", "rerouted", "exposure_mean_s", "exposure_max_s",
            "n_over_exposure_threshold", "n_in_dense_smoke", "dense_smoke_max_s", "exit_throughput_total", "gate_throughput_total",
            "exit_peak_rate_ps", "gate_peak_rate_ps", "corridor_closed_at_s", "sim_span_s", "stopped"]


def score(report, w=WEIGHTS):
    t90 = report["t90_s"] if report["t90_s"] is not None else 2.0 * report["sim_span_s"]
    return round(w["w_t90"] * t90 + w["w_exp"] * report["exposure_mean_s"] + w["w_trap"] * report["trapped"]
                 + w["w_dense"] * report["n_in_dense_smoke"], 1)


def run_variant(plan, fire, seed=42, fps=4.0, venue=None, **kw):
    """One (plan, fire) rehearsal with the solver's defaults. This is the tool an agent calls."""
    venue = venue or json.loads(json.dumps(VENUE))
    r = run(venue, plan, fire, seed=seed, fps=fps, **kw)
    r["score"] = score(r)
    return r


def _row(r):
    return dict({"plan_id": r["plan_id"], "fire": r["fire"]["name"], "score": r["score"]},
                **{k: r[k] for k in ROW_KEYS})


def _md_table(rows, cols):
    head = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    body = "".join("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |\n" for r in rows)
    return head + body


def _before_after(base, win):
    keys = ["t50_s", "t90_s", "t100_s", "trapped", "rerouted", "exposure_mean_s", "exposure_max_s",
            "n_over_exposure_threshold", "n_in_dense_smoke", "dense_smoke_max_s", "exit_throughput_total", "gate_throughput_total",
            "exit_peak_rate_ps", "corridor_closed_at_s", "score"]
    rows = [{"metric": k, "before (base)": base.get(k), "after (winner)": win.get(k)} for k in keys]
    return _md_table(rows, ["metric", "before (base)", "after (winner)"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", help="venue manifest .json (default: the mall, venue_def.VENUE)")
    ap.add_argument("--base", default="base", help="base plan .json (default: plan.BASE_PLAN)")
    ap.add_argument("--fires", default="1", help="'1' demo fire, 'all', or comma list of names / fire .json paths")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--fps", type=float, default=4.0, help="coarse for search; use 12 for a baked USD")
    ap.add_argument("--people", type=int, default=450)
    ap.add_argument("--tag", default="demo")
    ap.add_argument("--results", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results"))
    ap.add_argument("--weights", default=None, help="w_t90,w_exp,w_trap,w_dense (default 1,0.5,1000,5)")
    a = ap.parse_args()
    if a.weights:
        WEIGHTS.update(dict(zip(["w_t90", "w_exp", "w_trap", "w_dense"], (float(x) for x in a.weights.split(",")))))

    venue = json.load(open(a.venue)) if a.venue else None
    base = load_plan(a.base)
    variants, fires = enumerate_variants(base, venue), fire_scenarios(a.fires)
    base_id = plan_id(base)
    if not any(plan_id(p) == base_id for p in variants):
        variants.insert(0, json.loads(json.dumps(base)))
    print(f"{len(variants)} plans x {len(fires)} fires = {len(variants) * len(fires)} rehearsals "
          f"(seed {a.seed}, fps {a.fps}, {a.people} people, weights {WEIGHTS})")

    t_start, rows, per_plan = time.time(), [], {}
    for p in variants:
        pid = plan_id(p)
        for f in fires:
            t0 = time.time()
            r = run_variant(p, f, seed=a.seed, fps=a.fps, people=a.people, venue=venue)
            rows.append(_row(r))
            per_plan.setdefault(pid, {"plan": p, "runs": {}})["runs"][f["name"]] = r
            print(f"  {pid:22s} {f['name']:14s} t90 {str(r['t90_s']):>6}  trapped {r['trapped']:3d}  "
                  f"dense {r['n_in_dense_smoke']:3d}  exp {r['exposure_mean_s']:5.1f}  score {r['score']:8.1f}   "
                  f"({time.time() - t0:.1f}s)")

    ranked = []
    for pid, d in per_plan.items():
        worst = max(d["runs"].values(), key=lambda r: r["score"])
        ranked.append({"plan_id": pid, "plan": d["plan"], "worst_fire": worst["fire"]["name"],
                       "score_worst": worst["score"],
                       "score_by_fire": {k: r["score"] for k, r in d["runs"].items()},
                       "t90_by_fire": {k: r["t90_s"] for k, r in d["runs"].items()},
                       "trapped_by_fire": {k: r["trapped"] for k, r in d["runs"].items()}})
    ranked.sort(key=lambda x: x["score_worst"])
    winner = ranked[0]
    demo_fire = fires[0]["name"]
    base_r = per_plan[base_id]["runs"][demo_fire]
    win_r = per_plan[winner["plan_id"]]["runs"][demo_fire]

    os.makedirs(a.results, exist_ok=True)
    out_json = os.path.join(a.results, f"solve_{a.tag}.json")
    out_md = os.path.join(a.results, f"solve_{a.tag}.md")
    json.dump({"tag": a.tag, "seed": a.seed, "fps": a.fps, "people": a.people, "weights": WEIGHTS,
               "venue": (venue or {}).get("name", "mall (venue_def)"), "base_plan": base,
               "fires": fires, "base_plan_id": base_id, "winner_plan_id": winner["plan_id"],
               "ranked": ranked, "runs": rows,
               "before": base_r, "after": win_r,
               "elapsed_s": round(time.time() - t_start, 1),
               "model_note": base_r["model"]}, open(out_json, "w"), indent=1)

    md = [f"# Solve `{a.tag}` — {len(variants)} plans × {len(fires)} fire(s), seed {a.seed}\n",
          f"Weights: `{WEIGHTS}`. Score = worst case across fires; lower is better. "
          f"Base plan `{base_id}` → winner `{winner['plan_id']}`.\n",
          "## Ranked plans\n",
          _md_table([{"rank": i + 1, **{k: r[k] for k in ("plan_id", "score_worst", "worst_fire", "t90_by_fire", "trapped_by_fire")}}
                     for i, r in enumerate(ranked)],
                    ["rank", "plan_id", "score_worst", "worst_fire", "t90_by_fire", "trapped_by_fire"]),
          f"\n## Before → after on fire `{demo_fire}` (same seed)\n",
          _before_after(base_r, win_r),
          "\n## Disclosure\n",
          f"> {base_r['model']}\n",
          f"> Smoke params: `{base_r['smoke_params']}`\n"]
    open(out_md, "w").write("\n".join(md))

    print(f"\nTop 5 (worst-case score across {len(fires)} fire(s)):")
    for i, r in enumerate(ranked[:5]):
        print(f"  {i + 1}. {r['plan_id']:22s} score {r['score_worst']:8.1f}  t90 {r['t90_by_fire']}  trapped {r['trapped_by_fire']}")
    print(f"\nBase {base_id} vs winner {winner['plan_id']} on {demo_fire}:")
    for k in ("t90_s", "t100_s", "trapped", "n_in_dense_smoke", "dense_smoke_max_s", "exposure_mean_s",
              "n_over_exposure_threshold", "exit_throughput_total", "gate_throughput_total", "score"):
        print(f"  {k:28s} {str(base_r[k]):>28s} -> {str(win_r[k])}")
    print(f"\n{out_json}\n{out_md}\n({round(time.time() - t_start, 1)} s)")


if __name__ == "__main__":
    main()
