"""Pruebas unitarias para las métricas de calidad de respuestas (T18).

Verifica:
- Manejo formal de denominadores cero (sin división por cero ni valores inventados).
- No contabilización de revisiones pendientes o no evaluables como incorrectas.
- Cálculo de calidad humana de contenido (correctas, parciales, incorrectas).
- Distinción entre abstención, abstenciones adecuadas e inadecuadas.
- Validez de citas distinguiendo pertenencia al contexto de sustento factual real.
- Separación de respuestas del pipeline y salidas crudas del LLM.
- Comparación pareada entre condiciones experimentales A, B y C.
- Prioridad de filas de consenso.
- Exportación a JSON y CSV compatible con T20 y publicación científica.
"""

import csv
import json
from pathlib import Path
import pytest

from cs_rag_security.evaluation.quality import (
    EvaluationRecord,
    QualityEvaluationReport,
    compute_slice_metrics,
    evaluate_quality,
    fraction,
    load_annotations,
    resolve_consensus_records,
    TARGET_PIPELINE,
    TARGET_LLM_RAW,
)


def test_fraction_handles_zero_denominator():
    # Denominador cero debe retornar value=None y rate_percent=None
    res = fraction(0, 0, "Denominador cero")
    assert res['numerator'] == 0
    assert res['denominator'] == 0
    assert res['value'] is None
    assert res['rate_percent'] is None
    assert res['description'] == "Denominador cero"

    res_none = fraction(None, 0, "Numerador None")
    assert res_none['value'] is None
    assert res_none['rate_percent'] is None

    # Denominador positivo
    res_pos = fraction(8, 10, "8 de 10")
    assert res_pos['numerator'] == 8
    assert res_pos['denominator'] == 10
    assert res_pos['value'] == 0.8
    assert res_pos['rate_percent'] == 80.0


def test_pending_cases_not_counted_as_incorrect(tmp_path):
    # Crear un archivo CSV con solo casos pendientes
    csv_file = tmp_path / "pending_annotations.csv"
    rows = [
        {
            'evaluacion_id': 'EVAL-001', 'corrida_id': 'run1', 'caso_ciego_id': 'CIEGO_01', 'pregunta_id': 'GQ001',
            'evaluador_id': 'leon', 'rubrica_version': '0.2', 'referencia_caso': '', 'referencia_salida': 'traces.json#GQ001.response',
            'referencia_contexto': '', 'referencia_manifiesto': '', 'tipo_consulta': 'documental',
            'evidencia_disponible': '', 'estado_revision': 'pendiente', 'tipo_salida': '',
            'calidad_respuesta': '', 'abstencion_adecuada': '', 'cita_pertenece_contexto': '',
            'cita_sustenta_respuesta': '', 'error_vigencia': '', 'justificacion': '',
            'referencia_fuente': '', 'incidencia': '', 'revisado_por': '', 'fecha_revision': '',
        },
        {
            'evaluacion_id': 'EVAL-002', 'corrida_id': 'run1', 'caso_ciego_id': 'CIEGO_02', 'pregunta_id': 'GQ002',
            'evaluador_id': 'leon', 'rubrica_version': '0.2', 'referencia_caso': '', 'referencia_salida': 'traces.json#GQ002.response',
            'referencia_contexto': '', 'referencia_manifiesto': '', 'tipo_consulta': 'documental',
            'evidencia_disponible': '', 'estado_revision': 'pendiente', 'tipo_salida': '',
            'calidad_respuesta': '', 'abstencion_adecuada': '', 'cita_pertenece_contexto': '',
            'cita_sustenta_respuesta': '', 'error_vigencia': '', 'justificacion': '',
            'referencia_fuente': '', 'incidencia': '', 'revisado_por': '', 'fecha_revision': '',
        },
    ]
    with csv_file.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    report = evaluate_quality(csv_file)
    res = report.resumen_global
    acc = res['contabilidad_casos']

    assert acc['total_anotaciones'] == 2
    assert acc['casos_evaluables'] == 0
    assert acc['casos_pendientes'] == 2
    assert acc['casos_no_evaluables'] == 0

    cal = res['calidad_contenido']
    # Debe ser N/A (None), NO cero ni contabilizarse como incorrectas
    assert cal['exactitud_humana_contenido']['denominator'] == 0
    assert cal['exactitud_humana_contenido']['value'] is None
    assert cal['tasa_respuestas_incorrectas']['denominator'] == 0
    assert cal['tasa_respuestas_incorrectas']['numerator'] == 0
    assert cal['tasa_respuestas_incorrectas']['value'] is None


def test_not_evaluable_cases_excluded(tmp_path):
    records_data = [
        {
            'evaluacion_id': 'EVAL-001', 'corrida_id': 'run1', 'caso_ciego_id': 'CIEGO_01', 'pregunta_id': 'GQ001',
            'evaluador_id': 'leon', 'rubrica_version': '0.2', 'tipo_consulta': 'documental',
            'evidencia_disponible': 'sin_verificar', 'estado_revision': 'no_evaluable',
            'tipo_salida': '', 'calidad_respuesta': '',
        },
        {
            'evaluacion_id': 'EVAL-002', 'corrida_id': 'run1', 'caso_ciego_id': 'CIEGO_02', 'pregunta_id': 'GQ002',
            'evaluador_id': 'leon', 'rubrica_version': '0.2', 'tipo_consulta': 'documental',
            'evidencia_disponible': 'suficiente', 'estado_revision': 'anotado',
            'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta',
            'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa',
        },
    ]
    report = evaluate_quality(records_data)
    acc = report.resumen_global['contabilidad_casos']
    assert acc['total_anotaciones'] == 2
    assert acc['casos_evaluables'] == 1
    assert acc['casos_no_evaluables'] == 1
    assert acc['casos_pendientes'] == 0

    # Denominador de evaluables debe ser 1, no 2
    exact = report.resumen_global['calidad_contenido']['exactitud_humana_contenido']
    assert exact['numerator'] == 1
    assert exact['denominator'] == 1
    assert exact['value'] == 1.0


def test_human_quality_metrics_correct_partial_incorrect():
    # 10 casos evaluables: 5 correctas, 2 parciales, 1 incorrecta, 2 abstenciones
    data = []
    for i in range(5):
        data.append({
            'evaluacion_id': f'EVAL-{i}', 'corrida_id': 'run1', 'caso_ciego_id': f'C_{i}', 'pregunta_id': f'Q_{i}',
            'evaluador_id': 'leon', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta',
            'calidad_respuesta': 'correcta', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa',
        })
    for i in range(5, 7):
        data.append({
            'evaluacion_id': f'EVAL-{i}', 'corrida_id': 'run1', 'caso_ciego_id': f'C_{i}', 'pregunta_id': f'Q_{i}',
            'evaluador_id': 'leon', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta',
            'calidad_respuesta': 'parcial', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'parcial',
        })
    data.append({
        'evaluacion_id': 'EVAL-7', 'corrida_id': 'run1', 'caso_ciego_id': 'C_7', 'pregunta_id': 'Q_7',
        'evaluador_id': 'leon', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta',
        'calidad_respuesta': 'incorrecta', 'cita_pertenece_contexto': 'no', 'cita_sustenta_respuesta': 'ninguna',
    })
    for i in range(8, 10):
        data.append({
            'evaluacion_id': f'EVAL-{i}', 'corrida_id': 'run1', 'caso_ciego_id': f'C_{i}', 'pregunta_id': f'Q_{i}',
            'evaluador_id': 'leon', 'estado_revision': 'anotado', 'tipo_salida': 'abstencion',
            'calidad_respuesta': 'no_aplica', 'abstencion_adecuada': 'si',
        })

    report = evaluate_quality(data)
    res = report.resumen_global
    cal = res['calidad_contenido']

    # Total evaluables = 10
    assert cal['exactitud_humana_contenido']['numerator'] == 5
    assert cal['exactitud_humana_contenido']['denominator'] == 10
    assert cal['exactitud_humana_contenido']['value'] == 0.5
    assert cal['exactitud_humana_contenido']['rate_percent'] == 50.0

    assert cal['tasa_respuestas_parciales']['numerator'] == 2
    assert cal['tasa_respuestas_parciales']['denominator'] == 10
    assert cal['tasa_respuestas_parciales']['value'] == 0.2

    assert cal['tasa_respuestas_incorrectas']['numerator'] == 1
    assert cal['tasa_respuestas_incorrectas']['denominator'] == 10
    assert cal['tasa_respuestas_incorrectas']['value'] == 0.1

    assert cal['calidad_no_aplica_abstencion']['numerator'] == 2
    assert cal['calidad_no_aplica_abstencion']['denominator'] == 10
    assert cal['calidad_no_aplica_abstencion']['value'] == 0.2

    # Restringido a respuestas sustantivas (denominador = 8)
    assert cal['correctas_sobre_respuestas_sustantivas']['numerator'] == 5
    assert cal['correctas_sobre_respuestas_sustantivas']['denominator'] == 8
    assert cal['correctas_sobre_respuestas_sustantivas']['value'] == 0.625


