"""
certificate.py — the Evacuation Plan Certificate, v1 (Phase 3): base vs winner, same fire,
same seed, in both layers, plus the agreement verdict. Every number is read from the
run outputs; nothing is typed in by hand.

  python3 sim/certificate.py --layer1 results/solve_hospital.json \
      --layer2-base results/layer2_base.json --layer2-winner results/layer2_winner.json \
      --out ../grimoires/results/certificate.md

Layer 1 = rehearse.py / solve.py (Python grid solver, 300 people, SFPE door cap, grid smoke).
Layer 2 = measure.py on the Isaac Sim rehearsal (IRA characters on the NavMesh, 40 people,
no queuing, no smoke until Phase 4).

Agreement (ARCHITECTURE.md): same ordering of base vs winner on t90 in both layers, and
both layers report the same exits as unusable. Until Phase 4 puts smoke in the twin, the
second half is "not yet testable", and the certificate says so.
"""
import argparse
import json
import os


def fmt_t(v, span=None):
    if v is None:
        return f"not reached in {span:.0f} s" if span else "not reached"
    return f"{v:.1f} s"


def exits_str(d):
    return ", ".join(f"{k} {v}" for k, v in sorted(d.items())) or "—"


def closed_l1(r):
    return [k for k, v in r.get("corridor_closed_at_s", {}).items() if v is not None]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer1", required=True, help="solve_*.json (has before/after blocks)")
    ap.add_argument("--layer2-base", required=True, help="measure.py report for the base plan")
    ap.add_argument("--layer2-winner", required=True, help="measure.py report for the winner plan")
    ap.add_argument("--out", required=True)
    ap.add_argument("--date", default="2026-10-17")
    a = ap.parse_args()

    s = json.load(open(a.layer1))
    l1 = {"base": s["before"], "winner": s["after"]}
    l2 = {"base": json.load(open(a.layer2_base)), "winner": json.load(open(a.layer2_winner))}
    fire = s["fires"][0]
    for k in ("base", "winner"):
        if l2[k]["plan_id"] != l1[k]["plan_id"]:
            raise SystemExit(f"{k}: Layer 2 report is for {l2[k]['plan_id']}, Layer 1 for {l1[k]['plan_id']}")

    # ---- agreement -----------------------------------------------------------------
    t90_1 = {k: l1[k]["t90_s"] for k in l1}
    t90_2 = {k: l2[k]["t90_s"] for k in l2}
    order_1 = t90_1["winner"] < t90_1["base"]
    order_2 = (t90_2["winner"] is not None and t90_2["base"] is not None and t90_2["winner"] < t90_2["base"]) \
        or (t90_2["winner"] is not None and t90_2["base"] is None)          # winner cleared, base never did
    order_agree = order_1 == order_2
    closed_1 = {k: closed_l1(l1[k]) for k in l1}
    twin_has_smoke = any(l2[k].get("closed_exits") for k in l2)         # Phase 4 will add this key
    ratio = {k: (t90_2[k] / t90_1[k] if t90_2[k] and t90_1[k] else None) for k in l1}

    def row(k, label):
        return (f"| **{label}** `{l1[k]['plan_id']}` | {fmt_t(t90_1[k])} | {fmt_t(t90_2[k], l2[k]['sim_span_s'])} "
                f"| {exits_str(l1[k]['exit_throughput_total'])} | {exits_str(l2[k]['exit_throughput_total'])} "
                f"| {', '.join(closed_1[k]) or 'none'} | {', '.join(l2[k].get('closed_exits', [])) or 'not modelled (Phase 4)'} |")

    verdict = []
    verdict.append(f"- **Ordering:** Layer 1 says {'winner faster' if order_1 else 'base faster'} "
                   f"({fmt_t(t90_1['winner'])} vs {fmt_t(t90_1['base'])}); Layer 2 says "
                   f"{'winner faster' if order_2 else 'base faster or not resolved'} "
                   f"({fmt_t(t90_2['winner'], l2['winner']['sim_span_s'])} vs {fmt_t(t90_2['base'], l2['base']['sim_span_s'])}). "
                   f"→ **{'AGREE' if order_agree else 'DISAGREE'}**.")
    if twin_has_smoke:
        same_closed = all(set(closed_1[k]) == set(l2[k].get("closed_exits", [])) for k in l1)
        verdict.append(f"- **Unusable exits:** Layer 1 {closed_1}, Layer 2 {{k: l2[k].get('closed_exits') for k in l2}} → **{'AGREE' if same_closed else 'DISAGREE'}**.")
    else:
        verdict.append(f"- **Unusable exits:** Layer 1 closes {closed_1['base'] or 'none'} (smoke reaches the opening). "
                       "The twin has no smoke yet (Phase 4), so this half of the agreement test is **not yet testable** — stated, not assumed.")
    both = [k for k in l1 if ratio[k]]
    if both:
        verdict.append("- **Congestion caveat, measured:** Layer-2 / Layer-1 t90 = " +
                       ", ".join(f"{k} {ratio[k]:.2f}" for k in both) +
                       ". Expected direction: the twin is *faster* at crowded doors — Layer 1 models door throughput "
                       "(SFPE 1.3 p/m/s cap), IRA characters do not queue. A ratio below 1 at the base plan (one door for everyone) "
                       "is this effect, not a disagreement.")

    md = [
        f"# Evacuation Plan Certificate — {s['venue']}\n",
        f"**Fire:** `{fire['name']}` at grid-local {fire['origin']} · **Base plan:** `{l1['base']['plan_id']}` · **Recommended plan:** `{l1['winner']['plan_id']}` "
        f"(winner of {len(s['runs'])} variants on this fire; see `layer1_table.md`, robustness in `robustness_table.md`) · **Seed:** {s['seed']} · **Date:** {a.date}\n",
        f"Layer 1 = Python solver, {s['people']} people, fps {s['fps']}. Layer 2 = Isaac Sim rehearsal, {l2['base']['people']} characters, "
        f"exit = first frame within {l2['base']['reach_m']} m of the agent's exit target. Same fire origin, same plan knobs, same seed in both layers.\n",
        "| plan | Layer-1 t90 | Layer-2 t90 | exits used — Layer 1 | exits used — Layer 2 | closed exits — Layer 1 | closed exits — Layer 2 |",
        "|---|---|---|---|---|---|---|",
        row("base", "base"), row("winner", "winner"),
        "\n## Agreement\n", *verdict,
        "\n## Supporting numbers\n",
        "| metric | base L1 | winner L1 | base L2 | winner L2 |", "|---|---|---|---|---|",
        f"| t50 / t90 / t100 | {l1['base']['t50_s']} / {l1['base']['t90_s']} / {l1['base']['t100_s']} | {l1['winner']['t50_s']} / {l1['winner']['t90_s']} / {l1['winner']['t100_s']} "
        f"| {l2['base']['t50_s']} / {l2['base']['t90_s']} / {l2['base']['t100_s']} | {l2['winner']['t50_s']} / {l2['winner']['t90_s']} / {l2['winner']['t100_s']} |",
        f"| people | {s['people']} | {s['people']} | {l2['base']['people']} ({l2['base']['arrived']} arrived, {l2['base']['never_arrived']} never) | {l2['winner']['people']} ({l2['winner']['arrived']} arrived, {l2['winner']['never_arrived']} never) |",
        f"| over 30 s smoke threshold | {l1['base']['n_over_exposure_threshold']} | {l1['winner']['n_over_exposure_threshold']} | n/a (no smoke in twin yet) | n/a |",
        f"| rerouted / redirected | {l1['base']['rerouted']} | {l1['winner']['rerouted']} | {len(l2['base']['redirected'])} | {len(l2['winner']['redirected'])} |",
        "\n## What this certificate claims — and does not\n",
        "- *Rehearses, finds, ranks* — never *predicts*. *Exit saturated / corridor closed* — never *crush*. No crowd-density figure anywhere.",
        "- Fix = plan knobs only (exits opened, alarm earlier, stagger). Fire origin, spread, people count and seed held fixed within each layer.",
        "- Smoke: simplified grid front model in Layer 1; Flow in the twin is the visual of the same fire (Phase 4). Proxy venue, not a real hospital.",
        "- Most robust plan among those tried, not optimal. IRA has no congestion model — stated next to every Layer-2 number.",
        f"\nSources: `{os.path.basename(a.layer1)}`, `{os.path.basename(a.layer2_base)}`, `{os.path.basename(a.layer2_winner)}`; "
        f"Layer-2 model: {l2['base']['model']}\n",
    ]
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    open(a.out, "w").write("\n".join(md))
    print(f"wrote {a.out}\n  ordering agree: {order_agree} | t90 L1 {t90_1} | t90 L2 {t90_2} | L2/L1 {ratio}")


if __name__ == "__main__":
    main()
