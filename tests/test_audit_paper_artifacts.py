"""Pruebas automatizadas para la auditoría experimental, tablas y figuras científicas (T20).

Verifica:
- Auditoría exhaustiva de corridas reales (T11 baseline, offline mock, piloto PR7).
- Tratamiento estricto de denominadores cero (sin divisiones por cero ni valores inventados).
- Detección de datos incompletos y evaluaciones humanas pendientes (T12).
- Detección de corridas incompatibles (discrepancia en hashes de índice o datasets).
- Detección de ejecuciones duplicadas dentro de una misma corrida.
- Detección rigurosa de fugas de privacidad (preguntas gold, texto de fragmentos, raw_response, API keys).
- Generación y consistencia de tablas científicas en CSV y Markdown.
- Generación y consistencia de figuras científicas en SVG y PNG.
- Integración con métricas de calidad T18 (rúbrica v0.2).
- Manejo formal de la ausencia de métricas de seguridad T19 (reporte como pendiente sin inventar datos).
- Protección estricta contra sobrescritura accidental de resultados.
- Ejecución reproducible mediante CLI y script con registro de hashes en manifiesto.
"""

import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest
from PIL import Image

from cs_rag_security.evaluation.audit_experiment import (
    CODE_DUPLICATE_CASE,
    CODE_FILE_MISSING,
    CODE_HASH_MISMATCH,
    CODE_INCOMPATIBLE_RUNS,
    CODE_MALFORMED_HASH,
    CODE_MISSING_CASES,
    CODE_MOCK_RUN_LIMITATION,
    CODE_PENDING_EVALUATIONS,
    CODE_PRIVACY_VIOLATION,
    CODE_UNIMODAL_RUN,
    HASH_STATUS_FILE_NOT_FOUND,
    HASH_STATUS_MALFORMED,
    HASH_STATUS_MISMATCH,
    HASH_STATUS_VERIFIED,
    RUN_TYPE_MOCK_OFFLINE,
    RUN_TYPE_PILOT_LLM,
    RUN_TYPE_REAL_LLM,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    audit_experiments,
    audit_human_evaluation_coverage,
    audit_run,
    check_privacy_compliance_in_data,
    is_valid_sha256,
    verify_file_hashes,
)
from cs_rag_security.evaluation.figures import (
    generate_all_paper_figures,
    generate_fig_asr_condicion,
    generate_fig_exactitud_abc,
    generate_fig_latencias_condicion,
)
from cs_rag_security.evaluation.paper import generate_paper_artifacts
from cs_rag_security.evaluation.tables import (
    build_table_citation_quality_validity,
    build_table_latencies_and_tokens,
    extract_latency_and_token_metrics,
    format_fraction_cell,
    format_markdown_table,
    generate_all_paper_tables,
)
from cs_rag_security.ingestion import digest


def test_audit_real_and_mock_runs(tmp_path):
    """Verifica la auditoría sobre las evidencias existentes en el repositorio y fixtures sintéticos."""
    # 1. Baseline T11
    res_t11 = audit_run("results/llm_baseline")
    assert res_t11.run_type == RUN_TYPE_REAL_LLM
    assert res_t11.parameters["provider"] == "local"
    assert res_t11.parameters["model"] == "qwen2.5:3b"
    assert res_t11.parameters["seed"] == 42
    assert res_t11.parameters["temperature"] == 0
    assert res_t11.parameters["top_k"] == 5
    assert res_t11.parameters_compliant is True
    assert res_t11.conditions_present == ["A_sin_defensa"]
    assert res_t11.is_multimodal_abc is False
    assert res_t11.cases_count == 10
    assert res_t11.privacy_compliant is True

    # No clasificar como verificada una evidencia que no pudo comprobarse
    expected_index_status = (
        HASH_STATUS_VERIFIED
        if Path("data/vector_db/index.json").exists()
        else HASH_STATUS_FILE_NOT_FOUND
    )
    expected_gold_status = (
        HASH_STATUS_VERIFIED
        if Path("data/corpus_unsa/03_Preguntas_Respuestas/gold_questions.json").exists()
        else HASH_STATUS_FILE_NOT_FOUND
    )
    assert res_t11.hashes_status["index_sha256"]["status"] == expected_index_status
    assert res_t11.hashes_status["gold_sha256"]["status"] == expected_gold_status

    # 2. Mock offline 20261117_final
    res_mock = audit_run("results/offline_20261117_final")
    assert res_mock.run_type == RUN_TYPE_MOCK_OFFLINE
    assert res_mock.parameters["provider"] == "mock"
    assert res_mock.is_multimodal_abc is True
    assert len(res_mock.conditions_present) == 3
    assert res_mock.cases_count == 48  # 40 gold + 8 sintéticos
    assert any(i.code == CODE_MOCK_RUN_LIMITATION for i in res_mock.issues)

    # 3. Piloto PR7
    res_pilot = audit_run("results/piloto_ollama_pr7.json")
    assert res_pilot.run_type == RUN_TYPE_PILOT_LLM
    assert res_pilot.cases_count == 1

    # 4. Desacoplamiento de pruebas automatizadas mediante fixture sintético en tmp_path
    synth_index = tmp_path / "data/vector_db/index.json"
    synth_index.parent.mkdir(parents=True, exist_ok=True)
    synth_index.write_text(json.dumps({"fragmentos": ["f1", "f2"]}), encoding="utf-8")
    synth_index_hash = digest(synth_index)

    synth_gold = tmp_path / "data/corpus_unsa/03_Preguntas_Respuestas/gold_questions.json"
    synth_gold.parent.mkdir(parents=True, exist_ok=True)
    synth_gold.write_text(json.dumps({"preguntas": []}), encoding="utf-8")
    synth_gold_hash = digest(synth_gold)

    synth_run = tmp_path / "synthetic_run"
    synth_run.mkdir()
    (synth_run / "manifest.json").write_text(
        json.dumps({
            "run_id": "synth_1",
            "proveedor": "local",
            "modelo": "qwen2.5:3b",
            "index_sha256": synth_index_hash,
            "gold_sha256": synth_gold_hash,
            "parametros": {"seed": 42, "temperature": 0, "top_k": 5},
        }),
        encoding="utf-8",
    )
    (synth_run / "traces.json").write_text(json.dumps([]), encoding="utf-8")

    res_synth = audit_run(synth_run, base_dir=tmp_path)
    assert res_synth.hashes_status["index_sha256"]["status"] == HASH_STATUS_VERIFIED
    assert res_synth.hashes_status["gold_sha256"]["status"] == HASH_STATUS_VERIFIED
    assert res_synth.hashes_status["index_sha256"]["computed"] == synth_index_hash
    assert res_synth.hashes_status["gold_sha256"]["computed"] == synth_gold_hash


