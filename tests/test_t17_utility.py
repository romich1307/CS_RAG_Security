import csv
import hashlib
import json

import pytest

from cs_rag_security.defenses import MODES
from cs_rag_security.evaluation.audit_experiment import audit_run
from cs_rag_security.evaluation.quality import load_traces_dict
from scripts import run_t17_utility


@pytest.fixture
def utility_inputs(tmp_path, monkeypatch):
    def write_fixture(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value), encoding='utf-8')
        return path

    index = write_fixture('index.json', {
        'method': run_t17_utility.Index.method,
        'chunks': [{
            'chunk_id': 'C1',
            'documento_id': 'D1',
            'archivo_pdf': 'Reglamento-ficticio.pdf',
            'pagina_pdf': 2,
            'texto': 'La inscripción del laboratorio se registra en la plataforma académica.',
            'ocr_revision_manual_pendiente': False,
        }],
    })
    gold = write_fixture('gold.json', {
        'preguntas': [
            {'id': 'Q1', 'pregunta': '¿Dónde se registra la inscripción del laboratorio?'},
            {'id': 'Q2', 'pregunta': '¿Qué plataforma registra la inscripción?'},
        ],
    })
    baseline = write_fixture('baseline.json', {
        'hashes': {
            'index_sha256': hashlib.sha256(index.read_bytes()).hexdigest(),
            'gold_sha256': hashlib.sha256(gold.read_bytes()).hexdigest(),
        },
        'preguntas_evaluadas': ['Q1', 'Q2'],
        'modelo': 'qwen2.5:3b',
    })
    monkeypatch.setattr(run_t17_utility, 'BASELINE', baseline)
    monkeypatch.setattr(run_t17_utility, 'PRIVATE_RESULTS', tmp_path / 'llm_abc_local')
    return index, gold


def test_utility_run_pairs_rankings_and_separates_private_text(utility_inputs, monkeypatch):
    searches = []
    original_search = run_t17_utility.Index.search

    def count_search(index, question, k):
        searches.append(question)
        return original_search(index, question, k)

    monkeypatch.setattr(run_t17_utility.Index, 'search', count_search)
    out, manifest = run_t17_utility.run_utility(*utility_inputs, 't17_fixture', 'mock')
    public = json.loads((out / 'traces.json').read_text(encoding='utf-8'))
    private = json.loads((out / 'privado/raw_traces.json').read_text(encoding='utf-8'))

    assert len(searches) == 2
    assert len(public) == len(private) == manifest['total_trazas_esperadas'] == 6
    assert len({(row['case_id'], row['condition']) for row in public}) == 6
    assert all(row['retrieved_ids'] == ['C1'] for row in public)
    assert all('question' not in row and 'raw_response' not in row for row in public)
    assert all('texto' not in hit for row in public for hit in row['accepted_chunks'])
    assert private[0]['question'] == searches[0]
    assert 'plataforma académica' in private[0]['raw_response']
    with (out / 'traces.csv').open(encoding='utf-8', newline='') as stream:
        assert len(list(csv.DictReader(stream))) == 6

    for mode in MODES:
        by_mode = manifest['extra']['latencias_segundos'][mode]
        assert by_mode['pipeline_sin_recuperacion']['observaciones_validas'] == 2
        assert all(by_mode['pipeline_sin_recuperacion'][key] is not None
                   for key in ('media', 'mediana', 'percentil_95'))
        assert by_mode['generacion']['observaciones_validas'] == 0
        assert by_mode['generacion']['mediana'] is None

    traces_index = load_traces_dict(out / 'traces.json')
    assert traces_index.resolve('t17_fixture', 'Q1', MODES[0])['provider'] == 'mock'
    assert audit_run(out).paired_coverage['strictly_paired'] is True


def test_existing_utility_run_is_preserved(utility_inputs):
    run_id = 't17_existing'
    out, _ = run_t17_utility.run_utility(*utility_inputs, run_id, 'mock')
    before = {path.relative_to(out): path.read_bytes() for path in out.rglob('*') if path.is_file()}

    with pytest.raises(FileExistsError, match='ya existe'):
        run_t17_utility.run_utility(*utility_inputs, run_id, 'mock')

    assert {path.relative_to(out): path.read_bytes() for path in out.rglob('*') if path.is_file()} == before
