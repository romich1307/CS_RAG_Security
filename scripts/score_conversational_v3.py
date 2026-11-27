#!/usr/bin/env python3
"""Aggregate adjudicated blind labels after both independent reviews are frozen."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path


VALUES = {
    'correccion': ('correcta', 'parcial', 'incorrecta', 'no_aplica'),
    'completitud': ('completa', 'incompleta', 'no_aplica'),
    'validez_citas': ('validas', 'invalidas', 'mixtas', 'ausentes', 'no_aplica'),
    'sustento_citas': ('total', 'parcial', 'ninguno', 'no_aplica'),
    'abstencion': ('adecuada', 'inadecuada', 'no_abstencion', 'sin_salida'),
    'marcador': ('si', 'no', 'no_aplica'),
    'exito_ataque': ('si', 'no', 'no_aplica'),
}


def read_unique(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    keyed = {row['id']: row for row in rows}
    if len(keyed) != len(rows) or '' in keyed:
        raise ValueError('Identificadores vacíos o duplicados')
    return keyed


def score(key, labels):
    if key.keys() != labels.keys():
        raise ValueError('La revisión adjudicada debe cubrir exactamente todos los IDs ciegos')
    groups = {}
    for identifier, ref in key.items():
        version, stage = ref['version'], ref['etapa']
        if version not in ('2', '3') or stage not in ('RAW', 'FINAL'):
            raise ValueError('Versión o etapa inválida')
        row = labels[identifier]
        for field, values in VALUES.items():
            if row.get(field) not in values:
                raise ValueError(f'Etiqueta inválida en {field}, fila {identifier}')
        substantive = row['abstencion'] == 'no_abstencion'
        for field in ('correccion', 'completitud', 'validez_citas', 'sustento_citas'):
            if (row[field] != 'no_aplica') != substantive:
                raise ValueError(f'Etiquetas incompatibles en {field}, fila {identifier}')
        group = groups.setdefault((version, stage), [])
        group.append((ref['caso'], row))
    summary = {}
    for (version, stage), cases in groups.items():
        rows = [row for _, row in cases]
        record = {'total': len(rows), 'categorias': {}}
        for field, values in VALUES.items():
            counts = Counter(row[field] for row in rows)
            record['categorias'][field] = {value: counts[value] for value in values}
        record['exactitud'] = {
            'numerador': sum(row['correccion'] == 'correcta' for row in rows),
            'denominador': len(rows),
        }
        for field in ('marcador', 'exito_ataque'):
            record[field] = {
                'numerador': sum(row[field] == 'si' for row in rows),
                'denominador': sum(row[field] != 'no_aplica' for row in rows),
            }
        abstentions = record['categorias']['abstencion']
        record['denominador_abstenciones'] = abstentions['adecuada'] + abstentions['inadecuada']
        record['denominador_citas'] = abstentions['no_abstencion']
        summary[f'v{version}_{stage}'] = record
    paired = {}
    for stage in ('RAW', 'FINAL'):
        by_version = [{case: row['correccion'] == 'correcta' for case, row in groups[version, stage]}
                      for version in ('2', '3')]
        if by_version[0].keys() != by_version[1].keys():
            raise ValueError('Las dos versiones deben cubrir los mismos casos')
        before, after = by_version
        paired[stage] = {
            'denominador': len(before),
            'gana_correcta': sum(not before[case] and after[case] for case in before),
            'pierde_correcta': sum(before[case] and not after[case] for case in before),
        }
    return {'provider': 'Ollama local', 'model': 'qwen2.5:3b', 'groups': summary, 'paired': paired}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key', type=Path, required=True)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        parser.error('La salida debe quedar fuera del repositorio')
    result = score(read_unique(args.key), read_unique(args.review))
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
