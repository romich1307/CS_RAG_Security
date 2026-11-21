import json

import pytest

from scripts import audit_benign_detector


def test_benign_audit_reports_partition_counts_and_excludes_text(tmp_path, monkeypatch):
    controls = tmp_path / 'controls.jsonl'
    cases = [
        {
            'id': case_id,
            'particion': partition,
            'categoria': 'tramite',
            'etiqueta': 'benigno',
            'texto': fragment,
            'resultado_esperado': {'marcado': False},
        }
        for case_id, partition, fragment in (
            ('B1', 'desarrollo', 'Primer trámite ficticio.'),
            ('B2', 'desarrollo', 'Segundo trámite ficticio.'),
        )
    ]
    controls.write_text('\n'.join(map(json.dumps, cases)), encoding='utf-8')

    def detect(fragment):
        marked = fragment == cases[0]['texto']
        return {
            'detector': 'detector_de_prueba',
            'suspicious': marked,
            'reasons': ['motivo_de_prueba'] if marked else [],
        }

    monkeypatch.setattr(audit_benign_detector, 'detect', detect)
    report = audit_benign_detector.audit(controls)

    assert report['total'] == {
        'falsos_positivos': 1,
        'controles_evaluados': 2,
        'tasa_falsos_positivos': 0.5,
    }
    assert report['por_particion']['verificacion']['tasa_falsos_positivos'] is None
    assert report['casos'][0]['motivos'] == ['motivo_de_prueba']
    assert report['proveedor_llm'] is None
    assert all('texto' not in case for case in report['casos'])


def test_benign_audit_rejects_duplicate_ids(tmp_path):
    item = {
        'id': 'B1',
        'particion': 'desarrollo',
        'categoria': 'tramite',
        'etiqueta': 'benigno',
        'texto': 'El personal archiva la constancia.',
        'resultado_esperado': {'marcado': False},
    }
    controls = tmp_path / 'controls.jsonl'
    controls.write_text('\n'.join([json.dumps(item)] * 2), encoding='utf-8')

    with pytest.raises(ValueError, match='duplicado'):
        audit_benign_detector.audit(controls)
