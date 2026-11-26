from streamlit.testing.v1 import AppTest
from unittest.mock import patch
from cs_rag_security.retrieval import Index


def test_streamlit_form_and_query():
    app = AppTest.from_file('app/streamlit_app.py').run()
    assert not app.exception
    assert app.title[0].value == 'Consulta documental UNSA'
    app.text_input[0].set_value('¿Qué regula la evaluación por competencias?')
    app.button[0].click().run()
    assert not app.exception
    assert any('Prototipo académico no oficial' in item.proto.body for item in app.get('html'))


def test_streamlit_handles_api_runtime_error_401():
    fake_index = Index([])
    with patch('cs_rag_security.retrieval.Index.load', return_value=fake_index), \
         patch('cs_rag_security.pipeline.answer', side_effect=RuntimeError('Error HTTP del proveedor API (401)')):
        app = AppTest.from_file('app/streamlit_app.py').run()
        app.radio(key='perfil-c').set_value('Configuración experimental').run()
        app.selectbox(key='proveedor').select('api')
        app.text_input[0].set_value('¿Pregunta?')
        app.button[0].click().run()
        assert not app.exception
        assert len(app.error) == 1
        err_msg = app.error[0].value
        assert '401' in err_msg
        assert 'autenticación' in err_msg.lower()
        assert 'unsa-rag index' not in err_msg


def test_streamlit_handles_api_runtime_error_429():
    fake_index = Index([])
    with patch('cs_rag_security.retrieval.Index.load', return_value=fake_index), \
         patch('cs_rag_security.pipeline.answer', side_effect=RuntimeError('Error HTTP del proveedor API (429)')):
        app = AppTest.from_file('app/streamlit_app.py').run()
        app.radio(key='perfil-c').set_value('Configuración experimental').run()
        app.selectbox(key='proveedor').select('api')
        app.text_input[0].set_value('¿Pregunta?')
        app.button[0].click().run()
        assert not app.exception
        assert len(app.error) == 1
        err_msg = app.error[0].value
        assert '429' in err_msg
        assert 'cuota' in err_msg.lower() or 'solicitudes' in err_msg.lower()
        assert 'unsa-rag index' not in err_msg


def test_streamlit_handles_api_connection_error():
    fake_index = Index([])
    with patch('cs_rag_security.retrieval.Index.load', return_value=fake_index), \
         patch('cs_rag_security.pipeline.answer', side_effect=RuntimeError('Error de conexión con el proveedor API')):
        app = AppTest.from_file('app/streamlit_app.py').run()
        app.radio(key='perfil-c').set_value('Configuración experimental').run()
        app.selectbox(key='proveedor').select('api')
        app.text_input[0].set_value('¿Pregunta?')
        app.button[0].click().run()
        assert not app.exception
        assert len(app.error) == 1
        err_msg = app.error[0].value
        assert 'conexión' in err_msg.lower()
        assert 'unsa-rag index' not in err_msg


def test_streamlit_recommends_rebuild_index_only_on_missing_index():
    with patch('cs_rag_security.retrieval.Index.load', side_effect=FileNotFoundError('data/vector_db/index.json no existe')):
        app = AppTest.from_file('app/streamlit_app.py').run()
        app.text_input[0].set_value('¿Pregunta?')
        app.button[0].click().run()
        assert not app.exception
        assert len(app.error) == 1
        err_msg = app.error[0].value
        assert 'unsa-rag index' in err_msg


