"""Pair-level source-cue pass (PREREG amendment A5). Runs after the frozen strip_cues.py.
Replaces the names of the pair's own reference outlet (and its handle/short form) with "[medio]" in BOTH texts,
and removes byline fragments ("Publicado por: Redacción X"). Third-party outlets cited as sources are kept (PREREG §2)."""
import re

ALIASES = {"ABC Color": ["ABC Color", "ABC"], "Vanguardia": ["Vanguardia", "@vanguardiacom", "vanguardiacom"],
           "Telemundo 51": ["Telemundo 51", "Telemundo"], "Emol": ["Emol"], "Teletica": ["Teletica"]}


def names_for(outlet):
    base = re.sub(r"\s*\(.*\)", "", outlet or "").strip()
    return sorted(set(ALIASES.get(base, []) + ([base] if len(base) >= 4 else [])), key=len, reverse=True)


def pair_cues(text, outlet):
    log = []
    def sub(pattern, repl, t, kind):
        def f(m): log.append((kind, m.group())); return repl
        return re.sub(pattern, f, t)
    text = sub(r"Publicado por:\s*Redacci[oó]n\s+\w+\s*", "", text, "byline")
    for n in names_for(outlet):
        text = sub(r"(?<![\w@])" + re.escape(n) + r"(?!\w)", "[medio]", text, "pair_outlet")
    return text, log
