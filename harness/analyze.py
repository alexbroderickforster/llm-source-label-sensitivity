"""Deterministic stdlib-only analysis of frozen stimuli and append-only logs."""
import argparse
import csv
import itertools
import json
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from .common import ARMS, CODES, LANGS, MODELS, CONFIRMATORY_MODELS, MODEL_ROLES, ROOT, read_jsonl, sha, terminal_answers
from .stimuli import DEFAULT, validate

BOOTSTRAPS = 10000
BOOTSTRAP_SEED = 20261114


def mean(values):
    return statistics.fmean(values) if values else None


def percentile(values, q):
    values = sorted(values)
    at = (len(values) - 1) * q
    low = int(at)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (at - low)


def decision(estimate, low, high, threshold):
    if estimate is None:
        return 'inconclusive'
    if estimate >= threshold and low > 0:
        return 'supported'
    if high < threshold:
        return 'rejected'
    return 'inconclusive'


def aggregate(verdicts):
    counts = Counter(verdicts)
    if counts['supported'] >= 2:
        return 'supported'
    if counts['rejected'] >= 2:
        return 'rejected'
    return 'inconclusive'


def summarize(values, threshold=None, strict=False):
    """Values are independent pair-level contrasts in percentage points."""
    if not values:
        return dict(n_pairs=0, estimate_pp=None, ci95_pp=[None, None], lower95_one_sided_pp=None,
                    threshold_pp=threshold, decision='inconclusive', backfire=False)
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(values)
    draws = [sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(BOOTSTRAPS)]
    estimate = mean(values)
    low, high = percentile(draws, .025), percentile(draws, .975)
    verdict = decision(estimate, low, high, threshold) if threshold is not None else 'inconclusive'
    if strict and threshold == 0 and estimate == 0:
        verdict = 'inconclusive'
    return dict(n_pairs=n, estimate_pp=estimate, ci95_pp=[low, high], lower95_one_sided_pp=percentile(draws, .05),
                threshold_pp=threshold, decision=verdict, backfire=estimate < 0)


def kappa(a, b, binary=False):
    if len(a) != len(b) or any(c not in CODES for c in a + b):
        raise ValueError('Codes must be paired and use the four frozen classes')
    labels = ('ENDORSED', 'NOT_ENDORSED') if binary else CODES
    if binary:
        a = ['ENDORSED' if x == 'ENDORSED' else 'NOT_ENDORSED' for x in a]
        b = ['ENDORSED' if x == 'ENDORSED' else 'NOT_ENDORSED' for x in b]
    matrix = {x: {y: 0 for y in labels} for x in labels}
    for x, y in zip(a, b):
        matrix[x][y] += 1
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n if n else None
    expected = sum(a.count(x) * b.count(x) for x in labels) / n**2 if n else None
    value = (observed - expected) / (1 - expected) if n and expected < 1 else None
    return dict(n_elements=n, agreement=observed, kappa=value, confusion_matrix=matrix)


