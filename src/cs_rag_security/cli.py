import argparse
import json
from pathlib import Path
from cs_rag_security.ingestion import audit, load_pages, chunks
from cs_rag_security.retrieval import Index


def main():
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['audit', 'index', 'query', 'chat', 'evaluate'])
    p.add_argument('--corpus', default='data/corpus_unsa')
    p.add_argument('--index', default='data/vector_db/index.json')
    p.add_argument('--question', default='¿Qué regula la evaluación por competencias?')
    p.add_argument('--top-k', type=int, default=5)
    p.add_argument('--mode', default='C_defensa_propuesta')
    p.add_argument('--provider', choices=['mock', 'local'], default='mock')
    p.add_argument('--documental', action='store_true')
    p.add_argument('--output', default='results/offline')
    args = p.parse_args()
    if args.command in ('audit', 'index'):
        report = audit(args.corpus)
        if args.command == 'index':
            idx = Index(chunks(load_pages(args.corpus)))
            idx.save(args.index, report)
            report['chunks'] = len(idx.chunks)
            report['method'] = idx.method
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.command == 'query':
        print(json.dumps(Index.load(args.index).search(args.question, args.top_k), ensure_ascii=False, indent=2))
    elif args.command == 'chat':
        from cs_rag_security.pipeline import answer
        print(json.dumps(answer(Index.load(args.index), args.question, args.mode, args.provider, args.top_k, args.documental), ensure_ascii=False, indent=2))
    else:
        from cs_rag_security.evaluation import run
        print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
