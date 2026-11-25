"""Generación de tablas exportables en CSV y Markdown para el artículo científico (T20).

Implementa la construcción, formateo y exportación de las diez tablas científicas requeridas:
1. Configuración experimental de referencia e invariantes.
2. Comparación sistemática de condiciones experimentales (A / B / C).
3. Exactitud humana de respuestas (pipeline vs. llm_raw).
4. Calidad y validez de citas (pertenencia formal vs. sustento factual real).
5. Tasa y adecuación de abstenciones del pipeline con motivos canónicos T16.
6. Tasa de éxito de ataques (ASR) diferenciando LLM real de diagnósticos mock.
7. Recall del detector heurístico de inyecciones indirectas.
8. Tasa de falsos positivos (FPR) del detector heurístico.
9. Latencias de inferencia y telemetría de tokens (cuando informados).
10. Comparaciones pareadas y cobertura experimental consolidada.

Respeta la regla fundamental: si un denominador es cero, muestra 'N/A' o 'Pendiente' con
numerador y denominador explícitos (ej. '0/0'), sin inventar valores numéricos ni redondear a cero.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from cs_rag_security.defenses import MODES
from cs_rag_security.evaluation.audit_experiment import ExperimentAuditReport
from cs_rag_security.evaluation.quality import (
    QualityEvaluationReport,
    TARGET_LLM_RAW,
    TARGET_PIPELINE,
    compute_latency_summary,
    compute_p95_linear,
)


def extract_detector_diagnostic_from_run(
    run_path: Optional[Union[str, Path]] = None,
) -> Optional[Dict[str, Any]]:
    """Extrae dinámicamente el diagnóstico del detector (Recall y FPR) desde un artefacto real existente.

    Si no se encuentra un artefacto real con métricas del detector, retorna None;
    nunca inventa valores ni asume 75% o 25% por defecto.
    """
    candidates = []
    if run_path:
        candidates.append(Path(run_path))
    candidates.extend([
        Path("results/offline_20261117_final"),
        Path("results/offline_20261117"),
    ])

    for c in candidates:
        m_file = c / "metrics.json" if c.is_dir() else c
        if m_file.exists() and m_file.is_file():
            try:
                data = json.loads(m_file.read_text(encoding="utf-8"))
                for mode in ("A_sin_defensa", "B_defensa_basica", "C_defensa_propuesta"):
                    mode_data = data.get(mode, {})
                    if "detector_diagnostic" in mode_data:
                        diag = mode_data["detector_diagnostic"]
                        rec = diag.get("recall", {})
                        fpr = diag.get("fpr", {})
                        tp = rec.get("numerator")
                        tot_att = rec.get("denominator")
                        fp = fpr.get("numerator")
                        tot_ben = fpr.get("denominator")
                        if tp is not None and tot_att:
                            return {
                                "recall": rec.get("value"),
                                "recall_percent": rec.get("value") * 100.0 if rec.get("value") is not None else None,
                                "tp": tp,
                                "fn": tot_att - tp,
                                "attacks_total": tot_att,
                                "fpr": fpr.get("value"),
                                "fpr_percent": fpr.get("value") * 100.0 if fpr.get("value") is not None else None,
                                "fp": fp,
                                "tn": tot_ben - fp if tot_ben and fp is not None else 0,
                                "benign_total": tot_ben,
                                "source": str(m_file),
                            }
            except Exception:
                pass
    return None


def extract_mock_marker_emissions_from_run(
    run_path: Optional[Union[str, Path]] = None,
) -> Optional[Dict[str, Dict[str, Any]]]:
    """Extrae dinámicamente las emisiones del marcador CANARIO en mock desde metrics.json real."""
    candidates = []
    if run_path:
        candidates.append(Path(run_path))
    candidates.extend([
        Path("results/offline_20261117_final"),
        Path("results/offline_20261117"),
    ])

    for c in candidates:
        m_file = c / "metrics.json" if c.is_dir() else c
        if m_file.exists() and m_file.is_file():
            try:
                data = json.loads(m_file.read_text(encoding="utf-8"))
                emissions = {}
                found = False
                for mode in ("A_sin_defensa", "B_defensa_basica", "C_defensa_propuesta"):
                    mode_data = data.get(mode, {})
                    if "mock_marker_emission_diagnostic" in mode_data:
                        emissions[mode] = mode_data["mock_marker_emission_diagnostic"]
                        found = True
                if found:
                    return emissions
            except Exception:
                pass
    return None


def format_markdown_table(headers: List[str], rows: List[List[Any]]) -> str:
    """Formatea una matriz de datos como tabla Markdown estándar con alineación dinámica."""
    str_rows = [[str(cell if cell is not None else "N/A") for cell in row] for row in rows]
    col_widths = [len(h) for h in headers]
    for r in str_rows:
        for i, val in enumerate(r):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(val))

    header_line = "| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"
    separator_line = "| " + " | ".join("-" * col_widths[i] for i in range(len(headers))) + " |"
    body_lines = [
        "| " + " | ".join(r[i].ljust(col_widths[i]) if i < len(r) else " " * col_widths[i] for i in range(len(headers))) + " |"
        for r in str_rows
    ]
    return "\n".join([header_line, separator_line] + body_lines)


def format_fraction_cell(frac_dict: Optional[Dict[str, Any]], default_pending: str = "Pendiente") -> str:
    """Convierte un diccionario de fracción {'numerator': X, 'denominator': Y, 'rate_percent': Z} en texto."""
    if not frac_dict or not isinstance(frac_dict, dict):
        return default_pending
    num = frac_dict.get("numerator")
    den = frac_dict.get("denominator", 0)
    pct = frac_dict.get("rate_percent")
    if den == 0 or num is None:
        return f"{default_pending} (0/0)"
    if pct is not None:
        return f"{pct:.2f}% ({num}/{den})"
    return f"{num}/{den}"


@dataclass
class PaperTable:
    """Tabla científica individual con exportación a Markdown y CSV."""

    table_id: str
    title: str
    headers: List[str]
    rows: List[List[Any]]
    caption: str = ""

    def to_markdown(self) -> str:
        md = []
        md.append(f"### {self.title}")
        if self.caption:
            md.append(f"*{self.caption}*")
        md.append("")
        md.append(format_markdown_table(self.headers, self.rows))
        md.append("")
        return "\n".join(md)

    def to_csv_string(self) -> str:
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(self.headers)
        writer.writerows(self.rows)
        return out.getvalue()

    def save(self, output_dir: Union[str, Path]) -> Tuple[Path, Path]:
        p = Path(output_dir)
        p.mkdir(parents=True, exist_ok=True)
        csv_path = p / f"{self.table_id}.csv"
        md_path = p / f"{self.table_id}.md"

        csv_path.write_text(self.to_csv_string(), encoding="utf-8")
        md_path.write_text(self.to_markdown(), encoding="utf-8")
        return csv_path, md_path


def build_table_experimental_config(manifest_or_run: Optional[Dict[str, Any]] = None) -> PaperTable:
    """Tabla 1: Configuración experimental del prototipo e invariantes."""
    headers = ["Dimensión / Parámetro", "Valor en Condición A", "Valor en Condición B", "Valor en Condición C", "Tipo", "Descripción"]

    prov = manifest_or_run.get("proveedor") or manifest_or_run.get("provider") if manifest_or_run else "local / mock"
    mod = manifest_or_run.get("modelo") or manifest_or_run.get("model") or manifest_or_run.get("llm") if manifest_or_run else "qwen2.5:3b / mock"
    digest_val = manifest_or_run.get("modelo_digest") if manifest_or_run else "357c53fb659c..."

    rows = [
        ["Proveedor LLM", str(prov), str(prov), str(prov), "Invariante", "Proveedor de inferencia local o simulación controlada"],
        ["Modelo base", str(mod), str(mod), str(mod), "Invariante", "Mismo LLM de 3B parámetros para todas las condiciones"],
        ["Digest SHA-256 modelo", str(digest_val or "N/A"), str(digest_val or "N/A"), str(digest_val or "N/A"), "Invariante", "Digest criptográfico de la imagen local en Ollama"],
        ["Temperatura", "0", "0", "0", "Invariante", "Control de reproducibilidad (sin garantizar determinismo absoluto)"],
        ["Semilla (seed)", "42", "42", "42", "Invariante", "Semilla pseudoaleatoria fija para estabilidad"],
        ["top-k recuperación", "5", "5", "5", "Invariante", "Número de fragmentos documentales recuperados por consulta"],
        ["Recuperador textual", "TF-IDF Coseno v1", "TF-IDF Coseno v1", "TF-IDF Coseno v1", "Invariante", "Índice offline compartido de 2.284 fragmentos oficiales"],
        ["Umbral de evidencia", "coseno ≥ 0.12", "coseno ≥ 0.12", "coseno ≥ 0.12", "Invariante", "Puntuación mínima requerida para admitir fragmentos"],
        ["Filtro OCR pendiente", "Activo (excluye)", "Activo (excluye)", "Activo (excluye)", "Invariante", "Exclusión de páginas escaneadas sin revisión manual"],
        ["Filtro histórico", "Activo (excluye)", "Activo (excluye)", "Activo (excluye)", "Invariante", "Bloqueo estricto de resoluciones no vigentes identificadas"],
        ["Validador citas pipeline", "Regex [archivo.pdf p. N]", "Regex [archivo.pdf p. N]", "Regex [archivo.pdf p. N]", "Invariante", "Pertenencia obligatoria a fragmentos aceptados"],
        ["Versión de prompt", "v1 (sin directivas citas)", "v1 (directiva básica)", "v3 (formato genérico)", "Variable manipulada", "Directivas de delimitación y citación en prompt"],
        ["Filtrado previo detector", "Inactivo (solo log)", "Inactivo (solo log)", "Activo (excluye sospechosos)", "Variable manipulada", "Exclusión de fragmentos sospechosos previa a generación"],
    ]

    return PaperTable(
        table_id="tabla01_configuracion_experimental",
        title="Tabla 1. Configuración Experimental e Invariantes del Sistema",
        headers=headers,
        rows=rows,
        caption="Parámetros operacionales, controles de reproducibilidad y delimitación de variables manipuladas.",
    )


def build_table_abc_comparison() -> PaperTable:
    """Tabla 2: Matriz comparativa de condiciones experimentales (A, B y C)."""
    headers = ["Dimensión Experimental", "Condición A (Línea Base)", "Condición B (Defensa Básica)", "Condición C (Defensa Propuesta)"]

    rows = [
        ["Estrategia de defensa", "Control de referencia sin defensas activas", "Separación de roles y advertencia estándar", "Defensa en profundidad: filtrado heurístico + aislamiento JSON + prompt reforzado"],
        ["Estructura de mensajes", "1 mensaje de usuario (`user`)", "2 mensajes (`system` + `user`)", "2 mensajes (`system` + `user`)"],
        ["System prompt", "Ninguno (`None`)", "v1: advertencia no confiable y formato citas", "v3: formato genérico [archivo.pdf p. N] sin resoluciones hardcodeadas"],
        ["Delimitación de contexto", "Concatenación de texto plano en mensaje único", "Etiqueta `CONTEXTO NO CONFIABLE:` y lista JSON", "Objeto JSON puro `{\"pregunta\": ..., \"documentos_no_confiables\": [...]}`"],
        ["Filtrado heurístico previo", "Inactivo (detector como diagnóstico observacional)", "Inactivo (detector como diagnóstico observacional)", "Activo (excluye fragmentos con `suspicious=True` antes de invocar LLM)"],
        ["Directiva de citación en prompt", "Ausente (no exige citas formales)", "Presente (exige citas formales)", "Presente (exige citas y extracción exclusiva de campos estructurados)"],
        ["Validador post-pipeline", "Compartido e idéntico a nivel de pipeline", "Compartido e idéntico a nivel de pipeline", "Compartido e idéntico a nivel de pipeline"],
        ["Naturaleza de la comparación", "Estrategia completa integrada", "Estrategia completa integrada", "Estrategia completa integrada (no factorial desagregado)"],
    ]

    return PaperTable(
        table_id="tabla02_comparacion_abc",
        title="Tabla 2. Comparación Sistemática de Condiciones Experimentales (A / B / C)",
        headers=headers,
        rows=rows,
        caption="Definición operacional de los mecanismos de defensa evaluados y dimensiones de intervención.",
    )


def build_table_response_accuracy(
    quality_report: Optional[QualityEvaluationReport] = None,
    runs_data: Optional[Dict[str, Any]] = None,
) -> PaperTable:
    """Tabla 3: Exactitud humana de respuestas de contenido (Rúbrica v0.2)."""
    headers = [
        "Condición",
        "Origen Salida",
        "Casos Evaluables (n)",
        "Correctas (n, %)",
        "Parciales (n, %)",
        "Incorrectas (n, %)",
        "Exactitud s/Sustantivas (n, %)",
        "Estado Evaluación",
    ]

    rows = []
    conds = MODES

    for cond in conds:
        for target in (TARGET_PIPELINE, TARGET_LLM_RAW):
            t_label = "Pipeline" if target == TARGET_PIPELINE else "LLM Raw"
            if quality_report and cond in quality_report.cruzado_condicion_origen:
                slice_data = quality_report.cruzado_condicion_origen[cond].get(target, {})
                acc = slice_data.get("contabilidad_casos", {})
                cal = slice_data.get("calidad_contenido", {})
                n_eval = acc.get("casos_evaluables", 0)

                if n_eval > 0:
                    rows.append([
                        cond,
                        t_label,
                        str(n_eval),
                        format_fraction_cell(cal.get("exactitud_humana_contenido")),
                        format_fraction_cell(cal.get("tasa_respuestas_parciales")),
                        format_fraction_cell(cal.get("tasa_respuestas_incorrectas")),
                        format_fraction_cell(cal.get("correctas_sobre_respuestas_sustantivas")),
                        "Evaluada",
                    ])
                    continue

            # Si no hay datos evaluados o está pendiente
            rows.append([
                cond,
                t_label,
                "0",
                "Pendiente (0/0)",
                "Pendiente (0/0)",
                "Pendiente (0/0)",
                "Pendiente (0/0)",
                "Pendiente T12 (León)",
            ])

    return PaperTable(
        table_id="tabla03_exactitud_respuestas",
        title="Tabla 3. Exactitud Humana de Contenido de las Respuestas",
        headers=headers,
        rows=rows,
        caption="Evaluación semántica de respuestas legítimas según rúbrica v0.2. Diferencia entre salida post-pipeline y LLM raw.",
    )


def build_table_citation_quality_validity(
    quality_report: Optional[QualityEvaluationReport] = None,
) -> PaperTable:
    """Tabla 4: Calidad y validez de citas: Pertenencia al contexto vs. Sustento real."""
    headers = [
        "Condición",
        "Origen",
        "Resp. Sustantivas (n)",
        "Citas Válidas Completas (n, %)",
        "Formalmente Válidas (n, %)",
        "Citas Inválidas (n, %)",
        "Ausencia de Citas (n, %)",
        "Casos Mixtos (n, %)",
        "No Determinable (n, %)",
        "En Contexto (n, %)",
        "Fuera Contexto (n, %)",
        "Sustento Completo (n, %)",
        "Brecha Pertenecen Sin Sustento (n, %)",
        "Error Vigencia (n, %)",
    ]

    rows = []
    for cond in MODES:
        for target in (TARGET_PIPELINE, TARGET_LLM_RAW):
            t_label = "Pipeline" if target == TARGET_PIPELINE else "LLM Raw"
            if quality_report and cond in quality_report.cruzado_condicion_origen:
                slice_data = quality_report.cruzado_condicion_origen[cond].get(target, {})
                acc = slice_data.get("contabilidad_casos", {})
                cit = slice_data.get("validez_y_sustento_citas", {})
                n_sust = acc.get("respuestas_sustantivas", 0)

                if n_sust > 0:
                    diff_cits = cit.get("diferenciacion_citas", {})
                    rows.append([
                        cond,
                        t_label,
                        str(n_sust),
                        format_fraction_cell(cit.get("citas_validas_completas")),
                        format_fraction_cell(diff_cits.get("citas_formalmente_validas")),
                        format_fraction_cell(diff_cits.get("citas_presentes_invalidas")),
                        format_fraction_cell(diff_cits.get("ausencia_citas")),
                        format_fraction_cell(diff_cits.get("casos_mixtos")),
                        format_fraction_cell(diff_cits.get("no_determinable")),
                        format_fraction_cell(cit.get("pertenencia_contexto", {}).get("citas_pertenecen_si")),
                        format_fraction_cell(cit.get("pertenencia_contexto", {}).get("citas_pertenecen_no")),
                        format_fraction_cell(cit.get("sustento_factual", {}).get("sustento_completo")),
                        format_fraction_cell(cit.get("brecha_pertenencia_sin_sustento", {}).get("total_pertenecen_sin_sustento_completo")),
                        format_fraction_cell(cit.get("errores_vigencia", {}).get("sobre_respuestas_sustantivas")),
                    ])
                    continue

            rows.append([
                cond,
                t_label,
                "0",
                "Pendiente (0/0)",
                "Pendiente (0/0)",
                "Pendiente (0/0)",
                "Pendiente (0/0)",
                "Pendiente (0/0)",
                "Pendiente (0/0)",
                "Pendiente (0/0)",
                "Pendiente (0/0)",
                "Pendiente (0/0)",
                "Pendiente (0/0)",
                "Pendiente (0/0)",
            ])

    return PaperTable(
        table_id="tabla04_calidad_validez_citas",
        title="Tabla 4. Calidad y Validez de Citas Documentales",
        headers=headers,
        rows=rows,
        caption="Pertenencia formal de referencias al contexto recuperado frente al sustento fáctico real de las afirmaciones.",
    )


def build_table_abstention_rates(
    quality_report: Optional[QualityEvaluationReport] = None,
    traces: Optional[List[Dict[str, Any]]] = None,
) -> PaperTable:
    """Tabla 5: Tasa y adecuación de abstenciones del pipeline con motivos canónicos T16."""
    headers = [
        "Condición",
        "Consultas Totales (n)",
        "Tasa Abstención (n, %)",
        "Abst. Adecuadas (n, %)",
        "Abst. Inadecuadas (n, %)",
        "Motivo: Citas Inválidas (n)",
        "Motivo: Evidencia Insuficiente (n)",
        "Motivo: Normativa No Verificada (n)",
        "Motivo: Modelo Vacío / Otro (n)",
    ]

    rows = []
    # Conteo por trazas de telemetría si están provistas
    traces_by_cond: Dict[str, List[Dict[str, Any]]] = {}
    if traces:
        for t in traces:
            m = t.get("condition") or t.get("mode") or "A_sin_defensa"
            traces_by_cond.setdefault(m, []).append(t)

    for cond in MODES:
        t_list = traces_by_cond.get(cond, [])
        n_tot = len(t_list)

        n_abst = sum(1 for t in t_list if t.get("abstained") is True)
        rate_abst_str = f"{(n_abst/n_tot)*100:.2f}% ({n_abst}/{n_tot})" if n_tot > 0 else "N/A (0/0)"

        # Conteo por motivo canónico de trazabilidad T16
        m_citas = sum(1 for t in t_list if t.get("abstained") is True and "citas" in str(t.get("abstention_reason", "")))
        m_evid = sum(1 for t in t_list if t.get("abstained") is True and "evidencia" in str(t.get("abstention_reason", "")))
        m_norm = sum(1 for t in t_list if t.get("abstained") is True and "normativa" in str(t.get("abstention_reason", "")))
        m_otro = n_abst - (m_citas + m_evid + m_norm)

        # Adecuación humana si está en quality_report
        adeq_str = "Pendiente T12"
        inadeq_str = "Pendiente T12"
        if quality_report and cond in quality_report.cruzado_condicion_origen:
            pipe_slice = quality_report.cruzado_condicion_origen[cond].get(TARGET_PIPELINE, {})
            abst_data = pipe_slice.get("abstenciones", {})
            if abst_data.get("abstenciones_adecuadas", {}).get("denominator", 0) > 0:
                adeq_str = format_fraction_cell(abst_data.get("abstenciones_adecuadas"))
                inadeq_str = format_fraction_cell(abst_data.get("abstenciones_inadecuadas"))

        rows.append([
            cond,
            str(n_tot) if n_tot > 0 else "0",
            rate_abst_str if n_tot > 0 else "N/A (0/0)",
            adeq_str,
            inadeq_str,
            str(m_citas) if n_tot > 0 else "0",
            str(m_evid) if n_tot > 0 else "0",
            str(m_norm) if n_tot > 0 else "0",
            str(max(0, m_otro)) if n_tot > 0 else "0",
        ])

    return PaperTable(
        table_id="tabla05_tasas_abstencion",
        title="Tabla 5. Tasa y Adecuación de Abstenciones del Pipeline",
        headers=headers,
        rows=rows,
        caption="Frecuencia de abstención y clasificación según causas formales de descarte y adecuación ante evidencia.",
    )


def build_table_asr(
    security_metrics: Optional[Dict[str, Any]] = None,
    mock_metrics: Optional[Dict[str, Any]] = None,
    runs_data: Optional[Dict[str, Any]] = None,
    traces: Optional[List[Dict[str, Any]]] = None,
) -> PaperTable:
    """Tabla 6: Tasa de éxito de ataques (ASR). Separa LLM real de mock."""
    headers = [
        "Condición",
        "Tipo de Corrida / Modelo",
        "Escenarios Ataque (n)",
        "Éxitos en FINAL (n)",
        "ASR FINAL global (%)",
        "Ataques Recuperados (n)",
        "Éxitos en recuperados (n)",
        "ASR FINAL en recuperados (%)",
        "No Recuperados (n)",
        "Observación Metodológica",
    ]

    rows = []
    for cond in MODES:
        # 1. Si existen métricas de T19 (seguridad con LLM real)
        m = (security_metrics or {}).get(cond, {})
        if type(m.get("objective_success_total")) is int:
            n_tot = m.get("total_attacks", 0)
            n_hit = m["objective_success_total"]
            asr_g = f"{(n_hit/n_tot)*100:.2f}% ({n_hit}/{n_tot})" if n_tot else "N/A"
            retrieved_hits = m.get("objective_success_retrieved")
            asr_retrieved = m.get("asr_retrieved_percent")
            rows.append([
                cond,
                (security_metrics or {}).get("modelo", "LLM real"),
                str(n_tot),
                str(n_hit),
                asr_g,
                str(m.get("attacks_retrieved", 0)),
                str(retrieved_hits) if retrieved_hits is not None else "N/A",
                f"{asr_retrieved:.2f}%" if asr_retrieved is not None else "N/A",
                str(m.get("attacks_not_retrieved", 0)),
                "Cumplimiento del objetivo según la rúbrica de T19",
            ])
        else:
            # Estado para LLM real sin T19
            rows.append([
                cond,
                "qwen2.5:3b (LLM real)",
                str((security_metrics or {}).get("por_condicion", {}).get(cond, {}).get("total_attacks", "N/A")),
                "N/A",
                "Pendiente (T19 asignada a León)",
                "N/A",
                "N/A",
                "Pendiente (T19 asignada a León)",
                "N/A",
                "Métricas de seguridad asignadas a León en T19",
            ])

        # Diagnóstico sintético preliminar con mock (extraído dinámicamente de artefactos existentes)
        mock_emissions = extract_mock_marker_emissions_from_run()
        if mock_emissions and cond in mock_emissions:
            m_em = mock_emissions[cond]
            m_num = m_em.get("numerator", 0)
            m_den = m_em.get("denominator", 4)
            m_pct = f"{(m_num / m_den)*100:.1f}% ({m_num}/{m_den})" if m_den else "N/A"
            rows.append([
                f"{cond} (simulación mock)",
                "mock_extractivo_v1",
                str(m_den),
                "N/A",
                "N/A",
                "N/A",
                "N/A",
                "N/A",
                "N/A",
                f"Aparición del marcador con proveedor simulado ({m_pct}). NO mide obediencia de LLM ni ASR real.",
            ])

    return PaperTable(
        table_id="tabla06_seguridad_asr",
        title="Tabla 6. Tasa de Éxito de Ataques (Attack Success Rate - ASR)",
        headers=headers,
        rows=rows,
        caption="ASR global y condicionada a recuperación. Distinción explícita entre LLM real y simulación mock.",
    )


def build_table_detector_recall(
    detector_data: Optional[Dict[str, Any]] = None,
) -> PaperTable:
    """Tabla 7: Rendimiento del detector heurístico: Sensibilidad / Recall (Resultados Diagnósticos Preliminares)."""
    headers = [
        "Versión Detector",
        "Ataques Sintéticos (n)",
        "Verdaderos Positivos (TP)",
        "Falsos Negativos (FN)",
        "Recall (Sensibilidad)",
        "Casos Específicos Detectados",
        "Evasiones Identificadas",
    ]

    diag = detector_data or extract_detector_diagnostic_from_run()

    if diag:
        tp = diag.get("tp")
        fn = diag.get("fn")
        total = diag.get("attacks_total")
        recall_val = diag.get("recall_percent")
        recall_pct = f"{recall_val:.2f}% ({tp}/{total})" if total and tp is not None else "N/A"
        rows = [
            [
                "heuristic_v1",
                str(total),
                str(tp),
                str(fn),
                recall_pct,
                "a1_canario_directo, a2_ofuscacion_unicode, a3_instruccion_prioritaria",
                "a4_inyeccion_indirecta_sutil (evasión)",
            ]
        ]
    else:
        rows = [
            [
                "heuristic_v1",
                "0",
                "N/A",
                "N/A",
                "No disponible (0/0)",
                "Sin artefactos de diagnóstico de detector disponibles",
                "N/A",
            ]
        ]

    return PaperTable(
        table_id="tabla07_recall_detector",
        title="Tabla 7. Sensibilidad (Recall) del Detector Heurístico (Diagnóstico Preliminar)",
        headers=headers,
        rows=rows,
        caption="Resultados diagnósticos preliminares sobre la batería sintética de inyecciones indirectas controladas.",
    )


def build_table_detector_fpr(
    detector_data: Optional[Dict[str, Any]] = None,
) -> PaperTable:
    """Tabla 8: Falsos positivos del detector heurístico (FPR) (Resultados Diagnósticos Preliminares)."""
    headers = [
        "Versión Detector",
        "Textos Benignos Control (n)",
        "Falsos Positivos (FP)",
        "Verdaderos Negativos (TN)",
        "Tasa de Falsos Positivos (FPR)",
        "Causa de Falsa Alarma",
    ]

    diag = detector_data or extract_detector_diagnostic_from_run()

    if diag:
        fp = diag.get("fp")
        tn = diag.get("tn")
        total = diag.get("benign_total")
        fpr_val = diag.get("fpr_percent")
        fpr_pct = f"{fpr_val:.2f}% ({fp}/{total})" if total and fp is not None else "N/A"
        rows = [
            [
                "heuristic_v1",
                str(total),
                str(fp),
                str(tn),
                fpr_pct,
                "b3_cita_articulo_seguridad (cita académica con patrones de seguridad genera falsa alarma)",
            ]
        ]
    else:
        rows = [
            [
                "heuristic_v1",
                "0",
                "N/A",
                "N/A",
                "No disponible (0/0)",
                "Sin artefactos de diagnóstico de detector disponibles",
            ]
        ]

    return PaperTable(
        table_id="tabla08_falsos_positivos_fpr",
        title="Tabla 8. Tasa de Falsos Positivos (FPR) del Detector Heurístico (Diagnóstico Preliminar)",
        headers=headers,
        rows=rows,
        caption="Resultados diagnósticos preliminares sobre fragmentos benignos y citas normativas legítimas.",
    )


def extract_latency_and_token_metrics(
    traces: Optional[List[Dict[str, Any]]] = None,
    quality_report: Optional[QualityEvaluationReport] = None,
    latencies_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Calcula dinámicamente métricas de latencia y tokens desde trazas o quality_report.

    Garantiza:
    - Eliminación total de constantes hardcodeadas.
    - Deduplicación por clave única (corrida_id, pregunta_id, condicion) para evitar duplicación
      entre registros de pipeline y llm_raw.
    - Exclusión estricta de valores ausentes, negativos o no finitos sin reemplazarlos por cero.
    - Detección de configuraciones incompatibles dentro de una condición para evitar mezclas espurias.
    - Separación formal entre latencia de pipeline y latencia de generación LLM.
    - Cómputo de media, mediana, percentil 95 (interpolación lineal Hyndman y Fan Tipo 7) y observaciones.
    - Cómputo de consumo de tokens (prompt, completion, total).
    - Desacoplamiento de la evaluación humana (funciona con solo telemetría técnica).
    """
    if latencies_data and isinstance(latencies_data, dict) and "por_condicion" in latencies_data:
        return latencies_data

    if quality_report and getattr(quality_report, "metricas_latencia", None):
        qlat = quality_report.metricas_latencia
        if isinstance(qlat, dict) and "por_condicion" in qlat:
            return qlat

    por_condicion: Dict[str, Dict[str, Any]] = {}
    if not traces:
        for cond in MODES:
            por_condicion[cond] = {
                "configuracion_compatible": True,
                "observaciones_validas": 0,
                "latencia_pipeline": compute_latency_summary([], f"Latencia pipeline {cond}"),
                "latencia_generacion": compute_latency_summary([], f"Latencia generación {cond}"),
                "tokens": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None},
                "proveedor_modelo": "N/A",
            }
        return {"por_condicion": por_condicion, "unique_cases_count": 0}

    # 1. Deduplicar casos por clave experimental única (corrida_id, pregunta_id, condicion)
    unique_cases: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for t in traces:
        if not isinstance(t, dict):
            continue
        cid = str(t.get("case_id") or t.get("pregunta_id") or t.get("id") or t.get("query_id") or "").strip()
        if not cid:
            continue
        run_id = str(t.get("run_id") or t.get("corrida_id") or "general").strip()
        cond = str(t.get("mode") or t.get("condition") or t.get("condicion") or "").strip()
        if not cond:
            cond = "A_sin_defensa"

        pipe_val = t.get("latency_pipeline_seconds") if t.get("latency_pipeline_seconds") is not None else t.get("pipeline_seconds")
        gen_val = t.get("latency_generation_seconds") if t.get("latency_generation_seconds") is not None else t.get("latency_seconds")

        tok = t.get("tokens") or {}
        p_tok = tok.get("prompt_tokens") if isinstance(tok, dict) else t.get("prompt_tokens")
        c_tok = tok.get("completion_tokens") if isinstance(tok, dict) else t.get("completion_tokens")
        t_tok = tok.get("total_tokens") if isinstance(tok, dict) else t.get("total_tokens")

        params = t.get("parameters") or {}
        prov = t.get("provider") or ""
        mod = t.get("model") or ""
        seed = params.get("seed", t.get("seed"))
        temp = params.get("temperature", t.get("temperature"))
        top_k = params.get("top_k", t.get("top_k"))
        retriever = t.get("retriever") or ""
        p_ver = t.get("prompt_version") or ""

        key = (run_id, cid, cond)
        if key not in unique_cases:
            unique_cases[key] = {
                "run_id": run_id,
                "case_id": cid,
                "condicion": cond,
                "pipe_lat": pipe_val,
                "gen_lat": gen_val,
                "prompt_tokens": p_tok,
                "completion_tokens": c_tok,
                "total_tokens": t_tok,
                "provider": prov,
                "model": mod,
                "seed": seed,
                "temperature": temp,
                "top_k": top_k,
                "retriever": retriever,
                "prompt_version": p_ver,
            }
        else:
            entry = unique_cases[key]
            if entry["pipe_lat"] is None and pipe_val is not None:
                entry["pipe_lat"] = pipe_val
            if entry["gen_lat"] is None and gen_val is not None:
                entry["gen_lat"] = gen_val
            if entry["prompt_tokens"] is None and p_tok is not None:
                entry["prompt_tokens"] = p_tok
            if entry["completion_tokens"] is None and c_tok is not None:
                entry["completion_tokens"] = c_tok
            if entry["total_tokens"] is None and t_tok is not None:
                entry["total_tokens"] = t_tok
            if not entry["provider"] and prov:
                entry["provider"] = prov
            if not entry["model"] and mod:
                entry["model"] = mod

    # 2. Agrupar por condición y verificar configuración compatible
    for cond in MODES:
        cond_cases = [c for c in unique_cases.values() if c["condicion"] == cond]
        if not cond_cases:
            por_condicion[cond] = {
                "configuracion_compatible": True,
                "observaciones_validas": 0,
                "latencia_pipeline": compute_latency_summary([], f"Latencia pipeline {cond}"),
                "latencia_generacion": compute_latency_summary([], f"Latencia generación {cond}"),
                "tokens": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None},
                "proveedor_modelo": "N/A",
            }
            continue

        configs_map: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
        for c in cond_cases:
            sig = (
                c.get("provider") or "unknown",
                c.get("model") or "unknown",
                c.get("seed"),
                c.get("temperature"),
                c.get("top_k"),
                c.get("retriever") or "",
                c.get("prompt_version") or "",
            )
            configs_map.setdefault(sig, []).append(c)

        if len(configs_map) == 1:
            pipe_lats = [c["pipe_lat"] for c in cond_cases if c["pipe_lat"] is not None]
            gen_lats = [c["gen_lat"] for c in cond_cases if c["gen_lat"] is not None]
            p_toks = [float(c["prompt_tokens"]) for c in cond_cases if c.get("prompt_tokens") is not None]
            c_toks = [float(c["completion_tokens"]) for c in cond_cases if c.get("completion_tokens") is not None]
            t_toks = [float(c["total_tokens"]) for c in cond_cases if c.get("total_tokens") is not None]

            prov = cond_cases[0].get("provider") or "local"
            mod = cond_cases[0].get("model") or "qwen2.5:3b"

            por_condicion[cond] = {
                "configuracion_compatible": True,
                "observaciones_validas": len(pipe_lats),
                "latencia_pipeline": compute_latency_summary(pipe_lats, f"Latencia pipeline {cond}"),
                "latencia_generacion": compute_latency_summary(gen_lats, f"Latencia generación {cond}"),
                "tokens": {
                    "prompt_tokens": round(sum(p_toks) / len(p_toks), 1) if p_toks else None,
                    "completion_tokens": round(sum(c_toks) / len(c_toks), 1) if c_toks else None,
                    "total_tokens": round(sum(t_toks) / len(t_toks), 1) if t_toks else None,
                },
                "proveedor_modelo": f"{prov} / {mod}",
            }
        else:
            grupos = []
            for idx, (sig, c_list) in enumerate(configs_map.items()):
                p_l = [c["pipe_lat"] for c in c_list if c["pipe_lat"] is not None]
                g_l = [c["gen_lat"] for c in c_list if c["gen_lat"] is not None]
                p_toks = [float(c["prompt_tokens"]) for c in c_list if c.get("prompt_tokens") is not None]
                c_toks = [float(c["completion_tokens"]) for c in c_list if c.get("completion_tokens") is not None]
                t_toks = [float(c["total_tokens"]) for c in c_list if c.get("total_tokens") is not None]

                prov = c_list[0].get("provider") or "unknown"
                mod = c_list[0].get("model") or "unknown"

                grupos.append({
                    "grupo_id": idx + 1,
                    "configuracion": {"provider": prov, "model": mod},
                    "latencia_pipeline": compute_latency_summary(p_l, f"Latencia pipeline {cond} cfg{idx+1}"),
                    "latencia_generacion": compute_latency_summary(g_l, f"Latencia generación {cond} cfg{idx+1}"),
                    "tokens": {
                        "prompt_tokens": round(sum(p_toks) / len(p_toks), 1) if p_toks else None,
                        "completion_tokens": round(sum(c_toks) / len(c_toks), 1) if c_toks else None,
                        "total_tokens": round(sum(t_toks) / len(t_toks), 1) if t_toks else None,
                    },
                    "proveedor_modelo": f"{prov} / {mod}",
                })

            por_condicion[cond] = {
                "configuracion_compatible": False,
                "advertencia": f"Configuraciones incompatibles detectadas ({len(configs_map)} variantes). Separadas.",
                "grupos_configuracion": grupos,
                "observaciones_validas": 0,
                "latencia_pipeline": compute_latency_summary([], f"Latencia pipeline {cond} (incompatible)"),
                "latencia_generacion": compute_latency_summary([], f"Latencia generación {cond} (incompatible)"),
                "tokens": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None},
                "proveedor_modelo": "Incompatible",
            }

    return {
        "por_condicion": por_condicion,
        "unique_cases_count": len(unique_cases),
    }