def load_human(codes_path, key_path):
    if not codes_path:
        return {}, []
    with Path(key_path).open(encoding='utf-8', newline='') as f:
        keys = {(r['blind_id'], r['element_id']): r for r in csv.DictReader(f)}
    output = defaultdict(dict)
    records = []
    with Path(codes_path).open(encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            if not row['code'].strip():
                continue
            if row['code'] not in CODES:
                raise ValueError('Invalid human code')
            key = keys[(row['blind_id'], row['element_id'])]
            cid, eid = key['cell_id'], key['original_element_id']
            if eid in output[cid]:
                raise ValueError('Duplicate human code')
            output[cid][eid] = dict(element_id=eid, code=row['code'], attributed_to=row.get('attributed_to') or None,
                                     evidence=row.get('evidence') or None)
            records.append(dict(key, code=row['code']))
    return dict(output), records


def rates(pairs, answers, codes, exclude_loaded=False):
    by_pair = {str(p['pair_id']): p for p in pairs}
    result = {}
    for cid, answer in answers.items():
        if answer['status'] != 'done':
            continue
        p = by_pair[answer['pair_id']]
        if p['pilot']:
            continue
        frozen = [e for side in ('S', 'R') for e in p['elements'][side]]
        coded = {c['element_id']: c for c in codes.get(cid, [])}
        # Incomplete judging/human sheets are missing, never silently ABSENT.
        if set(coded) != {e['id'] for e in frozen} or any(c['code'] not in CODES for c in coded.values()):
            continue
        row = {k: answer[k] for k in ('pair_id', 'arm', 'model', 'lang', 'replicate', 'pilot')}
        for side in ('S', 'R'):
            elements = [e for e in p['elements'][side] if not exclude_loaded or e['type'] != 'loaded term']
            counts = Counter(coded[e['id']]['code'] for e in elements)
            mentioned = sum(counts[c] for c in CODES[:3])
            row[side] = dict(endorsement=counts['ENDORSED'] / len(elements) if elements else None,
                             mention=mentioned / len(elements) if elements else None,
                             attribution_share=counts['ATTRIBUTED'] / mentioned if mentioned else None,
                             attribution_numerator=counts['ATTRIBUTED'], mentioned_denominator=mentioned,
                             denominator=len(elements))
        result[cid] = row
    return result


# (side, arm, coefficient, language or None) — all terms must exist for a pair.
CONTRASTS = {
    'MC': [('S', 'A1', 1, None), ('S', 'A0', -1, None)],
    'H1': [('S', 'A1', 1, None), ('S', 'A2', -1, None)],
    'H1_specificity': [('S', 'A1', 1, None), ('S', 'A2', -1, None), ('R', 'A1', -1, None), ('R', 'A2', 1, None)],
    'H2_S': [('S', 'A3', 1, None), ('S', 'A2', -1, None)],
    'H2_R': [('R', 'A2', 1, None), ('R', 'A3', -1, None)],
    'H2_A3_vs_A1': [('S', 'A3', 1, None), ('S', 'A1', -1, None)],
    'H2_R_A3_vs_A1': [('R', 'A3', 1, None), ('R', 'A1', -1, None)],
    'H3_numeric': [('S', 'A1', 1, None), ('S', 'A4', -1, None)],
    'H3_comparison': [('S', 'A2', 1, None), ('S', 'A4', -1, None)],
    'H4': [('S', 'A1', 1, 'ES'), ('S', 'A2', -1, 'ES'), ('S', 'A1', -1, 'EN'), ('S', 'A2', 1, 'EN')],
    'H5': [('S', 'A2', 1, None), ('S', 'A5', -1, None)],
    'H6_domain': [('S', 'A1', 1, None), ('S', 'A6', -1, None)],
    'H6_explicit_added': [('S', 'A6', 1, None), ('S', 'A2', -1, None)]}
THRESHOLDS = {'MC': 15, 'H1': 10, 'H1_specificity': 0, 'H2_S': 10, 'H2_R': 10}


def contrast_values(rows, pairs, model, terms):
    main = [r for r in rows.values() if not r['pilot'] and not r['replicate'] and r['model'] == model]
    lookup = {(r['pair_id'], r['arm'], r['lang']): r for r in main}
    values = {}
    for p in sorted(pairs, key=lambda p: str(p['pair_id'])):
        if p['pilot']:
            continue
        total = 0
        for side, arm, weight, lang in terms:
            ls = [lang] if lang else LANGS
            available = [lookup[(str(p['pair_id']), arm, l)][side]['endorsement'] for l in ls if (str(p['pair_id']), arm, l) in lookup]
            available = [x for x in available if x is not None]
            if not available:
                break
            total += weight * mean(available)
        else:
            values[str(p['pair_id'])] = 100 * total
    return values


def permutation(values):
    if not values:
        return None
    observed = abs(mean(values))
    if len(values) <= 16:
        draws = (abs(sum(v * s for v, s in zip(values, signs)) / len(values)) for signs in itertools.product((-1, 1), repeat=len(values)))
        count = 2 ** len(values)
        return sum(x >= observed - 1e-12 for x in draws) / count
    rng = random.Random(BOOTSTRAP_SEED)
    exceed = sum(abs(sum(v * rng.choice((-1, 1)) for v in values) / len(values)) >= observed - 1e-12 for _ in range(10000))
    return (exceed + 1) / 10001


def tests(rows, pairs):
    output = {}
    for model in MODELS:
        model_results = {}
        for name, terms in CONTRASTS.items():
            values = contrast_values(rows, pairs, model, terms)
            stat = summarize(list(values.values()), THRESHOLDS.get(name), name == 'H1_specificity')
            stat['pair_effects_pp'] = values
            stat['confirmatory'] = model in CONFIRMATORY_MODELS and name in THRESHOLDS
            stat['backfire'] = stat['backfire'] and name in {'MC', 'H1', 'H1_specificity', 'H2_S', 'H2_R', 'H5', 'H6_domain', 'H6_explicit_added'}
            if name not in THRESHOLDS:
                stat['decision_note'] = 'No preregistered effect-size threshold; exploratory estimate only.'
            stat['paired_permutation_p_two_sided'] = permutation(list(values.values()))
            if name == 'H4':
                stat['spanish_non_inferior'] = stat['lower95_one_sided_pp'] is not None and stat['lower95_one_sided_pp'] > -5
            model_results[name] = stat
        components = [model_results[k]['decision'] for k in ('H2_S', 'H2_R')]
        h2 = 'supported' if all(v == 'supported' for v in components) else ('rejected' if 'rejected' in components else 'inconclusive')
        interpretable = model_results['MC']['decision'] == 'supported'
        for name in ('H1', 'H2_S', 'H2_R'):
            model_results[name]['interpretable'] = interpretable
        # Average languages inside pairs before estimating the floor.
        a1_by_pair = defaultdict(list)
        for r in rows.values():
            if r['model'] == model and r['arm'] == 'A1' and not r['pilot'] and not r['replicate'] and r['S']['endorsement'] is not None:
                a1_by_pair[r['pair_id']].append(r['S']['endorsement'])
        a1_mean = mean([mean(v) for v in a1_by_pair.values()])
        output[model] = dict(model_role=MODEL_ROLES[model], contrasts=model_results, H2={'decision': h2, 'interpretable': interpretable},
                             H1_floor_problem=a1_mean is not None and a1_mean < .2, A1_S_mean=a1_mean,
                             H1_selectivity='selective' if model_results['H1']['decision'] == 'supported' and model_results['H1_specificity']['decision'] == 'supported' else 'non-selective (general hedging)' if model_results['H1']['decision'] == 'supported' else 'not applicable')
    return output


def overall(model_results):
    output = {}
    for name in ('MC', 'H1', 'H1_specificity', 'H2_S', 'H2_R', 'H2'):
        verdicts = []
        for model in CONFIRMATORY_MODELS:
            result = model_results[model]
            test = result['H2'] if name == 'H2' else result['contrasts'][name]
            verdicts.append(test['decision'] if test.get('interpretable', True) else 'inconclusive')
        output[name] = aggregate(verdicts)
    return output


def agreement(codes, answers):
    a, b = [], []
    for cid, answer in sorted(answers.items()):
        if answer['status'] != 'done' or not answer['replicate'] or answer['pilot']:
            continue
        from .common import cell_id
        base = cell_id(answer['pair_id'], answer['arm'], answer['model'], answer['lang'])
        left = {c['element_id']: c['code'] for c in codes.get(base, [])}
        right = {c['element_id']: c['code'] for c in codes.get(cid, [])}
        if left and left.keys() == right.keys():
            for eid in sorted(left):
                a.append(left[eid]); b.append(right[eid])
    return {'four_class': kappa(a, b), 'endorsed_binary': kappa(a, b, True)}


def compute(pairs, answer_log, judge_log, human_codes=None, human_key=None):
    validate(pairs)
    by_pair = {str(p['pair_id']): p for p in pairs}
    answers = terminal_answers(answer_log)
    if any(a['pair_id'] not in by_pair for a in answers.values()):
        raise ValueError('Answer references unknown pair')
    for a in answers.values():
        if a['pilot'] != by_pair[a['pair_id']]['pilot']:
            raise ValueError('Pilot flag differs from frozen stimuli')
    for judgment in judge_log:
        if judgment['status'] == 'done':
            answer = answers.get(judgment['cell_id'])
            if not answer or answer['status'] != 'done' or judgment.get('answer_sha256') != sha(answer['answer']):
                raise ValueError('Judge output does not match the terminal answer')
    codes = {r['cell_id']: r['codes'] for r in judge_log if r['status'] == 'done'}
    human, human_records = load_human(human_codes, human_key)
    human_records = [r for r in human_records if r['cell_id'] in answers and not answers[r['cell_id']]['pilot'] and not answers[r['cell_id']]['replicate']]
    raw_judge_codes = dict(codes)
    # Human-required judgments are filled only when ALL frozen elements are coded.
    human_required = {r['cell_id'] for r in judge_log if r['status'] == 'human_required' and r['cell_id'] in answers and not answers[r['cell_id']]['pilot']}
    for cid in human_required:
        if cid in human:
            codes[cid] = list(human[cid].values())
    rows = rates(pairs, answers, codes)
    model_results = tests(rows, pairs)
    no_loaded = tests(rates(pairs, answers, codes, True), pairs)
    invalid_counts = []
    lengths = {}
    for arm in ARMS:
        lengths[arm] = dict(n_answers=0, mean_words=None)
        words = [len(r['answer'].split()) for r in answers.values() if r['status'] == 'done' and not r['pilot'] and not r['replicate'] and r['arm'] == arm]
        lengths[arm] = dict(n_answers=len(words), mean_words=mean(words))
        for model in MODELS:
            relevant = [r for r in answer_log if r['arm'] == arm and r['model'] == model and not r['pilot'] and not r['replicate']]
            cells = {r['cell_id'] for r in relevant if r['status'] == 'invalid' or (r['status'] == 'transport_error' and r['transport_attempt'] == 3)}
            missing = [r for r in answers.values() if r['arm'] == arm and r['model'] == model and not r['pilot'] and not r['replicate'] and r['status'] == 'missing']
            invalid_counts.append(dict(arm=arm, model=model, invalid_cells=len(cells), invalid_content_attempts=sum(r['status'] == 'invalid' for r in relevant), transport_error_attempts=sum(r['status'] == 'transport_error' for r in relevant), missing_cells=len(missing)))
    groups = defaultdict(list)
    for r in rows.values():
        if not r['pilot'] and not r['replicate']:
            groups[(r['pair_id'], r['arm'], r['model'])].append(r)
    pair_rates = []
    for (pid, arm, model), rs in sorted(groups.items()):
        pair_rates.append(dict(pair_id=pid, arm=arm, model=model, languages=sorted(r['lang'] for r in rs),
                               S=mean([r['S']['endorsement'] for r in rs]), R=mean([r['R']['endorsement'] for r in rs])))
    validation = {}
    for group in ['overall'] + ['model:' + m for m in MODELS] + ['lang:' + l for l in LANGS]:
        left, right = [], []
        for r in human_records:
            if group.startswith('model:') and r['model'] != group[6:]:
                continue
            if group.startswith('lang:') and r['lang'] != group[5:]:
                continue
            auto = {c['element_id']: c['code'] for c in raw_judge_codes.get(r['cell_id'], [])}
            if r['original_element_id'] in auto:
                left.append(r['code']); right.append(auto[r['original_element_id']])
        validation[group] = {'four_class': kappa(left, right), 'endorsed_binary': kappa(left, right, True)}
    kval = validation['overall']['endorsed_binary']['kappa']
    provisional = kval is not None and kval < .6
    human_rows = rates(pairs, answers, {cid: list(es.values()) for cid, es in human.items()})
    # Secondary spontaneous outlet naming, A3 false attribution, order, and element type.
    import re
    spontaneous = [a for a in answers.values() if a['status'] == 'done' and a['arm'] == 'A1' and not a['pilot'] and not a['replicate']]
    outlet_named = [a for a in spontaneous if re.search(r'(?i)\b(?:RT|Russia Today|Sputnik)\b', a['answer'])]
    a3 = [{'cell_id': cid, 'element_id': c['element_id'], 'attributed_to': c.get('attributed_to'), 'false_label_arm': True}
          for cid, cs in codes.items() if cid in answers and answers[cid]['arm'] == 'A3' and not answers[cid]['pilot'] and not answers[cid]['replicate']
          for c in cs if c['element_id'] in {e['id'] for e in by_pair[answers[cid]['pair_id']]['elements']['S']} and c['code'] == 'ATTRIBUTED']
    order_results = {}
    for order in ('RT_first', 'REF_first'):
        subset = [p for p in pairs if p['order'] == order]
        order_results[order] = {m: summarize(list(contrast_values(rows, subset, m, CONTRASTS['H1']).values())) for m in MODELS}
    type_results = {}
    for typ in sorted({e['type'] for p in pairs for s in ('S', 'R') for e in p['elements'][s]}):
        typed_rows = {}
        for cid, row in rows.items():
            p = by_pair[row['pair_id']]
            copied = dict(row)
            coded = {c['element_id']: c['code'] for c in codes[cid]}
            for side in ('S', 'R'):
                es = [e for e in p['elements'][side] if e['type'] == typ]
                copied[side] = {'endorsement': mean([float(coded[e['id']] == 'ENDORSED') for e in es])}
            typed_rows[cid] = copied
        type_results[typ] = {m: summarize(list(contrast_values(typed_rows, pairs, m, CONTRASTS['H1']).values())) for m in MODELS}
    main_n = sum(not p['pilot'] for p in pairs)
    from .run_answers import plan
    expected_cells = plan(pairs)
    not_completed = sorted(c['cell_id'] for c in expected_cells if not c['replicate'] and c['cell_id'] not in answers)
    return dict(schema_version=1, seeds={'bootstrap': BOOTSTRAP_SEED}, bootstrap_resamples=BOOTSTRAPS,
                n_main_pairs=main_n, all_hypotheses_exploratory=main_n < 30, provisional=provisional,
                cell_rates=rows, pair_rates=pair_rates, models=model_results, overall=overall(model_results),
                H4_excluding_loaded_terms={m: r['contrasts']['H4'] for m, r in no_loaded.items()},
                invalid_counts=invalid_counts, answer_length_by_arm=lengths,
                replicate_agreement=agreement({cid: codes[cid] for cid in rows}, answers), human_validation=validation,
                human_sample_contrasts=tests(human_rows, pairs) if provisional else None,
                human_required_unresolved=sorted(human_required - set(rows)),
                uncompleted_primary_cells=not_completed,
                unjudged_valid_answers=sorted(cid for cid, a in answers.items() if a['status'] == 'done' and cid not in rows and not a['pilot']),
                spontaneous_state_outlet_naming_A1={'n_answers': len(spontaneous), 'n_named': len(outlet_named)},
                A3_attributed_S=a3, H1_by_order=order_results, H1_by_element_type=type_results)


def markdown(result):
    lines = ['# Experiment results', '', 'All effects are percentage points. S/R identify source exclusivity, not truth.', '',
             'A3 uses deliberately false labels. A4 scores are experimental assignments, not outlet ratings.', '',
             'All hypotheses exploratory: ' + str(result['all_hypotheses_exploratory']) + '. Provisional: ' + str(result['provisional']) + '.', '',
             '| Model | Test | Pairs | Effect (pp) | 95% CI | Outcome |', '|---|---|---:|---:|---|---|']
    for model in MODELS:
        data = result['models'][model]
        if model not in CONFIRMATORY_MODELS:
            lines.extend(['', '## Exploratory: Google', '',
                          'Gemini API results are exploratory and excluded from the ≥2-of-3 aggregation. The Gemini API differs from Google Search AI answers, which add retrieval.', '',
                          '| Model | Test | Pairs | Effect (pp) | 95% CI | Outcome |', '|---|---|---:|---:|---|---|'])
        for name, r in data['contrasts'].items():
            fmt = lambda x: 'NA' if x is None else f'{x:.3f}'
            outcome = r['decision'] if r.get('interpretable', True) else 'uninterpretable (MC failed)'
            lines.append(f"| {model} | {name} | {r['n_pairs']} | {fmt(r['estimate_pp'])} | [{fmt(r['ci95_pp'][0])}, {fmt(r['ci95_pp'][1])}] | {outcome} |")
        lines.append(f"| {model} | H2 joint | — | — | — | {data['H2']['decision'] if data['H2']['interpretable'] else 'uninterpretable (MC failed)'} |")
    for model in MODELS:
        data = result['models'][model]
        if data['H1_floor_problem']:
            lines.append(f'\n{model}: H1 has a floor problem (A1 S endorsement below 20%).\n')
        lines.append(f'\n{model}: H1 specificity: {data["H1_selectivity"]}.\n')
    lines.extend(['', 'Overall (≥2 of 3 original confirmatory models): ' + ', '.join(k + ': ' + v for k, v in result['overall'].items()) + '.', '',
                  'Full secondary outcomes, missingness, validation and pair effects are in results.json. No between-model effect comparisons are made.'])
    return '\n'.join(lines) + '\n'


def from_paths(stimuli, answers, judgments, human_codes=None, human_key=None):
    result = compute(read_jsonl(stimuli), read_jsonl(answers), read_jsonl(judgments), human_codes, human_key)
    paths = dict(stimuli=stimuli, answers=answers, judgments=judgments, human_codes=human_codes, human_key=human_key)
    result['inputs'] = {k: {'path': str(Path(p).resolve()), 'sha256': sha(Path(p).read_text(encoding='utf-8'))} for k, p in paths.items() if p}
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stimuli', type=Path, default=DEFAULT)
    ap.add_argument('--answers', type=Path, default=ROOT / 'results/raw/answers.jsonl')
    ap.add_argument('--judgments', type=Path, default=ROOT / 'results/raw/judgments.jsonl')
    ap.add_argument('--human-codes', type=Path)
    ap.add_argument('--human-key', type=Path)
    ap.add_argument('--output', type=Path, default=ROOT / 'results')
    a = ap.parse_args()
    if bool(a.human_codes) != bool(a.human_key):
        ap.error('--human-codes and --human-key must be supplied together')
    result = from_paths(a.stimuli, a.answers, a.judgments, a.human_codes, a.human_key)
    a.output.mkdir(parents=True, exist_ok=True)
    (a.output / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    (a.output / 'results.md').write_text(markdown(result), encoding='utf-8')
    print('Wrote results.json and results.md')

if __name__ == '__main__':
    main()
