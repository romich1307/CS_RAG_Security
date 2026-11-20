"""Ejecutor reproducible para T11: Baseline con LLM real (Ollama qwen2.5:3b).

Condición experimental: A_sin_defensa (Baseline RAG sin mecanismos defensivos).
Modelo: qwen2.5:3b vía Ollama local (http://127.0.0.1:11434/api/chat).
Parámetros: temperature=0, seed=42, top_k=5, documental=True.
"""

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from cs_rag_security.ingestion import digest, read_json
from cs_rag_security.pipeline import answer
from cs_rag_security.retrieval import Index


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


def get_git_commit():
    try:
        res = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except Exception:
        return 'unknown'


def extract_citations(text: str):
    if not text:
        return []
    return re.findall(r'\[([^\[\]]+\.pdf) p\. (\d+)\]', text)


def determine_abstention_reason(res: dict) -> str:
    if not res.get('abstained'):
        return ''
    response = res.get('response', '')
    if 'no hay evidencia fiable suficiente' in response:
        return 'evidencia_insuficiente_o_no_fiable'
    if 'carece de citas válidas' in response:
        return 'citas_invalidas_o_ausentes'
    if 'rechazó la consulta' in response:
        return 'rechazo_del_modelo'
    if 'no devolvió contenido' in response:
        return 'modelo_vacio'
    return 'abstencion_otra'


def execute_question(idx: Index, q_data: dict, mode: str, provider: str, top_k: int, documental: bool, seed: int):
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
        'tokens': tokens,  # null si no fue reportado
    }
    return record


