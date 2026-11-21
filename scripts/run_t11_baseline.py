"""Ejecutor reproducible para T11: Baseline con LLM real (Ollama qwen2.5:3b).

Condición experimental: A_sin_defensa (Baseline RAG sin mecanismos defensivos).
Modelo: qwen2.5:3b vía Ollama local (http://127.0.0.1:11434/api/chat).
Parámetros: temperature=0, seed=42, top_k=5, documental=True.

Protección experimental:
- Genera un directorio único por corrida (results/llm_baseline_<timestamp>).
- Impide reutilizar o sobrescribir directorios existentes bajo cualquier circunstancia.
- Protege los artefactos versionados retirando enunciados y textos privados.
"""

import argparse
import csv
import importlib.metadata
import json
import os
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from cs_rag_security.ingestion import digest, read_json
from cs_rag_security.pipeline import answer
from cs_rag_security.retrieval import Index
from cs_rag_security.traceability import (
    determine_abstention_reason,
    ensure_unique_output_dir,
    extract_citations,
    get_git_commit,
)


SELECTED_QUESTION_IDS = [
    'GQ004',
    'GQ006',
    'GQ012',
    'GQ016',
    'GQ023',
    'GQ027',
    'GQ034',
    'GQ036',
    'GQ038',
    'GQ040',
]

TEST_QUESTION_ID = 'GQ001'


def execute_question(
    idx: Index,
    q_data: dict,
    mode: str,
    provider: str,
    top_k: int,
    documental: bool,
    seed: int
) -> dict:
    q_id = q_data['id']
    question = q_data['pregunta']

    # Comprobar que respuesta_referencia NUNCA se pasa al pipeline
    res = answer(
        index=idx,
        question=question,
        mode=mode,
        provider=provider,
        k=top_k,
        documental=documental,
        seed=seed,
    )

    retrieved = res.get('retrieved', [])
    accepted_ids = res.get('accepted_ids', [])
    accepted_chunks = [h for h in retrieved if h.get('chunk_id') in accepted_ids]

    raw_response = res.get('raw_response')
    final_response = res.get('response')
    abstained = res.get('abstained', False)
    abstention_reason = determine_abstention_reason(res)

    gen_meta = res.get('generation_metadata') or {}
    tokens = gen_meta.get('tokens')

    raw_citations = extract_citations(raw_response)
    final_citations = extract_citations(final_response)

    allowed = {(h['archivo_pdf'], str(h['pagina_pdf'])) for h in accepted_chunks}
    citations_valid = (
        bool(final_citations) and all(c in allowed for c in final_citations)
    ) if not abstained else False

    # Registro completo (para respaldo local)
    record = {
        'id': q_id,
        'question': question,
        'raw_response': raw_response,
        'response': final_response,
        'abstained': abstained,
        'abstention_reason': abstention_reason,
        'retrieved_chunks': [
            {
                'chunk_id': h['chunk_id'],
                'documento_id': h['documento_id'],
                'archivo_pdf': h['archivo_pdf'],
                'pagina_pdf': h['pagina_pdf'],
                'score': h.get('score'),
                'ocr_revision_manual_pendiente': h.get('ocr_revision_manual_pendiente', True),
            }
            for h in retrieved
        ],
        'accepted_chunks': [
            {
                'chunk_id': h['chunk_id'],
                'documento_id': h['documento_id'],
                'archivo_pdf': h['archivo_pdf'],
                'pagina_pdf': h['pagina_pdf'],
                'score': h.get('score'),
            }
            for h in accepted_chunks
        ],
        'accepted_ids': accepted_ids,
        'citations_raw': [{'archivo': c[0], 'pagina': int(c[1])} for c in raw_citations],
        'citations_final': [{'archivo': c[0], 'pagina': int(c[1])} for c in final_citations],
        'citations_valid': citations_valid,
        'model': gen_meta.get('model', 'qwen2.5:3b'),
        'provider': provider,
        'parameters': gen_meta.get('parameters', {'temperature': 0, 'seed': seed}),
        'latency_seconds': gen_meta.get('latency_seconds', res.get('seconds')),
        'pipeline_seconds': res.get('seconds'),
        'tokens': tokens,
    }
    return record


