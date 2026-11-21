"""Módulo para el cálculo de métricas de calidad de respuestas (T18).

Implementa las métricas de calidad de respuestas basadas en la rúbrica oficial T10 v0.2:
- Exactitud humana de contenido (correcta, parcial, incorrecta).
- Tasa de abstención y adecuación (adecuadas vs. inadecuadas).
- Validez y sustento de citas (pertenencia al contexto vs. sustento semántico real).
- Separación de respuesta post-pipeline y respuesta original del LLM (llm_raw).
- Comparaciones pareadas entre condiciones experimentales A/B/C sobre casos comunes.
- Resolución rigurosa de consensos y registro de desacuerdos sin elecciones arbitrarias.
- Diagnóstico de abstenciones fundamentado en motivos formales de T16.
- Tratamiento formal de exclusiones, revisiones pendientes y denominadores cero sin inventar datos.
- Exportación en formatos JSON y CSV compatibles con T20 y publicación científica.
"""

import csv
import json
import math
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from cs_rag_security.defenses import MODES
from cs_rag_security.traceability import ABSTENTION_REASON_INVALID_CITATIONS

# Condiciones experimentales estándar
CONDITIONS: Tuple[str, ...] = MODES  # ('A_sin_defensa', 'B_defensa_basica', 'C_defensa_propuesta')

# Objetivos / orígenes de respuesta
TARGET_PIPELINE: str = 'pipeline'
TARGET_LLM_RAW: str = 'llm_raw'
TARGETS: Tuple[str, ...] = (TARGET_PIPELINE, TARGET_LLM_RAW)

# Estados de revisión válidos (Rúbrica v0.2)
STATUS_PENDING: str = 'pendiente'
STATUS_ANNOTATED: str = 'anotado'
STATUS_CONSENSED: str = 'consensuado'
STATUS_NOT_EVALUABLE: str = 'no_evaluable'
VALID_STATUSES: Set[str] = {STATUS_PENDING, STATUS_ANNOTATED, STATUS_CONSENSED, STATUS_NOT_EVALUABLE}

# Valores canónicos de calidad de respuesta
QUALITY_CORRECT: str = 'correcta'
QUALITY_PARTIAL: str = 'parcial'
QUALITY_INCORRECT: str = 'incorrecta'
QUALITY_NOT_APPLICABLE: str = 'no_aplica'
VALID_QUALITIES: Set[str] = {QUALITY_CORRECT, QUALITY_PARTIAL, QUALITY_INCORRECT, QUALITY_NOT_APPLICABLE}

# Valores canónicos de tipo de salida
OUTPUT_RESPONSE: str = 'respuesta'
OUTPUT_ABSTENTION: str = 'abstencion'
VALID_OUTPUT_TYPES: Set[str] = {OUTPUT_RESPONSE, OUTPUT_ABSTENTION}

# Valores canónicos de adecuación de abstención
ABSTENTION_YES: str = 'si'
ABSTENTION_NO: str = 'no'
ABSTENTION_NA: str = 'no_aplica'

# Valores canónicos de pertenencia de citas
CITATION_IN_CONTEXT_YES: str = 'si'
CITATION_IN_CONTEXT_NO: str = 'no'
CITATION_NO_CITATIONS: str = 'sin_citas'
CITATION_IN_CONTEXT_NA: str = 'no_aplica'

# Valores canónicos de sustento de citas
GROUNDING_COMPLETE: str = 'completa'
GROUNDING_PARTIAL: str = 'parcial'
GROUNDING_NONE: str = 'ninguna'
GROUNDING_NO_CITATIONS: str = 'sin_citas'
GROUNDING_NA: str = 'no_aplica'

# Categorías formales de diferenciación de citas
CITATION_CAT_ABSENT: str = 'ausencia_citas'
CITATION_CAT_INVALID_PRESENT: str = 'citas_invalidas'
CITATION_CAT_FORMALLY_VALID: str = 'citas_formalmente_validas'
CITATION_CAT_MIXED: str = 'mixtas'
CITATION_CAT_INDETERMINATE: str = 'no_determinable'
VALID_CITATION_CATEGORIES: Set[str] = {
    CITATION_CAT_ABSENT,
    CITATION_CAT_INVALID_PRESENT,
    CITATION_CAT_FORMALLY_VALID,
    CITATION_CAT_MIXED,
    CITATION_CAT_INDETERMINATE,
}

# Normalización de cadenas para tolerancia a acentos o espacios
STRING_NORMALIZATION: Dict[str, str] = {
    'sí': 'si',
    'si': 'si',
    'no': 'no',
    'no_aplica': 'no_aplica',
    'no aplica': 'no_aplica',
    'n/a': 'no_aplica',
    'na': 'no_aplica',
    'correcta': 'correcta',
    'parcial': 'parcial',
    'incorrecta': 'incorrecta',
    'respuesta': 'respuesta',
    'abstencion': 'abstencion',
    'abstención': 'abstencion',
    'completa': 'completa',
    'ninguna': 'ninguna',
    'sin_citas': 'sin_citas',
    'sin citas': 'sin_citas',
    'suficiente': 'suficiente',
    'insuficiente': 'insuficiente',
    'sin_verificar': 'sin_verificar',
    'sin verificar': 'sin_verificar',
    'pendiente': 'pendiente',
    'anotado': 'anotado',
    'consensuado': 'consensuado',
    'no_evaluable': 'no_evaluable',
    'no evaluable': 'no_evaluable',
}


def normalize_value(val: Optional[str]) -> str:
    """Normaliza cadenas eliminando espacios superfluos y homogeneizando variantes léxicas."""
    if val is None:
        return ''
    cleaned = str(val).strip().lower()
    return STRING_NORMALIZATION.get(cleaned, cleaned)


def fraction(numerator: Optional[int], denominator: int, description: str = "") -> Dict[str, Any]:
    """Calcula una fracción estructurada garantizando manejo formal de denominadores cero.

    Si denominator == 0, value y rate_percent son None; jamás se inventa un valor numérico.
    """
    if denominator == 0 or numerator is None:
        return {
            'numerator': 0 if numerator is None else numerator,
            'denominator': denominator,
            'value': None,
            'rate_percent': None,
            'description': description,
        }
    val = numerator / denominator
    return {
        'numerator': numerator,
        'denominator': denominator,
        'value': val,
        'rate_percent': round(val * 100.0, 2),
        'description': description,
    }


def compute_p95_linear(sorted_clean_values: List[float]) -> Optional[float]:
    """Calcula el percentil 95 mediante interpolación lineal entre los dos rangos más cercanos.

    Método formal:
    Dado un conjunto de N valores ordenados x_0 <= x_1 <= ... <= x_{N-1}:
    - Si N == 1, p95 = x_0.
    - Si N > 1, se calcula el rango continuo r = 0.95 * (N - 1).
      Sea i = floor(r) y f = r - i.
      p95 = x_i + f * (x_{i+1} - x_i) si i + 1 < N, de lo contrario x_{N-1}.
    Este método coincide con Hyndman y Fan (1996) Tipo 7, el estándar por defecto en
    numpy.percentile(..., method='linear'), R (tipo 7), Python statistics.quantiles (method='inclusive')
    y bibliotecas científicas de referencia.
    """
    n = len(sorted_clean_values)
    if n == 0:
        return None
    if n == 1:
        return round(sorted_clean_values[0], 4)
    rank = 0.95 * (n - 1)
    i = int(rank)
    f = rank - i
    if i + 1 < n:
        res = sorted_clean_values[i] + f * (sorted_clean_values[i + 1] - sorted_clean_values[i])
    else:
        res = sorted_clean_values[-1]
    return round(res, 4)


def compute_latency_summary(latencies: List[Any], label: str = "") -> Dict[str, Any]:
    """Calcula media, mediana, percentil 95 y número de observaciones válidas para una serie de latencias.

    Criterios de inclusión/exclusión:
    - Excluye estrictamente valores ausentes (None, vacío), negativos (< 0) o no finitos (NaN, Inf).
    - Bajo ninguna circunstancia reemplaza valores faltantes por cero.
    - Si no existen observaciones válidas, reporta valores None sin inventar estimaciones.
    """
    clean: List[float] = []
    for val in latencies:
        if val is None or val == '':
            continue
        try:
            f = float(val)
        except (ValueError, TypeError):
            continue
        if math.isnan(f) or math.isinf(f) or f < 0:
            continue
        clean.append(f)

    n = len(clean)
    if n == 0:
        return {
            'observaciones_validas': 0,
            'media': None,
            'mediana': None,
            'percentil_95': None,
            'descripcion': label,
        }

    clean.sort()
    media = round(sum(clean) / n, 4)
    mediana = round(statistics.median(clean), 4)
    p95 = compute_p95_linear(clean)

    return {
        'observaciones_validas': n,
        'media': media,
        'mediana': mediana,
        'percentil_95': p95,
        'descripcion': label,
    }


def classify_citation_status(
    cita_pertenece: str = '',
    total_citations: Optional[int] = None,
    invalid_citations: Optional[int] = None,
    citations_valid_bool: Optional[bool] = None,
    abstention_reason: str = '',
) -> str:
    """Clasifica el estado formal de citas separando ausencia, inválidas, formalmente válidas, mixtas e indeterminadas.

    Reglas metodológicas:
    - Ausencia de citas (ausencia_citas): total_citations == 0 o cita_pertenece == 'sin_citas'.
    - Citas formalmente válidas (citas_formalmente_validas): total_citations > 0 con invalid_citations == 0,
      o cita_pertenece == 'si'.
    - Citas presentes pero inválidas (citas_invalidas): total_citations > 0 y todas son inválidas
      (invalid_citations == total_citations) o cita_pertenece == 'no' (sin evidencias de citas mixtas).
    - Casos mixtos (mixtas): total_citations > 1 con 0 < invalid_citations < total_citations.
    - No determinable (no_determinable): información histórica con 'citas_invalidas_o_ausentes' donde faltan
      conteos o evidencias detalladas, impidiendo distinguir entre ausencia e invalidez formal.
    """
    # 1. Si disponemos de conteos cuantitativos de T16
    if total_citations is not None:
        if total_citations == 0:
            return CITATION_CAT_ABSENT
        if invalid_citations is not None:
            if invalid_citations == 0:
                return CITATION_CAT_FORMALLY_VALID
            if invalid_citations == total_citations:
                return CITATION_CAT_INVALID_PRESENT
            if 0 < invalid_citations < total_citations:
                return CITATION_CAT_MIXED
        if citations_valid_bool is True:
            return CITATION_CAT_FORMALLY_VALID
        if citations_valid_bool is False and invalid_citations is None:
            return CITATION_CAT_INVALID_PRESENT

    # 2. Si se basa en la rúbrica humana (cita_pertenece_contexto)
    norm_pert = normalize_value(cita_pertenece)
    if norm_pert == CITATION_NO_CITATIONS:
        return CITATION_CAT_ABSENT
    if norm_pert == CITATION_IN_CONTEXT_YES:
        return CITATION_CAT_FORMALLY_VALID
    if norm_pert == CITATION_IN_CONTEXT_NO:
        if total_citations and invalid_citations and 0 < invalid_citations < total_citations:
            return CITATION_CAT_MIXED
        return CITATION_CAT_INVALID_PRESENT

    # 3. Si solo se cuenta con motivo de abstención de T16 o histórico
    if abstention_reason and ('citas_invalidas_o_ausentes' in abstention_reason or abstention_reason == ABSTENTION_REASON_INVALID_CITATIONS):
        # Información histórica que no permite discernir entre ausencia e invalidez
        return CITATION_CAT_INDETERMINATE

    return ''


