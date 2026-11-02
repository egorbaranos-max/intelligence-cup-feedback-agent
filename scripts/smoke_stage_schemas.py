"""Explicit local GPU checks for all stage schemas; synthetic structural probes only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

p = argparse.ArgumentParser()
p.add_argument('--repo', default=str(Path(__file__).resolve().parents[1]))
p.add_argument('--model-manifest', required=True)
p.add_argument('--output', required=True)
a = p.parse_args()
repo, output = Path(a.repo).resolve(), Path(a.output)
if output.exists():
    raise FileExistsError(f'Refusing to overwrite evidence: {output}')
output.parent.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(repo))
from agent.backend import LocalMLX
from agent.pipeline import validate_extraction, validate_matching, extraction_messages, matching_messages
from agent.verifier_v2 import validate_verification, verification_messages
from agent.prompts import VERIFICATION_POLICY

source = {'id': 'stage-probe', 'product_id': 'syntax-probe', 'speaker': 'user',
          'text': 'Добавьте изменение размера шрифта. Ещё нужна настройка межстрочного интервала. Сегодня приложение закрывается при запуске.',
          'product_context': 'Размер шрифта и межстрочный интервал пока фиксированы; настроек нет. Запуск приложения — существующая возможность.'}
expected_extraction = {'status': 'ok', 'intents': [
    {'kind': 'feature_request', 'origin': 'user_explicit', 'statement': 'Настройка размера шрифта',
     'evidence_refs': [{'span_id': 'span_0001'}], 'uncertainties': []},
]}
validated = validate_extraction(json.dumps(expected_extraction), source)
assert validated.ok, validated.errors
intent = validated.value['intents'][0]
candidates = [{'id': 'probe-one', 'product_id': 'syntax-probe', 'statement': 'Выбор размера шрифта в приложении'},
              {'id': 'probe-two', 'product_id': 'syntax-probe', 'statement': 'Настройка межстрочного интервала'}]
verification_prompt = verification_messages(source, intent)
verification_prompt[0]['content'] = VERIFICATION_POLICY + '\n' + verification_prompt[0]['content']
probes = [
    ('extraction', extraction_messages(source), lambda raw: validate_extraction(raw, source), 700),
    ('verification', verification_prompt, lambda raw: validate_verification(raw, source, intent), 300),
    ('matching', matching_messages(intent, candidates), lambda raw: validate_matching(raw, candidates), 300),
]
backend = LocalMLX(a.model_manifest)
report = {'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'running',
          'kind': 'named stage JSON schema integration; no accuracy evaluation',
          'model': backend.provenance, 'calls': [],
          'limitations': ['synthetic structural probes with actual stage prompts', 'no semantic accuracy claim', 'no holdout or human labels',
                          'verification and matching use a declared synthetic fixture intent, not prior model output'],
          'smoke_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'code_sha256': {name: hashlib.sha256((repo / name).read_bytes()).hexdigest() for name in
                          ['agent/backend.py', 'agent/structured.py', 'agent/response_schemas.py', 'agent/prompts.py',
                           'agent/pipeline.py', 'agent/verifier_v2.py']}}

def save():
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

save()
try:
    for stage, messages, validator, limit in probes:
        raw, stats = backend.generate(messages, max_tokens=limit, schema_name=stage)
        result = validator(raw)
        call = {'stage': stage, 'response_schema': stage, 'messages': messages,
                'raw_response': raw, 'stats': stats, 'mechanical_validation': result.ok,
                'validation_errors': result.errors}
        report['calls'].append(call); save()
        assert result.ok, result.errors
        assert stats['response_schema'] == stage
        assert stats['structured_json']['schema_name'] == stage
        assert stats['structured_json']['schema_sha256'] == backend.provenance['decoding']['structured_json']['schemas'][stage]['schema_sha256']
        if stage == 'extraction':
            call['observed_intent_count'] = len(result.value['intents'])
    report['status'] = 'passed'; save()
except Exception as exc:
    report.update(status='failed', error_type=type(exc).__name__, error=str(exc))
    if hasattr(exc, 'raw_response'):
        report['failed_raw_response'] = exc.raw_response
        report['failed_stats'] = exc.stats
    save()
    raise
print(json.dumps({'status': report['status'], 'calls': len(report['calls']), 'output': str(output)}))
