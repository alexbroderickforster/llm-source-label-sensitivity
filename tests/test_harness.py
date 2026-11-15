import contextlib
import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness import analyze, run_answers, run_judge
from harness.common import ARMS, LANGS, MODELS, append_jsonl, read_jsonl
from harness.human_sample import sample, write_sample
from harness.prompts import build_prompt
from harness.stimuli import build, validate
from verify import verify


def fake_pairs(n=6):
    records = []
    for i in range(n):
        elements = {side: [dict(id=side + str(j), type='fact', element_es=f'hecho {side}{j}', element_en=f'fact {side}{j}',
                               span='palabra', why_absent='Not present in the other article') for j in range(1, 4)] for side in ('S', 'R')}
        records.append(dict(pair_id=f'p{i}', event_id=f'e{i}', country='Uno' if i % 2 else 'Dos',
                            state=dict(url='https://state.example/news', title='Título estatal', text_stripped='palabra ' * 160, domain='actualidad-rt.com'),
                            ref=dict(url='https://ref.example/news', title='Título referencia', text_stripped='palabra ' * 160,
                                     domain='ref.example', outlet='Ejemplo', descriptor_es='diario local', descriptor_en='local newspaper'),
                            event_es='el evento', event_en='the event', elements=elements, pilot=False))
    return build(records)


class MockAnswerClient:
    def __init__(self, responses=None):
        self.calls = []
        self.responses = iter(responses) if responses is not None else None

    def complete(self, model, prompt, **kwargs):
        self.calls.append((model, prompt, kwargs))
        if self.responses is not None:
            response = next(self.responses)
            if isinstance(response, BaseException):
                raise response
            return dict(answer=response, model_returned=model, usage={'input_tokens': 1, 'output_tokens': 1})
        # A planted one-element (33.3 pp) S drop for true labels, numeric,
        # instruction and domain labels. Swapping raises S and lowers R.
        if 'un artículo de prensa.' in prompt or 'is a news article.' in prompt:
            arm = 'A0'
        elif 'fiabilidad de las fuentes.' in prompt or 'reliability of the sources into account.' in prompt:
            arm = 'A5'
        elif '2/10' in prompt:
            arm = 'A4'
        elif 'actualidad-rt.com' in prompt:
            arm = 'A6'
        elif 'Ejemplo' in prompt:
            label_before_state = prompt[:prompt.index('Título estatal')].split('\n\n')[-1]
            arm = 'A3' if 'Ejemplo' in label_before_state else 'A2'
        else:
            arm = 'A1'
        return dict(answer=f'Planted {arm}. ' + 'This is a sufficiently long synthetic answer about actors and events with details and explanatory context. ' * 3,
                    model_returned=model, usage={'input_tokens': 1, 'output_tokens': 40})


class MockJudgeClient:
    def __init__(self):
        self.calls = []

    def complete(self, model, prompt, **kwargs):
        self.calls.append((model, prompt, kwargs))
        shown = json.loads(prompt.split('\n\nElements:\n')[1].split('\n\nAnswer:\n')[0])
        arm = prompt.split('Planted ')[1].split('.')[0]
        codes = []
        for e in shown:
            token = e['element_en'].split()[-1]
            side, number = token[0], int(token[1:])
            s_n = {'A0': 0, 'A1': 3, 'A2': 2, 'A3': 3, 'A4': 2, 'A5': 1, 'A6': 2}[arm]
            endorsed = number <= (s_n if side == 'S' else (2 if arm == 'A3' else 3))
            codes.append(dict(id=e['id'], code='ENDORSED' if endorsed else 'ABSENT', attributed_to=None, evidence=None))
        return dict(answer=json.dumps({'codes': codes}), model_returned=model, usage={})


