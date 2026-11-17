import os
from pathlib import Path
import pytest
from cs_rag_security.ingestion import audit, chunks
from cs_rag_security.retrieval import Index


def test_chunk_metadata_and_search(tmp_path):
    page = {'texto': 'Evaluación por competencias. Diagnóstico y control.', 'documento_id': 'demo', 'pagina_pdf': 3}
    idx = Index(chunks([page]))
    assert idx.search('competencias')[0]['pagina_pdf'] == 3
    assert idx.search('xyzabcdef') == []
    idx.save(tmp_path / 'i.json', {})
    assert Index.load(tmp_path / 'i.json').search('control') == idx.search('control')
    with pytest.raises(ValueError):
        idx.search('control', 0)
    with pytest.raises(ValueError):
        chunks([page], 10, 10)


@pytest.mark.corpus
@pytest.mark.skipif(not Path('data/corpus_unsa/04_Metadatos/documents.json').exists(), reason='corpus privado ausente')
def test_real_corpus():
    report = audit('data/corpus_unsa')
    assert (report['pdf_oficiales'], report['pdf_historicos'], report['paginas_piloto'], report['paginas_ocr'], report['preguntas_gold']) == (11, 1, 137, 115, 40)
