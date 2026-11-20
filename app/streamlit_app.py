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
        index = Index.load('data/vector_db/index.json')
    except (OSError, FileNotFoundError) as exc:
        st.error(f'No se pudo cargar el índice: {exc}. Primero ejecute unsa-rag index.')
    except Exception as exc:
        st.error(f'Error al inicializar el índice: {exc}')
    else:
        try:
            result = answer(index, question, mode, provider, k, documental)
            st.write(result['response'])
            for warning in result['warnings']:
                st.warning(warning)
            with st.expander('Fuentes, páginas, puntuaciones y trazabilidad'):
                st.json(result)
        except RuntimeError as exc:
            msg = str(exc)
            if '401' in msg:
                st.error('Error de autenticación con el proveedor API (HTTP 401). Verifique las credenciales configuradas (RAG_API_KEY).')
            elif '429' in msg:
                st.error('Límite de solicitudes o cuota excedida en el proveedor API (HTTP 429). Intente nuevamente más tarde.')
            elif 'conexión' in msg.lower() or 'connection' in msg.lower():
                st.error('Error de conexión con el proveedor API. Verifique su acceso a la red.')
            else:
                st.error(f'Error del proveedor API: {msg}')
        except ValueError as exc:
            st.error(f'Error de validación o configuración: {exc}')
        except (OSError, KeyError) as exc:
            st.error(f'No se pudo completar la consulta: {exc}')
