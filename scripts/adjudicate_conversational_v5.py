#!/usr/bin/env python3
"""Combine independent blind assessments and explicitly adjudicate disagreements."""
import argparse
import json
from pathlib import Path

from score_conversational_v3 import VALUES, read_unique, score


FIELDS = tuple(VALUES)


def adjudicate(blind, first, second, resolution):
    if first.keys() != blind.keys() or second.keys() != blind.keys():
        raise ValueError('Ambas revisiones deben cubrir los mismos IDs de la hoja original')
    agreed, disputes = {}, {}
    agreement = dict.fromkeys(FIELDS, 0)
    for identifier in blind:
        left, right = first[identifier], second[identifier]
        for field, values in VALUES.items():
            if left.get(field) not in values or right.get(field) not in values:
                raise ValueError(f'Etiqueta ausente o inválida en {field}, fila {identifier}')
            agreement[field] += left[field] == right[field]
        if all(left[field] == right[field] for field in FIELDS):
            agreed[identifier] = left
        else:
            disputes[identifier] = (left, right)
    if disputes.keys() != resolution.keys():
        raise ValueError(f'Se deben adjudicar exactamente los {len(disputes)} IDs discrepantes')
    result = {**agreed, **resolution}
    for identifier, original in blind.items():
        is_missing = original['estado'] in ('sin_salida', 'formato_invalido')
        if (result[identifier].get('abstencion') == 'sin_salida') != is_missing:
            raise ValueError(f'El estado operativo de {identifier} no concuerda con la adjudicación')
    return result, {field: {'numerador': n, 'denominador': len(blind)}
                    for field, n in agreement.items()}, len(disputes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('blind', 'first', 'second', 'key', 'output'):
        parser.add_argument(f'--{name}', required=True, type=Path)
    parser.add_argument('--resolution', type=Path)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        parser.error('El agregado de una evaluación privada debe quedar fuera del repositorio')
    blind = read_unique(args.blind)
    labels, agreement, disputes = adjudicate(
        blind, read_unique(args.first), read_unique(args.second),
        read_unique(args.resolution) if args.resolution else {},
    )
    original_key = read_unique(args.key)
    versions = {'4': '2', '5': '3'}
    projected = {identifier: {**row, 'version': versions[row['version']]}
                 for identifier, row in original_key.items()}
    result = score(projected, labels)
    result['groups'] = {f'v{int(group[1]) + 2}{group[2:]}': row
                        for group, row in result['groups'].items()}
    result['agreement'] = agreement
    result['disputed_rows'] = disputes
    result['operation'] = {
        group: dict.fromkeys(('sin_salida', 'formato_invalido'), 0)
        for group in result['groups']
    }
    for identifier, ref in original_key.items():
        state = blind[identifier]['estado']
        if state in ('sin_salida', 'formato_invalido'):
            result['operation'][f"v{ref['version']}_{ref['etapa']}"][state] += 1
    with args.output.open('x', encoding='utf-8') as file:
        json.dump(result, file, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
