import pytest

from cs_rag_security.defenses import MODES
from scripts.compute_security_metrics import compute


def test_report_keeps_mock_separate_and_preserves_missing_observations():
    records = [
        {
            'kind': 'synthetic', 'id': 'P1', 'mode': MODES[0], 'attack': True,
            'attack_retrieved': True, 'marker_emitted': False, 'detected': True,
        },
        {
            'kind': 'synthetic', 'id': 'P2', 'mode': MODES[0], 'attack': True,
            'attack_retrieved': False, 'detected': False,
        },
        {'kind': 'synthetic', 'id': 'B1', 'mode': MODES[0], 'attack': False, 'detected': True},
    ]
    report = compute(records, {'provider': 'mock'})
    diag = report['diagnostico_mock'][MODES[0]]

    assert MODES[0] not in report
    assert diag['resultado_global'] == {
        'numerator': 0, 'denominator': 2, 'missing': 1, 'value': None,
    }
    assert diag['resultado_recuperados']['value'] == 0.0
    assert diag['recall_detector']['value'] == 0.5
    assert diag['fpr_detector']['value'] == 1.0


def test_duplicate_case_would_inflate_a_condition_denominator():
    record = {
        'case_kind': 'synthetic_benign', 'case_id': 'B1',
        'condition': MODES[1], 'detected': False,
    }
    with pytest.raises(ValueError, match='duplicado'):
        compute([record, record], {'proveedor': 'mock'})


def test_no_exposed_cases_leaves_retrieved_result_without_estimate():
    record = {
        'case_kind': 'synthetic_attack', 'case_id': 'P1', 'condition': MODES[0],
        'attack_retrieved': False, 'marker_emitted': False, 'detected': True,
    }
    report = compute([record], {'proveedor': 'local', 'modelo': 'modelo_de_prueba'})

    assert report[MODES[0]]['asr_global_percent'] == 0.0
    assert report[MODES[0]]['asr_retrieved_percent'] is None
    assert report['por_condicion'][MODES[0]]['fpr_detector']['value'] is None
