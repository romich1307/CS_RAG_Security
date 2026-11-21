"""Ejecuta la comparación pareada de utilidad sobre las consultas legítimas."""

import argparse
import hashlib
import ipaddress
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import ProxyHandler, build_opener

from cs_rag_security.defenses import MODES
from cs_rag_security.evaluation.quality import compute_latency_summary
from cs_rag_security.generation import NoRedirect
from cs_rag_security.pipeline import answer
from cs_rag_security.retrieval import Index
from cs_rag_security.traceability import (
    build_run_manifest,
    build_trace_record,
    is_path_git_ignored,
    save_experimental_run,
)


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / 'results/llm_baseline/manifest.json'
PRIVATE_RESULTS = ROOT / 'results/llm_abc_local'
T08_INDEX_HASH = '7364fa03eeb3fc6dfd2a7832ef421c74f9ef31c63bd34635f53b671e625618fa'
TOP_K = 5
SEED = 42


def snapshot(path, allowed_hashes, description):
    data = path.read_bytes()
    checksum = hashlib.sha256(data).hexdigest()
    if checksum not in allowed_hashes:
        raise ValueError(f'El SHA-256 del {description} no coincide con una instantánea registrada.')
    return json.loads(data), checksum


def local_model(expected):
    model = os.environ.get('RAG_LOCAL_MODEL')
    if model != expected:
        raise ValueError(f'Configura RAG_LOCAL_MODEL con {expected}.')
    url = urlparse(os.environ.get('RAG_LOCAL_URL', 'http://127.0.0.1:11434/api/chat'))
    if (
        url.scheme != 'http' or not url.hostname or not ipaddress.ip_address(url.hostname).is_loopback
        or url.username or url.password or url.path != '/api/chat' or url.query or url.fragment
    ):
        raise ValueError('Se requiere una URL local de Ollama con ruta /api/chat.')
    server = f'{url.scheme}://{url.netloc}'
    opener = build_opener(ProxyHandler({}), NoRedirect())
    with opener.open(f'{server}/api/tags', timeout=5) as response:
        tags = json.load(response)
    with opener.open(f'{server}/api/version', timeout=5) as response:
        version = json.load(response).get('version')
    checksum = next(
        (item.get('digest') for item in tags['models'] if model in (item.get('model'), item.get('name'))),
        None,
    )
    if not isinstance(checksum, str) or not re.fullmatch(r'[0-9a-f]{64}', checksum) or not version:
        raise ValueError('Ollama no devolvió digest y versión para el modelo seleccionado.')
    return {'modelo': model, 'modelo_digest': checksum, 'ollama_version': version}


def summarize_latencies(records):
    by_mode = {}
    for mode in MODES:
        condition_records = [record for record in records if record['condition'] == mode]
        by_mode[mode] = {
            'pipeline_sin_recuperacion': compute_latency_summary(
                [record['latency_pipeline_seconds'] for record in condition_records],
                'Pipeline sin la recuperación pareada compartida',
            ),
            'generacion': compute_latency_summary(
                [record['latency_generation_seconds'] for record in condition_records],
                'Llamada al generador',
            ),
        }
    return by_mode


def run_utility(index_path, gold_path, run_id, provider):
    if provider not in ('mock', 'local'):
        raise ValueError('El proveedor debe ser mock o local.')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', run_id):
        raise ValueError('El ID de corrida debe contener solo letras, cifras, guiones o guiones bajos.')
    out = PRIVATE_RESULTS / run_id
    private = out / 'privado'
    if out.exists():
        raise FileExistsError(f'La corrida ya existe: {out}')
    if out.resolve() != out or not all(is_path_git_ignored(path, ROOT) for path in (out, private)):
        raise ValueError('La corrida requiere rutas locales ignoradas por Git.')
    baseline = json.loads(BASELINE.read_text(encoding='utf-8'))
    source_hashes = baseline['hashes']
    index_input, index_hash = snapshot(
        index_path, {source_hashes['index_sha256'], T08_INDEX_HASH}, 'índice documental',
    )
    gold_input, gold_hash = snapshot(gold_path, {source_hashes['gold_sha256']}, 'gold')
    if index_input['method'] != Index.method:
        raise ValueError('El piloto requiere el recuperador textual de T14.')
    index = Index(index_input['chunks'])
    questions = {item['id']: item['pregunta'] for item in gold_input['preguntas']}
    selected = baseline['preguntas_evaluadas']
    config = local_model(baseline['modelo']) if provider == 'local' else {
        'modelo': 'mock_extractivo_v1', 'modelo_digest': None, 'ollama_version': None,
    }

    started = datetime.now(timezone.utc).isoformat()
    traces, failures = [], []
    parameters = {'top_k': TOP_K, 'seed': SEED, 'documental': True, 'temperature': 0.0, 'evidence_threshold': 0.12}
    for case_id in selected:
        question = questions[case_id]
        hits = index.search(question, TOP_K)
        for mode in MODES:
            try:
                result = answer(
                    index, question, mode=mode, provider=provider, k=TOP_K,
                    documental=True, seed=SEED, hits=hits,
                )
            except (TimeoutError, URLError, ValueError) as error:
                failures.append({'case_id': case_id, 'condition': mode, 'tipo_error': type(error).__name__})
                continue
            traces.append(build_trace_record(
                run_id=run_id, case_id=case_id, mode=mode, pipeline_result=result,
                case_kind='gold', question=question, provider=provider,
                model=config['modelo'], model_digest=config['modelo_digest'], **parameters,
            ))

    version = next((trace['detector_version'] for trace in traces), None)
    manifest = build_run_manifest(
        run_id=run_id, task_name='T17_utilidad_pareada',
        description='Comparación A/B/C de consultas documentales legítimas',
        evaluated_cases=selected, modes=list(MODES), provider=provider, model=config['modelo'],
        started_utc=started, finished_utc=datetime.now(timezone.utc).isoformat(),
        model_digest=config['modelo_digest'], detector_version=version, parameters=parameters,
        index_path=index_path, gold_path=gold_path, attacks_path=None,
        extra_hashes={'index_sha256': index_hash, 'gold_sha256': gold_hash},
        extra_metadata={
            'alcance': 'consultas_legitimas',
            'ollama_version': config['ollama_version'],
            'recuperador': index.method,
            'trazas_registradas': len(traces),
            'incidencias': failures,
            'latencias_segundos': summarize_latencies(traces),
        },
    )
    save_experimental_run(out, manifest, traces, private_dir=private)
    return out, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--indice', type=Path, required=True)
    parser.add_argument('--gold', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--proveedor', choices=('mock', 'local'), default='mock')
    args = parser.parse_args()
    try:
        out, manifest = run_utility(args.indice, args.gold, args.run_id, args.proveedor)
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')
    extra = manifest['extra']
    print(f'{out} · {extra["trazas_registradas"]} trazas, {len(extra["incidencias"])} errores.')
    return int(bool(extra['incidencias']))


if __name__ == '__main__':
    raise SystemExit(main())
