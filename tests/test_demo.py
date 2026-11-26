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


def conversational_generation(monkeypatch, claims, state='completa', missing='', accepted=None):
    if accepted is None:
        accepted = [] if state == 'rechazar' else list(range(1, len(claims) + 1))
    generate = Mock(side_effect=[
        {'text': json.dumps({'afirmaciones': claims}), 'metadata': {'model': 'fixture'}},
        {'text': json.dumps({'estado': state, 'falta': missing, 'aceptadas': accepted})},
    ])
    monkeypatch.setattr(demo, 'generate', generate)
    return generate


def test_conversational_complete_list_answers_without_copying_passage(monkeypatch):
    quote = 'Autoevaluación, coevaluación y heteroevaluación'
    gen = conversational_generation(monkeypatch, [{
        'texto': 'Los tres tipos son la autoevaluación, la coevaluación y la heteroevaluación.',
        'pasaje': 1, 'respaldo': quote,
    }], missing='Repetición del contenido ya contestado')
    idx = Index([chunk('reglamento', f'Evaluación por participantes. {quote}. Otros criterios.')])
    result = demo.answer_demo(idx, '¿Cuáles son los tipos de evaluación por participantes?', converse=True)
    assert result['coverage'] == 'completa'
    assert result['response'] == (
        'Los tres tipos son la autoevaluación, la coevaluación y la heteroevaluación. '
        '[reglamento.pdf p. 3]'
    )
    assert 'Otros criterios' not in result['response']
    assert not result['abstained'] and gen.call_count == 2


def test_conversational_partial_requires_a_missing_part_of_the_question(monkeypatch):
    gen = conversational_generation(monkeypatch, [{
        'texto': 'La matrícula comienza el lunes.',
        'pasaje': 1, 'respaldo': 'matrícula comienza el lunes',
    }], 'parcial', 'cuánto cuesta')
    index = Index([chunk('calendario', 'La matrícula comienza el lunes.')])
    result = demo.answer_demo(index, '¿Cuándo comienza la matrícula y cuánto cuesta?', converse=True)
    assert result['coverage'] == 'parcial'
    assert result['response'].startswith('Evidencia parcial.')
    assert gen.call_count == 2


def test_conversational_multisource_cites_each_claim_from_metadata(monkeypatch):
    conversational_generation(monkeypatch, [
        {'texto': 'La matrícula comienza el lunes.', 'pasaje': 1,
         'respaldo': 'La matrícula comienza el lunes'},
        {'texto': 'Para matricularse, hace falta una solicitud.', 'pasaje': 2,
         'respaldo': 'La matrícula requiere una solicitud'},
    ])
    index = Index([
        chunk('calendario', 'La matrícula comienza el lunes.', documento_id='RCU-0127-2020'),
        chunk('requisitos', 'La matrícula requiere una solicitud.', documento_id='RCU-0320-2022'),
    ])
    result = demo.answer_demo(index, 'matrícula RCU-0127-2020 y RCU-0320-2022', converse=True)
    assert result['sources'] == [{'archivo': 'calendario.pdf', 'pagina': 3},
                                 {'archivo': 'requisitos.pdf', 'pagina': 3}]
    assert '[calendario.pdf p. 3]' in result['response']
    assert '[requisitos.pdf p. 3]' in result['response']


@pytest.mark.parametrize('available, calls', [(False, 0), (True, 1)])
def test_conversational_abstains_if_retrieval_or_model_finds_no_evidence(monkeypatch, available, calls):
    gen = conversational_generation(monkeypatch, [])
    index = Index([chunk('doc', 'La matrícula requiere una solicitud.')] if available else [])
    result = demo.answer_demo(index, 'matrícula', converse=True)
    assert result['abstained'] and not result['sources'] and gen.call_count == calls


@pytest.mark.parametrize('claim,state,missing,calls', [
    ({'texto': 'Hay matrícula.', 'pasaje': 8, 'respaldo': 'matrícula requiere una solicitud'}, 'completa', '', 1),
    ({'texto': 'Hay matrícula. [otro.pdf p. 9]', 'pasaje': 1, 'respaldo': 'matrícula requiere una solicitud'}, 'completa', '', 1),
    ({'texto': 'La matrícula requiere un pago.', 'pasaje': 1, 'respaldo': 'matrícula requiere un pago'}, 'completa', '', 1),
    ({'texto': 'Actualmente se exige una solicitud.', 'pasaje': 1, 'respaldo': 'matrícula requiere una solicitud'}, 'completa', '', 1),
    ({'texto': 'La matrícula requiere un pago.', 'pasaje': 1, 'respaldo': 'matrícula requiere una solicitud'}, 'rechazar', '', 2),
    ({'texto': 'Hace falta una solicitud.', 'pasaje': 1, 'respaldo': 'matrícula requiere una solicitud'}, 'parcial', 'detalle inventado', 2),
])
def test_conversational_rejects_unverifiable_output(monkeypatch, claim, state, missing, calls):
    gen = conversational_generation(monkeypatch, [claim], state, missing)
    index = Index([chunk('doc', 'La matrícula requiere una solicitud.')])
    result = demo.answer_demo(index, '¿Qué requiere la matrícula?', converse=True)
    assert result['reason'] == 'salida_no_verificable' and not result['sources']
    assert 'pago' not in result['response'] and 'otro.pdf' not in result['response']
    assert gen.call_count == calls