def test_audit_zero_denominators_handling():
    """Verifica que denominadores cero produzcan N/A o Pendiente sin lanzar divisiones por cero."""
    # Celda de fracción con denominador 0
    zero_frac = {"numerator": 0, "denominator": 0, "rate_percent": None, "value": None}
    cell_text = format_fraction_cell(zero_frac, default_pending="Pendiente")
    assert "Pendiente (0/0)" in cell_text

    none_frac = {"numerator": None, "denominator": 0, "rate_percent": None, "value": None}
    cell_none = format_fraction_cell(none_frac, default_pending="N/A")
    assert "N/A (0/0)" in cell_none

    # Fracción válida
    valid_frac = {"numerator": 8, "denominator": 10, "rate_percent": 80.0, "value": 0.8}
    assert format_fraction_cell(valid_frac) == "80.00% (8/10)"

    # Formateo de tabla markdown con celdas None
    headers = ["Metrica", "Valor"]
    rows = [["Exactitud", None], ["Abstencion", "100.0%"]]
    md = format_markdown_table(headers, rows)
    assert "N/A" in md
    assert "100.0%" in md


def test_audit_incomplete_data_and_pending_cases(tmp_path):
    """Verifica la detección de casos faltantes y la auditoría de anotaciones humanas pendientes."""
    # 1. Detección de casos faltantes frente a lista esperada
    expected = ["GQ001", "GQ002", "GQ003", "GQ004"]
    # Simulamos una corrida que solo tiene GQ004
    run_dir = tmp_path / "run_incomplete"
    run_dir.mkdir()
    manifest = {
        "run_id": "incomplete_1",
        "proveedor": "local",
        "modelo": "qwen2.5:3b",
        "parametros": {"seed": 42, "temperature": 0, "top_k": 5},
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    traces = [{"case_id": "GQ004", "condition": "A_sin_defensa"}]
    (run_dir / "traces.json").write_text(json.dumps(traces), encoding="utf-8")

    res = audit_run(run_dir, expected_cases=expected)
    assert any(i.code == CODE_MISSING_CASES for i in res.issues)
    assert set(res.missing_expected_cases) == {"GQ001", "GQ002", "GQ003"}

    # 2. Auditoría de anotaciones humanas reales de T12 (todas pendientes)
    t12_csv = Path("results/t12_evaluacion/t12_evaluacion_ciega.csv")
    if t12_csv.exists():
        cov = audit_human_evaluation_coverage(t12_csv)
        assert cov["status"] == "pendiente"
        assert cov["total_registros"] == 20
        assert cov["evaluables"] == 0
        assert cov["pendientes"] == 20
        assert cov["tasa_pendientes"] == "100.0%"


def test_audit_incompatible_runs(tmp_path):
    """Verifica que corridas con hashes de índice o gold distintos sean señaladas como incompatibles."""
    run1 = tmp_path / "run_1"
    run1.mkdir()
    (run1 / "manifest.json").write_text(
        json.dumps({
            "run_id": "r1", "proveedor": "local", "modelo": "qwen2.5:3b",
            "index_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "gold_sha256": "622eb3d76e5d56138358d20db376d6e62f61ac378b1c0d41dbc3a543c8210da2",
        }),
        encoding="utf-8",
    )
    (run1 / "traces.json").write_text(json.dumps([]), encoding="utf-8")

    run2 = tmp_path / "run_2"
    run2.mkdir()
    (run2 / "manifest.json").write_text(
        json.dumps({
            "run_id": "r2", "proveedor": "local", "modelo": "qwen2.5:3b",
            "index_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "gold_sha256": "622eb3d76e5d56138358d20db376d6e62f61ac378b1c0d41dbc3a543c8210da2",
        }),
        encoding="utf-8",
    )
    (run2 / "traces.json").write_text(json.dumps([]), encoding="utf-8")

    rep = audit_experiments([run1, run2])
    assert rep.overall_status == "rechazado"
    assert any(i.code == CODE_INCOMPATIBLE_RUNS for i in rep.all_issues)
    assert rep.cross_run_consistency["shared_index_hash"] is False


def test_audit_duplicate_cases_detection(tmp_path):
    """Verifica que se detecten tuplas (case_id, condition) duplicadas."""
    run_dir = tmp_path / "run_dups"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps({"run_id": "r_dup", "proveedor": "local", "modelo": "qwen2.5:3b"}),
        encoding="utf-8",
    )
    # Misma consulta y misma condición dos veces
    traces = [
        {"case_id": "GQ004", "condition": "A_sin_defensa", "abstained": True},
        {"case_id": "GQ004", "condition": "A_sin_defensa", "abstained": True},
    ]
    (run_dir / "traces.json").write_text(json.dumps(traces), encoding="utf-8")

    res = audit_run(run_dir)
    assert any(i.code == CODE_DUPLICATE_CASE for i in res.issues)
    assert len(res.duplicates) == 1