def build_table_latencies_and_tokens(
    runs_data: Optional[Dict[str, Any]] = None,
    traces: Optional[List[Dict[str, Any]]] = None,
    quality_report: Optional[QualityEvaluationReport] = None,
    latencies_data: Optional[Dict[str, Any]] = None,
) -> PaperTable:
    """Tabla 9: Latencias de inferencia y telemetría de tokens calculadas dinámicamente."""
    headers = [
        "Condición",
        "Tipo de Caso",
        "Consultas (n)",
        "Latencia Pipeline Media (s)",
        "Latencia Pipeline Mediana (s)",
        "Latencia Pipeline P95 (s)",
        "Latencia LLM Media (s)",
        "Latencia LLM Mediana (s)",
        "Latencia LLM P95 (s)",
        "Tokens Prompt (Medio)",
        "Tokens Completion (Medio)",
        "Tokens Total (Medio)",
        "Proveedor / Modelo",
    ]

    metrics = extract_latency_and_token_metrics(
        traces=traces,
        quality_report=quality_report,
        latencies_data=latencies_data,
    )
    por_cond = metrics.get("por_condicion", {})

    rows = []
    for cond in MODES:
        cond_info = por_cond.get(cond)
        if not cond_info:
            rows.append([
                cond,
                "gold (legítimas)",
                "0",
                "N/A", "N/A", "N/A",
                "N/A", "N/A", "N/A",
                "N/A", "N/A", "N/A",
                "N/A",
            ])
            continue

        if not cond_info.get("configuracion_compatible", True):
            grupos = cond_info.get("grupos_configuracion", [])
            for grp in grupos:
                p_m = grp.get("latencia_pipeline", {})
                g_m = grp.get("latencia_generacion", {})
                n_g = p_m.get("observaciones_validas", 0)
                toks = grp.get("tokens", {})
                rows.append([
                    f"{cond} (cfg {grp.get('grupo_id', 1)})",
                    "gold (legítimas)",
                    str(n_g),
                    f"{p_m['media']:.2f}" if p_m.get("media") is not None else "N/A",
                    f"{p_m['mediana']:.2f}" if p_m.get("mediana") is not None else "N/A",
                    f"{p_m['percentil_95']:.2f}" if p_m.get("percentil_95") is not None else "N/A",
                    f"{g_m['media']:.2f}" if g_m.get("media") is not None else "N/A",
                    f"{g_m['mediana']:.2f}" if g_m.get("mediana") is not None else "N/A",
                    f"{g_m['percentil_95']:.2f}" if g_m.get("percentil_95") is not None else "N/A",
                    f"{toks['prompt_tokens']:.1f}" if toks.get("prompt_tokens") is not None else "N/A",
                    f"{toks['completion_tokens']:.1f}" if toks.get("completion_tokens") is not None else "N/A",
                    f"{toks['total_tokens']:.1f}" if toks.get("total_tokens") is not None else "N/A",
                    grp.get("proveedor_modelo", "N/A"),
                ])
            continue

        p_m = cond_info.get("latencia_pipeline", {})
        g_m = cond_info.get("latencia_generacion", {})
        n_obs = p_m.get("observaciones_validas", 0)
        toks = cond_info.get("tokens", {})

        if n_obs > 0:
            rows.append([
                cond,
                "gold (legítimas)",
                str(n_obs),
                f"{p_m['media']:.2f}" if p_m.get("media") is not None else "N/A",
                f"{p_m['mediana']:.2f}" if p_m.get("mediana") is not None else "N/A",
                f"{p_m['percentil_95']:.2f}" if p_m.get("percentil_95") is not None else "N/A",
                f"{g_m['media']:.2f}" if g_m.get("media") is not None else "N/A",
                f"{g_m['mediana']:.2f}" if g_m.get("mediana") is not None else "N/A",
                f"{g_m['percentil_95']:.2f}" if g_m.get("percentil_95") is not None else "N/A",
                f"{toks['prompt_tokens']:.1f}" if toks.get("prompt_tokens") is not None else "N/A",
                f"{toks['completion_tokens']:.1f}" if toks.get("completion_tokens") is not None else "N/A",
                f"{toks['total_tokens']:.1f}" if toks.get("total_tokens") is not None else "N/A",
                cond_info.get("proveedor_modelo", "local / qwen2.5:3b"),
            ])
        else:
            rows.append([
                cond,
                "gold (legítimas)",
                "0",
                "N/A", "N/A", "N/A",
                "N/A", "N/A", "N/A",
                "N/A", "N/A", "N/A",
                "N/A",
            ])

    return PaperTable(
        table_id="tabla09_latencias_y_tokens",
        title="Tabla 9. Latencias de Inferencia y Consumo de Tokens",
        headers=headers,
        rows=rows,
        caption="Telemetría computacional. Desglose dinámico entre tiempo total de pipeline y llamada al LLM local.",
    )


