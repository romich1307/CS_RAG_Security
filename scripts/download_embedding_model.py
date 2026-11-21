"""Descarga explícita y acotada del modelo público usado en T08; no consume APIs LLM."""
import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

MODEL_ID = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
REVISION = 'e8f8c211226b894fcb81acc59f3b34ba3efd5f42'
EXPECTED = {
    'onnx/model_quint8_avx2.onnx': '98a01d88b7de996cdea58c32ca71208c09968d143798814b2ea09d3439dc334f',
    'tokenizer.json': '2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8',
    'config.json': '6300193cb75e01cf80c96decef7187dfb33094d97cc1490b7ead6ff134476e4e',
    'sentence_bert_config.json': '70f4448f31320443fe3557cacea5abf2dcc4915dda8c80646bec9f3bb0aa5a1f',
    '1_Pooling/config.json': '4be450dde3b0273bb9787637cfbd28fe04a7ba6ab9d36ac48e92b11e350ffc23',
    'README.md': '1e98ea05b0de579fcaad3d625b62ea55647142ed674d5f5ebf1440e4bbbb6f23',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sizes = {}
    for name, expected in EXPECTED.items():
        target = args.output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(f'https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{name}',
                                         headers={'User-Agent': 'CS-RAG-Security-research/0.1'})
        digest, count = hashlib.sha256(), 0
        with urllib.request.urlopen(request, timeout=90) as response, target.open('xb') as stream:
            while block := response.read(1024 * 1024):
                count += len(block)
                if count > 160 * 1024 * 1024:
                    raise ValueError('Archivo excede el límite de la variante compacta')
                digest.update(block)
                stream.write(block)
        if digest.hexdigest() != expected:
            raise ValueError(f'El archivo descargado no coincide con la revisión fijada: {name}')
        sizes[name] = count
    manifest = {'model_id': MODEL_ID, 'revision': REVISION, 'onnx_file': 'onnx/model_quint8_avx2.onnx',
                'max_length': 128, 'pooling': 'attention_mask_mean', 'normalize': 'l2',
                'quantization': 'quint8_avx2', 'license': 'apache-2.0',
                'files_sha256': EXPECTED, 'files_bytes': sizes,
                'source': f'https://huggingface.co/{MODEL_ID}/tree/{REVISION}'}
    (args.output / 'model_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Modelo descargado y verificado: {sum(sizes.values())} bytes')


if __name__ == '__main__':
    main()
