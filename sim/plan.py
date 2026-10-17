"""
plan.py — what a "plan" is, the variants the solver tries, and the fire scenarios.

A plan is the set of knobs an operator actually controls. The fire is the
scenario, held fixed across variants so the comparison is fair.
"""
import itertools
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_PLAN = {
    "gates_open": ["G1", "G2"],
    "exits_open": ["E1", "E2", "E3"],
    "alarm_delay_s": 30.0,     # ignition -> people start moving (detection + announcement)
    "stagger_s": 25.0,         # spread of departure times (all-at-once vs zoned)
    "route_bias": {},          # stand -> exit steering by stewards/signage (defined, not enumerated in v1)
}

# The variant space for v1: 2 x 2 x 3 x 2 = 24 plans.
KNOBS = {
    "gates_open": [["G1", "G2"], ["G1", "G2", "G3"]],
    "exits_open": [["E1", "E2", "E3"], ["E1", "E2", "E3", "E4"]],
    "alarm_delay_s": [30.0, 15.0, 5.0],
    "stagger_s": [25.0, 10.0],
}

# Fire origins in metres. "default" is the demo fire: NE concourse, so it smokes
# out gate G2 and loads exit E3 — chosen to make the base plan visibly fail.
FIRES = {
    "default": {"name": "ne_concourse", "origin": [44.0, 17.0]},
    "sw_concourse": {"name": "sw_concourse", "origin": [12.0, 8.0]},
    "centre_stand": {"name": "centre_stand", "origin": [30.0, 22.5]},
    "west_gate": {"name": "west_gate", "origin": [19.5, 16.0]},
}


def plan_id(plan):
    g = "".join(x[1:] for x in plan["gates_open"])
    e = "".join(x[1:] for x in plan["exits_open"])
    return f"G{g}-E{e}-a{int(plan['alarm_delay_s'])}-s{int(plan['stagger_s'])}"


def exit_variants(base_exits, venue_exits):
    """The base exits plus every subset of the venue's remaining exits, base first."""
    rest = [e for e in venue_exits if e not in base_exits]
    return [list(base_exits) + list(extra)
            for r in range(len(rest) + 1) for extra in itertools.combinations(rest, r)]


def enumerate_variants(base=BASE_PLAN, venue=None):
    """With no venue: the v1 mall grid (KNOBS). With a venue manifest (a real building):
    exits come from the venue, gates from the base plan (grid venues have none)."""
    knobs = dict(KNOBS)
    if venue is not None:
        knobs["exits_open"] = exit_variants(base["exits_open"], list(venue.get("exits", {})))
        if not venue.get("gates"):
            knobs["gates_open"] = [list(base.get("gates_open", []))]
    keys = list(knobs)
    out = []
    for combo in itertools.product(*(knobs[k] for k in keys)):
        p = json.loads(json.dumps(base))
        p.update(dict(zip(keys, combo)))
        out.append(p)
    return out


def fire_scenarios(which="1"):
    """'1' -> the demo fire only; 'all' -> every origin; or a name / comma list."""
    if which == "1":
        return [dict(FIRES["default"])]
    if which == "all":
        return [dict(f) for f in FIRES.values()]
    return [load_fire(n) for n in which.split(",")]   # a FIRES name or a fire .json path


def load_plan(arg):
    if arg == "base":
        return json.loads(json.dumps(BASE_PLAN))
    return json.load(open(arg))


def load_fire(arg):
    if arg in FIRES:
        return dict(FIRES[arg])
    return json.load(open(arg))


if __name__ == "__main__":
    vs = enumerate_variants()
    print(f"{len(vs)} variants; base = {plan_id(BASE_PLAN)}")
    for v in vs:
        print(" ", plan_id(v))
    print("fires:", ", ".join(f"{k}@{v['origin']}" for k, v in FIRES.items()))
