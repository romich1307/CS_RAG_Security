import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

np = pytest.importorskip('numpy')
from cs_rag_security.retrieval import semantico
from scripts import retrieval_benchmark as benchmark


class FakeEncoder:
    def __init__(self, directory, threads=4):
        self.directory = Path(directory)
        self.np = np
        self.manifest_sha256 = 'fixture-model'
        self.max_length = 128

    def token_lengths(self, texts):
        return [len(text.split()) for text in texts]

    def encode(self, texts):
        return np.asarray([[0.0, 1.0] if text == 'segundo' else [1.0, 0.0] for text in texts], dtype=np.float32)


def test_local_store_roundtrip_metadata_ties_and_integrity(tmp_path, monkeypatch):
    monkeypatch.setattr(semantico, 'LocalEncoder', FakeEncoder)
    records = [{'chunk_id': 'a', 'texto': 'primero', 'pagina_pdf': 1},
               {'chunk_id': 'b', 'texto': 'segundo', 'pagina_pdf': 2},
               {'chunk_id': 'c', 'texto': 'primero', 'pagina_pdf': 3}]
    index = semantico.SemanticIndex(records, tmp_path)
    assert index.search('segundo', 1) == [{**records[1], 'score': 1.0}]
    assert [hit['chunk_id'] for hit in index.search('primero', 3)] == ['a', 'c', 'b']
    assert index.search('   ') == []
    with pytest.raises(ValueError):
        index.search('primero', 0)
    saved = tmp_path / 'index'
    index.save(saved)
    loaded = semantico.SemanticIndex.load(saved, tmp_path)
    assert loaded.search('segundo', 3) == index.search('segundo', 3)
    with pytest.raises(FileExistsError):
        index.save(saved)
    (saved / 'vectors.npy').write_bytes(b'alterado')
    with pytest.raises(ValueError, match='alterado'):
        semantico.SemanticIndex.load(saved, tmp_path)


def test_masked_pooling_ignores_padding():
    encoder = semantico.LocalEncoder.__new__(semantico.LocalEncoder)
    encoder.np = np
    record = SimpleNamespace(ids=[1, 2, 0], attention_mask=[1, 1, 0], type_ids=[0, 0, 0])
    encoder.tokenizer = SimpleNamespace(encode_batch=lambda texts: [record] * len(texts))
    token_vectors = np.asarray([[[2., 0.], [0., 2.], [100., 100.]]], dtype=np.float32)
    encoder.session = SimpleNamespace(run=lambda names, inputs: [np.repeat(token_vectors, len(inputs['input_ids']), axis=0)])
    encoder.input_names = {'input_ids', 'attention_mask'}
    actual = encoder.encode(['texto'])
    np.testing.assert_allclose(actual, [[2**-0.5, 2**-0.5]], rtol=1e-6)


def test_gold_separation_duplicate_ids_and_invalid_primary(tmp_path, monkeypatch):
    page = {'documento_id': 'demo', 'pagina_pdf': 1, 'texto': 'Documento independiente del gold'}
    folder = tmp_path / '03_Preguntas_Respuestas'
    folder.mkdir()
    question = {'id': 'Q1', 'pregunta': 'Consulta', 'respuesta_referencia': 'NO_INDEXAR_GOLD',
                'apta_para_evaluar_recuperacion_documental_piloto': True,
                'fuentes': [{'documento_id': 'demo', 'pagina_pdf': 1}]}
    path = folder / 'gold_questions.json'
    path.write_text(json.dumps({'preguntas': [question]}), encoding='utf-8')
    monkeypatch.setattr(benchmark, 'audit', lambda root: {'fixture': True})
    monkeypatch.setattr(benchmark, 'load_pages', lambda root: [page])
    pages, questions, _, _ = benchmark.load_inputs(tmp_path, {'primary_question_ids': ['Q1']})
    assert 'NO_INDEXAR_GOLD' not in str(pages) + str(questions)
    with pytest.raises(ValueError, match='primaria'):
        benchmark.load_inputs(tmp_path, {'primary_question_ids': ['Q2']})
    path.write_text(json.dumps({'preguntas': [question, question]}), encoding='utf-8')
    with pytest.raises(ValueError, match='duplicado'):
        benchmark.load_inputs(tmp_path, {'primary_question_ids': ['Q1']})


def test_metrics_keep_unique_question_and_latency_denominators():
    rows = [{'question_id': 'Q1', 'method': 'demo', 'hit_at_1': False, 'hit_at_3': True, 'hit_at_5': True}]
    timing = [{'question_id': 'Q1', 'method': 'demo', 'seconds': value} for value in (.1, .2, .3)]
    result = benchmark.summarize(rows, timing, ['Q1'], ['demo'])['methods']['demo']
    assert result['hit_at_3'] == {'numerator': 1, 'denominator': 1, 'value': 1.0}
    assert result['latency']['denominator'] == 3
    assert result['latency']['p95_linear'] == pytest.approx(.29)


def test_missing_model_and_existing_output_fail_early(tmp_path):
    with pytest.raises(ValueError, match='modelo local'):
        semantico.LocalEncoder(tmp_path / 'missing')
    with pytest.raises(FileExistsError):
        benchmark.main(['--model-directory', str(tmp_path), '--index-directory', str(tmp_path / 'i'),
                        '--output', str(tmp_path)])


@pytest.mark.skipif(not os.environ.get('RAG_EMBEDDING_MODEL'), reason='Modelo local opcional no configurado')
def test_real_local_model_persistence(tmp_path):
    records = [{'chunk_id': 'a', 'texto': 'Evaluación académica del estudiante', 'pagina_pdf': 1},
               {'chunk_id': 'b', 'texto': 'Resultados deportivos de fútbol', 'pagina_pdf': 2}]
    model = os.environ['RAG_EMBEDDING_MODEL']
    index = semantico.SemanticIndex(records, model)
    assert index.vectors.shape == (2, 384)
    np.testing.assert_allclose(np.linalg.norm(index.vectors, axis=1), [1, 1], rtol=1e-5)
    index.save(tmp_path / 'stored')
    loaded = semantico.SemanticIndex.load(tmp_path / 'stored', model)
    assert loaded.search(records[0]['texto'], 1)[0]['chunk_id'] == 'a'
    np.testing.assert_array_equal(loaded.vectors, index.vectors)
