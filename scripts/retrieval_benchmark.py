"""Benchmark T08: mismos documentos/preguntas, recuperación textual y ONNX local."""
import argparse
import csv
import importlib.metadata
import json
import os
import platform
import random
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from cs_rag_security.ingestion import audit, chunks, digest, load_pages, read_json
from cs_rag_security.retrieval import Index
from cs_rag_security.retrieval.semantico import SemanticIndex


def fraction(numerator, denominator):
    return {'numerator': numerator, 'denominator': denominator,
            'value': numerator / denominator if denominator else None}


def load_inputs(corpus, protocol):
    report = audit(corpus)
    pages = load_pages(corpus)
    gold_path = corpus / '03_Preguntas_Respuestas/gold_questions.json'
    gold = read_json(gold_path)['preguntas']
    keys = {(page['documento_id'], page['pagina_pdf']) for page in pages}
    questions, seen = [], set()
    for question in gold:
        if not question.get('apta_para_evaluar_recuperacion_documental_piloto'):
            continue
        if not question['id'] or question['id'] in seen or not question['pregunta'].strip():
            raise ValueError('ID duplicado o pregunta vacía')
        seen.add(question['id'])
        if not question['fuentes'] or any((s['documento_id'], s['pagina_pdf']) not in keys for s in question['fuentes']):
            raise ValueError('Fuente fuera del corpus oficial')
        # Las respuestas de referencia no forman parte del índice ni del expediente exportado.
        questions.append({key: question[key] for key in ('id', 'pregunta', 'fuentes')})
    primary = protocol['primary_question_ids']
    if not primary or len(primary) != len(set(primary)) or not set(primary) <= seen:
        raise ValueError('Selección primaria inválida')
    return pages, questions, report, digest(gold_path)


def summarize(rows, timings, identifiers, methods):
    selected = set(identifiers)
    result = {'n_questions': len(selected), 'methods': {}}
    for method in methods:
        subset = [row for row in rows if row['question_id'] in selected and row['method'] == method]
        assert len(subset) == len(selected)
        durations = [row['seconds'] for row in timings if row['question_id'] in selected and row['method'] == method]
        ordered = sorted(durations)
        position = (len(ordered) - 1) * 0.95
        low = int(position)
        p95 = ordered[low] + (ordered[min(low + 1, len(ordered) - 1)] - ordered[low]) * (position - low)
        result['methods'][method] = {
            'provider': 'local_cpu_retrieval',
            **{f'hit_at_{k}': fraction(sum(row[f'hit_at_{k}'] for row in subset), len(subset)) for k in (1, 3, 5)},
            'latency': {'denominator': len(durations), 'unit': 'seconds',
                        'median': statistics.median(durations), 'p95_linear': p95,
                        'mean': statistics.mean(durations)},
        }
    return result


def directory_bytes(path):
    return sum(item.stat().st_size for item in Path(path).rglob('*') if item.is_file())


