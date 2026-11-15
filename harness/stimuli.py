"""Frozen local stimulus JSONL format and validation.

Each line has pair_id, event_id, country; state {url,title,text_stripped,domain};
ref {url,title,text_stripped,outlet,descriptor_es,descriptor_en,domain}; event_es,
event_en; elements {S:[{id,type,element_es,element_en,span,why_absent_from_B}],
R:[{id,type,element_es,element_en,span,why_absent_from_A}]}; order and pilot.
Absence explanations may instead use the common key why_absent. They are
required because PREREG requires a recorded exclusivity rationale.
This builder consumes human-reviewed, already stripped records; it does not
infer eligibility, draft elements, translate, or alter protected source files.
"""
import argparse
import json
import random
from pathlib import Path
from pipeline.strip_cues import leak_scan
from .common import ROOT, read_jsonl

DEFAULT = ROOT / 'data/stimuli/pairs.jsonl'
TYPES = {'fact', 'causal attribution', 'characterisation', 'loaded term', 'quoted-actor claim'}

def validate_pair(p):
    for key in ('pair_id', 'event_id', 'country', 'event_es', 'event_en'):
        if not p.get(key):
            raise ValueError('Missing ' + key)
    if p.get('order') not in ('RT_first', 'REF_first') or type(p.get('pilot')) is not bool:
        raise ValueError('Invalid order or pilot flag')
    ids = []
    for side, article in (('S', p['state']), ('R', p['ref'])):
        keys = ['url', 'title', 'text_stripped', 'domain']
        if side == 'R':
            keys += ['outlet', 'descriptor_es', 'descriptor_en']
        if any(not isinstance(article.get(k), str) or not article[k].strip() for k in keys):
            raise ValueError('Missing article fields')
        if len(article['text_stripped'].split()) < 150:
            raise ValueError('Article under 150 words')
        if leak_scan(article['title'] + '\n' + article['text_stripped'])['remaining_cues']:
            raise ValueError('Source cue leak')
        elements = p['elements'][side]
        if not 3 <= len(elements) <= 5:
            raise ValueError('Require 3–5 elements per side')
        for e in elements:
            if any(not e.get(k) for k in ('id', 'type', 'element_es', 'element_en', 'span')):
                raise ValueError('Incomplete element')
            if e['type'] not in TYPES or e['span'] not in article['title'] + '\n' + article['text_stripped']:  # titles are shown to models (PREREG §2)
                raise ValueError('Invalid element type or supporting span')
            if not any(e.get(k) for k in ('why_absent', 'why_absent_from_A', 'why_absent_from_B')):
                raise ValueError('Missing exclusivity rationale')
            ids.append(e['id'])
    if len(set(ids)) != len(ids):
        raise ValueError('Element IDs must be unique within pair')
    return p

def validate(pairs):
    for p in pairs:
        validate_pair(p)
    if len({str(p['pair_id']) for p in pairs}) != len(pairs):
        raise ValueError('Duplicate pair IDs')
    main = [p for p in pairs if not p['pilot']]
    if len({p['event_id'] for p in main}) != len(main):
        raise ValueError('Repeated main event episode')
    return pairs

def build(records, output=None):
    # Sort before assignment so filesystem/input enumeration cannot change order.
    pairs = json.loads(json.dumps(sorted(records, key=lambda p: str(p['pair_id']))))
    rng = random.Random(20261113)
    # Balance pilot and main independently; odd strata differ by one.
    for pilot in (False, True):
        group = [p for p in pairs if p['pilot'] == pilot]
        orders = ['RT_first'] * (len(group) // 2) + ['REF_first'] * (len(group) - len(group) // 2)
        rng.shuffle(orders)
        for p, order in zip(group, orders):
            p['order'] = order
    validate(pairs)
    if output is not None:
        output = Path(output)
        if output.exists():
            raise FileExistsError('Refusing to overwrite frozen stimuli')
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(p, ensure_ascii=False) + '\n' for p in pairs), encoding='utf-8')
    return pairs

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, help='Human-reviewed JSONL to build')
    ap.add_argument('--output', type=Path, default=DEFAULT)
    a = ap.parse_args()
    pairs = build(read_jsonl(a.input), a.output) if a.input else validate(read_jsonl(a.output))
    print(json.dumps({'pairs': len(pairs), 'main': sum(not p['pilot'] for p in pairs),
                      'countries': len({p['country'] for p in pairs if not p['pilot']})}))

if __name__ == '__main__':
    main()