def test_audit_privacy_boundaries_detection():
    """Verifica que se identifique cualquier exposición de datos privados."""
    gold_q = ["¿Cuál es el procedimiento de convalidación académica según el RCU-0161-2021?"]

    # 1. Exposición de raw_response
    rec_raw = [{"case_id": "c1", "raw_response": "Texto confidencial del modelo"}]
    ok, issues = check_privacy_compliance_in_data(rec_raw, gold_questions=gold_q, source_name="test_raw")
    assert ok is False
    assert any("raw_response" in i.message for i in issues)

    # 2. Exposición de question
    rec_q = [{"case_id": "c2", "question": "¿Pregunta no permitida?"}]
    ok, issues = check_privacy_compliance_in_data(rec_q, gold_questions=gold_q, source_name="test_q")
    assert ok is False
    assert any("question" in i.message for i in issues)

    # 3. Exposición de texto en fragmentos
    rec_chunk = [{
        "case_id": "c3",
        "retrieved_chunks": [{"chunk_id": "ch1", "texto": "Fragmento privado del PDF"}],
    }]
    ok, issues = check_privacy_compliance_in_data(rec_chunk, gold_questions=gold_q, source_name="test_chunk")
    assert ok is False
    assert any("texto" in i.message for i in issues)

    # 4. Enunciado literal de gold_questions
    rec_gold = [{"case_id": "c4", "response": "¿Cuál es el procedimiento de convalidación académica según el RCU-0161-2021?"}]
    ok, issues = check_privacy_compliance_in_data(rec_gold, gold_questions=gold_q, source_name="test_gold")
    assert ok is False
    assert any("pregunta gold" in i.message for i in issues)

    # 5. Clave de API
    rec_key = [{"case_id": "c5", "metadata": "sk-proj-1234567890abcdef"}]
    ok, issues = check_privacy_compliance_in_data(rec_key, gold_questions=gold_q, source_name="test_key")
    assert ok is False
    assert any("credencial" in i.message for i in issues)

    # 6. Registro saneado conforme
    rec_clean = [{
        "case_id": "GQ004",
        "condition": "A_sin_defensa",
        "abstained": True,
        "abstention_reason": "citas_invalidas_o_ausentes",
        "citations_valid": False,
        "citations_invalid_count": 0,
        "latency_pipeline_seconds": 24.5,
    }]
    ok, issues = check_privacy_compliance_in_data(rec_clean, gold_questions=gold_q, source_name="test_clean")
    assert ok is True
    assert len(issues) == 0


def test_paper_tables_generation(tmp_path):
    """Verifica la generación de las 10 tablas científicas en CSV y Markdown."""
    tables_dir = tmp_path / "tables"
    collection = generate_all_paper_tables()
    assert len(collection.tables) == 10

    saved = collection.save_all(tables_dir)
    assert len(saved) == 10

    for tid, (csv_p, md_p) in saved.items():
        assert csv_p.exists() and csv_p.stat().st_size > 0
        assert md_p.exists() and md_p.stat().st_size > 0

        # Validar que el CSV se puede parsear sin error
        with csv_p.open(encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) >= 2  # Encabezado + al menos 1 fila

        # Validar que el Markdown contiene encabezados y separadores
        md_content = md_p.read_text(encoding="utf-8")
        assert "| " in md_content
        assert "| ---" in md_content


def test_scientific_figures_generation(tmp_path):
    """Verifica la generación de las 6 figuras científicas en SVG y PNG."""
    fig_dir = tmp_path / "figures"
    saved = generate_all_paper_figures(output_dir=fig_dir)
    assert len(saved) == 6

    for fid, (svg_p, png_p) in saved.items():
        assert svg_p.exists() and svg_p.stat().st_size > 0
        assert png_p.exists() and png_p.stat().st_size > 0

        # Validar estructura XML de SVG
        svg_text = svg_p.read_text(encoding="utf-8")
        assert svg_text.startswith("<svg")
        assert svg_text.strip().endswith("</svg>")

        # Validar carga de imagen PNG con Pillow
        with Image.open(png_p) as img:
            assert img.format == "PNG"
            assert img.size[0] >= 800
            assert img.size[1] >= 400


def test_missing_values_not_plotted_as_zero(tmp_path):
    """Verifica que valores faltantes o pendientes no se representen como 0% en figuras."""
    fig_dir = tmp_path / "figs_no_zero"

    # Figura 1 sin datos evaluables (T12 pendiente)
    s1, p1 = generate_fig_exactitud_abc(accuracy_data={}, output_dir=fig_dir)
    svg1 = s1.read_text(encoding="utf-8")
    assert "Evaluación Humana Pendiente" in svg1
    assert "Denominador evaluable: n=0" in svg1

    # Figura 4 sin métricas de seguridad T19
    s4, p4 = generate_fig_asr_condicion(security_data=None, output_dir=fig_dir)
    svg4 = s4.read_text(encoding="utf-8")
    assert "MÉTRICAS DE SEGURIDAD CON LLM REAL PENDIENTES" in svg4
    assert "Jamás se grafica como 0% de ataque" in svg4