def write_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def cpu_name():
    if os.name == 'nt':
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
            return winreg.QueryValueEx(key, 'ProcessorNameString')[0].strip()
    return platform.processor()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, default=Path('data/corpus_unsa'))
    parser.add_argument('--model-directory', type=Path, required=True)
    parser.add_argument('--index-directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--protocol', type=Path, default=Path('experiments/retrieval_protocol.json'))
    parser.add_argument('--reuse-index', action='store_true')
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError(args.output)
    if args.index_directory.exists() and not args.reuse_index:
        raise FileExistsError(args.index_directory)
    protocol = read_json(args.protocol)
    if protocol['top_k'] != [1, 3, 5] or not 1 <= protocol['latency_repeats'] <= 100:
        raise ValueError('Protocolo top-k o repeticiones inválido')
    started = datetime.now(timezone.utc).isoformat()
    pages, questions, report, gold_hash = load_inputs(args.corpus, protocol)
    fragments = chunks(pages, protocol['chunk_size_words'], protocol['chunk_overlap_words'])
    if any(fragment['documento_id'] == 'RCU-0252-2021' for fragment in fragments):
        raise ValueError('Documento histórico en el benchmark')
    start = time.perf_counter()
    baseline = Index(fragments)
    build_seconds = {baseline.method: time.perf_counter() - start}
    start = time.perf_counter()
    if args.reuse_index:
        semantic = SemanticIndex.load(args.index_directory / 'semantic', args.model_directory, protocol['onnx_threads'])
        if semantic.chunks != fragments:
            raise ValueError('El índice guardado corresponde a otros fragmentos')
    else:
        semantic = SemanticIndex(fragments, args.model_directory, protocol['onnx_threads'])
        args.index_directory.mkdir(parents=True, exist_ok=False)
        semantic.save(args.index_directory / 'semantic')
        baseline.save(args.index_directory / 'textual.json', {'scope': 'T08', 'n_chunks': len(fragments)})
    build_seconds[semantic.method] = time.perf_counter() - start
    model = semantic.encoder.manifest
    if (model['model_id'] != protocol['model_id'] or model['revision'] != protocol['model_revision'] or
            model['onnx_file'] != protocol['model_variant'] or model['max_length'] != protocol['model_max_tokens']):
        raise ValueError('El modelo no corresponde al protocolo fijado')
    indexes = [baseline, semantic]
    for index in indexes:
        for question in questions[:protocol['warmup_queries_per_method']]:
            index.search(question['pregunta'], k=5)
    rows, ranked = [], []
    for question in questions:
        expected = {(source['documento_id'], source['pagina_pdf']) for source in question['fuentes']}
        for index in indexes:
            hits = index.search(question['pregunta'], k=5)
            row = {'question_id': question['id'], 'method': index.method,
                   'primary': question['id'] in protocol['primary_question_ids'],
                   'expected_pages': '|'.join(f'{doc}:{page}' for doc, page in sorted(expected)),
                   'retrieved_ids': '|'.join(hit['chunk_id'] for hit in hits),
                   'retrieved_pages': '|'.join(f"{hit['documento_id']}:{hit['pagina_pdf']}" for hit in hits)}
            for k in (1, 3, 5):
                found = {(hit['documento_id'], hit['pagina_pdf']) for hit in hits[:k]}
                row[f'hit_at_{k}'] = bool(expected & found)
            rows.append(row)
            ranked.append({'question_id': question['id'], 'method': index.method, 'hits': [
                {key: hit[key] for key in ('chunk_id', 'documento_id', 'archivo_pdf', 'pagina_pdf', 'score')}
                for hit in hits]})
    schedule = [(question, repetition) for question in questions for repetition in range(protocol['latency_repeats'])]
    random.Random(protocol['seed']).shuffle(schedule)
    timings = []
    for number, (question, repetition) in enumerate(schedule):
        order = indexes if number % 2 == 0 else list(reversed(indexes))
        for index in order:
            start = time.perf_counter()
            index.search(question['pregunta'], k=5)
            timings.append({'question_id': question['id'], 'method': index.method,
                            'repetition': repetition, 'seconds': time.perf_counter() - start})
    methods = [index.method for index in indexes]
    metrics = {
        'primary': summarize(rows, timings, protocol['primary_question_ids'], methods),
        'exploratory_all_original_gold': summarize(rows, timings, [q['id'] for q in questions], methods),
        'costs': {
            baseline.method: {'build_seconds': build_seconds[baseline.method],
                              'artifact_bytes': (args.index_directory / 'textual.json').stat().st_size,
                              'storage': 'JSON de fragmentos; TF-IDF se reconstruye al cargar'},
            semantic.method: {'build_or_load_seconds': build_seconds[semantic.method],
                              'artifact_bytes': directory_bytes(args.index_directory / 'semantic'),
                              'vector_bytes_in_memory': semantic.vectors.nbytes,
                              'model_files_bytes': sum(model['files_bytes'].values()),
                              'storage': 'JSON de fragmentos y matriz float32 NPY normalizada'},
        },
    }
    base = Path(__file__).resolve().parents[1]
    sources = [Path(__file__), base / 'src/cs_rag_security/retrieval/__init__.py',
               base / 'src/cs_rag_security/retrieval/semantico.py', base / 'src/cs_rag_security/ingestion/__init__.py',
               base / 'pyproject.toml']
    import psutil
    manifest = {
        'status': 'completed', 'task': 'T08', 'scope': 'retrieval_only_no_llm_generation',
        'started_utc': started, 'finished_utc': datetime.now(timezone.utc).isoformat(),
        'python': platform.python_version(), 'platform': platform.platform(),
        'hardware': {'cpu': cpu_name(), 'logical_cpus': os.cpu_count(), 'ram_bytes': psutil.virtual_memory().total,
                     'device': 'CPUExecutionProvider', 'onnx_threads': protocol['onnx_threads']},
        'versions': {name: importlib.metadata.version(name) for name in ('numpy', 'onnxruntime', 'tokenizers', 'psutil')},
        'corpus': report, 'gold_sha256': gold_hash, 'protocol_sha256': digest(args.protocol),
        'protocol': protocol, 'n_chunks': len(fragments), 'n_questions': len(questions),
        'model': model, 'model_manifest_sha256': semantic.encoder.manifest_sha256,
        'model_directory_name': args.model_directory.name, 'reuse_index': args.reuse_index,
        'semantic_comparison': 'executed',
        'truncated_chunks': fraction(sum(n > semantic.encoder.max_length for n in semantic.token_lengths), len(fragments)),
        'source_sha256': {str(path.relative_to(base)): digest(path) for path in sources},
        'limitations': [
            'La muestra primaria consta de 13 preguntas con cotejo asistido; revisión humana del equipo pendiente.',
            'Las 40 preguntas son un análisis exploratorio; GQ030 y GQ040 conservan incidencias conocidas.',
            'Los dos métodos reciben los mismos fragmentos; MiniLM trunca a 128 tokens y se informa cuántos.',
            'TF-IDF descarta puntuaciones no positivas; el semántico devuelve sus cinco vecinos.',
            'Hit@k exige al menos una fuente documento/página; no mide exactitud del LLM ni vigencia actual.',
            '115 páginas OCR conservan revisión pendiente. Un modelo, una máquina y una corrida de construcción.',
            'La latencia incluye vectorizar la consulta y buscar; excluye carga e indexación. Cinco repeticiones por pregunta.',
            'Los tamaños de artefactos usan formatos distintos; los pesos del modelo se informan por separado.',
        ],
    }
    args.output.mkdir(parents=True, exist_ok=False)
    write_csv(args.output / 'retrieval.csv', rows)
    write_csv(args.output / 'latency.csv', timings)
    (args.output / 'ranked_hits.json').write_text(json.dumps(ranked, ensure_ascii=False, indent=2), encoding='utf-8')
    (args.output / 'metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
    (args.output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'n_chunks': len(fragments), 'primary': metrics['primary'],
                      'exploratory': metrics['exploratory_all_original_gold'],
                      'costs': metrics['costs'], 'truncated_chunks': manifest['truncated_chunks']}, indent=2))
    return metrics


if __name__ == '__main__':
    main()
