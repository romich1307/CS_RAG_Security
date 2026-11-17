import re
import time
from cs_rag_security.defenses import prepare
from cs_rag_security.generation import generate

WARNINGS = ['Prototipo académico no oficial.', 'La procedencia institucional no certifica vigencia.',
            'OCR pendiente de revisión: cotejar cifras y artículos con el PDF.',
            'Faltan RCU-0435-2017, RCU-0317-2026 y RCU-0590-2023.',
            'RCU-0127-2020 es modificatoria; RCU-0009-2026 afecta una disposición específica.']


def answer(index, question, mode='C_defensa_propuesta', provider='mock', k=5, documental=False, seed=42, hits=None):
    start = time.perf_counter()
    retrieved = index.search(question, k) if hits is None else hits
    kept, messages, log = prepare(question, retrieved, mode)
    # Consulta normativa actual requiere verificación humana, independiente de la defensa.
    reliable = [h for h in kept if h.get('score', 0) >= 0.12 and
                (not h.get('ocr_revision_manual_pendiente', True)) and
                (documental or h.get('normativa_actual_verificada', False))]
    abstain = not reliable
    response = 'Me abstengo: no hay evidencia fiable suficiente o vigencia verificada. Puede consultar fragmentos como material documental provisional.'
    if reliable:
        # Conserva las mismas fronteras de seguridad y metadatos de las tres variantes.
        _, messages, _ = prepare(question, reliable, mode)
        response = generate(messages, reliable, provider, seed)
        if provider != 'mock':
            allowed = {(h['archivo_pdf'], str(h['pagina_pdf'])) for h in reliable}
            citations = re.findall(r'\[([^\[\]]+\.pdf) p\. (\d+)\]', response)
            if not citations or any(c not in allowed for c in citations):
                response = 'Me abstengo: la salida del modelo carece de citas válidas del contexto.'
                abstain = True
    return {'question': question, 'response': response, 'provider': provider, 'mode': mode,
            'documental': documental, 'abstained': abstain, 'warnings': WARNINGS,
            'retrieved': retrieved, 'accepted_ids': [h['chunk_id'] for h in reliable], 'detector_log': log,
            'seconds': time.perf_counter() - start, 'seed': seed, 'top_k': k,
            'retriever': index.method, 'citation_validation': 'solo pertenencia; no certifica entailment'}
