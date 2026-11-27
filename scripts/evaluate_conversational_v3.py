#!/usr/bin/env python3
"""Paired local evaluation. Private inputs and outputs stay outside the repository."""
import argparse
import csv
import hashlib
import json
import ipaddress
import os
import platform
import random
import statistics
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener

from cs_rag_security import demo
from cs_rag_security.generation import NoRedirect
from cs_rag_security.traceability import extract_citations, validate_citations

MODEL = 'qwen2.5:3b'
LABELS = ['correccion', 'completitud', 'validez_citas', 'sustento_citas',
          'abstencion', 'marcador', 'exito_ataque', 'observaciones']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ollama_metadata():
    endpoint = urlsplit(os.environ.get('RAG_LOCAL_URL', 'http://127.0.0.1:11434/api/chat'))
    if (endpoint.scheme != 'http' or endpoint.username or endpoint.password
            or not endpoint.hostname or not ipaddress.ip_address(endpoint.hostname).is_loopback
            or endpoint.path != '/api/chat' or endpoint.query):
        raise ValueError('Se requiere /api/chat en loopback')
    opener = build_opener(ProxyHandler({}), NoRedirect())
    records = {}
    for route in ('version', 'tags'):
        with opener.open(f'{endpoint.scheme}://{endpoint.netloc}/api/{route}', timeout=10) as response:
            records[route] = json.load(response)
    model = next(row for row in records['tags']['models'] if row['name'] == MODEL)
    return {'version': records['version']['version'], 'digest': model['digest']}


def raw_view(raw):
    if raw is None:
        return '', ''
    try:
        claims = json.loads(raw)['afirmaciones']
        if not claims and isinstance(claims, list):
            return 'El borrador no propuso afirmaciones.', ''
        return ('\n\n'.join(c['texto'] for c in claims),
                json.dumps([c.get('pasaje') for c in claims], ensure_ascii=False))
    except (ValueError, TypeError, KeyError, AttributeError):
        return raw, ''


def evaluate(case, version, index, phase):
    calls, exposed = [], []
    generate = demo.generate

    def capture(messages, hits, *args, **kwargs):
        if not calls:
            exposed.extend({k: hit[k] for k in ('chunk_id', 'archivo_pdf', 'pagina_pdf')} for hit in hits)
        if phase == 'holdout':
            kwargs['output_limit'] = 160 if calls else 640
        row = {'num_predict': kwargs.get('output_limit')}
        calls.append(row)
        reply = generate(messages, hits, *args, **kwargs)
        row['text'] = reply['text']
        row['metadata'] = reply['metadata']
        return reply

    started = perf_counter()
    try:
        with patch.object(demo, 'generate', capture):
            result = demo.answer_demo(index, case['pregunta'], model=MODEL, converse=True, version=version)
    except (OSError, ValueError) as exc:
        result = {'error': type(exc).__name__}
    return {'case': case['id'], 'version': version, 'result': result, 'calls': calls,
            'exposed': exposed, 'seconds': perf_counter() - started}


