"""Módulo de trazabilidad experimental para CS_RAG_Security (T16).

Define el esquema estandarizado de trazas, registro de fragmentos y motivos de descarte,
decisiones del detector, procedencia por hashes, y separación estricta entre trazas privadas
locales completas y artefactos públicos saneados para control de versiones mediante
listas explícitas de campos autorizados (allowlists).
Reutilizable por el futuro runner experimental T17 y scripts de evaluación.
"""

import csv
import importlib.metadata
import json
import os
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from cs_rag_security.ingestion import digest
from cs_rag_security.ingestion.normativa import historical_hit

# Versiones fijadas de prompts por condición experimental
PROMPT_VERSIONS: Dict[str, str] = {
    'A_sin_defensa': 'v1',
    'B_defensa_basica': 'v1',
    'C_defensa_propuesta': 'v3',
}

# Versión por defecto del detector heurístico (actualizable con T15)
DEFAULT_DETECTOR_VERSION: str = 'heuristic_v1'
DETECTOR_VERSION: str = DEFAULT_DETECTOR_VERSION

# Motivos estándar de descarte de fragmentos
DISCARD_REASON_DETECTOR: str = 'detector_suspicious'
DISCARD_REASON_HISTORICAL: str = 'documento_historico'
DISCARD_REASON_SCORE: str = 'score_insuficiente'
DISCARD_REASON_OCR_PENDING: str = 'ocr_revision_pendiente'
DISCARD_REASON_NORMATIVE_UNVERIFIED: str = 'normativa_no_verificada'
DISCARD_REASON_OTHER: str = 'descarte_otro'

# Motivos estándar de abstención del pipeline
ABSTENTION_REASON_INSUFFICIENT_EVIDENCE: str = 'evidencia_insuficiente_o_no_fiable'
ABSTENTION_REASON_INVALID_CITATIONS: str = 'citas_invalidas_o_ausentes'
ABSTENTION_REASON_MODEL_REFUSAL: str = 'rechazo_del_modelo'
ABSTENTION_REASON_EMPTY_OUTPUT: str = 'modelo_vacio'
ABSTENTION_REASON_NORMATIVE_UNVERIFIED: str = 'normativa_no_verificada'
ABSTENTION_REASON_OTHER: str = 'abstencion_otra'

# Expresión regular canónica para extracción de citas [archivo.pdf p. N]
CITATION_REGEX: re.Pattern = re.compile(r'\[([^\[\]]+\.pdf) p\. (\d+)\]')

# ---------------------------------------------------------------------------
# Listas explícitas de campos autorizados para saneamiento público (Allowlists)
# Ningún campo fuera de estas listas puede figurar en los artefactos para Git.
# ---------------------------------------------------------------------------

ALLOWED_CHUNK_FIELDS = frozenset({
    'rank',
    'chunk_id',
    'documento_id',
    'archivo_pdf',
    'pagina_pdf',
    'score',
    'status',
    'discard_reasons',
    'detector_suspicious',
    'detector_score',
    'detector_reasons',
    'ocr_revision_manual_pendiente',
    'normativa_actual_verificada',
})

ALLOWED_DETECTOR_LOG_FIELDS = frozenset({
    'chunk_id',
    'suspicious',
    'score',
    'reasons',
    'detector',
})

ALLOWED_CITATION_FIELDS = frozenset({
    'archivo',
    'pagina',
})

ALLOWED_PARAMETER_FIELDS = frozenset({
    'seed',
    'temperature',
    'top_k',
    'documental',
    'evidence_threshold',
})

ALLOWED_TOKEN_FIELDS = frozenset({
    'prompt_tokens',
    'completion_tokens',
    'total_tokens',
})

ALLOWED_TRACE_FIELDS = frozenset({
    'run_id',
    'case_id',
    'id',
    'case_kind',
    'mode',
    'condition',
    'prompt_version',
    'provider',
    'model',
    'model_digest',
    'parameters',
    'generation_performed',
    'abstained',
    'abstention_reason',
    'citations_raw',
    'citations_final',
    'citations_valid',
    'allowed_citations',
    'retrieved_chunks',
    'accepted_chunks',
    'discarded_chunks',
    'evaluated_chunks',
    'accepted_ids',
    'discarded_ids',
    'retrieved_ids',
    'detector_version',
    'detector_applied',
    'detector_suspicious_count',
    'any_detector_suspicious',
    'detector_log',
    'latency_generation_seconds',
    'latency_pipeline_seconds',
    'latency_seconds',
    'pipeline_seconds',
    'tokens',
    'response',
})


def extract_citations(text: Optional[str]) -> List[Tuple[str, str]]:
    """Extrae tuplas (archivo_pdf, pagina_str) de citas formales en formato [archivo.pdf p. N]."""
    if not text or not isinstance(text, str):
        return []
    return CITATION_REGEX.findall(text)


