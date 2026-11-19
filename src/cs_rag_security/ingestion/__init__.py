"""Lectura estricta del corpus piloto; nunca lee gold para indexar."""
import hashlib
import json
from pathlib import Path
from cs_rag_security.ingestion.normativa import context_relations, excluded_ids, official_path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_pages(root):
    root = Path(root)
    documents = read_json(root / '04_Metadatos/documents.json')['documentos']
    docs = {d['id']: d for d in documents}
    if len(docs) != len(documents):
        raise ValueError('ID de documento duplicado')
    relations = read_json(root / '04_Metadatos/relaciones_normativas.json')['relaciones_conocidas_no_exhaustivas']
    blocked = excluded_ids(documents, relations)
    seen = set()
    pages = []
    source = root / '05_Texto_Procesado/paginas_rag_piloto.jsonl'
    for line in source.read_text(encoding='utf-8').splitlines():
        p = json.loads(line)
        d = docs[p['documento_id']]
        if not official_path(d.get('archivo_en_paquete')) or d['id'] in blocked:
            raise ValueError('Página histórica, externa o sin archivo oficial')
        key = (p['documento_id'], p['pagina_pdf'])
        if key in seen or type(p['pagina_pdf']) is not int or not 1 <= p['pagina_pdf'] <= d['archivo_local']['paginas_pdf']:
            raise ValueError('Página duplicada o fuera de rango')
        if p['archivo_pdf'] != d['archivo_pdf'] or not isinstance(p['texto'], str):
            raise ValueError('Metadatos de página incompatibles')
        if type(p['ocr_revision_manual_pendiente']) is not bool or p['metodo'] not in ('texto_pdf', 'ocr_tesseract_spa'):
            raise ValueError('Extracción desconocida')
        if p['metodo'].startswith('ocr') and not p['ocr_revision_manual_pendiente']:
            raise ValueError('OCR sin advertencia de revisión')
        seen.add(key)
        pages.append({**p, 'estado_normativo': d['vigencia']['estado'],
                      'fecha_resolucion': d['fecha_resolucion'], 'aviso_uso': d['vigencia']['advertencia'],
                      'origen': 'oficial_piloto', 'normativa_actual_verificada': False,
                      'relaciones_normativas': context_relations(d['id'], relations)})
    expected = {(d['id'], n) for d in docs.values() if official_path(d.get('archivo_en_paquete')) and d['id'] not in blocked
                for n in range(1, d['archivo_local']['paginas_pdf'] + 1)}
    if seen != expected:
        raise ValueError('Cobertura de páginas incompleta')
    return pages


def audit(root):
    root = Path(root)
    for name in ('relaciones_normativas.json', 'descargas_pendientes.json'):
        read_json(root / '04_Metadatos' / name)
    docs = read_json(root / '04_Metadatos/documents.json')['documentos']
    hashes = {}
    for d in docs:
        if d.get('archivo_local'):
            path = root / d['archivo_en_paquete']
            actual = digest(path)
            if actual != d['archivo_local']['sha256'] or path.stat().st_size != d['archivo_local']['tamano_bytes']:
                raise ValueError(f'Integridad PDF: {path}')
            hashes[d['archivo_pdf']] = actual
    official = list((root / '01_Corpus_Oficial').glob('*.pdf'))
    historical = list((root / '01B_Historicos').glob('*.pdf'))
    if len(official) != 11 or len(historical) != 1 or historical[0].name != 'RCU-0252-2021.pdf':
        raise ValueError('Inventario PDF inesperado')
    gold = read_json(root / '03_Preguntas_Respuestas/gold_questions.json')
    pending = read_json(root / '03_Preguntas_Respuestas/preguntas_pendientes.json')
    pages = load_pages(root)
    return {'pdf_oficiales': len(official), 'pdf_historicos': len(historical), 'paginas_piloto': len(pages),
            'paginas_ocr': sum(p['ocr_revision_manual_pendiente'] for p in pages),
            'preguntas_gold': len(gold['preguntas']), 'pendientes_tipo': type(pending).__name__,
            'sha256_pdf': hashes, 'sha256_jsonl': digest(root / '05_Texto_Procesado/paginas_rag_piloto.jsonl'),
            'ausentes_conocidos': ['RCU-0435-2017.pdf', 'RCU-0317-2026.pdf', 'RCU-0590-2023.pdf']}


def chunks(pages, size=180, overlap=30):
    if size <= overlap or overlap < 0:
        raise ValueError('Tamaño/solapamiento inválidos')
    result = []
    for p in pages:
        # Respeta párrafos cuando caben; subdivide párrafos largos por palabras.
        blocks = p['texto'].split('\n\n')
        for bi, block in enumerate(blocks):
            words = block.split()
            for start in range(0, len(words), size - overlap):
                result.append({**p, 'texto': ' '.join(words[start:start + size]),
                               'chunk_id': f"{p['documento_id']}:{p['pagina_pdf']}:{bi}:{start}"})
                if start + size >= len(words):
                    break
    return result
