"""Mide las alertas del detector sobre controles benignos etiquetados."""

import argparse
import hashlib
import json
from pathlib import Path

from cs_rag_security.defenses import detect


CONTROLS = Path(__file__).resolve().parents[1] / 'experiments/benign_v2.jsonl'
PARTITIONS = ('desarrollo', 'verificacion')


def summarize(records):
    total = len(records)
    marked = sum(record['marcado'] for record in records)
    return {
        'falsos_positivos': marked,
        'controles_evaluados': total,
        'tasa_falsos_positivos': marked / total if total else None,
    }


def audit(controls_path):
    records = []
    seen_ids = set()
    versions = set()
    checksum = hashlib.sha256()

    with controls_path.open('rb') as stream:
        for number, raw_line in enumerate(stream, start=1):
            checksum.update(raw_line)
            line = raw_line.decode('utf-8')
            if not line.strip():
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f'Línea {number}: JSON inválido.') from error
            if not isinstance(case, dict):
                raise ValueError(f'Línea {number}: se esperaba un objeto.')

            case_id = case.get('id')
            partition = case.get('particion')
            category = case.get('categoria')
            fragment = case.get('texto')
            expected = case.get('resultado_esperado')
            if not isinstance(case_id, str) or not case_id.strip() or case_id in seen_ids:
                raise ValueError(f'Línea {number}: ID vacío, inválido o duplicado.')
            if partition not in PARTITIONS or not isinstance(category, str) or not category.strip():
                raise ValueError(f'Línea {number}: partición o categoría inválida.')
            if (
                case.get('etiqueta') != 'benigno'
                or not isinstance(expected, dict)
                or expected.get('marcado') is not False
            ):
                raise ValueError(f'Línea {number}: se esperaba un control benigno.')
            if not isinstance(fragment, str) or not fragment.strip():
                raise ValueError(f'Línea {number}: fragmento vacío o inválido.')

            result = detect(fragment)
            versions.add(result['detector'])
            seen_ids.add(case_id)
            records.append({
                'id': case_id,
                'particion': partition,
                'categoria': category,
                'marcado': result['suspicious'],
                'score': result['score'],
                'motivos': result['reasons'],
            })

    if not records:
        raise ValueError('El archivo no contiene controles benignos.')
    if len(versions) != 1:
        raise ValueError('La auditoría encontró más de una versión del detector.')

    return {
        'detector': versions.pop(),
        'proveedor_llm': None,
        'dataset_sha256': checksum.hexdigest(),
        'total': summarize(records),
        'por_particion': {
            partition: summarize([record for record in records if record['particion'] == partition])
            for partition in PARTITIONS
        },
        'casos': records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--controles', type=Path, default=CONTROLS)
    parser.add_argument('--salida', type=Path, help='Ruta nueva para el informe JSON.')
    args = parser.parse_args()

    try:
        payload = json.dumps(audit(args.controles), ensure_ascii=False, indent=2) + '\n'
        if args.salida:
            with args.salida.open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(payload)
        else:
            print(payload, end='')
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
