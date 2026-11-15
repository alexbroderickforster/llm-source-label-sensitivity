"""Local pair-review page (PREREG §2). Run:  .venv/bin/python pipeline/review_app.py   then open http://127.0.0.1:8765
Reads data/pair_review.csv (seeded order) and article texts; saves decisions back to the CSV after every click.
Binds to 127.0.0.1 only. No external requests."""
import csv, hashlib, json, os, tempfile, threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys; sys.path.insert(0, str(Path(__file__).resolve().parent)); import elements_view, coding_view

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data/pair_review.csv"
STATE = json.load(open(ROOT / "data/state_articles.json"))
LOCK = threading.Lock()
EDITABLE = ["event_id", "same_event_same_stage", "eligible", "reason", "reviewed_at"]


def load():
    with open(CSV, newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for c in EDITABLE: r.setdefault(c, "")
    return rows


def save(rows):
    cols = list(rows[0].keys())
    fd, tmp = tempfile.mkstemp(dir=CSV.parent, suffix=".csv")
    with os.fdopen(fd, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows)
    os.replace(tmp, CSV)


def translation(url):
    f = ROOT / "data/translations" / (hashlib.sha256(url.encode()).hexdigest() + ".json")
    if not f.exists(): return None
    try:
        d = json.load(open(f)); return {"title": d.get("title_en", ""), "text": d.get("text_en", "")}
    except Exception: return None


def ref_text(url):
    f = ROOT / "data/articles" / (hashlib.sha256(url.encode()).hexdigest() + ".json")
    return json.load(open(f))["text"] if f.exists() else "(text not fetched; open the link)"


PAGE = r"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Pair review</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#fbfaf7;--fg:#1d1d1b;--mut:#6b6a66;--line:#e2e0da;--card:#fff;--rt:#b4412f;--ref:#2f6db4;--ok:#2e7d4f;--no:#a33}
@media (prefers-color-scheme:dark){:root{--bg:#171716;--fg:#ecebe6;--mut:#a3a29c;--line:#34332f;--card:#201f1d;--rt:#e0806f;--ref:#7fb0ea;--ok:#6fcf97;--no:#ef7b7b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,sans-serif}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 16px;z-index:2}
.bar{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center}.mut{color:var(--mut);font-size:13px}
.prog{font-weight:600}.flags{color:var(--no);font-size:13px}
main{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:16px}@media(max-width:900px){main{grid-template-columns:1fr}}
.col{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;max-height:calc(100vh - 250px);overflow:auto}
.col h2{font-size:17px;margin:4px 0 6px}.tag{font-size:12px;font-weight:700;letter-spacing:.04em;text-transform:uppercase}
.rt .tag{color:var(--rt)}.ref .tag{color:var(--ref)}.txt{white-space:pre-wrap}a{color:inherit}
footer{position:sticky;bottom:0;background:var(--bg);border-top:1px solid var(--line);padding:10px 16px;display:flex;flex-wrap:wrap;gap:10px;align-items:center}
button{font:inherit;padding:7px 12px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}
button.on.yes{background:var(--ok);color:#fff;border-color:var(--ok)}button.on.no{background:var(--no);color:#fff;border-color:var(--no)}
input{font:inherit;padding:7px 9px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg)}
.grp{display:flex;gap:6px;align-items:center}.saved{font-size:13px;color:var(--ok)}
</style></head><body>
<header><div class="bar"><span class="prog" id="prog"></span><span class="mut" id="meta"></span><span class="flags" id="flags"></span><a class="mut" href="/elements">→ element check</a></div>
<div class="mut" id="note"></div></header>
<main><section class="col rt"><div class="tag">RT en Español</div><h2 id="st"></h2><div class="mut" id="sm"></div><div class="txt" id="sx"></div></section>
<section class="col ref"><div class="tag" id="rtag">Reference</div><h2 id="rt"></h2><div class="mut" id="rm"></div><div class="txt" id="rx"></div></section></main>
<footer>
<div class="grp">Same event &amp; same stage? <button data-f="same_event_same_stage" data-v="yes" class="yes">Yes (1)</button><button data-f="same_event_same_stage" data-v="no" class="no">No (2)</button></div>
<div class="grp">Eligible? <button data-f="eligible" data-v="yes" class="yes">Yes (3)</button><button data-f="eligible" data-v="no" class="no">No (4)</button></div>
<input id="eid" placeholder="event id (same story = same id)" size="26"><input id="reason" placeholder="reason (short)" size="30">
<button id="lang">Show English (T)</button><button id="prev">← Prev</button><button id="next">Next →</button><span class="saved" id="saved"></span>
<span class="mut">Exclude: opinion/analysis, &lt;150 words, paywall, different stage, outside ±3 days.</span>
</footer>
<script>
let rows=[],i=0,en=false;
const $=id=>document.getElementById(id);
async function init(){rows=await (await fetch('/rows')).json();i=Math.max(0,rows.findIndex(r=>!r.eligible));show();}
async function show(){const r=rows[i];const d=await (await fetch('/pair?i='+i)).json();
 const se=en&&d.state_en, re_=en&&d.ref_en;$('lang').textContent=en?'Show Spanish (T)':'Show English (T)';
 $('st').textContent=se?d.state_en.title:r.state_title;$('sm').innerHTML=`${r.state_date} · ${r.country} · ${r.state_words} words · <a href="${r.state_url}" target="_blank" rel="noopener">open</a>`;$('sx').textContent=se?d.state_en.text:(en?'(English translation not ready yet — showing Spanish)\n\n':'')+d.state;
 $('rtag').textContent='Reference: '+r.ref_outlet+(r.wire?' ('+r.wire+')':'');$('rt').textContent=re_?d.ref_en.title:r.ref_title;
 $('rm').innerHTML=`${r.ref_date} (${r.day_gap} days apart) · ${r.ref_words} words · similarity ${r.tfidf} · <a href="${r.ref_url}" target="_blank" rel="noopener">open</a>`;$('rx').textContent=re_?d.ref_en.text:(en?'(English translation not ready yet — showing Spanish)\n\n':'')+d.ref;
 $('flags').textContent=r.auto_flags?'⚠ '+r.auto_flags:'';$('note').innerHTML=(r.ai_eligible?`<b>AI suggestion:</b> same event/stage <b>${r.ai_same_stage}</b>, eligible <b>${r.ai_eligible}</b> (${r.ai_confidence}) — ${r.ai_reason} · event: <i>${r.ai_event}</i><br>`:'<b>AI suggestion:</b> none (not screened)<br>')+'Search-agent note: '+(r.agent_note||'—');
 $('eid').value=r.event_id||'';$('reason').value=r.reason||'';
 document.querySelectorAll('button[data-f]').forEach(b=>b.classList.toggle('on',r[b.dataset.f]===b.dataset.v));
 const elig=new Set(rows.filter(x=>x.eligible==='yes').map(x=>x.event_id||('art'+x.state_idx)));
 const done=rows.filter(x=>x.eligible).length;
 $('prog').textContent=`${elig.size} / 40 eligible events`;$('meta').textContent=`row ${i+1} of ${rows.length} · review order ${r.review_order} · ${done} rows decided · cutoff Sat 14 Nov 22:00 UTC (5 pm EST)`;
 document.querySelectorAll('.col').forEach(c=>c.scrollTop=0);}
async function put(f,v){rows[i][f]=v;const r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({i,field:f,value:v})});
 $('saved').textContent=r.ok?'saved':'SAVE FAILED';setTimeout(()=>$('saved').textContent='',1200);show();}
document.querySelectorAll('button[data-f]').forEach(b=>b.onclick=()=>put(b.dataset.f,b.dataset.v));
$('eid').onchange=e=>put('event_id',e.target.value.trim());$('reason').onchange=e=>put('reason',e.target.value.trim());
$('lang').onclick=()=>{en=!en;show();};$('next').onclick=()=>{if(i<rows.length-1){i++;show();}};$('prev').onclick=()=>{if(i>0){i--;show();}};
document.addEventListener('keydown',e=>{if(e.target.tagName==='INPUT')return;
 const m={'1':['same_event_same_stage','yes'],'2':['same_event_same_stage','no'],'3':['eligible','yes'],'4':['eligible','no']};
 if(m[e.key])put(...m[e.key]);if(e.key==='t'||e.key==='T')$('lang').click();if(e.key==='ArrowRight')$('next').click();if(e.key==='ArrowLeft')$('prev').click();});
init();
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code); self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/elements"):
            return elements_view.handle_get(self, self.path)
        if self.path.startswith("/coding"):
            return coding_view.handle_get(self, self.path)
        if self.path == "/":
            return self._send(200, PAGE, "text/html")
        if self.path == "/rows":
            return self._send(200, json.dumps(load(), ensure_ascii=False))
        if self.path.startswith("/pair?i="):
            r = load()[int(self.path.split("=")[1])]
            return self._send(200, json.dumps({"state": STATE[int(r["state_idx"])]["text"], "ref": ref_text(r["ref_url"]),
                                               "state_en": translation(r["state_url"]), "ref_en": translation(r["ref_url"])}, ensure_ascii=False))
        self._send(404, "{}")

    def do_POST(self):
        if self.path.startswith("/elements"):
            return elements_view.handle_post(self, self.path, self.rfile.read(int(self.headers["Content-Length"])))
        if self.path.startswith("/coding"):
            return coding_view.handle_post(self, self.path, self.rfile.read(int(self.headers["Content-Length"])))
        if self.path != "/save": return self._send(404, "{}")
        d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if d.get("field") not in EDITABLE[:-1]: return self._send(400, "{}")
        with LOCK:
            rows = load()
            rows[int(d["i"])][d["field"]] = str(d["value"])[:300]
            rows[int(d["i"])]["reviewed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            save(rows)
        self._send(200, "{}")

    def log_message(self, *a): pass


if __name__ == "__main__":
    print("Pair review on http://127.0.0.1:8765  (Ctrl-C to stop)")
    ThreadingHTTPServer(("127.0.0.1", 8765), H).serve_forever()
