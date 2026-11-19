"""Pruebas unitarias sin acceso a los PDF originales."""
import hashlib
from pathlib import Path

from scripts.audit_corpus import (
    generate_markdown,
    declared_in_package,
    metadata_status,
    page_numbers,
    pdf_identifier,
    referenced_pdf_names,
    sha256,
)


def test_pdf_identifier():
    assert pdf_identifier('x/y/RCU-0161-2021.pdf') == 'rcu-0161-2021.pdf'
    assert pdf_identifier('RCU-0161-2021') == 'rcu-0161-2021.pdf'
    assert pdf_identifier('sin-identificar') == ''


def test_fuentes_anidadas_y_paginas():
    item = {'fuentes': [{'archivo_pdf': 'RCU-0127-2020.pdf', 'pagina': 3}, {'archivo': 'RCU-0320-2022.pdf', 'paginas': [5, 8]}]}
    assert referenced_pdf_names(item) == {'rcu-0127-2020.pdf', 'rcu-0320-2022.pdf'}
    assert page_numbers(item) == [3, 5, 8]


def test_sha256(tmp_path: Path):
    file = tmp_path / 'test.pdf'
    file.write_bytes(b'contenido de prueba')
    assert sha256(file) == hashlib.sha256(b'contenido de prueba').hexdigest()


def test_generate_markdown_minimo():
    counts = {'pdf': 1, 'preguntas_gold': 1, 'registros_validacion': 1}
    result = {'conteos': counts,
              'integridad': [{'archivo': 'x.pdf', 'estado': 'coincide'}],
              'metadatos': [], 'extraccion': [], 'incidencias': [], 'limitaciones': []}
    report = generate_markdown(result)
    assert 'Auditoría del corpus UNSA' in report
    assert 'x.pdf' in report
    assert 'evidencias/revision_visual_rcu_0127_2020_p8.md' in report
    assert 'VALIDACION_GOLD_PILOTO.md' in report


def test_pdf_declarado_mediante_ruta_pero_ausente():
    documento = {
        "id": "RCU-0999-2026",
        "archivo_en_paquete": "01_Corpus_Oficial/RCU-0999-2026.pdf",
    }
    assert declared_in_package(documento["archivo_en_paquete"])
    nombre, presente, situacion = metadata_status(documento, {})
    assert nombre == "rcu-0999-2026.pdf"
    assert presente is False
    assert situacion == "no_encontrado_declarado_incluido"


def test_pdf_sin_inclusion_confirmada_no_es_un_error_de_perdida():
    documento = {"id": "RCU-0998-2026", "archivo_en_paquete": "no"}
    assert not declared_in_package(documento["archivo_en_paquete"])
    assert metadata_status(documento, {})[2] == "no_encontrado_inclusion_no_confirmada"
