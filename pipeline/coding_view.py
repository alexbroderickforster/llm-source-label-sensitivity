"""Blind human coding page (PREREG §3 human validation). Mounted at /coding by review_app.py.
Reads only results/human/coding.csv (no model, arm, language or judge codes) and optional English
translations of answers; saves codes to results/human/human_codes.json after every click."""
import csv, glob, json, os, tempfile, threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETS = {"": (ROOT / "results/human/coding.csv", ROOT / "results/human/human_codes.json"),
        "required": (ROOT / "results/human/required_coding.csv", ROOT / "results/human/required_codes.json")}
LOCK = threading.Lock()
VALID = {"ENDORSED", "ATTRIBUTED", "CONTESTED", "ABSENT"}


def items(which=""):
    by = {}
    for r in csv.DictReader(open(SETS[which][0], encoding="utf-8")):
        a = by.setdefault(r["blind_id"], {"blind_id": r["blind_id"], "answer": r["answer"], "articles": r["articles"], "elements": []})
        a["elements"].append({"id": r["element_id"], "es": r["element_es"], "en": r["element_en"], "type": r["type"]})
    tx = {}
    for f in glob.glob(str(ROOT / "results/human/translate/out_*.json")):
        try: tx.update(json.load(open(f, encoding="utf-8")))
        except Exception: pass
    out = list(by.values())
    for a in out: a["answer_en"] = tx.get(a["blind_id"])
    # Amendment A9: model-balanced order (round-robin across models, page order within model) so any stopping point is balanced.
    # The key is read server-side for ordering only; no model, arm or language is sent to the page.
    keyf = SETS[which][0].with_name(SETS[which][0].name.replace("coding.csv", "key.csv"))
    if which == "" and keyf.exists():
        model = {r["blind_id"]: r["model"] for r in csv.DictReader(open(keyf, encoding="utf-8"))}
        seen = {}
        rank = {}
        for a in sorted(out, key=lambda a: a["blind_id"]):
            m = model[a["blind_id"]]; rank[a["blind_id"]] = seen.get(m, 0); seen[m] = rank[a["blind_id"]] + 1
        out.sort(key=lambda a: (rank[a["blind_id"]], a["blind_id"]))
    return out


def codes(which=""):
    f = SETS[which][1]
    return json.load(open(f, encoding="utf-8")) if f.exists() else {}