def test_integration_with_t18_and_pending_t12(tmp_path):
    """Verifica la integración con T18 y el tratamiento formal de T12 pendiente."""
    out_dir = tmp_path / "paper_artifacts_t18"
    res = generate_paper_artifacts(
        output_dir=out_dir,
        annotations_path="results/t12_evaluacion/t12_evaluacion_ciega.csv",
        mapping_path="results/t12_evaluacion/t12_material_ciego.json",
        traces_path="results/llm_baseline/traces.json",
    )

    manifest = res["manifest"]
    assert manifest["auditoria_resumen"]["privacidad_conforme"] is True
    assert (out_dir / "audit_report.json").exists()
    assert (out_dir / "audit_report.md").exists()
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "DOCUMENTACION_REPRODUCCION.md").exists()
    assert (out_dir / "tables").exists()
    assert (out_dir / "figures").exists()

    # Tabla 3 de exactitud debe reportar formalmente 'Pendiente T12'
    t3_md = (out_dir / "tables/tabla03_exactitud_respuestas.md").read_text(encoding="utf-8")
    assert "Pendiente" in t3_md
    assert "0/0" in t3_md


def test_absence_of_t19_metrics_handling(tmp_path):
    """Verifica que ante la ausencia de métricas T19, el sistema informe N/A sin fallar ni inventar datos."""
    out_dir = tmp_path / "paper_no_t19"
    res = generate_paper_artifacts(
        output_dir=out_dir,
        security_metrics_path=None,
    )

    # Tabla 6 de ASR
    t6_md = (out_dir / "tables/tabla06_seguridad_asr.md").read_text(encoding="utf-8")
    assert "Pendiente (T19 asignada a León)" in t6_md
    assert "mock_extractivo_v1" in t6_md
    assert "NO mide obediencia de LLM" in t6_md


def test_protection_against_accidental_overwrite(tmp_path):
    """Verifica que se impida la sobrescritura accidental de evidencias existentes."""
    out_dir = tmp_path / "existing_run"
    out_dir.mkdir()
    dummy_file = out_dir / "dummy.txt"
    dummy_file.write_text("datos previos", encoding="utf-8")

    # Sin force=True debe lanzar FileExistsError
    with pytest.raises(FileExistsError):
        generate_paper_artifacts(output_dir=out_dir, force=False)

    # Con force=True debe permitir la regeneración
    res = generate_paper_artifacts(output_dir=out_dir, force=True)
    assert res["output_dir"] == str(out_dir)
    assert (out_dir / "manifest.json").exists()


def test_force_cannot_overwrite_protected_or_historical_paths():
    """Verifica que --force no pueda sobrescribir evidencias históricas, datos ni áreas privadas (Punto 8)."""
    # 1. Evidencia histórica de T11
    with pytest.raises(PermissionError, match="Operación bloqueada"):
        generate_paper_artifacts(output_dir="results/llm_baseline", force=True)

    # 2. Evidencia histórica mock
    with pytest.raises(PermissionError, match="Operación bloqueada"):
        generate_paper_artifacts(output_dir="results/offline_20261117_final", force=True)

    # 3. Directorio de datos
    with pytest.raises(PermissionError, match="Operación bloqueada"):
        generate_paper_artifacts(output_dir="data", force=True)

    # 4. Directorio privado
    with pytest.raises(PermissionError, match="Operación bloqueada"):
        generate_paper_artifacts(output_dir="results/llm_baseline_local", force=True)


def test_critical_audit_error_blocks_generation(tmp_path):
    """Verifica que una corrida con errores críticos de auditoría no produzca resultados válidos (Punto 6)."""
    # 1. Caso hash malformado: debe detectarse como error crítico incluso si el archivo original no existe
    bad_run = tmp_path / "bad_run"
    bad_run.mkdir()
    # Manifiesto con hash deliberadamente malformado
    (bad_run / "manifest.json").write_text(
        json.dumps({
            "run_id": "bad_run_1",
            "proveedor": "local",
            "modelo": "qwen2.5:3b",
            "index_sha256": "hash_totalmente_corrompido_00000000000000000000000000000000",
        }),
        encoding="utf-8",
    )
    (bad_run / "traces.json").write_text(json.dumps([]), encoding="utf-8")

    # El hash malformado debe detectarse directamente en la auditoría unitaria
    audit_res = audit_run(bad_run)
    assert audit_res.hashes_status["index_sha256"]["status"] == HASH_STATUS_MALFORMED
    assert any(i.code == CODE_MALFORMED_HASH and i.severity == SEVERITY_ERROR for i in audit_res.issues)

    out_dir = tmp_path / "out_blocked"

    # Sin force debe abortar con RuntimeError
    with pytest.raises(RuntimeError, match="Generación abortada: la auditoría experimental detectó errores críticos"):
        generate_paper_artifacts(output_dir=out_dir, run_paths=[bad_run], force=False)

    # Con force=True genera artefactos explícitamente marcados como RECHAZADOS / NO VÁLIDOS
    res = generate_paper_artifacts(output_dir=out_dir, run_paths=[bad_run], force=True)
    assert res["manifest"]["valido_para_publicacion"] is False
    assert "ARTEFACTOS DE AUDITORÍA RECHAZADOS" in res["manifest"].get("advertencia_critica", "")

    # 2. Caso archivo alterado (mismatch con hash válido pero no coincidente): también bloquea generación
    fake_base = tmp_path / "env_mismatch"
    synth_file = fake_base / "data/vector_db/index.json"
    synth_file.parent.mkdir(parents=True, exist_ok=True)
    synth_file.write_text("contenido real sintético", encoding="utf-8")

    mismatch_run = tmp_path / "run_mismatch"
    mismatch_run.mkdir()
    (mismatch_run / "manifest.json").write_text(
        json.dumps({
            "run_id": "bad_run_mismatch",
            "proveedor": "local",
            "modelo": "qwen2.5:3b",
            "index_sha256": "0" * 64,  # hash válido de 64 hex pero que no coincide con el contenido
        }),
        encoding="utf-8",
    )
    (mismatch_run / "traces.json").write_text(json.dumps([]), encoding="utf-8")

    out_mismatch = tmp_path / "out_mismatch_blocked"
    with pytest.raises(RuntimeError, match="Generación abortada: la auditoría experimental detectó errores críticos"):
        generate_paper_artifacts(output_dir=out_mismatch, run_paths=[mismatch_run], force=False, base_dir=fake_base)


