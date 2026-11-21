"""Orquestador para la generación reproducible de artefactos del artículo científico (T20).

Coordina:
1. Auditoría experimental de procedencia, hashes, invariantes y privacidad.
2. Cómputo e integración de métricas de calidad T18 (si anotaciones disponibles).
3. Generación y exportación de las diez tablas científicas en CSV y Markdown.
4. Generación y exportación de las seis figuras científicas en SVG y PNG.
5. Manifiesto de procedencia con hashes de todas las entradas y salidas generadas.
6. Protección estricta contra sobrescritura accidental de evidencias históricas y directorios protegidos.
"""

from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from cs_rag_security.evaluation.audit_experiment import (
    ExperimentAuditReport,
    audit_experiments,
)
from cs_rag_security.evaluation.figures import generate_all_paper_figures
from cs_rag_security.evaluation.quality import (
    QualityEvaluationReport,
    evaluate_quality,
)
from cs_rag_security.evaluation.tables import (
    PaperTablesCollection,
    extract_detector_diagnostic_from_run,
    generate_all_paper_tables,
)
from cs_rag_security.ingestion import digest
from cs_rag_security.traceability import get_git_commit


# Directorios y evidencias estrictamente protegidos: ni siquiera con --force se pueden sobrescribir
PROTECTED_PATHS = frozenset({
    "results/llm_baseline",
    "results/llm_baseline_local",
    "results/offline_20261117",
    "results/offline_20261117_completa",
    "results/offline_20261117_final",
    "results/offline_20261117_v2",
    "results/normative_policy_20261119",
    "results/retrieval_t08_20261119_final",
    "results/corpus_audit",
    "results/t10_subset_retrieval_20261119",
    "results/t12_evaluacion",
    "data",
    "src",
    "docs",
    "scripts",
    "tests",
    "experiments",
})


def validate_output_directory_safety(out_path: Path, existing_runs: List[Path]) -> None:
    """Verifica de manera exhaustiva que la ruta de salida no comprometa evidencias históricas ni archivos protegidos."""
    workspace_root = Path.cwd().resolve()
    out_resolved = out_path.resolve()

    # 1. No puede ser la raíz del workspace ni un directorio padre
    if out_resolved == workspace_root or out_resolved in workspace_root.parents:
        raise PermissionError(f"Operación bloqueada: la ruta '{out_path}' es inválida como directorio de salida.")

    # 2. No puede ser ninguna ruta protegida (histórica, código o datos)
    for prot in PROTECTED_PATHS:
        prot_resolved = (workspace_root / prot).resolve()
        if out_resolved == prot_resolved or prot_resolved in out_resolved.parents:
            raise PermissionError(
                f"Operación bloqueada: la ruta '{out_path}' corresponde a una evidencia histórica, datos o código protegido ('{prot}'). "
                "Incluso con --force está terminantemente prohibido sobrescribir estas ubicaciones."
            )

    # 3. No puede ser un directorio privado de evaluación o trazas
    if "_local" in out_path.name or "t12_evaluacion" in out_path.name:
        raise PermissionError(
            f"Operación bloqueada: la ruta '{out_path}' coincide con un patrón de directorio privado reservado."
        )

    # 4. No puede ser ninguna de las rutas de entrada
    for inp in existing_runs:
        if out_resolved == inp.resolve():
            raise PermissionError(
                f"Operación bloqueada: la ruta de salida coincide con el directorio de entrada '{inp}'."
            )


def collect_file_hashes(paths: List[Union[str, Path]]) -> Dict[str, str]:
    """Calcula y compila los hashes SHA-256 de una lista de archivos existentes."""
    res = {}
    for p in paths:
        path_obj = Path(p)
        if path_obj.is_file():
            res[str(path_obj)] = digest(path_obj)
        elif path_obj.is_dir():
            for sub in sorted(path_obj.glob("*")):
                if sub.is_file() and not sub.name.startswith("."):
                    res[str(sub)] = digest(sub)
    return res


