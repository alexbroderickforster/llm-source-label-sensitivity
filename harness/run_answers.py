"""Plan by default; an explicit --execute is the only path to SDK use."""
import argparse
import time
import json
import random
import re
from pathlib import Path
from .common import ARMS, LANGS, MODELS, MODEL_ROLES, ROOT, append_jsonl, cell_id, now, read_jsonl, sha, terminal_answers
from .prompts import build_prompt
from .stimuli import DEFAULT, validate

# TODO: fill verified USD per million input/output tokens before budgeting a run.
PRICING = {m: {'input': None, 'output': None} for m in MODELS}
EXECUTION_SEED = 20261116
MAX_OUTPUT_TOKENS = 4096  # PREREG amendment A4 (was 1,024; thinking models truncated in the pilot)
RATE_LIMIT_WAITS = [10, 20, 40, 60, 60, 90, 120, 120, 180, 240]  # A4: rate limits are waited out, not counted as transport errors

def plan(pairs, models=MODELS, arms=ARMS, pilot=False, langs=LANGS):
    pairs = sorted([p for p in pairs if p['pilot'] == pilot], key=lambda p: str(p['pair_id']))
    selected = set(random.Random(20261115).sample([str(p['pair_id']) for p in pairs], int(len(pairs) * .2 + .5)))
    cells = []
    for p in pairs:
        for arm in arms:
            for model in models:
                for lang in langs:
                    for replicate in range(2 if str(p['pair_id']) in selected else 1):
                        cells.append(dict(cell_id=cell_id(p['pair_id'], arm, model, lang, replicate), pair_id=str(p['pair_id']),
                                          arm=arm, model=model, model_role=MODEL_ROLES[model], lang=lang, replicate=replicate, pilot=pilot))
    random.Random(EXECUTION_SEED).shuffle(cells)
    return cells

def invalid_reason(response):
    text = response.get('answer', '')
    if not text.strip():
        return 'empty'
    refusal = re.search(
        r"(?i)^(?:(?:i(?:['’]m| am) sorry|sorry|lo siento)[,.:! ]*(?:but |pero )?)?"
        r"(?:i (?:cannot|can['’]t|will not|won['’]t|am unable to) "
        r"(?:help|assist|answer|comply|fulfil|respond|provide)|"
        r"no (?:puedo|estoy en condiciones de) (?:ayudar|responder|cumplir|proporcionar|atender|realizar))\b",
        text.strip())
    if response.get('refusal') or refusal:
        return 'refusal'
    if len(text.split()) < 30:
        return 'under_30_words'
    return None

def run(cells, pairs, log_path, client):
    done = terminal_answers(read_jsonl(log_path))
    by_pair = {str(p['pair_id']): p for p in pairs}
    history = read_jsonl(log_path)
    for cell in cells:
        if cell['cell_id'] in done:
            continue
        prompt = build_prompt(by_pair[cell['pair_id']], cell['arm'], cell['lang'])
        previous = [r for r in history if r['cell_id'] == cell['cell_id']]
        if any(r['prompt_sha256'] != sha(prompt) for r in previous):
            raise ValueError('Prompt changed during resume')
        attempt = max([r['attempt'] for r in previous], default=0)
        # Resume the same generation after interruption, preserving retry budget.
        generation = max([r['generation'] for r in previous], default=0)
        if previous and previous[-1]['status'] == 'invalid':
            generation += 1
        while generation < 2:
            old = [r for r in previous if r['generation'] == generation and r['status'] == 'transport_error']
            response = None
            for transport in range(len(old), 4):  # original request plus 3 retries
                attempt += 1
                row = dict(cell, model_requested=cell['model'], model_returned=None, prompt_sha256=sha(prompt),
                           answer=None, usage={}, started_at=now(), attempt=attempt, generation=generation, transport_attempt=transport)
                try:
                    for wait in RATE_LIMIT_WAITS + [None]:
                        try:
                            response = client.complete(cell['model'], prompt, max_tokens=MAX_OUTPUT_TOKENS)
                            break
                        except Exception as exc:
                            if wait is None or not ('RateLimit' in type(exc).__name__ or type(exc).__name__ == 'RateLimited'):
                                raise
                            time.sleep(wait)
                except Exception as exc:
                    row.update(status='transport_error', error_type=type(exc).__name__, ended_at=now())
                    append_jsonl(log_path, row)
                    # Exception messages may contain credentials or provider request text; never log them.
                    continue
                reason = invalid_reason(response)
                row.update(answer=response.get('answer', ''), usage=response.get('usage', {}),
                           model_returned=response.get('model_returned'), stop_reason=response.get('stop_reason'), ended_at=now(),
                           invalid_reason=reason, status='invalid' if reason else 'done')
                append_jsonl(log_path, row)
                break
            if response is not None and not invalid_reason(response):
                break
            generation += 1
        else:
            append_jsonl(log_path, dict(cell, model_requested=cell['model'], model_returned=None,
                         prompt_sha256=sha(prompt), answer=None, usage={}, started_at=now(), ended_at=now(),
                         attempt=attempt, generation=1, status='missing', invalid_reason='regeneration_exhausted'))

def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true', help='Default: do not construct SDK clients')
    mode.add_argument('--execute', action='store_true')
    ap.add_argument('--stimuli', type=Path, default=DEFAULT)
    ap.add_argument('--answers', type=Path, default=ROOT / 'results/raw/answers.jsonl')
    ap.add_argument('--pairs', nargs='+', help='Pair IDs; replicate draw occurs before filtering')
    ap.add_argument('--models', nargs='+', choices=MODELS, default=list(MODELS))
    ap.add_argument('--arms', nargs='+', choices=ARMS, default=list(ARMS))
    ap.add_argument('--langs', nargs='+', choices=LANGS, default=list(LANGS))
    ap.add_argument('--limit', type=int)
    ap.add_argument('--pilot', action='store_true')
    return ap

def main():
    a = parser().parse_args()
    pairs = validate(read_jsonl(a.stimuli))
    if not pairs:
        raise SystemExit('No frozen stimuli; build data/stimuli/pairs.jsonl first.')
    cells = plan(pairs, a.models, a.arms, a.pilot, a.langs)
    if a.pairs:
        cells = [c for c in cells if c['pair_id'] in a.pairs]
    done = terminal_answers(read_jsonl(a.answers))
    cells = [c for c in cells if c['cell_id'] not in done]
    if a.limit is not None:
        if a.limit < 0:
            raise SystemExit('--limit must be nonnegative')
        cells = cells[:a.limit]
    if not a.execute:
        by_pair = {str(p['pair_id']): p for p in pairs}
        costs = {}
        for model in a.models:
            subset = [c for c in cells if c['model'] == model]
            tokens = sum((len(build_prompt(by_pair[c['pair_id']], c['arm'], c['lang'])) + 3) // 4 for c in subset)
            prices = PRICING[model]
            costs[model] = dict(calls=len(subset), estimated_input_tokens=tokens, max_output_tokens=MAX_OUTPUT_TOKENS * len(subset),
                                cost_usd='price unknown' if None in prices.values() else (tokens * prices['input'] + MAX_OUTPUT_TOKENS * len(subset) * prices['output']) / 1e6)
        print(json.dumps({'mode': 'dry-run', 'pending_calls': len(cells), 'replicates': sum(c['replicate'] for c in cells),
                          'cost_estimate': costs, 'estimate_note': 'Input heuristic: characters/4; excludes retries; output budget is a ceiling.', 'plan': cells}, indent=2))
        return
    from .clients import ProviderClient
    run(cells, pairs, a.answers, ProviderClient())

if __name__ == '__main__':
    main()
