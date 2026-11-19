"""Pruebas unitarias sin acceso a los PDF originales."""
import hashlib
from pathlib import Path

from scripts.audit_corpus import (
    generate_markdown,
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
