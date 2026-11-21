"""Embeddings multilingües ONNX locales y almacén exacto de vectores normalizados."""
import hashlib
import json
from pathlib import Path


def file_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class LocalEncoder:
    """MiniLM cuantizado; tokenizador y pesos ya verificados en disco."""

    def __init__(self, model_directory, threads=4):
        self.directory = Path(model_directory).resolve()
        if not self.directory.is_dir():
            raise ValueError('Se requiere la carpeta de un modelo local ya disponible.')
        if not 1 <= threads <= 32:
            raise ValueError('Número de hilos entre 1 y 32')
        try:
            import numpy as np
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ImportError as exc:
            raise RuntimeError('Instala las dependencias opcionales semantic del proyecto.') from exc
        self.np = np
        manifest_path = self.directory / 'model_manifest.json'
        self.manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        self.manifest_sha256 = file_hash(manifest_path)
        for name, expected in self.manifest['files_sha256'].items():
            path = (self.directory / name).resolve()
            if not path.is_relative_to(self.directory) or not path.is_file() or file_hash(path) != expected:
                raise ValueError('Integridad de los archivos del modelo local')
        model_path = (self.directory / self.manifest['onnx_file']).resolve()
        if not model_path.is_relative_to(self.directory) or self.manifest['onnx_file'] not in self.manifest['files_sha256']:
            raise ValueError('Archivo ONNX fuera del manifiesto')
        if 'tokenizer.json' not in self.manifest['files_sha256']:
            raise ValueError('Tokenizador fuera del manifiesto')
        self.max_length = int(self.manifest['max_length'])
        if not 2 <= self.max_length <= 512 or self.manifest['pooling'] != 'attention_mask_mean':
            raise ValueError('Configuración de embeddings no admitida')
        self.tokenizer = Tokenizer.from_file(str(self.directory / 'tokenizer.json'))
        self.pad_id = self.tokenizer.token_to_id('<pad>')
        if self.pad_id is None:
            raise ValueError('Tokenizador sin token de padding esperado')
        self._configure_tokenizer()
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(str(model_path), sess_options=options, providers=['CPUExecutionProvider'])
        self.input_names = {item.name for item in self.session.get_inputs()}
        if not self.input_names <= {'input_ids', 'attention_mask', 'token_type_ids'}:
            raise ValueError('Entradas ONNX no admitidas')
        self.threads = threads

    def _configure_tokenizer(self):
        self.tokenizer.enable_truncation(max_length=self.max_length)
        self.tokenizer.enable_padding(pad_id=self.pad_id, pad_token='<pad>')

    def token_lengths(self, texts):
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        try:
            return [len(record.ids) for record in self.tokenizer.encode_batch(texts)]
        finally:
            self._configure_tokenizer()

    def encode(self, texts, batch_size=16):
        if not texts or not 1 <= batch_size <= 128:
            raise ValueError('Se requieren textos y un lote entre 1 y 128')
        np = self.np
        vectors = []
        for offset in range(0, len(texts), batch_size):
            records = self.tokenizer.encode_batch(texts[offset:offset + batch_size])
            inputs = {
                'input_ids': np.asarray([record.ids for record in records], dtype=np.int64),
                'attention_mask': np.asarray([record.attention_mask for record in records], dtype=np.int64),
                'token_type_ids': np.asarray([record.type_ids for record in records], dtype=np.int64),
            }
            token_vectors = self.session.run(None, {name: inputs[name] for name in self.input_names})[0]
            if token_vectors.ndim != 3:
                raise ValueError('Se esperaban embeddings por token en la salida ONNX')
            mask = inputs['attention_mask'][..., None].astype(np.float32)
            pooled = (token_vectors * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1e-9)
            normalized = pooled / np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-9)
            if not np.isfinite(normalized).all():
                raise ValueError('Embeddings no finitos')
            vectors.append(normalized.astype(np.float32))
        return np.concatenate(vectors, axis=0)


class SemanticIndex:
    method = 'onnx_minilm_multilingual_quint8_avx2_coseno_v1'

    def __init__(self, chunks, model_directory, threads=4):
        if not chunks:
            raise ValueError('El índice semántico requiere fragmentos.')
        self.encoder = LocalEncoder(model_directory, threads)
        self.model_directory = self.encoder.directory
        self.chunks = list(chunks)
        texts = [chunk['texto'] for chunk in self.chunks]
        self.token_lengths = self.encoder.token_lengths(texts)
        self.vectors = self.encoder.encode(texts)

    def search(self, question, k=5):
        if not 1 <= k <= 100:
            raise ValueError('top-k entre 1 y 100')
        if not question.strip():
            return []
        scores = self.vectors @ self.encoder.encode([question])[0]
        ranked = self.encoder.np.argsort(-scores, kind='stable')[:k]
        return [{**self.chunks[int(i)], 'score': float(scores[i])} for i in ranked]

    def save(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=False)
        chunks_path, vectors_path = directory / 'chunks.json', directory / 'vectors.npy'
        chunks_path.write_text(json.dumps(self.chunks, ensure_ascii=False), encoding='utf-8')
        self.encoder.np.save(vectors_path, self.vectors, allow_pickle=False)
        manifest = {'method': self.method, 'model_manifest_sha256': self.encoder.manifest_sha256,
                    'shape': list(self.vectors.shape), 'chunks_sha256': file_hash(chunks_path),
                    'vectors_sha256': file_hash(vectors_path), 'token_lengths': self.token_lengths}
        (directory / 'index.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')

    @classmethod
    def load(cls, directory, model_directory, threads=4):
        directory = Path(directory)
        manifest = json.loads((directory / 'index.json').read_text(encoding='utf-8'))
        if (manifest['method'] != cls.method or file_hash(directory / 'chunks.json') != manifest['chunks_sha256'] or
                file_hash(directory / 'vectors.npy') != manifest['vectors_sha256']):
            raise ValueError('Índice semántico incompatible o alterado')
        self = cls.__new__(cls)
        self.encoder = LocalEncoder(model_directory, threads)
        if self.encoder.manifest_sha256 != manifest['model_manifest_sha256']:
            raise ValueError('El modelo no coincide con el índice')
        self.model_directory = self.encoder.directory
        self.chunks = json.loads((directory / 'chunks.json').read_text(encoding='utf-8'))
        self.vectors = self.encoder.np.load(directory / 'vectors.npy', allow_pickle=False)
        self.token_lengths = manifest['token_lengths']
        if (list(self.vectors.shape) != manifest['shape'] or self.vectors.ndim != 2 or
                self.vectors.shape[0] != len(self.chunks) or not self.encoder.np.isfinite(self.vectors).all()):
            raise ValueError('Dimensiones del índice semántico incompatibles')
        return self
