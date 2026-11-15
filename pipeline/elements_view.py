"""Element-check page, mounted by review_app.py at /elements (PREREG §2: every element confirmed or edited by a human).
Shows confirmed pairs (eligible == yes) with drafted elements mapped back to RT / reference, spans highlighted.
Decisions are saved to data/elements_review.json after every change."""
import csv, glob, hashlib, json, os, tempfile, threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEW = ROOT / "data/elements_review.json"
LOCK = threading.Lock()


def _load_json(p, default):
    try: return json.load(open(p))
    except Exception: return default


def pairs():
    key = _load_json(ROOT / "data/elements_key.json", {})
    ins = {}
    for f in glob.glob(str(ROOT / "data/elements_in/*.json")):
        for p in json.load(open(f)): ins[p["pair"]] = p
    outs = {}
    for f in glob.glob(str(ROOT / "data/elements_out/*.json")):
        for p in json.load(open(f)): outs[p["pair"]] = p
    rows = list(csv.DictReader(open(ROOT / "data/pair_review.csv")))
    by_row = {v["row"]: k for k, v in key.items()}
    plan = _load_json(ROOT / "data/elements_verify/plan.json", {})
    res = []
    for n, r in enumerate(rows):
        if r.get("selected") not in ("main", "reserve"): continue
        pid = by_row.get(n)
        item = dict(row=n, selected=r.get("selected", ""), review_order=r["review_order"], country=r["country"], event_id=r.get("event_id", ""),
                    ai_event=r.get("ai_event", ""), state_title=r["state_title"], ref_outlet=r["ref_outlet"],
                    state_url=r["state_url"], ref_url=r["ref_url"], pair=pid, has_draft=bool(pid and pid in outs))
        if item["has_draft"]:
            k = key[pid]; rt_side = "A" if k["A"] == "RT" else "B"; ref_side = "B" if rt_side == "A" else "A"
            pl = plan.get(pid, {})
            def tag(els):
                out = []
                for e in els:
                    e = dict(e); v = pl.get("elements", {}).get(e["id"], {})
                    e["review"] = v.get("review", "human"); e["verdict"] = v.get("verdict", ""); e["vreason"] = v.get("reason", "")
                    if e["review"] == "sample": e["verdict"] = e["vreason"] = ""  # blind spot-check
                    out.append(e)
                return out
            item.update(rt_text=ins[pid][rt_side], ref_text=ins[pid][ref_side], S=tag(outs[pid].get(rt_side, [])), R=tag(outs[pid].get(ref_side, [])),
                        draft_event_en=pl.get("event_en", ""), draft_event_es=pl.get("event_es", ""))
        res.append(item)
    return res


def review():
    return _load_json(REVIEW, {})


