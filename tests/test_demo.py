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
    def fixture(*args, **kwargs):
        fields = kwargs['output_schema']['properties']
        if 'afirmaciones' in fields:
            return {'text': json.dumps({'afirmaciones': claims}), 'metadata': {'model': 'fixture'}}
        review = {'falta': missing, 'aceptadas': accepted}
        if 'estado' in fields:
            review['estado'] = state
        return {'text': json.dumps(review)}

    generate = Mock(side_effect=fixture)
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
    generate = conversational_generation(monkeypatch, [{
        'texto': 'La matrícula comienza el lunes.', 'pasaje': 1,
        'respaldo': 'La matrícula comienza el lunes',
    }], state='parcial', missing='Qué cuesta')
    index = Index([chunk('calendario', 'La matrícula comienza el lunes. Consultar cuánto cuesta.')])
    question = '¿Cuándo comienza la matrícula? ¿Qué cuesta?'
    result = demo.answer_demo(index, question, converse=True)
    assert result['coverage'] == 'parcial'
    assert result['response'].endswith('La matrícula comienza el lunes. [calendario.pdf p. 3]')
    assert result['ollama_calls'] == generate.call_count == 2
    draft, review = (call.kwargs for call in generate.call_args_list)
    assert draft['output_limit'] == 640 and review['output_limit'] == 160
    assert 'estado' not in review['output_schema']['properties']
    assert review['output_schema']['properties']['falta']['enum'] == [
        '', 'Cuándo comienza la matrícula', 'Qué cuesta',
    ]
    assert all(json.loads(call.args[0][1]['content'])['pregunta'] == question
               for call in generate.call_args_list)


def test_conversational_focused_question_requests_one_cohesive_claim(monkeypatch):
    gen = conversational_generation(monkeypatch, [
        {'texto': 'Los tipos son autoevaluación, coevaluación y heteroevaluación.',
         'pasaje': 1, 'respaldo': 'Autoevaluación, coevaluación y heteroevaluación'},
    ])
    index = Index([chunk('reglamento', 'Evaluación por participantes. Autoevaluación, coevaluación '
                          'y heteroevaluación. Los momentos son inicial y final.')])
    result = demo.answer_demo(index, '¿Cuáles son los tipos de evaluación por participantes?', converse=True)
    review = json.loads(gen.call_args_list[1].args[0][1]['content'])
    schema = gen.call_args_list[0].kwargs['output_schema']['properties']['afirmaciones']
    assert schema['maxItems'] == 1
    assert len(review['afirmaciones']) == 1 and 'momentos' not in result['response']
    assert len(review['pasajes_no_confiables']) == 1
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


def test_demo_index_cache_reuses_vectors_and_invalidates_after_rebuild(tmp_path):
    path = tmp_path / 'index.json'
    Index([chunk('first', 'Reglamento anterior')]).save(path, {})
    first = demo.load_demo_index(path)
    assert demo.load_demo_index(path) is first
    assert demo._documentary_index(first) is demo._documentary_index(first)

    replacement = tmp_path / 'replacement.json'
    Index([chunk('second', 'Reglamento actualizado')]).save(replacement, {})
    replacement.replace(path)
    second = demo.load_demo_index(path)
    assert second is not first
    assert demo._documentary_index(second).search('actualizado')[0]['chunk_id'] == 'second'
    path.unlink()
    with pytest.raises(FileNotFoundError):
        demo.load_demo_index(path)


def test_conversational_flags_missing_explicit_source(monkeypatch):
    conversational_generation(monkeypatch, [{
        'texto': 'La matrícula comienza el lunes.', 'pasaje': 1,
        'respaldo': 'La matrícula comienza el lunes',
    }])
    index = Index([chunk('calendario', 'La matrícula comienza el lunes.',
                         documento_id='RCU-0127-2020')])
    result = demo.answer_demo(index, 'matrícula RCU-0127-2020 y RCU-0320-2022', converse=True)
    assert result['coverage'] == 'parcial'
    assert result['response'].startswith('Evidencia parcial.')


def test_conversational_merges_repeated_claims_without_losing_sources(monkeypatch):
    quote = 'La matrícula requiere una solicitud'
    conversational_generation(monkeypatch, [
        {'texto': quote + '.', 'pasaje': 1, 'respaldo': quote},
        {'texto': quote, 'pasaje': 2, 'respaldo': quote},
    ])
    result = demo.answer_demo(Index([chunk('a', quote), chunk('b', quote)]),
                              '¿Qué requiere la matrícula y qué indican ambos documentos?', converse=True)
    assert result['response'] == quote + '. [a.pdf p. 3] [b.pdf p. 3]'
    assert len(result['sources']) == 2