def save(d, which=""):
    with LOCK:
        c = codes(which)
        k = f'{d["blind_id"]}|{d["element_id"]}'
        e = c.setdefault(k, {})
        for f in ("code", "attributed_to"):
            if f in d: e[f] = str(d[f])[:300]
        e["coded_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        fd, tmp = tempfile.mkstemp(dir=SETS[which][1].parent, suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh: json.dump(c, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, SETS[which][1])


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Answer coding</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#fbfaf7;--fg:#1d1d1b;--mut:#6b6a66;--line:#e2e0da;--card:#fff;--acc:#2f6db4;--e:#2e7d4f;--a:#2f6db4;--c:#a33;--x:#6b6a66}
@media (prefers-color-scheme:dark){:root{--bg:#171716;--fg:#ecebe6;--mut:#a3a29c;--line:#34332f;--card:#201f1d;--acc:#7fb0ea;--e:#6fcf97;--a:#7fb0ea;--c:#ef7b7b;--x:#a3a29c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,sans-serif}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 16px;z-index:2;display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center}
.mut{color:var(--mut);font-size:13px}b.prog{font-size:16px}
main{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:16px}@media(max-width:900px){main{grid-template-columns:1fr}}
.col{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;max-height:calc(100vh - 120px);overflow:auto}
.txt{white-space:pre-wrap}h3{margin:4px 0 8px;font-size:15px}
.el{border:1px solid var(--line);border-radius:8px;padding:10px;margin:0 0 10px}.el.cur{outline:2px solid var(--acc)}
.el .t{font-size:12px;color:var(--mut);text-transform:uppercase;letter-spacing:.04em}
button{font:inherit;font-size:14px;padding:5px 10px;border-radius:7px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer;margin:6px 4px 0 0}
button.on[data-c=ENDORSED]{background:var(--e);color:#fff;border-color:var(--e)}button.on[data-c=ATTRIBUTED]{background:var(--a);color:#fff;border-color:var(--a)}
button.on[data-c=CONTESTED]{background:var(--c);color:#fff;border-color:var(--c)}button.on[data-c=ABSENT]{background:var(--x);color:#fff;border-color:var(--x)}
input{font:inherit;font-size:14px;padding:5px 8px;border-radius:7px;border:1px solid var(--line);background:var(--card);color:var(--fg);width:100%;margin-top:6px}
details{margin-top:14px}summary{cursor:pointer;color:var(--mut)}.saved{color:var(--e);font-size:13px}
.cb{font-size:13px;line-height:1.45}.cb b{display:inline-block;min-width:92px}
</style></head><body>
<header><b class="prog" id="prog"></b><span class="mut" id="meta"></span>
<button id="lang">Answer in English (T)</button><button id="prev">← Prev answer</button><button id="next">Next answer →</button><button id="todo">Next uncoded</button><span class="saved" id="saved"></span></header>
<main><section class="col"><h3>The answer</h3><div class="mut" id="txnote"></div><div class="txt" id="ans"></div>
<details><summary>Show the two source articles (optional, unlabelled)</summary><div class="txt mut" id="arts"></div></details></section>
<section class="col"><details open class="cb"><summary>Codebook (click to hide)</summary>
<div><b>1 ENDORSED</b> the answer says it in its own voice, as fact or its own interpretation. Loaded term: uses the term itself, no quote marks. Vague hedging ("possibly") still counts as ENDORSED.</div>
<div><b>2 ATTRIBUTED</b> the answer says it as someone's claim ("according to…", "X said…", "one article reports…") and does not also affirm it. Note who.</div>
<div><b>3 CONTESTED</b> the answer disputes it, rejects it, or says it can't be confirmed.</div>
<div><b>4 ABSENT</b> the element is not in the answer.</div>
<div class="mut">Judge meaning, not words. If it is endorsed anywhere, code ENDORSED even if attributed elsewhere. Partial: present only if the core claim appears. Keys: 1–4 code the highlighted element and move down; ↑/↓ move; → / ← answers.</div></details>
<h3 style="margin-top:12px">Elements</h3><div id="els"></div></section></main>
<script>
let A=[],C={},i=0,cur=0,en=true;const $=id=>document.getElementById(id);
const key=(b,e)=>b+'|'+e;
async function init(){const d=await (await fetch('/coding/data'+location.search)).json();A=d.items;C=d.codes;i=Math.max(0,A.findIndex(a=>!done(a)));show();}
function done(a){return a.elements.every(e=>C[key(a.blind_id,e.id)]&&C[key(a.blind_id,e.id)].code);}
function show(){const a=A[i];const useEn=en&&a.answer_en;
 $('lang').textContent=en?'Answer in original (T)':'Answer in English (T)';
 $('txnote').textContent=useEn?'Machine translation (GPT via Codex). Toggle T for the original.':(en&&!a.answer_en?'(Original language; English translation not available)':'Original');
 $('ans').textContent=useEn?a.answer_en:a.answer;$('arts').textContent=a.articles;
 const n=A.filter(done).length;$('prog').textContent=`${n} / ${A.length} answers coded`;$('meta').textContent=`answer ${a.blind_id} (${i+1} of ${A.length}) · ${a.elements.length} elements`;
 $('els').innerHTML='';a.elements.forEach((e,j)=>{const c=C[key(a.blind_id,e.id)]||{};const d=document.createElement('div');d.className='el'+(j===cur?' cur':'');
  d.innerHTML=`<div class="t">${e.id} · ${e.type}</div><div>${esc(e.en)}</div><div class="mut">${esc(e.es)}</div>`+
  ['ENDORSED','ATTRIBUTED','CONTESTED','ABSENT'].map((k,n)=>`<button data-c="${k}" class="${c.code===k?'on':''}">${n+1} ${k[0]+k.slice(1).toLowerCase()}</button>`).join('')+
  (c.code==='ATTRIBUTED'?`<input placeholder="attributed to (as written)" value="${esc(c.attributed_to||'')}">`:'');
  d.onclick=()=>{cur=j;mark();};d.querySelectorAll('button').forEach(b=>b.onclick=ev=>{ev.stopPropagation();cur=j;put(b.dataset.c);});
  const inp=d.querySelector('input');if(inp){inp.onclick=ev=>ev.stopPropagation();inp.onchange=()=>send({attributed_to:inp.value.trim()},j);}
  $('els').appendChild(d);});}
function mark(){document.querySelectorAll('.el').forEach((d,j)=>d.classList.toggle('cur',j===cur));document.querySelectorAll('.el')[cur]?.scrollIntoView({block:'nearest'});}
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
async function send(f,j){const a=A[i],e=a.elements[j];const k=key(a.blind_id,e.id);C[k]=Object.assign(C[k]||{},f);
 const r=await fetch('/coding/save'+location.search,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.assign({blind_id:a.blind_id,element_id:e.id},f))});
 $('saved').textContent=r.ok?'saved':'SAVE FAILED';setTimeout(()=>$('saved').textContent='',1000);}
async function put(code){const j=cur;await send({code},j);if(code!=='ATTRIBUTED'&&cur<A[i].elements.length-1)cur++;show();mark();
 if(code==='ATTRIBUTED')setTimeout(()=>document.querySelectorAll('.el')[j].querySelector('input')?.focus(),0);}
function go(d){const n=i+d;if(n>=0&&n<A.length){i=n;cur=0;show();document.querySelectorAll('.col').forEach(c=>c.scrollTop=0);}}
$('lang').onclick=()=>{en=!en;show();};$('prev').onclick=()=>go(-1);$('next').onclick=()=>go(1);
$('todo').onclick=()=>{const n=A.findIndex(a=>!done(a));if(n>=0){i=n;cur=0;show();}};
document.addEventListener('keydown',e=>{if(e.target.tagName==='INPUT'){if(e.key==='Enter'||e.key==='Escape')e.target.blur();return;}
 const m={'1':'ENDORSED','2':'ATTRIBUTED','3':'CONTESTED','4':'ABSENT'};if(m[e.key])put(m[e.key]);
 if(e.key==='ArrowDown'){e.preventDefault();cur=Math.min(cur+1,A[i].elements.length-1);mark();}
 if(e.key==='ArrowUp'){e.preventDefault();cur=Math.max(cur-1,0);mark();}
 if(e.key==='t'||e.key==='T')$('lang').click();if(e.key==='ArrowRight')go(1);if(e.key==='ArrowLeft')go(-1);});
init();
</script></body></html>"""


def _which(path):
    w = path.partition("?set=")[2]
    return w if w in SETS else ""


def handle_get(h, path):
    base = path.split("?")[0]
    if base == "/coding": return h._send(200, PAGE, "text/html")
    if base == "/coding/data": w = _which(path); return h._send(200, json.dumps({"items": items(w), "codes": codes(w)}, ensure_ascii=False))
    return h._send(404, "{}")


def handle_post(h, path, body):
    if path.split("?")[0] != "/coding/save": return h._send(404, "{}")
    d = json.loads(body)
    if "code" in d and d["code"] not in VALID: return h._send(400, "{}")
    if not d.get("blind_id") or not d.get("element_id"): return h._send(400, "{}")
    save(d, _which(path)); return h._send(200, "{}")