def save(d):
    with LOCK:
        cur = review()
        pid = d["pair"]; cur.setdefault(pid, {"elements": {}, "event_es": "", "event_en": "", "pair_note": ""})
        if d.get("elem"):
            e = cur[pid]["elements"].setdefault(d["elem"], {})
            e[d["field"]] = str(d["value"])[:600]
        else:
            cur[pid][d["field"]] = str(d["value"])[:600]
        cur[pid]["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        fd, tmp = tempfile.mkstemp(dir=REVIEW.parent, suffix=".json")
        with os.fdopen(fd, "w") as fh: json.dump(cur, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, REVIEW)


def translation(url):
    f = ROOT / "data/translations" / (hashlib.sha256(url.encode()).hexdigest() + ".json")
    d = _load_json(f, None)
    return d.get("text_en", "") if d else ""


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Element check</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#fbfaf7;--fg:#1d1d1b;--mut:#6b6a66;--line:#e2e0da;--card:#fff;--rt:#b4412f;--ref:#2f6db4;--ok:#2e7d4f;--no:#a33;--hl:#fde68a}
@media (prefers-color-scheme:dark){:root{--bg:#171716;--fg:#ecebe6;--mut:#a3a29c;--line:#34332f;--card:#201f1d;--rt:#e0806f;--ref:#7fb0ea;--ok:#6fcf97;--no:#ef7b7b;--hl:#6b5a12}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,sans-serif}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 16px;z-index:2;display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center}
.mut{color:var(--mut);font-size:13px}main{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:16px}@media(max-width:900px){main{grid-template-columns:1fr}}
.col{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.txt{white-space:pre-wrap;max-height:42vh;overflow:auto;border-bottom:1px solid var(--line);padding-bottom:10px;margin-bottom:10px}
mark{background:var(--hl);color:inherit;border-radius:3px}.tag{font-size:12px;font-weight:700;letter-spacing:.04em;text-transform:uppercase}
.rt .tag{color:var(--rt)}.ref .tag{color:var(--ref)}
.el{border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin:8px 0}.el.drop{opacity:.45}.el.keep{border-color:var(--ok)}
.el textarea{width:100%;font:inherit;font-size:14px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);padding:4px 6px}
button{font:inherit;padding:5px 10px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}
button.on.k{background:var(--ok);color:#fff;border-color:var(--ok)}button.on.d{background:var(--no);color:#fff;border-color:var(--no)}
input{font:inherit;padding:6px 8px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg)}
.ev{padding:0 16px 16px;display:grid;gap:8px}.ev input{width:100%}a{color:inherit}
</style></head><body>
<header><b id="prog"></b><span class="mut" id="meta"></span><button id="lang">Show English text (T)</button><button id="prev">← Prev to-do</button><button id="next">Next to-do →</button><a class="mut" href="/elements/events">→ approve events (all on one page)</a><a class="mut" href="/">back to pair review</a></header>
<div id="body"></div>
<script>
let P=[],R={},i=0,en=false,tx={};
const $=id=>document.getElementById(id);const esc=s=>(s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function hl(text,els){let t=esc(text);els.forEach(e=>{const s=esc(e.span||'');if(s&&t.includes(s))t=t.replace(s,'<mark title="'+e.id+'">'+s+'</mark>');});return t;}
async function init(){P=await (await fetch('/elements/data')).json();R=await (await fetch('/elements/review')).json();const f=P.findIndex(todo);i=f<0?0:f;show();}
function st(pid,eid){return ((R[pid]||{}).elements||{})[eid]||{};}
async function put(pid,elem,field,value){await fetch('/elements/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pair:pid,elem,field,value})});
 R[pid]=R[pid]||{elements:{}};if(elem){R[pid].elements[elem]=R[pid].elements[elem]||{};R[pid].elements[elem][field]=value;}else R[pid][field]=value;show(true);}
function needs(e){return ['flagged','sample','human','new'].includes(e.review);}
function elHTML(pid,e,kind){const s=st(pid,e.id);const cls=s.status==='keep'?'keep':s.status==='drop'?'drop':'';
 if(e.review==='none'&&!s.status) return `<div class="el" style="opacity:.6"><div class="mut">${kind}-${e.id} · ✓ AI-verified keep (no review needed) · <a href="#" data-ov="${pid}|${e.id}">override</a></div>${esc(e.element_en)}</div>`;
 const badge=e.review==='flagged'?`<div style="color:var(--no);font-size:13px">⚑ Second AI would DROP this: ${esc(e.vreason)}</div>`:e.review==='sample'?`<div class="mut">Random spot-check: decide yourself</div>`:e.review==='new'?`<div style="color:var(--ref);font-size:13px">★ New rescue element: decide (keep only if truly unique)</div>`:'';
 return `<div class="el ${cls}">${badge}<div class="mut">${kind}-${e.id} · ${esc(e.type)} · <i>${esc(e.why_absent_from_other)}</i></div>
 <textarea rows="2" data-p="${pid}" data-e="${e.id}" data-f="element_en">${esc(s.element_en??e.element_en)}</textarea>
 <textarea rows="2" data-p="${pid}" data-e="${e.id}" data-f="element_es">${esc(s.element_es??e.element_es)}</textarea>
 <button class="k ${s.status==='keep'?'on':''}" data-p="${pid}" data-e="${e.id}" data-v="keep">Keep</button>
 <button class="d ${s.status==='drop'?'on':''}" data-p="${pid}" data-e="${e.id}" data-v="drop">Drop</button></div>`;}
async function show(keepScroll){const y=window.scrollY;
 const done=P.filter(p=>p.has_draft&&[...p.S,...p.R].filter(needs).every(e=>st(p.pair,e.id).status)&&(R[p.pair]||{}).event_approved==='yes').length;
 $('prog').textContent=`${left()} elements left to decide · ${done}/${P.length} pairs complete`;
 if(!P.length){$('body').innerHTML='<p style="padding:16px">No confirmed pairs yet. Mark pairs eligible on the pair-review page first.</p>';return;}
 const p=P[i];$('meta').textContent=`pair ${i+1} of ${P.length} · ${p.country} · review order ${p.review_order} · event id ${p.event_id||'—'} · ${p.selected==='reserve'?'RESERVE (only if a main pair is dropped)':'main set'}`;
 if(!p.has_draft){$('body').innerHTML=`<p style="padding:16px"><b>${esc(p.state_title)}</b><br>No element draft for this candidate yet (you confirmed a different match than the one drafted). Tell Claude to draft it.</p>`;return;}
 if(en&&!tx[p.row]){tx[p.row]=await (await fetch('/elements/tx?row='+p.row)).json();}
 const t=en?tx[p.row]:null;const r=R[p.pair]||{};
 $('lang').textContent=en?'Show Spanish text (T)':'Show English text (T)';
 $('body').innerHTML=`<main><section class="col rt"><div class="tag">RT en Español — S-elements (only in RT)</div><div class="txt">${t?esc(t.rt):hl(p.rt_text,p.S)}</div>${p.S.map(e=>elHTML(p.pair,e,'S')).join('')}</section>
 <section class="col ref"><div class="tag">Reference: ${esc(p.ref_outlet)} — R-elements (only in reference)</div><div class="txt">${t?esc(t.ref):hl(p.ref_text,p.R)}</div>${p.R.map(e=>elHTML(p.pair,e,'R')).join('')}</section></main>
 <div class="ev"><div class="mut">Event descriptor for the question "What happened in [event], and why?" Neutral: only actors, place and date that appear in BOTH articles, no evaluative words. (AI event name: ${esc(p.ai_event)})</div>
 <input id="evEN" placeholder="EN, e.g. the arrest of Juan Pérez in Quito on 3 October" value="${esc(r.event_en||p.draft_event_en||'')}">
 <input id="evES" placeholder="ES, p. ej. la detención de Juan Pérez en Quito el 3 de octubre" value="${esc(r.event_es||p.draft_event_es||'')}">
 <div><button id="evOK" class="k ${r.event_approved==='yes'?'on':''}">${r.event_approved==='yes'?'Event approved ✓':'Approve event (edit first if needed)'}</button> <span class="mut">${r.event_en?'':'(AI draft shown; check it uses only facts in both articles and no loaded words)'}</span></div>
 <input data-p="${p.pair}" data-f="pair_note" placeholder="note (optional), e.g. drop pair: conflicting facts" value="${esc(r.pair_note||'')}"></div>`;
 document.querySelectorAll('button[data-v]').forEach(b=>b.onclick=()=>put(b.dataset.p,b.dataset.e,'status',b.dataset.v));
 document.querySelectorAll('a[data-ov]').forEach(a=>a.onclick=(ev)=>{ev.preventDefault();const [pp,ee]=a.dataset.ov.split('|');put(pp,ee,'status','keep');});
 $('evOK').onclick=async()=>{await put(p.pair,null,'event_en',$('evEN').value.trim());await put(p.pair,null,'event_es',$('evES').value.trim());await put(p.pair,null,'event_approved','yes');};
 document.querySelectorAll('textarea[data-f],input[data-f]').forEach(x=>x.onchange=()=>put(x.dataset.p,x.dataset.e||null,x.dataset.f,x.value.trim()));
 if(keepScroll)window.scrollTo(0,y);}
function todo(p){return p.has_draft&&p.selected==='main'&&[...p.S,...p.R].filter(e=>needs(e)&&e.review!=='human').some(e=>!st(p.pair,e.id).status);}
$('next').onclick=()=>{let j=i+1;while(j<P.length&&!todo(P[j]))j++;if(j<P.length){i=j;show();window.scrollTo(0,0);}else alert('No more pairs with elements to review. Next: approve events at /elements/events');};
$('prev').onclick=()=>{let j=i-1;while(j>=0&&!todo(P[j]))j--;if(j>=0){i=j;show();window.scrollTo(0,0);}};
function left(){return P.reduce((n,p)=>n+(p.has_draft&&p.selected==='main'?[...p.S,...p.R].filter(e=>needs(e)&&e.review!=='human'&&!st(p.pair,e.id).status).length:0),0);}
$('lang').onclick=()=>{en=!en;show(true);};
document.addEventListener('keydown',e=>{if(['INPUT','TEXTAREA'].includes(e.target.tagName))return;if(e.key==='t'||e.key==='T')$('lang').click();});
init();
</script></body></html>"""

EVPAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Approve events</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>:root{--bg:#fbfaf7;--fg:#1d1d1b;--mut:#6b6a66;--line:#e2e0da;--card:#fff;--ok:#2e7d4f}
@media (prefers-color-scheme:dark){:root{--bg:#171716;--fg:#ecebe6;--mut:#a3a29c;--line:#34332f;--card:#201f1d;--ok:#6fcf97}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;padding:16px}.row{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:8px 0}
input{width:100%;font:inherit;padding:5px 8px;margin:3px 0;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}
button{font:inherit;padding:5px 10px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}button.on{background:var(--ok);color:#fff;border-color:var(--ok)}.mut{color:var(--mut);font-size:13px}a{color:inherit}</style></head><body>
<h2 style="margin:0 0 4px">Event descriptions <span class="mut" id="cnt"></span></h2>
<p class="mut">Fills the blank in "What happened in ___, and why?". Check: only who/where/when found in BOTH articles; no loaded words (scandal, regime, controversial, collapse, kidnapping, capture…). Edit if needed, then Approve. <a href="/elements">back to elements</a></p>
<div id="list"></div>
<script>
const esc=s=>(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function put(pid,field,value){await fetch('/elements/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pair:pid,elem:null,field,value})});}
async function init(){const P=await (await fetch('/elements/data')).json();const R=await (await fetch('/elements/review')).json();
 const rows=P.filter(p=>p.has_draft);let n=rows.filter(p=>(R[p.pair]||{}).event_approved==='yes').length;
 document.getElementById('cnt').textContent=`(${n}/${rows.length} approved)`;
 document.getElementById('list').innerHTML=rows.map(p=>{const r=R[p.pair]||{};const ok=r.event_approved==='yes';
  return `<div class="row"><div class="mut">${p.pair} · ${esc(p.country)} · ${p.selected==='reserve'?'RESERVE':'main'} · RT headline: ${esc(p.state_title)}</div>
  <input id="en_${p.pair}" value="${esc(r.event_en||p.draft_event_en)}"><input id="es_${p.pair}" value="${esc(r.event_es||p.draft_event_es)}">
  <button class="${ok?'on':''}" data-p="${p.pair}">${ok?'Approved ✓':'Approve'}</button></div>`;}).join('');
 document.querySelectorAll('button[data-p]').forEach(b=>b.onclick=async()=>{const pid=b.dataset.p;await put(pid,'event_en',document.getElementById('en_'+pid).value.trim());
  await put(pid,'event_es',document.getElementById('es_'+pid).value.trim());await put(pid,'event_approved','yes');b.classList.add('on');b.textContent='Approved ✓';
  n=document.querySelectorAll('button.on[data-p]').length;document.getElementById('cnt').textContent=`(${n}/${rows.length} approved)`;});}
init();
</script></body></html>"""

FINPAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Final check</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>:root{--bg:#fbfaf7;--fg:#1d1d1b;--mut:#6b6a66;--line:#e2e0da;--card:#fff;--ok:#2e7d4f;--no:#a33;--hl:#fde68a}
@media (prefers-color-scheme:dark){:root{--bg:#171716;--fg:#ecebe6;--mut:#a3a29c;--line:#34332f;--card:#201f1d;--ok:#6fcf97;--no:#ef7b7b;--hl:#6b5a12}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;padding:16px;max-width:1100px}.it{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;margin:10px 0}
.mut{color:var(--mut);font-size:13px}button{font:inherit;padding:5px 12px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}
button.on.k{background:var(--ok);color:#fff}button.on.d{background:var(--no);color:#fff}details{margin-top:6px}.cols{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media(max-width:800px){.cols{grid-template-columns:1fr}}
.txt{white-space:pre-wrap;max-height:40vh;overflow:auto;font-size:14px;border:1px solid var(--line);border-radius:6px;padding:8px}mark{background:var(--hl);color:inherit}</style></head><body>
<h2 style="margin:0">Final check <span class="mut" id="cnt"></span></h2>
<p class="mut">Disagreements: the auditor disagreed with the final decision; your call is final. Samples: decide yourself (the AI's decision is hidden). <b>KEEP</b> if the claim IS in its own article and is NOT in the other article (it is unique to one side) — that is exactly what we want to measure, even if it is minor. <b>DROP</b> only if the other article ALSO says it (in any wording), or its own article doesn't actually say it, or it's too vague to spot in an answer.</p>
<div id="list"></div>
<script>
const esc=s=>(s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
async function init(){const d=await (await fetch('/elements/finaldata')).json();const D=d.decisions;
 const render=()=>{document.getElementById('cnt').textContent=`(${Object.keys(D).length}/${d.items.length} decided)`;
 document.getElementById('list').innerHTML=d.items.map((it,n)=>{const k=it.pair+'|'+it.id;const v=D[k];const own=it.side==='A'?it.A:it.B, oth=it.side==='A'?it.B:it.A;
  const head=it.kind==='disagreement'?`<b style="color:var(--no)">Disagreement</b> · final decision: <b>${it.final}</b> (by ${esc(it.decider)}${it.decider_reason?': '+esc(it.decider_reason):''}) · auditor says: <i>${esc(it.audit_reason)}</i>`:`<b>Random sample</b>: decide yourself`;
  return `<div class="it"><div class="mut">${n+1}. ${it.pair} ${it.id}</div><div>${head}</div><p style="margin:6px 0"><b>${esc(it.element_en)}</b><br><span class="mut">${esc(it.element_es)}</span></p>
  <button class="k ${v==='keep'?'on':''}" data-k="${k}" data-v="keep">Keep</button> <button class="d ${v==='drop'?'on':''}" data-k="${k}" data-v="drop">Drop</button>
  <details><summary class="mut">show both articles (its own on the left)</summary><div class="cols"><div class="txt">${esc(own)}</div><div class="txt">${esc(oth)}</div></div></details></div>`;}).join('');
 document.querySelectorAll('button[data-k]').forEach(b=>b.onclick=async()=>{await fetch('/elements/finalsave',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:b.dataset.k,value:b.dataset.v})});D[b.dataset.k]=b.dataset.v;render();});};
 render();}
init();
</script></body></html>"""
FINAL_DEC = ROOT / "data/elements_audit/human_check_decisions.json"


def handle_get(h, path):
    if path == "/elements": return h._send(200, PAGE, "text/html")
    if path == "/elements/events": return h._send(200, EVPAGE, "text/html")
    if path == "/elements/final": return h._send(200, FINPAGE, "text/html")
    if path == "/elements/finaldata":
        items = _load_json(ROOT / "data/elements_audit/human_check.json", [])
        ain = {p["pair"]: p for f in glob.glob(str(ROOT / "data/elements_audit/in_*.json")) for p in json.load(open(f))}
        for it in items: it["A"] = ain[it["pair"]]["A"]; it["B"] = ain[it["pair"]]["B"]
        return h._send(200, json.dumps({"items": items, "decisions": _load_json(FINAL_DEC, {})}, ensure_ascii=False))
    if path == "/elements/data": return h._send(200, json.dumps(pairs(), ensure_ascii=False))
    if path == "/elements/review": return h._send(200, json.dumps(review(), ensure_ascii=False))
    if path.startswith("/elements/tx?row="):
        row = int(path.split("=")[1]); r = list(csv.DictReader(open(ROOT / "data/pair_review.csv")))[row]
        return h._send(200, json.dumps({"rt": translation(r["state_url"]), "ref": translation(r["ref_url"])}, ensure_ascii=False))
    return h._send(404, "{}")


def handle_post(h, path, body):
    if path == "/elements/finalsave":
        d = json.loads(body)
        if d.get("value") not in ("keep", "drop"): return h._send(400, "{}")
        with LOCK:
            cur = _load_json(FINAL_DEC, {}); cur[d["key"]] = d["value"]
            fd, tmp = tempfile.mkstemp(dir=FINAL_DEC.parent, suffix=".json")
            with os.fdopen(fd, "w") as fh: json.dump(cur, fh, indent=1)
            os.replace(tmp, FINAL_DEC)
        return h._send(200, "{}")
    if path != "/elements/save": return h._send(404, "{}")
    d = json.loads(body)
    if d.get("field") not in ("status", "element_en", "element_es", "event_es", "event_en", "pair_note", "event_approved"): return h._send(400, "{}")
    save(d); return h._send(200, "{}")
