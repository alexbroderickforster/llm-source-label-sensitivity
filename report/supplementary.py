"""Exploratory numbers cited in the report that results.json does not contain. All are labelled exploratory in the text.
Writes report/supplementary.json. Inputs: results/results.json, judgments, human codes and keys (all frozen)."""
import csv, json, random
from collections import defaultdict
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness.analyze import kappa

R = json.load(open(ROOT / "results/results.json"))
SEED = 20261114
out = {}

# 1. Score-arm selectivity: [S(A1)-S(A4)] - [R(A1)-R(A4)], pair-level, bootstrap over pairs (exploratory DiD, same form as H1-specificity)
# 2. Attribution share of mentioned RT-only claims, A2 vs A5 (does the nudge turn claims into attributed ones?)
pair = defaultdict(lambda: defaultdict(list))
for c in R["cell_rates"].values():
    if c["pilot"] or c["replicate"]: continue
    for side in ("S", "R"):
        if c[side]["denominator"]:
            pair[(c["model"], c["arm"], side, "end")][c["pair_id"]].append(c[side]["endorsement"])
        if c[side].get("mentioned_denominator"):
            pair[(c["model"], c["arm"], side, "att")][c["pair_id"]].append(c[side]["attribution_share"])
pm = {k: {p: sum(v) / len(v) for p, v in d.items()} for k, d in pair.items()}


def boot(vals):
    rng = random.Random(SEED)
    b = sorted(sum(rng.choice(vals) for _ in vals) / len(vals) for _ in range(10000))
    return [round(100 * sum(vals) / len(vals), 1), round(100 * b[249], 1), round(100 * b[9749], 1)]


models = sorted({k[0] for k in pm})
out["score_selectivity_DiD_pp"] = {}
out["true_label_selectivity_DiD_pp"] = {}
out["attribution_share_S_mentioned_pct"] = {}
for m in models:
    for name, arm in (("score_selectivity_DiD_pp", "A4"), ("true_label_selectivity_DiD_pp", "A2")):
        ps = set(pm[(m, "A1", "S", "end")]) & set(pm[(m, arm, "S", "end")]) & set(pm[(m, "A1", "R", "end")]) & set(pm[(m, arm, "R", "end")])
        d = [(pm[(m, "A1", "S", "end")][p] - pm[(m, arm, "S", "end")][p]) - (pm[(m, "A1", "R", "end")][p] - pm[(m, arm, "R", "end")][p]) for p in sorted(ps)]
        out[name][m] = boot(d)
    out["attribution_share_S_mentioned_pct"][m] = {a: round(100 * sum(pm[(m, a, "S", "att")].values()) / len(pm[(m, a, "S", "att")]), 1) for a in ("A1", "A2", "A5")}

# 3. Human-judge agreement: bootstrap CI over answers (cluster), disagreement breakdown, exploratory kappa without quoted-actor claims
# Public version: validation-sample rows only (blind IDs starting with B); claim types from data/pairs_public.jsonl.
key = {(k["blind_id"], k["element_id"]): k for k in csv.DictReader(open(ROOT / "results/human/all_human_key.csv"))}
etype = {}
for l in open(ROOT / "data/pairs_public.jsonl"):
    p = json.loads(l)
    for side in ("S", "R"):
        for e in p["elements"][side]: etype[(p["pair_id"], e["id"])] = e["type"]
typ = {bk: etype[(k["pair_id"], k["original_element_id"])] for bk, k in key.items()}
J = {}
for l in open(ROOT / "results/raw/judgments_all_main.jsonl"):
    j = json.loads(l)
    if j["status"] == "done": J[j["cell_id"]] = {c["element_id"]: c["code"] for c in j["codes"]}
by_ans = defaultdict(list); n_codes = 0
for r in (r for r in csv.DictReader(open(ROOT / "results/human/all_human_codes.csv")) if r["blind_id"].startswith("B")):
    n_codes += 1
    k = key[(r["blind_id"], r["element_id"])]
    if k["cell_id"] not in J: continue
    by_ans[r["blind_id"]].append((r["code"], J[k["cell_id"]][k["original_element_id"]], typ[(r["blind_id"], r["element_id"])]))
items = [x for v in by_ans.values() for x in v]
out["human_codes_total"] = n_codes
out["human_codes_with_judge"] = len(items)
out["human_answers_with_judge"] = len(by_ans)
rng = random.Random(SEED); ids = sorted(by_ans); ks = []
for _ in range(2000):
    s = [x for b in (rng.choice(ids) for _ in ids) for x in by_ans[b]]
    ks.append(kappa([a for a, _, _ in s], [b for _, b, _ in s], True)["kappa"])
ks.sort()
out["kappa_binary"] = [round(kappa([a for a, _, _ in items], [b for _, b, _ in items], True)["kappa"], 3), round(ks[49], 3), round(ks[1949], 3)]
ea = [x for x in items if x[0] == "ENDORSED" and x[1] == "ATTRIBUTED"]
out["human_fact_judge_attributed"] = {"total": len(ea), "quoted_actor": sum(1 for x in ea if x[2] == "quoted-actor claim")}
xe = [x for x in items if x[0] == "ABSENT" and x[1] == "ENDORSED"]
out["human_absent_judge_fact"] = {"total": len(xe), "fact_type": sum(1 for x in xe if x[2] == "fact")}
nq = [x for x in items if x[2] != "quoted-actor claim"]
out["kappa_binary_excluding_quoted_actor_exploratory"] = round(kappa([a for a, _, _ in nq], [b for _, b, _ in nq], True)["kappa"], 3)
out["spontaneous_state_outlet_naming_A1"] = R["spontaneous_state_outlet_naming_A1"]

json.dump(out, open(ROOT / "report/supplementary.json", "w"), indent=1)
print(json.dumps(out, indent=1))