def test_no_causal_claims_in_mode_a_artifacts(tmp_path):
    """Verifica que no se formulen afirmaciones causales no demostradas sobre las abstenciones de T11 (Punto 2)."""
    out_dir = tmp_path / "out_causal_check"
    generate_paper_artifacts(output_dir=out_dir)

    t5_md = (out_dir / "tables/tabla05_tasas_abstencion.md").read_text(encoding="utf-8")
    t10_md = (out_dir / "tables/tabla10_comparaciones_pareadas_y_cobertura.md").read_text(encoding="utf-8")
    f1_svg = (out_dir / "figures/fig1_exactitud_abc.svg").read_text(encoding="utf-8")
    f3_svg = (out_dir / "figures/fig3_tasas_abstencion.svg").read_text(encoding="utf-8")

    # Ninguno debe atribuir causalidad no demostrada al prompt
    all_content = t5_md + t10_md + f1_svg + f3_svg
    assert "Asimetría Metodológica en Modo A" not in all_content
    assert "Ausencia de directiva de citas formales en prompt de Modo A activa filtro" not in all_content
    # Debe consignar el motivo canónico formal
    assert "citas_invalidas_o_ausentes" in all_content
    assert "no se formulan afirmaciones causales no demostradas" in all_content


def test_privacy_audit_does_not_leak_detected_content():
    """Verifica que el reporte de incidencias no reproduzca secretos ni textos privados detectados (Punto 9)."""
    secret = "sk-proj-supersecreto1234567890abcdef"
    gold_text = "¿Cuál es la regulación específica del régimen de matrícula según el RCU-0127-2020?"
    dirty_records = [
        {"case_id": "c1", "api_key": secret},
        {"case_id": "c2", "response": gold_text},
    ]

    ok, issues = check_privacy_compliance_in_data(dirty_records, gold_questions=[gold_text], source_name="test")
    assert ok is False
    assert len(issues) >= 2

    for iss in issues:
        # El secreto y el texto gold NO deben figurar en el mensaje de la incidencia
        assert secret not in iss.message
        assert gold_text not in iss.message
        assert "omitid" in iss.message.lower()


def test_historical_code_evolution_distinguished_from_evidence_alteration(tmp_path):
    """Verifica que la auditoría distinga la evolución legítima del código de una alteración de datos (Punto 5)."""
    # 1. Verificación reproducible e independiente mediante fixtures sintéticos en tmp_path
    fake_base = tmp_path / "env_synth"
    synth_idx = fake_base / "data/vector_db/index.json"
    synth_idx.parent.mkdir(parents=True, exist_ok=True)
    synth_idx.write_text(json.dumps({"version": "sintetica_v1"}), encoding="utf-8")
    valid_idx_hash = digest(synth_idx)

    synth_gold = fake_base / "data/corpus_unsa/03_Preguntas_Respuestas/gold_questions.json"
    synth_gold.parent.mkdir(parents=True, exist_ok=True)
    synth_gold.write_text(json.dumps({"preguntas": ["P1"]}), encoding="utf-8")
    valid_gold_hash = digest(synth_gold)

    synth_run_dir = tmp_path / "run_historical"
    synth_run_dir.mkdir()
    (synth_run_dir / "manifest.json").write_text(
        json.dumps({
            "run_id": "synth_historical_1",
            "proveedor": "local",
            "modelo": "qwen2.5:3b",
            "commit_git": "0000000000000000000000000000000000000000",
            "index_sha256": valid_idx_hash,
            "gold_sha256": valid_gold_hash,
            "parametros": {"seed": 42, "temperature": 0, "top_k": 5},
        }),
        encoding="utf-8",
    )
    (synth_run_dir / "traces.json").write_text(json.dumps([]), encoding="utf-8")

    res_synth = audit_run(synth_run_dir, base_dir=fake_base)
    # Los datos sintéticos originales están íntegros
    assert res_synth.hashes_status["index_sha256"]["status"] == HASH_STATUS_VERIFIED
    assert res_synth.hashes_status["gold_sha256"]["status"] == HASH_STATUS_VERIFIED

    # La evolución legítima de código se clasifica como SEVERITY_INFO
    code_issues_synth = [i for i in res_synth.issues if i.code == "HISTORICAL_CODE_EVOLUTION"]
    assert len(code_issues_synth) >= 1
    assert code_issues_synth[0].severity == SEVERITY_INFO
    assert "evolución legítima" in code_issues_synth[0].message

    # 2. Alteración deliberada de evidencia de datos frente a evolución de código
    synth_idx.write_text(json.dumps({"version": "sintetica_alterada"}), encoding="utf-8")
    res_altered = audit_run(synth_run_dir, base_dir=fake_base)
    # Debe señalar discrepancia crítica de datos con SEVERITY_ERROR
    assert res_altered.hashes_status["index_sha256"]["status"] == HASH_STATUS_MISMATCH
    assert any(i.code == CODE_HASH_MISMATCH and i.severity == SEVERITY_ERROR for i in res_altered.issues)

    # 3. Comprobación sobre evidencia histórica de T11 en el repositorio local
    res = audit_run("results/llm_baseline")
    # No clasificar como verificada una evidencia que no pudo comprobarse
    expected_index_status = (
        HASH_STATUS_VERIFIED
        if Path("data/vector_db/index.json").exists()
        else HASH_STATUS_FILE_NOT_FOUND
    )
    expected_gold_status = (
        HASH_STATUS_VERIFIED
        if Path("data/corpus_unsa/03_Preguntas_Respuestas/gold_questions.json").exists()
        else HASH_STATUS_FILE_NOT_FOUND
    )
    assert res.hashes_status["index_sha256"]["status"] == expected_index_status
    assert res.hashes_status["gold_sha256"]["status"] == expected_gold_status

    code_issues = [i for i in res.issues if i.code == "HISTORICAL_CODE_EVOLUTION"]
    assert len(code_issues) >= 1
    assert code_issues[0].severity == SEVERITY_INFO
    assert "evolución legítima" in code_issues[0].message


