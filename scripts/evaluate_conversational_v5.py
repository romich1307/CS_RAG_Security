#!/usr/bin/env python3
"""Compare v4 and v5 with equal Ollama budgets, preserving private traces and blind records."""
import argparse
import json
import statistics
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


def raw_selection_view(raw, exposed, passages):
    if raw is None:
        return '', ''
    try:
        pairs = json.loads(raw)['selecciones']
        positions = [n for selected in pairs.values() for n in selected]
        if not all(type(n) is int and 1 <= n <= len(exposed) for n in positions):
            raise ValueError('Referencia fuera del contexto')
    except (AttributeError, ValueError, TypeError, KeyError):
        return '', ''
    if not positions:
        return 'El selector no propuso pasajes.', ''
    return ('\n\n'.join(passages[exposed[n - 1]['chunk_id']]['texto'] for n in positions),
            json.dumps(positions))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=Path, default=Path('data/vector_db/index.json'))
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase', choices=('pilot', 'holdout'), required=True)
    parser.add_argument('--qualified-manifest', type=Path)
    args = parser.parse_args()
    if args.phase == 'holdout' and not args.qualified_manifest:
        parser.error('La verificación requiere el manifiesto del piloto calificado')
    root = Path(__file__).resolve().parents[1]
    if any(path.resolve().is_relative_to(root) for path in (args.cases, args.output)):
        parser.error('Consultas y salidas privadas deben quedar fuera del repositorio')
    cases = json.loads(args.cases.read_text(encoding='utf-8'))
    if not cases or len({case['id'] for case in cases}) != len(cases):
        parser.error('Se requieren casos con identificadores únicos')

    sources = [args.index, args.cases, Path(__file__),
               Path(__file__).with_name('evaluate_conversational_v3.py'),
               *sorted(Path(demo.__file__).parent.rglob('*.py')),
               *sorted(Path('data/corpus_unsa').rglob('*.pdf')),
               *sorted(Path('data/corpus_unsa').rglob('*.jsonl')),
               *sorted(Path('data/corpus_unsa').rglob('gold_questions.json'))]
    if args.qualified_manifest:
        approval = args.qualified_manifest.with_name('qualification.json')
        if not approval.is_file():
            parser.error('Falta el dictamen explícito de aprobación del piloto')
        gate = json.loads(approval.read_text())
        if gate.get('passed') is not True or gate.get('manifest_sha256') != digest(args.qualified_manifest):
            parser.error('El dictamen no aprueba este manifiesto')
        pilot = json.loads(args.qualified_manifest.read_text())
        frozen = {k: v for k, v in pilot['hashes'].items() if k != pilot['cases']}
        if (pilot['phase'] != 'pilot' or not Path(args.qualified_manifest.parent/'technical.json').is_file()
                or any(digest(Path(k)) != h for k, h in frozen.items())
                or pilot['ollama'] != ollama_metadata() or digest(args.cases) == pilot['hashes'][pilot['cases']]):
            parser.error('El código o entorno difieren del piloto o se repiten sus consultas')
    manifest = {
        'phase': args.phase, 'cases': str(args.cases),
        'schedule': 'serial, orden alternado, sin reiniciar caché entre casos', 'model': MODEL, 'provider': 'Ollama local',
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
            for version in ((5,) if args.phase == 'pilot' else (4, 5) if i % 2 == 0 else (5, 4)):
                row = evaluate(case, version, index, 'holdout')
                row['raw_received'] = bool(row['calls'] and 'text' in row['calls'][0])
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
                if version == 5:
                    draft, refs = raw_selection_view(raw, row['exposed'], passages)
                else:
                    draft, refs = raw_view(raw)
                    try:
                        draft = draft if raw is None or isinstance(json.loads(raw)['afirmaciones'], list) else ''
                    except (ValueError, KeyError, TypeError):
                        draft, refs = '', ''
                for stage, answer, references in (
                    ('RAW', draft, refs), ('FINAL', result.get('response', ''), ''),
                ):
                    identifier = uuid.uuid4().hex
                    key.append({'id': identifier, 'caso': case['id'], 'version': version, 'etapa': stage})
                    blind.append({'id': identifier, 'pregunta': case['pregunta'], 'respuesta': answer,
                                  'referencias': references, 'evidencia': evidence,
                                  'estado': ('disponible' if answer else 'formato_invalido'
                                             if stage == 'RAW' and row['raw_received'] else 'sin_salida')})
    # Map version labels into the historical reducer's two fixed slots.
    normalized = [{**r, 'version': r['version'] - 2} for r in rows]
    if args.phase == 'pilot':
        normalized.extend({**r, 'version': 2} for r in rows)
    paired_summary = summarize(cases, normalized)
    metrics = {}
    for version in ((5,) if args.phase == 'pilot' else (4, 5)):
        arm = [r for r in rows if r['version'] == version]
        values = paired_summary[version - 2]
        expected = {case['id']: set(map(tuple, case['paginas'])) for case in cases if case['paginas']}
        values['hit_at_3'] = sum(bool(expected.get(row['case'], set()) & {
            (h['archivo_pdf'], h['pagina_pdf']) for h in row['exposed'][:3]}) for row in arm)
        stages = {}
        for stage in ('prepare_index', 'retrieve', 'filter', 'context', 'draft_ollama',
                      'review_ollama', 'validation_and_format'):
            measured = [r['result']['timings_ms'][stage] for r in arm
                        if stage in r['result'].get('timings_ms', {})]
            if measured:
                stages[stage] = {'n': len(measured), 'median_ms': statistics.median(measured),
                                 'mean_ms': statistics.mean(measured)}
        values['stage_times'] = stages
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
