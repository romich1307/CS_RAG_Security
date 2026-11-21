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


def load_traces_dict(traces_source: Union[str, Path, List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    """Carga y mapea trazas experimentales por ID de pregunta/caso para fundamentar motivos de abstención."""
    traces_data: List[Dict[str, Any]] = []
    if isinstance(traces_source, (str, Path)):
        p = Path(traces_source)
        if not p.exists():
            return {}
        if p.suffix.lower() == '.json':
            content = json.loads(p.read_text(encoding='utf-8'))
            traces_data = content if isinstance(content, list) else content.get('traces', [])
        else:
            with p.open('r', encoding='utf-8', errors='replace') as f:
                traces_data = list(csv.DictReader(f))
    elif isinstance(traces_source, list):
        traces_data = traces_source
    else:
        return {}

    by_id: Dict[str, Dict[str, Any]] = {}
    for t in traces_data:
        tid = t.get('id') or t.get('pregunta_id') or t.get('case_id')
        if tid:
            by_id[str(tid)] = t
    return by_id


def load_annotations(
    source: Union[str, Path, List[Dict[str, Any]]],
    blind_mapping: Optional[Union[Dict[str, Any], Path, str]] = None,
    traces_source: Optional[Union[str, Path, List[Dict[str, Any]]]] = None,
) -> List[EvaluationRecord]:
    """Carga y normaliza anotaciones desde un archivo CSV, JSON o lista de diccionarios.

    Permite incorporar opcionalmente un mapa de desenmascaramiento ciego (blind_mapping)
    para asociar caso_ciego_id con su condición experimental real (A, B, C) y target,
    así como fuentes de trazas experimentales reales (traces_source) de T16 para fundamentar
    los diagnósticos canónicos de abstención.
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

    traces_dict: Dict[str, Dict[str, Any]] = load_traces_dict(traces_source) if traces_source else {}
    cached_trace_files: Dict[str, Dict[str, Dict[str, Any]]] = {}

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

        # Fundamentar abstención en trazas reales de T16 si no fue provisto en la anotación
        if not motivo_abs:
            qid = raw.get('pregunta_id', '') or caso_id
            if qid in traces_dict:
                motivo_abs = traces_dict[qid].get('abstention_reason') or ''
            ref_salida = raw.get('referencia_salida', '')
            if not motivo_abs and ref_salida and '#' in ref_salida:
                file_part, key_part = ref_salida.split('#', 1)
                trace_file_path = Path(file_part)
                if trace_file_path.exists():
                    if file_part not in cached_trace_files:
                        cached_trace_files[file_part] = load_traces_dict(trace_file_path)
                    sub_id = key_part.split('.')[0] if '.' in key_part else key_part
                    if sub_id in cached_trace_files[file_part]:
                        motivo_abs = cached_trace_files[file_part][sub_id].get('abstention_reason') or ''

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
        case_id = r.caso_ciego_id or r.pregunta_id or r.evaluacion_id or f'row_{idx}'
        key = (r.corrida_id, case_id, r.condicion, r.target)
        grouped.setdefault(key, []).append(r)

    resolved: List[EvaluationRecord] = []
    conflicts: List[Dict[str, Any]] = []

    keys_to_compare = (
        'calidad_respuesta', 'tipo_salida', 'abstencion_adecuada',
        'cita_pertenece_contexto', 'cita_sustenta_respuesta', 'error_vigencia'
    )

    for (_, case_id, condicion, target), items in grouped.items():
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
                    'corrida_id': items[0].corrida_id,
                    'caso_id': case_id,
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
                    evaluacion_id=f"CONFLICT-{case_id}-{target}",
                    corrida_id=items[0].corrida_id,
                    caso_ciego_id=items[0].caso_ciego_id,
                    pregunta_id=items[0].pregunta_id,
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
                    condicion=items[0].condicion,
                    target=target,
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

    Verifica de manera explícita si las abstenciones del pipeline corresponden al motivo canónico
    de T16 citas_invalidas_o_ausentes, en lugar de asumir causas no sustentadas.
    """
    by_case: Dict[Tuple[str, str], Dict[str, EvaluationRecord]] = {}
    for r in records:
        cid = r.pregunta_id or r.caso_ciego_id or r.evaluacion_id
        by_case.setdefault((r.corrida_id, cid), {})[r.target] = r

    n_pairs = 0
    llm_correct_pipeline_abstained = 0
    llm_correct_pipeline_abstained_by_citations = 0
    llm_substantive_pipeline_abstained = 0
    llm_citas_invalidas_pipeline_abstained = 0
    identical_calidad = 0

    for _, targets in by_case.items():
        pipe_rec = targets.get(TARGET_PIPELINE)
        raw_rec = targets.get(TARGET_LLM_RAW)
        if pipe_rec and raw_rec and pipe_rec.is_evaluable and raw_rec.is_evaluable:
            n_pairs += 1
            is_citation_abstention = (
                pipe_rec.is_abstention
                and (
                    pipe_rec.motivo_abstencion == ABSTENTION_REASON_INVALID_CITATIONS
                    or ABSTENTION_REASON_INVALID_CITATIONS in pipe_rec.justificacion
                    or ABSTENTION_REASON_INVALID_CITATIONS in pipe_rec.incidencia
                    or 'citas_invalidas_o_ausentes' in pipe_rec.motivo_abstencion
                )
            )

            if raw_rec.calidad_respuesta == QUALITY_CORRECT and pipe_rec.is_abstention:
                llm_correct_pipeline_abstained += 1
                if is_citation_abstention:
                    llm_correct_pipeline_abstained_by_citations += 1

            if raw_rec.is_substantive_response and pipe_rec.is_abstention:
                llm_substantive_pipeline_abstained += 1

            if raw_rec.cita_pertenece_contexto != CITATION_IN_CONTEXT_YES and pipe_rec.is_abstention:
                llm_citas_invalidas_pipeline_abstained += 1

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
        'llm_citas_invalidas_y_pipeline_abstuvo': fraction(
            llm_citas_invalidas_pipeline_abstained, n_pairs,
            'Casos donde el LLM crudo tuvo citas inválidas y el pipeline protegió absteniéndose'
        ),
        'concordancia_calidad_respuesta': fraction(
            identical_calidad, n_pairs,
            'Casos donde la calidad asignada al LLM crudo y al pipeline fue idéntica'
        ),
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
    por origen de respuesta (pipeline vs llm_raw).
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

    # 6. Manifiesto del informe
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
        desacuerdos_sin_consenso=conflicts,
    )