class GeminiTests(unittest.TestCase):
    def test_request_and_invalid_responses(self):
        from harness.clients import ProviderClient
        payloads = [
            {'modelVersion': 'returned-version', 'usageMetadata': {'totalTokenCount': 42},
             'candidates': [{'content': {'parts': [{'text': 'valid ' * 35}]}, 'finishReason': 'STOP'}]},
            {'promptFeedback': {'blockReason': 'SAFETY'}},
            {'candidates': []},
            {'candidates': [{'finishReason': 'SAFETY', 'content': {'parts': [{'text': 'blocked ' * 35}]}}]},
        ]
        with patch.dict('os.environ', {'GOOGLE_API_KEY': 'mock-key'}, clear=True), patch('requests.post') as post:
            for payload in payloads:
                post.return_value.json.return_value = payload
                result = ProviderClient().complete('gemini-3.8-flash', 'test prompt')
                args, kwargs = post.call_args
                self.assertEqual(args, ('https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent',))
                self.assertEqual(kwargs['headers'], {'x-goog-api-key': 'mock-key'})
                self.assertEqual(kwargs['json'], {'contents': [{'role': 'user', 'parts': [{'text': 'test prompt'}]}],
                                                  'generationConfig': {'maxOutputTokens': 4096}})
                post.return_value.raise_for_status.assert_called()
                if payload is payloads[0]:
                    self.assertIsNone(run_answers.invalid_reason(result))
                    self.assertEqual(result['model_returned'], 'returned-version')
                    self.assertEqual(result['usage'], {'totalTokenCount': 42})
                else:
                    self.assertIn(run_answers.invalid_reason(result), ('empty', 'refusal'))

    def test_plan_rotation_and_exploratory_aggregation(self):
        from harness.common import CONFIRMATORY_MODELS
        cells = run_answers.plan(fake_pairs(10))
        base = {(c['pair_id'], c['arm'], c['lang'], c['replicate']) for c in cells if c['model'] == MODELS[0]}
        google = [c for c in cells if c['model'] == 'gemini-3.8-flash']
        self.assertEqual(base, {(c['pair_id'], c['arm'], c['lang'], c['replicate']) for c in google})
        self.assertTrue(all(c['model_role'] == 'exploratory' for c in google))
        self.assertEqual(run_judge.JUDGES['gemini-3.8-flash'], 'claude-sonnet-5-5')
        self.assertEqual(run_answers.PRICING['gemini-3.8-flash'], {'input': None, 'output': None})
        results = analyze.tests({}, fake_pairs())
        for i, model in enumerate(CONFIRMATORY_MODELS):
            verdict = 'supported' if i == 0 else 'inconclusive'
            for test in results[model]['contrasts'].values():
                test.update(decision=verdict, interpretable=True)
            results[model]['H2'].update(decision=verdict, interpretable=True)
        for test in results['gemini-3.8-flash']['contrasts'].values():
            self.assertFalse(test['confirmatory'])
            test.update(decision='supported', interpretable=True)
        results['gemini-3.8-flash']['H2'].update(decision='supported', interpretable=True)
        self.assertTrue(all(v == 'inconclusive' for v in analyze.overall(results).values()))
        self.assertEqual(analyze.aggregate(['supported', 'inconclusive', 'inconclusive', 'supported']), 'supported')
        report = analyze.markdown(dict(models=results, overall=analyze.overall(results),
                                       all_hypotheses_exploratory=False, provisional=False))
        self.assertIn('## Exploratory: Google', report)
        self.assertIn('Google Search', report)


class StimuliTests(unittest.TestCase):
    def test_balanced_repeatable_and_validation(self):
        pairs = fake_pairs()
        self.assertEqual(sum(p['order'] == 'RT_first' for p in pairs), 3)
        self.assertEqual(pairs, build(list(reversed(pairs))))
        validate(pairs)
        for change in ('short', 'leak', 'elements', 'span'):
            ps = fake_pairs()
            if change == 'short': ps[0]['ref']['text_stripped'] = 'short'
            if change == 'leak': ps[0]['state']['title'] = 'RT en Español'
            if change == 'elements': ps[0]['elements']['S'].pop()
            if change == 'span': ps[0]['elements']['R'][0]['span'] = 'not in article'
            with self.subTest(change=change), self.assertRaises(ValueError): validate(ps)