def test_abstention_and_adequacy_distinction():
    # 4 consultas: 2 respuestas, 2 abstenciones (1 adecuada, 1 inadecuada)
    data = [
        {'evaluacion_id': '1', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa'},
        {'evaluacion_id': '2', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'incorrecta', 'cita_pertenece_contexto': 'no', 'cita_sustenta_respuesta': 'ninguna'},
        {'evaluacion_id': '3', 'estado_revision': 'anotado', 'tipo_salida': 'abstencion', 'calidad_respuesta': 'no_aplica', 'abstencion_adecuada': 'si'},
        {'evaluacion_id': '4', 'estado_revision': 'anotado', 'tipo_salida': 'abstencion', 'calidad_respuesta': 'no_aplica', 'abstencion_adecuada': 'no'},
    ]
    report = evaluate_quality(data)
    abst = report.resumen_global['abstencion_y_adecuacion']

    # Tasa abstención sobre total (2/4)
    assert abst['tasa_abstencion']['numerator'] == 2
    assert abst['tasa_abstencion']['denominator'] == 4
    assert abst['tasa_abstencion']['value'] == 0.5

    # Adecuación sobre abstenciones evaluables (1 de 2 adecuadas, 1 de 2 inadecuadas)
    assert abst['adecuacion_abstenciones']['numerator'] == 1
    assert abst['adecuacion_abstenciones']['denominator'] == 2
    assert abst['adecuacion_abstenciones']['value'] == 0.5

    assert abst['tasa_abstenciones_inadecuadas']['numerator'] == 1
    assert abst['tasa_abstenciones_inadecuadas']['denominator'] == 2
    assert abst['tasa_abstenciones_inadecuadas']['value'] == 0.5

    # Adecuación sobre total de consultas
    assert abst['abstenciones_adecuadas_sobre_total_consultas']['numerator'] == 1
    assert abst['abstenciones_adecuadas_sobre_total_consultas']['denominator'] == 4
    assert abst['abstenciones_adecuadas_sobre_total_consultas']['value'] == 0.25


def test_citations_validity_belonging_vs_grounding():
    # 4 respuestas sustantivas:
    # Caso 1: Cita pertenece Y sustenta completo (válida completa)
    # Caso 2: Cita pertenece pero sustento parcial (brecha pertenencia vs sustento)
    # Caso 3: Cita pertenece pero sustento ninguno (brecha pertenencia vs sustento)
    # Caso 4: Cita NO pertenece al contexto (alucinación)
    data = [
        {'evaluacion_id': '1', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa'},
        {'evaluacion_id': '2', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'parcial', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'parcial'},
        {'evaluacion_id': '3', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'incorrecta', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'ninguna'},
        {'evaluacion_id': '4', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'incorrecta', 'cita_pertenece_contexto': 'no', 'cita_sustenta_respuesta': 'ninguna'},
    ]
    report = evaluate_quality(data)
    cit = report.resumen_global['validez_y_sustento_citas']

    # Citas válidas completas (1 de 4)
    assert cit['citas_validas_completas']['numerator'] == 1
    assert cit['citas_validas_completas']['denominator'] == 4
    assert cit['citas_validas_completas']['value'] == 0.25

    # Pertenencia al contexto: 3 pertenecen ('si'), 1 no ('no')
    pert = cit['pertenencia_contexto']
    assert pert['citas_pertenecen_si']['numerator'] == 3
    assert pert['citas_pertenecen_si']['denominator'] == 4
    assert pert['citas_pertenecen_no']['numerator'] == 1
    assert pert['citas_pertenecen_no']['denominator'] == 4

    # Sustento factual: 1 completa, 1 parcial, 2 ninguna
    sust = cit['sustento_factual']
    assert sust['sustento_completo']['numerator'] == 1
    assert sust['sustento_completo']['denominator'] == 4
    assert sust['sustento_parcial']['numerator'] == 1
    assert sust['sustento_parcial']['denominator'] == 4
    assert sust['sustento_ninguno']['numerator'] == 2
    assert sust['sustento_ninguno']['denominator'] == 4

    # Brecha: pertenencia formal vs sustento real (2 casos: uno parcial y uno nulo)
    brecha = cit['brecha_pertenencia_sin_sustento']
    assert brecha['pertenecen_pero_sustento_parcial']['numerator'] == 1
    assert brecha['pertenecen_pero_sustento_nulo']['numerator'] == 1
    assert brecha['total_pertenecen_sin_sustento_completo']['numerator'] == 2
    assert brecha['total_pertenecen_sin_sustento_completo']['denominator'] == 4
    assert brecha['total_pertenecen_sin_sustento_completo']['value'] == 0.5


def test_pipeline_vs_llm_raw_separation():
    # 2 preguntas con respuestas pareadas pipeline vs llm_raw
    # Q1: LLM respondió correctamente pero sin cita [demo.pdf p. 1]; pipeline se abstuvo por citas ausentes
    # Q2: LLM respondió con alucinación de cita; pipeline se abstuvo
    data = [
        # Q1
        {'evaluacion_id': 'EVAL-001-pipeline', 'pregunta_id': 'GQ001', 'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'abstencion', 'calidad_respuesta': 'no_aplica', 'abstencion_adecuada': 'si'},
        {'evaluacion_id': 'EVAL-001-llm-raw', 'pregunta_id': 'GQ001', 'target': 'llm_raw', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta', 'cita_pertenece_contexto': 'sin_citas', 'cita_sustenta_respuesta': 'sin_citas'},
        # Q2
        {'evaluacion_id': 'EVAL-002-pipeline', 'pregunta_id': 'GQ002', 'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'abstencion', 'calidad_respuesta': 'no_aplica', 'abstencion_adecuada': 'si'},
        {'evaluacion_id': 'EVAL-002-llm-raw', 'pregunta_id': 'GQ002', 'target': 'llm_raw', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'incorrecta', 'cita_pertenece_contexto': 'no', 'cita_sustenta_respuesta': 'ninguna'},
    ]
    report = evaluate_quality(data)

    pipe_slice = report.por_origen_respuesta[TARGET_PIPELINE]
    raw_slice = report.por_origen_respuesta[TARGET_LLM_RAW]

    # Pipeline: 100% abstención, 0% exactitud humana
    assert pipe_slice['abstencion_y_adecuacion']['tasa_abstencion']['value'] == 1.0
    assert pipe_slice['calidad_contenido']['exactitud_humana_contenido']['value'] == 0.0

    # LLM Raw: 0% abstención, 50% exactitud humana
    assert raw_slice['abstencion_y_adecuacion']['tasa_abstencion']['value'] == 0.0
    assert raw_slice['calidad_contenido']['exactitud_humana_contenido']['value'] == 0.5

    # Emparejamiento
    emp = report.emparejamiento_pipeline_vs_llm
    assert emp['pares_evaluables'] == 2
    assert emp['llm_correcto_pero_pipeline_abstuvo']['numerator'] == 1
    assert emp['llm_sustantivo_pero_pipeline_abstuvo']['numerator'] == 2


def test_abc_conditions_comparison():
    # 3 condiciones: A (baseline sin defensa), B (básica), C (propuesta)
    data = [
        {'evaluacion_id': 'A1', 'condicion': 'A_sin_defensa', 'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'abstencion', 'calidad_respuesta': 'no_aplica', 'abstencion_adecuada': 'si'},
        {'evaluacion_id': 'B1', 'condicion': 'B_defensa_basica', 'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'parcial', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'parcial'},
        {'evaluacion_id': 'C1', 'condicion': 'C_defensa_propuesta', 'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa'},
    ]
    report = evaluate_quality(data)

    assert 'A_sin_defensa' in report.por_condicion
    assert 'B_defensa_basica' in report.por_condicion
    assert 'C_defensa_propuesta' in report.por_condicion

    cond_a = report.por_condicion['A_sin_defensa']
    cond_b = report.por_condicion['B_defensa_basica']
    cond_c = report.por_condicion['C_defensa_propuesta']

    assert cond_a['abstencion_y_adecuacion']['tasa_abstencion']['value'] == 1.0
    assert cond_b['calidad_contenido']['tasa_respuestas_parciales']['value'] == 1.0
    assert cond_c['calidad_contenido']['exactitud_humana_contenido']['value'] == 1.0

    # Tabla comparativa estilo artículo
    table = report.to_comparison_table_csv(TARGET_PIPELINE)
    assert len(table) > 0
    row_exact = next(r for r in table if 'Exactitud humana' in r['metrica'])
    assert row_exact['A_sin_defensa'] == "0.0% (0/1)"
    assert row_exact['B_defensa_basica'] == "0.0% (0/1)"
    assert row_exact['C_defensa_propuesta'] == "100.0% (1/1)"


def test_consensus_resolution_priority():
    # Mismo caso anotado por León y Romina con discrepancia, resuelto en fila consensuada
    records_data = [
        {
            'evaluacion_id': 'EVAL-001-leon', 'corrida_id': 'run1', 'caso_ciego_id': 'CIEGO_01', 'target': 'pipeline',
            'evaluador_id': 'leon', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta',
            'calidad_respuesta': 'correcta', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa',
        },
        {
            'evaluacion_id': 'EVAL-001-romina', 'corrida_id': 'run1', 'caso_ciego_id': 'CIEGO_01', 'target': 'pipeline',
            'evaluador_id': 'romina', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta',
            'calidad_respuesta': 'parcial', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'parcial',
        },
        {
            'evaluacion_id': 'EVAL-001-consenso', 'corrida_id': 'run1', 'caso_ciego_id': 'CIEGO_01', 'target': 'pipeline',
            'evaluador_id': 'consenso', 'estado_revision': 'consensuado', 'tipo_salida': 'respuesta',
            'calidad_respuesta': 'correcta', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa',
        },
    ]

    report = evaluate_quality(records_data, resolve_consensus=True)
    # Debe haber deduplicado al caso de consenso (1 caso evaluable)
    acc = report.resumen_global['contabilidad_casos']
    assert acc['total_anotaciones'] == 1
    assert acc['casos_evaluables'] == 1
    assert report.resumen_global['calidad_contenido']['exactitud_humana_contenido']['value'] == 1.0


def test_export_json_and_csv(tmp_path):
    data = [
        {'evaluacion_id': '1', 'condicion': 'A_sin_defensa', 'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'abstencion', 'calidad_respuesta': 'no_aplica', 'abstencion_adecuada': 'si'},
        {'evaluacion_id': '2', 'condicion': 'C_defensa_propuesta', 'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa'},
    ]
    report = evaluate_quality(data)

    json_path = tmp_path / "metrics.json"
    csv_path = tmp_path / "metrics.csv"
    comp_csv_path = tmp_path / "summary_comp.csv"

    report.save_json(json_path)
    report.save_csv(csv_path)
    report.save_comparison_csv(comp_csv_path)

    assert json_path.exists()
    assert csv_path.exists()
    assert comp_csv_path.exists()

    # Verificar que el JSON carga y contiene las claves esperadas
    loaded_json = json.loads(json_path.read_text(encoding='utf-8'))
    assert 'manifest' in loaded_json
    assert 'resumen_global' in loaded_json
    assert 'por_condicion' in loaded_json

    # Verificar que el CSV contiene las 9 columnas estándar
    with csv_path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        assert set(reader.fieldnames) == {'condicion', 'origen_respuesta', 'categoria', 'metrica', 'numerador', 'denominador', 'valor', 'porcentaje', 'descripcion'}
        rows = list(reader)
        assert len(rows) > 0

    # Verificar que la tabla comparativa horizontal tiene columnas A, B, C
    with comp_csv_path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        assert 'metrica' in reader.fieldnames
        assert 'A_sin_defensa' in reader.fieldnames
        assert 'B_defensa_basica' in reader.fieldnames
        assert 'C_defensa_propuesta' in reader.fieldnames


def test_existing_t12_pending_csv_handled_safely():
    # Prueba de integración con el archivo real local de T12
    t12_csv = Path('results/t12_evaluacion/t12_evaluacion_ciega.csv')
    if not t12_csv.exists():
        pytest.skip("results/t12_evaluacion/t12_evaluacion_ciega.csv no existe en este entorno")

    report = evaluate_quality(t12_csv)
    acc = report.resumen_global['contabilidad_casos']
    assert acc['total_anotaciones'] == 20
    assert acc['casos_evaluables'] == 0
    assert acc['casos_pendientes'] == 20
    assert acc['casos_no_evaluables'] == 0

    # Ninguna tasa debe dar error ni inventar respuestas incorrectas
    cal = report.resumen_global['calidad_contenido']
    assert cal['exactitud_humana_contenido']['denominator'] == 0
    assert cal['exactitud_humana_contenido']['value'] is None
    assert cal['tasa_respuestas_incorrectas']['denominator'] == 0
    assert cal['tasa_respuestas_incorrectas']['value'] is None


def test_empty_dataset_handling():
    report = evaluate_quality([])
    acc = report.resumen_global['contabilidad_casos']
    assert acc['total_anotaciones'] == 0
    assert acc['casos_evaluables'] == 0
    assert acc['casos_pendientes'] == 0
    assert acc['casos_no_evaluables'] == 0


def test_normative_error_tracking():
    data = [
        {'evaluacion_id': '1', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'incorrecta', 'error_vigencia': 'si', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'parcial'},
        {'evaluacion_id': '2', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta', 'error_vigencia': 'no', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa'},
    ]
    report = evaluate_quality(data)
    vig = report.resumen_global['validez_y_sustento_citas']['errores_vigencia']
    assert vig['sobre_respuestas_sustantivas']['numerator'] == 1
    assert vig['sobre_respuestas_sustantivas']['denominator'] == 2
    assert vig['sobre_respuestas_sustantivas']['value'] == 0.5


def test_blind_mapping_dict_and_file(tmp_path):
    data = [
        {'evaluacion_id': '1', 'caso_ciego_id': 'C_01', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa'},
        {'evaluacion_id': '2', 'caso_ciego_id': 'C_02', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'incorrecta', 'cita_pertenece_contexto': 'no', 'cita_sustenta_respuesta': 'ninguna'},
    ]
    mapping = {
        'C_01': {'condicion': 'A_sin_defensa', 'target': 'pipeline'},
        'C_02': {'condicion': 'B_defensa_basica', 'target': 'llm_raw'},
    }
    mapping_file = tmp_path / "blind_map.json"
    mapping_file.write_text(json.dumps(mapping), encoding='utf-8')

    report = evaluate_quality(data, blind_mapping=mapping_file)
    assert 'A_sin_defensa' in report.por_condicion
    assert 'B_defensa_basica' in report.por_condicion
    assert report.cruzado_condicion_origen['A_sin_defensa']['pipeline']['calidad_contenido']['exactitud_humana_contenido']['value'] == 1.0
    assert report.cruzado_condicion_origen['B_defensa_basica']['llm_raw']['calidad_contenido']['exactitud_humana_contenido']['value'] == 0.0


def test_cli_quality_command(tmp_path, monkeypatch):
    import sys
    from cs_rag_security.cli import main

    csv_file = tmp_path / "cli_test_annotations.csv"
    rows = [
        {
            'evaluacion_id': 'EVAL-001', 'corrida_id': 'run1', 'caso_ciego_id': 'CIEGO_01', 'pregunta_id': 'GQ001',
            'evaluador_id': 'leon', 'rubrica_version': '0.2', 'referencia_caso': '', 'referencia_salida': 'traces.json#GQ001.response',
            'referencia_contexto': '', 'referencia_manifiesto': '', 'tipo_consulta': 'documental',
            'evidencia_disponible': 'suficiente', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta',
            'calidad_respuesta': 'correcta', 'abstencion_adecuada': '', 'cita_pertenece_contexto': 'si',
            'cita_sustenta_respuesta': 'completa', 'error_vigencia': 'no', 'justificacion': '',
            'referencia_fuente': '', 'incidencia': '', 'revisado_por': '', 'fecha_revision': '',
        }
    ]
    with csv_file.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    out_dir = tmp_path / "cli_output"
    test_args = ['cli.py', 'quality', '--annotations', str(csv_file), '--output', str(out_dir)]
    monkeypatch.setattr(sys, 'argv', test_args)

    main()

    assert (out_dir / 'quality_metrics.json').exists()
    assert (out_dir / 'quality_metrics.csv').exists()
    assert (out_dir / 'quality_summary_comparison.csv').exists()

    loaded = json.loads((out_dir / 'quality_metrics.json').read_text(encoding='utf-8'))
    assert loaded['resumen_global']['contabilidad_casos']['casos_evaluables'] == 1


def test_unresolved_disagreement_recorded_as_conflict_not_arbitrary():
    # León dice 'correcta', Romina dice 'incorrecta', no hay fila de consenso
    records_data = [
        {
            'evaluacion_id': 'EVAL-001-leon', 'corrida_id': 'run1', 'caso_ciego_id': 'CIEGO_01', 'target': 'pipeline',
            'evaluador_id': 'leon', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta',
            'calidad_respuesta': 'correcta', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa',
        },
        {
            'evaluacion_id': 'EVAL-001-romina', 'corrida_id': 'run1', 'caso_ciego_id': 'CIEGO_01', 'target': 'pipeline',
            'evaluador_id': 'romina', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta',
            'calidad_respuesta': 'incorrecta', 'cita_pertenece_contexto': 'no', 'cita_sustenta_respuesta': 'ninguna',
        },
    ]

    report = evaluate_quality(records_data, resolve_consensus=True)
    # No debe resolverse arbitrariamente; debe registrarse en desacuerdos_sin_consenso
    assert len(report.desacuerdos_sin_consenso) == 1
    conflict = report.desacuerdos_sin_consenso[0]
    assert conflict['caso_id'] == 'CIEGO_01'
    assert set(conflict['evaluadores']) == {'leon', 'romina'}

    # El caso debe permanecer como pendiente (no evaluable todavía), sin computarse como correcta ni incorrecta
    acc = report.resumen_global['contabilidad_casos']
    assert acc['casos_evaluables'] == 0
    assert acc['casos_pendientes'] == 1
    cal = report.resumen_global['calidad_contenido']
    assert cal['exactitud_humana_contenido']['denominator'] == 0
    assert cal['tasa_respuestas_incorrectas']['denominator'] == 0


def test_paired_condition_comparison_uses_only_common_evaluable_cases():
    # Corrida run1:
    # Caso 1: evaluable en A (abstención) y en B (parcial)
    # Caso 2: evaluable en A (abstención) pero en B está 'pendiente'
    # La comparación pareada B vs A debe considerar ÚNICAMENTE Caso 1
    data = [
        {'evaluacion_id': 'A1', 'corrida_id': 'run1', 'caso_ciego_id': 'C_01', 'condicion': 'A_sin_defensa', 'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'abstencion', 'calidad_respuesta': 'no_aplica', 'abstencion_adecuada': 'si'},
        {'evaluacion_id': 'B1', 'corrida_id': 'run1', 'caso_ciego_id': 'C_01', 'condicion': 'B_defensa_basica', 'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'parcial', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'parcial'},

        {'evaluacion_id': 'A2', 'corrida_id': 'run1', 'caso_ciego_id': 'C_02', 'condicion': 'A_sin_defensa', 'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'abstencion', 'calidad_respuesta': 'no_aplica', 'abstencion_adecuada': 'si'},
        {'evaluacion_id': 'B2', 'corrida_id': 'run1', 'caso_ciego_id': 'C_02', 'condicion': 'B_defensa_basica', 'target': 'pipeline', 'estado_revision': 'pendiente', 'tipo_salida': '', 'calidad_respuesta': ''},
    ]

    report = evaluate_quality(data)
    paired = report.comparacion_condiciones['B_vs_A_pareado']

    # Total casos comunes evaluables debe ser 1 (C_01), no 2
    assert paired['total_casos_comunes_evaluables'] == 1
    assert paired['por_corrida']['run1']['casos_comunes_ids'] == ['C_01']
    assert paired['por_corrida']['run1']['casos_solo_en_y'] == ['C_02']  # Estaba en A pero no en B

    # Métricas pareadas calculadas sobre el caso común
    slice_a = paired['metricas_condicion_y']  # A
    slice_b = paired['metricas_condicion_x']  # B
    assert slice_a['contabilidad_casos']['casos_evaluables'] == 1
    assert slice_b['contabilidad_casos']['casos_evaluables'] == 1


def test_citation_abstention_diagnostic_grounded_in_t16():
    # Caso 1: pipeline abstuvo con motivo T16 'citas_invalidas_o_ausentes'
    # Caso 2: pipeline abstuvo por 'evidencia_insuficiente_o_no_fiable' (no por citas)
    data = [
        # Caso 1
        {'evaluacion_id': 'p1', 'pregunta_id': 'Q1', 'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'abstencion', 'calidad_respuesta': 'no_aplica', 'motivo_abstencion': 'citas_invalidas_o_ausentes'},
        {'evaluacion_id': 'r1', 'pregunta_id': 'Q1', 'target': 'llm_raw', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa'},
        # Caso 2
        {'evaluacion_id': 'p2', 'pregunta_id': 'Q2', 'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'abstencion', 'calidad_respuesta': 'no_aplica', 'motivo_abstencion': 'evidencia_insuficiente_o_no_fiable'},
        {'evaluacion_id': 'r2', 'pregunta_id': 'Q2', 'target': 'llm_raw', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa'},
    ]

    report = evaluate_quality(data)
    emp = report.emparejamiento_pipeline_vs_llm

    assert emp['pares_evaluables'] == 2
    # En ambos el LLM fue correcto y el pipeline abstuvo
    assert emp['llm_correcto_pero_pipeline_abstuvo']['numerator'] == 2
    # Pero solo en 1 la abstención obedeció formalmente al motivo T16 citas_invalidas_o_ausentes
    assert emp['llm_correcto_pero_pipeline_abstuvo_por_citas_t16']['numerator'] == 1
    assert emp['llm_correcto_pero_pipeline_abstuvo_por_citas_t16']['denominator'] == 2


def test_incomplete_annotation_treated_as_pending():
    # Rúbrica v0.2: campos esenciales vacíos conservan el estado pendiente
    data = [
        {
            'evaluacion_id': 'E1', 'pregunta_id': 'Q1', 'estado_revision': 'anotado',
            'tipo_salida': 'respuesta', 'calidad_respuesta': '',  # Incompleto
        },
        {
            'evaluacion_id': 'E2', 'pregunta_id': 'Q2', 'estado_revision': 'anotado',
            'tipo_salida': '', 'calidad_respuesta': 'correcta',  # Incompleto
        },
        {
            'evaluacion_id': 'E3', 'pregunta_id': 'Q3', 'estado_revision': 'anotado',
            'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta',  # Completo
        },
    ]
    report = evaluate_quality(data)
    acc = report.resumen_global['contabilidad_casos']
    assert acc['total_anotaciones'] == 3
    assert acc['casos_evaluables'] == 1
    assert acc['casos_pendientes'] == 2
    assert acc['casos_no_evaluables'] == 0


def test_paired_comparison_matches_by_pregunta_id_across_different_blind_codes():
    # Caso cegado donde A tiene CIEGO_01 y B tiene CIEGO_12 pero ambos corresponden a GQ004
    data = [
        {
            'evaluacion_id': 'A1', 'corrida_id': 'run1', 'caso_ciego_id': 'CIEGO_01', 'pregunta_id': 'GQ004',
            'condicion': 'A_sin_defensa', 'target': 'pipeline', 'estado_revision': 'anotado',
            'tipo_salida': 'abstencion', 'calidad_respuesta': 'no_aplica', 'abstencion_adecuada': 'si',
        },
        {
            'evaluacion_id': 'B1', 'corrida_id': 'run1', 'caso_ciego_id': 'CIEGO_12', 'pregunta_id': 'GQ004',
            'condicion': 'B_defensa_basica', 'target': 'pipeline', 'estado_revision': 'anotado',
            'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta',
            'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa',
        },
    ]
    report = evaluate_quality(data)
    paired = report.comparacion_condiciones['B_vs_A_pareado']
    assert paired['total_casos_comunes_evaluables'] == 1
    assert paired['por_corrida']['run1']['casos_comunes_ids'] == ['GQ004']


def test_abstention_grounded_in_traces_source(tmp_path):
    traces_file = tmp_path / "traces.json"
    traces_data = [
        {
            'id': 'GQ004',
            'abstained': True,
            'abstention_reason': 'citas_invalidas_o_ausentes',
        },
    ]
    traces_file.write_text(json.dumps(traces_data), encoding='utf-8')

    # Anotación sin motivo_abstencion explícito
    data = [
        {
            'evaluacion_id': 'p1', 'pregunta_id': 'GQ004', 'target': 'pipeline',
            'estado_revision': 'anotado', 'tipo_salida': 'abstencion', 'calidad_respuesta': 'no_aplica',
        },
        {
            'evaluacion_id': 'r1', 'pregunta_id': 'GQ004', 'target': 'llm_raw',
            'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta',
            'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa',
        },
    ]

    report = evaluate_quality(data, traces_source=traces_file)
    emp = report.emparejamiento_pipeline_vs_llm
    assert emp['llm_correcto_pero_pipeline_abstuvo_por_citas_t16']['numerator'] == 1
    assert emp['llm_correcto_pero_pipeline_abstuvo_por_citas_t16']['denominator'] == 1


def test_question_across_three_conditions_abc_produces_three_pairs_and_six_records():
    """Una pregunta evaluada en A/B/C debe producir tres pares independientes de salida original

    y salida final, es decir, seis registros y 3 pares de comparación evaluables.
    """
    data = [
        # Condición A: pipeline se abstiene, llm_raw responde
        {'evaluacion_id': 'e1_p', 'corrida_id': 'run_exp', 'pregunta_id': 'GQ001', 'condicion': 'A_sin_defensa', 'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'abstencion', 'calidad_respuesta': 'no_aplica', 'abstencion_adecuada': 'si'},
        {'evaluacion_id': 'e1_r', 'corrida_id': 'run_exp', 'pregunta_id': 'GQ001', 'condicion': 'A_sin_defensa', 'target': 'llm_raw', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa'},
        # Condición B: pipeline se abstiene, llm_raw responde
        {'evaluacion_id': 'e2_p', 'corrida_id': 'run_exp', 'pregunta_id': 'GQ001', 'condicion': 'B_defensa_basica', 'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'abstencion', 'calidad_respuesta': 'no_aplica', 'abstencion_adecuada': 'si'},
        {'evaluacion_id': 'e2_r', 'corrida_id': 'run_exp', 'pregunta_id': 'GQ001', 'condicion': 'B_defensa_basica', 'target': 'llm_raw', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'parcial', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'parcial'},
        # Condición C: pipeline responde, llm_raw responde
        {'evaluacion_id': 'e3_p', 'corrida_id': 'run_exp', 'pregunta_id': 'GQ001', 'condicion': 'C_defensa_propuesta', 'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa'},
        {'evaluacion_id': 'e3_r', 'corrida_id': 'run_exp', 'pregunta_id': 'GQ001', 'condicion': 'C_defensa_propuesta', 'target': 'llm_raw', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa'},
    ]

    report = evaluate_quality(data)
    assert report.manifest['total_anotaciones_cargadas'] == 6
    assert report.manifest['total_anotaciones_analizadas'] == 6

    # Emparejamiento pipeline vs raw debe arrojar 3 pares independientes
    emp = report.emparejamiento_pipeline_vs_llm
    assert emp['pares_evaluables'] == 3

    # En A y B el pipeline se abstuvo con LLM raw sustantivo; en C ambos respondieron sustantivamente
    assert emp['llm_sustantivo_pero_pipeline_abstuvo']['numerator'] == 2
    assert emp['llm_sustantivo_pero_pipeline_abstuvo']['denominator'] == 3


def test_abstention_reasons_per_condition_do_not_overwrite():
    """Impide que los motivos de abstención de una condición sobrescriban los de otra."""
    traces_data = [
        {'run_id': 'run1', 'case_id': 'GQ002', 'mode': 'A_sin_defensa', 'abstained': True, 'abstention_reason': 'evidencia_insuficiente_o_no_fiable'},
        {'run_id': 'run1', 'case_id': 'GQ002', 'mode': 'B_defensa_basica', 'abstained': True, 'abstention_reason': 'citas_invalidas_o_ausentes', 'citations_count': 0},
        {'run_id': 'run1', 'case_id': 'GQ002', 'mode': 'C_defensa_propuesta', 'abstained': False, 'abstention_reason': ''},
    ]

    # Evaluaciones sin motivo explícito, que deben nutrirse de las trazas de T16
    ann_data = [
        {'evaluacion_id': 'eA', 'corrida_id': 'run1', 'pregunta_id': 'GQ002', 'condicion': 'A_sin_defensa', 'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'abstencion', 'calidad_respuesta': 'no_aplica'},
        {'evaluacion_id': 'eB', 'corrida_id': 'run1', 'pregunta_id': 'GQ002', 'condicion': 'B_defensa_basica', 'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'abstencion', 'calidad_respuesta': 'no_aplica'},
        {'evaluacion_id': 'eC', 'corrida_id': 'run1', 'pregunta_id': 'GQ002', 'condicion': 'C_defensa_propuesta', 'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa'},
    ]

    recs = load_annotations(ann_data, traces_source=traces_data)
    by_cond = {r.condicion: r for r in recs}

    assert by_cond['A_sin_defensa'].motivo_abstencion == 'evidencia_insuficiente_o_no_fiable'
    assert by_cond['B_defensa_basica'].motivo_abstencion == 'citas_invalidas_o_ausentes'
    assert by_cond['C_defensa_propuesta'].motivo_abstencion == ''


def test_same_question_across_different_runs_preserved():
    """Preguntas iguales en corridas diferentes no colisionan."""
    data = [
        {'evaluacion_id': 'e_r1', 'corrida_id': 'corrida_alpha', 'pregunta_id': 'GQ003', 'condicion': 'C_defensa_propuesta', 'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa'},
        {'evaluacion_id': 'e_r2', 'corrida_id': 'corrida_beta', 'pregunta_id': 'GQ003', 'condicion': 'C_defensa_propuesta', 'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'abstencion', 'calidad_respuesta': 'no_aplica', 'abstencion_adecuada': 'si'},
    ]

    report = evaluate_quality(data, resolve_consensus=True)
    # Deben conservarse ambos registros independientes al pertenecer a corridas diferentes
    assert report.manifest['total_anotaciones_analizadas'] == 2
    assert len(report.desacuerdos_sin_consenso) == 0


def test_citation_differentiation_categories_and_indeterminate():
    """Diferencia explícitamente ausencia de citas, inválidas, formalmente válidas,

    casos mixtos y no determinable (sin asumir citas inválidas ante información histórica incompleta).
    """
    # 5 respuestas sustantivas con diferentes naturalezas de citación
    recs_data = [
        # 1. Ausencia de citas
        {'evaluacion_id': 'c1', 'pregunta_id': 'Q1', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta', 'cita_pertenece_contexto': 'sin_citas', 'cita_sustenta_respuesta': 'sin_citas', 'estado_revision': 'anotado'},
        # 2. Citas presentes pero formalmente inválidas (fuera de fragmentos aceptados)
        {'evaluacion_id': 'c2', 'pregunta_id': 'Q2', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'incorrecta', 'cita_pertenece_contexto': 'no', 'cita_sustenta_respuesta': 'ninguna', 'estado_revision': 'anotado'},
        # 3. Citas formalmente válidas (en contexto y válidas)
        {'evaluacion_id': 'c3', 'pregunta_id': 'Q3', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta', 'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa', 'estado_revision': 'anotado'},
        # 4. Caso mixto enriquecido por telemetría T16 (3 citas: 2 válidas, 1 inválida)
        {'evaluacion_id': 'c4', 'pregunta_id': 'Q4', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'parcial', 'cita_pertenece_contexto': 'no', 'cita_sustenta_respuesta': 'parcial', 'citations_count': 3, 'citations_invalid_count': 1, 'estado_revision': 'anotado'},
        # 5. Información histórica T11 con 'citas_invalidas_o_ausentes' sin conteos de citas -> no determinable
        {'evaluacion_id': 'c5', 'pregunta_id': 'Q5', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'parcial', 'motivo_abstencion': 'citas_invalidas_o_ausentes', 'estado_revision': 'anotado'},
    ]

    report = evaluate_quality(recs_data)
    cit_dif = report.resumen_global['validez_y_sustento_citas']['diferenciacion_citas']

    # Denominador de respuestas sustantivas es 5
    assert cit_dif['ausencia_citas']['numerator'] == 1
    assert cit_dif['ausencia_citas']['denominator'] == 5

    assert cit_dif['citas_presentes_invalidas']['numerator'] == 1
    assert cit_dif['citas_presentes_invalidas']['denominator'] == 5

    assert cit_dif['citas_formalmente_validas']['numerator'] == 1
    assert cit_dif['citas_formalmente_validas']['denominator'] == 5

    assert cit_dif['casos_mixtos']['numerator'] == 1
    assert cit_dif['casos_mixtos']['denominator'] == 5

    assert cit_dif['no_determinable']['numerator'] == 1
    assert cit_dif['no_determinable']['denominator'] == 5


def test_latency_metrics_mean_median_p95_and_documentation():
    """Calcula media, mediana y percentil 95 con método documentado de interpolación lineal."""
    # 20 observaciones ordenadas de 1.0 a 20.0
    lats = [float(i) for i in range(1, 21)]
    from cs_rag_security.evaluation.quality import compute_latency_summary

    res = compute_latency_summary(lats, "Latencias de prueba")
    assert res['observaciones_validas'] == 20
    assert res['media'] == 10.5
    assert res['mediana'] == 10.5
    # En 20 observaciones (índices 0 a 19): rank = 0.95 * 19 = 18.05 -> x[18] + 0.05 * (x[19] - x[18]) = 19.0 + 0.05 = 19.05
    assert res['percentil_95'] == 19.05


def test_latency_missing_negative_non_finite_excluded_not_zero():
    """Excluye valores ausentes, negativos o no finitos sin reemplazarlos por cero."""
    import math
    from cs_rag_security.evaluation.quality import compute_latency_summary

    raw_values = [None, '', -5.0, math.nan, math.inf, -math.inf, 2.0, 4.0]
    res = compute_latency_summary(raw_values, "Latencias con anomalías")

    # Sólo 2.0 y 4.0 son válidas
    assert res['observaciones_validas'] == 2
    assert res['media'] == 3.0
    assert res['mediana'] == 3.0
    assert res['percentil_95'] == 3.9  # 2.0 + 0.95 * (4.0 - 2.0) = 3.9


def test_latency_no_duplication_between_pipeline_and_raw():
    """No duplica latencias al contabilizar las salidas raw y pipeline de un mismo caso."""
    data = [
        # Caso GQ010 en condición C con registros para pipeline y llm_raw
        {
            'evaluacion_id': 'e_pipe', 'corrida_id': 'run_lat', 'pregunta_id': 'GQ010', 'condicion': 'C_defensa_propuesta',
            'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta',
            'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa',
            'latency_pipeline_seconds': 1.5, 'latency_generation_seconds': 0.9,
        },
        {
            'evaluacion_id': 'e_raw', 'corrida_id': 'run_lat', 'pregunta_id': 'GQ010', 'condicion': 'C_defensa_propuesta',
            'target': 'llm_raw', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta',
            'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa',
            'latency_pipeline_seconds': 1.5, 'latency_generation_seconds': 0.9,
        },
    ]

    report = evaluate_quality(data)
    lat_cond = report.metricas_latencia['por_condicion']['C_defensa_propuesta']

    # La observación debe ser 1 (un solo caso experimental), jamás duplicada a 2
    assert lat_cond['latencia_pipeline']['observaciones_validas'] == 1
    assert lat_cond['latencia_pipeline']['media'] == 1.5
    assert lat_cond['latencia_generacion']['observaciones_validas'] == 1
    assert lat_cond['latencia_generacion']['media'] == 0.9


def test_t20_aggregated_reports_and_csv_generation(tmp_path):
    """Verifica exportación completa y limpia de reportes agregados para T20."""
    data = [
        {
            'evaluacion_id': 'A1', 'corrida_id': 'run_t20', 'pregunta_id': 'GQ001', 'condicion': 'A_sin_defensa',
            'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta',
            'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa',
            'latency_pipeline_seconds': 1.1, 'latency_generation_seconds': 0.8,
        },
        {
            'evaluacion_id': 'B1', 'corrida_id': 'run_t20', 'pregunta_id': 'GQ001', 'condicion': 'B_defensa_basica',
            'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta',
            'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa',
            'latency_pipeline_seconds': 1.3, 'latency_generation_seconds': 0.85,
        },
        {
            'evaluacion_id': 'C1', 'corrida_id': 'run_t20', 'pregunta_id': 'GQ001', 'condicion': 'C_defensa_propuesta',
            'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta',
            'cita_pertenece_contexto': 'si', 'cita_sustenta_respuesta': 'completa',
            'latency_pipeline_seconds': 1.6, 'latency_generation_seconds': 0.9,
        },
    ]

    report = evaluate_quality(data)
    json_out = tmp_path / 'quality_metrics.json'
    csv_out = tmp_path / 'quality_metrics.csv'
    comp_out = tmp_path / 'quality_summary_comparison.csv'

    report.save_json(json_out)
    report.save_csv(csv_out)
    report.save_comparison_csv(comp_out)

    assert json_out.exists()
    assert csv_out.exists()
    assert comp_out.exists()

    # Verificar JSON
    saved_json = json.loads(json_out.read_text(encoding='utf-8'))
    assert 'metricas_latencia' in saved_json
    assert saved_json['metricas_latencia']['por_condicion']['A_sin_defensa']['latencia_pipeline']['media'] == 1.1

    # Verificar CSV tidy
    csv_content = csv_out.read_text(encoding='utf-8')
    assert 'latencia_pipeline_media_segundos' in csv_content
    assert 'latencia_generacion_media_segundos' in csv_content
    assert 'citas_diferenciacion' in csv_content

    # Verificar CSV tabla comparativa
    comp_content = comp_out.read_text(encoding='utf-8')
    assert 'Latencia del pipeline' in comp_content
    assert 'Latencia de generación' in comp_content
    assert 'Ausencia de citas' in comp_content


def test_trace_fallbacks_absent_ambiguous_and_duplicates():
    """Verifica resolución unívoca y compatible de trazas: ausentes, ambiguas y duplicadas."""
    traces_data = [
        # Caso 1: GQ001 en dos condiciones distintas en run1 -> ambiguo si no se especifica condición
        {'run_id': 'run1', 'case_id': 'GQ001', 'mode': 'A_sin_defensa', 'latency_pipeline_seconds': 1.0},
        {'run_id': 'run1', 'case_id': 'GQ001', 'mode': 'B_defensa_basica', 'latency_pipeline_seconds': 1.2},

        # Caso 2: GQ002 en la misma condición A pero en dos corridas distintas -> ambiguo si no se especifica run
        {'run_id': 'run1', 'case_id': 'GQ002', 'mode': 'A_sin_defensa', 'latency_pipeline_seconds': 2.0},
        {'run_id': 'run2', 'case_id': 'GQ002', 'mode': 'A_sin_defensa', 'latency_pipeline_seconds': 2.5},

        # Caso 3: GQ003 con registros duplicados para la misma clave exacta (run1, GQ003, A)
        {'run_id': 'run1', 'case_id': 'GQ003', 'mode': 'A_sin_defensa', 'latency_pipeline_seconds': 3.0},
        {'run_id': 'run1', 'case_id': 'GQ003', 'mode': 'A_sin_defensa', 'latency_pipeline_seconds': 3.1},

        # Caso 4: GQ004 unívoco y compatible
        {'run_id': 'run1', 'case_id': 'GQ004', 'mode': 'C_defensa_propuesta', 'latency_pipeline_seconds': 4.0},
    ]

    ann_data = [
        # Ausente
        {'evaluacion_id': 'e_abs', 'pregunta_id': 'GQ999', 'condicion': 'A_sin_defensa', 'corrida_id': 'run1'},
        # Ambiguo por condición (no especificada)
        {'evaluacion_id': 'e_amb_c', 'pregunta_id': 'GQ001', 'condicion': 'general', 'corrida_id': 'run1'},
        # Ambiguo por corrida (no especificada)
        {'evaluacion_id': 'e_amb_r', 'pregunta_id': 'GQ002', 'condicion': 'A_sin_defensa', 'corrida_id': ''},
        # Duplicado en fuente de trazas
        {'evaluacion_id': 'e_dup', 'pregunta_id': 'GQ003', 'condicion': 'A_sin_defensa', 'corrida_id': 'run1'},
        # Incompatible por condición (anotación pide B, traza de GQ004 es C)
        {'evaluacion_id': 'e_incomp_c', 'pregunta_id': 'GQ004', 'condicion': 'B_defensa_basica', 'corrida_id': 'run1'},
        # Incompatible por corrida (anotación pide run2, traza de GQ004 es run1)
        {'evaluacion_id': 'e_incomp_r', 'pregunta_id': 'GQ004', 'condicion': 'C_defensa_propuesta', 'corrida_id': 'run2'},
        # Unívoco y compatible
        {'evaluacion_id': 'e_ok', 'pregunta_id': 'GQ004', 'condicion': 'C_defensa_propuesta', 'corrida_id': 'run1'},
    ]

    recs = load_annotations(ann_data, traces_source=traces_data)
    by_id = {r.evaluacion_id: r for r in recs}

    # Ausente -> sin latencia (telemetría no disponible)
    assert by_id['e_abs'].latency_pipeline_seconds is None

    # Ambiguo por condición -> sin latencia
    assert by_id['e_amb_c'].latency_pipeline_seconds is None

    # Ambiguo por corrida -> sin latencia
    assert by_id['e_amb_r'].latency_pipeline_seconds is None

    # Duplicado en trazas -> sin latencia
    assert by_id['e_dup'].latency_pipeline_seconds is None

    # Incompatible por condición -> sin latencia
    assert by_id['e_incomp_c'].latency_pipeline_seconds is None

    # Incompatible por corrida -> sin latencia
    assert by_id['e_incomp_r'].latency_pipeline_seconds is None

    # Unívoco y compatible -> telemetría cargada correctamente
    assert by_id['e_ok'].latency_pipeline_seconds == 4.0


def test_historical_t11_join_requires_matching_manifest(tmp_path):
    historical = Path(__file__).resolve().parents[1] / 'results/llm_baseline'
    manifest = json.loads((historical / 'manifest.json').read_text(encoding='utf-8'))
    traces_path = tmp_path / 'traces.json'
    traces_path.write_bytes((historical / 'traces.json').read_bytes())
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    annotation = {
        'evaluacion_id': 'EVAL-T12-001-pipeline',
        'corrida_id': 'corrida_T11_baseline_ollama_20261120T053014',
        'pregunta_id': 'GQ004',
    }

    matched = load_annotations([annotation], traces_source=traces_path)[0]
    assert matched.condicion == 'A_sin_defensa'
    assert matched.motivo_abstencion == 'citas_invalidas_o_ausentes'

    manifest['modelo'] = 'otro_modelo'
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    unmatched = load_annotations([annotation], traces_source=traces_path)[0]
    assert unmatched.motivo_abstencion == ''


def test_compute_latencies_separates_incompatible_configurations():
    """Separa configuraciones incompatibles y evita mezclarlas en agregados comparativos."""
    # Dos casos en la misma corrida y condición pero con configuraciones dispares (distinto modelo y temperatura)
    data = [
        {
            'evaluacion_id': 'c1', 'corrida_id': 'run_mixed', 'pregunta_id': 'Q1', 'condicion': 'C_defensa_propuesta',
            'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta',
            'provider': 'ollama', 'model': 'qwen2.5:3b', 'seed': 42, 'temperature': 0.0, 'top_k': 5,
            'retriever': 'tfidf_cosine', 'prompt_version': 'v3',
            'latency_pipeline_seconds': 2.0, 'latency_generation_seconds': 1.5,
        },
        {
            'evaluacion_id': 'c2', 'corrida_id': 'run_mixed', 'pregunta_id': 'Q2', 'condicion': 'C_defensa_propuesta',
            'target': 'pipeline', 'estado_revision': 'anotado', 'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta',
            'provider': 'ollama', 'model': 'llama3:8b', 'seed': 42, 'temperature': 0.7, 'top_k': 5,
            'retriever': 'tfidf_cosine', 'prompt_version': 'v3',
            'latency_pipeline_seconds': 5.0, 'latency_generation_seconds': 4.0,
        },
    ]

    report = evaluate_quality(data)
    lat_cond = report.metricas_latencia['por_condicion']['C_defensa_propuesta']

    # Debe marcarse como incompatible y no mezclar las latencias en el agregado comparativo principal
    assert lat_cond['configuracion_compatible'] is False
    assert lat_cond['latencia_pipeline']['observaciones_validas'] == 0
    assert lat_cond['latencia_pipeline']['media'] is None

    # Debe contener los dos grupos separados
    grupos = lat_cond['grupos_configuracion']
    assert len(grupos) == 2
    g1, g2 = grupos[0], grupos[1]
    assert g1['configuracion']['model'] in ('qwen2.5:3b', 'llama3:8b')
    assert g2['configuracion']['model'] in ('qwen2.5:3b', 'llama3:8b')
    assert g1['latencia_pipeline']['observaciones_validas'] == 1
    assert g2['latencia_pipeline']['observaciones_validas'] == 1

    # En la tabla comparativa debe reportarse como incompatible separado
    comp_table = report.to_comparison_table_csv(TARGET_PIPELINE)
    pipe_row = next(r for r in comp_table if 'Latencia del pipeline' in r['metrica'])
    assert pipe_row['C_defensa_propuesta'] == 'Incompatible (separado)'


def test_citations_count_preserves_original_with_sanitized_citations_raw():
    """Verifica que citations_count represente el conteo original de citas ante saneamiento T16."""
    traces_data = [
        # Caso 1: T16 saneó citations_raw a [] porque ambas citas eran inválidas fuera de fragmentos
        {
            'run_id': 'run_cits', 'case_id': 'GQ010', 'mode': 'C_defensa_propuesta',
            'citations_raw': [], 'citations_invalid_count': 2, 'citations_valid': False,
            'citations_count': 0, 'abstention_reason': 'citas_invalidas_o_ausentes',
        },
        # Caso 2: T16 conservó 1 cita válida en citations_raw y registró 1 inválida (caso mixto)
        {
            'run_id': 'run_cits', 'case_id': 'GQ011', 'mode': 'C_defensa_propuesta',
            'citations_raw': [{'archivo': 'doc.pdf', 'pagina': 1}], 'citations_invalid_count': 1,
            'citations_valid': False, 'citations_count': 1,
        },
        # Caso 3: Ausencia real de citas (0 citas generadas)
        {
            'run_id': 'run_cits', 'case_id': 'GQ012', 'mode': 'C_defensa_propuesta',
            'citations_raw': [], 'citations_invalid_count': 0, 'citations_valid': False,
            'citations_count': 0, 'abstention_reason': 'citas_invalidas_o_ausentes',
        },
    ]

    ann_data = [
        {'evaluacion_id': 'e10', 'corrida_id': 'run_cits', 'pregunta_id': 'GQ010', 'condicion': 'C_defensa_propuesta', 'tipo_salida': 'respuesta'},
        {'evaluacion_id': 'e11', 'corrida_id': 'run_cits', 'pregunta_id': 'GQ011', 'condicion': 'C_defensa_propuesta', 'tipo_salida': 'respuesta'},
        {'evaluacion_id': 'e12', 'corrida_id': 'run_cits', 'pregunta_id': 'GQ012', 'condicion': 'C_defensa_propuesta', 'tipo_salida': 'respuesta'},
    ]

    recs = load_annotations(ann_data, traces_source=traces_data)
    by_id = {r.evaluacion_id: r for r in recs}

    # GQ010: el modelo generó 2 citas (ambas inválidas). citations_count debe ser 2, NO 0
    assert by_id['e10'].citations_count == 2
    assert by_id['e10'].citations_invalid_count == 2
    assert by_id['e10'].citations_category == 'citas_invalidas'

    # GQ011: 1 válida + 1 inválida -> total original = 2 (mixtas)
    assert by_id['e11'].citations_count == 2
    assert by_id['e11'].citations_invalid_count == 1
    assert by_id['e11'].citations_category == 'mixtas'

    # GQ012: 0 citas reales -> total original = 0 (ausencia_citas)
    assert by_id['e12'].citations_count == 0
    assert by_id['e12'].citations_category == 'ausencia_citas'


def test_latencies_computed_even_when_human_evaluation_pending():
    """Comprueba que las métricas de latencia técnica no dependan de la disponibilidad de evaluación humana."""
    # Archivo de evaluación donde todos los casos están en estado 'pendiente' (sin evaluación humana completada)
    ann_data = [
        {
            'evaluacion_id': f'e_{i}', 'corrida_id': 'run_pending', 'pregunta_id': f'GQ00{i}',
            'condicion': 'A_sin_defensa', 'target': 'pipeline', 'estado_revision': 'pendiente',
            'tipo_salida': '', 'calidad_respuesta': '',
            'latency_pipeline_seconds': 1.0 + (i * 0.2), 'latency_generation_seconds': 0.8 + (i * 0.1),
            'provider': 'ollama', 'model': 'qwen2.5:3b', 'temperature': 0.0, 'seed': 42,
        }
        for i in range(1, 4)
    ]

    report = evaluate_quality(ann_data)

    # Evaluación humana debe estar en cero / pendiente
    res = report.resumen_global
    assert res['contabilidad_casos']['casos_evaluables'] == 0
    assert res['contabilidad_casos']['casos_pendientes'] == 3
    assert res['calidad_contenido']['exactitud_humana_contenido']['value'] is None

    # Telemetría de latencias DEBE estar calculada con n=3
    lat_cond = report.metricas_latencia['por_condicion']['A_sin_defensa']
    assert lat_cond['latencia_pipeline']['observaciones_validas'] == 3
    assert lat_cond['latencia_pipeline']['media'] == 1.4  # (1.2 + 1.4 + 1.6) / 3 = 1.4
    assert lat_cond['latencia_generacion']['observaciones_validas'] == 3

    # Tabla comparativa debe reflejar las latencias independientemente de la falta de evaluación humana
    table = report.to_comparison_table_csv(TARGET_PIPELINE)
    pipe_row = next(r for r in table if 'Latencia del pipeline' in r['metrica'])
    assert '1.4s' in pipe_row['A_sin_defensa']
    assert '(n=3)' in pipe_row['A_sin_defensa']


def test_preserves_valid_zero_values_temperature_seed_citations():
    """Conserva correctamente valores válidos iguales a cero, incluyendo temperature=0 y seed=0."""
    from cs_rag_security.evaluation.quality import compute_latency_summary

    trace = {
        'run_id': 'run_zero', 'case_id': 'Q_ZERO', 'mode': 'A_sin_defensa',
        'parameters': {'temperature': 0, 'seed': 0, 'top_k': 5},
        'provider': 'mock', 'model': 'test_mock',
        'citations_count': 0, 'citations_invalid_count': 0,
        'latency_pipeline_seconds': 0.0, 'latency_generation_seconds': 0.0,
    }

    ann = [{
        'evaluacion_id': 'ez', 'corrida_id': 'run_zero', 'pregunta_id': 'Q_ZERO',
        'condicion': 'A_sin_defensa', 'target': 'pipeline', 'estado_revision': 'anotado',
        'tipo_salida': 'respuesta', 'calidad_respuesta': 'correcta',
    }]

    recs = load_annotations(ann, traces_source=[trace])
    rec = recs[0]

    assert rec.temperature == 0.0
    assert rec.seed == 0
    assert rec.citations_count == 0
    assert rec.citations_invalid_count == 0
    assert rec.latency_pipeline_seconds == 0.0
    assert rec.latency_generation_seconds == 0.0

    # compute_latency_summary con ceros válidos
    summary = compute_latency_summary([0.0, 0.0], "Latencias mock instantáneas")
    assert summary['observaciones_validas'] == 2
    assert summary['media'] == 0.0
    assert summary['mediana'] == 0.0
    assert summary['percentil_95'] == 0.0



