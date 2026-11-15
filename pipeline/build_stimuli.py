"""Assemble harness stimulus records from the review sheet, blinded element drafts and human element decisions.

  pilot: python pipeline/build_stimuli.py pilot   -> data/stimuli/pilot_records.jsonl (drafted elements, coordinator-written events)
  main:  python pipeline/build_stimuli.py main    -> data/stimuli/main_records.jsonl  (only human-kept elements; human event descriptors)
Then freeze order with harness.stimuli.build (seeded, balanced)."""
import csv, glob, hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Outlet descriptors for the true label (A2/A5). Wire copy is labelled as the agency.
DESCRIPTORS = {
    "infobae": ("diario argentino", "Argentine newspaper"), "extra": ("diario ecuatoriano", "Ecuadorian newspaper"),
    "emol": ("diario digital chileno", "Chilean news site"), "cronista": ("diario argentino", "Argentine newspaper"),
    "excelsior": ("diario mexicano", "Mexican newspaper"), "excélsior": ("diario mexicano", "Mexican newspaper"),
    "correo del sur": ("diario boliviano", "Bolivian newspaper"), "vistazo": ("revista ecuatoriana", "Ecuadorian magazine"),
    "mundo marítimo": ("sitio chileno de noticias marítimas", "Chilean maritime news site"),
    "abc color": ("diario paraguayo", "Paraguayan newspaper"), "caretas": ("revista peruana", "Peruvian magazine"),
    "contexto tucumán": ("medio digital argentino", "Argentine news site"), "el búho": ("medio digital peruano", "Peruvian news site"),
    "el comercio (ec)": ("diario ecuatoriano", "Ecuadorian newspaper"), "el universal (cartagena": ("diario colombiano", "Colombian newspaper"),
    "expansión política": ("medio digital mexicano", "Mexican news site"), "la prensa (hn)": ("diario hondureño", "Honduran newspaper"),
    "la republica (cr)": ("diario costarricense", "Costa Rican newspaper"), "la república (co)": ("diario colombiano", "Colombian newspaper"),
    "n+": ("cadena de noticias mexicana", "Mexican news network"), "ntn24": ("canal de noticias colombiano", "Colombian news channel"),
    "perfil": ("diario argentino", "Argentine newspaper"), "primicias": ("medio digital ecuatoriano", "Ecuadorian news site"),
    "teletica": ("canal de televisión costarricense", "Costa Rican TV channel"), "vanguardia": ("diario colombiano", "Colombian newspaper"),
    "iprofesional": ("medio digital argentino", "Argentine news site"), "última hora": ("diario paraguayo", "Paraguayan newspaper"),
}
NAMES = {"n+ / televisa": "N+", "el universal (cartagena, co)": "El Universal"}
WIRE = {"EFE": ("agencia de noticias española", "Spanish news agency"), "AFP": ("agencia de noticias francesa", "French news agency"),
        "Europa Press": ("agencia de noticias española", "Spanish news agency")}

PILOT = {  # pair: (event_es, event_en) — coordinator-written, neutral (pilot only)
    "p054": ("las declaraciones de la funcionaria antidrogas de EE.UU. Sara Carter sobre la presidenta Claudia Sheinbaum",
             "the remarks by US drug policy official Sara Carter about President Claudia Sheinbaum"),
    "p088": ("la votación de la Asamblea General de la ONU sobre el embargo de EE.UU. a Cuba",
             "the UN General Assembly vote on the US embargo against Cuba"),
    "p093": ("el discurso de José Antonio Kast ante la Asamblea General de la ONU", "José Antonio Kast's speech to the UN General Assembly"),
    "p055": ("la primera vuelta de las elecciones presidenciales de Brasil", "the first round of Brazil's presidential election"),
    "p013": ("las protestas contra el gobierno de Abelardo de la Espriella en Colombia", "the protests against Abelardo de la Espriella's government in Colombia"),
    "p018": ("el plan de Bolivia para convertir autobuses diésel a gas natural", "Bolivia's plan to convert diesel buses to natural gas"),
    "p089": ("las denuncias de torturas en la cárcel de Esmeraldas, Ecuador", "the torture allegations at the Esmeraldas prison in Ecuador"),
    "p072": ("la huelga de los trabajadores portuarios en Uruguay", "the port workers' strike in Uruguay"),
}


