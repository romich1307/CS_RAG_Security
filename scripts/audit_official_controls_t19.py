"""Mide alertas del detector en el corpus piloto oficial fijado en T08."""

import argparse
import json
from pathlib import Path

from cs_rag_security import defenses
from cs_rag_security.ingestion import chunks, digest, load_pages, read_json


MANIFEST = (
    Path(__file__).resolve().parents[1]
    / 'results/retrieval_t08_20261119_final/manifest.json'
)


def audit(corpus):
    manifest = read_json(MANIFEST)
    source = corpus / '05_Texto_Procesado/paginas_rag_piloto.jsonl'
    source_hash = digest(source)
    if source_hash != manifest['corpus']['sha256_jsonl']:
        raise ValueError('El texto procesado no coincide con el manifiesto de T08.')

    pages = load_pages(corpus)
    pdfs = {page['archivo_pdf'] for page in pages}
    for name in sorted(pdfs):
        pdf = corpus / '01_Corpus_Oficial' / name
        if digest(pdf) != manifest['corpus']['sha256_pdf'].get(name):
            raise ValueError(f'El PDF {name} no coincide con el manifiesto de T08.')

    config = manifest['protocol']
    fragments = chunks(pages, config['chunk_size_words'], config['chunk_overlap_words'])
    ids = {fragment['chunk_id'] for fragment in fragments}
    if not fragments or len(fragments) != len(ids) or len(fragments) != manifest['n_chunks']:
        raise ValueError('El número de fragmentos no coincide con el manifiesto de T08.')

    decisions = [defenses.detect(fragment['texto']) for fragment in fragments]
    (detector,) = {decision['detector'] for decision in decisions}
    alerts = [
        fragment['chunk_id']
        for fragment, decision in zip(fragments, decisions, strict=True)
        if decision['suspicious']
    ]
    return {
        'tarea': 'T19',
        'tipo_evaluacion': 'control_benigno_corpus_oficial',
        'proveedor': 'no_aplica',
        'modelo': None,
        'detector_version': detector,
        'hashes_entradas': {
            'manifiesto_t08_sha256': digest(MANIFEST),
            'corpus_piloto_sha256': source_hash,
            'detector_sha256': digest(defenses.__file__),
        },
        'pdf_oficiales_verificados': len(pdfs),
        'paginas': len(pages),
        'tasa_alertas': {
            'numerator': len(alerts),
            'denominator': len(fragments),
            'value': len(alerts) / len(fragments),
        },
        'ids_con_alerta': alerts,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--salida', type=Path, help='Ruta a un archivo JSON nuevo.')
    args = parser.parse_args()
    try:
        payload = json.dumps(audit(args.corpus), ensure_ascii=False, indent=2) + '\n'
        if args.salida:
            with args.salida.open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(payload)
        else:
            print(payload, end='')
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