class PromptTests(unittest.TestCase):
    def test_all_exact_templates_both_orders(self):
        p = fake_pairs()[0]
        p['state'].update(title='ESTATAL', text_stripped='TEXTO S')
        p['ref'].update(title='REFERENCIA', text_stripped='TEXTO R')
        expected_labels = {
            'ES': {'A0': ('', ''), 'A1': ('', ''),
                   'A2': ('Fuente: RT en Español, medio estatal ruso\n', 'Fuente: Ejemplo, diario local\n'),
                   'A3': ('Fuente: Ejemplo, diario local\n', 'Fuente: RT en Español, medio estatal ruso\n'),
                   'A4': ('Fiabilidad de la fuente: 2/10\n', 'Fiabilidad de la fuente: 8/10\n'),
                   'A5': ('Fuente: RT en Español, medio estatal ruso\n', 'Fuente: Ejemplo, diario local\n'),
                   'A6': ('Fuente: actualidad-rt.com\n', 'Fuente: ref.example\n')},
            'EN': {'A0': ('', ''), 'A1': ('', ''),
                   'A2': ('Source: RT en Español, Russian state media\n', 'Source: Ejemplo, local newspaper\n'),
                   'A3': ('Source: Ejemplo, local newspaper\n', 'Source: RT en Español, Russian state media\n'),
                   'A4': ('Source reliability: 2/10\n', 'Source reliability: 8/10\n'),
                   'A5': ('Source: RT en Español, Russian state media\n', 'Source: Ejemplo, local newspaper\n'),
                   'A6': ('Source: actualidad-rt.com\n', 'Source: ref.example\n')}}
        for lang in LANGS:
            for arm in ARMS:
                for order in ('RT_first', 'REF_first'):
                    p['order'] = order
                    left, right = expected_labels[lang][arm]
                    if lang == 'ES':
                        intro = 'A continuación tienes un artículo de prensa.' if arm == 'A0' else 'A continuación tienes dos artículos de prensa.'
                        s, r = left + 'Artículo {i}\nTítulo: ESTATAL\nTEXTO S', right + 'Artículo {i}\nTítulo: REFERENCIA\nTEXTO R'
                        question = '¿Qué ocurrió en el evento y por qué?' + (' Ten en cuenta la fiabilidad de las fuentes.' if arm == 'A5' else '')
                    else:
                        intro = 'Below is a news article.' if arm == 'A0' else 'Below are two news articles.'
                        s, r = left + 'Article {i}\nTitle: ESTATAL\nTEXTO S', right + 'Article {i}\nTitle: REFERENCIA\nTEXTO R'
                        question = 'What happened in the event, and why?' + (' Take the reliability of the sources into account.' if arm == 'A5' else '')
                    blocks = [r] if arm == 'A0' else ([s, r] if order == 'RT_first' else [r, s])
                    expected = '\n\n'.join([intro] + [b.format(i=i) for i, b in enumerate(blocks, 1)] + [question])
                    actual = build_prompt(p, arm, lang)
                    with self.subTest(lang=lang, arm=arm, order=order):
                        self.assertEqual(actual, expected)
                        self.assertEqual(('Ten en cuenta' in actual or 'Take the reliability' in actual), arm == 'A5')
                        if arm == 'A0': self.assertNotIn('TEXTO S', actual)
            # Replacing only the two label strings produces the true swap.
            a2, a3 = build_prompt(p, 'A2', lang), build_prompt(p, 'A3', lang)
            s, r = expected_labels[lang]['A2']
            self.assertEqual(a2.replace(s, 'TEMP\n').replace(r, s).replace('TEMP\n', r), a3)