def test_streamlit_does_not_expose_raw_response_in_ui():
    fake_index = Index([])
    rejected_raw = 'RAW_UNSAFE_MODEL_OUTPUT_SECRET_LEAK_123'
    fake_result = {
        'question': '¿Consulta de prueba?',
        'response': 'Me abstengo: la salida del modelo carece de citas válidas del contexto.',
        'raw_response': rejected_raw,
        'unlisted_internal_field': 'VALOR_INTERNO_NO_SEGURO',
        'provider': 'local',
        'mode': 'C_defensa_propuesta',
        'documental': True,
        'abstained': True,
        'warnings': ['Prototipo académico no oficial.'],
        'retrieved': [{'texto': 'CORPUS_PRIVADO'}],
        'evaluated_chunks': [{'chunk_id': 'seguro', 'texto': 'CORPUS_PRIVADO'}],
        'accepted_ids': [],
        'detector_log': [],
        'seconds': 0.12,
        'seed': 42,
        'top_k': 5,
        'retriever': 'mock',
        'citation_validation': 'solo pertenencia; no certifica entailment',
        'generation_metadata': {'provider': 'local', 'model': 'qwen2.5:3b',
                                'internal': 'PROVEEDOR_PRIVADO'}
    }
    with patch('cs_rag_security.retrieval.Index.load', return_value=fake_index), \
         patch('cs_rag_security.pipeline.answer', return_value=fake_result):
        app = AppTest.from_file('app/streamlit_app.py').run()
        app.radio(key='perfil-c').set_value('Configuración experimental')
        app.text_input[0].set_value('¿Consulta de prueba?')
        app.button[0].click().run()
        assert not app.exception
        # La respuesta validada (abstención segura) sí debe mostrarse
        assert any('Me abstengo: la salida del modelo carece de citas válidas del contexto.' in el.value for el in app.text)
        # raw_response y campos no seguros NO deben aparecer en ninguna sección de la interfaz (ni en json ni en textos)
        assert len(app.code) == 1
        rendered_json = app.code[0].value
        assert 'raw_response' not in rendered_json
        assert rejected_raw not in rendered_json
        assert 'CORPUS_PRIVADO' not in rendered_json
        assert 'PROVEEDOR_PRIVADO' not in rendered_json
        assert 'unlisted_internal_field' not in rendered_json
        assert 'VALOR_INTERNO_NO_SEGURO' not in rendered_json

        # Confirmar que en la interfaz solo se exponen campos de la lista explícita segura
        import json
        from app.streamlit_app import SAFE_TRACE_FIELDS
        parsed_trace = json.loads(rendered_json)
        assert set(parsed_trace.keys()).issubset(set(SAFE_TRACE_FIELDS))
        assert 'raw_response' not in SAFE_TRACE_FIELDS

        for el in app.main:
            if hasattr(el, 'value') and isinstance(el.value, str):
                assert rejected_raw not in el.value
                assert 'VALOR_INTERNO_NO_SEGURO' not in el.value

        # Confirmar que el resultado devuelto por pipeline conserva íntegramente raw_response para auditoría
        assert fake_result['raw_response'] == rejected_raw


def test_demo_streamlit_handles_local_connection_and_model_errors():
    from urllib.error import HTTPError, URLError

    for error, expected in [
        (URLError('PROVEEDOR_PRIVADO'), 'ollama serve'),
        (HTTPError(None, 404, 'PROVEEDOR_PRIVADO', None, None), 'ollama list'),
        (RuntimeError('PROVEEDOR_PRIVADO'), 'No se pudo completar la generación'),
    ]:
        with patch('cs_rag_security.retrieval.Index.load', return_value=Index([])), \
             patch('cs_rag_security.demo.answer_demo', side_effect=error):
            app = AppTest.from_file('app/streamlit_app.py').run()
            app.selectbox(key='proveedor').select('local').run()
            app.text_input[0].set_value('¿Consulta de prueba?')
            app.button[0].click().run()
            assert not app.exception
            assert expected in app.error[0].value
            assert 'PROVEEDOR_PRIVADO' not in app.error[0].value


def test_redesigned_mock_renders_only_the_validated_excerpt():
    response = {
        'response': 'MOCK\n[documento.pdf p. 2] Texto documental <literal>.',
        'provider': 'mock',
        'mode': 'C_defensa_propuesta',
        'abstained': False,
        'sources': [{'archivo': 'documento.pdf', 'pagina': 2}],
        'evaluated_chunks': [
            {'chunk_id': 'admitido', 'status': 'accepted', 'archivo_pdf': 'documento.pdf',
             'pagina_pdf': 2, 'score': 0.5, 'texto': 'CONTENIDO_PRIVADO'},
            {'chunk_id': 'rechazado', 'status': 'discarded', 'archivo_pdf': 'rechazado.pdf',
             'pagina_pdf': 9, 'texto': 'CONTENIDO_DESCARTADO'},
        ],
    }

    with patch('cs_rag_security.retrieval.Index.load', return_value=Index([])), \
         patch('cs_rag_security.demo.answer_demo', return_value=response) as answer_demo:
        app = AppTest.from_file('app/streamlit_app.py').run()
        app.selectbox(key='top-k').select(3)
        app.text_input[0].set_value('¿Qué indica el documento?')
        app.button[0].click().run()

        assert not app.exception
        assert answer_demo.call_args.args[1:] == ('¿Qué indica el documento?', 'mock', 3, True, None)
        rendered_html = '\n'.join(item.proto.body for item in app.get('html'))
        assert 'Texto documental &lt;literal&gt;.' in rendered_html
        assert 'documento.pdf, página 2' in [item.value for item in app.text]
        assert 'CONTENIDO_PRIVADO' not in rendered_html
        assert 'CONTENIDO_DESCARTADO' not in app.code[0].value
        assert 'rechazado' in app.code[0].value
        app.selectbox(key='top-k').select(4).run()
        assert not app.code
