import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from cs_rag_security.evaluation import run
from cs_rag_security.retrieval import Index
from cs_rag_security.defenses import MODES


def test_paired_evaluation_and_mock_not_asr(tmp_path, monkeypatch):
    import cs_rag_security.evaluation as ev
    index = tmp_path / 'index.json'
    Index([{'documento_id': 'demo', 'archivo_pdf': 'demo.pdf', 'pagina_pdf': 1,
            'texto': 'Evaluación académica', 'chunk_id': 'demo:1',
            'ocr_revision_manual_pendiente': False}]).save(index, {})
    root = tmp_path / 'corpus'
    (root / '03_Preguntas_Respuestas').mkdir(parents=True)
    (root / '03_Preguntas_Respuestas/gold_questions.json').write_text(json.dumps({'preguntas': [
        {'id': 'q1', 'pregunta': 'Evaluación académica', 'respuesta_referencia': 'Referencia',
         'apta_para_evaluar_recuperacion_documental_piloto': True,
         'fuentes': [{'documento_id': 'demo', 'pagina_pdf': 1}]}]}))
    monkeypatch.setattr(ev, 'audit', lambda root: {'fixture': True})
    args = SimpleNamespace(index=str(index), corpus=str(root), output=str(tmp_path / 'run'), top_k=1, provider='mock')
    metrics = run(args)
    rows = json.loads((Path(args.output) / 'traces.json').read_text())
    for mode in MODES:
        assert metrics[mode]['asr_all']['value'] is None
        assert metrics[mode]['answer_exact_pilot']['value'] is None
        assert metrics[mode]['provider'] == 'mock'
    for row in rows[::3]:
        paired = [r for r in rows if (r['kind'], r['id']) == (row['kind'], row['id'])]
        assert len({r['retrieved_ids'] for r in paired}) == 1
    # Verifica que las trazas conservan generation_metadata para mock sin inventar datos ausentes
    for row in rows:
        assert 'generation_metadata' in row
        if row['generation_metadata'] is not None:
            assert row['generation_metadata']['provider'] == 'mock'
            assert row['generation_metadata']['model'] == 'mock_extractivo_v1'
            assert row['generation_metadata']['parameters'] == {'seed': 42}
            assert 'system_fingerprint' not in row['generation_metadata']
            assert 'usage' not in row['generation_metadata']
            assert 'tokens' not in row['generation_metadata']
    with pytest.raises(FileExistsError):
        run(args)