def test_conversational_reviewer_sees_conditions_outside_the_selected_quote(monkeypatch):
    quote = 'Se convalida un crédito extracurricular'
    passage = quote + ' tras acreditar un idioma extranjero o nativo intermedio en el noveno semestre.'
    generator = conversational_generation(monkeypatch, [
        {'texto': quote + '.', 'pasaje': 1, 'respaldo': quote},
    ], state='rechazar')
    result = demo.answer_demo(Index([chunk('doc', passage)]),
                              '¿Qué condiciones tiene la convalidación por idioma intermedio?',
                              converse=True)
    review = json.loads(generator.call_args_list[1].args[0][1]['content'])
    assert review['pasajes_no_confiables'][0]['texto'] == passage
    assert result['abstained'] and not result['sources']


@pytest.mark.parametrize('case_id,discarded', [
    ('a1', True), ('a2', True), ('a3', True), ('a4', False),
    ('b1', False), ('b2', False), ('b3', True), ('b4', False),
])
def test_conversational_keeps_existing_detector_decisions(monkeypatch, case_id, discarded):
    records = [json.loads(line) for line in Path('experiments/attacks.jsonl').read_text().splitlines()]
    record = next(row for row in records if row['id'] == case_id)
    generate = conversational_generation(monkeypatch, [])
    index = Index([chunk(case_id, 'matrícula ' + record['text'])])
    result = demo.answer_demo(index, 'matrícula', converse=True)
    row, = result['evaluated_chunks']
    assert row['detector_suspicious'] is discarded
    assert result['exposed_ids'] == ([] if discarded else [case_id])
    assert generate.call_count == (0 if discarded else 1)
    assert result['abstained'] and not result['sources']


def test_conversational_preserves_verified_conditions_and_reports_stages(monkeypatch):
    quote = ('En el noveno semestre, acreditar un idioma extranjero o nativo de nivel '
             'intermedio permite convalidar un crédito extracurricular.')
    generate = conversational_generation(monkeypatch, [{
        'texto': quote, 'pasaje': 1, 'respaldo': quote,
    }])
    result = demo.answer_demo(Index([chunk('doc', quote)]),
                              '¿Qué contempla el reglamento sobre convalidar por idioma intermedio?',
                              converse=True)
    assert result['response'] == quote + ' [doc.pdf p. 3]'
    assert result['coverage'] == 'completa'
    assert result['ollama_calls'] == generate.call_count == 2
    assert set(result['timings_ms']) == {
        'prepare_index', 'retrieve', 'filter', 'context', 'draft_ollama',
        'review_ollama', 'validation_and_format', 'total',
    }
    assert all(elapsed >= 0 for elapsed in result['timings_ms'].values())


def test_conversational_abstains_when_only_corpus_scope_matches(monkeypatch):
    gen = conversational_generation(monkeypatch, [])
    index = Index([chunk('doc', 'Reglamentos de la UNSA sobre la asistencia.')])
    result = demo.answer_demo(index,
                              '¿Cuál es la temperatura de Neptuno según los reglamentos de la UNSA?',
                              converse=True)
    assert result['reason'] == 'evidencia_insuficiente'
    assert result['ollama_calls'] == 0
    gen.assert_not_called()



def test_conversational_marks_partial_when_only_one_request_matches_admitted_passages(monkeypatch):
    generator = conversational_generation(monkeypatch, [{
        'texto': 'La matrícula comienza el lunes.', 'pasaje': 1,
        'respaldo': 'La matrícula comienza el lunes',
    }])
    result = demo.answer_demo(Index([chunk('doc', 'La matrícula comienza el lunes.')]),
                              '¿Cuándo comienza la matrícula? ¿Qué cuesta?', converse=True)
    assert result['coverage'] == 'parcial'
    assert result['response'].endswith('La matrícula comienza el lunes. [doc.pdf p. 3]')
    assert result['ollama_calls'] == generator.call_count == 2
    assert all(json.loads(call.args[0][1]['content'])['pregunta'] == '¿Cuándo comienza la matrícula?'
               for call in generator.call_args_list)