def test_hash_verification_all_states(tmp_path):
    """Verifica explícitamente los 4 estados: verified, mismatch, malformed y file_not_found."""
    fake_base = tmp_path / "env_states"
    idx_file = fake_base / "data/vector_db/index.json"
    idx_file.parent.mkdir(parents=True, exist_ok=True)
    idx_file.write_text("indice real de prueba", encoding="utf-8")
    idx_hash = digest(idx_file)

    # 1. Verified (archivo presente y hash coincide)
    res_v, iss_v = verify_file_hashes({"index_sha256": idx_hash}, base_dir=fake_base)
    assert res_v["index_sha256"]["status"] == HASH_STATUS_VERIFIED
    assert len(iss_v) == 0

    # 2. Mismatch (archivo alterado: existe pero el hash calculado discrepa)
    res_m, iss_m = verify_file_hashes({"index_sha256": "a" * 64}, base_dir=fake_base)
    assert res_m["index_sha256"]["status"] == HASH_STATUS_MISMATCH
    assert any(i.code == CODE_HASH_MISMATCH and i.severity == SEVERITY_ERROR for i in iss_m)

    # 3. Malformed (hash con formato corrupto/inválido: archivo presente)
    res_mal_pres, iss_mal_pres = verify_file_hashes({"index_sha256": "malformed_hash_123"}, base_dir=fake_base)
    assert res_mal_pres["index_sha256"]["status"] == HASH_STATUS_MALFORMED
    assert any(i.code == CODE_MALFORMED_HASH and i.severity == SEVERITY_ERROR for i in iss_mal_pres)

    # 4. Malformed (hash con formato corrupto/inválido: archivo ausente)
    # Debe detectarse incluso cuando el archivo original no existe
    res_mal_abs, iss_mal_abs = verify_file_hashes({"gold_sha256": "malformed_hash_456"}, base_dir=fake_base)
    assert res_mal_abs["gold_sha256"]["status"] == HASH_STATUS_MALFORMED
    assert any(i.code == CODE_MALFORMED_HASH and i.severity == SEVERITY_ERROR for i in iss_mal_abs)

    # 5. File not found (hash válido de 64 hex pero archivo no existe en disco)
    res_fnf, iss_fnf = verify_file_hashes({"gold_sha256": "b" * 64}, base_dir=fake_base)
    assert res_fnf["gold_sha256"]["status"] == HASH_STATUS_FILE_NOT_FOUND
    assert any(i.code == CODE_FILE_MISSING and i.severity == SEVERITY_WARNING for i in iss_fnf)


def test_cli_execution_paper_artifacts(tmp_path):
    """Verifica la ejecución mediante el script reproducible scripts/generate_paper_artifacts.py."""
    out_dir = tmp_path / "cli_artifacts"
    cmd = [
        sys.executable,
        "scripts/generate_paper_artifacts.py",
        "--output",
        str(out_dir),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0, f"Error en CLI: {proc.stderr}"
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "audit_report.json").exists()
    assert (out_dir / "tables/tabla01_configuracion_experimental.csv").exists()
    assert (out_dir / "figures/fig1_exactitud_abc.svg").exists()
    assert (out_dir / "figures/fig1_exactitud_abc.png").exists()

    # Validar que el manifiesto contiene los hashes de entradas y salidas
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["hashes_salidas"]) > 0
    assert len(manifest["hashes_entradas"]) > 0


