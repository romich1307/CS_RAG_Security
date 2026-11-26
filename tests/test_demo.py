import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from cs_rag_security import demo
from cs_rag_security.retrieval import Index


def chunk(cid, text, **overrides):
    return {
        'chunk_id': cid, 'texto': text, 'archivo_pdf': f'{cid}.pdf', 'pagina_pdf': 3,
        'origen': 'oficial_piloto', 'ocr_revision_manual_pendiente': False, **overrides,
    }


def generation(monkeypatch, passages, partial=False):
    generate = Mock(return_value={
        'metadata': {'model': 'fixture'},
        'text': json.dumps({'parcial': partial, 'pasajes': passages}),
    })
    monkeypatch.setattr(demo, 'generate', generate)
    return generate


def test_demo_backfills_after_exclusions_and_validates_partial_result(monkeypatch):
    quote = 'El reglamento explica los criterios de matrícula'
    index = Index([
        chunk('ocr', 'matrícula', ocr_revision_manual_pendiente=True),
        chunk('historic', 'matrícula', usar_como_norma_vigente=False),
        chunk('foreign', 'matrícula', origen='experimental'),
        chunk('admitted', quote),
    ])
    generate = generation(monkeypatch, [1], partial=True)
    result = demo.answer_demo(index, 'matrícula', k=1)
    assert result['response'].startswith('Evidencia parcial.')
    assert '[admitted.pdf p. 3]' in result['response']
    assert result['sources'] == [{'archivo': 'admitted.pdf', 'pagina': 3}]
    assert result['exposed_ids'] == ['admitted']
    assert 'raw_response' not in result
    assert [row['discard_reasons'] for row in result['evaluated_chunks']] == [
        ['ocr_revision_pendiente'], ['documento_historico'], ['origen_no_admitido'], [],
    ]
    messages = generate.call_args.args[0]
    assert messages[0]['role'] == 'system'
    assert demo.SINGLE_PASSAGE_GUIDANCE in messages[0]['content']
    assert json.loads(messages[1]['content'])['documentos_no_confiables'] == [
        {'numero': 1, 'documento': 'admitted.pdf', 'texto': quote},
    ]


@pytest.mark.parametrize('passages,reason', [
    ([], 'modelo_sin_evidencia'),
    ([9], 'salida_no_verificable'),
    ([True], 'salida_no_verificable'),
    ([{'fuente': 1, 'extracto': 'El trámite requiere un soborno'}], 'salida_no_verificable'),
    ([{'extracto': 'El trámite requiere una solicitud'}], 'salida_no_verificable'),
])
def test_demo_rejects_absent_unrecognized_or_invented_evidence(monkeypatch, passages, reason):
    generation(monkeypatch, passages)
    index = Index([chunk('a', 'El trámite requiere una solicitud')])
    result = demo.answer_demo(index, 'trámite')
    assert result['abstained'] and result['reason'] == reason and not result['sources']
    assert 'soborno' not in result['response']


@pytest.mark.parametrize('question,documental,reason', [
    ('¿Sigue vigente el reglamento?', True, 'vigencia_no_certificada'),
    ('reglamento', False, 'vigencia_no_certificada'),
    ('xyzabc', True, 'evidencia_insuficiente'),
    ('matrícula', True, 'ocr_pendiente'),
])
def test_demo_abstains_before_generation(monkeypatch, question, documental, reason):
    generate = generation(monkeypatch, [])
    index = Index([chunk('ocr', 'matrícula', ocr_revision_manual_pendiente=True)])
    result = demo.answer_demo(index, question, documental=documental)
    assert result['reason'] == reason and not result['exposed_ids']
    generate.assert_not_called()


def test_demo_detector_uses_existing_attack_and_control(monkeypatch):
    records = [json.loads(line) for line in Path('experiments/attacks.jsonl').read_text().splitlines()]
    attack = next(row for row in records if row['id'] == 'a1')
    benign = next(row for row in records if row['id'] == 'b3')
    clean = 'Los criterios de matrícula figuran en el documento'
    index = Index([
        chunk('attack', 'matrícula ' + attack['text']),
        chunk('benign', 'matrícula ' + benign['text']),
        chunk('clean', clean),
    ])
    generation(monkeypatch, [1])
    result = demo.answer_demo(index, 'matrícula')
    rows = {row['chunk_id']: row for row in result['evaluated_chunks']}
    assert rows['attack']['detector_suspicious']
    assert rows['benign']['detector_suspicious']
    assert result['exposed_ids'] == ['clean']
    assert result['sources'] == [{'archivo': 'clean.pdf', 'pagina': 3}]


def test_demo_explicit_document_excludes_other_relevant_documents(monkeypatch):
    generate = generation(monkeypatch, [1])
    index = Index([
        chunk('other', 'matrícula'),
        chunk('wanted', 'El reglamento estipula requisitos de matrícula',
              documento_id='RCU-0127-2020'),
    ])
    result = demo.answer_demo(index, 'matrícula en la rcu-0127-2020')
    assert result['exposed_ids'] == ['wanted']
    assert result['sources'] == [{'archivo': 'wanted.pdf', 'pagina': 3}]
    generate.assert_called_once()


def test_demo_balances_context_across_explicit_documents(monkeypatch):
    generate = generation(monkeypatch, [1, 2])
    index = Index([
        chunk('first', 'Los requisitos para matrícula constan en el acta', documento_id='RCU-0127-2020'),
        chunk('second', 'Los requisitos adicionales constan en el anexo', documento_id='RCU-0127-2020'),
        chunk('third', 'El calendario de matrícula consta en el anexo', documento_id='RCU-0320-2022'),
    ])
    result = demo.answer_demo(index, 'matrícula RCU-0127-2020 y RCU-0320-2022', k=2)
    assert result['exposed_ids'] == ['first', 'third']
    assert generate.call_args.args[0][0]['content'] == demo.SYSTEM
    assert [source['archivo'] for source in result['sources']] == ['first.pdf', 'third.pdf']


def test_demo_search_rejoins_words_wrapped_in_pdf_without_rewriting_citation(monkeypatch):
    fragment = 'Se modificó el reglamento de prácticas Pre- Profesionales'
    original_index = Index([chunk('pdf', fragment)])
    assert original_index.search('preprofesionales') == []
    generation(monkeypatch, [1])
    result = demo.answer_demo(original_index, 'preprofesionales')
    assert result['exposed_ids'] == ['pdf']
    assert fragment in result['response']
    assert result['sources'] == [{'archivo': 'pdf.pdf', 'pagina': 3}]