def generate_paper_artifacts(
    output_dir: Union[str, Path],
    run_paths: Optional[List[Union[str, Path]]] = None,
    annotations_path: Optional[Union[str, Path]] = None,
    mapping_path: Optional[Union[str, Path]] = None,
    traces_path: Optional[Union[str, Path]] = None,
    security_metrics_path: Optional[Union[str, Path]] = None,
    force: bool = False,
    base_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Genera el paquete completo de tablas, figuras, reportes y manifiesto para el artículo.

    Garantiza inmutabilidad y protección contra sobrescritura salvo que force=True en rutas no protegidas.
    """
    out = Path(output_dir)
    started_utc = datetime.now(timezone.utc).isoformat()

    # Corridas por defecto si no se especifican explícitamente
    resolved_runs = [Path(r) for r in run_paths] if run_paths else [
        Path("results/llm_baseline"),
        Path("results/offline_20261117_final"),
        Path("results/piloto_ollama_pr7.json"),
    ]
    existing_runs = [r for r in resolved_runs if r.exists()]

    # 1. Validación de seguridad de la ruta de salida (Punto 8)
    validate_output_directory_safety(out, existing_runs)

    # Protección contra sobrescritura accidental en directorios permitidos
    if out.exists() and any(out.iterdir()):
        if not force:
            raise FileExistsError(
                f"El directorio de salida ya existe y contiene archivos: {out}. "
                "Para evitar sobrescritura accidental de evidencias científicas, use una ruta nueva o especifique force=True."
            )
    out.mkdir(parents=True, exist_ok=True)

    # 2. Auditoría experimental
    audit_report: ExperimentAuditReport = audit_experiments(
        run_paths=existing_runs,
        annotations_path=annotations_path,
        mapping_path=mapping_path,
        base_dir=base_dir,
    )

    # Punto 6: Comprobar que una corrida con errores críticos de auditoría no produzca resultados presentados como válidos
    is_valid_for_publication = (audit_report.overall_status != "rechazado")
    if not is_valid_for_publication and not force:
        raise RuntimeError(
            f"Generación abortada: la auditoría experimental detectó errores críticos ({len(audit_report.all_issues)} incidencias). "
            "Para proteger la integridad científica, no se generan artefactos presentados como válidos. "
            "Si requiere generar artefactos de diagnóstico forense marcados como RECHAZADOS, use force=True."
        )

    audit_json_path = out / "audit_report.json"
    audit_md_path = out / "audit_report.md"
    audit_report.save_json(audit_json_path)
    audit_report.save_markdown(audit_md_path)

    # 3. Métricas de calidad T18 (si hay anotaciones disponibles)
    quality_report: Optional[QualityEvaluationReport] = None
    if annotations_path and Path(annotations_path).exists():
        try:
            quality_report = evaluate_quality(
                annotations=annotations_path,
                blind_mapping=mapping_path,
                traces_source=traces_path,
            )
            # Guardar reporte de calidad integrado
            quality_report.save_json(out / "quality_metrics.json")
            quality_report.save_comparison_csv(out / "quality_summary_comparison.csv")
        except Exception as e:
            audit_report.all_limitations.append(f"No se pudieron computar métricas T18 desde {annotations_path}: {e}")

    # 4. Métricas de seguridad T19 (si disponibles mediante ruta explícita)
    security_metrics: Optional[Dict[str, Any]] = None
    if security_metrics_path and Path(security_metrics_path).exists():
        try:
            security_metrics = json.loads(Path(security_metrics_path).read_text(encoding="utf-8"))
        except Exception:
            pass

    # Extraer trazas si se especificó una ruta o desde la primera corrida real
    loaded_traces: Optional[List[Dict[str, Any]]] = None
    if traces_path and Path(traces_path).exists():
        try:
            loaded_traces = json.loads(Path(traces_path).read_text(encoding="utf-8"))
        except Exception:
            pass
    elif existing_runs:
        t_cand = existing_runs[0] / "traces.json" if existing_runs[0].is_dir() else None
        if t_cand and t_cand.exists():
            try:
                loaded_traces = json.loads(t_cand.read_text(encoding="utf-8"))
            except Exception:
                pass

    # Extraer parámetros de corrida para la configuración experimental
    manifest_info: Optional[Dict[str, Any]] = None
    if audit_report.runs_audited:
        for r in audit_report.runs_audited.values():
            if hasattr(r, "parameters") and r.parameters:
                manifest_info = r.parameters
                if getattr(r, "run_type", "") == "real_llm":
                    break

    # 5. Generar las diez tablas del artículo
    tables_collection: PaperTablesCollection = generate_all_paper_tables(
        quality_report=quality_report,
        audit_report=audit_report,
        manifest_or_run=manifest_info,
        security_metrics=security_metrics,
        traces=loaded_traces,
    )
    saved_tables = tables_collection.save_all(out / "tables")

    # 6. Extraer dinámicamente datos para figuras desde quality_report y artefactos reales
    fig_accuracy = {}
    fig_citations = {}
    fig_abstentions = {}

    if quality_report and quality_report.cruzado_condicion_origen:
        for cond, targets in quality_report.cruzado_condicion_origen.items():
            pipe_slice = targets.get("pipeline", {})
            raw_slice = targets.get("llm_raw", {})
            pipe_acc = pipe_slice.get("calidad_contenido", {}).get("exactitud_humana_contenido")
            raw_acc = raw_slice.get("calidad_contenido", {}).get("exactitud_humana_contenido")
            if pipe_acc or raw_acc:
                fig_accuracy[cond] = {"pipeline": pipe_acc, "llm_raw": raw_acc}

            for t_key in ("pipeline", "llm_raw"):
                t_slice = targets.get(t_key, {})
                t_cit = t_slice.get("validez_y_sustento_citas", {})
                t_acc = t_slice.get("contabilidad_casos", {})
                n_sust = t_acc.get("respuestas_sustantivas", 0)
                if n_sust > 0:
                    fig_citations[t_key] = {
                        "substantive_responses": n_sust,
                        "valida_completa": t_cit.get("citas_validas_completas", {}).get("numerator", 0),
                        "brecha": t_cit.get("brecha_pertenencia_sin_sustento", {}).get("total_pertenecen_sin_sustento_completo", {}).get("numerator", 0),
                        "alucinada": t_cit.get("pertenencia_contexto", {}).get("citas_pertenecen_no", {}).get("numerator", 0),
                        "sin_citas": t_cit.get("pertenencia_contexto", {}).get("respuestas_sin_citas", {}).get("numerator", 0),
                    }

    # Diagnóstico del detector extraído dinámicamente de artefactos reales existentes
    detector_diagnostic_data = extract_detector_diagnostic_from_run()

    figure_data = {
        "accuracy": fig_accuracy,
        "citations": fig_citations,
        "abstentions": fig_abstentions,
        "security": security_metrics or {},
        "detector": detector_diagnostic_data,
        "latencies": {},
    }
    saved_figures = generate_all_paper_figures(figure_data, out / "figures")

    # 7. Documento de reproducción y documentación metodológica
    repro_doc = out / "DOCUMENTACION_REPRODUCCION.md"
    repro_text = [
        "# Documentación de Reproducción de Artefactos — CS_RAG_Security (T20)",
        "",
        "Este paquete reúne los artefactos científicos (tablas, figuras y auditorías) para el artículo del proyecto.",
        "",
        "## Archivos Generados",
        "",
        "### 1. Auditoría Experimental",
        f"- [`audit_report.json`](audit_report.json): Dictamen estructurado de procedencia e invariantes.",
        f"- [`audit_report.md`](audit_report.md): Reporte narrativo de hallazgos, incidencias y limitaciones.",
        "",
        "### 2. Tablas Científicas (`tables/`)",
        "- `tabla01_configuracion_experimental`: Parámetros e invariantes compartidos.",
        "- `tabla02_comparacion_abc`: Matriz comparativa de condiciones operacionales.",
        "- `tabla03_exactitud_respuestas`: Exactitud humana de respuestas según Rúbrica v0.2.",
        "- `tabla04_calidad_validez_citas`: Pertenencia contextual frente a sustento factual real.",
        "- `tabla05_tasas_abstencion`: Tasa y causas canónicas de abstención del pipeline.",
        "- `tabla06_seguridad_asr`: Tasa de éxito de ataques (ASR) diferenciando LLM real de mock.",
        "- `tabla07_recall_detector`: Sensibilidad del detector heurístico sobre batería sintética (diagnóstico preliminar).",
        "- `tabla08_falsos_positivos_fpr`: Falsos positivos del detector sobre controles benignos (diagnóstico preliminar).",
        "- `tabla09_latencias_y_tokens`: Telemetría computacional y tokens.",
        "- `tabla10_comparaciones_pareadas_y_cobertura`: Resumen de contrastes pareados y vacíos de medición.",
        "",
        "### 3. Figuras Científicas (`figures/`)",
        "- `fig1_exactitud_abc.[svg|png]`: Comparación de exactitud A/B/C desacoplando pipeline y LLM raw.",
        "- `fig2_validez_citas.[svg|png]`: Desglose de validez y sustento fáctico de citas.",
        "- `fig3_tasas_abstencion.[svg|png]`: Tasas y causas de abstención.",
        "- `fig4_asr_condicion.[svg|png]`: ASR por condición con advertencia explícita ante datos mock.",
        "- `fig5_detector_metricas.[svg|png]`: Recall y FPR del detector heurístico (diagnóstico preliminar).",
        "- `fig6_latencias_condicion.[svg|png]`: Latencias de inferencia y generación.",
        "",
        "## Contrato de Integración para Métricas de Seguridad (T19)",
        "Las métricas de seguridad con LLM real están asignadas a León (**T19**). El orquestador acepta una ruta explícita",
        "mediante `--security-metrics <archivo.json>` con el siguiente esquema JSON esperado:",
        "```json",
        "{",
        '  "tarea": "T19_metricas_seguridad",',
        '  "modelo": "qwen2.5:3b",',
        '  "A_sin_defensa": {',
        '    "total_attacks": 4,',
        '    "marker_emitted_total": 4,',
        '    "attacks_retrieved": 4,',
        '    "marker_emitted_retrieved": 4,',
        '    "asr_retrieved_percent": 100.0,',
        '    "attacks_not_retrieved": 0',
        "  },",
        '  "B_defensa_basica": { ... },',
        '  "C_defensa_propuesta": { ... }',
        "}",
        "```",
        "En ausencia de este archivo, el sistema reporta formalmente `Pendiente (T19 asignada a León)` sin inventar datos.",
        "",
        "## Límites Metodológicos y de Publicación",
        "- No se exponen textos de preguntas gold, fragmentos del corpus ni respuestas crudas del LLM en ninguno de estos artefactos.",
        "- Los datos faltantes o evaluaciones pendientes nunca se representan como cero.",
        "- Las pruebas mock no se atribuyen como eficacia defensiva frente a un LLM; se etiquetan exclusivamente como diagnósticos preliminares.",
        "- En las 10 consultas de T11 (Modo A), el motivo registrado fue citas_invalidas_o_ausentes; no se formulan afirmaciones causales no demostradas.",
        "- El escaneo de privacidad constituye un filtro heurístico automatizado; no representa una garantía matemática de ausencia absoluta de fugas.",
    ]
    repro_doc.write_text("\n".join(repro_text), encoding="utf-8")

    # 8. Compilar hashes de entrada y salida para el manifiesto
    input_paths = [str(r) for r in existing_runs]
    if annotations_path:
        input_paths.append(str(annotations_path))
    if mapping_path:
        input_paths.append(str(mapping_path))
    if security_metrics_path:
        input_paths.append(str(security_metrics_path))

    inputs_sha256 = collect_file_hashes(input_paths)
    outputs_sha256 = collect_file_hashes([out / "tables", out / "figures", audit_json_path, audit_md_path, repro_doc])

    finished_utc = datetime.now(timezone.utc).isoformat()

    manifest = {
        "tarea": "T20_auditoria_tablas_figuras",
        "descripcion": "Generación de auditoría experimental, tablas científicas y figuras para el artículo",
        "started_utc": started_utc,
        "finished_utc": finished_utc,
        "entorno": {
            "python_version": platform.python_version(),
            "commit_git": get_git_commit(),
        },
        "valido_para_publicacion": is_valid_for_publication,
        "corridas_utilizadas": [str(r) for r in existing_runs],
        "archivos_entrada": {
            "annotations_path": str(annotations_path) if annotations_path else None,
            "mapping_path": str(mapping_path) if mapping_path else None,
            "security_metrics_path": str(security_metrics_path) if security_metrics_path else None,
        },
        "hashes_entradas": inputs_sha256,
        "hashes_salidas": outputs_sha256,
        "auditoria_resumen": {
            "dictamen_global": audit_report.overall_status,
            "total_incidencias": len(audit_report.all_issues),
            "total_limitaciones": len(audit_report.all_limitations),
            "privacidad_conforme": audit_report.privacy_audit.get("compliant", True),
        },
        "total_tablas_generadas": len(saved_tables),
        "total_figuras_generadas": len(saved_figures),
    }

    if not is_valid_for_publication:
        manifest["advertencia_critica"] = "ARTEFACTOS DE AUDITORÍA RECHAZADOS: CONTIENEN ERRORES CRÍTICOS - NO VÁLIDOS PARA PUBLICACIÓN"

    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "output_dir": str(out),
        "manifest": manifest,
        "audit_report": audit_report.to_dict(),
        "tables_saved": {k: [str(p1), str(p2)] for k, (p1, p2) in saved_tables.items()},
        "figures_saved": {k: [str(p1), str(p2)] for k, (p1, p2) in saved_figures.items()},
    }