def test_conversational_drops_invalid_claim_before_review_without_losing_valid_evidence(monkeypatch):
    generator = conversational_generation(monkeypatch, [
        {'texto': 'Se exige un pago.', 'pasaje': 1, 'respaldo': 'Se exige un pago'},
        {'texto': 'La matrícula comienza el lunes.', 'pasaje': 1,
         'respaldo': 'La matrícula comienza el lunes'},
    ], state='parcial', missing='cuánto cuesta', accepted=[1])
    index = Index([chunk('doc', 'La matrícula comienza el lunes.')])
    result = demo.answer_demo(index, '¿Cuándo comienza la matrícula y cuánto cuesta?', converse=True)
    assert result['coverage'] == 'parcial'
    review = json.loads(generator.call_args_list[1].args[0][1]['content'])
    assert [claim['texto'] for claim in review['afirmaciones']] == ['La matrícula comienza el lunes.']
    assert 'pago' not in result['response']


def test_v3_keeps_subquestions_and_only_publishes_supported_claims(monkeypatch):
    quote = 'Las inscripciones comienzan el lunes'
    index = Index([
        chunk('calendario', quote),
        chunk('costos', 'El trámite de inscripción no tiene costo'),
    ])
    generator = Mock(side_effect=[
        {'metadata': {'model': 'fixture'}, 'text': json.dumps({'afirmaciones': [
            {'texto': 'Las inscripciones empiezan el lunes.', 'pasaje': 1, 'respaldo': quote},
            {'texto': 'La inscripción cuesta cien soles.', 'pasaje': 2,
             'respaldo': 'cuesta cien soles'},
        ]})},
        {'text': '{"aceptadas":[1],"incompleta":false}'},
    ])
    monkeypatch.setattr(demo, 'generate', generator)
    question = '¿Cuándo comienzan las inscripciones? ¿Qué costo tiene el trámite?'
    result = demo.answer_demo(index, question, converse=True, version=3)
    assert result['profile'] == 'demo_conversacional_v3'
    assert result['exposed_ids'] == ['calendario', 'costos']
    assert result['coverage'] == 'parcial'
    assert result['response'].endswith('Las inscripciones empiezan el lunes. [calendario.pdf p. 3]')
    assert 'cien soles' not in result['response']
    for call in generator.call_args_list:
        payload = json.loads(call.args[0][1]['content'])
        assert payload['pregunta'] == question


@pytest.mark.parametrize(('review', 'reason'), [
    ('{"aceptadas":[],"incompleta":true}', 'revision_sin_afirmaciones'),
    ('{"aceptadas":[true],"incompleta":false}', 'revision_no_verificable'),
])
def test_v3_fails_closed_on_rejected_or_invalid_review(monkeypatch, review, reason):
    quote = 'Las inscripciones comienzan el lunes'
    index = Index([chunk('calendario', quote)])
    generator = Mock(side_effect=[
        {'metadata': {'model': 'fixture'}, 'text': json.dumps({'afirmaciones': [
            {'texto': quote, 'pasaje': 1, 'respaldo': quote},
        ]})},
        {'text': review},
    ])
    monkeypatch.setattr(demo, 'generate', generator)
    result = demo.answer_demo(index, '¿Cuándo comienzan las inscripciones?', converse=True, version=3)
    assert result['abstained']
    assert result['reason'] == reason
    assert result['sources'] == []


def test_v3_reviewer_can_reject_irrelevant_claim_without_flagging_coverage(monkeypatch):
    relevant = 'Las inscripciones comienzan el lunes'
    irrelevant = 'La inscripción se tramita en secretaría'
    index = Index([chunk('norma', f'{relevant}. {irrelevant}.')])
    generator = Mock(side_effect=[
        {'metadata': {'model': 'fixture'}, 'text': json.dumps({'afirmaciones': [
            {'texto': relevant, 'pasaje': 1, 'respaldo': relevant},
            {'texto': irrelevant, 'pasaje': 1, 'respaldo': irrelevant},
        ]})},
        {'text': '{"aceptadas":[1],"incompleta":false}'},
    ])
    monkeypatch.setattr(demo, 'generate', generator)
    result = demo.answer_demo(index, '¿Cuándo comienzan las inscripciones?', converse=True, version=3)
    assert result['coverage'] == 'completa'
    assert result['response'] == f'{relevant} [norma.pdf p. 3]'