@dataclass
class EvaluationRecord:
    """Representa una fila individual de anotación humana según la rúbrica oficial T10 v0.2."""

    evaluacion_id: str
    corrida_id: str
    caso_ciego_id: str
    pregunta_id: str
    evaluador_id: str
    rubrica_version: str = '0.2'
    referencia_caso: str = ''
    referencia_salida: str = ''
    referencia_contexto: str = ''
    referencia_manifiesto: str = ''
    tipo_consulta: str = 'documental'
    evidencia_disponible: str = ''
    estado_revision: str = STATUS_PENDING
    tipo_salida: str = ''
    calidad_respuesta: str = ''
    abstencion_adecuada: str = ''
    cita_pertenece_contexto: str = ''
    cita_sustenta_respuesta: str = ''
    error_vigencia: str = 'no'
    justificacion: str = ''
    referencia_fuente: str = ''
    incidencia: str = ''
    revisado_por: str = ''
    fecha_revision: str = ''
    motivo_abstencion: str = ''

    # Metadatos derivados / asociados
    condicion: str = 'general'
    target: str = TARGET_PIPELINE  # 'pipeline' o 'llm_raw'

    # Telemetría de citas, latencias y configuración experimental compatible (T16)
    citations_count: Optional[int] = None
    citations_invalid_count: Optional[int] = None
    citations_valid: Optional[bool] = None
    citations_category: str = ''
    latency_pipeline_seconds: Optional[float] = None
    latency_generation_seconds: Optional[float] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    seed: Optional[int] = None
    retriever: Optional[str] = None
    top_k: Optional[int] = None
    temperature: Optional[float] = None
    prompt_version: Optional[str] = None

    def __post_init__(self):
        # Normalizar valores léxicos
        self.estado_revision = normalize_value(self.estado_revision) or STATUS_PENDING
        self.tipo_salida = normalize_value(self.tipo_salida)
        self.calidad_respuesta = normalize_value(self.calidad_respuesta)
        self.abstencion_adecuada = normalize_value(self.abstencion_adecuada)
        self.cita_pertenece_contexto = normalize_value(self.cita_pertenece_contexto)
        self.cita_sustenta_respuesta = normalize_value(self.cita_sustenta_respuesta)
        self.error_vigencia = normalize_value(self.error_vigencia)
        self.evidencia_disponible = normalize_value(self.evidencia_disponible)
        self.motivo_abstencion = normalize_value(self.motivo_abstencion)

        # Inferencia de target si no se especificó explícitamente
        if not self.target or self.target not in TARGETS:
            if 'raw_response' in self.referencia_salida or 'llm-raw' in self.evaluacion_id or 'llm_raw' in self.evaluacion_id:
                self.target = TARGET_LLM_RAW
            elif 'response' in self.referencia_salida or 'pipeline' in self.evaluacion_id:
                self.target = TARGET_PIPELINE
            else:
                self.target = TARGET_PIPELINE

        # Inferencia de condición si no se especificó
        if self.condicion == 'general':
            for cond in CONDITIONS:
                if cond in self.referencia_salida or cond in self.corrida_id or cond in self.referencia_manifiesto:
                    self.condicion = cond
                    break

    @property
    def is_not_evaluable(self) -> bool:
        """Determina si el caso fue marcado formalmente como no evaluable o carece de verificación."""
        return self.estado_revision == STATUS_NOT_EVALUABLE or self.evidencia_disponible == 'sin_verificar'

    @property
    def is_pending(self) -> bool:
        """Determina si la evaluación aún está pendiente."""
        if self.is_not_evaluable:
            return False
        if self.estado_revision == STATUS_PENDING or not self.estado_revision:
            return True
        # Conforme a la rúbrica v0.2: un campo esencial vacío conserva el estado pendiente
        if not self.tipo_salida or not self.calidad_respuesta:
            return True
        return False

    @property
    def is_evaluable(self) -> bool:
        """Determina si la fila contiene una evaluación humana completa y válida."""
        if self.is_pending or self.is_not_evaluable:
            return False
        # Para ser evaluable debe tener estado completado y etiquetas válidas
        if self.estado_revision not in (STATUS_ANNOTATED, STATUS_CONSENSED):
            return False
        return True

    @property
    def is_substantive_response(self) -> bool:
        """Indica si el sistema emitió una contestación sustantiva evaluable."""
        return self.is_evaluable and self.tipo_salida == OUTPUT_RESPONSE

    @property
    def is_abstention(self) -> bool:
        """Indica si el sistema emitió una abstención evaluable."""
        return self.is_evaluable and self.tipo_salida == OUTPUT_ABSTENTION

    @property
    def experimental_case_key(self) -> Tuple[str, str, str]:
        """Clave compuesta corrida_id + pregunta_id + condición que identifica unívocamente el caso experimental."""
        cid = self.pregunta_id or self.caso_ciego_id or self.evaluacion_id
        return (self.corrida_id or 'general', cid, self.condicion or 'general')

    @property
    def full_case_key(self) -> Tuple[str, str, str, str]:
        """Clave unívoca considerando adicionalmente el origen de la respuesta (pipeline vs llm_raw)."""
        run_id, cid, cond = self.experimental_case_key
        return (run_id, cid, cond, self.target)