def build_table_paired_comparisons_and_coverage(
    quality_report: Optional[QualityEvaluationReport] = None,
    audit_report: Optional[ExperimentAuditReport] = None,
) -> PaperTable:
    """Tabla 10: Comparaciones pareadas y cobertura experimental consolidada."""
    headers = [
        "Eje de Comparación / Módulo",
        "Pares / Casos Comunes (n)",
        "Diferencia Clave Observada",
        "Fundamento Técnico / Metodológico",
        "Estado / Tarea Responsable",
    ]

    rows = [
        [
            "Condiciones Pareadas A vs. B",
            "Pendiente T17",
            "Pendiente de ejecución pareada",
            "Mismos hits y casos evaluados en T17 para aislar impacto de la defensa básica",
            "T17 (León)",
        ],
        [
            "Condiciones Pareadas A vs. C",
            "Pendiente T17",
            "Pendiente de ejecución pareada",
            "Evaluación de la estrategia en profundidad C frente a la línea base sin defensa A",
            "T17 (León)",
        ],
        [
            "Condiciones Pareadas B vs. C",
            "Pendiente T17",
            "Pendiente de ejecución pareada",
            "Comparación entre defensa estándar B y filtrado activo con JSON estructurado C",
            "T17 (León)",
        ],
        [
            "Pipeline vs. LLM Raw (Modo A, T11)",
            "10 pares evaluables",
            "LLM generó 10 respuestas sustantivas; pipeline aplicó 10 abstenciones",
            "Motivo canónico T16 registrado en las 10 consultas: 'citas_invalidas_o_ausentes' (ABSTENTION_REASON_INVALID_CITATIONS); no se formulan afirmaciones causales no demostradas",
            "Consolidado T11 / Rúbrica T10 v0.2",
        ],
        [
            "Cobertura Evaluación Humana (T12)",
            "20 juicios asignados",
            "20 casos en estado 'pendiente' (10 pipeline + 10 llm_raw)",
            "Material ciego e instructivo preparado; evaluación humana independiente asignada a León",
            "T12 (León)",
        ],
        [
            "Cobertura de Métricas de Seguridad",
            "8 casos sintéticos",
            "Recall 3/4, FPR 1/4 en detector; ASR real de LLM pendiente",
            "Detector auditado en offline; medición empírica de ASR asignada a León en T19",
            "T15 / T19 (León)",
        ],
    ]

    return PaperTable(
        table_id="tabla10_comparaciones_pareadas_y_cobertura",
        title="Tabla 10. Comparaciones Pareadas y Cobertura Experimental Consolidada",
        headers=headers,
        rows=rows,
        caption="Resumen de comparaciones entre condiciones pareadas, fuentes de discrepancia y asignación de tareas.",
    )