def v4_generation(monkeypatch, claims, accepted, complete):
    generator = Mock(side_effect=[
        {'metadata': {'model': 'fixture'}, 'text': json.dumps({'afirmaciones': claims})},
        {'text': json.dumps({'aceptadas': accepted, 'completas': complete})},
    ])
    monkeypatch.setattr(demo, 'generate', generator)
    return generator


def test_v4_cannot_mark_missing_subquestion_complete(monkeypatch):
    first = 'El horario comienza el lunes'
    second = 'El trámite cuesta cinco soles'
    index = Index([chunk('horario', first), chunk('costos', second)])
    gen = v4_generation(monkeypatch, [
        {'texto': first, 'respaldo': first, 'peticion': 1, 'pasaje': 1},
        {'texto': second, 'respaldo': second, 'peticion': 2, 'pasaje': 2},
    ], [1], [1, 2])
    result = demo.answer_demo(index, '¿Cuándo comienza el horario y cuánto cuesta el trámite?',
                              converse=True, version=4)
    assert result['profile'] == 'demo_conversacional_v4'
    assert result['coverage'] == 'parcial'
    assert result['sources'] == [{'archivo': 'horario.pdf', 'pagina': 3}]
    assert gen.call_count == 2
    assert len(json.loads(gen.call_args.args[0][1]['content'])['peticiones']) == 2


@pytest.mark.parametrize(('answer_both', 'coverage'), [(False, 'parcial'), (True, 'completa')])
def test_v4_covers_each_named_resolution_per_request(monkeypatch, answer_both, coverage):
    first = 'La matrícula comienza el lunes'
    second = 'La matrícula comienza el martes'
    index = Index([
        chunk('a', first, documento_id='RCU-0127-2020'),
        chunk('b', second, documento_id='RCU-0320-2022'),
    ])
    v4_generation(monkeypatch, [
        {'texto': first, 'respaldo': first, 'peticion': 1, 'pasaje': 1},
        {'texto': second, 'respaldo': second, 'peticion': 1, 'pasaje': 2},
    ], [1, 2] if answer_both else [1], [1])
    result = demo.answer_demo(index, '¿Qué fechas de matrícula indican RCU-0127-2020 y RCU-0320-2022?',
                              converse=True, version=4)
    assert result['coverage'] == coverage
    assert len(result['sources']) == (2 if answer_both else 1)


def test_v4_keeps_part_without_document_id_in_mixed_search(monkeypatch):
    first = 'La matrícula comienza el lunes'
    second = 'El trámite cuesta cinco soles'
    index = Index([chunk('a', first, documento_id='RCU-0127-2020'), chunk('b', second)])
    gen = v4_generation(monkeypatch, [
        {'texto': first, 'respaldo': first, 'peticion': 1, 'pasaje': 1},
        {'texto': second, 'respaldo': second, 'peticion': 2, 'pasaje': 2},
    ], [1, 2], [1, 2])
    result = demo.answer_demo(index, '¿Cuándo comienza la matrícula según RCU-0127-2020? ¿Cuánto cuesta el trámite?',
                              converse=True, version=4)
    assert result['exposed_ids'] == ['a', 'b']
    assert result['coverage'] == 'completa'
    assert all(call.args[0][0]['role'] == 'system' and call.args[0][1]['role'] == 'user'
               for call in gen.call_args_list)


def test_v4_typographic_anchor_keeps_metadata_citation(monkeypatch):
    quote = 'La fase “preliminar” requiere registro'
    index = Index([chunk('tramite', quote)])
    v4_generation(monkeypatch, [
        {'texto': 'Se requiere registrar la fase preliminar.', 'respaldo': quote.replace('“', '"').replace('”', '"'),
         'peticion': 1, 'pasaje': 1},
    ], [1], [1])
    result = demo.answer_demo(index, '¿Qué requiere la fase preliminar?', converse=True, version=4)
    assert result['response'] == 'Se requiere registrar la fase preliminar. [tramite.pdf p. 3]'


@pytest.mark.parametrize('change', [
    {'respaldo': 'ase inicial requiere registro'},
    {'respaldo': 'La fase inicial requiere pago'},
    {'pasaje': 2},
    {'peticion': True},
    {'texto': 'La fase inicial requiere registro. [otra.pdf p. 9]'},
])
def test_v4_rejects_unsafe_or_unanchored_claim(monkeypatch, change):
    quote = 'La fase inicial requiere registro'
    gen = v4_generation(monkeypatch, [
        {'texto': quote, 'respaldo': quote, 'peticion': 1, 'pasaje': 1, **change},
    ], [1], [1])
    result = demo.answer_demo(Index([chunk('registro', quote)]), '¿Qué requiere la fase inicial?',
                              converse=True, version=4)
    assert result['reason'] == 'salida_formato_o_anclaje_invalido'
    assert not result['sources']
    assert gen.call_count == 1


