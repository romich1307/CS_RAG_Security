#!/usr/bin/env python3
"""Compare v3 and v4 with equal Ollama budgets, preserving private traces and blind records."""
import argparse
import json
import platform
import random
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from evaluate_conversational_v3 import (
    LABELS, MODEL, csv_export, demo, digest, evaluate, ollama_metadata, raw_view, summarize,
)
from cs_rag_security.traceability import extract_citations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=Path, default=Path('data/vector_db/index.json'))
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if any(path.resolve().is_relative_to(root) for path in (args.cases, args.output)):
        parser.error('Consultas y salidas privadas deben quedar fuera del repositorio')
    cases = json.loads(args.cases.read_text(encoding='utf-8'))
    if not cases or len({case['id'] for case in cases}) != len(cases):
        parser.error('Se requieren casos con identificadores únicos')

    sources = [args.index, args.cases, Path(__file__),
               Path(__file__).with_name('evaluate_conversational_v3.py'),
               *sorted(Path(demo.__file__).parent.rglob('*.py'))]
    manifest = {
        'phase': 'v3-v4 holdout', 'model': MODEL, 'provider': 'Ollama local',
        'ollama': ollama_metadata(), 'started_utc': datetime.now(timezone.utc).isoformat(),
        'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'platform': platform.platform(), 'python': platform.python_version(),
        'git_status': subprocess.check_output(['git', 'status', '--porcelain'], text=True),
        'top_k': 5, 'seed': 42, 'temperature': 0, 'num_predict': {'draft': 640, 'review': 160},
        'hashes': {str(p): digest(p) for p in sources},
    }
    index = demo.load_demo_index(args.index)
    passages = {hit['chunk_id']: hit for hit in index.chunks}
    args.output.mkdir(mode=0o700)
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    rows, blind, key = [], [], []
    with (args.output / 'traces.jsonl').open('x', encoding='utf-8') as trace:
        for i, case in enumerate(cases):
            for version in ((3, 4) if i % 2 == 0 else (4, 3)):
                row = evaluate(case, version, index, 'holdout')
                rows.append(row)
                trace.write(json.dumps(row, ensure_ascii=False) + '\n')
                trace.flush()
                result = row['result']
                print(case['id'], version, result.get('reason') or result.get('coverage')
                      or result.get('error'), round(row['seconds'], 2), flush=True)
                evidence = '\n\n'.join(
                    f"{n}. [{h['archivo_pdf']} p. {h['pagina_pdf']}] {passages[h['chunk_id']]['texto']}"
                    for n, h in enumerate(row['exposed'], 1)
                )
                raw = row['calls'][0].get('text') if row['calls'] else None
                draft, refs = raw_view(raw)
                for stage, answer, references in (
                    ('RAW', draft, refs), ('FINAL', result.get('response', ''), ''),
                ):
                    identifier = uuid.uuid4().hex
                    key.append({'id': identifier, 'caso': case['id'], 'version': version, 'etapa': stage})
                    blind.append({'id': identifier, 'pregunta': case['pregunta'], 'respuesta': answer,
                                  'referencias': references, 'evidencia': evidence,
                                  'estado': 'disponible' if answer else 'sin_salida'})
    # Map version labels into the historical reducer's two fixed slots.
    paired_summary = summarize(cases, [{**r, 'version': r['version'] - 1} for r in rows])
    metrics = {}
    for version in (3, 4):
        arm = [r for r in rows if r['version'] == version]
        values = paired_summary[version - 1]
        for status in ('completa', 'parcial'):
            values[status] = sum(r['result'].get('coverage') == status for r in arm)
        values['ollama_calls'] = sum(len(r['calls']) for r in arm)
        references = {case['id']: {tuple(p) for p in case['paginas']} for case in cases}
        values['cites_all_expected'] = sum(
            bool(expected) and expected <= {(f, int(p)) for f, p in extract_citations(
                row['result'].get('response', ''))}
            for row in arm if (expected := references[row['case']])
        )
        metrics[version] = values
    if any(digest(Path(p)) != h for p, h in manifest['hashes'].items()):
        raise RuntimeError('Cambió una entrada durante la corrida')
    if ollama_metadata() != manifest['ollama']:
        raise RuntimeError('Cambió Ollama o el modelo durante la corrida')
    random.SystemRandom().shuffle(blind)
    csv_export(args.output / 'blind.csv', list(blind[0]) + LABELS, blind)
    csv_export(args.output / 'key.csv', list(key[0]), key)
    (args.output / 'technical.json').write_text(json.dumps(metrics, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
