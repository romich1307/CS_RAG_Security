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
    generation_metadata = None
    raw_response = None
    if reliable:
        # Conserva las mismas fronteras de seguridad y metadatos de las tres variantes.
        _, messages, _ = prepare(question, reliable, mode)
        gen = generate(messages, reliable, provider, seed, True)
        if isinstance(gen, dict):
            raw_text = gen.get('text')
            response = raw_text if isinstance(raw_text, str) else (str(raw_text) if raw_text is not None else '')
            generation_metadata = gen.get('metadata')
        else:
            response = str(gen) if gen is not None else ''
            generation_metadata = None
        raw_response = response
        if provider != 'mock':
            is_refusal = bool(generation_metadata and (
                generation_metadata.get('refusal') or
                generation_metadata.get('finish_reason') in ('refusal', 'content_filter')
            ))
            if is_refusal:
                refusal_msg = generation_metadata.get('refusal') if generation_metadata else None
                response = f'Me abstengo: el modelo rechazó la consulta ({refusal_msg}).' if refusal_msg else 'Me abstengo: el modelo rechazó la consulta.'
                abstain = True
            elif not response.strip():
                response = 'Me abstengo: el modelo no devolvió contenido.'
                abstain = True
            else:
                allowed = {(h['archivo_pdf'], str(h['pagina_pdf'])) for h in reliable}
                citations = re.findall(r'\[([^\[\]]+\.pdf) p\. (\d+)\]', response)
                if not citations or any(c not in allowed for c in citations):
                    response = 'Me abstengo: la salida del modelo carece de citas válidas del contexto.'
                    abstain = True
    return {'question': question, 'response': response, 'raw_response': raw_response, 'provider': provider, 'mode': mode,
            'documental': documental, 'abstained': abstain, 'warnings': WARNINGS,
            'retrieved': retrieved, 'accepted_ids': [h['chunk_id'] for h in reliable], 'detector_log': log,
            'seconds': time.perf_counter() - start, 'seed': seed, 'top_k': k,
            'retriever': index.method, 'citation_validation': 'solo pertenencia; no certifica entailment',
            'generation_metadata': generation_metadata}
