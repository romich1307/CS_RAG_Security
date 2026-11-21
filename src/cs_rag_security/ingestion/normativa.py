"""Reglas documentales conservadoras; no certifican vigencia jurídica actual."""
from pathlib import PurePosixPath

HISTORICAL_IDS = frozenset({'RCU-0252-2021'})


def excluded_ids(documents, relations):
    blocked = set(HISTORICAL_IDS)
    for document in documents:
        path = PurePosixPath(document.get('archivo_en_paquete') or '')
        if document.get('usar_como_norma_vigente') is False or '01B_Historicos' in path.parts:
            blocked.add(document['id'])
    for relation in relations:
        # Una derogación de disposición/artículo no elimina el reglamento entero.
        scope = relation.get('alcance', '').casefold()
        if relation.get('tipo') == 'deja_sin_efecto' and any(word in scope for word in ('completa', 'total')):
            blocked.add(relation['documento_origen'])
    return blocked


def official_path(path):
    path = PurePosixPath(path or '')
    return (not path.is_absolute() and '..' not in path.parts and
            len(path.parts) == 2 and path.parts[0] == '01_Corpus_Oficial' and
            path.suffix.lower() == '.pdf')


def context_relations(document_id, relations):
    return [dict(relation) for relation in relations
            if document_id in (relation.get('documento_origen'), relation.get('documento_posterior'))]


def historical_hit(hit):
    identifiers = {hit.get('documento_id'), PurePosixPath(hit.get('archivo_pdf', '')).stem}
    return bool(identifiers & HISTORICAL_IDS) or hit.get('usar_como_norma_vigente') is False
