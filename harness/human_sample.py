"""Create a balanced random, blinded answer-level validation sample."""
import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path
from .common import ROOT, MODELS, ARMS, LANGS, read_jsonl, terminal_answers
from .stimuli import DEFAULT

SAMPLE_SEED = 20261117

def sample(answers, n=120):
    groups = defaultdict(list)
    for r in answers:
        if r['status'] == 'done' and not r['pilot'] and not r['replicate']:
            groups[(r['model'], r['arm'], r['lang'])].append(r)
    if sum(map(len, groups.values())) < n:
        raise ValueError(f'Need {n} eligible answers')
    expected = {(m, a, l) for m in MODELS for a in ARMS for l in LANGS}
    if set(groups) != expected:
        raise ValueError(f'Validation sample requires all {len(expected)} model×arm×language strata')
    rng = random.Random(SAMPLE_SEED)
    for group in groups.values():
        group.sort(key=lambda r: r['cell_id'])
        rng.shuffle(group)
    keys = sorted(groups)
    rng.shuffle(keys)
    chosen = []
    while len(chosen) < n:
        for key in keys:
            if groups[key] and len(chosen) < n:
                chosen.append(groups[key].pop())
    rng.shuffle(chosen)
    return chosen

def write_sample(answers, pairs, directory, n=120):
    selected = sample(answers, n)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    sheet, key = directory / 'coding.csv', directory / 'key.csv'
    if sheet.exists() or key.exists():
        raise FileExistsError('Refusing to overwrite human coding files')
    by_pair = {str(p['pair_id']): p for p in pairs}
    rng = random.Random(SAMPLE_SEED)
    with sheet.open('w', newline='', encoding='utf-8') as sf, key.open('w', newline='', encoding='utf-8') as kf:
        sw = csv.DictWriter(sf, fieldnames=['blind_id', 'element_id', 'element_es', 'element_en', 'type', 'articles', 'answer', 'code', 'attributed_to', 'evidence'])
        kw = csv.DictWriter(kf, fieldnames=['blind_id', 'element_id', 'cell_id', 'original_element_id', 'pair_id', 'arm', 'model', 'lang'])
        sw.writeheader(); kw.writeheader()
        for i, answer in enumerate(selected, 1):
            p = by_pair[answer['pair_id']]
            elements = [e for side in ('S', 'R') for e in p['elements'][side]]
            rng.shuffle(elements)
            articles = '\n\n'.join(p[s]['title'] + '\n' + p[s]['text_stripped'] for s in (('state', 'ref') if p['order'] == 'RT_first' else ('ref', 'state')))
            for j, e in enumerate(elements, 1):
                sw.writerow(dict(blind_id=f'B{i:03}', element_id=f'E{j}', element_es=e['element_es'], element_en=e['element_en'],
                                 type=e['type'], articles=articles, answer=answer['answer'], code='', attributed_to='', evidence=''))
                kw.writerow(dict(blind_id=f'B{i:03}', element_id=f'E{j}', cell_id=answer['cell_id'], original_element_id=e['id'],
                                 pair_id=answer['pair_id'], arm=answer['arm'], model=answer['model'], lang=answer['lang']))
    return sheet, key

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--answers', type=Path, default=ROOT / 'results/raw/answers.jsonl')
    ap.add_argument('--stimuli', type=Path, default=DEFAULT)
    ap.add_argument('--output', type=Path, default=ROOT / 'results/human')
    a = ap.parse_args()
    write_sample(list(terminal_answers(read_jsonl(a.answers)).values()), read_jsonl(a.stimuli), a.output)
    print('Wrote coding.csv and separate key.csv. Give the coder only coding.csv and the frozen codebook.')

if __name__ == '__main__':
    main()
