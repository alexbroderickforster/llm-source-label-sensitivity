"""Recompute every numeric and nonnumeric result from the recorded inputs."""
import argparse
import json
from pathlib import Path
from harness.analyze import from_paths, markdown
from harness.common import ROOT, sha


def verify(path):
    path = Path(path)
    saved = json.loads(path.read_text(encoding='utf-8'))
    inputs = saved['inputs']
    for meta in inputs.values():
        if sha(Path(meta['path']).read_text(encoding='utf-8')) != meta['sha256']:
            raise AssertionError('Input changed: ' + meta['path'])
    fresh = from_paths(**{k: v['path'] for k, v in inputs.items()})
    if fresh != saved:
        raise AssertionError('Recomputed results differ from results.json')
    md = path.with_suffix('.md')
    if not md.exists() or md.read_text(encoding='utf-8') != markdown(fresh):
        raise AssertionError('Markdown table differs from recomputed report')
    return True

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('results', nargs='?', type=Path, default=ROOT / 'results/results.json')
    a = ap.parse_args()
    verify(a.results)
    print('Verified every result and the Markdown report against raw inputs.')
