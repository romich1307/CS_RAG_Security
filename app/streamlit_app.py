from html import escape
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError

import streamlit as st

from cs_rag_security.defenses import MODES
from cs_rag_security.demo import PROFILE, answer_demo
from cs_rag_security.pipeline import answer
from cs_rag_security.retrieval import Index
from cs_rag_security.traceability import extract_citations, sanitize_chunk_dict


APP_DIR = Path(__file__).resolve().parent
INDEX_PATH = APP_DIR.parent / 'data/vector_db/index.json'
SAFE_TRACE_FIELDS = (
    'provider', 'mode', 'profile', 'abstained', 'reason', 'retriever',
    'top_k', 'model', 'coverage', 'evaluated_chunks', 'exposed_ids',
)
DEFENSE_LABELS = dict(zip(MODES, ('A  Sin defensa', 'B  Defensa básica', 'C  Defensa propuesta')))
DEMO_LABEL = 'Demostración documental'
PROVIDER_LABELS = {'mock': 'Mock local', 'local': 'Ollama local', 'api': 'API'}
CITATION_AT_LINE_START = re.compile(r'(?m)^\[([^\[\]\r\n]+\.pdf) p\. (\d+)\] ')


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


def presentation(result):
    metadata = result.get('generation_metadata') or {}
    if metadata.get('refusal') or metadata.get('finish_reason') in ('refusal', 'content_filter'):
        response = 'Me abstengo: el modelo rechazó la consulta.'
    else:
        response = result['response']
    sources = result.get('sources')
    if sources is None and not result['abstained']:
        sources = [
            {'archivo': name, 'pagina': page}
            for name, page in dict.fromkeys(extract_citations(response))
        ]
    return response, sources or [], safe_trace(result)


def mock_passages(response, trace, accepted):
    if trace.get('provider') != 'mock' or trace.get('abstained'):
        return None
    matches = list(CITATION_AT_LINE_START.finditer(response))
    locations = [(row.get('archivo_pdf'), str(row.get('pagina_pdf'))) for row in accepted]
    if not matches or [match.groups() for match in matches] != locations:
        return None
    ends = [match.start() for match in matches[1:]] + [len(response)]
    return [response[match.end():end].rstrip('\r\n') for match, end in zip(matches, ends)]


def fragment_markup(number, chunk, passage=''):
    name = escape(str(chunk.get('archivo_pdf') or chunk.get('documento_id') or chunk.get('chunk_id') or ''))
    page = chunk.get('pagina_pdf')
    score = chunk.get('score')
    page_markup = f'<div class="fragment-page">Página {escape(str(page))}</div>' if page is not None else ''
    score_markup = f'<span class="fragment-score">similitud {score:.2f}</span>' if isinstance(score, (int, float)) else ''
    passage_markup = f'<p>{escape(passage)}</p>' if passage else ''
    selected = ' fragment-first' if number == 1 else ''
    return (
        f'<article class="fragment{selected}"><span class="fragment-number">{number:02}</span>'
        f'<div><div class="fragment-title"><strong>{name}</strong>{score_markup}</div>'
        f'{page_markup}{passage_markup}</div></article>'
    )


def show_result(response, sources, trace):
    chunks = trace['evaluated_chunks']
    accepted = [chunk for chunk in chunks if chunk.get('status') == 'accepted']
    passages = mock_passages(response, trace, accepted)

    with st.container(key='resultados'):
        fragments, source = st.columns([815, 525], gap='large')
        with fragments:
            st.subheader('Respuesta del asistente' if trace.get('profile') == 'demo_conversacional_v1' else 'Fragmentos recuperados', anchor=False)
            if passages is None:
                st.text(response)
                rows = accepted if not trace['abstained'] else []
                passages = [''] * len(rows)
            else:
                rows = accepted
            for number, (chunk, passage) in enumerate(zip(rows, passages), start=1):
                st.html(fragment_markup(number, chunk, passage))
            if sources:
                st.subheader('Fuentes citadas', anchor=False)
                for item in sources:
                    st.text(f"{item['archivo']}, página {item['pagina']}")
        with source:
            st.subheader('Fuente en JSON', anchor=False)
            with st.container(key='fuente-json'):
                st.code(json.dumps(trace, ensure_ascii=False, indent=2),
                        language='json', line_numbers=True, wrap_lines=True)


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