def test_v4_never_uses_wrong_named_resolution_for_a_subquestion(monkeypatch):
    quote = 'La matrícula comienza el lunes'
    index = Index([chunk('a', quote, documento_id='RCU-0127-2020'),
                   chunk('b', quote, documento_id='RCU-0320-2022')])
    v4_generation(monkeypatch, [
        {'texto': quote, 'respaldo': quote, 'peticion': 1, 'pasaje': 2},
        {'texto': quote, 'respaldo': quote, 'peticion': 2, 'pasaje': 2},
    ], [1], [1, 2])
    result = demo.answer_demo(
        index, '¿Cuándo comienza la matrícula según RCU-0127-2020? '
        '¿Cuándo comienza la matrícula según RCU-0320-2022?', converse=True, version=4,
    )
    assert result['coverage'] == 'parcial'
    assert result['sources'] == [{'archivo': 'b.pdf', 'pagina': 3}]


def test_v4_fails_closed_on_malformed_review(monkeypatch):
    quote = 'La matrícula comienza el lunes'
    v4_generation(monkeypatch, [
        {'texto': quote, 'respaldo': quote, 'peticion': 1, 'pasaje': 1},
    ], [True], [1])
    result = demo.answer_demo(Index([chunk('a', quote)]), '¿Cuándo comienza la matrícula?',
                              converse=True, version=4)
    assert result['reason'] == 'revision_no_verificable'
    assert not result['sources']


@pytest.mark.parametrize('version', [3, 4])
def test_conversational_filters_existing_flagged_fixture_before_generation(monkeypatch, version):
    record = next(r for r in map(json.loads, Path('experiments/attacks.jsonl').read_text().splitlines())
                  if r['id'] == 'a3')
    generator = Mock()
    monkeypatch.setattr(demo, 'generate', generator)
    result = demo.answer_demo(Index([chunk('fixture', 'Reglamento académico. ' + record['text'])]),
                              '¿Qué indica el reglamento académico?', converse=True, version=version)
    assert result['abstained'] and not result['exposed_ids']
    assert result['evaluated_chunks'][0]['detector_suspicious']
    generator.assert_not_called()


def v5_generation(monkeypatch, selections, decisions):
    grouped = {key: [] for key in decisions}
    for item in selections:
        grouped[str(item['peticion'])].append(item['pasaje'])
    generator = Mock(side_effect=[
        {'metadata': {'model': 'fixture'}, 'text': json.dumps({'selecciones': grouped})},
        {'text': json.dumps(decisions)},
    ])
    monkeypatch.setattr(demo, 'generate', generator)
    return generator


def test_v5_returns_exact_temporal_and_quantitative_evidence(monkeypatch):
    source = 'En la siguiente clase programada, la docente dará retroalimentación de las cuatro actividades.'
    v5_generation(monkeypatch, [{'peticion': 1, 'pasaje': 1}],
                  {'1': {'estado': 'completa', 'pasajes': [1]}})
    result = demo.answer_demo(Index([chunk('norma', source)]), '¿Cuándo habrá retroalimentación?',
                              converse=True, version=5)
    assert result['coverage'] == 'completa'
    assert result['response'] == f'{source} [norma.pdf p. 3]'


def test_v5_renders_complete_multisource_with_literal_actors_and_exceptions(monkeypatch):
    first = 'La Jefatura designará coordinadores, salvo cuando el cargo esté vacante.'
    second = 'El departamento académico aprueba los instrumentos con respaldo de validez.'
    index = Index([chunk('a', first, documento_id='RCU-0127-2020'),
                   chunk('b', second, documento_id='RCU-0320-2022')])
    v5_generation(monkeypatch, [{'peticion': 1, 'pasaje': 1}, {'peticion': 2, 'pasaje': 2}],
                  {'1': {'estado': 'completa', 'pasajes': [1]}, '2': {'estado': 'completa', 'pasajes': [2]}})
    result = demo.answer_demo(index, '¿Quién designará coordinadores según RCU-0127-2020? '
                              '¿Quién aprueba instrumentos según RCU-0320-2022?', converse=True, version=5)
    assert result['coverage'] == 'completa' and first in result['response'] and second in result['response']


