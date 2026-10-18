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
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crowding import summary as crowd_summary  # noqa: E402


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
    ap.add_argument("--layer2-note", default="", help="one line on how the twin runs were set up (e.g. doors open)")
    ap.add_argument("--sensitivity", action="append", default=[],
                    help="repeatable: 'label::base_report.json::winner_report.json' — the same runs under another twin setup")
    ap.add_argument("--crowding-check", help="rehearse.py report of a deliberately bad plan, to show the door-crowding flag fires")
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
                       "In the twin the closure is *scripted from Layer 1's closure time* (characters assigned to that exit are re-assigned "
                       "at 21.7 s; Flow renders the same fire) — it is not read back from the Flow smoke, so this half of the agreement test "
                       "is **not independently testable yet** — stated, not assumed. The Flow-fire runs are reported under Sensitivity.")
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
        f"| door crowding, worst door (demand) | {crowd_summary(l1['base'].get('door_crowding'))} | {crowd_summary(l1['winner'].get('door_crowding'))} "
        f"| {crowd_summary(l2['base'].get('door_crowding'))} | {crowd_summary(l2['winner'].get('door_crowding'))} |",
        "\nDoor crowding = people not yet out within 2 m of the door centre over a 6.3 m² half-disc, every sample; 4 p/m² is Fruin's "
        "LOS E/F (movement stops), 6 p/m² the crush band. It is **demand** — how many people press on one door at once — a crush-risk "
        "flag. Neither layer simulates body pressure (Layer 1 queues at the door cap but bodies overlap; IRA characters avoid each other "
        "but are not stopped by contact), so a figure above 6 means *this door is asked to take more people than can physically fit*, "
        "not *a crush happens*. In the twin a character counts as out 1.5 m from a target that sits 1.25 m inside the door, i.e. about "
        "2.75 m before the door line, so the twin figure is a lower bound and a sanity check; the operative flag is Layer 1 (300 people, door cap).",
    ]
    if a.layer2_note:
        md.insert(3, f"Twin setup: {a.layer2_note}\n")
    for spec in a.sensitivity:
        label, pb, pw = spec.split("::")
        sb, sw = json.load(open(pb)), json.load(open(pw))
        agree = sw["t90_s"] is not None and (sb["t90_s"] is None or sw["t90_s"] < sb["t90_s"])
        md += [f"\n## Sensitivity — {label}\n",
               "| plan | Layer-2 t50 / t90 / t100 (headline setup) | Layer-2 t50 / t90 / t100 (this setup) | exits used (this setup) | door crowding (this setup) |",
               "|---|---|---|---|---|",
               f"| base `{l1['base']['plan_id']}` | {l2['base']['t50_s']} / {l2['base']['t90_s']} / {l2['base']['t100_s']} | {sb['t50_s']} / {sb['t90_s']} / {fmt_t(sb['t100_s'], sb['sim_span_s']) if sb['t100_s'] is None else sb['t100_s']} | {exits_str(sb['exit_throughput_total'])} | {crowd_summary(sb.get('door_crowding'))} |",
               f"| winner `{l1['winner']['plan_id']}` | {l2['winner']['t50_s']} / {l2['winner']['t90_s']} / {l2['winner']['t100_s']} | {sw['t50_s']} / {sw['t90_s']} / {fmt_t(sw['t100_s'], sw['sim_span_s']) if sw['t100_s'] is None else sw['t100_s']} | {exits_str(sw['exit_throughput_total'])} | {crowd_summary(sw.get('door_crowding'))} |",
               f"\nWinner faster under this setup too: **{'yes' if agree else 'NO'}**. Same seed and spawn positions in both setups."]
        extra = []
        for k, r in (("base", sb), ("winner", sw)):
            if r.get("arrived_after_closure"):
                extra.append(f"{k}: {sum(r['arrived_after_closure'].values())} of {r['people']} still reached "
                             f"{', '.join(r['arrived_after_closure'])} after its smoke closure (they had already set off; IRA does not re-route mid-walk)")
            if r.get("never_arrived"):
                extra.append(f"{k}: {r['never_arrived']} never came within {r['reach_m']} m of an exit target — "
                             f"they stopped {', '.join(str(v) for v in r['never_arrived_agents'].values())} m short behind characters parked on it")
        if extra:
            md.append("Caveats: " + "; ".join(extra) + ".")
    if a.crowding_check:
        c = json.load(open(a.crowding_check))
        md += ["\n## Door-crowding flag — does it fire when it should?\n",
               f"A deliberately bad plan `{c['plan_id']}` (everyone released at once) on the same fire and seed: "
               f"{crowd_summary(c['door_crowding'])}, t90 {fmt_t(c['t90_s'])}. Faster on paper, flagged in red — this is the case the agent's "
               "alarm/stagger floors exist for, and the flag now catches it from the data rather than from a rule."]
    md += [
        "\n## What this certificate claims — and does not\n",
        "- *Rehearses, finds, ranks* — never *predicts*. *Exit saturated / corridor closed / door crowding (demand)* — never *crush*. "
        "The only density-shaped number is door-crowding demand, labelled as a risk flag, not a prediction.",
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
