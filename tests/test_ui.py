from streamlit.testing.v1 import AppTest


def test_streamlit_form_and_query():
    app = AppTest.from_file('app/streamlit_app.py').run()
    assert not app.exception
    assert app.title[0].value == 'Consulta documental UNSA'
    app.text_input[0].set_value('¿Qué regula la evaluación por competencias?')
    app.button[0].click().run()
    assert not app.exception
    assert any('Prototipo académico no oficial' in x.value for x in app.warning)