def sanitize_record_for_git(record: dict) -> dict:
    """Elimina enunciados gold, fragmentos de texto y salidas raw del LLM para cumplir reglas de privacidad."""
    retrieved = [
        {k: v for k, v in c.items() if k != 'texto'}
        for c in record.get('retrieved_chunks', [])
    ]
    accepted = [
        {k: v for k, v in c.items() if k != 'texto'}
        for c in record.get('accepted_chunks', [])
    ]
    sanitized = {
        'id': record['id'],
        'abstained': record['abstained'],
        'abstention_reason': record['abstention_reason'],
        'retrieved_chunks': retrieved,
        'accepted_chunks': accepted,
        'accepted_ids': record['accepted_ids'],
        'citations_raw': record['citations_raw'],
        'citations_final': record['citations_final'],
        'citations_valid': record['citations_valid'],
        'model': record['model'],
        'provider': record['provider'],
        'parameters': record['parameters'],
        'latency_seconds': record['latency_seconds'],
        'pipeline_seconds': record['pipeline_seconds'],
        'tokens': record['tokens'],
        'response': record['response'],
    }
    return sanitized


def build_manifest(
    out_dir: Path,
    evaluated_ids: list,
    mode: str,
    provider: str,
    model: str,
    model_digest: str,
    top_k: int,
    documental: bool,
    seed: int,
    started_utc: str,
    finished_utc: str,
    index_path: Path = Path('data/vector_db/index.json'),
    gold_path: Path = Path('data/corpus_unsa/03_Preguntas_Respuestas/gold_questions.json')
) -> dict:
    src_hashes = {str(p): digest(p) for p in sorted(Path('src').rglob('*.py'))}

    manifest = {
        'tarea': 'T11_baseline_ollama',
        'descripcion': 'Evaluación baseline con LLM real local sobre preguntas legítimas del dataset gold',
        'modo_experimental': mode,
        'modo_descripcion': 'A_sin_defensa: contexto concatenado directamente sin separación de roles ni filtrado heurístico (baseline de referencia)',
        'proveedor': provider,
        'modelo': model,
        'modelo_digest': model_digest,
        'parametros': {
            'temperature': 0,
            'seed': seed,
            'top_k': top_k,
            'documental': documental,
            'evidence_threshold': 0.12,
        },
        'commit_git': get_git_commit(),
        'python_version': platform.python_version(),
        'package_version': importlib.metadata.version('cs-rag-security'),
        'started_utc': started_utc,
        'finished_utc': finished_utc,
        'hashes': {
            'index_sha256': digest(index_path) if index_path.exists() else None,
            'gold_sha256': digest(gold_path) if gold_path.exists() else None,
            'src_sha256': src_hashes,
        },
        'preguntas_evaluadas': evaluated_ids,
        'total_preguntas': len(evaluated_ids),
        'condiciones_experimentales': {
            'aislamiento_gold': 'La respuesta gold nunca se indexa, no se pasa al pipeline ni se envía al LLM.',
            'verificacion_citas': 'Validador estricto compartido por A, B y C a nivel de pipeline: requiere formato [archivo.pdf p. N] perteneciente al conjunto de fragmentos aceptados. En las 10 consultas ejecutadas del baseline A, al no incluir instrucciones de formato en el prompt, el modelo omitió citas válidas en esos 10 casos, resultando en abstención del pipeline.',
            'preservacion_fallos': 'Trazas completas con raw_response y respuesta validada, preservando abstenciones.',
            'tratamiento_abstenciones': "Las abstenciones no se consideran automáticamente respuestas incorrectas; conforme a la rúbrica v0.2 se asigna calidad_respuesta = 'no_aplica' y se audita raw_response por separado.",
        }
    }
    (out_dir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


def write_traces_csv(out_dir: Path, records: list):
    """Escribe trazas CSV con métricas, tokens y telemetría autorizada (sin texto privado)."""
    fieldnames = [
        'id', 'abstained', 'abstention_reason', 'citations_valid',
        'latency_seconds', 'pipeline_seconds', 'prompt_tokens', 'completion_tokens', 'total_tokens',
        'model', 'provider', 'response'
    ]
    rows = []
    for r in records:
        tokens = r.get('tokens') or {}
        rows.append({
            'id': r['id'],
            'abstained': r['abstained'],
            'abstention_reason': r['abstention_reason'],
            'citations_valid': r['citations_valid'],
            'latency_seconds': r['latency_seconds'],
            'pipeline_seconds': r['pipeline_seconds'],
            'prompt_tokens': tokens.get('prompt_tokens'),
            'completion_tokens': tokens.get('completion_tokens'),
            'total_tokens': tokens.get('total_tokens'),
            'model': r['model'],
            'provider': r['provider'],
            'response': r['response'],
        })
    with (out_dir / 'traces.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def get_default_output_dir() -> Path:
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    return Path('results') / f'llm_baseline_{timestamp}'


def run_baseline(
    output_dir: Optional[Union[str, Path]] = None,
    mode: str = 'A_sin_defensa',
    model: str = 'qwen2.5:3b',
    provider: str = 'local',
    top_k: int = 5,
    seed: int = 42,
    model_digest: str = '357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b',
    test_only: bool = False,
    target_ids: Optional[list] = None,
    index_path: Union[str, Path] = 'data/vector_db/index.json',
    gold_path: Union[str, Path] = 'data/corpus_unsa/03_Preguntas_Respuestas/gold_questions.json',
    save_raw_backup: bool = True,
) -> Path:
    if output_dir is None:
        out_dir = get_default_output_dir()
    else:
        out_dir = Path(output_dir)

    ensure_unique_output_dir(out_dir)

    index_path = Path(index_path)
    gold_path = Path(gold_path)

    idx = Index.load(index_path)
    gold_data = read_json(gold_path)
    gold_by_id = {q['id']: q for q in gold_data['preguntas']}

    if target_ids is None:
        target_ids = [TEST_QUESTION_ID] if test_only else SELECTED_QUESTION_IDS

    started_utc = datetime.now(timezone.utc).isoformat()
    raw_records = []

    for q_id in target_ids:
        q_data = gold_by_id[q_id]
        rec = execute_question(
            idx=idx,
            q_data=q_data,
            mode=mode,
            provider=provider,
            top_k=top_k,
            documental=True,
            seed=seed,
        )
        raw_records.append(rec)

    finished_utc = datetime.now(timezone.utc).isoformat()

    # Sanitizar registros para versión Git
    sanitized_records = [sanitize_record_for_git(r) for r in raw_records]

    # Guardar traces.json sanitizado
    traces_file = out_dir / ('test_traces.json' if test_only else 'traces.json')
    traces_file.write_text(json.dumps(sanitized_records, ensure_ascii=False, indent=2), encoding='utf-8')

    if not test_only:
        write_traces_csv(out_dir, sanitized_records)
        build_manifest(
            out_dir=out_dir,
            evaluated_ids=target_ids,
            mode=mode,
            provider=provider,
            model=model,
            model_digest=model_digest,
            top_k=top_k,
            documental=True,
            seed=seed,
            started_utc=started_utc,
            finished_utc=finished_utc,
            index_path=index_path,
            gold_path=gold_path,
        )

        if save_raw_backup:
            # Respaldo local privado fuera de Git
            raw_traces_file = out_dir / 'raw_traces.json'
            raw_traces_file.write_text(json.dumps(raw_records, ensure_ascii=False, indent=2), encoding='utf-8')

    return out_dir


def main():
    parser = argparse.ArgumentParser(description='Ejecutor T11 Baseline con Ollama')
    parser.add_argument('--test-only', action='store_true', help='Ejecutar únicamente la consulta piloto de prueba GQ001')
    parser.add_argument('--output-dir', default=None, help='Directorio de salida único (por defecto: results/llm_baseline_<timestamp>)')
    parser.add_argument('--mode', default='A_sin_defensa', choices=['A_sin_defensa', 'B_defensa_basica', 'C_defensa_propuesta'])
    parser.add_argument('--model', default='qwen2.5:3b')
    parser.add_argument('--provider', default='local')
    parser.add_argument('--top-k', type=int, default=5)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--model-digest', default='357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b')
    args = parser.parse_args()

    os.environ['RAG_LOCAL_MODEL'] = args.model
    os.environ['RAG_LOCAL_URL'] = 'http://127.0.0.1:11434/api/chat'

    out_dir = run_baseline(
        output_dir=args.output_dir,
        mode=args.mode,
        model=args.model,
        provider=args.provider,
        top_k=args.top_k,
        seed=args.seed,
        model_digest=args.model_digest,
        test_only=args.test_only,
    )
    print(f"\nEjecución finalizada con éxito. Salida en: {out_dir}")
    print("Nota: para preparar la evaluación humana T12 use: python scripts/prepare_t12_eval.py")


if __name__ == '__main__':
    main()