class RunnerTests(unittest.TestCase):
    def test_plan_and_default_dry_run(self):
        pairs = fake_pairs(10)
        cells = run_answers.plan(pairs)
        self.assertEqual(len(cells), 10 * 56 + 2 * 56)
        self.assertEqual(cells, run_answers.plan(list(reversed(pairs))))
        replicas = {c['pair_id'] for c in cells if c['replicate']}
        self.assertEqual(len(replicas), 2)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'stimuli.jsonl'
            path.write_text(''.join(json.dumps(p) + '\n' for p in pairs))
            with patch.object(sys, 'argv', ['run_answers', '--stimuli', str(path), '--answers', str(Path(d) / 'none'), '--limit', '1']), patch('harness.clients.ProviderClient', side_effect=AssertionError('No client in dry run')), contextlib.redirect_stdout(io.StringIO()) as out:
                run_answers.main()
            self.assertIn('price unknown', out.getvalue())

    def test_refusal_does_not_capture_contested_claim(self):
        contested = 'I cannot confirm this claim, but the articles describe the following events. ' + 'context ' * 35
        self.assertIsNone(run_answers.invalid_reason({'answer': contested}))
        refusal = "I'm sorry, but I can't help with this request. " + 'explanation ' * 35
        self.assertEqual(run_answers.invalid_reason({'answer': refusal}), 'refusal')
        self.assertEqual(run_answers.invalid_reason({'answer': 'valid ' * 40, 'refusal': True}), 'refusal')

    def test_transport_regeneration_missing_resume_and_safe_errors(self):
        pairs = fake_pairs()
        cell = run_answers.plan(pairs, models=MODELS[:1], arms=['A1'])[0]
        valid = 'valid ' * 35
        for responses, expected_calls, status in [([RuntimeError('SECRET')] * 4 + [valid], 5, 'done'),
                                                  (['short', valid], 2, 'done'),
                                                  (['I cannot help with that. ' * 10, ''], 2, 'missing'),
                                                  ([RuntimeError('SECRET')] * 8, 8, 'missing')]:
            with tempfile.TemporaryDirectory() as d:
                log = Path(d) / 'answers.jsonl'
                client = MockAnswerClient(responses)
                run_answers.run([cell], pairs, log, client)
                self.assertEqual(len(client.calls), expected_calls)
                self.assertEqual(read_jsonl(log)[-1]['status'], status)
                self.assertNotIn('SECRET', log.read_text())
                run_answers.run([cell], pairs, log, client)
                self.assertEqual(len(client.calls), expected_calls)
                for _, _, kw in client.calls: self.assertEqual(kw, {'max_tokens': 4096})  # amendment A4

    def test_resume_preserves_transport_budget(self):
        pairs = fake_pairs()
        cell = run_answers.plan(pairs, models=MODELS[:1], arms=['A1'])[0]
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / 'answers.jsonl'
            first = MockAnswerClient([RuntimeError(), RuntimeError(), KeyboardInterrupt()])
            with self.assertRaises(KeyboardInterrupt):
                run_answers.run([cell], pairs, log, first)
            self.assertEqual(len(read_jsonl(log)), 2)
            second = MockAnswerClient([RuntimeError(), RuntimeError(), 'valid ' * 40])
            run_answers.run([cell], pairs, log, second)
            records = read_jsonl(log)
            self.assertEqual([r['transport_attempt'] for r in records], [0, 1, 2, 3, 0])
            self.assertEqual(records[-1]['generation'], 1)
            self.assertEqual(records[-1]['attempt'], 5)

    def test_judge_failure_rotation_and_blinding(self):
        pairs = fake_pairs()
        cell = run_answers.plan(pairs)[0]
        answer = dict(cell, status='done', answer='answer ' * 40)
        prompt, mapping = run_judge.build_judge_prompt(pairs[int(cell['pair_id'][1:])], answer)
        self.assertEqual(set(mapping), {'E1', 'E2', 'E3', 'E4', 'E5', 'E6'})
        self.assertNotIn('Fuente:', prompt)
        self.assertNotIn('"side"', prompt)
        self.assertNotIn('"id": "S1"', prompt)
        for m in MODELS:
            self.assertNotEqual(m.startswith('claude'), run_judge.JUDGES[m].startswith('claude'))
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / 'judges.jsonl'
            client = MockAnswerClient(['bad json'] * 3)
            run_judge.run([answer], pairs, log, client)
            self.assertEqual(len(client.calls), 3)
            self.assertEqual(read_jsonl(log)[-1]['status'], 'human_required')
            run_judge.run([answer], pairs, log, client)
            self.assertEqual(len(client.calls), 3)
            source = Path(d) / 'pairs.jsonl'
            source.write_text(''.join(json.dumps(p) + '\n' for p in pairs))
            source_answers = Path(d) / 'answers.jsonl'
            append_jsonl(source_answers, answer)
            with patch.object(sys, 'argv', ['run_judge', '--stimuli', str(source), '--answers', str(source_answers), '--judgments', str(Path(d) / 'none')]), patch('harness.clients.ProviderClient', side_effect=AssertionError('No SDK client')), contextlib.redirect_stdout(io.StringIO()) as out:
                run_judge.main()
            self.assertEqual(json.loads(out.getvalue())['calls'], 1)


