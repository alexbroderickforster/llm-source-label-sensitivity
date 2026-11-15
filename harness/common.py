"""Shared serialization and paths. Never loads dotenv files."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIRMATORY_MODELS = ('claude-sonnet-5-5', 'gpt-5.4-mini-2026-03-17', 'qwen/qwen3.8-27b')
EXPLORATORY_MODELS = ('gemini-3.8-flash',)
MODELS = CONFIRMATORY_MODELS + EXPLORATORY_MODELS
MODEL_ROLES = {m: 'confirmatory' if m in CONFIRMATORY_MODELS else 'exploratory' for m in MODELS}
ARMS = tuple('A' + str(i) for i in range(7))
LANGS = ('ES', 'EN')
CODES = ('ENDORSED', 'ATTRIBUTED', 'CONTESTED', 'ABSENT')

def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]

def append_jsonl(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
        f.flush()
        import os
        os.fsync(f.fileno())

def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def now():
    return datetime.now(timezone.utc).isoformat()

def cell_id(pair_id, arm, model, lang, replicate=0):
    return json.dumps([str(pair_id), arm, model, lang, replicate], separators=(',', ':'))

def terminal_answers(rows):
    return {r['cell_id']: r for r in rows if r['status'] in ('done', 'missing')}
