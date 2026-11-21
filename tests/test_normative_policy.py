import json
from hashlib import sha256

import pytest

from cs_rag_security.ingestion import chunks, load_pages
from cs_rag_security.ingestion.normativa import excluded_ids, official_path
from cs_rag_security.pipeline import answer
from cs_rag_security.retrieval import Index
from scripts.validate_normative_policy import source_digest


def fixture_corpus(tmp_path, document_id='RCU-0504-2020', relations=None):
    (tmp_path / '04_Metadatos').mkdir()
    (tmp_path / '05_Texto_Procesado').mkdir()
    document = {'id': document_id, 'archivo_pdf': document_id + '.pdf',
                'archivo_en_paquete': '01_Corpus_Oficial/' + document_id + '.pdf',
                'usar_como_norma_vigente': True, 'archivo_local': {'paginas_pdf': 1},
                'vigencia': {'estado': 'sin_certificar', 'advertencia': 'Revisión pendiente'},
                'fecha_resolucion': '2020-01-01'}
    (tmp_path / '04_Metadatos/documents.json').write_text(json.dumps({'documentos': [document]}), encoding='utf-8')
    (tmp_path / '04_Metadatos/relaciones_normativas.json').write_text(json.dumps({
        'relaciones_conocidas_no_exhaustivas': relations or []}), encoding='utf-8')
    page = {'documento_id': document_id, 'archivo_pdf': document_id + '.pdf',
            'pagina_pdf': 1, 'texto': 'Evaluación académica y actividades extracurriculares',
            'metodo': 'texto_pdf', 'ocr_revision_manual_pendiente': False}
    (tmp_path / '05_Texto_Procesado/paginas_rag_piloto.jsonl').write_text(json.dumps(page) + '\n', encoding='utf-8')
    return tmp_path


def test_historical_id_blocked_even_if_misclassified_as_official(tmp_path):
    root = fixture_corpus(tmp_path, 'RCU-0252-2021')
    with pytest.raises(ValueError, match='histórica'):
        load_pages(root)


def test_complete_repeal_blocks_origin_but_partial_repeal_does_not():
    relations = [
        {'documento_origen': 'RCU-1000-2020', 'tipo': 'deja_sin_efecto', 'alcance': 'Resolución completa'},
        {'documento_origen': 'RCU-0127-2020', 'tipo': 'deroga_disposicion', 'alcance': 'Tercera disposición final'},
    ]
    blocked = excluded_ids([], relations)
    assert 'RCU-1000-2020' in blocked
    assert 'RCU-0127-2020' not in blocked


def test_modified_rule_keeps_relation_and_unverified_current_status(tmp_path):
    relation = {'documento_origen': 'RCU-0504-2020', 'documento_posterior': 'RCU-0999-2021',
                'tipo': 'modifica_articulo', 'alcance': 'Artículo 4'}
    pages = load_pages(fixture_corpus(tmp_path, relations=[relation]))
    assert pages[0]['relaciones_normativas'] == [relation]
    assert pages[0]['normativa_actual_verificada'] is False
    hit = {**pages[0], 'chunk_id': 'fixture:1'}
    assert answer(Index([hit]), 'evaluación')['abstained']
    assert not answer(Index([hit]), 'evaluación', documental=True)['abstained']


@pytest.mark.parametrize('documental', [False, True])
def test_stale_index_cannot_send_known_historical_rule_to_generation(documental):
    historical = {'documento_id': 'RCU-0252-2021', 'archivo_pdf': 'RCU-0252-2021.pdf',
                  'pagina_pdf': 2, 'chunk_id': 'historical:2', 'texto': 'Evaluación académica',
                  'ocr_revision_manual_pendiente': False, 'normativa_actual_verificada': True}
    result = answer(Index([historical]), 'evaluación', documental=documental)
    assert result['abstained'] and result['accepted_ids'] == []
    assert 'MOCK' not in result['response']


def test_mixed_index_accepts_official_fragment_and_blocks_excluded_one(tmp_path):
    official, = chunks(load_pages(fixture_corpus(tmp_path)))
    assert official['usar_como_norma_vigente'] is True
    historical = {**official, 'documento_id': 'RCU-0999-2017',
                  'archivo_pdf': 'RCU-0999-2017.pdf', 'chunk_id': 'historical:1',
                  'usar_como_norma_vigente': False}
    index = Index([historical, official])
    result = answer(index, 'evaluación académica', documental=True)
    assert {hit['chunk_id'] for hit in result['retrieved']} == {historical['chunk_id'], official['chunk_id']}
    assert result['accepted_ids'] == [official['chunk_id']]
    assert not result['abstained']
    assert official['archivo_pdf'] in result['response']
    assert historical['archivo_pdf'] not in result['response']


def test_source_digest_matches_git_bytes_with_lf_or_crlf(tmp_path):
    path = tmp_path / 'source.py'
    path.write_bytes(b'# example\nx = 1\n')
    expected = sha256(path.read_bytes()).hexdigest()
    assert source_digest(path) == expected
    path.write_bytes(b'# example\r\nx = 1\r\n')
    assert source_digest(path) == expected


@pytest.mark.parametrize('path', ['01B_Historicos/x.pdf', '01_Corpus_Oficial/../01B_Historicos/x.pdf',
                                 '/01_Corpus_Oficial/x.pdf', '01_Corpus_Oficial/x.txt'])
def test_nonofficial_paths_rejected(path):
    assert not official_path(path)
