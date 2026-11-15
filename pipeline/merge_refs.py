"""Merge subagent reference searches (data/refs/out_*.json), fetch candidate texts, and build the
human review sheet data/pair_review.csv in seeded random order (seed 20261113, PREREG §2)."""
import csv, hashlib, json, random, re, time
from datetime import date
from pathlib import Path
import requests, trafilatura
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "data/cache/html_refs"; HTML.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (academic research client)"}
EXCLUDED = ("dw.com", "bbc.", "france24", "voanoticias", "telesurtv", "prensa-latina", "hispantv", "granma", "cubadebate", "vtv.gob", "rt.com", "sputnik", "noticiaslatam", "msn.com", "yahoo.", "wikipedia")
_last = {}

def fetch(url):
    f = HTML / (hashlib.sha256(url.encode()).hexdigest() + ".html")
    if f.exists():
        html = f.read_text(errors="ignore")
    else:
        dom = url.split("/")[2]
        w = 2 - (time.time() - _last.get(dom, 0))
        if w > 0: time.sleep(w)
        _last[dom] = time.time()
        try:
            r = requests.get(url, headers=UA, timeout=25)
        except requests.RequestException:
            return None, "fetch_error"
        if r.status_code != 200: return None, f"http_{r.status_code}"
        html = r.text; f.write_text(html)
    t = trafilatura.extract(html)
    if t:
        import ftfy; t = ftfy.fix_text(t)
    return (t, "ok") if t else (None, "no_text")

def main():
    arts = json.load(open(ROOT / "data/state_articles.json"))
    rows = []
    for p in sorted((ROOT / "data/refs").glob("out_*.json")):
        for o in json.load(open(p)):
            a = arts[o["idx"]]
            for m in o.get("matches", []):
                url = m.get("url", "")
                if not url.startswith("http") or any(x in url for x in EXCLUDED): continue
                text, status = fetch(url)
                words = len(text.split()) if text else 0
                score = 0.0
                if text:
                    A = a["title"] + " " + " ".join(a["text"].split()[:300]); B = (m.get("title") or "") + " " + " ".join(text.split()[:300])
                    score = float(cosine_similarity(TfidfVectorizer().fit_transform([A, B]))[0, 1])
                    (ROOT / "data/articles" / (hashlib.sha256(url.encode()).hexdigest() + ".json")).write_text(json.dumps(
                        {"url": url, "title": m.get("title"), "date": m.get("date"), "text": text, "words": words, "outlet": m.get("outlet"), "wire": m.get("wire")}, ensure_ascii=False))
                try: gap = abs((date.fromisoformat(m.get("date", "")[:10]) - date.fromisoformat(a["date"][:10])).days)
                except Exception: gap = ""
                rows.append(dict(state_idx=o["idx"], country=a["country"], event=o.get("event", ""), state_date=a["date"][:10], state_title=a["title"], state_url=a["url"], state_words=a["words"],
                                 ref_outlet=m.get("outlet"), wire=m.get("wire") or "", ref_title=m.get("title"), ref_date=m.get("date"), day_gap=gap, ref_url=url,
                                 ref_words=words, fetch=status, tfidf=round(score, 3), same_stage_agent=m.get("same_stage"), agent_note=m.get("note", "")))
    # auto flags (a human still decides)
    for r in rows:
        f = []
        if r["fetch"] != "ok": f.append("text_not_fetched")
        elif r["ref_words"] < 150: f.append("ref_under_150w")
        if r["state_words"] < 150: f.append("state_under_150w")
        if r["same_stage_agent"] is False: f.append("different_stage")
        if r["day_gap"] != "" and r["day_gap"] > 3: f.append("outside_3_days")
        r["auto_flags"] = ";".join(f)
    # seeded order over state articles (PREREG: seed 20261113); best candidate first within an article
    ids = sorted({r["state_idx"] for r in rows}); random.Random(20261113).shuffle(ids)
    order = {i: k for k, i in enumerate(ids)}
    rows.sort(key=lambda r: (order[r["state_idx"]], r["auto_flags"] != "", -r["tfidf"]))
    for r in rows:
        r["review_order"] = order[r["state_idx"]] + 1
        r.update(event_id="", same_event_same_stage="", eligible="", reason="")
    cols = ["review_order", "state_idx", "country", "event", "state_date", "ref_date", "day_gap", "state_title", "ref_outlet", "wire", "ref_title",
            "state_words", "ref_words", "tfidf", "auto_flags", "agent_note", "state_url", "ref_url", "fetch", "same_stage_agent",
            "event_id", "same_event_same_stage", "eligible", "reason"]
    out = ROOT / "data/pair_review.csv"
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    clean = {r["state_idx"] for r in rows if not r["auto_flags"]}
    print(f"candidate pairs: {len(rows)}; state articles with ≥1 candidate: {len(ids)}; with ≥1 unflagged candidate: {len(clean)}")
    from collections import Counter
    print("flags:", Counter(f for r in rows for f in r["auto_flags"].split(";") if f))
    print("unflagged by country:", Counter(arts[i]["country"] for i in clean))
    print("ref outlets (unflagged):", Counter(r["ref_outlet"] for r in rows if not r["auto_flags"]).most_common(8))

if __name__ == "__main__": main()