def test_windows_crlf_and_gitattributes_portability(tmp_path):
    """Verifica la compatibilidad multiplataforma y normalización LF de experiments/attacks.jsonl."""
    # 1. Comprobar que .gitattributes contiene la regla para attacks.jsonl conservando reglas existentes
    gitattrs_path = Path(".gitattributes")
    assert gitattrs_path.exists(), "Falta el archivo .gitattributes en la raíz"
    content = gitattrs_path.read_text(encoding="utf-8")
    assert "experiments/attacks.jsonl text eol=lf" in content
    assert "results/normative_policy_*/validation.json text eol=lf" in content
    assert "results/llm_baseline/*.csv whitespace=-blank-at-eol" in content

    # 2. Comprobar que attacks.jsonl en disco no contiene retornos de carro CRLF
    attacks_file = Path("experiments/attacks.jsonl")
    raw_bytes = attacks_file.read_bytes()
    assert b"\r\n" not in raw_bytes, "experiments/attacks.jsonl contiene finales de línea CRLF en lugar de LF"

    # 3. Comprobar que el hash SHA-256 en disco coincide exactamente con el manifiesto histórico
    expected_hash = "4235a3263ff411ac50b3261bc5fba689768161f935cce1a42f76136293309bf7"
    computed_hash = digest(attacks_file)
    assert computed_hash == expected_hash, f"Hash discrepa: {computed_hash} != {expected_hash}"

    # 4. Simulación de checkout en Windows con core.autocrlf=true:
    # Si un archivo fuera convertido espuriamente a CRLF, la verificación criptográfica DEBE rechazarlo
    crlf_content = raw_bytes.replace(b"\n", b"\r\n")
    crlf_file = tmp_path / "attacks_crlf.jsonl"
    crlf_file.write_bytes(crlf_content)

    from cs_rag_security.evaluation.audit_experiment import _audit_single_file_hash, CODE_HASH_MISMATCH
    status_crlf, issue_crlf = _audit_single_file_hash(expected_hash, crlf_file, "attacks_sha256", "test_win")
    assert status_crlf["status"] == "mismatch"
    assert issue_crlf is not None
    assert issue_crlf.code == CODE_HASH_MISMATCH
    assert issue_crlf.severity == "error"

    # 5. Con LF (enforced por .gitattributes), la verificación criptográfica es verified
    status_lf, issue_lf = _audit_single_file_hash(expected_hash, attacks_file, "attacks_sha256", "test_win")
    assert status_lf["status"] == "verified"
    assert issue_lf is None


def test_t11_real_latencies_recalculated_dynamically(tmp_path):
    """Verifica que las latencias de T11 se recalculan dinámicamente desde trazas reales sin hardcoding."""
    traces_file = Path("results/llm_baseline/traces.json")
    assert traces_file.exists(), "Falta el archivo de trazas históricas de T11"
    traces = json.loads(traces_file.read_text(encoding="utf-8"))
    assert len(traces) == 10

    # 1. Tabla 9 construida exclusivamente desde las trazas
    t9 = build_table_latencies_and_tokens(traces=traces)
    assert t9.table_id == "tabla09_latencias_y_tokens"
    assert len(t9.rows) >= 3

    # Localizar fila de Modo A
    row_a = [r for r in t9.rows if r[0] == "A_sin_defensa"][0]
    # Consultas (n)
    assert row_a[2] == "10"
    # Latencia Pipeline Media (s): 25.2074 redondea formalmente a 25.21 s (verificando observación de León)
    assert row_a[3] == "25.21"
    # Latencia Pipeline Mediana (s)
    assert row_a[4] == "23.12"
    # Latencia LLM Media (s): 25.1924 redondea formalmente a 25.19 s (verificando observación de León)
    assert row_a[6] == "25.19"
    # Latencia LLM Mediana (s)
    assert row_a[7] == "23.11"
    # Tokens promedio dinámicos
    assert row_a[9] == "255.9"   # Prompt tokens medio
    assert row_a[10] == "201.0"  # Completion tokens medio
    assert row_a[11] == "456.9"  # Total tokens medio
    assert "qwen2.5:3b" in row_a[12]

    # Modos B y C deben reportar N/A o 0 al no contar con trazas
    row_b = [r for r in t9.rows if r[0] == "B_defensa_basica"][0]
    assert row_b[2] == "0"
    assert row_b[3] == "N/A"
    assert row_b[6] == "N/A"

    # 2. Figura 6 generada desde métricas extraídas dinámicamente
    metrics = extract_latency_and_token_metrics(traces=traces)
    svg_p, png_p = generate_fig_latencias_condicion(metrics, output_dir=tmp_path / "fig_test")
    assert svg_p.exists()
    assert png_p.exists()
    svg_text = svg_p.read_text(encoding="utf-8")
    assert "25.21 s" in svg_text
    assert "25.19 s" in svg_text
    assert "n = 10" in svg_text
    # No deben figurar las constantes antiguas
    assert "24.95 s" not in svg_text


def test_synthetic_latencies_distinct_from_t11(tmp_path):
    """Demuestra la ausencia total de constantes hardcodeadas procesando latencias sintéticas arbitrarias."""
    synth_traces = [
        {
            "id": f"SYNTH_{i}",
            "mode": "A_sin_defensa",
            "pipeline_seconds": 15.5,
            "latency_seconds": 12.0,
            "tokens": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "provider": "test_prov",
            "model": "test_model:7b",
        }
        for i in range(5)
    ]

    t9 = build_table_latencies_and_tokens(traces=synth_traces)
    row_a = [r for r in t9.rows if r[0] == "A_sin_defensa"][0]
    assert row_a[2] == "5"
    assert row_a[3] == "15.50"
    assert row_a[4] == "15.50"
    assert row_a[6] == "12.00"
    assert row_a[7] == "12.00"
    assert row_a[9] == "100.0"
    assert row_a[10] == "50.0"
    assert row_a[11] == "150.0"
    assert row_a[12] == "test_prov / test_model:7b"

    # Figura 6 con datos sintéticos
    svg_p, _ = generate_fig_latencias_condicion(extract_latency_and_token_metrics(traces=synth_traces), output_dir=tmp_path)
    svg_txt = svg_p.read_text(encoding="utf-8")
    assert "15.50 s" in svg_txt
    assert "12.00 s" in svg_txt
    assert "n = 5" in svg_txt


