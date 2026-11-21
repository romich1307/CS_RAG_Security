"""Script para preparar localmente el material de evaluación humana T12.

Condición experimental evaluada: Baseline T11 Ollama (qwen2.5:3b).
Rúbrica: Versión 0.2 (criterios acordados en T10 de origin/main).
Aislamiento: Excluido de Git. No contiene respuestas esperadas ni referencias gold.
Integridad: Verifica el hash SHA-256 del índice y correspondencia de chunks.
"""

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def prepare_t12_evaluation(
    manifest_path: Path,
    traces_path: Path,
    index_path: Path,
    output_dir: Path,
    evaluator_id: str = 'leon',
    rubrica_version: str = '0.2',
) -> dict:
    manifest_path = Path(manifest_path)
    traces_path = Path(traces_path)
    index_path = Path(index_path)
    output_dir = Path(output_dir)

    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifiesto no encontrado: {manifest_path}")
    if not traces_path.exists():
        raise FileNotFoundError(f"Archivo de trazas no encontrado: {traces_path}")
    if not index_path.exists():
        raise FileNotFoundError(f"Índice vectorial no encontrado: {index_path}")

    # 1. Cargar manifiesto y verificar hash del índice
    with manifest_path.open('r', encoding='utf-8') as f:
        manifest = json.load(f)

    expected_index_sha256 = manifest.get('hashes', {}).get('index_sha256')
    actual_index_sha256 = compute_sha256(index_path)

    if expected_index_sha256 != actual_index_sha256:
        raise ValueError(
            f"Fallo de verificación de integridad: el hash SHA-256 del índice ({actual_index_sha256}) "
            f"no coincide con el registrado en el manifiesto ({expected_index_sha256}). "
            f"No se reconstruye artificialmente la evidencia."
        )

    # 2. Cargar índice y construir diccionario de fragmentos
    with index_path.open('r', encoding='utf-8') as f:
        index_data = json.load(f)

    chunks_by_id = {c['chunk_id']: c for c in index_data.get('chunks', [])}

    # 3. Cargar trazas originales
    with traces_path.open('r', encoding='utf-8') as f:
        traces = json.load(f)

    corrida_id = f"corrida_{manifest.get('tarea', 't11_baseline')}_{manifest.get('started_utc', '').replace(':', '').replace('-', '')[:15]}"

    t12_cases = []
    csv_rows = []

    for idx, r in enumerate(traces, start=1):
        caso_ciego_id = f'CIEGO_{idx:02d}'
        q_id = r['id']

        # Verificar correspondencia estricta de chunks
        accepted_chunks = r.get('accepted_chunks', [])
        evidencia_recuperada = []

        for c in accepted_chunks:
            cid = c['chunk_id']
            if cid not in chunks_by_id:
                raise ValueError(
                    f"Fallo de correspondencia: el chunk_id '{cid}' de la pregunta '{q_id}' "
                    f"no se encuentra en el índice verificado. "
                    f"No se inventa evidencia."
                )
            chunk_source = chunks_by_id[cid]
            evidencia_recuperada.append({
                'chunk_id': cid,
                'documento_id': c.get('documento_id', chunk_source.get('documento_id')),
                'archivo_pdf': c.get('archivo_pdf', chunk_source.get('archivo_pdf')),
                'pagina_pdf': c.get('pagina_pdf', chunk_source.get('pagina_pdf')),
                'score': c.get('score'),
                'texto': chunk_source.get('texto', ''),
            })

        # Caso ciego con separación estricta LLM raw vs pipeline
        # NOTA: NUNCA se incluye respuesta_referencia ni fuentes esperadas del gold
        t12_cases.append({
            'caso_ciego_id': caso_ciego_id,
            'pregunta_id': q_id,
            'pregunta': r['question'],
            'tipo_consulta': 'documental',
            'respuesta_final_pipeline': r['response'],
            'respuesta_original_llm': r['raw_response'],
            'abstained': r.get('abstained', False),
            'motivo_abstencion': r.get('abstention_reason', ''),
            'evidencia_recuperada_sistema': evidencia_recuperada,
        })

        # Filas CSV según rúbrica v0.2 canónica de origin/main (24 columnas estándar)
        # Se genera una fila para la respuesta validada del pipeline y otra para la respuesta original cruda del LLM
        csv_rows.append({
            'evaluacion_id': f'EVAL-T12-{idx:03d}-pipeline',
            'corrida_id': corrida_id,
            'caso_ciego_id': caso_ciego_id,
            'pregunta_id': q_id,
            'evaluador_id': evaluator_id,
            'rubrica_version': rubrica_version,
            'referencia_caso': f"{output_dir.name}/t12_material_ciego.json#{caso_ciego_id}",
            'referencia_salida': f"results/llm_baseline_local/traces.json#{q_id}.response",
            'referencia_contexto': f"results/llm_baseline_local/traces.json#{q_id}.accepted_chunks",
            'referencia_manifiesto': "results/llm_baseline/manifest.json",
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
            'referencia_fuente': '',
            'incidencia': '',
            'revisado_por': '',
            'fecha_revision': '',
        })

        csv_rows.append({
            'evaluacion_id': f'EVAL-T12-{idx:03d}-llm-raw',
            'corrida_id': corrida_id,
            'caso_ciego_id': caso_ciego_id,
            'pregunta_id': q_id,
            'evaluador_id': evaluator_id,
            'rubrica_version': rubrica_version,
            'referencia_caso': f"{output_dir.name}/t12_material_ciego.json#{caso_ciego_id}",
            'referencia_salida': f"results/llm_baseline_local/traces.json#{q_id}.raw_response",
            'referencia_contexto': f"results/llm_baseline_local/traces.json#{q_id}.accepted_chunks",
            'referencia_manifiesto': "results/llm_baseline/manifest.json",
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
            'referencia_fuente': '',
            'incidencia': '',
            'revisado_por': '',
            'fecha_revision': '',
        })

    # Reservar un directorio nuevo para preservar las anotaciones de sesiones anteriores.
    output_dir.mkdir(parents=True, exist_ok=False)
    json_path = output_dir / 't12_material_ciego.json'
    csv_path = output_dir / 't12_evaluacion_ciega.csv'

    json_path.write_text(json.dumps(t12_cases, ensure_ascii=False, indent=2), encoding='utf-8')

    # 24 columnas exactas de plantilla_anotacion_qa.csv en origin/main
    fieldnames = [
        'evaluacion_id', 'corrida_id', 'caso_ciego_id', 'pregunta_id', 'evaluador_id',
        'rubrica_version', 'referencia_caso', 'referencia_salida', 'referencia_contexto',
        'referencia_manifiesto', 'tipo_consulta', 'evidencia_disponible', 'estado_revision',
        'tipo_salida', 'calidad_respuesta', 'abstencion_adecuada', 'cita_pertenece_contexto',
        'cita_sustenta_respuesta', 'error_vigencia', 'justificacion', 'referencia_fuente',
        'incidencia', 'revisado_por', 'fecha_revision'
    ]

    with csv_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

    return {
        'casos_generados': len(t12_cases),
        'filas_evaluacion': len(csv_rows),
        'index_sha256': actual_index_sha256,
        'json_path': str(json_path),
        'csv_path': str(csv_path),
        'output_dir': str(output_dir),
    }