st.set_page_config(page_title='Consulta documental UNSA', layout='wide')
st.html('<style>' + (APP_DIR / 'consulta.css').read_text(encoding='utf-8') + '</style>')

with st.container(key='cabecera'):
    st.html('<img class="unsa-logo" src="app/static/logo-unsa.png" alt="Universidad Nacional de San Agustín de Arequipa">')
    st.title('Consulta documental UNSA', anchor=False)
    st.html('<p class="aviso-prototipo">Prototipo académico no oficial</p>')

with st.container(key='consulta'):
    intro = st.empty()

    with st.container(key='formulario'):
        question = st.text_input('Pregunta', placeholder='Escribe tu consulta', label_visibility='collapsed')
        defense_col, provider_col, top_k_col, options_col, submit_col = st.columns(
            [4.9, 2.25, 0.85, 1.2, 1.5], gap='small', vertical_alignment='bottom',
        )
        with defense_col:
            mode = st.radio('Defensa', MODES, index=2, format_func=DEFENSE_LABELS.get,
                            horizontal=True, key='defensa')
        demo = mode == MODES[2] and st.session_state.get(
            'perfil-c', DEMO_LABEL,
        ) == DEMO_LABEL

        provider_values = ('mock', 'local') if demo else ('mock', 'local', 'api')
        if st.session_state.get('proveedor') == 'api' and demo:
            st.session_state['proveedor'] = 'mock'
        with provider_col:
            provider = st.selectbox(
                'Proveedor', provider_values, format_func=PROVIDER_LABELS.get, key='proveedor',
            )
        with top_k_col:
            k = st.selectbox('Top K', tuple(range(1, 11)), index=4, key='top-k')
        with submit_col:
            submitted = st.button('Consultar', type='primary', use_container_width=True)
        with options_col:
            with st.popover('Configuración'):
                st.radio(
                    'Perfil', (DEMO_LABEL, 'Configuración experimental'),
                    key='perfil-c', disabled=mode != MODES[2],
                )
                documental = st.checkbox(
                    'Consulta documental provisional', value=True, key='documental',
                    help='Desmarque esta opción para solicitar una comprobación de vigencia.',
                )
                if demo:
                    st.caption(f'Perfil {PROFILE}. Los extractos se citan con el PDF y la página del índice.')
                else:
                    st.caption('Configuración experimental. A carece de aislamiento de instrucciones.')
                model = None
                if provider == 'local':
                    model = st.text_input(
                        'Modelo instalado en Ollama', os.environ.get('RAG_LOCAL_MODEL') or 'qwen2.5:3b',
                        disabled=not demo,
                    )
                    if not demo:
                        st.caption('Las condiciones históricas usan el modelo configurado en RAG_LOCAL_MODEL.')


query_settings = (question, mode, demo, provider, k, documental, model)
if submitted:
    st.session_state.pop('consulta_resultado', None)
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
                        result = answer_demo(index, question, provider, k, documental, model.strip() if model else None, converse=True)
                    else:
                        result = answer(index, question, mode, provider, k, documental)
                st.session_state['consulta_resultado'] = (query_settings, presentation(result))
            except (OSError, RuntimeError, ValueError, KeyError, TypeError, AttributeError) as exc:
                st.error(provider_error(exc, provider))

previous = st.session_state.get('consulta_resultado')
if previous is not None and previous[0] == query_settings:
    show_result(*previous[1])
else:
    st.session_state.pop('consulta_resultado', None)
    intro.subheader('¿Qué deseas consultar?', anchor=False)

with st.container(key='pie'):
    st.html("""
        <footer class="avisos">
            <div>
                <p>El modo Mock está activo por defecto y muestra extractos de los documentos.</p>
            </div>
            <div>
                <p>La vigencia de cada reglamento se confirma en su fuente oficial.</p>
            </div>
        </footer>
    """)
