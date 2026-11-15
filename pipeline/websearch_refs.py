"""Find same-event reference articles for state-media articles via Claude's web search tool.

For each state article in data/state_articles.json:
  1. Ask Claude (web_search, restricted to REFERENCE_DOMAINS) for up to 3 articles on the same event,
     published within +/-3 days. Raw responses are cached in data/cache/websearch/.
  2. Fetch each candidate URL, extract text with trafilatura, and score TF-IDF similarity vs the state article.
Writes data/websearch_pairs.csv (best reference per state article, all scores) for HUMAN confirmation.

Reference set = private national/regional outlets + wire copies. Foreign state-funded broadcasters
(DW, BBC, France 24) and state media (teleSUR, Prensa Latina, HispanTV) are excluded on purpose.
"""
import csv, hashlib, json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import anthropic, requests, trafilatura
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data/cache/websearch"; CACHE.mkdir(parents=True, exist_ok=True)
HTML_CACHE = ROOT / "data/cache/html_ws"; HTML_CACHE.mkdir(parents=True, exist_ok=True)
MODEL = "claude-sonnet-5-5"
UA = {"User-Agent": "Mozilla/5.0 (academic research client)"}
REFERENCE_DOMAINS = [
    "infobae.com", "lanacion.com.ar", "eltiempo.com", "elespectador.com",
    "elcomercio.pe", "larepublica.pe", "eluniversal.com.mx", "milenio.com", "animalpolitico.com",
    "latercera.com", "emol.com", "biobiochile.cl", "eldeber.com.bo", "abc.com.py", "ultimahora.com",
    "primicias.ec", "elcomercio.com", "eluniverso.com", "prensa.com", "elnacional.com", "efectococuyo.com",
    "swissinfo.ch", "cnnespanol.cnn.com", "elfinanciero.com.mx",
    "nacion.com", "laprensagrafica.com", "prensalibre.com", "elheraldo.co", "semana.com", "listindiario.com",
]

PROMPT = """You are helping build a research dataset of news articles that cover the SAME specific event.

State-media article (Spanish):
- Title: {title}
- Published: {date}
- Country: {country}
- Opening: {lead}

Search for news articles from the allowed outlets that report on this SAME specific event (same incident,
announcement, decision or statement, not merely the same topic), published between {d0} and {d1}.
Prefer straight news reports over opinion. Return at most 3.

Reply with ONLY a JSON object, no prose: {{"matches": [{{"url": "...", "outlet": "...", "title": "...", "date": "YYYY-MM-DD or unknown"}}]}}
If you find nothing that covers the same event, reply {{"matches": []}}."""


def ask(client, art, model=None):
    model = model or MODEL
    key = hashlib.sha256(art["url"].encode()).hexdigest()
    f = CACHE / f"{model}-{key}.json"
    if f.exists():
        return json.loads(f.read_text())
    d = date.fromisoformat(art["date"][:10])
    prompt = PROMPT.format(title=art["title"], date=art["date"][:10], country=art.get("country", "?"),
                           lead=" ".join(art["text"].split()[:80]),
                           d0=(d - timedelta(days=3)).isoformat(), d1=(d + timedelta(days=3)).isoformat())
    try:
        extra = {} if "haiku" in model else {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
        resp = client.beta.messages.create(
            model=model, max_tokens=4000, **extra,
            output_config={"effort": "low"},
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 3,
                    "allowed_domains": REFERENCE_DOMAINS}],
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIStatusError as e:
        return {"error": f"{e.status_code}: {e.message}"}
    except anthropic.APIConnectionError as e:
        return {"error": f"connection: {e}"}
    text = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"\{.*\}", text, re.S)
    try:
        matches = json.loads(m.group(0)).get("matches", []) if m else []
    except json.JSONDecodeError:
        matches = []
    out = {"state_url": art["url"], "stop_reason": resp.stop_reason, "matches": matches,
           "usage": {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens,
                     "searches": getattr(getattr(resp.usage, "server_tool_use", None), "web_search_requests", None)}}
    f.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


_last = {}
def fetch(url):
    key = hashlib.sha256(url.encode()).hexdigest()
    f = HTML_CACHE / f"{key}.html"
    if f.exists():
        html = f.read_text(errors="ignore")
    else:
        dom = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
        wait = 2 - (time.time() - _last.get(dom, 0))
        if wait > 0: time.sleep(wait)
        _last[dom] = time.time()
        try:
            r = requests.get(url, headers=UA, timeout=25)
        except requests.RequestException:
            return None
        if r.status_code != 200: return None
        html = r.text; f.write_text(html)
    return trafilatura.extract(html) or None


def main(limit=None):
    arts = json.load(open(ROOT / "data/state_articles.json"))
    if limit: arts = arts[: int(limit)]
    client = anthropic.Anthropic()
    with ThreadPoolExecutor(4) as ex:
        results = list(ex.map(lambda a: ask(client, a, "claude-haiku-5-5"), arts))
        retry = [i for i, r in enumerate(results) if "error" in r or not r.get("matches")]
        print(f"haiku pass: {len(arts) - len(retry)} with matches; retrying {len(retry)} with {MODEL}")
        for i, r in zip(retry, ex.map(lambda i: ask(client, arts[i], MODEL), retry)):
            if "error" not in r and r.get("matches"): results[i] = r
    rows, tot = [], {"in": 0, "out": 0, "searches": 0, "errors": 0}
    for art, res in zip(arts, results):
        if "error" in res:
            tot["errors"] += 1; continue
        for k in ("in", "out", "searches"): tot[k] += res["usage"].get(k) or 0
        best = None
        for m in res["matches"]:
            url = m.get("url", "")
            if not any(d in url for d in REFERENCE_DOMAINS): continue
            text = fetch(url)
            if not text or len(text.split()) < 150: continue
            a = art["title"] + " " + " ".join(art["text"].split()[:300])
            b = (m.get("title") or "") + " " + " ".join(text.split()[:300])
            score = float(cosine_similarity(TfidfVectorizer().fit_transform([a, b]))[0, 1])
            cand = dict(country=art.get("country"), state_outlet=art.get("outlet"), state_url=art["url"],
                        state_title=art["title"], state_date=art["date"][:10], ref_outlet=m.get("outlet"),
                        ref_url=url, ref_title=m.get("title"), ref_date=m.get("date"),
                        score=round(score, 3), state_words=len(art["text"].split()), ref_words=len(text.split()))
            ref_file = ROOT / "data/articles" / f"{hashlib.sha256(url.encode()).hexdigest()}.json"
            if not ref_file.exists():
                ref_file.write_text(json.dumps({"url": url, "title": m.get("title"), "date": m.get("date"),
                                                "text": text, "words": len(text.split()),
                                                "domain": re.sub(r"^https?://(www\.)?", "", url).split("/")[0]},
                                               ensure_ascii=False))
            if not best or score > best["score"]: best = cand
        if best: rows.append(best)
    rows.sort(key=lambda r: -r["score"])
    with open(ROOT / "data/websearch_pairs.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["empty"]); w.writeheader(); w.writerows(rows)
    print(f"state articles: {len(arts)}  with a fetched same-event candidate: {len(rows)}")
    print("usage:", tot, " est. cost ~$%.2f" % (tot["in"] * 2e-6 + tot["out"] * 1e-5 + tot["searches"] * 0.01))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
