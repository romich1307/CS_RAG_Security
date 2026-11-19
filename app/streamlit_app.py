import os
import streamlit as st
from cs_rag_security.retrieval import Index
from cs_rag_security.defenses import MODES
from cs_rag_security.pipeline import answer

st.title('Consulta documental UNSA')
st.warning('Prototipo académico no oficial')
st.caption('MOCK por defecto: muestra extractos, no genera una respuesta de LLM.')
mode = st.selectbox('Defensa (A solo para evaluación controlada)', MODES, index=2)
provider = st.selectbox('Proveedor', ['mock', 'local', 'api'])
documental = st.checkbox('Consulta documental provisional, sin afirmar vigencia', value=False)
question = st.text_input('Pregunta')
k = st.slider('Fragmentos top-k', 1, 10, 5)
if st.button('Consultar') and question.strip():
    try:
        result = answer(Index.load('data/vector_db/index.json'), question, mode, provider, k, documental)
        st.write(result['response'])
        for warning in result['warnings']:
            st.warning(warning)
        with st.expander('Fuentes, páginas, puntuaciones y trazabilidad'):
            st.json(result)
    except (OSError, ValueError, KeyError) as exc:
        st.error(f'No se pudo consultar: {exc}. Primero ejecute unsa-rag index.')
