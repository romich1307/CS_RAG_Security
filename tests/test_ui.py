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
    assert any('Prototipo académico no oficial' in x.value for x in app.warning)


def test_streamlit_handles_api_runtime_error_401():
    fake_index = Index([])
    with patch('cs_rag_security.retrieval.Index.load', return_value=fake_index), \
         patch('cs_rag_security.pipeline.answer', side_effect=RuntimeError('Error HTTP del proveedor API (401)')):
        app = AppTest.from_file('app/streamlit_app.py').run()
        app.selectbox[1].select('api')
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
        app.selectbox[1].select('api')
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
        app.selectbox[1].select('api')
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