def descriptor(outlet, wire):
    if wire and wire in WIRE: return wire, *WIRE[wire]
    o = (outlet or "").lower()
    for k, v in DESCRIPTORS.items():
        if k in o: return NAMES.get(o, outlet.split(" (")[0]), *v
    raise KeyError(f"no descriptor for outlet {outlet!r}; add it to DESCRIPTORS")


def split_title(text):
    sep = "\n\n" if "\n\n" in text else "\n"
    head, _, body = text.partition(sep)
    return head.strip(), body.strip()


def load():
    key = json.load(open(ROOT / "data/elements_key.json"))
    ins = {p["pair"]: p for f in glob.glob(str(ROOT / "data/elements_in/*.json")) for p in json.load(open(f))}
    outs = {p["pair"]: p for f in glob.glob(str(ROOT / "data/elements_out/*.json")) for p in json.load(open(f))}
    rows = list(csv.DictReader(open(ROOT / "data/pair_review.csv")))
    return key, ins, outs, rows


def record(pid, key, ins, outs, rows, pilot, review=None, plan=None):
    k = key[pid]; r = rows[k["row"]]
    rt, rf = ("A", "B") if k["A"] == "RT" else ("B", "A")
    st_title, st_text = split_title(ins[pid][rt]); rf_title, rf_text = split_title(ins[pid][rf])
    def els(side, prefix):
        out = []
        for e in outs[pid][side]:
            ed = (review or {}).get("elements", {}).get(e["id"], {}) if review is not None else {}
            if review is not None:
                status = ed.get("status")
                if status is None:  # amendment A6: unreviewed elements are kept iff the verifier kept them and no human review was required
                    v = (plan or {}).get("elements", {}).get(e["id"], {})
                    status = "keep" if v.get("review") == "none" and v.get("verdict") == "keep" else None
                if status != "keep": continue
            out.append(dict(id=f"{prefix}{len(out)+1}", draft_id=e["id"], type=e["type"], element_es=ed.get("element_es") or e["element_es"],
                            element_en=ed.get("element_en") or e["element_en"], span=e["span"], why_absent=e.get("why_absent_from_other", "")))
        return out
    outlet, d_es, d_en = descriptor(r["ref_outlet"], r.get("wire"))
    ev_es, ev_en = (PILOT[pid] if pilot else (review["event_es"], review["event_en"]))
    return dict(pair_id=pid, event_id=r["event_id"] or pid, country=r["country"],
                state=dict(url=r["state_url"], title=st_title, text_stripped=st_text, domain="actualidad-rt.com"),
                ref=dict(url=r["ref_url"], title=rf_title, text_stripped=rf_text, outlet=outlet, descriptor_es=d_es, descriptor_en=d_en,
                         domain=r["ref_url"].split("/")[2].removeprefix("www.")),
                event_es=ev_es, event_en=ev_en, elements=dict(S=els(rt, "S"), R=els(rf, "R")), pilot=pilot)


def main(which):
    key, ins, outs, rows = load()
    if which == "pilot":
        recs = [record(pid, key, ins, outs, rows, True) for pid in PILOT]
        out = ROOT / "data/stimuli/pilot_records.jsonl"
    else:
        rev = json.load(open(ROOT / "data/elements_review.json"))
        plan = json.load(open(ROOT / "data/elements_verify/plan.json"))
        by_row = {v["row"]: p for p, v in key.items()}
        recs = []
        for n, r in enumerate(rows):
            if r.get("selected") != "main": continue
            pid = by_row[n]
            if rev.get(pid, {}).get("event_approved") not in ("yes", "ai"): raise SystemExit(f"{pid}: event descriptor not approved")
            recs.append(record(pid, key, ins, outs, rows, False, rev[pid], plan.get(pid)))
        out = ROOT / "data/stimuli/main_records.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as fh:
        for x in recs: fh.write(json.dumps(x, ensure_ascii=False) + "\n")
    print(f"{len(recs)} records -> {out}")


if __name__ == "__main__":
    main(sys.argv[1])
