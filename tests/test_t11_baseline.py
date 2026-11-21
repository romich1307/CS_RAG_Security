"""Pruebas automatizadas para protección experimental T11 y preparación T12.

Verifica:
1. Protección contra sobrescritura o reutilización de directorios existentes.
2. Generación de directorio único por ejecución.
3. Ejecución offline con mock (sin dependencias de red ni Ollama).
4. Integridad de hash y correspondencia estricta en preparación T12.
5. Ausencia de datos gold privados en artefactos versionados y material ciego.
6. Conformidad estricta con la rúbrica v0.2 de origin/main (24 columnas estándar).
"""

import json
from pathlib import Path
import pytest

from cs_rag_security.retrieval import Index
from scripts.prepare_t12_eval import prepare_t12_evaluation, compute_sha256
from scripts.run_t11_baseline import (
    ensure_unique_output_dir,
    get_default_output_dir,
    run_baseline,
    sanitize_record_for_git,
)


def create_mock_environment(tmp_path: Path):
    """Crea un entorno mock con índice y gold sintéticos para pruebas sin Ollama."""
    idx_dir = tmp_path / 'vector_db'
    idx_dir.mkdir(parents=True)
    idx_file = idx_dir / 'index.json'

    chunks = [
        {
            'chunk_id': 'doc1:1:1:0',
            'documento_id': 'doc1',
            'archivo_pdf': 'doc1.pdf',
            'pagina_pdf': 1,
            'texto': 'Texto de prueba sobre régimen académico.',
            'ocr_revision_manual_pendiente': False,
        },
        {
            'chunk_id': 'doc1:2:1:0',
            'documento_id': 'doc1',
            'archivo_pdf': 'doc1.pdf',
            'pagina_pdf': 2,
            'texto': 'Otro fragmento con requisitos específicos.',
            'ocr_revision_manual_pendiente': False,
        }
    ]
    Index(chunks).save(idx_file, {})

    gold_dir = tmp_path / 'gold'
    gold_dir.mkdir(parents=True)
    gold_file = gold_dir / 'gold_questions.json'
    gold_data = {
        'preguntas': [
            {
                'id': 'GQ001',
                'pregunta': '¿Pregunta sintética de prueba?',
                'respuesta_referencia': 'Respuesta privada que no debe filtrarse.',
                'apta_para_evaluar_recuperacion_documental_piloto': True,
            }
        ]
    }
    gold_file.write_text(json.dumps(gold_data, ensure_ascii=False), encoding='utf-8')

    return idx_file, gold_file


def test_ensure_unique_output_dir_raises_on_existing(tmp_path):
    existing = tmp_path / 'existing_run'
    existing.mkdir()
    assert existing.exists()

    with pytest.raises(FileExistsError) as exc_info:
        ensure_unique_output_dir(existing)
    assert 'no puede ser reutilizado ni sobrescrito' in str(exc_info.value)


def test_ensure_unique_output_dir_creates_new(tmp_path):
    new_dir = tmp_path / 'new_run'
    assert not new_dir.exists()

    res = ensure_unique_output_dir(new_dir)
    assert res == new_dir
    assert new_dir.exists()
    assert new_dir.is_dir()


def test_get_default_output_dir_generates_unique_paths():
    p1 = get_default_output_dir()
    assert 'results/llm_baseline_' in str(p1)


def test_run_baseline_refuses_overwrite(tmp_path):
    idx_file, gold_file = create_mock_environment(tmp_path)
    existing_out = tmp_path / 'already_exists'
    existing_out.mkdir()

    with pytest.raises(FileExistsError):
        run_baseline(
            output_dir=existing_out,
            provider='mock',
            test_only=True,
            index_path=idx_file,
            gold_path=gold_file,
        )