def build_manifest(out_dir: Path, evaluated_ids: list, mode: str, provider: str, model: str, model_digest: str, top_k: int, documental: bool, seed: int, started_utc: str, finished_utc: str):
    index_path = Path('data/vector_db/index.json')
    gold_path = Path('data/corpus_unsa/03_Preguntas_Respuestas/gold_questions.json')
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
            'verificacion_citas': 'Validador estricto compartido por A, B y C a nivel de pipeline: requiere formato [archivo.pdf p. N] perteneciente al conjunto de fragmentos aceptados. El modo A no utiliza instrucciones defensivas ni de citación en su prompt, por lo que respuestas sin citas válidas resultan en abstención del pipeline.',
            'preservacion_fallos': 'Trazas completas con raw_response y respuesta validada, preservando abstenciones.',
            'tratamiento_abstenciones': "Las abstenciones no se consideran automáticamente respuestas incorrectas; conforme a la rúbrica v0.1 se asigna calidad_respuesta = 'no_aplica' y se audita raw_response por separado.",
        }
    }
    (out_dir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


def prepare_t12_blind_materials(out_dir: Path, records: list, corrida_id: str):
    t12_cases = []
    csv_rows = []

    for idx, r in enumerate(records, start=1):
        caso_ciego_id = f'CIEGO_{idx:02d}'
        evaluacion_id = f'EVAL-T12-{idx:03d}'
        q_id = r['id']

        t12_cases.append({
            'caso_ciego_id': caso_ciego_id,
            'pregunta_id': q_id,
            'pregunta': r['question'],
            'tipo_consulta': 'documental',
            'respuesta_a_evaluar': r['response'],
            'raw_response_audit': r['raw_response'],
            'abstained': r['abstained'],
            'motivo_abstencion': r['abstention_reason'],
            'evidencia_recuperada_sistema': r['accepted_chunks'],
            # Nota: NUNCA se incluye 'respuesta_referencia' (gold) ni fuentes esperadas del gold en la evaluación a ciegas
        })

        csv_rows.append({
            'evaluacion_id': evaluacion_id,
            'corrida_id': corrida_id,
            'caso_ciego_id': caso_ciego_id,
            'pregunta_id': q_id,
            'evaluador_id': 'leon',
            'rubrica_version': '0.1',
            'referencia_caso': f'results/llm_baseline/t12_material_ciego.json#{caso_ciego_id}',
            'referencia_salida': f'results/llm_baseline/traces.json#{q_id}',
            'referencia_contexto': f'results/llm_baseline/traces.json#{q_id}.accepted_chunks',
            'referencia_manifiesto': 'results/llm_baseline/manifest.json',
            'tipo_consulta': 'documental',
            'evidencia_disponible': '',
            'estado_revision': 'pendiente',
            'tipo_salida': '',
            'calidad_respuesta': '',
            'abstencion_adecuada': '',
            'cita_pertenece_contexto': '',
            'cita_sustenta_respuesta': '',
            'error_vigencia': '',
            'justificacion': '',
            'referencia_fuente': '',  # A ser completado por el evaluador en T12
            'incidencia': '',
            'revisado_por': '',
            'fecha_revision': '',
        })

    (out_dir / 't12_material_ciego.json').write_text(json.dumps(t12_cases, ensure_ascii=False, indent=2), encoding='utf-8')

    fieldnames = [
        'evaluacion_id', 'corrida_id', 'caso_ciego_id', 'pregunta_id', 'evaluador_id',
        'rubrica_version', 'referencia_caso', 'referencia_salida', 'referencia_contexto',
        'referencia_manifiesto', 'tipo_consulta', 'evidencia_disponible', 'estado_revision',
        'tipo_salida', 'calidad_respuesta', 'abstencion_adecuada', 'cita_pertenece_contexto',
        'cita_sustenta_respuesta', 'error_vigencia', 'justificacion', 'referencia_fuente',
        'incidencia', 'revisado_por', 'fecha_revision'
    ]
    with (out_dir / 't12_evaluacion_ciega.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)


def write_traces_csv(out_dir: Path, records: list):
    fieldnames = [
        'id', 'question', 'abstained', 'abstention_reason', 'citations_valid',
        'latency_seconds', 'pipeline_seconds', 'prompt_tokens', 'completion_tokens', 'total_tokens',
        'model', 'provider', 'response', 'raw_response'
    ]
    rows = []
    for r in records:
        tokens = r.get('tokens') or {}
        rows.append({
            'id': r['id'],
            'question': r['question'],
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
            'raw_response': r['raw_response'],
        })
    with (out_dir / 'traces.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description='Ejecutor T11 Baseline con Ollama')
    parser.add_argument('--test-only', action='store_true', help='Ejecutar únicamente la consulta piloto de prueba GQ001')
    parser.add_argument('--output-dir', default='results/llm_baseline', help='Directorio de salida')
    parser.add_argument('--mode', default='A_sin_defensa', choices=['A_sin_defensa', 'B_defensa_basica', 'C_defensa_propuesta'])
    parser.add_argument('--model', default='qwen2.5:3b')
    parser.add_argument('--provider', default='local')
    parser.add_argument('--top-k', type=int, default=5)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--model-digest', default='357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b')
    args = parser.parse_args()

    os.environ['RAG_LOCAL_MODEL'] = args.model
    os.environ['RAG_LOCAL_URL'] = 'http://127.0.0.1:11434/api/chat'

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    idx = Index.load('data/vector_db/index.json')
    gold_data = read_json('data/corpus_unsa/03_Preguntas_Respuestas/gold_questions.json')
    gold_by_id = {q['id']: q for q in gold_data['preguntas']}

    target_ids = [TEST_QUESTION_ID] if args.test_only else SELECTED_QUESTION_IDS

    print(f"=== T11 Baseline Ollama ===")
    print(f"Modo: {args.mode}")
    print(f"Modelo: {args.model}")
    print(f"Preguntas a ejecutar ({len(target_ids)}): {target_ids}")
    print(f"Directorio de salida: {out_dir}")

    started_utc = datetime.now(timezone.utc).isoformat()
    records = []

    for q_id in target_ids:
        q_data = gold_by_id[q_id]
        print(f"\n[{q_id}] Ejecutando: {q_data['pregunta'][:60]}...")
        rec = execute_question(
            idx=idx,
            q_data=q_data,
            mode=args.mode,
            provider=args.provider,
            top_k=args.top_k,
            documental=True,
            seed=args.seed
        )
        records.append(rec)
        print(f" -> Latencia: {rec['latency_seconds']:.2f}s | Abstenido: {rec['abstained']} | Motivo: {rec['abstention_reason']}")
        print(f" -> Tokens: {rec['tokens']}")
        print(f" -> Citas raw: {rec['citations_raw']} | Citas final: {rec['citations_final']}")

    finished_utc = datetime.now(timezone.utc).isoformat()

    # Guardar traces.json
    traces_file = out_dir / ('test_traces.json' if args.test_only else 'traces.json')
    traces_file.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\nGuardado: {traces_file}")

    if not args.test_only:
        write_traces_csv(out_dir, records)
        print(f"Guardado: {out_dir / 'traces.csv'}")

        corrida_id = f"corrida_t11_baseline_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        build_manifest(
            out_dir=out_dir,
            evaluated_ids=target_ids,
            mode=args.mode,
            provider=args.provider,
            model=args.model,
            model_digest=args.model_digest,
            top_k=args.top_k,
            documental=True,
            seed=args.seed,
            started_utc=started_utc,
            finished_utc=finished_utc,
        )
        print(f"Guardado: {out_dir / 'manifest.json'}")

        prepare_t12_blind_materials(
            out_dir=out_dir,
            records=records,
            corrida_id=corrida_id
        )
        print(f"Guardado: {out_dir / 't12_material_ciego.json'}")
        print(f"Guardado: {out_dir / 't12_evaluacion_ciega.csv'}")

    print("\nEjecución finalizada con éxito.")


if __name__ == '__main__':
    main()