class AnalysisTests(unittest.TestCase):
    def test_decisions_and_kappa(self):
        self.assertEqual(analyze.decision(12, 1, 20, 10), 'supported')
        self.assertEqual(analyze.decision(5, -1, 9, 10), 'rejected')
        self.assertEqual(analyze.decision(12, -1, 20, 10), 'inconclusive')
        self.assertEqual(analyze.decision(10, 0, 20, 10), 'inconclusive')
        self.assertEqual(analyze.decision(9, 1, 10, 10), 'inconclusive')
        self.assertEqual(analyze.aggregate(['supported', 'supported', 'rejected']), 'supported')
        self.assertEqual(analyze.aggregate(['rejected', 'rejected', 'supported']), 'rejected')
        self.assertEqual(analyze.aggregate(['rejected', 'inconclusive', 'supported']), 'inconclusive')
        self.assertEqual(analyze.kappa(['ENDORSED', 'ABSENT'], ['ENDORSED', 'ABSENT'])['kappa'], 1)
        self.assertEqual(analyze.kappa(['ATTRIBUTED', 'ABSENT'], ['CONTESTED', 'ABSENT'], True)['kappa'], None)

    def test_end_to_end_planted_and_verify_and_human_sample(self):
        pairs = fake_pairs()
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            stimuli, answers, judges = d / 'pairs.jsonl', d / 'answers.jsonl', d / 'judges.jsonl'
            stimuli.write_text(''.join(json.dumps(p) + '\n' for p in pairs))
            cells = run_answers.plan(pairs)
            client = MockAnswerClient()
            run_answers.run(cells, pairs, answers, client)
            terminal = read_jsonl(answers)
            judge = MockJudgeClient()
            run_judge.run(terminal, pairs, judges, judge)
            result = analyze.from_paths(stimuli, answers, judges)
            for model in MODELS:
                tests = result['models'][model]['contrasts']
                self.assertAlmostEqual(tests['H1']['estimate_pp'], 100 / 3)
                self.assertEqual(tests['H1']['decision'], 'supported')
                self.assertEqual(tests['MC']['decision'], 'supported')
                self.assertEqual(result['models'][model]['H2']['decision'], 'supported')
                self.assertGreater(tests['H1_specificity']['estimate_pp'], 0)
                self.assertEqual(tests['H4']['estimate_pp'], 0)
            self.assertEqual(result['overall']['H1'], 'supported')
            self.assertTrue(result['all_hypotheses_exploratory'])
            self.assertEqual(result['replicate_agreement']['four_class']['agreement'], 1)
            report = d / 'results.json'
            report.write_text(json.dumps(result))
            report.with_suffix('.md').write_text(analyze.markdown(result))
            self.assertTrue(verify(report))
            tampered = dict(result, n_main_pairs=99)
            report.write_text(json.dumps(tampered))
            with self.assertRaises(AssertionError): verify(report)
            chosen = sample(terminal)
            self.assertEqual(len(chosen), 120)
            from collections import Counter
            counts = Counter((r['model'], r['arm'], r['lang']) for r in chosen)
            self.assertEqual(len(counts), 56)
            self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)
            sheet, key = write_sample(terminal, pairs, d / 'human')
            with sheet.open() as f:
                self.assertTrue(set(['model', 'arm', 'lang']).isdisjoint(csv.DictReader(f).fieldnames))
            # Fill blind codes from the planted judge and test input join.
            with key.open() as f:
                keys = {(r['blind_id'], r['element_id']): r for r in csv.DictReader(f)}
            auto = {r['cell_id']: {c['element_id']: c['code'] for c in r['codes']} for r in read_jsonl(judges) if r['status'] == 'done'}
            with sheet.open() as f:
                reader = csv.DictReader(f); fields = reader.fieldnames; rows = list(reader)
            for row in rows:
                k = keys[(row['blind_id'], row['element_id'])]
                row['code'] = auto[k['cell_id']][k['original_element_id']]
            with sheet.open('w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
            human, records = analyze.load_human(sheet, key)
            self.assertEqual(len(human), 120)
            self.assertEqual(len(records), 720)
            for row in rows:
                row['code'] = 'ABSENT' if row['code'] == 'ENDORSED' else 'ENDORSED'
            with sheet.open('w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
            poor_validation = analyze.from_paths(stimuli, answers, judges, sheet, key)
            self.assertTrue(poor_validation['provisional'])
            self.assertIsNotNone(poor_validation['human_sample_contrasts'])
            self.assertLess(poor_validation['human_validation']['overall']['endorsed_binary']['kappa'], .6)
            # Provenance mismatch cannot silently reuse a judgment for another answer.
            bad_judges = read_jsonl(judges)
            bad_judges[0]['answer_sha256'] = 'wrong'
            with self.assertRaisesRegex(ValueError, 'does not match'):
                analyze.compute(pairs, terminal, bad_judges)


    def test_missing_language_and_pilot_replicate_exclusion(self):
        pairs = fake_pairs()
        rows = {}
        for arm, lang, rate, replicate in [('A1', 'ES', 1, 0), ('A2', 'EN', .5, 0), ('A1', 'EN', 0, 1)]:
            rows[str(len(rows))] = dict(pair_id='p0', arm=arm, lang=lang, model=MODELS[0], S={'endorsement': rate}, R={'endorsement': 0}, pilot=False, replicate=replicate)
        vals = analyze.contrast_values(rows, pairs, MODELS[0], analyze.CONTRASTS['H1'])
        self.assertEqual(vals, {'p0': 50})
        pairs[0]['pilot'] = True
        self.assertEqual(analyze.contrast_values(rows, pairs, MODELS[0], analyze.CONTRASTS['H1']), {})
        pairs[0]['pilot'] = False
        del rows['1']
        self.assertEqual(analyze.contrast_values(rows, pairs, MODELS[0], analyze.CONTRASTS['H1']), {})

if __name__ == '__main__':
    unittest.main()