def test_absence_of_traces_reports_na(tmp_path):
    """Verifica que ante ausencia total de trazas, Tabla 9 y Figura 6 informan formalmente N/A."""
    t9 = build_table_latencies_and_tokens(traces=None, quality_report=None)
    for r in t9.rows:
        assert r[2] == "0"
        assert r[3] == "N/A"
        assert r[4] == "N/A"
        assert r[5] == "N/A"
        assert r[6] == "N/A"
        assert r[7] == "N/A"
        assert r[8] == "N/A"
        assert r[9] == "N/A"
        assert r[10] == "N/A"
        assert r[11] == "N/A"

    svg_p, _ = generate_fig_latencias_condicion(latencies_data=None, output_dir=tmp_path)
    svg_txt = svg_p.read_text(encoding="utf-8")
    assert "Medición Pendiente (N/A)" in svg_txt
    assert "Sin trazas disponibles (n = 0)" in svg_txt


def test_partially_available_latencies(tmp_path):
    """Verifica el comportamiento cuando solo ciertas condiciones cuentan con trazas registradas."""
    partial_traces = [
        {"id": "GQ1", "mode": "A_sin_defensa", "pipeline_seconds": 18.0, "latency_seconds": 17.5},
        {"id": "GQ2", "mode": "C_defensa_propuesta", "pipeline_seconds": 22.0, "latency_seconds": 20.0},
    ]

    t9 = build_table_latencies_and_tokens(traces=partial_traces)
    row_a = [r for r in t9.rows if r[0] == "A_sin_defensa"][0]
    row_b = [r for r in t9.rows if r[0] == "B_defensa_basica"][0]
    row_c = [r for r in t9.rows if r[0] == "C_defensa_propuesta"][0]

    assert row_a[2] == "1"
    assert row_a[3] == "18.00"
    assert row_b[2] == "0"
    assert row_b[3] == "N/A"
    assert row_c[2] == "1"
    assert row_c[3] == "22.00"


def test_incompatible_configurations_separated(tmp_path):
    """Verifica que configuraciones incompatibles en una misma condición no se promedian espuriamente."""
    incompat_traces = [
        {"id": "G1", "mode": "A_sin_defensa", "pipeline_seconds": 10.0, "latency_seconds": 9.0, "model": "qwen2.5:3b"},
        {"id": "G2", "mode": "A_sin_defensa", "pipeline_seconds": 30.0, "latency_seconds": 29.0, "model": "llama3:8b"},
    ]

    metrics = extract_latency_and_token_metrics(traces=incompat_traces)
    cond_a = metrics["por_condicion"]["A_sin_defensa"]
    assert cond_a["configuracion_compatible"] is False
    assert len(cond_a["grupos_configuracion"]) == 2

    t9 = build_table_latencies_and_tokens(traces=incompat_traces)
    # Deben existir filas separadas para cada variante
    cfg_rows = [r for r in t9.rows if "A_sin_defensa (cfg" in r[0]]
    assert len(cfg_rows) == 2
    assert cfg_rows[0][3] == "10.00"
    assert cfg_rows[1][3] == "30.00"

    # En Figura 6 se muestra advertencia de configuración incompatible
    svg_p, _ = generate_fig_latencias_condicion(metrics, output_dir=tmp_path)
    svg_txt = svg_p.read_text(encoding="utf-8")
    assert "Configuración Incompatible" in svg_txt


def test_deduplication_between_raw_and_pipeline():
    """Verifica que registros de una misma consulta con salida raw y pipeline no dupliquen latencias."""
    dup_traces = [
        {"id": "GQ001", "mode": "A_sin_defensa", "run_id": "r1", "target": "pipeline", "pipeline_seconds": 20.0, "latency_seconds": 19.0},
        {"id": "GQ001", "mode": "A_sin_defensa", "run_id": "r1", "target": "llm_raw", "pipeline_seconds": 20.0, "latency_seconds": 19.0},
    ]

    metrics = extract_latency_and_token_metrics(traces=dup_traces)
    assert metrics["unique_cases_count"] == 1
    cond_a = metrics["por_condicion"]["A_sin_defensa"]
    assert cond_a["observaciones_validas"] == 1
    assert cond_a["latencia_pipeline"]["media"] == 20.0


def test_compatibility_with_t18_citation_differentiation():
    """Verifica que Tabla 4 incluya las categorías formales de citas introducidas por T18."""
    t4 = build_table_citation_quality_validity()
    # Encabezados requeridos
    assert "Formalmente Válidas (n, %)" in t4.headers
    assert "Citas Inválidas (n, %)" in t4.headers
    assert "Ausencia de Citas (n, %)" in t4.headers
    assert "Casos Mixtos (n, %)" in t4.headers
    assert "No Determinable (n, %)" in t4.headers

    # Filas pendientes
    for r in t4.rows:
        assert r[2] == "0"
        assert r[3] == "Pendiente (0/0)"


def test_t19_figure_plots_rubric_stages_and_distinguishes_missing(tmp_path):
    metrics = {
        "proveedor": "local",
        "modelo": "fixture-llm",
        "por_condicion": {
            "A_sin_defensa": {
                "asr_raw": {"value": 0.5, "numerator": 10, "denominator": 20, "missing": 0},
                "asr_final": {"value": 0.0, "numerator": 0, "denominator": 20, "missing": 0},
            },
            "B_defensa_basica": {
                "asr_raw": {"value": None, "numerator": 0, "denominator": 20, "missing": 1},
            },
        },
    }
    svg, _ = generate_fig_asr_condicion(metrics, tmp_path)
    text = svg.read_text()
    assert "50% (10/20)" in text
    assert "0% (0/20)" in text
    assert "fixture-llm" in text
    assert text.count("N/A") == 4