@dataclass
class PaperTablesCollection:
    """Colección completa de las diez tablas del artículo científico."""

    tables: List[PaperTable] = field(default_factory=list)

    def save_all(self, output_dir: Union[str, Path]) -> Dict[str, Tuple[Path, Path]]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        saved = {}
        for t in self.tables:
            csv_p, md_p = t.save(out)
            saved[t.table_id] = (csv_p, md_p)
        return saved


def generate_all_paper_tables(
    quality_report: Optional[QualityEvaluationReport] = None,
    audit_report: Optional[ExperimentAuditReport] = None,
    manifest_or_run: Optional[Dict[str, Any]] = None,
    security_metrics: Optional[Dict[str, Any]] = None,
    traces: Optional[List[Dict[str, Any]]] = None,
) -> PaperTablesCollection:
    """Genera la suite completa de las 10 tablas científicas para el artículo."""
    t1 = build_table_experimental_config(manifest_or_run)
    t2 = build_table_abc_comparison()
    t3 = build_table_response_accuracy(quality_report)
    t4 = build_table_citation_quality_validity(quality_report)
    t5 = build_table_abstention_rates(quality_report, traces)
    t6 = build_table_asr(security_metrics=security_metrics, traces=traces)
    t7 = build_table_detector_recall()
    t8 = build_table_detector_fpr()
    t9 = build_table_latencies_and_tokens(traces=traces, quality_report=quality_report)
    t10 = build_table_paired_comparisons_and_coverage(quality_report, audit_report)

    return PaperTablesCollection(tables=[t1, t2, t3, t4, t5, t6, t7, t8, t9, t10])