def test_v5_preserves_supported_part_and_does_not_echo_false_premise(monkeypatch):
    source = 'La inasistencia justificada requiere documentación y la aprobación se registra en el sistema.'
    v5_generation(monkeypatch, [{'peticion': 1, 'pasaje': 1}],
                  {'1': {'estado': 'completa', 'pasajes': [1]}, '2': {'estado': 'sin_evidencia', 'pasajes': []}})
    result = demo.answer_demo(Index([chunk('norma', source)]),
                              '¿Dónde se registra la aprobación y qué planta debe llevar por inasistencia?',
                              converse=True, version=5)
    assert result['coverage'] == 'parcial'
    assert 'petición 2' in result['response'].lower()
    assert 'planta' not in result['response']


@pytest.mark.parametrize(('stage', 'value', 'reason'), [
    (0, '{"selecciones":{"1":[99]}}', 'salida_formato_o_anclaje_invalido'),
    (0, 'texto sin cita', 'salida_formato_o_anclaje_invalido'),
    (1, '{"1":{"estado":"completa","pasajes":[true]}}', 'revision_no_verificable'),
    (1, '{"1":{"estado":"completa","pasajes":[]}}', 'revision_no_verificable'),
])
def test_v5_never_renders_raw_or_fabricated_references(monkeypatch, stage, value, reason):
    gen = v5_generation(monkeypatch, [{'peticion': 1, 'pasaje': 1}],
                        {'1': {'estado': 'completa', 'pasajes': [1]}})
    outputs = [{'metadata': {'model': 'fixture'}, 'text': '{"selecciones":{"1":[1]}}'},
               {'text': '{"1":{"estado":"completa","pasajes":[1]}}'}]
    outputs[stage]['text'] = value
    gen.side_effect = outputs
    result = demo.answer_demo(Index([chunk('a', 'La matrícula exige una solicitud.')]),
                              '¿Qué exige la matrícula?', converse=True, version=5)
    assert result['reason'] == reason and result['abstained']
    assert not result['sources'] and value not in result['response']


def test_v5_certified_vigencia_is_not_inferred(monkeypatch):
    generator = Mock()
    monkeypatch.setattr(demo, 'generate', generator)
    result = demo.answer_demo(Index([]), '¿Qué plazo vigente se aplica?', converse=True, version=5)
    assert result['reason'] == 'vigencia_no_certificada'
    generator.assert_not_called()


def test_v5_filters_existing_flagged_fixture_before_prompt(monkeypatch):
    record = next(r for r in map(json.loads, Path('experiments/attacks.jsonl').read_text().splitlines())
                  if r['id'] == 'a3')
    generator = Mock()
    monkeypatch.setattr(demo, 'generate', generator)
    result = demo.answer_demo(Index([chunk('fixture', 'Trámite académico. ' + record['text'])]),
                              '¿Qué indica el trámite académico?', converse=True, version=5)
    assert result['abstained'] and not result['exposed_ids']
    assert result['evaluated_chunks'][0]['detector_suspicious']
    generator.assert_not_called()


def test_v5_accepts_legitimate_documentary_obligation(monkeypatch):
    source = 'El estudiante deberá presentar la constancia y la solicitud dentro de cinco días.'
    v5_generation(monkeypatch, [{'peticion': 1, 'pasaje': 1}],
                  {'1': {'estado': 'completa', 'pasajes': [1]}})
    result = demo.answer_demo(Index([chunk('tramite', source)]), '¿Qué debe presentar el estudiante?',
                              converse=True, version=5)
    assert source in result['response']


def test_v5_cli_prints_public_fields_only(monkeypatch, capsys):
    from cs_rag_security.cli import main

    monkeypatch.setattr(demo, 'load_demo_index', lambda path: Index([]))
    monkeypatch.setattr(demo, 'answer_demo', Mock(return_value={
        'profile': 'demo_conversacional_v5', 'response': 'Respuesta pública.',
        'sources': [], 'abstained': False, 'raw_response': 'privado', 'timings_ms': {},
    }))
    monkeypatch.setattr('sys.argv', ['unsa-rag', 'chat', '--demo', '--demo-version', '5', '--provider', 'local'])
    main()
    assert demo.answer_demo.call_args.kwargs['version'] == 5
    result = json.loads(capsys.readouterr().out)
    assert result == {'profile': 'demo_conversacional_v5', 'response': 'Respuesta pública.',
                      'sources': [], 'abstained': False}
