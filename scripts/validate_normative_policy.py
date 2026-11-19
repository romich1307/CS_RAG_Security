"""Auditoría reproducible de T06; no altera el corpus ni ejecuta un LLM."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from cs_rag_security.defenses import MODES
from cs_rag_security.ingestion import audit, chunks, digest, load_pages, read_json
from cs_rag_security.ingestion.normativa import excluded_ids
from cs_rag_security.pipeline import answer
from cs_rag_security.retrieval import Index


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, default=Path('data/corpus_unsa'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError(args.output)
    report = audit(args.corpus)
    pages = load_pages(args.corpus)
    fragments = chunks(pages)
    documents = read_json(args.corpus / '04_Metadatos/documents.json')['documentos']
    relations = read_json(args.corpus / '04_Metadatos/relaciones_normativas.json')['relaciones_conocidas_no_exhaustivas']
    blocked = excluded_ids(documents, relations)
    historical_count = sum(page['documento_id'] in blocked for page in pages)
    assert historical_count == 0
    index = Index(fragments)
    current = answer(index, 'evaluación por competencias')
    documental = answer(index, 'evaluación por competencias', documental=True)
    assert current['abstained'] and not current['accepted_ids']
    assert not documental['abstained']
    stale = Index([{'documento_id': 'RCU-0252-2021', 'archivo_pdf': 'RCU-0252-2021.pdf',
                    'pagina_pdf': 2, 'chunk_id': 'historical_fixture', 'texto': 'Evaluación académica',
                    'ocr_revision_manual_pendiente': False, 'normativa_actual_verificada': True}])
    stale_checks = []
    for mode in MODES:
        for documentary in (False, True):
            result = answer(stale, 'evaluación académica', mode=mode, documental=documentary)
            assert result['abstained'] and not result['accepted_ids']
            stale_checks.append({'mode': mode, 'documental': documentary, 'blocked': True})
    base = Path(__file__).resolve().parents[1]
    source_paths = [Path(__file__), base / 'src/cs_rag_security/ingestion/__init__.py',
                    base / 'src/cs_rag_security/ingestion/normativa.py', base / 'src/cs_rag_security/pipeline.py']
    payload = {'status': 'completed', 'task': 'T06', 'timestamp_utc': datetime.now(timezone.utc).isoformat(),
               'provider': 'mock', 'scope': 'integridad_y_reglas_documentales_sin_medicion_de_eficacia_LLM',
               'corpus': report, 'n_chunks': len(fragments), 'excluded_document_ids': sorted(blocked),
               'historical_pages_in_current_index': historical_count,
               'uncertified_current_query_abstained': current['abstained'],
               'documentary_mock_query_answered': not documental['abstained'],
               'stale_index_controls': stale_checks,
               'input_sha256': {name: digest(args.corpus / '04_Metadatos' / name)
                                for name in ('documents.json', 'relaciones_normativas.json', 'descargas_pendientes.json')},
               'source_sha256': {str(path.relative_to(base)): digest(path) for path in source_paths},
               'limitations': ['Vigencia actual no certificada.', '115 páginas OCR conservan revisión pendiente.',
                               'RCU-0435-2017, RCU-0317-2026 y RCU-0590-2023 no están en el paquete.',
                               'Las comprobaciones de consulta usan mock; no miden calidad ni seguridad de un LLM.']}
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'validation.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: payload[key] for key in ('status', 'n_chunks', 'excluded_document_ids',
                                                  'historical_pages_in_current_index')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