def validate_citations(
    citations: List[Tuple[str, str]],
    allowed_chunks: List[Dict[str, Any]],
    abstained: bool = False,
) -> Tuple[bool, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Valida la pertenencia estricta de las citas extraídas al conjunto de fragmentos aceptados.

    Retorna:
        (citations_valid, citations_list, allowed_list)
    """
    allowed_set = {
        (str(h.get('archivo_pdf')), str(h.get('pagina_pdf')))
        for h in allowed_chunks
        if h.get('archivo_pdf') is not None and h.get('pagina_pdf') is not None
    }
    allowed_list = [
        {'archivo': str(h.get('archivo_pdf')), 'pagina': int(h.get('pagina_pdf', 0))}
        for h in allowed_chunks
        if h.get('archivo_pdf') is not None and h.get('pagina_pdf') is not None
    ]
    citations_list = [{'archivo': c[0], 'pagina': int(c[1])} for c in citations]

    if abstained or not citations:
        is_valid = False
    else:
        is_valid = all(c in allowed_set for c in citations)
    return is_valid, citations_list, allowed_list


def evaluate_chunk_filtering(
    chunk: Dict[str, Any],
    detector_decision: Optional[Dict[str, Any]],
    mode: str,
    documental: bool = False,
    evidence_threshold: float = 0.12,
) -> Tuple[str, List[str]]:
    """Determina si un fragmento individual es aceptado o descartado, identificando los motivos.

    Retorna:
        (status, discard_reasons) donde status es 'accepted' o 'discarded'.
    """
    reasons: List[str] = []

    # 1. Filtro del detector (se aplica como exclusión únicamente en Modo C)
    if mode == 'C_defensa_propuesta':
        if detector_decision and detector_decision.get('suspicious'):
            reasons.append(DISCARD_REASON_DETECTOR)

    # 2. Exclusión de documento histórico no vigente
    if historical_hit(chunk):
        reasons.append(DISCARD_REASON_HISTORICAL)

    # 3. Puntuación insuficiente respecto al umbral de similitud
    score = chunk.get('score', 0)
    if score is None or float(score) < evidence_threshold:
        reasons.append(DISCARD_REASON_SCORE)

    # 4. Revisión manual OCR pendiente (bloquea fundamentación en todos los modos)
    if chunk.get('ocr_revision_manual_pendiente', True):
        reasons.append(DISCARD_REASON_OCR_PENDING)

    # 5. Normativa actual no verificada (en consultas normativas vigentes no documentales)
    if not documental and not chunk.get('normativa_actual_verificada', False):
        reasons.append(DISCARD_REASON_NORMATIVE_UNVERIFIED)

    status = 'accepted' if not reasons else 'discarded'
    return status, reasons


def evaluate_retrieved_chunks(
    retrieved: List[Dict[str, Any]],
    detector_log: List[Dict[str, Any]],
    mode: str,
    documental: bool = False,
    evidence_threshold: float = 0.12,
    kept: Optional[List[Dict[str, Any]]] = None,
    reliable: Optional[List[Dict[str, Any]]] = None,
    detector_version: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Evalúa la lista ordenada de fragmentos recuperados, preservando orden y puntuaciones.

    Si se suministra `reliable` (desde el pipeline), se garantiza identidad matemática con
    los fragmentos efectivamente enviados al generador sin alterar el comportamiento.

    Retorna:
        evaluated_chunks: lista completa ordenada (rank 1..k) con estatus y motivos de descarte.
        accepted_chunks: lista de fragmentos originales que resultaron aceptados.
        discarded_chunks: lista de fragmentos descartados con sus motivos de descarte.
    """
    log_by_id = {
        d.get('chunk_id'): d
        for d in detector_log
        if isinstance(d, dict) and 'chunk_id' in d
    }

    evaluated_chunks: List[Dict[str, Any]] = []
    accepted_chunks: List[Dict[str, Any]] = []
    discarded_chunks: List[Dict[str, Any]] = []

    reliable_ids = {h.get('chunk_id') for h in reliable} if reliable is not None else None
    kept_ids = {h.get('chunk_id') for h in kept} if kept is not None else None

    for rank, chunk in enumerate(retrieved, start=1):
        cid = chunk.get('chunk_id')
        det_dec = log_by_id.get(cid)

        # Si el pipeline ya calculó reliable, respetarlo fielmente como decisión real
        if reliable_ids is not None:
            is_accepted = cid in reliable_ids
            status = 'accepted' if is_accepted else 'discarded'
            if is_accepted:
                reasons = []
            else:
                reasons = []
                # Exclusión por detector en prepare (modo C)
                if kept_ids is not None and cid not in kept_ids:
                    reasons.append(DISCARD_REASON_DETECTOR)
                elif mode == 'C_defensa_propuesta' and det_dec and det_dec.get('suspicious'):
                    reasons.append(DISCARD_REASON_DETECTOR)
                if historical_hit(chunk):
                    reasons.append(DISCARD_REASON_HISTORICAL)
                score = chunk.get('score', 0)
                if score is None or float(score) < evidence_threshold:
                    reasons.append(DISCARD_REASON_SCORE)
                if chunk.get('ocr_revision_manual_pendiente', True):
                    reasons.append(DISCARD_REASON_OCR_PENDING)
                if not documental and not chunk.get('normativa_actual_verificada', False):
                    reasons.append(DISCARD_REASON_NORMATIVE_UNVERIFIED)
                if not reasons:
                    reasons.append(DISCARD_REASON_OTHER)
        else:
            status, reasons = evaluate_chunk_filtering(
                chunk=chunk,
                detector_decision=det_dec,
                mode=mode,
                documental=documental,
                evidence_threshold=evidence_threshold,
            )

        det_version_resolved = (
            detector_version
            or (det_dec.get('detector') if det_dec else None)
            or DEFAULT_DETECTOR_VERSION
        )

        chunk_eval: Dict[str, Any] = {
            'rank': rank,
            'chunk_id': cid,
            'documento_id': chunk.get('documento_id'),
            'archivo_pdf': chunk.get('archivo_pdf'),
            'pagina_pdf': chunk.get('pagina_pdf'),
            'score': chunk.get('score'),
            'status': status,
            'discard_reasons': reasons,
            'detector_suspicious': det_dec.get('suspicious', False) if det_dec else False,
            'detector_score': det_dec.get('score', 0) if det_dec else 0,
            'detector_reasons': det_dec.get('reasons', []) if det_dec else [],
            'ocr_revision_manual_pendiente': chunk.get('ocr_revision_manual_pendiente', True),
            'normativa_actual_verificada': chunk.get('normativa_actual_verificada', False),
        }
        if 'texto' in chunk:
            chunk_eval['texto'] = chunk['texto']

        evaluated_chunks.append(chunk_eval)

        if status == 'accepted':
            accepted_chunks.append(chunk)
        else:
            discarded_chunks.append(chunk_eval)

    # Si se suministró reliable original del pipeline, garantizar identidad de instancias
    if reliable is not None:
        accepted_chunks = reliable

    return evaluated_chunks, accepted_chunks, discarded_chunks


def determine_abstention_reason(res: Dict[str, Any]) -> str:
    """Clasifica el motivo canónico de abstención diferenciando ausencia de generación de modelo vacío."""
    if not res.get('abstained'):
        return ''
    response = res.get('response', '') or ''
    raw_response = res.get('raw_response')
    gen_meta = res.get('generation_metadata') or {}
    generation_performed = bool(raw_response is not None or gen_meta)

    # 1. Rechazo explícito del generador
    if gen_meta and (
        gen_meta.get('refusal')
        or gen_meta.get('finish_reason') in ('refusal', 'content_filter')
    ):
        return ABSTENTION_REASON_MODEL_REFUSAL
    if 'rechazó la consulta' in response:
        return ABSTENTION_REASON_MODEL_REFUSAL

    # 2. Respuesta vacía emitida por el generador
    if 'no devolvió contenido' in response or (
        generation_performed and isinstance(raw_response, str) and not raw_response.strip()
    ):
        return ABSTENTION_REASON_EMPTY_OUTPUT

    # 3. Citas inválidas o ausentes
    if 'carece de citas válidas' in response:
        return ABSTENTION_REASON_INVALID_CITATIONS

    # 4. Ausencia de generación previa por falta de evidencia o vigencia
    if 'no hay evidencia fiable suficiente' in response or 'vigencia verificada' in response or not generation_performed:
        return ABSTENTION_REASON_INSUFFICIENT_EVIDENCE

    # 5. Normativa no verificada
    if 'normativa' in response and 'verific' in response:
        return ABSTENTION_REASON_NORMATIVE_UNVERIFIED

    return ABSTENTION_REASON_OTHER


def build_trace_record(
    run_id: str,
    case_id: str,
    mode: str,
    pipeline_result: Dict[str, Any],
    case_kind: str = 'gold',
    question: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    model_digest: Optional[str] = None,
    prompt_version: Optional[str] = None,
    detector_version: Optional[str] = None,
    seed: int = 42,
    top_k: int = 5,
    temperature: float = 0.0,
    documental: bool = False,
    evidence_threshold: float = 0.12,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Construye un registro de traza estructurado y exhaustivo para una consulta y condición."""
    raw_response = pipeline_result.get('raw_response')
    final_response = pipeline_result.get('response', '')
    abstained = pipeline_result.get('abstained', False)
    abstention_reason = determine_abstention_reason(pipeline_result)

    gen_meta = pipeline_result.get('generation_metadata') or {}
    generation_performed = bool(raw_response is not None or gen_meta)

    # Fragmentos evaluados
    if 'evaluated_chunks' in pipeline_result and 'discarded_chunks' in pipeline_result:
        evaluated_chunks = pipeline_result['evaluated_chunks']
        discarded_chunks = pipeline_result['discarded_chunks']
        retrieved_raw = pipeline_result.get('retrieved', [])
        accepted_ids = pipeline_result.get('accepted_ids', [])
        accepted_chunks = [h for h in retrieved_raw if h.get('chunk_id') in accepted_ids]
    else:
        retrieved_raw = pipeline_result.get('retrieved', [])
        detector_log = pipeline_result.get('detector_log', [])
        evaluated_chunks, accepted_chunks, discarded_chunks = evaluate_retrieved_chunks(
            retrieved=retrieved_raw,
            detector_log=detector_log,
            mode=mode,
            documental=documental,
            evidence_threshold=evidence_threshold,
            detector_version=detector_version,
        )
        accepted_ids = [c['chunk_id'] for c in accepted_chunks]

    accepted_ids_list = accepted_ids or [
        c['chunk_id'] for c in evaluated_chunks if c.get('status') == 'accepted'
    ]
    discarded_ids_list = [
        c['chunk_id'] for c in evaluated_chunks if c.get('status') == 'discarded'
    ]
    retrieved_ids_list = [c.get('chunk_id') for c in retrieved_raw if 'chunk_id' in c]

    # Citas
    raw_citations_tuples = extract_citations(raw_response)
    final_citations_tuples = extract_citations(final_response)
    citations_valid, final_citations_list, allowed_citations_list = validate_citations(
        citations=final_citations_tuples,
        allowed_chunks=accepted_chunks,
        abstained=abstained,
    )
    raw_citations_list = [{'archivo': c[0], 'pagina': int(c[1])} for c in raw_citations_tuples]

    # Metadatos de generación y tokens
    resolved_provider = provider or pipeline_result.get('provider') or gen_meta.get('provider', 'mock')
    resolved_model = model or gen_meta.get('model') or ('qwen2.5:3b' if resolved_provider == 'local' else 'mock_extractivo_v1')
    resolved_prompt_version = prompt_version or pipeline_result.get('prompt_version') or PROMPT_VERSIONS.get(mode, 'v1')

    # Detector dinámico (T15 ready)
    det_log = pipeline_result.get('detector_log', [])
    resolved_detector_version = (
        detector_version
        or pipeline_result.get('detector_version')
        or (det_log[0].get('detector') if det_log and isinstance(det_log[0], dict) and det_log[0].get('detector') else None)
        or DEFAULT_DETECTOR_VERSION
    )

    gen_latency = gen_meta.get('latency_seconds')
    pipe_latency = pipeline_result.get('seconds')
    tokens_data = gen_meta.get('tokens')

    det_suspicious_count = sum(1 for d in det_log if isinstance(d, dict) and d.get('suspicious'))
    any_det_suspicious = det_suspicious_count > 0

    record: Dict[str, Any] = {
        'run_id': run_id,
        'case_id': case_id,
        'id': case_id,
        'case_kind': case_kind,
        'mode': mode,
        'condition': mode,
        'prompt_version': resolved_prompt_version,
        'provider': resolved_provider,
        'model': resolved_model,
        'model_digest': model_digest,
        'parameters': {
            'seed': seed,
            'temperature': temperature,
            'top_k': top_k,
            'documental': documental,
            'evidence_threshold': evidence_threshold,
        },
        'generation_performed': generation_performed,
        'question': question or pipeline_result.get('question'),
        'raw_response': raw_response,
        'response': final_response,
        'abstained': abstained,
        'abstention_reason': abstention_reason,
        'citations_raw': raw_citations_list,
        'citations_final': final_citations_list,
        'citations_valid': citations_valid,
        'allowed_citations': allowed_citations_list,
        'retrieved_chunks': evaluated_chunks,
        'accepted_chunks': [
            {
                'rank': c.get('rank', i),
                'chunk_id': c.get('chunk_id'),
                'documento_id': c.get('documento_id'),
                'archivo_pdf': c.get('archivo_pdf'),
                'pagina_pdf': c.get('pagina_pdf'),
                'score': c.get('score'),
                'ocr_revision_manual_pendiente': c.get('ocr_revision_manual_pendiente', True),
                'normativa_actual_verificada': c.get('normativa_actual_verificada', False),
                **({'texto': c['texto']} if 'texto' in c else {}),
            }
            for i, c in enumerate(accepted_chunks, start=1)
        ],
        'discarded_chunks': discarded_chunks,
        'evaluated_chunks': evaluated_chunks,
        'accepted_ids': accepted_ids_list,
        'discarded_ids': discarded_ids_list,
        'retrieved_ids': retrieved_ids_list,
        'detector_version': resolved_detector_version,
        'detector_applied': mode == 'C_defensa_propuesta',
        'detector_log': det_log,
        'detector_suspicious_count': det_suspicious_count,
        'any_detector_suspicious': any_det_suspicious,
        'latency_generation_seconds': gen_latency,
        'latency_pipeline_seconds': pipe_latency,
        'latency_seconds': gen_latency if gen_latency is not None else pipe_latency,
        'pipeline_seconds': pipe_latency,
        'tokens': tokens_data,
        'retriever': pipeline_result.get('retriever', 'tfidf_cosine'),
        'warnings': pipeline_result.get('warnings', []),
    }

    if extra_metadata:
        record['extra_metadata'] = extra_metadata

    return record


def sanitize_chunk_dict(chunk: Dict[str, Any]) -> Dict[str, Any]:
    """Copia exclusivamente los campos autorizados en ALLOWED_CHUNK_FIELDS.

    Garantiza que ningún campo de texto (texto, text, contenido, payload, etc.) pueda filtrarse.
    """
    return {k: v for k, v in chunk.items() if k in ALLOWED_CHUNK_FIELDS}


def sanitize_detector_log_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """Copia exclusivamente los campos autorizados en ALLOWED_DETECTOR_LOG_FIELDS."""
    return {k: v for k, v in d.items() if k in ALLOWED_DETECTOR_LOG_FIELDS}


def sanitize_trace_record(
    record: Dict[str, Any],
    redact_gold_response: bool = True,
    redact_attack_response: bool = True,
) -> Dict[str, Any]:
    """Sanea una traza individual mediante una lista explícita de campos autorizados (allowlist).

    Reglas estrictas de confidencialidad:
    1. 'question' y 'raw_response' se excluyen incondicionalmente.
    2. Las estructuras anidadas ('retrieved_chunks', 'accepted_chunks', 'discarded_chunks',
       'evaluated_chunks', 'detector_log', 'citations', 'parameters') se filtran con allowlists explícitas.
    3. Si la respuesta final no es una abstención:
       - Si case_kind == 'gold' -> '[CONTENIDO_CORPUS_PRIVADO_PROTEGIDO]'
       - Si case_kind en ('synthetic_attack', 'attack') -> '[RESPUESTA_SINTETICA_PROTEGIDA]'
    """
    retrieved = [sanitize_chunk_dict(c) for c in record.get('retrieved_chunks', []) if isinstance(c, dict)]
    accepted = [sanitize_chunk_dict(c) for c in record.get('accepted_chunks', []) if isinstance(c, dict)]
    discarded = [sanitize_chunk_dict(c) for c in record.get('discarded_chunks', []) if isinstance(c, dict)]
    evaluated = [sanitize_chunk_dict(c) for c in record.get('evaluated_chunks', []) if isinstance(c, dict)]

    det_log_sanitized = [
        sanitize_detector_log_dict(d)
        for d in record.get('detector_log', [])
        if isinstance(d, dict)
    ]

    raw_params = record.get('parameters') or {}
    sanitized_params = {k: raw_params[k] for k in ALLOWED_PARAMETER_FIELDS if k in raw_params}

    raw_tokens = record.get('tokens')
    sanitized_tokens = (
        {k: raw_tokens[k] for k in ALLOWED_TOKEN_FIELDS if k in raw_tokens}
        if isinstance(raw_tokens, dict)
        else None
    )

    sanitized_citations_raw = [
        {k: c[k] for k in ALLOWED_CITATION_FIELDS if k in c}
        for c in record.get('citations_raw', [])
        if isinstance(c, dict)
    ]
    sanitized_citations_final = [
        {k: c[k] for k in ALLOWED_CITATION_FIELDS if k in c}
        for c in record.get('citations_final', [])
        if isinstance(c, dict)
    ]
    sanitized_allowed_citations = [
        {k: c[k] for k in ALLOWED_CITATION_FIELDS if k in c}
        for c in record.get('allowed_citations', [])
        if isinstance(c, dict)
    ]

    final_resp = record.get('response', '')
    abstained = bool(record.get('abstained', False))
    case_kind = record.get('case_kind', 'gold')

    if not abstained:
        if case_kind == 'gold' and redact_gold_response:
            final_resp = '[CONTENIDO_CORPUS_PRIVADO_PROTEGIDO]'
        elif case_kind in ('synthetic_attack', 'attack') and redact_attack_response:
            final_resp = '[RESPUESTA_SINTETICA_PROTEGIDA]'

    sanitized: Dict[str, Any] = {
        'run_id': record.get('run_id'),
        'case_id': record.get('case_id', record.get('id')),
        'id': record.get('id', record.get('case_id')),
        'case_kind': case_kind,
        'mode': record.get('mode', record.get('condition')),
        'condition': record.get('condition', record.get('mode')),
        'prompt_version': record.get('prompt_version', PROMPT_VERSIONS.get(record.get('mode', ''), 'v1')),
        'provider': record.get('provider'),
        'model': record.get('model'),
        'model_digest': record.get('model_digest'),
        'parameters': sanitized_params,
        'generation_performed': bool(record.get('generation_performed', False)),
        'abstained': abstained,
        'abstention_reason': record.get('abstention_reason', ''),
        'citations_raw': sanitized_citations_raw,
        'citations_final': sanitized_citations_final,
        'citations_valid': bool(record.get('citations_valid', False)),
        'allowed_citations': sanitized_allowed_citations,
        'retrieved_chunks': retrieved,
        'accepted_chunks': accepted,
        'discarded_chunks': discarded,
        'evaluated_chunks': evaluated,
        'accepted_ids': list(record.get('accepted_ids', [])),
        'discarded_ids': list(record.get('discarded_ids', [])),
        'retrieved_ids': list(record.get('retrieved_ids', [])),
        'detector_version': record.get('detector_version', DEFAULT_DETECTOR_VERSION),
        'detector_applied': bool(record.get('detector_applied', record.get('mode') == 'C_defensa_propuesta')),
        'detector_log': det_log_sanitized,
        'detector_suspicious_count': int(record.get('detector_suspicious_count', 0)),
        'any_detector_suspicious': bool(record.get('any_detector_suspicious', False)),
        'latency_generation_seconds': record.get('latency_generation_seconds', record.get('latency_seconds')),
        'latency_pipeline_seconds': record.get('latency_pipeline_seconds', record.get('pipeline_seconds')),
        'latency_seconds': record.get('latency_seconds', record.get('latency_generation_seconds')),
        'pipeline_seconds': record.get('pipeline_seconds', record.get('latency_pipeline_seconds')),
        'tokens': sanitized_tokens,
        'response': final_resp,
    }

    # Asegurar que ninguna clave fuera de ALLOWED_TRACE_FIELDS esté en la salida
    return {k: v for k, v in sanitized.items() if k in ALLOWED_TRACE_FIELDS}


def sanitize_traces(
    records: List[Dict[str, Any]],
    redact_gold_response: bool = True,
    redact_attack_response: bool = True,
) -> List[Dict[str, Any]]:
    """Sanea una lista de trazas completas asegurando la no filtración de datos confidenciales."""
    return [
        sanitize_trace_record(
            r,
            redact_gold_response=redact_gold_response,
            redact_attack_response=redact_attack_response,
        )
        for r in records
    ]


def get_git_commit() -> str:
    """Obtiene el hash commit actual de HEAD."""
    try:
        res = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except Exception:
        return 'unknown'


def is_git_dirty() -> bool:
    """Indica si el árbol de trabajo de Git tiene modificaciones no comprometidas."""
    try:
        res = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            check=True
        )
        return bool(res.stdout.strip())
    except Exception:
        return False


def is_path_git_ignored(path: Union[str, Path], repo_root: Optional[Union[str, Path]] = None) -> bool:
    """Verifica si Git ignora efectivamente la ruta especificada mediante 'git check-ignore'."""
    p = Path(path).resolve()
    root = Path(repo_root).resolve() if repo_root else Path(__file__).resolve().parents[2]
    try:
        rel_path = p.relative_to(root)
        target = f"{rel_path.as_posix()}/" if p.is_dir() or not p.suffix else rel_path.as_posix()
        res = subprocess.run(
            ['git', 'check-ignore', '-q', target],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        return res.returncode == 0
    except ValueError:
        # La ruta está fuera del árbol de trabajo del repositorio (ej. almacenamiento externo o /tmp)
        posix_str = p.as_posix()
        return any(
            pat in posix_str
            for pat in ('_local', '_private', '_backup', 'raw_traces', 'private_traces')
        )
    except Exception:
        return False


def compute_directory_source_hashes(root_dir: Union[str, Path], pattern: str = '*.py') -> Dict[str, str]:
    """Calcula los hashes SHA-256 de todos los archivos fuente coincidentes de forma determinista."""
    root = Path(root_dir)
    if not root.exists():
        return {}
    return {str(p): digest(p) for p in sorted(root.rglob(pattern)) if p.is_file()}


def build_run_manifest(
    run_id: str,
    task_name: str,
    description: str,
    evaluated_cases: List[str],
    modes: List[str],
    provider: str,
    model: str,
    started_utc: str,
    finished_utc: str,
    model_digest: Optional[str] = None,
    detector_version: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    index_path: Path = Path('data/vector_db/index.json'),
    gold_path: Path = Path('data/corpus_unsa/03_Preguntas_Respuestas/gold_questions.json'),
    attacks_path: Optional[Path] = Path('experiments/attacks.jsonl'),
    src_dir: Path = Path('src'),
    scripts_dir: Path = Path('scripts'),
    extra_hashes: Optional[Dict[str, Any]] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Genera el manifiesto exhaustivo de procedencia para una ejecución experimental."""
    src_hashes = compute_directory_source_hashes(src_dir, '*.py')
    scripts_hashes = compute_directory_source_hashes(scripts_dir, '*.py')

    hashes_dict: Dict[str, Any] = {
        'index_sha256': digest(index_path) if index_path and index_path.exists() else None,
        'gold_sha256': digest(gold_path) if gold_path and gold_path.exists() else None,
        'attacks_sha256': digest(attacks_path) if attacks_path and attacks_path.exists() else None,
        'src_sha256': src_hashes,
        'scripts_sha256': scripts_hashes,
    }
    if extra_hashes:
        hashes_dict.update(extra_hashes)

    installed_versions = {}
    for pkg in ('pytest', 'streamlit', 'onnxruntime', 'numpy'):
        try:
            installed_versions[pkg] = importlib.metadata.version(pkg)
        except Exception:
            pass

    try:
        pkg_version = importlib.metadata.version('cs-rag-security')
    except Exception:
        pkg_version = '0.1.0'

    resolved_detector_version = detector_version or DEFAULT_DETECTOR_VERSION

    manifest: Dict[str, Any] = {
        'run_id': run_id,
        'tarea': task_name,
        'descripcion': description,
        'condiciones_evaluadas': modes,
        'versiones_prompt': {m: PROMPT_VERSIONS.get(m, 'v1') for m in modes},
        'proveedor': provider,
        'modelo': model,
        'modelo_digest': model_digest,
        'parametros': parameters or {
            'temperature': 0,
            'seed': 42,
            'top_k': 5,
            'documental': True,
            'evidence_threshold': 0.12,
        },
        'entorno': {
            'commit_git': get_git_commit(),
            'git_dirty': is_git_dirty(),
            'python_version': platform.python_version(),
            'package_version': pkg_version,
            'dependency_versions': installed_versions,
        },
        'started_utc': started_utc,
        'finished_utc': finished_utc,
        'hashes': hashes_dict,
        'detector_version': resolved_detector_version,
        'casos_evaluados': evaluated_cases,
        'total_casos': len(evaluated_cases),
        'total_trazas_esperadas': len(evaluated_cases) * len(modes),
        'politica_privacidad': (
            'Las trazas versionadas en Git no contienen texto de enunciados gold, '
            'fragmentos del corpus ni respuestas raw del LLM. Las trazas completas '
            'se conservan únicamente en directorios locales no versionados.'
        ),
    }

    if extra_metadata:
        manifest['extra'] = extra_metadata

    return manifest


def ensure_unique_output_dir(out_dir: Union[str, Path]) -> Path:
    """Asegura la creación de un directorio nuevo impidiendo sobrescritura de ejecuciones previas."""
    p = Path(out_dir)
    if p.exists():
        raise FileExistsError(
            f"El directorio de salida ya existe y no puede ser reutilizado ni sobrescrito: {p}"
        )
    p.mkdir(parents=True, exist_ok=False)
    return p


def write_traces_json(path: Union[str, Path], records: List[Dict[str, Any]], indent: int = 2) -> None:
    """Escribe trazas en formato JSON con codificación UTF-8."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(records, ensure_ascii=False, indent=indent), encoding='utf-8')


def write_traces_csv(path: Union[str, Path], records: List[Dict[str, Any]]) -> None:
    """Escribe trazas saneadas en formato CSV con telemetría, métricas y sin texto privado."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        'run_id', 'case_id', 'case_kind', 'mode', 'prompt_version',
        'provider', 'model', 'model_digest', 'seed', 'temperature', 'top_k', 'documental',
        'generation_performed', 'abstained', 'abstention_reason', 'citations_valid', 'citations_count',
        'retrieved_count', 'accepted_count', 'discarded_count', 'discard_reasons',
        'detector_applied', 'detector_suspicious_count', 'any_detector_suspicious',
        'latency_generation_seconds', 'latency_pipeline_seconds', 'latency_seconds', 'pipeline_seconds',
        'prompt_tokens', 'completion_tokens', 'total_tokens', 'response'
    ]
    rows = []
    for r in records:
        tokens = r.get('tokens') or {}
        params = r.get('parameters') or {}
        discard_reasons_set = set()
        for c in r.get('discarded_chunks', []):
            if isinstance(c, dict):
                for reason in c.get('discard_reasons', []):
                    discard_reasons_set.add(reason)

        row = {
            'run_id': r.get('run_id', ''),
            'case_id': r.get('case_id', r.get('id', '')),
            'case_kind': r.get('case_kind', ''),
            'mode': r.get('mode', r.get('condition', '')),
            'prompt_version': r.get('prompt_version', ''),
            'provider': r.get('provider', ''),
            'model': r.get('model', ''),
            'model_digest': r.get('model_digest', '') or '',
            'seed': params.get('seed', r.get('seed', '')),
            'temperature': params.get('temperature', 0),
            'top_k': params.get('top_k', r.get('top_k', '')),
            'documental': params.get('documental', r.get('documental', False)),
            'generation_performed': r.get('generation_performed', False),
            'abstained': r.get('abstained', False),
            'abstention_reason': r.get('abstention_reason', ''),
            'citations_valid': r.get('citations_valid', False),
            'citations_count': len(r.get('citations_final', [])),
            'retrieved_count': len(r.get('retrieved_chunks', [])),
            'accepted_count': len(r.get('accepted_chunks', [])),
            'discarded_count': len(r.get('discarded_chunks', [])),
            'discard_reasons': '|'.join(sorted(discard_reasons_set)),
            'detector_applied': r.get('detector_applied', False),
            'detector_suspicious_count': r.get('detector_suspicious_count', 0),
            'any_detector_suspicious': r.get('any_detector_suspicious', False),
            'latency_generation_seconds': r.get('latency_generation_seconds', r.get('latency_seconds', '')),
            'latency_pipeline_seconds': r.get('latency_pipeline_seconds', r.get('pipeline_seconds', '')),
            'latency_seconds': r.get('latency_seconds', r.get('latency_generation_seconds', '')),
            'pipeline_seconds': r.get('pipeline_seconds', r.get('latency_pipeline_seconds', '')),
            'prompt_tokens': tokens.get('prompt_tokens', '') if tokens.get('prompt_tokens') is not None else '',
            'completion_tokens': tokens.get('completion_tokens', '') if tokens.get('completion_tokens') is not None else '',
            'total_tokens': tokens.get('total_tokens', '') if tokens.get('total_tokens') is not None else '',
            'response': r.get('response', ''),
        }
        rows.append(row)

    with p.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_experimental_run(
    output_dir: Union[str, Path],
    manifest: Dict[str, Any],
    raw_traces: List[Dict[str, Any]],
    private_dir: Optional[Union[str, Path]] = None,
    redact_gold_response: bool = True,
    redact_attack_response: bool = True,
) -> Tuple[Path, Optional[Path]]:
    """Persiste los artefactos de una corrida experimental respetando la separación estricta de privacidad.

    - En output_dir: guarda manifest.json, traces.json y traces.csv totalmente saneados (sin texto privado).
    - En private_dir (opcional): verifica que esté efectivamente ignorado por Git y guarda trazas completas.
    """
    out_path = ensure_unique_output_dir(output_dir)

    # 1. Guardar trazas saneadas para Git
    sanitized_traces = sanitize_traces(
        raw_traces,
        redact_gold_response=redact_gold_response,
        redact_attack_response=redact_attack_response,
    )
    write_traces_json(out_path / 'traces.json', sanitized_traces)
    write_traces_csv(out_path / 'traces.csv', sanitized_traces)
    (out_path / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    # 2. Guardar trazas completas privadas en directorio protegido
    priv_path = None
    if private_dir:
        priv_p = Path(private_dir)
        if not is_path_git_ignored(priv_p):
            raise ValueError(
                f"Error de seguridad: la ruta privada '{priv_p}' no está ignorada por Git. "
                f"Verifique las reglas de .gitignore antes de persistir datos confidenciales."
            )
        priv_path = ensure_unique_output_dir(priv_p)
        write_traces_json(priv_path / 'private_traces.json', raw_traces)
        write_traces_json(priv_path / 'raw_traces.json', raw_traces)
        write_traces_csv(priv_path / 'private_traces.csv', raw_traces)
        private_manifest = {**manifest, 'es_privado': True, 'contiene_texto_corpus': True}
        (priv_path / 'manifest.json').write_text(json.dumps(private_manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    return out_path, priv_path
