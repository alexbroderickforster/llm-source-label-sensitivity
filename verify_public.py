"""Recompute every result in results/results.json from the public files, without the article texts.

The full stimulus file contains copyrighted article texts and is not redistributed. data/pairs_public.jsonl is the
same file with each article's title and text replaced by their SHA-256 hashes (which also appear in
stimuli_manifest.json). The analysis never uses article text, only the claims, events, order and pilot flags; the
text checks run when the stimuli are built, so here they are replaced by a structural check.

Usage:  python verify_public.py
"""
import json
from pathlib import Path
import harness.analyze as analyze
from harness.common import read_jsonl

ROOT = Path(__file__).resolve().parent


def validate_public(pairs):
    for p in pairs:
        for side, art in (("S", p["state"]), ("R", p["ref"])):
            assert art.get("url") and art.get("text_sha256"), "missing article metadata"
            assert 3 <= len(p["elements"][side]) <= 5, "3-5 claims per side"
    assert len({p["pair_id"] for p in pairs}) == len(pairs)
    return pairs


analyze.validate = validate_public  # text-free structural check instead of the text-based one

saved = json.loads((ROOT / "results/results.json").read_text(encoding="utf-8"))
fresh = analyze.compute(read_jsonl(ROOT / "data/pairs_public.jsonl"),
                        read_jsonl(ROOT / "results/raw/answers_all_main.jsonl"),
                        read_jsonl(ROOT / "results/raw/judgments_all_main.jsonl"),
                        ROOT / "results/human/all_human_codes.csv", ROOT / "results/human/all_human_key.csv")
saved.pop("inputs", None); fresh.pop("inputs", None)  # recorded input paths/hashes are machine-specific
diff = [k for k in set(saved) | set(fresh) if saved.get(k) != fresh.get(k)]
if diff:
    raise SystemExit("MISMATCH in: " + ", ".join(sorted(diff)))
print("Verified: every result in results/results.json was recomputed from the public answers, judgments and human codes.")
