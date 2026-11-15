"""Amendment A6: build the human-review plan from the second-model verification.
flagged = verifier verdict 'drop'; sample = seeded 20% (seed 20261117) of the remaining, not-yet-human-decided elements."""
import glob, json, random
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

def main():
    ver = {p["pair"]: p for f in sorted(glob.glob(str(ROOT / "data/elements_verify/out_*.json"))) for p in json.load(open(f))}
    try: human = json.load(open(ROOT / "data/elements_review.json"))
    except Exception: human = {}
    plan, pool = {}, []
    for pid, p in sorted(ver.items()):
        plan[pid] = {"event_en": p.get("event_en", ""), "event_es": p.get("event_es", ""), "elements": {}}
        for c in p["checks"]:
            decided = bool(human.get(pid, {}).get("elements", {}).get(c["id"], {}).get("status"))
            mode = "human_before_A6" if decided else ("flagged" if c["verdict"] == "drop" else "none")
            plan[pid]["elements"][c["id"]] = {"verdict": c["verdict"], "reason": c.get("reason", ""), "review": mode}
            if mode == "none": pool.append((pid, c["id"]))
    k = round(len(pool) * 0.2)
    for pid, eid in random.Random(20261117).sample(sorted(pool), k):
        plan[pid]["elements"][eid]["review"] = "sample"
    json.dump(plan, open(ROOT / "data/elements_verify/plan.json", "w"), ensure_ascii=False, indent=1)
    from collections import Counter
    print(len(plan), "pairs;", Counter(e["review"] for p in plan.values() for e in p["elements"].values()))

if __name__ == "__main__": main()