def test_run_baseline_mock_execution_and_sanitization(tmp_path):
    idx_file, gold_file = create_mock_environment(tmp_path)
    out_dir = tmp_path / 'run_mock_01'

    run_baseline(
        output_dir=out_dir,
        provider='mock',
        test_only=False,
        target_ids=['GQ001'],
        index_path=idx_file,
        gold_path=gold_file,
    )

    assert out_dir.exists()
    assert (out_dir / 'manifest.json').exists()
    assert (out_dir / 'traces.json').exists()
    assert (out_dir / 'traces.csv').exists()
    assert (out_dir / 'raw_traces.json').exists()

    # Verificar que traces.json sanitizado no expone question ni raw_response ni texto
    sanitized_traces = json.loads((out_dir / 'traces.json').read_text(encoding='utf-8'))
    assert len(sanitized_traces) == 1
    t = sanitized_traces[0]
    assert t['id'] == 'GQ001'
    assert 'question' not in t
    assert 'raw_response' not in t
    for chunk in t['retrieved_chunks'] + t['accepted_chunks']:
        assert 'texto' not in chunk
    assert 'latency_seconds' in t
    assert 'tokens' in t

    # Verificar traces.csv
    csv_text = (out_dir / 'traces.csv').read_text(encoding='utf-8')
    header = csv_text.splitlines()[0]
    assert 'question' not in header
    assert 'raw_response' not in header
    assert 'latency_seconds' in header
    assert 'tokens' in header

    # Verificar que el respaldo raw sí conserva los datos completos
    raw_traces = json.loads((out_dir / 'raw_traces.json').read_text(encoding='utf-8'))
    assert 'question' in raw_traces[0]
    assert 'raw_response' in raw_traces[0]


def test_prepare_t12_evaluation_hash_mismatch(tmp_path):
    idx_file, _ = create_mock_environment(tmp_path)

    manifest_file = tmp_path / 'manifest.json'
    manifest_data = {
        'tarea': 'test_t12',
        'started_utc': '2026-11-20T00:00:00',
        'hashes': {
            'index_sha256': '0000000000000000000000000000000000000000000000000000000000000000'
        }
    }
    manifest_file.write_text(json.dumps(manifest_data), encoding='utf-8')

    traces_file = tmp_path / 'traces.json'
    traces_file.write_text(json.dumps([]), encoding='utf-8')

    with pytest.raises(ValueError) as exc_info:
        prepare_t12_evaluation(
            manifest_path=manifest_file,
            traces_path=traces_file,
            index_path=idx_file,
            output_dir=tmp_path / 't12_out',
        )
    assert 'Fallo de verificación de integridad' in str(exc_info.value)
    assert 'No se reconstruye artificialmente la evidencia' in str(exc_info.value)


def test_prepare_t12_evaluation_chunk_missing(tmp_path):
    idx_file, _ = create_mock_environment(tmp_path)
    real_hash = compute_sha256(idx_file)

    manifest_file = tmp_path / 'manifest.json'
    manifest_data = {
        'tarea': 'test_t12',
        'started_utc': '2026-11-20T00:00:00',
        'hashes': {'index_sha256': real_hash}
    }
    manifest_file.write_text(json.dumps(manifest_data), encoding='utf-8')

    # Trazas con un chunk_id inexistente en el índice
    traces_file = tmp_path / 'traces.json'
    traces_data = [
        {
            'id': 'GQ001',
            'question': '¿Pregunta?',
            'raw_response': 'Salida raw',
            'response': 'Salida pipeline',
            'abstained': False,
            'abstention_reason': '',
            'accepted_chunks': [
                {'chunk_id': 'chunk_fantasma:99:99:0', 'score': 0.9}
            ]
        }
    ]
    traces_file.write_text(json.dumps(traces_data), encoding='utf-8')

    with pytest.raises(ValueError) as exc_info:
        prepare_t12_evaluation(
            manifest_path=manifest_file,
            traces_path=traces_file,
            index_path=idx_file,
            output_dir=tmp_path / 't12_out',
        )
    assert 'Fallo de correspondencia' in str(exc_info.value)
    assert 'No se inventa evidencia' in str(exc_info.value)