def main():
    parser = argparse.ArgumentParser(description='Preparación local de material de evaluación T12')
    parser.add_argument('--manifest', default='results/llm_baseline/manifest.json', help='Ruta a manifest.json')
    parser.add_argument('--traces', default='results/llm_baseline_local/traces.json', help='Ruta a traces.json con trazas originales')
    parser.add_argument('--index', default='data/vector_db/index.json', help='Ruta al índice vectorial')
    parser.add_argument('--output-dir', default='results/t12_evaluacion',
                        help='Directorio local nuevo para la sesión de evaluación')
    parser.add_argument('--evaluator', default='leon', help='ID del evaluador')
    parser.add_argument('--rubrica-version', default='0.2', help='Versión de la rúbrica')
    args = parser.parse_args()

    try:
        res = prepare_t12_evaluation(
            manifest_path=Path(args.manifest),
            traces_path=Path(args.traces),
            index_path=Path(args.index),
            output_dir=Path(args.output_dir),
            evaluator_id=args.evaluator,
            rubrica_version=args.rubrica_version,
        )
        print("=== Material de Evaluación T12 preparado con éxito ===")
        print(f"Directorio de salida: {res['output_dir']}")
        print(f"Casos ciegos: {res['casos_generados']}")
        print(f"Filas de evaluación (24 columnas origin/main): {res['filas_evaluacion']}")
        print(f"Hash del índice verificado: {res['index_sha256']}")
        print(f"JSON ciego: {res['json_path']}")
        print(f"CSV de evaluación (rúbrica {args.rubrica_version}): {res['csv_path']}")
    except Exception as e:
        print(f"Error preparando material T12: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