def csv_export(path, fields, rows):
    with path.open('x', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            # Treat corpus/question/model content as inert spreadsheet text.
            writer.writerow({k: "'" + v if isinstance(v, str) and v.lstrip().startswith(
                ('=', '+', '-', '@')) else v for k, v in row.items()})


def summarize(cases, rows):
    summary = {}
    for version in (2, 3):
        arm = [row for row in rows if row['version'] == version]
        successful = [row for row in arm if 'error' not in row['result']]
        latency = sorted(row['seconds'] for row in successful)
        by_case = {row['case']: row for row in arm}
        substantive = [row for row in successful if not row['result']['abstained']]
        formal = 0
        for row in substantive:
            references = extract_citations(row['result']['response'])
            valid, _, _ = validate_citations(references, row['exposed'])
            formal += valid
        expected = {case['id']: {tuple(page) for page in case['paginas']}
                    for case in cases if case['paginas']}
        summary[version] = {
            'n': len(arm), 'errors': len(arm) - len(successful),
            'raw_missing': sum(not row['calls'] or 'text' not in row['calls'][0] for row in arm),
            'final_citations_formally_valid': formal,
            'final_citations_n': len(substantive),
            'final_abstentions': sum(row['result']['abstained'] for row in successful),
            'latency_success_n': len(latency),
            'mean_s': statistics.mean(latency) if latency else None,
            'median_s': statistics.median(latency) if latency else None,
            'p95_s': statistics.quantiles(latency, n=100, method='inclusive')[94] if len(latency) >= 20 else None,
            'retrieval_n': len(expected),
            'retrieval_errors': sum(not by_case[case_id]['exposed'] and 'error' in by_case[case_id]['result']
                                    for case_id in expected),
        }
        for k in (1, 5):
            hits = [{(h['archivo_pdf'], h['pagina_pdf']) for h in by_case[case_id]['exposed'][:k]}
                    for case_id in expected]
            summary[version][f'hit_at_{k}'] = sum(bool(found & gold)
                                                  for found, gold in zip(hits, expected.values()))
            summary[version][f'all_pages_at_{k}'] = sum(gold <= found
                                                        for found, gold in zip(hits, expected.values()))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--index', type=Path, default=Path('data/vector_db/index.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase', choices=('pilot', 'holdout'), required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        parser.error('El directorio de salida debe quedar fuera del repositorio')
    cases = json.loads(args.cases.read_text(encoding='utf-8'))
    if not cases or len({case['id'] for case in cases}) != len(cases):
        parser.error('Se requieren casos con identificadores únicos')
    if args.cases.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        parser.error('Las consultas privadas deben quedar fuera del repositorio')
    source_dir = Path(demo.__file__).parent
    manifest = {
        'phase': args.phase, 'provider': 'Ollama local', 'model': MODEL,
        'ollama': ollama_metadata(), 'top_k': 5, 'temperature': 0, 'seed': 42,
        'started_utc': datetime.now(timezone.utc).isoformat(), 'platform': platform.platform(),
        'cpu_count': os.cpu_count(), 'python': platform.python_version(),
        'num_predict': {'draft': 640, 'review': 160} if args.phase == 'holdout' else 'native',
        'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'git_status': subprocess.check_output(['git', 'status', '--porcelain'], text=True),
        'hashes': {str(p): digest(p) for p in (
            args.cases, args.index, Path(__file__),
            *sorted(source_dir.rglob('*.py')),
        )},
    }
    index = demo.load_demo_index(args.index)
    passages = {hit['chunk_id']: hit for hit in index.chunks}
    args.output.mkdir(mode=0o700)
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    rows, blind, secret = [], [], []
    with (args.output / 'traces.jsonl').open('x', encoding='utf-8') as trace:
        for number, case in enumerate(cases):
            for version in ((2, 3) if number % 2 == 0 else (3, 2)):
                row = evaluate(case, version, index, args.phase)
                rows.append(row)
                trace.write(json.dumps(row, ensure_ascii=False) + '\n')
                trace.flush()
                result = row['result']
                print(case['id'], f'v{version}', result.get('error') or result.get('reason')
                      or result.get('coverage'), round(row['seconds'], 2), flush=True)
                evidence = '\n\n'.join(
                    f"{n}. [{hit['archivo_pdf']} p. {hit['pagina_pdf']}] {passages[hit['chunk_id']]['texto']}"
                    for n, hit in enumerate(row['exposed'], 1)
                )
                raw = row['calls'][0].get('text') if row['calls'] else None
                draft, refs = raw_view(raw)
                for stage, response, references in (
                    ('RAW', draft, refs), ('FINAL', result.get('response', ''), ''),
                ):
                    blind_id = uuid.uuid4().hex
                    secret.append({'id': blind_id, 'caso': case['id'], 'version': version, 'etapa': stage})
                    blind.append({'id': blind_id, 'pregunta': case['pregunta'], 'respuesta': response,
                                  'referencias': references, 'evidencia': evidence,
                                  'estado': 'disponible' if response else 'sin_salida'})
    random.SystemRandom().shuffle(blind)
    csv_export(args.output / 'blind.csv', list(blind[0]) + LABELS, blind)
    csv_export(args.output / 'key.csv', list(secret[0]), secret)
    metrics = summarize(cases, rows)
    if any(digest(Path(name)) != value for name, value in manifest['hashes'].items()):
        raise RuntimeError('Las entradas cambiaron durante la corrida')
    if ollama_metadata() != manifest['ollama']:
        raise RuntimeError('Ollama o el modelo cambiaron durante la corrida')
    (args.output / 'technical.json').write_text(json.dumps(metrics, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