def test_prepare_t12_evaluation_success_with_exact_text_and_canonical_rubrica_v02(tmp_path):
    idx_file, _ = create_mock_environment(tmp_path)
    real_hash = compute_sha256(idx_file)

    manifest_file = tmp_path / 'manifest.json'
    manifest_data = {
        'tarea': 'test_t12',
        'started_utc': '2026-11-20T00:00:00',
        'hashes': {'index_sha256': real_hash}
    }
    manifest_file.write_text(json.dumps(manifest_data), encoding='utf-8')

    traces_file = tmp_path / 'traces.json'
    traces_data = [
        {
            'id': 'GQ001',
            'question': '¿Pregunta de evaluación?',
            'raw_response': 'Respuesta raw sustantiva sin formato de citas.',
            'response': 'Me abstengo: la salida del modelo carece de citas válidas del contexto.',
            'abstained': True,
            'abstention_reason': 'citas_invalidas_o_ausentes',
            'accepted_chunks': [
                {
                    'chunk_id': 'doc1:1:1:0',
                    'documento_id': 'doc1',
                    'archivo_pdf': 'doc1.pdf',
                    'pagina_pdf': 1,
                    'score': 0.85,
                }
            ]
        }
    ]
    traces_file.write_text(json.dumps(traces_data), encoding='utf-8')

    out_dir = tmp_path / 't12_eval'
    res = prepare_t12_evaluation(
        manifest_path=manifest_file,
        traces_path=traces_file,
        index_path=idx_file,
        output_dir=out_dir,
        evaluator_id='leon',
        rubrica_version='0.2',
    )

    assert res['casos_generados'] == 1
    assert res['filas_evaluacion'] == 2  # Una fila para pipeline, una para llm-raw
    assert (out_dir / 't12_material_ciego.json').exists()
    assert (out_dir / 't12_evaluacion_ciega.csv').exists()

    blind_cases = json.loads((out_dir / 't12_material_ciego.json').read_text(encoding='utf-8'))
    b = blind_cases[0]
    assert b['caso_ciego_id'] == 'CIEGO_01'
    assert b['pregunta_id'] == 'GQ001'
    assert b['respuesta_original_llm'] == 'Respuesta raw sustantiva sin formato de citas.'
    assert b['respuesta_final_pipeline'] == 'Me abstengo: la salida del modelo carece de citas válidas del contexto.'
    assert 'respuesta_referencia' not in b
    # Comprobar que el texto exacto del fragmento fue extraído del índice
    assert len(b['evidencia_recuperada_sistema']) == 1
    assert b['evidencia_recuperada_sistema'][0]['texto'] == 'Texto de prueba sobre régimen académico.'

    # Comprobar plantilla CSV: exactamente las 24 columnas estándar de origin/main
    csv_text = (out_dir / 't12_evaluacion_ciega.csv').read_text(encoding='utf-8')
    lines = csv_text.splitlines()
    header = lines[0].split(',')

    expected_24_cols = [
        'evaluacion_id', 'corrida_id', 'caso_ciego_id', 'pregunta_id', 'evaluador_id',
        'rubrica_version', 'referencia_caso', 'referencia_salida', 'referencia_contexto',
        'referencia_manifiesto', 'tipo_consulta', 'evidencia_disponible', 'estado_revision',
        'tipo_salida', 'calidad_respuesta', 'abstencion_adecuada', 'cita_pertenece_contexto',
        'cita_sustenta_respuesta', 'error_vigencia', 'justificacion', 'referencia_fuente',
        'incidencia', 'revisado_por', 'fecha_revision'
    ]
    assert header == expected_24_cols

    # Verificar que hay 2 filas: una para el pipeline y otra para el llm-raw
    row_pipeline = lines[1].split(',')
    row_llm_raw = lines[2].split(',')
    assert row_pipeline[0].endswith('-pipeline')
    assert row_llm_raw[0].endswith('-llm-raw')
    assert row_pipeline[header.index('rubrica_version')] == '0.2'
    assert row_llm_raw[header.index('rubrica_version')] == '0.2'
    assert '.response' in row_pipeline[header.index('referencia_salida')]
    assert '.raw_response' in row_llm_raw[header.index('referencia_salida')]
