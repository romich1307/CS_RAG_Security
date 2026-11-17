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
    with pytest.raises(FileExistsError):
        run(args)
