import json
from pathlib import Path
from cs_rag_security.defenses import MODES, detect, prepare


def test_labeled_hard_cases_and_false_alarms():
    cases = {c['id']: c for c in map(json.loads, Path('experiments/attacks.jsonl').read_text().splitlines())}
    # Estas limitaciones deben seguir visibles; no adaptar etiquetas para mejorar métricas.
    assert cases['a4']['attack'] and not detect(cases['a4']['text'])['suspicious']
    assert not cases['b3']['attack'] and detect(cases['b3']['text'])['suspicious']
    assert detect(cases['a3']['text'])['suspicious']
    for c in cases.values():
        hit = {'chunk_id': c['id'], 'archivo_pdf': 'SINTETICO.pdf', 'pagina_pdf': 1, 'texto': c['text']}
        kept, messages, log = prepare('evaluación', [hit], MODES[2])
        assert bool(kept) != log[0]['suspicious']
        assert len(prepare('evaluación', [hit], MODES[0])[0]) == 1
        assert len(prepare('evaluación', [hit], MODES[1])[0]) == 1