def test_conversational_filters_existing_injection_before_drafting_and_review(monkeypatch):
    records = [json.loads(line) for line in Path('experiments/attacks.jsonl').read_text().splitlines()]
    attack = next(row for row in records if row['id'] == 'a1')
    gen = conversational_generation(monkeypatch, [{
        'texto': 'Para matricularse, hace falta una solicitud.',
        'pasaje': 1, 'respaldo': 'La matrícula requiere una solicitud',
    }])
    index = Index([chunk('attack', 'matrícula ' + attack['text']),
                   chunk('calendario', 'La matrícula requiere una solicitud.')])
    result = demo.answer_demo(index, 'matrícula', converse=True)
    assert result['exposed_ids'] == ['calendario']
    assert any(row['chunk_id'] == 'attack' and row['detector_suspicious']
               for row in result['evaluated_chunks'])
    for call in gen.call_args_list:
        assert attack['text'] not in call.args[0][1]['content']


def test_conversational_renders_only_claims_accepted_by_reviewer(monkeypatch):
    conversational_generation(monkeypatch, [
        {'texto': 'Para matricularse, hace falta una solicitud.', 'pasaje': 1,
         'respaldo': 'La matrícula requiere una solicitud'},
        {'texto': 'También se exige un pago.', 'pasaje': 1,
         'respaldo': 'La matrícula requiere una solicitud'},
    ], accepted=[1])
    result = demo.answer_demo(Index([chunk('doc', 'La matrícula requiere una solicitud.')]),
                              '¿Qué requisitos y trámites tiene la matrícula?', converse=True)
    assert result['coverage'] == 'completa'
    assert result['response'] == 'Para matricularse, hace falta una solicitud. [doc.pdf p. 3]'


def test_conversational_explicit_subquestions_preserve_supported_answer(monkeypatch):
    generate = Mock(side_effect=[
        {'text': json.dumps({'afirmaciones': [{
            'texto': 'La matrícula comienza el lunes.', 'pasaje': 1,
            'respaldo': 'La matrícula comienza el lunes',
        }]}), 'metadata': {'model': 'fixture'}},
        {'text': '{"estado":"completa","falta":"","aceptadas":[1]}'},
        {'text': '{"afirmaciones":[]}', 'metadata': {'model': 'fixture'}},
    ])
    monkeypatch.setattr(demo, 'generate', generate)
    index = Index([chunk('calendario', 'La matrícula comienza el lunes.')])
    result = demo.answer_demo(index, '¿Cuándo comienza la matrícula? ¿Qué cuesta?', converse=True)
    assert result['coverage'] == 'parcial'
    assert result['response'].endswith('La matrícula comienza el lunes. [calendario.pdf p. 3]')
    assert generate.call_count == 3
    assert json.loads(generate.call_args_list[-1].args[0][1]['content'])['pregunta'] == '¿Qué cuesta?'


def test_conversational_focused_question_reviews_only_the_direct_answer(monkeypatch):
    gen = conversational_generation(monkeypatch, [
        {'texto': 'Los tipos son autoevaluación, coevaluación y heteroevaluación.',
         'pasaje': 1, 'respaldo': 'Autoevaluación, coevaluación y heteroevaluación'},
        {'texto': 'Los momentos son inicial y final.',
         'pasaje': 1, 'respaldo': 'Los momentos son inicial y final'},
    ], accepted=[1])
    index = Index([chunk('reglamento', 'Evaluación por participantes. Autoevaluación, coevaluación '
                          'y heteroevaluación. Los momentos son inicial y final.')])
    result = demo.answer_demo(index, '¿Cuáles son los tipos de evaluación por participantes?', converse=True)
    review = json.loads(gen.call_args_list[1].args[0][1]['content'])
    assert len(review['afirmaciones']) == 1 and 'momentos' not in result['response']
    assert result['coverage'] == 'completa'


def test_conversational_document_identifier_scopes_retrieval_without_boosting_headers(monkeypatch):
    gen = conversational_generation(monkeypatch, [{
        'texto': 'La matrícula comienza el lunes.', 'pasaje': 1,
        'respaldo': 'La matrícula comienza el lunes',
    }])
    index = Index([
        chunk('cabecera', 'RCU-0127-2020 matrícula', documento_id='RCU-0127-2020'),
        chunk('calendario', 'La matrícula comienza el lunes.', documento_id='RCU-0127-2020'),
        chunk('otra', 'La matrícula comienza el lunes.', documento_id='RCU-0320-2022'),
    ])
    result = demo.answer_demo(index, '¿Cuándo comienza la matrícula en RCU-0127-2020?', k=1, converse=True)
    assert result['exposed_ids'] == ['calendario']
    assert result['sources'] == [{'archivo': 'calendario.pdf', 'pagina': 3}]
    assert gen.call_count == 2
