"""Blind rotating judge. Default is an offline plan."""
import argparse
import json
import random
from pathlib import Path
from .common import CODES, ROOT, append_jsonl, now, read_jsonl, sha, terminal_answers
from .stimuli import DEFAULT, validate

JUDGES = {'gemini-3.8-flash': 'claude-sonnet-5-5', 'claude-sonnet-5-5': 'gpt-5.5-2026-04-23',
          'gpt-5.4-mini-2026-03-17': 'claude-sonnet-5-5', 'qwen/qwen3.8-27b': 'claude-sonnet-5-5'}

def build_judge_prompt(pair, answer):
    elements = [(side, e) for side in ('S', 'R') for e in pair['elements'][side]]
    rng = random.Random(int(sha(answer['cell_id']), 16))
    rng.shuffle(elements)
    mapping = {f'E{i}': {'side': side, 'element_id': e['id']} for i, (side, e) in enumerate(elements, 1)}
    template = (ROOT / 'prompts/judge.md').read_text(encoding='utf-8').split('```')[1].strip()
    # No original IDs, source side, arm, model, or language metadata is exposed.
    shown = [{'id': f'E{i}', 'type': e['type'], 'element_es': e['element_es'], 'element_en': e['element_en']}
             for i, (_, e) in enumerate(elements, 1)]
    sides = ['state', 'ref'] if pair['order'] == 'RT_first' else ['ref', 'state']
    articles = '\n\n'.join(f"Article {i}\nTitle: {pair[side]['title']}\n{pair[side]['text_stripped']}" for i, side in enumerate(sides, 1))
    return template + '\n\n' + articles + '\n\nElements:\n' + json.dumps(shown, ensure_ascii=False) + '\n\nAnswer:\n' + answer['answer'], mapping

def judge_prefix(pair):
    """Shared, identical-per-pair beginning of every judge prompt (instructions + articles); used only for prompt caching."""
    template = (ROOT / 'prompts/judge.md').read_text(encoding='utf-8').split('```')[1].strip()
    sides = ['state', 'ref'] if pair['order'] == 'RT_first' else ['ref', 'state']
    return template + '\n\n' + '\n\n'.join(f"Article {i}\nTitle: {pair[side]['title']}\n{pair[side]['text_stripped']}" for i, side in enumerate(sides, 1))

def parse_codes(text, mapping):
    # Tolerant of formatting only (code fences, trailing text, over-long optional evidence quotes); the codes themselves are validated strictly.
    start = text.find('{')
    if start < 0:
        raise ValueError('No JSON object')
    value, _ = json.JSONDecoder().raw_decode(text[start:])
    codes = value['codes']
    for c in codes:
        if isinstance(c, dict) and isinstance(c.get('evidence'), str) and len(c['evidence'].split()) > 25:
            c['evidence'] = ' '.join(c['evidence'].split()[:25])
    if not isinstance(codes, list) or len(codes) != len(mapping):
        raise ValueError('Incorrect code count')
    if {c['id'] for c in codes} != set(mapping):
        raise ValueError('Incorrect or repeated IDs')
    for c in codes:
        if c['code'] not in CODES or not {'attributed_to', 'evidence'} <= set(c):
            raise ValueError('Invalid code schema')
        if c['attributed_to'] is not None and not isinstance(c['attributed_to'], str):
            raise ValueError('Invalid attribution')
        if c['evidence'] is not None and (not isinstance(c['evidence'], str) or len(c['evidence'].split()) > 25):
            raise ValueError('Invalid evidence')
        if c['code'] == 'ATTRIBUTED' and not c['attributed_to']:
            raise ValueError('Attribution requires an identifiable source')
    return [dict(c, **mapping[c['id']]) for c in codes]

def run(answers, pairs, log_path, client):
    history = read_jsonl(log_path)
    done = {r['cell_id'] for r in history if r['status'] in ('done', 'human_required')}
    by_pair = {str(p['pair_id']): p for p in pairs}
    # Judge calls grouped by pair so the cached prefix stays warm; call order does not affect any single judgement.
    for answer in sorted(answers, key=lambda r: (str(r['pair_id']), r['cell_id'])):
        if answer['status'] != 'done' or answer['cell_id'] in done:
            continue
        prompt, mapping = build_judge_prompt(by_pair[answer['pair_id']], answer)
        prior = [r for r in history if r['cell_id'] == answer['cell_id']]
        if any(r['prompt_sha256'] != sha(prompt) for r in prior):
            raise ValueError('Judge input changed during resume')
        for attempt in range(len(prior) + 1, 4):  # original plus two retries
            row = {'cell_id': answer['cell_id'], 'model_requested': JUDGES[answer['model']],
                   'model_returned': None, 'prompt_sha256': sha(prompt), 'answer_sha256': sha(answer['answer']),
                   'mapping': mapping, 'attempt': attempt, 'started_at': now(), 'usage': {}, 'answer': None}
            try:
                prefix = judge_prefix(by_pair[answer['pair_id']])
                assert prompt.startswith(prefix)
                result = client.complete(row['model_requested'], prompt, max_tokens=4096, temperature=0, cache_prefix=prefix)
                row.update(answer=result['answer'], model_returned=result.get('model_returned'), usage=result.get('usage', {}))
                row['codes'] = parse_codes(result['answer'], mapping)
                row['status'] = 'done'
            except Exception as exc:
                row.update(status='parse_or_transport_error', error_type=type(exc).__name__)
            row['ended_at'] = now()
            append_jsonl(log_path, row)
            if row['status'] == 'done':
                break
        else:
            append_jsonl(log_path, {'cell_id': answer['cell_id'], 'status': 'human_required',
                                   'mapping': mapping, 'answer_sha256': sha(answer['answer']), 'ended_at': now()})

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--execute', action='store_true')
    ap.add_argument('--stimuli', type=Path, default=DEFAULT)
    ap.add_argument('--answers', type=Path, default=ROOT / 'results/raw/answers.jsonl')
    ap.add_argument('--judgments', type=Path, default=ROOT / 'results/raw/judgments.jsonl')
    ap.add_argument('--limit', type=int)
    a = ap.parse_args()
    pairs = validate(read_jsonl(a.stimuli))
    done = {r['cell_id'] for r in read_jsonl(a.judgments) if r['status'] in ('done', 'human_required')}
    answers = [r for r in terminal_answers(read_jsonl(a.answers)).values() if r['status'] == 'done' and r['cell_id'] not in done]
    if a.limit is not None:
        if a.limit < 0:
            raise SystemExit('--limit must be nonnegative')
        answers = answers[:a.limit]
    if not a.execute:
        print(json.dumps({'mode': 'dry-run', 'calls': len(answers), 'price': 'price unknown',
                          'plan': [{'cell_id': r['cell_id'], 'judge': JUDGES[r['model']]} for r in answers]}, indent=2))
        return
    from .clients import ProviderClient
    run(answers, pairs, a.judgments, ProviderClient())

if __name__ == '__main__':
    main()
