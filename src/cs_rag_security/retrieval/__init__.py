"""Fallback TF-IDF coseno local, sin embeddings ni descargas."""
import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

STOP = set('de la el los las un una y o en por para con que se del al es a como cual cuales segun'.split())


def tokens(text):
    text = ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if unicodedata.category(c) != 'Mn')
    return [t for t in re.findall(r'[a-z0-9]+', text) if t not in STOP and len(t) > 1]


class Index:
    method = 'fallback_textual_tfidf_coseno_v1'

    def __init__(self, chunks, *, tokenizer=tokens):
        self.chunks = chunks
        self.tokenizer = tokenizer
        counts = [Counter(tokenizer(c['texto'])) for c in chunks]
        df = Counter(t for c in counts for t in c)
        self.idf = {t: math.log((1 + len(chunks)) / (1 + n)) + 1 for t, n in df.items()}
        self.vectors = [self.vector(c) for c in counts]

    def vector(self, counts):
        v = {t: (1 + math.log(n)) * self.idf[t] for t, n in counts.items() if t in self.idf}
        norm = math.sqrt(sum(x*x for x in v.values())) or 1
        return {t: x / norm for t, x in v.items()}

    def search(self, question, k=5, *, document_ids=None):
        if not 1 <= k <= 100:
            raise ValueError('top-k entre 1 y 100')
        q = self.vector(Counter(self.tokenizer(question)))
        scores = [
            (sum(q.get(t, 0) * v for t, v in vec.items()), i)
            for i, vec in enumerate(self.vectors)
            if not document_ids or self.chunks[i].get('documento_id') in document_ids
        ]
        return [{**self.chunks[i], 'score': s} for s, i in sorted(scores, key=lambda x: (-x[0], x[1]))[:k] if s > 0]

    def save(self, path, manifest):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'method': self.method, 'manifest': manifest, 'chunks': self.chunks}, ensure_ascii=False), encoding='utf-8')

    @classmethod
    def load(cls, path, *, tokenizer=tokens):
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if data['method'] != cls.method:
            raise ValueError('Versión de índice incompatible')
        return cls(data['chunks'], tokenizer=tokenizer)