def test_evaluate_traces_preserve_generation_metadata_api(tmp_path, monkeypatch):
    import csv
    import cs_rag_security.evaluation as ev
    import cs_rag_security.pipeline as pipe

    index = tmp_path / 'index.json'
    Index([{'documento_id': 'demo', 'archivo_pdf': 'demo.pdf', 'pagina_pdf': 1,
            'texto': 'Evaluación académica', 'chunk_id': 'demo:1',
            'ocr_revision_manual_pendiente': False}]).save(index, {})
    root = tmp_path / 'corpus'
    (root / '03_Preguntas_Respuestas').mkdir(parents=True)
    (root / '03_Preguntas_Respuestas/gold_questions.json').write_text(json.dumps({'preguntas': [
        {'id': 'q1', 'pregunta': 'Evaluación académica', 'respuesta_referencia': 'Referencia',
         'apta_para_evaluar_recuperacion_documental_piloto': True,
         'fuentes': [{'documento_id': 'demo', 'pagina_pdf': 1}]}]}))
    monkeypatch.setattr(ev, 'audit', lambda root: {'fixture': True})

    # Mock de generación de API con metadatos completos reportados
    def mock_generate_api(messages, hits, provider='api', seed=42, return_metadata=False):
        meta = {
            'provider': 'api',
            'model': 'gpt-4o-mini-2024-07-18',
            'parameters': {'temperature': 0, 'seed': seed},
            'latency_seconds': 0.123,
            'latency': 0.123,
            'system_fingerprint': 'fp_prod_987',
            'usage': {'prompt_tokens': 80, 'completion_tokens': 25, 'total_tokens': 105},
            'tokens': {'prompt_tokens': 80, 'completion_tokens': 25, 'total_tokens': 105}
        }
        text = 'Respuesta válida con [demo.pdf p. 1] y [SINTETICO_NO_OFICIAL.pdf p. 1].'
        return {'text': text, 'metadata': meta} if return_metadata else text

    monkeypatch.setattr(pipe, 'generate', mock_generate_api)

    args = SimpleNamespace(index=str(index), corpus=str(root), output=str(tmp_path / 'run_api'), top_k=1, provider='api')
    run(args)

    rows = json.loads((Path(args.output) / 'traces.json').read_text(encoding='utf-8'))
    assert len(rows) > 0
    for row in rows:
        assert 'generation_metadata' in row
        meta = row['generation_metadata']
        assert meta is not None
        assert meta['model'] == 'gpt-4o-mini-2024-07-18'
        assert meta['parameters'] == {'temperature': 0, 'seed': 42}
        assert meta['latency_seconds'] == 0.123
        assert meta['system_fingerprint'] == 'fp_prod_987'
        assert meta['tokens'] == {'prompt_tokens': 80, 'completion_tokens': 25, 'total_tokens': 105}
        assert meta['usage'] == {'prompt_tokens': 80, 'completion_tokens': 25, 'total_tokens': 105}

    # Verificar que traces.csv también contiene generation_metadata
    with (Path(args.output) / 'traces.csv').open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        assert 'generation_metadata' in reader.fieldnames
        csv_rows = list(reader)
        assert len(csv_rows) == len(rows)
        for cr in csv_rows:
            parsed_meta = json.loads(cr['generation_metadata'])
            assert parsed_meta['model'] == 'gpt-4o-mini-2024-07-18'
            assert parsed_meta['system_fingerprint'] == 'fp_prod_987'


def test_evaluate_traces_record_missing_data_without_inventing(tmp_path, monkeypatch):
    import cs_rag_security.evaluation as ev
    import cs_rag_security.pipeline as pipe

    index = tmp_path / 'index.json'
    Index([{'documento_id': 'demo', 'archivo_pdf': 'demo.pdf', 'pagina_pdf': 1,
            'texto': 'Evaluación académica', 'chunk_id': 'demo:1',
            'ocr_revision_manual_pendiente': False}]).save(index, {})
    root = tmp_path / 'corpus'
    (root / '03_Preguntas_Respuestas').mkdir(parents=True)
    (root / '03_Preguntas_Respuestas/gold_questions.json').write_text(json.dumps({'preguntas': [
        {'id': 'q1', 'pregunta': 'Evaluación académica', 'respuesta_referencia': 'Referencia',
         'apta_para_evaluar_recuperacion_documental_piloto': True,
         'fuentes': [{'documento_id': 'demo', 'pagina_pdf': 1}]}]}))
    monkeypatch.setattr(ev, 'audit', lambda root: {'fixture': True})

    # Simular respuesta API que omite system_fingerprint y usage
    def mock_generate_api_omitted(messages, hits, provider='api', seed=42, return_metadata=False):
        meta = {
            'provider': 'api',
            'model': 'gpt-4o-mini',
            'parameters': {'temperature': 0, 'seed': seed},
            'latency_seconds': 0.05,
            'latency': 0.05
        }
        text = 'Respuesta [demo.pdf p. 1].'
        return {'text': text, 'metadata': meta} if return_metadata else text

    monkeypatch.setattr(pipe, 'generate', mock_generate_api_omitted)

    args = SimpleNamespace(index=str(index), corpus=str(root), output=str(tmp_path / 'run_missing'), top_k=1, provider='api')
    run(args)

    rows = json.loads((Path(args.output) / 'traces.json').read_text(encoding='utf-8'))
    for row in rows:
        meta = row['generation_metadata']
        assert meta is not None
        assert meta['model'] == 'gpt-4o-mini'
        assert 'system_fingerprint' not in meta
        assert 'tokens' not in meta
        assert 'usage' not in meta
