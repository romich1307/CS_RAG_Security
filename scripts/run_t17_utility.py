"""Ejecuta la comparación pareada de utilidad sobre las consultas legítimas."""

import argparse
import hashlib
import ipaddress
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import ProxyHandler, build_opener

from cs_rag_security.defenses import MODES
from cs_rag_security.generation import NoRedirect
from cs_rag_security.pipeline import answer
from cs_rag_security.retrieval import Index

from .run_t11_baseline import determine_abstention_reason, extract_citations


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


def write_json(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def run_utility(index_path, gold_path, run_id, provider):
    if provider not in ('mock', 'local'):
        raise ValueError('El proveedor debe ser mock o local.')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', run_id):
        raise ValueError('El ID de corrida debe contener solo letras, cifras, guiones o guiones bajos.')
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

    out = PRIVATE_RESULTS / run_id
    if out.resolve() != out or subprocess.run(
        ['git', 'check-ignore', '-q', '--', str(out / 'manifest.json')], cwd=ROOT, check=False,
    ).returncode != 0:
        raise ValueError('La corrida requiere una ruta local ignorada por Git.')
    out.mkdir(parents=True)
    started = datetime.now(timezone.utc).isoformat()
    traces, private_traces = [], []
    for case_id in selected:
        question = questions[case_id]
        hits = index.search(question, TOP_K)
        retrieved_ids = [hit['chunk_id'] for hit in hits]
        for mode in MODES:
            common = {
                'run_id': run_id, 'case_id': case_id, 'pregunta_id': case_id, 'case_kind': 'gold',
                'condition': mode, 'provider': provider, 'model': config['modelo'],
                'retrieved_ids': retrieved_ids,
            }
            try:
                result = answer(
                    index, question, mode=mode, provider=provider, k=TOP_K,
                    documental=True, seed=SEED, hits=hits,
                )
            except (TimeoutError, URLError, ValueError) as error:
                traces.append({**common, 'status': 'error', 'tipo_error': type(error).__name__})
                continue
            generation = result['generation_metadata'] or {}
            accepted_ids = result['accepted_ids']
            sources = {(hit['archivo_pdf'], str(hit['pagina_pdf'])) for hit in hits
                       if hit['chunk_id'] in accepted_ids}
            citations = extract_citations(result['response'])
            tags = result['detector_log']
            trace = {
                **common, 'status': 'completo',
                'accepted_ids': accepted_ids,
                'discarded_ids': [hit_id for hit_id in retrieved_ids if hit_id not in accepted_ids],
                'abstained': result['abstained'],
                'abstention_reason': determine_abstention_reason(result),
                'generation_performed': result['raw_response'] is not None,
                'citations_valid': not result['abstained'] and bool(citations)
                and all(citation in sources for citation in citations),
                'latency_pipeline_seconds': result['seconds'],
                'latency_generation_seconds': generation.get('latency_seconds'),
                'tokens': generation.get('tokens'),
                'prompt_version': result.get('prompt_version', 'v3' if mode == MODES[2] else 'v1'),
                'detector_version': result.get('detector_version') or (tags[0]['detector'] if tags else None),
                'detector_log': tags,
            }
            traces.append(trace)
            private_traces.append({
                **trace, 'question': question, 'response': result['response'],
                'raw_response': result['raw_response'], 'retrieved': hits,
            })

    commit = subprocess.run(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()
    manifest = {
        'run_id': run_id, 'tarea': 'T17_utilidad_pareada', 'proveedor': provider, **config,
        'alcance': 'consultas_legitimas', 'commit_git': commit,
        'started_utc': started, 'finished_utc': datetime.now(timezone.utc).isoformat(),
        'condiciones_evaluadas': list(MODES), 'casos_evaluados': selected,
        'parametros': {'top_k': TOP_K, 'seed': SEED, 'documental': True, 'temperature': 0},
        'recuperador': index.method,
        'hashes': {'index_sha256': index_hash, 'gold_sha256': gold_hash},
        'trazas_esperadas': len(selected) * len(MODES), 'trazas_registradas': len(traces),
        'trazas_con_error': sum(trace['status'] == 'error' for trace in traces),
    }
    write_json(out / 'traces.json', traces)
    write_json(out / 'raw_traces.json', private_traces)
    write_json(out / 'manifest.json', manifest)
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
    print(f'{out} · {manifest["trazas_registradas"]} trazas, {manifest["trazas_con_error"]} errores.')
    return int(manifest['trazas_con_error'] > 0)


if __name__ == '__main__':
    raise SystemExit(main())
