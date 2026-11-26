import os
from pathlib import Path
from urllib.error import HTTPError, URLError

import streamlit as st

from cs_rag_security.defenses import MODES
from cs_rag_security.demo import answer_demo
from cs_rag_security.pipeline import answer
from cs_rag_security.retrieval import Index
from cs_rag_security.traceability import (
    extract_citations,
    sanitize_chunk_dict,
)

INDEX_PATH = Path(__file__).resolve().parents[1] / 'data/vector_db/index.json'
SAFE_TRACE_FIELDS = (
    'provider', 'mode', 'profile', 'abstained', 'reason', 'retriever',
    'top_k', 'model', 'coverage', 'evaluated_chunks', 'exposed_ids',
)


def safe_trace(result):
    trace = {key: result[key] for key in SAFE_TRACE_FIELDS if key in result}
    trace['evaluated_chunks'] = [
        sanitize_chunk_dict(chunk) for chunk in result.get('evaluated_chunks', [])
    ]
    if 'exposed_ids' not in trace:
        trace['exposed_ids'] = result.get('accepted_ids', []) if (
            result.get('generation_metadata') and result['provider'] != 'mock'
        ) else []
    return trace


def show_result(result):
    metadata = result.get('generation_metadata') or {}
    if metadata.get('refusal') or metadata.get('finish_reason') in ('refusal', 'content_filter'):
        st.write('Me abstengo: el modelo rechazó la consulta.')
    elif result['abstained']:
        st.write(result['response'])
    else:
        st.text(result['response'])
    sources = result.get('sources')
    if sources is None and not result['abstained']:
        sources = [
            {'archivo': name, 'pagina': page}
            for name, page in dict.fromkeys(extract_citations(result['response']))
        ]
    if sources:
        st.subheader('Fuentes citadas')
        for source in sources:
            st.text(f"{source['archivo']} · página {source['pagina']}")
    with st.expander('Trazabilidad de recuperación y filtrado'):
        st.json(safe_trace(result))


def provider_error(exc, provider):
    if isinstance(exc, HTTPError):
        if provider == 'local' and exc.code == 404:
            return 'Ollama no encontró el modelo o la ruta de chat. Revise el modelo con ollama list.'
        return 'El servidor de generación no pudo completar la consulta.'
    if isinstance(exc, (URLError, TimeoutError)):
        return 'No se pudo conectar con Ollama o se agotó la espera. Compruebe ollama serve.'
    if provider == 'api':
        message = str(exc)
        if message == 'Error HTTP del proveedor API (401)':
            return 'Error de autenticación del proveedor API (401). Revise la configuración.'
        if message == 'Error HTTP del proveedor API (429)':
            return 'Cuota del proveedor API excedida (429). Inténtelo más tarde.'
        if message == 'Error de conexión con el proveedor API':
            return message
    if isinstance(exc, ValueError):
        return 'No se pudo validar la configuración o la respuesta del proveedor.'
    return 'No se pudo completar la generación.'


st.title('Consulta documental UNSA')
st.warning('Prototipo académico no oficial. El corpus no certifica vigencia normativa.')
demo_label = 'C · Demostración documental'
selection = st.selectbox('Configuración', [demo_label, *MODES])
demo = selection == demo_label
provider = st.selectbox(
    'Proveedor', ['mock', 'local'] if demo else ['mock', 'local', 'api'],
    format_func={'mock': 'Mock extractivo', 'local': 'Ollama local', 'api': 'API experimental'}.get,
)
mode = MODES[2] if selection == demo_label else selection
if provider == 'mock':
    st.caption('Simulación mock. Muestra extractos sin usar un LLM.')
if demo and provider == 'local':
    st.caption('Respuesta documental con citas de PDF y página.')
elif not demo:
    st.caption('Configuración experimental. A carece de aislamiento de instrucciones.')
model = None
if provider == 'local':
    model = st.text_input('Modelo instalado en Ollama', os.environ.get('RAG_LOCAL_MODEL') or 'qwen2.5:3b',
                          disabled=not demo)
    if not demo:
        st.caption('Las condiciones históricas usan el modelo configurado en RAG_LOCAL_MODEL.')
documental = st.checkbox('Consulta documental provisional', value=True,
                         help='Desmarque esta opción para solicitar una comprobación de vigencia.')
question = st.text_input('Pregunta')
k = st.slider('Fragmentos del contexto', 1, 10, 5)
if st.button('Consultar'):
    if not question.strip():
        st.info('Escriba una pregunta documental.')
    else:
        try:
            index = Index.load(INDEX_PATH)
        except FileNotFoundError:
            st.error('Falta el índice local. Prepare el corpus y ejecute unsa-rag index.')
        except (OSError, ValueError, TypeError, KeyError):
            st.error('No se pudo leer el índice local. Compruebe que el archivo sea compatible.')
        else:
            try:
                with st.spinner('Buscando evidencia documental…'):
                    if demo:
                        result = answer_demo(
                            index, question, provider, k, documental,
                            model.strip() if model else None, converse=True,
                        )
                    else:
                        result = answer(index, question, mode, provider, k, documental)
                show_result(result)
            except (OSError, RuntimeError, ValueError, KeyError, TypeError, AttributeError) as exc:
                st.error(provider_error(exc, provider))