class TracesIndex(dict):
    """Índice de trazas experimentales con resolución estricta de unicidad y compatibilidad.

    Garantiza:
    - Indexación inequívoca por clave compuesta completa (run_id, case_id, condicion).
    - Detección explícita de registros duplicados para la misma clave exacta.
    - Fallbacks históricos únicamente cuando la coincidencia es inequívoca y compatible.
    - Rechazo inmediato ante ambigüedades (múltiples corridas o condiciones para una misma consulta sin especificar).
    - Reporte de telemetría no disponible (None) ante coincidencias ausentes, ambiguas o incompatibles.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.duplicates: Set[Tuple[str, str, str]] = set()
        self.ambiguities: Set[Any] = set()

    def resolve(
        self,
        run_key: str = '',
        cid_key: str = '',
        cond_key: str = '',
    ) -> Optional[Dict[str, Any]]:
        """Resuelve una traza de manera unívoca y compatible.

        Retorna None si la traza está ausente, si es ambigua, si hay duplicados,
        o si los parámetros especificados son incompatibles con la traza candidata.
        """
        run_k = str(run_key or '').strip()
        cid_k = str(cid_key or '').strip()
        cond_k = str(cond_key or '').strip()

        if not cid_k:
            return None

        # 1. Búsqueda exacta si se dispone de corrida y condición
        if run_k and cond_k and cond_k != 'general':
            exact_k = (run_k, cid_k, cond_k)
            if exact_k in self.duplicates:
                return None  # Duplicado en la fuente de trazas -> no unívoco
            if exact_k in self:
                return self[exact_k]
            # Si no coincide exactamente, no buscar en otra corrida o condición
            return None

        # 2. Búsqueda por (cid_k, cond_k) si no se especificó run_k
        if cond_k and cond_k != 'general':
            if run_k:
                return None  # run_k fue dada pero no hubo match exacto -> incompatible
            key_cc = (cid_k, cond_k)
            if key_cc in self.ambiguities:
                return None  # Ambigüedad: existe en múltiples corridas
            if key_cc in self:
                cand = self[key_cc]
                t_cond = str(cand.get('mode') or cand.get('condition') or cand.get('condicion') or '').strip()
                if cond_k != t_cond:
                    return None
                return cand
            return None

        # 3. Búsqueda por (run_k, cid_k) si no se especificó cond_k
        if run_k:
            if cond_k and cond_k != 'general':
                return None  # cond_k fue dada pero no hubo match exacto -> incompatible
            key_rc = (run_k, cid_k)
            if key_rc in self.ambiguities:
                return None  # Ambigüedad: existe en múltiples condiciones
            if key_rc in self:
                cand = self[key_rc]
                t_run = str(cand.get('run_id') or cand.get('corrida_id') or '').strip()
                if run_k != t_run:
                    return None
                return cand
            return None

        # 4. Fallback por cid_k simple únicamente si en todo el universo de trazas es unívoco
        if cid_k in self.ambiguities:
            return None
        if cid_k in self:
            cand = self[cid_k]
            t_run = str(cand.get('run_id') or cand.get('corrida_id') or '').strip()
            t_cond = str(cand.get('mode') or cand.get('condition') or cand.get('condicion') or '').strip()
            if run_k and t_run and run_k != t_run:
                return None
            if cond_k and cond_k != 'general' and t_cond and cond_k != t_cond:
                return None
            return cand

        return None


def load_traces_dict(traces_source: Union[str, Path, List[Dict[str, Any]]]) -> TracesIndex:
    """Carga y mapea trazas experimentales indexándolas estrictamente por unicidad y compatibilidad.

    Garantiza:
    - Indexación inequívoca por clave compuesta (run_id, case_id, condicion).
    - Impedir que motivos de abstención o telemetría de una condición sobrescriban los de otra.
    - Soporte de fallbacks históricos únicamente cuando la coincidencia es unívoca y compatible.
    - Detección de ambigüedades y duplicados, reportando None (telemetría no disponible).
    - Preservación de conteos cuantitativos de citas y latencias desacopladas.
    """
    traces_data: List[Dict[str, Any]] = []
    if isinstance(traces_source, (str, Path)):
        p = Path(traces_source)
        if not p.exists():
            return TracesIndex()
        if p.suffix.lower() == '.json':
            content = json.loads(p.read_text(encoding='utf-8'))
            traces_data = content if isinstance(content, list) else content.get('traces', [])
        else:
            with p.open('r', encoding='utf-8', errors='replace') as f:
                traces_data = list(csv.DictReader(f))
    elif isinstance(traces_source, list):
        traces_data = traces_source
    else:
        return TracesIndex()

    index = TracesIndex()
    exact_map: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    cid_cond_map: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    run_cid_map: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    cid_map: Dict[str, List[Dict[str, Any]]] = {}

    for t in traces_data:
        run_id = str(t.get('run_id') or t.get('corrida_id') or '').strip()
        cid = str(t.get('case_id') or t.get('pregunta_id') or t.get('id') or '').strip()
        cond = str(t.get('mode') or t.get('condition') or t.get('condicion') or '').strip()

        if not cid:
            continue

        exact_k = (run_id, cid, cond)
        exact_map.setdefault(exact_k, []).append(t)

        if cond:
            cid_cond_map.setdefault((cid, cond), []).append(t)
        if run_id:
            run_cid_map.setdefault((run_id, cid), []).append(t)
        cid_map.setdefault(cid, []).append(t)

    # 1. Claves exactas (run_id, case_id, condicion)
    for exact_k, t_list in exact_map.items():
        if len(t_list) == 1:
            index[exact_k] = t_list[0]
        else:
            index.duplicates.add(exact_k)

    # 2. Claves (case_id, condicion) - unívocas únicamente si no colisionan entre corridas
    for cc_k, t_list in cid_cond_map.items():
        if len(t_list) == 1:
            index[cc_k] = t_list[0]
        else:
            index.ambiguities.add(cc_k)

    # 3. Claves (run_id, case_id) - unívocas únicamente si no colisionan entre condiciones
    for rc_k, t_list in run_cid_map.items():
        if len(t_list) == 1:
            index[rc_k] = t_list[0]
        else:
            index.ambiguities.add(rc_k)

    # 4. Fallback case_id simple - unívoco únicamente si no colisiona en todo el universo
    for c_k, t_list in cid_map.items():
        if len(t_list) == 1:
            index[c_k] = t_list[0]
        else:
            index.ambiguities.add(c_k)

    return index


def load_annotations(
    source: Union[str, Path, List[Dict[str, Any]]],
    blind_mapping: Optional[Union[Dict[str, Any], Path, str]] = None,
    traces_source: Optional[Union[str, Path, List[Dict[str, Any]]]] = None,
) -> List[EvaluationRecord]:
    """Carga y normaliza anotaciones desde un archivo CSV, JSON o lista de diccionarios.

    Permite incorporar opcionalmente un mapa de desenmascaramiento ciego (blind_mapping)
    para asociar caso_ciego_id con su condición experimental real (A, B, C) y target,
    así como fuentes de trazas experimentales reales (traces_source) de T16 para fundamentar
    los diagnósticos canónicos de abstención y enriquecer con telemetría de citas y latencias.
    """
    records_data: List[Dict[str, Any]] = []

    if isinstance(source, (str, Path)):
        p = Path(source)
        if not p.exists():
            raise FileNotFoundError(f"Archivo de anotaciones no encontrado: {p}")
        if p.suffix.lower() == '.json':
            content = json.loads(p.read_text(encoding='utf-8'))
            records_data = content if isinstance(content, list) else content.get('anotaciones', [])
        else:
            with p.open('r', encoding='utf-8', errors='replace') as f:
                reader = csv.DictReader(f)
                records_data = list(reader)
    elif isinstance(source, list):
        records_data = source
    else:
        raise TypeError(f"Fuente no soportada: {type(source)}")

    # Cargar mapa de correspondencia si fue proporcionado como ruta
    mapping_dict: Dict[str, Any] = {}
    if blind_mapping:
        if isinstance(blind_mapping, (str, Path)):
            mp = Path(blind_mapping)
            if mp.exists():
                mapping_dict = json.loads(mp.read_text(encoding='utf-8'))
        elif isinstance(blind_mapping, dict):
            mapping_dict = blind_mapping

    traces_dict: Dict[Any, Dict[str, Any]] = load_traces_dict(traces_source) if traces_source else {}
    cached_trace_files: Dict[str, Dict[Any, Dict[str, Any]]] = {}

    records: List[EvaluationRecord] = []
    for raw in records_data:
        caso_id = raw.get('caso_ciego_id', '') or raw.get('pregunta_id', '')
        mapped_info = mapping_dict.get(caso_id, {})
        if isinstance(mapped_info, str):
            mapped_cond = mapped_info
            mapped_target = None
            mapped_motivo = None
        else:
            mapped_cond = mapped_info.get('condicion') or mapped_info.get('mode')
            mapped_target = mapped_info.get('target') or mapped_info.get('origen_respuesta')
            mapped_motivo = mapped_info.get('motivo_abstencion') or mapped_info.get('abstention_reason')

        cond = raw.get('condicion') or raw.get('mode') or mapped_cond or 'general'
        target = raw.get('target') or raw.get('origen_respuesta') or mapped_target or ''
        motivo_abs = raw.get('motivo_abstencion') or raw.get('abstention_reason') or mapped_motivo or ''

        # Buscar traza asociada mediante clave unívoca y compatible
        matched_trace: Optional[Dict[str, Any]] = None
        run_key = str(raw.get('corrida_id') or '').strip()
        q_key = str(raw.get('pregunta_id') or caso_id).strip()
        cond_key = str(cond).strip()

        if traces_dict:
            if isinstance(traces_dict, TracesIndex):
                matched_trace = traces_dict.resolve(run_key, q_key, cond_key)
            else:
                if run_key and q_key and cond_key and (run_key, q_key, cond_key) in traces_dict:
                    matched_trace = traces_dict[(run_key, q_key, cond_key)]
                elif q_key and cond_key and (q_key, cond_key) in traces_dict:
                    cand = traces_dict[(q_key, cond_key)]
                    t_run = str(cand.get('run_id') or cand.get('corrida_id') or '').strip()
                    if not run_key or not t_run or run_key == t_run:
                        matched_trace = cand

        # También verificar referencia_salida con #
        ref_salida = raw.get('referencia_salida', '')
        if not matched_trace and ref_salida and '#' in ref_salida:
            file_part, key_part = ref_salida.split('#', 1)
            trace_file_path = Path(file_part)
            if trace_file_path.exists():
                if file_part not in cached_trace_files:
                    cached_trace_files[file_part] = load_traces_dict(trace_file_path)
                sub_id = key_part.split('.')[0] if '.' in key_part else key_part
                tf_dict = cached_trace_files[file_part]
                if isinstance(tf_dict, TracesIndex):
                    matched_trace = tf_dict.resolve(run_key, sub_id, cond_key)
                elif tf_dict:
                    if run_key and sub_id and cond_key and (run_key, sub_id, cond_key) in tf_dict:
                        matched_trace = tf_dict[(run_key, sub_id, cond_key)]
                    elif sub_id and cond_key and (sub_id, cond_key) in tf_dict:
                        cand = tf_dict[(sub_id, cond_key)]
                        t_run = str(cand.get('run_id') or cand.get('corrida_id') or '').strip()
                        if not run_key or not t_run or run_key == t_run:
                            matched_trace = cand

        if matched_trace and not motivo_abs:
            motivo_abs = matched_trace.get('abstention_reason') or ''

        # Telemetría de citas cuantitativas de T16
        c_count: Optional[int] = None
        c_inv: Optional[int] = None
        c_valid: Optional[bool] = None

        if matched_trace:
            inv_val = matched_trace.get('citations_invalid_count')
            if inv_val is None:
                inv_val = matched_trace.get('invalid_citations_count')
            if inv_val is not None and str(inv_val).strip() != '':
                try:
                    c_inv = int(inv_val)
                except (ValueError, TypeError):
                    pass

            cv = matched_trace.get('citations_valid')
            if cv is not None:
                if isinstance(cv, str):
                    c_valid = cv.lower() == 'true'
                else:
                    c_valid = bool(cv)

            # Regla de saneamiento T16: citations_raw solo conserva citas formalmente válidas
            # pertenecientes al contexto admisible; las inválidas han sido filtradas para evitar fuga.
            # Por tanto, el conteo original de citas es:
            #   original_citations_count = len(citations_raw_saneadas) + citations_invalid_count
            raw_cits = matched_trace.get('citations_raw')
            trace_c_count = matched_trace.get('citations_count')
            tc_int: Optional[int] = None
            if trace_c_count is not None and str(trace_c_count).strip() != '':
                try:
                    tc_int = int(trace_c_count)
                except (ValueError, TypeError):
                    pass

            if isinstance(raw_cits, list):
                valid_count = len(raw_cits)
                invalid_count = c_inv if (c_inv is not None and c_inv > 0) else 0
                c_count = valid_count + invalid_count
                if tc_int is not None and tc_int > c_count:
                    c_count = tc_int
            elif tc_int is not None:
                if c_inv is not None and c_inv > 0 and tc_int < c_inv:
                    c_count = tc_int + c_inv
                else:
                    c_count = tc_int
            elif c_inv is not None and c_inv > 0:
                c_count = c_inv

        # Fallback a columnas presentes directamente en la anotación
        if c_inv is None and raw.get('citations_invalid_count') is not None and str(raw.get('citations_invalid_count')).strip() != '':
            try:
                c_inv = int(raw['citations_invalid_count'])
            except (ValueError, TypeError):
                pass
        if c_count is None and raw.get('citations_count') is not None and str(raw.get('citations_count')).strip() != '':
            try:
                c_count = int(raw['citations_count'])
            except (ValueError, TypeError):
                pass
        if c_valid is None and raw.get('citations_valid') is not None and str(raw.get('citations_valid')).strip() != '':
            val_str = str(raw['citations_valid']).strip().lower()
            c_valid = val_str == 'true'

        cit_cat = classify_citation_status(
            cita_pertenece=raw.get('cita_pertenece_contexto', ''),
            total_citations=c_count,
            invalid_citations=c_inv,
            citations_valid_bool=c_valid,
            abstention_reason=motivo_abs,
        )

        # Telemetría de latencias desacopladas
        pipe_lat: Optional[float] = None
        gen_lat: Optional[float] = None
        if matched_trace:
            p_val = matched_trace.get('latency_pipeline_seconds') if matched_trace.get('latency_pipeline_seconds') is not None else matched_trace.get('pipeline_seconds')
            if p_val is not None and str(p_val).strip() != '':
                try:
                    pf = float(p_val)
                    if pf >= 0 and not (math.isnan(pf) or math.isinf(pf)):
                        pipe_lat = pf
                except (ValueError, TypeError):
                    pass

            g_val = matched_trace.get('latency_generation_seconds') if matched_trace.get('latency_generation_seconds') is not None else matched_trace.get('latency_seconds')
            if g_val is not None and str(g_val).strip() != '':
                try:
                    gf = float(g_val)
                    if gf >= 0 and not (math.isnan(gf) or math.isinf(gf)):
                        gen_lat = gf
                except (ValueError, TypeError):
                    pass

        # Fallback si las latencias vinieron en raw
        if pipe_lat is None:
            p_raw = raw.get('latency_pipeline_seconds') if raw.get('latency_pipeline_seconds') is not None else raw.get('pipeline_seconds')
            if p_raw is not None and str(p_raw).strip() != '':
                try:
                    pf = float(p_raw)
                    if pf >= 0 and not (math.isnan(pf) or math.isinf(pf)):
                        pipe_lat = pf
                except (ValueError, TypeError):
                    pass
        if gen_lat is None:
            g_raw = raw.get('latency_generation_seconds') if raw.get('latency_generation_seconds') is not None else raw.get('latency_seconds')
            if g_raw is not None and str(g_raw).strip() != '':
                try:
                    gf = float(g_raw)
                    if gf >= 0 and not (math.isnan(gf) or math.isinf(gf)):
                        gen_lat = gf
                except (ValueError, TypeError):
                    pass

        # Configuración experimental compatible (preservando valores válidos iguales a cero)
        prov = raw.get('provider') if raw.get('provider') is not None else (matched_trace.get('provider') if matched_trace else None)
        mod = raw.get('model') if raw.get('model') is not None else (matched_trace.get('model') if matched_trace else None)

        ret_val = raw.get('retriever')
        if ret_val is None and matched_trace:
            ret_val = matched_trace.get('retriever') or matched_trace.get('index_method')
        retriever = str(ret_val).strip() if ret_val is not None and str(ret_val).strip() != '' else None

        s_val = raw.get('seed')
        if s_val is None and matched_trace:
            s_val = matched_trace.get('seed')
            if s_val is None and isinstance(matched_trace.get('parameters'), dict):
                s_val = matched_trace['parameters'].get('seed')
        try:
            seed = int(s_val) if s_val is not None and str(s_val).strip() != '' else None
        except (ValueError, TypeError):
            seed = None

        tk_val = raw.get('top_k')
        if tk_val is None and matched_trace:
            tk_val = matched_trace.get('top_k')
            if tk_val is None and isinstance(matched_trace.get('parameters'), dict):
                tk_val = matched_trace['parameters'].get('top_k')
        try:
            top_k = int(tk_val) if tk_val is not None and str(tk_val).strip() != '' else None
        except (ValueError, TypeError):
            top_k = None

        temp_val = raw.get('temperature')
        if temp_val is None and matched_trace:
            temp_val = matched_trace.get('temperature')
            if temp_val is None and isinstance(matched_trace.get('parameters'), dict):
                temp_val = matched_trace['parameters'].get('temperature')
        try:
            temp = float(temp_val) if temp_val is not None and str(temp_val).strip() != '' else None
        except (ValueError, TypeError):
            temp = None

        p_ver = raw.get('prompt_version') if raw.get('prompt_version') is not None else (matched_trace.get('prompt_version') if matched_trace else None)

        record = EvaluationRecord(
            evaluacion_id=raw.get('evaluacion_id', ''),
            corrida_id=raw.get('corrida_id', ''),
            caso_ciego_id=raw.get('caso_ciego_id', ''),
            pregunta_id=raw.get('pregunta_id', ''),
            evaluador_id=raw.get('evaluador_id', ''),
            rubrica_version=raw.get('rubrica_version', '0.2'),
            referencia_caso=raw.get('referencia_caso', ''),
            referencia_salida=raw.get('referencia_salida', ''),
            referencia_contexto=raw.get('referencia_contexto', ''),
            referencia_manifiesto=raw.get('referencia_manifiesto', ''),
            tipo_consulta=raw.get('tipo_consulta', 'documental'),
            evidencia_disponible=raw.get('evidencia_disponible', ''),
            estado_revision=raw.get('estado_revision', STATUS_PENDING),
            tipo_salida=raw.get('tipo_salida', ''),
            calidad_respuesta=raw.get('calidad_respuesta', ''),
            abstencion_adecuada=raw.get('abstencion_adecuada', ''),
            cita_pertenece_contexto=raw.get('cita_pertenece_contexto', ''),
            cita_sustenta_respuesta=raw.get('cita_sustenta_respuesta', ''),
            error_vigencia=raw.get('error_vigencia', 'no'),
            justificacion=raw.get('justificacion', ''),
            referencia_fuente=raw.get('referencia_fuente', ''),
            incidencia=raw.get('incidencia', ''),
            revisado_por=raw.get('revisado_por', ''),
            fecha_revision=raw.get('fecha_revision', ''),
            motivo_abstencion=motivo_abs,
            condicion=cond,
            target=target,
            citations_count=c_count,
            citations_invalid_count=c_inv,
            citations_valid=c_valid,
            citations_category=cit_cat,
            latency_pipeline_seconds=pipe_lat,
            latency_generation_seconds=gen_lat,
            provider=prov,
            model=mod,
            seed=seed,
            retriever=retriever,
            top_k=top_k,
            temperature=temp,
            prompt_version=p_ver,
        )
        records.append(record)

    return records


def resolve_consensus_records(
    records: List[EvaluationRecord],
    return_conflicts: bool = False,
) -> Union[List[EvaluationRecord], Tuple[List[EvaluationRecord], List[Dict[str, Any]]]]:
    """Resuelve anotaciones múltiples sobre una misma salida seleccionando la fila de consenso.

    Si una salida cuenta con fila 'consensuado', esta prevalece.
    Si existen múltiples evaluadores con juicios anotados:
    - Si coinciden en todos sus juicios, se toma una única anotación sin duplicar el caso.
    - Si presentan desacuerdo y NO existe fila consensuada, se registra el conflicto formalmente
      sin resolverlo de forma arbitraria, manteniéndose el caso como pendiente de consenso.
    """
    grouped: Dict[Tuple[str, str, str, str], List[EvaluationRecord]] = {}
    for idx, r in enumerate(records):
        case_id = r.pregunta_id or r.caso_ciego_id or r.evaluacion_id or f'row_{idx}'
        key = (r.corrida_id or 'general', case_id, r.condicion or 'general', r.target)
        grouped.setdefault(key, []).append(r)

    resolved: List[EvaluationRecord] = []
    conflicts: List[Dict[str, Any]] = []

    keys_to_compare = (
        'calidad_respuesta', 'tipo_salida', 'abstencion_adecuada',
        'cita_pertenece_contexto', 'cita_sustenta_respuesta', 'error_vigencia'
    )

    for (corrida_id, case_id, condicion, target), items in grouped.items():
        consensuados = [i for i in items if i.estado_revision == STATUS_CONSENSED]
        if consensuados:
            resolved.append(consensuados[-1])
            continue

        anotados = [i for i in items if i.estado_revision == STATUS_ANNOTATED]
        if anotados:
            if len(anotados) == 1:
                resolved.append(anotados[0])
                continue

            # Múltiples evaluadores: verificar concordancia
            first_item = anotados[0]
            has_disagreement = any(
                getattr(item, k) != getattr(first_item, k)
                for item in anotados[1:]
                for k in keys_to_compare
            )

            if not has_disagreement:
                resolved.append(first_item)
            else:
                evaluadores_list = [i.evaluador_id for i in anotados]
                conflict_entry = {
                    'corrida_id': corrida_id,
                    'caso_id': case_id,
                    'condicion': condicion,
                    'target': target,
                    'evaluadores': evaluadores_list,
                    'juicios': [
                        {
                            'evaluador_id': i.evaluador_id,
                            'calidad_respuesta': i.calidad_respuesta,
                            'tipo_salida': i.tipo_salida,
                            'abstencion_adecuada': i.abstencion_adecuada,
                            'cita_pertenece_contexto': i.cita_pertenece_contexto,
                            'cita_sustenta_respuesta': i.cita_sustenta_respuesta,
                            'error_vigencia': i.error_vigencia,
                        }
                        for i in anotados
                    ],
                    'motivo': 'desacuerdo_entre_evaluadores_sin_consenso',
                }
                conflicts.append(conflict_entry)
                # Mantener el caso en pendiente de consenso sin resolver arbitrariamente
                conflict_record = EvaluationRecord(
                    evaluacion_id=f"CONFLICT-{corrida_id}-{case_id}-{condicion}-{target}",
                    corrida_id=items[0].corrida_id,
                    caso_ciego_id=items[0].caso_ciego_id,
                    pregunta_id=items[0].pregunta_id or case_id,
                    evaluador_id="multiple_en_conflicto",
                    rubrica_version=items[0].rubrica_version,
                    referencia_caso=items[0].referencia_caso,
                    referencia_salida=items[0].referencia_salida,
                    referencia_contexto=items[0].referencia_contexto,
                    referencia_manifiesto=items[0].referencia_manifiesto,
                    tipo_consulta=items[0].tipo_consulta,
                    evidencia_disponible=items[0].evidencia_disponible,
                    estado_revision=STATUS_PENDING,
                    tipo_salida='',
                    calidad_respuesta='',
                    incidencia=f"Desacuerdo sin consenso entre evaluadores ({', '.join(evaluadores_list)})",
                    condicion=condicion,
                    target=target,
                    citations_count=items[0].citations_count,
                    citations_invalid_count=items[0].citations_invalid_count,
                    citations_valid=items[0].citations_valid,
                    citations_category=items[0].citations_category,
                    latency_pipeline_seconds=items[0].latency_pipeline_seconds,
                    latency_generation_seconds=items[0].latency_generation_seconds,
                    provider=items[0].provider,
                    model=items[0].model,
                    seed=items[0].seed,
                    retriever=items[0].retriever,
                    top_k=items[0].top_k,
                    temperature=items[0].temperature,
                    prompt_version=items[0].prompt_version,
                )
                resolved.append(conflict_record)
            continue

        # Si ninguno fue completado, conservar el primero (ej. pendiente o no_evaluable)
        resolved.append(items[0])

    if return_conflicts:
        return resolved, conflicts
    return resolved


def compute_slice_metrics(records: List[EvaluationRecord], slice_name: str = "") -> Dict[str, Any]:
    """Calcula todas las métricas de calidad para un corte dado de anotaciones.

    Garantiza:
    1. Registro explícito de numeradores y denominadores en cada tasa.
    2. No contabilizar evaluaciones pendientes como respuestas incorrectas.
    3. Manejo de división por cero mediante valores None/null.
    4. Separación estricta entre pertenencia al contexto y sustento real de citas.
    5. No distorsión por campos no_aplica ni sin_verificar en denominadores específicos.
    """
    total_records = len(records)
    pending_records = [r for r in records if r.is_pending]
    not_evaluable_records = [r for r in records if r.is_not_evaluable]
    evaluable_records = [r for r in records if r.is_evaluable]

    n_eval = len(evaluable_records)
    n_pending = len(pending_records)
    n_not_evaluable = len(not_evaluable_records)
    n_excluded = n_pending + n_not_evaluable

    # Partición por tipo de salida
    substantive_responses = [r for r in evaluable_records if r.is_substantive_response]
    abstentions = [r for r in evaluable_records if r.is_abstention]
    n_substantive = len(substantive_responses)
    n_abstentions = len(abstentions)

    # 1. Calidad de contenido (sobre total evaluable)
    n_correct = sum(1 for r in evaluable_records if r.calidad_respuesta == QUALITY_CORRECT)
    n_partial = sum(1 for r in evaluable_records if r.calidad_respuesta == QUALITY_PARTIAL)
    n_incorrect = sum(1 for r in evaluable_records if r.calidad_respuesta == QUALITY_INCORRECT)
    n_quality_na = sum(1 for r in evaluable_records if r.calidad_respuesta == QUALITY_NOT_APPLICABLE)

    # 2. Abstenciones y adecuación
    # Abstenciones evaluables para adecuación (donde abstencion_adecuada es 'si' o 'no', excluyendo 'no_aplica')
    abstentions_with_adequacy = [r for r in abstentions if r.abstencion_adecuada in (ABSTENTION_YES, ABSTENTION_NO)]
    n_abst_eval = len(abstentions_with_adequacy)
    n_abst_adequate = sum(1 for r in abstentions_with_adequacy if r.abstencion_adecuada == ABSTENTION_YES)
    n_abst_inadequate = sum(1 for r in abstentions_with_adequacy if r.abstencion_adecuada == ABSTENTION_NO)

    # 3. Citas: Pertenencia vs. Sustento Real (sobre respuestas sustantivas evaluables)
    # Pertenencia
    n_cit_in_context = sum(1 for r in substantive_responses if r.cita_pertenece_contexto == CITATION_IN_CONTEXT_YES)
    n_cit_out_context = sum(1 for r in substantive_responses if r.cita_pertenece_contexto == CITATION_IN_CONTEXT_NO)
    n_cit_missing = sum(1 for r in substantive_responses if r.cita_pertenece_contexto == CITATION_NO_CITATIONS)

    # Sustento
    n_ground_complete = sum(1 for r in substantive_responses if r.cita_sustenta_respuesta == GROUNDING_COMPLETE)
    n_ground_partial = sum(1 for r in substantive_responses if r.cita_sustenta_respuesta == GROUNDING_PARTIAL)
    n_ground_none = sum(1 for r in substantive_responses if r.cita_sustenta_respuesta == GROUNDING_NONE)
    n_ground_missing = sum(1 for r in substantive_responses if r.cita_sustenta_respuesta == GROUNDING_NO_CITATIONS)

    # Citas válidas completas (pertenencia 'si' Y sustento 'completa')
    n_valid_citations = sum(
        1 for r in substantive_responses
        if r.cita_pertenece_contexto == CITATION_IN_CONTEXT_YES and r.cita_sustenta_respuesta == GROUNDING_COMPLETE
    )

    # Pertenencia formal sin sustento real suficiente
    n_in_context_partial_ground = sum(
        1 for r in substantive_responses
        if r.cita_pertenece_contexto == CITATION_IN_CONTEXT_YES and r.cita_sustenta_respuesta == GROUNDING_PARTIAL
    )
    n_in_context_no_ground = sum(
        1 for r in substantive_responses
        if r.cita_pertenece_contexto == CITATION_IN_CONTEXT_YES and r.cita_sustenta_respuesta == GROUNDING_NONE
    )
    n_in_context_insufficient = n_in_context_partial_ground + n_in_context_no_ground

    # Diferenciación formal de citas (separación explícita sobre respuestas sustantivas)
    n_cit_absent = sum(
        1 for r in substantive_responses
        if r.citations_category == CITATION_CAT_ABSENT or (not r.citations_category and r.cita_pertenece_contexto == CITATION_NO_CITATIONS)
    )
    n_cit_invalid_present = sum(
        1 for r in substantive_responses
        if r.citations_category == CITATION_CAT_INVALID_PRESENT or (not r.citations_category and r.cita_pertenece_contexto == CITATION_IN_CONTEXT_NO)
    )
    n_cit_formally_valid = sum(
        1 for r in substantive_responses
        if r.citations_category == CITATION_CAT_FORMALLY_VALID or (not r.citations_category and r.cita_pertenece_contexto == CITATION_IN_CONTEXT_YES)
    )
    n_cit_mixed = sum(
        1 for r in substantive_responses
        if r.citations_category == CITATION_CAT_MIXED
    )
    n_cit_indeterminate = sum(
        1 for r in substantive_responses
        if r.citations_category == CITATION_CAT_INDETERMINATE
    )

    # Error de vigencia
    n_vigencia_error_substantive = sum(1 for r in substantive_responses if r.error_vigencia == 'si')
    n_vigencia_error_all = sum(1 for r in evaluable_records if r.error_vigencia == 'si')

    # Evidencia disponible en evaluables
    n_evid_suficiente = sum(1 for r in evaluable_records if r.evidencia_disponible == 'suficiente')
    n_evid_insuficiente = sum(1 for r in evaluable_records if r.evidencia_disponible == 'insuficiente')
    n_evid_sin_verificar = sum(1 for r in evaluable_records if r.evidencia_disponible == 'sin_verificar')

    return {
        'nombre_corte': slice_name,
        'contabilidad_casos': {
            'total_anotaciones': total_records,
            'casos_evaluables': n_eval,
            'casos_pendientes': n_pending,
            'casos_no_evaluables': n_not_evaluable,
            'casos_excluidos': n_excluded,
            'tasa_completitud': fraction(n_eval, total_records, 'Proporción de anotaciones evaluadas sobre el total'),
        },
        'evidencia_disponible': {
            'suficiente': fraction(n_evid_suficiente, n_eval, 'Evidencia suficiente según evaluador'),
            'insuficiente': fraction(n_evid_insuficiente, n_eval, 'Evidencia insuficiente según evaluador'),
            'sin_verificar': fraction(n_evid_sin_verificar, n_eval, 'Evidencia sin verificar'),
        },
        'tipo_salida': {
            'respuestas_sustantivas': fraction(n_substantive, n_eval, 'Salidas con respuesta sustantiva'),
            'abstenciones': fraction(n_abstentions, n_eval, 'Salidas con abstención formal o justificada'),
        },
        'calidad_contenido': {
            # Conforme a Rúbrica v0.2: Denominador incluye abstenciones (todas las consultas legítimas evaluables)
            'exactitud_humana_contenido': fraction(
                n_correct, n_eval,
                'Respuestas correctas sobre todas las consultas evaluables (incluye abstenciones, rúbrica T10 v0.2)'
            ),
            'tasa_respuestas_parciales': fraction(
                n_partial, n_eval,
                'Respuestas parcialmente correctas sobre todas las consultas evaluables'
            ),
            'tasa_respuestas_incorrectas': fraction(
                n_incorrect, n_eval,
                'Respuestas incorrectas sobre todas las consultas evaluables'
            ),
            'calidad_no_aplica_abstencion': fraction(
                n_quality_na, n_eval,
                'Abstenciones con calidad clasificada como no_aplica'
            ),
            # Denominador condicional restringido a respuestas sustantivas
            'correctas_sobre_respuestas_sustantivas': fraction(
                n_correct, n_substantive,
                'Exactitud condicional en respuestas sustantivas (correctas / respuestas sustantivas)'
            ),
            'parciales_sobre_respuestas_sustantivas': fraction(
                n_partial, n_substantive,
                'Respuestas parcialmente correctas sobre respuestas sustantivas evaluables'
            ),
            'incorrectas_sobre_respuestas_sustantivas': fraction(
                n_incorrect, n_substantive,
                'Respuestas incorrectas sobre respuestas sustantivas evaluables'
            ),
        },
        'abstencion_y_adecuacion': {
            'tasa_abstencion': fraction(
                n_abstentions, n_eval,
                'Tasa de abstención sobre consultas evaluables'
            ),
            'adecuacion_abstenciones': fraction(
                n_abst_adequate, n_abst_eval,
                'Abstenciones adecuadas sobre el total de abstenciones evaluadas'
            ),
            'tasa_abstenciones_inadecuadas': fraction(
                n_abst_inadequate, n_abst_eval,
                'Abstenciones inadecuadas sobre el total de abstenciones evaluadas'
            ),
            'abstenciones_adecuadas_sobre_total_consultas': fraction(
                n_abst_adequate, n_eval,
                'Abstenciones adecuadas sobre el total de consultas evaluables'
            ),
            'abstenciones_inadecuadas_sobre_total_consultas': fraction(
                n_abst_inadequate, n_eval,
                'Abstenciones inadecuadas sobre el total de consultas evaluables'
            ),
            'abstenciones_evaluadas_para_adecuacion': n_abst_eval,
        },
        'validez_y_sustento_citas': {
            # Métrica combinada oficial Rúbrica v0.2
            'citas_validas_completas': fraction(
                n_valid_citations, n_substantive,
                'Respuestas con citas pertenecientes al contexto Y con sustento completo sobre respuestas sustantivas'
            ),
            # Desglose de pertenencia al contexto recuperado
            'pertenencia_contexto': {
                'citas_pertenecen_si': fraction(
                    n_cit_in_context, n_substantive,
                    'Respuestas cuyas citas pertenecen íntegramente al contexto recuperado aceptado'
                ),
                'citas_pertenecen_no': fraction(
                    n_cit_out_context, n_substantive,
                    'Respuestas con al menos una cita fuera del contexto aceptado (alucinación/fabricación)'
                ),
                'respuestas_sin_citas': fraction(
                    n_cit_missing, n_substantive,
                    'Respuestas sustantivas que omitieron citar fuentes'
                ),
            },
            # Desglose de sustento factual real
            'sustento_factual': {
                'sustento_completo': fraction(
                    n_ground_complete, n_substantive,
                    'Citas que respaldan la totalidad de las afirmaciones sustanciales'
                ),
                'sustento_parcial': fraction(
                    n_ground_partial, n_substantive,
                    'Citas que respaldan únicamente una parte de lo afirmado'
                ),
                'sustento_ninguno': fraction(
                    n_ground_none, n_substantive,
                    'Citas que carecen de sustento para lo afirmado'
                ),
                'sin_citas': fraction(
                    n_ground_missing, n_substantive,
                    'Respuestas sustantivas sin citas'
                ),
            },
            # Distinción de brecha: Pertenecen formalmente pero no sustentan
            'brecha_pertenencia_sin_sustento': {
                'pertenecen_pero_sustento_parcial': fraction(
                    n_in_context_partial_ground, n_substantive,
                    'Citas pertenecientes al contexto que solo sustentan parcialmente la respuesta'
                ),
                'pertenecen_pero_sustento_nulo': fraction(
                    n_in_context_no_ground, n_substantive,
                    'Citas pertenecientes al contexto que carecen de sustento real para lo afirmado'
                ),
                'total_pertenecen_sin_sustento_completo': fraction(
                    n_in_context_insufficient, n_substantive,
                    'Total de respuestas con citas válidas en contexto pero con sustento insuficiente'
                ),
            },
            # Errores de vigencia normativa
            'errores_vigencia': {
                'sobre_respuestas_sustantivas': fraction(
                    n_vigencia_error_substantive, n_substantive,
                    'Respuestas sustantivas que afirman vigencia no verificada o errónea'
                ),
                'sobre_total_consultas': fraction(
                    n_vigencia_error_all, n_eval,
                    'Total de respuestas con error de vigencia sobre consultas evaluables'
                ),
            },
            # Diferenciación formal de citas (desacoplada de sustento fáctico)
            'diferenciacion_citas': {
                'ausencia_citas': fraction(
                    n_cit_absent, n_substantive,
                    'Ausencia total de citas en respuestas sustantivas'
                ),
                'citas_presentes_invalidas': fraction(
                    n_cit_invalid_present, n_substantive,
                    'Citas presentes pero formalmente inválidas (fuera de fragmentos aceptados)'
                ),
                'citas_formalmente_validas': fraction(
                    n_cit_formally_valid, n_substantive,
                    'Citas presentes y formalmente válidas en fragmentos aceptados'
                ),
                'casos_mixtos': fraction(
                    n_cit_mixed, n_substantive,
                    'Casos mixtos con al menos una cita válida y una inválida'
                ),
                'no_determinable': fraction(
                    n_cit_indeterminate, n_substantive,
                    'Casos con etiqueta citas_invalidas_o_ausentes sin evidencia cuantitativa histórica suficiente'
                ),
            },
        },
    }


def compare_slices(slice_a: Dict[str, Any], slice_b: Dict[str, Any], label_a: str, label_b: str) -> Dict[str, Any]:
    """Calcula diferencias (deltas) entre dos cortes de métricas."""
    def diff_val(metric_path: List[str]) -> Optional[float]:
        curr_a = slice_a
        curr_b = slice_b
        for k in metric_path:
            curr_a = curr_a.get(k, {}) if isinstance(curr_a, dict) else {}
            curr_b = curr_b.get(k, {}) if isinstance(curr_b, dict) else {}
        val_a = curr_a.get('value') if isinstance(curr_a, dict) else None
        val_b = curr_b.get('value') if isinstance(curr_b, dict) else None
        if val_a is not None and val_b is not None:
            return round(val_a - val_b, 4)
        return None

    return {
        'comparacion': f'{label_a} vs {label_b}',
        'delta_exactitud_humana_contenido': diff_val(['calidad_contenido', 'exactitud_humana_contenido']),
        'delta_exactitud_sobre_sustantivas': diff_val(['calidad_contenido', 'correctas_sobre_respuestas_sustantivas']),
        'delta_respuestas_parciales': diff_val(['calidad_contenido', 'tasa_respuestas_parciales']),
        'delta_respuestas_incorrectas': diff_val(['calidad_contenido', 'tasa_respuestas_incorrectas']),
        'delta_tasa_abstencion': diff_val(['abstencion_y_adecuacion', 'tasa_abstencion']),
        'delta_adecuacion_abstenciones': diff_val(['abstencion_y_adecuacion', 'adecuacion_abstenciones']),
        'delta_citas_validas_completas': diff_val(['validez_y_sustento_citas', 'citas_validas_completas']),
    }


def compute_paired_condition_comparison(
    records: List[EvaluationRecord],
    cond_x: str,
    cond_y: str,
    target: str = TARGET_PIPELINE,
) -> Dict[str, Any]:
    """Compara de forma estrictamente pareada dos condiciones experimentales.

    Utiliza únicamente los casos comunes que fueron efectivamente evaluables en ambas
    condiciones dentro de una misma corrida experimental, evitando sesgos por casos dispares.
    """
    runs: Dict[str, List[EvaluationRecord]] = {}
    for r in records:
        if r.target == target:
            runs.setdefault(r.corrida_id or 'general', []).append(r)

    total_common_cases = 0
    all_recs_x: List[EvaluationRecord] = []
    all_recs_y: List[EvaluationRecord] = []
    per_run_details: Dict[str, Any] = {}

    for run_id, run_records in runs.items():
        cases_x = {
            (r.pregunta_id or r.caso_ciego_id): r
            for r in run_records
            if r.condicion == cond_x and r.is_evaluable
        }
        cases_y = {
            (r.pregunta_id or r.caso_ciego_id): r
            for r in run_records
            if r.condicion == cond_y and r.is_evaluable
        }

        common_ids = sorted(set(cases_x.keys()) & set(cases_y.keys()))
        only_x = sorted(set(cases_x.keys()) - set(cases_y.keys()))
        only_y = sorted(set(cases_y.keys()) - set(cases_x.keys()))

        run_recs_x = [cases_x[cid] for cid in common_ids]
        run_recs_y = [cases_y[cid] for cid in common_ids]

        all_recs_x.extend(run_recs_x)
        all_recs_y.extend(run_recs_y)
        total_common_cases += len(common_ids)

        per_run_details[run_id] = {
            'casos_comunes': len(common_ids),
            'casos_comunes_ids': common_ids,
            'casos_solo_en_x': only_x,
            'casos_solo_en_y': only_y,
        }

    slice_x = compute_slice_metrics(all_recs_x, f"{cond_x}_comunes")
    slice_y = compute_slice_metrics(all_recs_y, f"{cond_y}_comunes")
    deltas = compare_slices(slice_x, slice_y, cond_x, cond_y)

    return {
        'condicion_x': cond_x,
        'condicion_y': cond_y,
        'target': target,
        'total_casos_comunes_evaluables': total_common_cases,
        'por_corrida': per_run_details,
        'metricas_condicion_x': slice_x,
        'metricas_condicion_y': slice_y,
        'deltas': deltas,
    }


def compare_paired_pipeline_vs_llm_raw(records: List[EvaluationRecord]) -> Dict[str, Any]:
    """Compara por pares de casos las discrepancias entre la respuesta del pipeline y la salida cruda del LLM.

    Utiliza la clave compuesta corrida_id + pregunta_id + condición para identificar inequívocamente cada
    caso experimental. Una pregunta evaluada en A/B/C produce tres pares independientes de salida original
    y salida final (6 registros en total).

    Separa explícitamente las causas de abstención por citas:
    - Ausencia de citas
    - Citas presentes pero inválidas
    - Casos mixtos
    - No determinables (cuando la información histórica no permite distinguir)
    """
    by_case: Dict[Tuple[str, str, str], Dict[str, EvaluationRecord]] = {}
    for r in records:
        run_id, cid, cond = r.experimental_case_key
        by_case.setdefault((run_id, cid, cond), {})[r.target] = r

    n_pairs = 0
    llm_correct_pipeline_abstained = 0
    llm_correct_pipeline_abstained_by_citations = 0
    llm_substantive_pipeline_abstained = 0

    # Separación explícita de citas
    llm_sin_citas_pipeline_abstained = 0
    llm_citas_invalidas_pipeline_abstained = 0
    llm_citas_mixtas_pipeline_abstained = 0
    llm_citas_no_determinable_pipeline_abstained = 0

    identical_calidad = 0

    for (run_id, cid, cond), targets in by_case.items():
        pipe_rec = targets.get(TARGET_PIPELINE)
        raw_rec = targets.get(TARGET_LLM_RAW)
        if pipe_rec and raw_rec and pipe_rec.is_evaluable and raw_rec.is_evaluable:
            n_pairs += 1
            is_citation_abstention = (
                pipe_rec.is_abstention
                and (
                    pipe_rec.motivo_abstencion == ABSTENTION_REASON_INVALID_CITATIONS
                    or 'citas_invalidas_o_ausentes' in pipe_rec.motivo_abstencion
                    or ABSTENTION_REASON_INVALID_CITATIONS in pipe_rec.justificacion
                    or ABSTENTION_REASON_INVALID_CITATIONS in pipe_rec.incidencia
                )
            )

            if raw_rec.calidad_respuesta == QUALITY_CORRECT and pipe_rec.is_abstention:
                llm_correct_pipeline_abstained += 1
                if is_citation_abstention:
                    llm_correct_pipeline_abstained_by_citations += 1

            if raw_rec.is_substantive_response and pipe_rec.is_abstention:
                llm_substantive_pipeline_abstained += 1

            if pipe_rec.is_abstention:
                cat = raw_rec.citations_category or pipe_rec.citations_category
                if not cat:
                    cat = classify_citation_status(
                        cita_pertenece=raw_rec.cita_pertenece_contexto,
                        total_citations=raw_rec.citations_count,
                        invalid_citations=raw_rec.citations_invalid_count,
                        citations_valid_bool=raw_rec.citations_valid,
                        abstention_reason=pipe_rec.motivo_abstencion if is_citation_abstention else '',
                    )

                if is_citation_abstention:
                    if cat == CITATION_CAT_ABSENT:
                        llm_sin_citas_pipeline_abstained += 1
                    elif cat == CITATION_CAT_INVALID_PRESENT:
                        llm_citas_invalidas_pipeline_abstained += 1
                    elif cat == CITATION_CAT_MIXED:
                        llm_citas_mixtas_pipeline_abstained += 1
                    elif cat == CITATION_CAT_INDETERMINATE:
                        llm_citas_no_determinable_pipeline_abstained += 1
                    elif raw_rec.cita_pertenece_contexto == CITATION_IN_CONTEXT_NO:
                        llm_citas_invalidas_pipeline_abstained += 1
                    elif raw_rec.cita_pertenece_contexto == CITATION_NO_CITATIONS:
                        llm_sin_citas_pipeline_abstained += 1
                else:
                    if cat == CITATION_CAT_INVALID_PRESENT or raw_rec.cita_pertenece_contexto == CITATION_IN_CONTEXT_NO:
                        llm_citas_invalidas_pipeline_abstained += 1
                    elif cat == CITATION_CAT_ABSENT or raw_rec.cita_pertenece_contexto == CITATION_NO_CITATIONS:
                        llm_sin_citas_pipeline_abstained += 1
                    elif cat == CITATION_CAT_MIXED:
                        llm_citas_mixtas_pipeline_abstained += 1

            if raw_rec.calidad_respuesta == pipe_rec.calidad_respuesta:
                identical_calidad += 1

    return {
        'pares_evaluables': n_pairs,
        'llm_correcto_pero_pipeline_abstuvo': fraction(
            llm_correct_pipeline_abstained, n_pairs,
            'Casos donde el LLM crudo respondió correctamente pero el pipeline se abstuvo'
        ),
        'llm_correcto_pero_pipeline_abstuvo_por_citas_t16': fraction(
            llm_correct_pipeline_abstained_by_citations, n_pairs,
            'Casos donde el LLM crudo respondió correctamente pero el pipeline se abstuvo con motivo formal T16 citas_invalidas_o_ausentes'
        ),
        'llm_sustantivo_pero_pipeline_abstuvo': fraction(
            llm_substantive_pipeline_abstained, n_pairs,
            'Casos donde el LLM crudo generó respuesta sustantiva pero el pipeline aplicó abstención'
        ),
        'desglose_citas_abstencion_pipeline': {
            'llm_sin_citas_y_pipeline_abstuvo': fraction(
                llm_sin_citas_pipeline_abstained, n_pairs,
                'Casos donde el LLM crudo omitió citas y el pipeline se abstuvo'
            ),
            'llm_citas_invalidas_y_pipeline_abstuvo': fraction(
                llm_citas_invalidas_pipeline_abstained, n_pairs,
                'Casos donde el LLM crudo incluyó citas presentes pero formalmente inválidas y el pipeline se abstuvo'
            ),
            'llm_citas_mixtas_y_pipeline_abstuvo': fraction(
                llm_citas_mixtas_pipeline_abstained, n_pairs,
                'Casos donde el LLM crudo incluyó citas mixtas (válidas e inválidas) y el pipeline se abstuvo'
            ),
            'llm_citas_no_determinables_y_pipeline_abstuvo': fraction(
                llm_citas_no_determinable_pipeline_abstained, n_pairs,
                'Casos donde la información histórica no permite distinguir entre citas ausentes o inválidas'
            ),
        },
        'llm_citas_invalidas_y_pipeline_abstuvo': fraction(
            llm_citas_invalidas_pipeline_abstained, n_pairs,
            'Casos donde el LLM crudo tuvo citas presentes pero inválidas y el pipeline protegió absteniéndose'
        ),
        'llm_sin_citas_y_pipeline_abstuvo': fraction(
            llm_sin_citas_pipeline_abstained, n_pairs,
            'Casos donde el LLM crudo omitió citas y el pipeline protegió absteniéndose'
        ),
        'llm_citas_no_determinables_y_pipeline_abstuvo': fraction(
            llm_citas_no_determinable_pipeline_abstained, n_pairs,
            'Casos donde no se puede determinar si las citas fueron ausentes o inválidas y el pipeline se abstuvo'
        ),
        'concordancia_calidad_respuesta': fraction(
            identical_calidad, n_pairs,
            'Casos donde la calidad asignada al LLM crudo y al pipeline fue idéntica'
        ),
    }


def _extract_case_config(case: Dict[str, Any]) -> Dict[str, Any]:
    """Extrae y normaliza los parámetros de configuración experimental de un caso."""
    return {
        'provider': case.get('provider') or 'no_especificado',
        'model': case.get('model') or 'no_especificado',
        'seed': case.get('seed'),
        'retriever': case.get('retriever') or 'no_especificado',
        'top_k': case.get('top_k'),
        'temperature': case.get('temperature'),
        'prompt_version': case.get('prompt_version') or 'no_especificado',
    }


def _config_signature(cfg: Dict[str, Any]) -> Tuple[Any, ...]:
    """Genera una firma hashable para verificar compatibilidad estricta de configuraciones."""
    temp_val = float(cfg['temperature']) if cfg.get('temperature') is not None else None
    return (
        str(cfg.get('provider') or '').strip().lower(),
        str(cfg.get('model') or '').strip(),
        cfg.get('seed'),
        str(cfg.get('retriever') or '').strip().lower(),
        cfg.get('top_k'),
        temp_val,
        str(cfg.get('prompt_version') or '').strip(),
    )


def compute_quality_latencies(records: List[EvaluationRecord]) -> Dict[str, Any]:
    """Calcula métricas agregadas de latencia (media, mediana, p95, n_validas) sin duplicaciones.

    Garantiza:
    - Agrupación por clave experimental única (corrida_id, pregunta_id, condicion) para evitar
      duplicar latencias entre salidas raw y pipeline.
    - Exclusión estricta de valores ausentes, negativos o no finitos sin reemplazarlos por cero.
    - Separación formal entre latencia de pipeline y latencia de generación.
    - Verificación rigurosa de compatibilidad de configuración experimental (provider, model, seed,
      temperature, top_k, retriever, prompt_version).
    - Separación de configuraciones incompatibles evitando mezclarlas en agregados comparativos.
    - Conservación estricta de valores válidos iguales a cero (como temperature=0 y seed=0).
    - Desacoplamiento de la disponibilidad o estado de la evaluación humana (pendiente/no evaluable).
    - Documentación explícita del método de interpolación lineal para el percentil 95.
    """
    # 1. Deduplicar por caso experimental único (corrida_id, pregunta_id, condicion)
    unique_cases: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for r in records:
        key = r.experimental_case_key
        if key not in unique_cases:
            unique_cases[key] = {
                'corrida_id': r.corrida_id or 'general',
                'pregunta_id': r.pregunta_id or r.caso_ciego_id or r.evaluacion_id,
                'condicion': r.condicion or 'general',
                'latency_pipeline_seconds': r.latency_pipeline_seconds,
                'latency_generation_seconds': r.latency_generation_seconds,
                'provider': r.provider,
                'model': r.model,
                'seed': r.seed,
                'retriever': r.retriever,
                'top_k': r.top_k,
                'temperature': r.temperature,
                'prompt_version': r.prompt_version,
            }
        else:
            case_entry = unique_cases[key]
            if case_entry['latency_pipeline_seconds'] is None and r.latency_pipeline_seconds is not None:
                case_entry['latency_pipeline_seconds'] = r.latency_pipeline_seconds
            if case_entry['latency_generation_seconds'] is None and r.latency_generation_seconds is not None:
                case_entry['latency_generation_seconds'] = r.latency_generation_seconds
            if not case_entry['provider'] and r.provider:
                case_entry['provider'] = r.provider
            if not case_entry['model'] and r.model:
                case_entry['model'] = r.model
            if case_entry['seed'] is None and r.seed is not None:
                case_entry['seed'] = r.seed
            if not case_entry['retriever'] and r.retriever:
                case_entry['retriever'] = r.retriever
            if case_entry['top_k'] is None and r.top_k is not None:
                case_entry['top_k'] = r.top_k
            if case_entry['temperature'] is None and r.temperature is not None:
                case_entry['temperature'] = r.temperature
            if not case_entry['prompt_version'] and r.prompt_version:
                case_entry['prompt_version'] = r.prompt_version

    # 2. Métricas por condición con verificación de configuración compatible
    por_condicion: Dict[str, Dict[str, Any]] = {}
    for cond in CONDITIONS:
        cond_cases = [c for c in unique_cases.values() if c['condicion'] == cond]
        if not cond_cases:
            por_condicion[cond] = {
                'configuracion_compatible': True,
                'configuracion': {},
                'latencia_pipeline': compute_latency_summary([], f'Latencia del pipeline (s) en {cond}'),
                'latencia_generacion': compute_latency_summary([], f'Latencia de generación LLM (s) en {cond}'),
            }
            continue

        configs_map: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
        for c in cond_cases:
            cfg = _extract_case_config(c)
            configs_map.setdefault(_config_signature(cfg), []).append(c)

        if len(configs_map) == 1:
            pipe_lats = [c['latency_pipeline_seconds'] for c in cond_cases if c['latency_pipeline_seconds'] is not None]
            gen_lats = [c['latency_generation_seconds'] for c in cond_cases if c['latency_generation_seconds'] is not None]
            por_condicion[cond] = {
                'configuracion_compatible': True,
                'configuracion': _extract_case_config(cond_cases[0]),
                'latencia_pipeline': compute_latency_summary(pipe_lats, f'Latencia del pipeline (s) en {cond}'),
                'latencia_generacion': compute_latency_summary(gen_lats, f'Latencia de generación LLM (s) en {cond}'),
            }
        else:
            grupos: List[Dict[str, Any]] = []
            for idx, (sig, c_list) in enumerate(configs_map.items()):
                p_l = [c['latency_pipeline_seconds'] for c in c_list if c['latency_pipeline_seconds'] is not None]
                g_l = [c['latency_generation_seconds'] for c in c_list if c['latency_generation_seconds'] is not None]
                grupos.append({
                    'grupo_id': idx + 1,
                    'configuracion': _extract_case_config(c_list[0]),
                    'latencia_pipeline': compute_latency_summary(p_l, f'Latencia pipeline {cond} cfg{idx+1}'),
                    'latencia_generacion': compute_latency_summary(g_l, f'Latencia generación {cond} cfg{idx+1}'),
                })
            por_condicion[cond] = {
                'configuracion_compatible': False,
                'advertencia': f'Configuraciones incompatibles detectadas ({len(configs_map)} variantes). Separadas para evitar mezclas espurias.',
                'grupos_configuracion': grupos,
                'latencia_pipeline': compute_latency_summary([], f'Latencia pipeline {cond} (incompatible)'),
                'latencia_generacion': compute_latency_summary([], f'Latencia generación {cond} (incompatible)'),
            }

    # 3. Métricas por corrida y condición (separando configuraciones incompatibles)
    por_corrida_y_condicion: Dict[str, Dict[str, Any]] = {}
    runs = sorted(set(c['corrida_id'] for c in unique_cases.values()))
    for run_id in runs:
        por_corrida_y_condicion[run_id] = {}
        for cond in CONDITIONS:
            rc_cases = [c for c in unique_cases.values() if c['corrida_id'] == run_id and c['condicion'] == cond]
            if not rc_cases:
                continue

            configs_map_rc: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
            for c in rc_cases:
                cfg = _extract_case_config(c)
                configs_map_rc.setdefault(_config_signature(cfg), []).append(c)

            if len(configs_map_rc) == 1:
                pipe_lats = [c['latency_pipeline_seconds'] for c in rc_cases if c['latency_pipeline_seconds'] is not None]
                gen_lats = [c['latency_generation_seconds'] for c in rc_cases if c['latency_generation_seconds'] is not None]
                por_corrida_y_condicion[run_id][cond] = {
                    'configuracion_compatible': True,
                    'configuracion': _extract_case_config(rc_cases[0]),
                    'latencia_pipeline': compute_latency_summary(pipe_lats, f'Latencia pipeline {run_id} {cond}'),
                    'latencia_generacion': compute_latency_summary(gen_lats, f'Latencia generación {run_id} {cond}'),
                }
            else:
                grupos_rc: List[Dict[str, Any]] = []
                for idx, (sig, c_list) in enumerate(configs_map_rc.items()):
                    p_l = [c['latency_pipeline_seconds'] for c in c_list if c['latency_pipeline_seconds'] is not None]
                    g_l = [c['latency_generation_seconds'] for c in c_list if c['latency_generation_seconds'] is not None]
                    grupos_rc.append({
                        'grupo_id': idx + 1,
                        'configuracion': _extract_case_config(c_list[0]),
                        'latencia_pipeline': compute_latency_summary(p_l, f'Latencia pipeline {run_id} {cond} cfg{idx+1}'),
                        'latencia_generacion': compute_latency_summary(g_l, f'Latencia generación {run_id} {cond} cfg{idx+1}'),
                    })
                por_corrida_y_condicion[run_id][cond] = {
                    'configuracion_compatible': False,
                    'advertencia': f'Configuraciones incompatibles detectadas en corrida {run_id} ({len(configs_map_rc)} variantes). Separadas.',
                    'grupos_configuracion': grupos_rc,
                    'latencia_pipeline': compute_latency_summary([], f'Latencia pipeline {run_id} {cond} (incompatible)'),
                    'latencia_generacion': compute_latency_summary([], f'Latencia generación {run_id} {cond} (incompatible)'),
                }

    return {
        'metodo_calculo_p95': 'Interpolación lineal entre los dos rangos más cercanos (Hyndman y Fan Tipo 7 / numpy.percentile method="linear")',
        'criterios_exclusion': 'Exclusión estricta de valores ausentes, negativos o no finitos (NaN/Inf). No reemplazo por cero.',
        'por_condicion': por_condicion,
        'por_corrida_y_condicion': por_corrida_y_condicion,
    }


@dataclass
class QualityEvaluationReport:
    """Informe consolidado de métricas de calidad de respuestas (T18)."""

    manifest: Dict[str, Any]
    resumen_global: Dict[str, Any]
    por_origen_respuesta: Dict[str, Dict[str, Any]]
    por_condicion: Dict[str, Dict[str, Any]]
    cruzado_condicion_origen: Dict[str, Dict[str, Dict[str, Any]]]
    comparacion_origenes: Dict[str, Any]
    comparacion_condiciones: Dict[str, Any]
    emparejamiento_pipeline_vs_llm: Dict[str, Any]
    metricas_latencia: Dict[str, Any] = field(default_factory=dict)
    desacuerdos_sin_consenso: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el informe a un diccionario serializable."""
        return {
            'manifest': self.manifest,
            'resumen_global': self.resumen_global,
            'por_origen_respuesta': self.por_origen_respuesta,
            'por_condicion': self.por_condicion,
            'cruzado_condicion_origen': self.cruzado_condicion_origen,
            'comparacion_origenes': self.comparacion_origenes,
            'comparacion_condiciones': self.comparacion_condiciones,
            'emparejamiento_pipeline_vs_llm': self.emparejamiento_pipeline_vs_llm,
            'metricas_latencia': self.metricas_latencia,
            'desacuerdos_sin_consenso': self.desacuerdos_sin_consenso,
        }

    def save_json(self, path: Union[str, Path]) -> None:
        """Guarda el reporte en formato JSON indentado."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')

    def to_csv_rows(self) -> List[Dict[str, Any]]:
        """Genera una lista de filas planas estructuradas para análisis estadístico (formato largo/tidy)."""
        rows: List[Dict[str, Any]] = []

        def extract_metrics_to_rows(cond: str, target: str, slice_data: Dict[str, Any]):
            # 1. Contabilidad
            acc = slice_data.get('contabilidad_casos', {})
            rows.append({
                'condicion': cond, 'origen_respuesta': target, 'categoria': 'contabilidad',
                'metrica': 'total_anotaciones', 'numerador': acc.get('total_anotaciones', 0),
                'denominador': acc.get('total_anotaciones', 0), 'valor': 1.0 if acc.get('total_anotaciones') else None,
                'porcentaje': '100.0%' if acc.get('total_anotaciones') else 'N/A',
                'descripcion': 'Total de anotaciones en el corte',
            })
            rows.append({
                'condicion': cond, 'origen_respuesta': target, 'categoria': 'contabilidad',
                'metrica': 'casos_evaluables', 'numerador': acc.get('casos_evaluables', 0),
                'denominador': acc.get('total_anotaciones', 0),
                'valor': acc.get('tasa_completitud', {}).get('value'),
                'porcentaje': f"{acc.get('tasa_completitud', {}).get('rate_percent', 0.0)}%" if acc.get('tasa_completitud', {}).get('rate_percent') is not None else 'N/A',
                'descripcion': 'Casos evaluables con etiquetas completadas',
            })
            rows.append({
                'condicion': cond, 'origen_respuesta': target, 'categoria': 'contabilidad',
                'metrica': 'casos_pendientes', 'numerador': acc.get('casos_pendientes', 0),
                'denominador': acc.get('total_anotaciones', 0),
                'valor': (acc.get('casos_pendientes', 0) / acc.get('total_anotaciones')) if acc.get('total_anotaciones') else None,
                'porcentaje': f"{round((acc.get('casos_pendientes', 0) / acc.get('total_anotaciones')) * 100, 2)}%" if acc.get('total_anotaciones') else 'N/A',
                'descripcion': 'Anotaciones humanas pendientes',
            })
            rows.append({
                'condicion': cond, 'origen_respuesta': target, 'categoria': 'contabilidad',
                'metrica': 'casos_no_evaluables', 'numerador': acc.get('casos_no_evaluables', 0),
                'denominador': acc.get('total_anotaciones', 0),
                'valor': (acc.get('casos_no_evaluables', 0) / acc.get('total_anotaciones')) if acc.get('total_anotaciones') else None,
                'porcentaje': f"{round((acc.get('casos_no_evaluables', 0) / acc.get('total_anotaciones')) * 100, 2)}%" if acc.get('total_anotaciones') else 'N/A',
                'descripcion': 'Casos excluidos por material insuficiente o sin verificar',
            })

            # Fracciones helper
            def add_fraction_row(categoria: str, metrica: str, frac_dict: Dict[str, Any]):
                num = frac_dict.get('numerator')
                den = frac_dict.get('denominator')
                val = frac_dict.get('value')
                pct = f"{frac_dict.get('rate_percent')}%" if frac_dict.get('rate_percent') is not None else 'N/A'
                desc = frac_dict.get('description', '')
                rows.append({
                    'condicion': cond, 'origen_respuesta': target, 'categoria': categoria,
                    'metrica': metrica, 'numerador': num, 'denominador': den, 'valor': val,
                    'porcentaje': pct, 'descripcion': desc,
                })

            # 2. Calidad de contenido
            cal = slice_data.get('calidad_contenido', {})
            for m in ('exactitud_humana_contenido', 'correctas_sobre_respuestas_sustantivas',
                      'tasa_respuestas_parciales', 'tasa_respuestas_incorrectas',
                      'calidad_no_aplica_abstencion', 'parciales_sobre_respuestas_sustantivas',
                      'incorrectas_sobre_respuestas_sustantivas'):
                if m in cal:
                    add_fraction_row('calidad_contenido', m, cal[m])

            # 3. Abstención y adecuación
            abst = slice_data.get('abstencion_y_adecuacion', {})
            for m in ('tasa_abstencion', 'adecuacion_abstenciones', 'tasa_abstenciones_inadecuadas',
                      'abstenciones_adecuadas_sobre_total_consultas', 'abstenciones_inadecuadas_sobre_total_consultas'):
                if m in abst:
                    add_fraction_row('abstencion', m, abst[m])

            # 4. Citas y sustento
            cit = slice_data.get('validez_y_sustento_citas', {})
            if 'citas_validas_completas' in cit:
                add_fraction_row('citas', 'citas_validas_completas', cit['citas_validas_completas'])
            for m, frac in cit.get('pertenencia_contexto', {}).items():
                add_fraction_row('citas_pertenencia', m, frac)
            for m, frac in cit.get('sustento_factual', {}).items():
                add_fraction_row('citas_sustento', m, frac)
            for m, frac in cit.get('brecha_pertenencia_sin_sustento', {}).items():
                add_fraction_row('citas_brecha', m, frac)
            for m, frac in cit.get('errores_vigencia', {}).items():
                add_fraction_row('citas_vigencia', m, frac)
            for m, frac in cit.get('diferenciacion_citas', {}).items():
                add_fraction_row('citas_diferenciacion', m, frac)

        # Extraer filas cruzadas (condición x origen)
        for cond, targets in self.cruzado_condicion_origen.items():
            for target, sdata in targets.items():
                extract_metrics_to_rows(cond, target, sdata)

        # Si no había divisiones cruzadas, extraer de por_origen_respuesta y por_condicion
        if not rows:
            for target, sdata in self.por_origen_respuesta.items():
                extract_metrics_to_rows('todas', target, sdata)
            for cond, sdata in self.por_condicion.items():
                extract_metrics_to_rows(cond, 'todos', sdata)

        # 5. Métricas de latencia por condición (sin duplicar observaciones entre raw y pipeline)
        lat_por_cond = self.metricas_latencia.get('por_condicion', {})
        for cond, lat_data in lat_por_cond.items():
            compat = lat_data.get('configuracion_compatible', True)
            if compat:
                for tipo_lat in ('latencia_pipeline', 'latencia_generacion'):
                    ldata = lat_data.get(tipo_lat, {})
                    obs = ldata.get('observaciones_validas', 0)
                    media = ldata.get('media')
                    mediana = ldata.get('mediana')
                    p95 = ldata.get('percentil_95')
                    origen_tag = 'pipeline' if tipo_lat == 'latencia_pipeline' else 'llm_raw'

                    rows.append({
                        'condicion': cond, 'origen_respuesta': origen_tag, 'categoria': 'latencia',
                        'metrica': f'{tipo_lat}_media_segundos', 'numerador': obs, 'denominador': obs,
                        'valor': media, 'porcentaje': f"{media}s" if media is not None else 'N/A',
                        'descripcion': f'Media de {tipo_lat} en segundos (n={obs})',
                    })
                    rows.append({
                        'condicion': cond, 'origen_respuesta': origen_tag, 'categoria': 'latencia',
                        'metrica': f'{tipo_lat}_mediana_segundos', 'numerador': obs, 'denominador': obs,
                        'valor': mediana, 'porcentaje': f"{mediana}s" if mediana is not None else 'N/A',
                        'descripcion': f'Mediana de {tipo_lat} en segundos (n={obs})',
                    })
                    rows.append({
                        'condicion': cond, 'origen_respuesta': origen_tag, 'categoria': 'latencia',
                        'metrica': f'{tipo_lat}_p95_segundos', 'numerador': obs, 'denominador': obs,
                        'valor': p95, 'porcentaje': f"{p95}s" if p95 is not None else 'N/A',
                        'descripcion': f'Percentil 95 de {tipo_lat} en segundos (n={obs}, interpolación lineal)',
                    })
            else:
                for grp in lat_data.get('grupos_configuracion', []):
                    gid = grp.get('grupo_id')
                    for tipo_lat in ('latencia_pipeline', 'latencia_generacion'):
                        ldata = grp.get(tipo_lat, {})
                        obs = ldata.get('observaciones_validas', 0)
                        media = ldata.get('media')
                        mediana = ldata.get('mediana')
                        p95 = ldata.get('percentil_95')
                        origen_tag = 'pipeline' if tipo_lat == 'latencia_pipeline' else 'llm_raw'

                        rows.append({
                            'condicion': f"{cond}_cfg{gid}", 'origen_respuesta': origen_tag, 'categoria': 'latencia',
                            'metrica': f'{tipo_lat}_media_segundos', 'numerador': obs, 'denominador': obs,
                            'valor': media, 'porcentaje': f"{media}s" if media is not None else 'N/A',
                            'descripcion': f'Media de {tipo_lat} grupo {gid} en segundos (n={obs})',
                        })
                        rows.append({
                            'condicion': f"{cond}_cfg{gid}", 'origen_respuesta': origen_tag, 'categoria': 'latencia',
                            'metrica': f'{tipo_lat}_mediana_segundos', 'numerador': obs, 'denominador': obs,
                            'valor': mediana, 'porcentaje': f"{mediana}s" if mediana is not None else 'N/A',
                            'descripcion': f'Mediana de {tipo_lat} grupo {gid} en segundos (n={obs})',
                        })
                        rows.append({
                            'condicion': f"{cond}_cfg{gid}", 'origen_respuesta': origen_tag, 'categoria': 'latencia',
                            'metrica': f'{tipo_lat}_p95_segundos', 'numerador': obs, 'denominador': obs,
                            'valor': p95, 'porcentaje': f"{p95}s" if p95 is not None else 'N/A',
                            'descripcion': f'Percentil 95 de {tipo_lat} grupo {gid} en segundos (n={obs}, interpolación lineal)',
                        })

        return rows

    def save_csv(self, path: Union[str, Path]) -> None:
        """Guarda las métricas en un archivo CSV tabular ordenado."""
        rows = self.to_csv_rows()
        if not rows:
            return
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = ['condicion', 'origen_respuesta', 'categoria', 'metrica', 'numerador', 'denominador', 'valor', 'porcentaje', 'descripcion']
        with p.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def to_comparison_table_csv(self, target: str = TARGET_PIPELINE) -> List[Dict[str, str]]:
        """Genera una tabla comparativa horizontal estilo artículo científico para A vs B vs C."""
        metrics_to_include = [
            ('Exactitud humana de contenido (correctas / todas las consultas evaluables, incluye abstenciones)', ['calidad_contenido', 'exactitud_humana_contenido']),
            ('Exactitud condicional en respuestas sustantivas (correctas / respuestas sustantivas)', ['calidad_contenido', 'correctas_sobre_respuestas_sustantivas']),
            ('Tasa de respuestas parciales (parcial / evaluables)', ['calidad_contenido', 'tasa_respuestas_parciales']),
            ('Tasa de respuestas incorrectas (incorrecta / evaluables)', ['calidad_contenido', 'tasa_respuestas_incorrectas']),
            ('Tasa de abstención (abstenciones / evaluables)', ['abstencion_y_adecuacion', 'tasa_abstencion']),
            ('Adecuación de abstenciones (adecuadas / abstenciones)', ['abstencion_y_adecuacion', 'adecuacion_abstenciones']),
            ('Citas válidas completas (en contexto + sustento / sustantivas)', ['validez_y_sustento_citas', 'citas_validas_completas']),
            ('Pertenencia al contexto (en contexto / sustantivas)', ['validez_y_sustento_citas', 'pertenencia_contexto', 'citas_pertenecen_si']),
            ('Sustento factual completo (sustento / sustantivas)', ['validez_y_sustento_citas', 'sustento_factual', 'sustento_completo']),
            ('Citas en contexto pero sustento parcial/nulo', ['validez_y_sustento_citas', 'brecha_pertenencia_sin_sustento', 'total_pertenecen_sin_sustento_completo']),
            ('Errores de vigencia normativa (sobre sustantivas)', ['validez_y_sustento_citas', 'errores_vigencia', 'sobre_respuestas_sustantivas']),
            ('Ausencia de citas (respuestas sustantivas sin citas)', ['validez_y_sustento_citas', 'diferenciacion_citas', 'ausencia_citas']),
            ('Citas presentes pero inválidas (fuera de fragmentos)', ['validez_y_sustento_citas', 'diferenciacion_citas', 'citas_presentes_invalidas']),
            ('Citas formalmente válidas (en fragmentos)', ['validez_y_sustento_citas', 'diferenciacion_citas', 'citas_formalmente_validas']),
            ('Casos mixtos de citación (citas válidas e inválidas)', ['validez_y_sustento_citas', 'diferenciacion_citas', 'casos_mixtos']),
            ('Citas no determinables (información histórica)', ['validez_y_sustento_citas', 'diferenciacion_citas', 'no_determinable']),
        ]

        table: List[Dict[str, str]] = []
        for label, path in metrics_to_include:
            row: Dict[str, str] = {'metrica': label, 'origen_respuesta': target}
            for cond in CONDITIONS:
                slice_data = self.cruzado_condicion_origen.get(cond, {}).get(target)
                if not slice_data:
                    slice_data = self.por_condicion.get(cond)

                if slice_data:
                    curr = slice_data
                    for k in path:
                        curr = curr.get(k, {}) if isinstance(curr, dict) else {}
                    num = curr.get('numerator')
                    den = curr.get('denominator')
                    pct = curr.get('rate_percent')
                    if den and den > 0 and pct is not None:
                        row[cond] = f"{pct}% ({num}/{den})"
                    elif den == 0:
                        row[cond] = "N/A (0/0)"
                    else:
                        row[cond] = "N/A"
                else:
                    row[cond] = "N/A"
            table.append(row)

        # Filas de telemetría de latencias
        lat_por_cond = self.metricas_latencia.get('por_condicion', {})
        for tipo_lat, label in [
            ('latencia_pipeline', 'Latencia del pipeline (media [mediana, p95] s)'),
            ('latencia_generacion', 'Latencia de generación LLM (media [mediana, p95] s)'),
        ]:
            row_lat: Dict[str, str] = {'metrica': label, 'origen_respuesta': target}
            for cond in CONDITIONS:
                ldata = lat_por_cond.get(cond, {}).get(tipo_lat, {})
                obs = ldata.get('observaciones_validas', 0)
                media = ldata.get('media')
                mediana = ldata.get('mediana')
                p95 = ldata.get('percentil_95')
                if obs > 0 and media is not None:
                    row_lat[cond] = f"{media}s [med: {mediana}s, p95: {p95}s] (n={obs})"
                elif not lat_por_cond.get(cond, {}).get('configuracion_compatible', True):
                    row_lat[cond] = "Incompatible (separado)"
                else:
                    row_lat[cond] = "N/A (0/0)"
            table.append(row_lat)

        return table

    def save_comparison_csv(self, path: Union[str, Path], target: str = TARGET_PIPELINE) -> None:
        """Guarda la tabla comparativa horizontal en formato CSV para el artículo científico."""
        table = self.to_comparison_table_csv(target)
        if not table:
            return
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = ['metrica', 'origen_respuesta', *CONDITIONS]
        with p.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(table)


def evaluate_quality(
    annotations: Union[str, Path, List[Dict[str, Any]]],
    blind_mapping: Optional[Union[Dict[str, Any], Path, str]] = None,
    manifest_info: Optional[Dict[str, Any]] = None,
    resolve_consensus: bool = True,
    traces_source: Optional[Union[str, Path, List[Dict[str, Any]]]] = None,
) -> QualityEvaluationReport:
    """Función principal para la evaluación de calidad de respuestas (T18).

    Toma anotaciones humanas en CSV, JSON o lista de dicts, las normaliza según la rúbrica v0.2,
    resuelve filas de consenso y calcula métricas agregadas globales, por condición (A/B/C) y
    por origen de respuesta (pipeline vs llm_raw), integrando latencias y diferenciación de citas.
    """
    records = load_annotations(annotations, blind_mapping, traces_source)

    conflicts: List[Dict[str, Any]] = []
    if resolve_consensus:
        res_output = resolve_consensus_records(records, return_conflicts=True)
        if isinstance(res_output, tuple):
            eval_records, conflicts = res_output
        else:
            eval_records = res_output
    else:
        eval_records = records

    # 1. Resumen global
    resumen_global = compute_slice_metrics(eval_records, 'global')

    # 2. Desglose por origen de respuesta (pipeline vs llm_raw)
    por_origen: Dict[str, Dict[str, Any]] = {}
    for target in TARGETS:
        target_records = [r for r in eval_records if r.target == target]
        por_origen[target] = compute_slice_metrics(target_records, f'target_{target}')

    # 3. Desglose por condición (A, B, C)
    por_condicion: Dict[str, Dict[str, Any]] = {}
    for cond in CONDITIONS:
        cond_records = [r for r in eval_records if r.condicion == cond]
        por_condicion[cond] = compute_slice_metrics(cond_records, f'condicion_{cond}')

    # 4. Cruce condición x origen
    cruzado: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for cond in CONDITIONS:
        cruzado[cond] = {}
        for target in TARGETS:
            subset = [r for r in eval_records if r.condicion == cond and r.target == target]
            cruzado[cond][target] = compute_slice_metrics(subset, f'{cond}_{target}')

    # 5. Comparaciones
    comparacion_origenes = compare_slices(
        por_origen.get(TARGET_PIPELINE, {}),
        por_origen.get(TARGET_LLM_RAW, {}),
        'pipeline',
        'llm_raw',
    )

    # Comparaciones pareadas rigurosas sobre casos comunes evaluables
    comparacion_condiciones: Dict[str, Any] = {}
    if 'A_sin_defensa' in por_condicion and 'B_defensa_basica' in por_condicion:
        comparacion_condiciones['B_vs_A_pareado'] = compute_paired_condition_comparison(
            eval_records, 'B_defensa_basica', 'A_sin_defensa', TARGET_PIPELINE
        )
    if 'A_sin_defensa' in por_condicion and 'C_defensa_propuesta' in por_condicion:
        comparacion_condiciones['C_vs_A_pareado'] = compute_paired_condition_comparison(
            eval_records, 'C_defensa_propuesta', 'A_sin_defensa', TARGET_PIPELINE
        )
    if 'B_defensa_basica' in por_condicion and 'C_defensa_propuesta' in por_condicion:
        comparacion_condiciones['C_vs_B_pareado'] = compute_paired_condition_comparison(
            eval_records, 'C_defensa_propuesta', 'B_defensa_basica', TARGET_PIPELINE
        )

    emparejamiento = compare_paired_pipeline_vs_llm_raw(eval_records)

    # 6. Métricas de latencia desacopladas y no duplicadas
    metricas_latencia = compute_quality_latencies(eval_records)

    # 7. Manifiesto del informe
    manifest = {
        'tarea': 'T18_metricas_calidad_respuestas',
        'fecha_evaluacion_utc': datetime.now(timezone.utc).isoformat(),
        'rubrica_version': '0.2',
        'total_anotaciones_cargadas': len(records),
        'total_anotaciones_analizadas': len(eval_records),
        'consenso_resuelto': resolve_consensus,
        'condiciones_reconocidas': list(CONDITIONS),
        'origenes_reconocidos': list(TARGETS),
        'desacuerdos_sin_consenso_detectados': len(conflicts),
        'metodo_p95': metricas_latencia.get('metodo_calculo_p95'),
    }
    if manifest_info:
        manifest.update(manifest_info)

    return QualityEvaluationReport(
        manifest=manifest,
        resumen_global=resumen_global,
        por_origen_respuesta=por_origen,
        por_condicion=por_condicion,
        cruzado_condicion_origen=cruzado,
        comparacion_origenes=comparacion_origenes,
        comparacion_condiciones=comparacion_condiciones,
        emparejamiento_pipeline_vs_llm=emparejamiento,
        metricas_latencia=metricas_latencia,
        desacuerdos_sin_consenso=conflicts,
    )
