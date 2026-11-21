import argparse
import json
from pathlib import Path
from cs_rag_security.ingestion import audit, load_pages, chunks
from cs_rag_security.retrieval import Index


def main():
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['audit', 'index', 'query', 'chat', 'evaluate', 'quality'])
    p.add_argument('--corpus', default='data/corpus_unsa')
    p.add_argument('--index', default='data/vector_db/index.json')
    p.add_argument('--question', default='¿Qué regula la evaluación por competencias?')
    p.add_argument('--top-k', type=int, default=5)
    p.add_argument('--mode', default='C_defensa_propuesta')
    p.add_argument('--provider', choices=['mock', 'local', 'api'], default='mock')
    p.add_argument('--documental', action='store_true')
    p.add_argument('--output', default='results/offline')
    p.add_argument('--annotations', default=None, help='Ruta a archivo CSV o JSON de anotaciones')
    p.add_argument('--mapping', default=None, help='Ruta a archivo JSON de mapeo ciego de casos')
    p.add_argument('--traces', default=None, help='Ruta a archivo de trazas experimentales T16 (JSON o CSV)')
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
    elif args.command == 'quality':
        from cs_rag_security.evaluation import evaluate_quality
        ann_path = args.annotations or 'docs/evaluation/plantilla_anotacion_qa.csv'
        out_dir = Path(args.output)
        report = evaluate_quality(ann_path, args.mapping, traces_source=args.traces)
        out_dir.mkdir(parents=True, exist_ok=True)
        report.save_json(out_dir / 'quality_metrics.json')
        report.save_csv(out_dir / 'quality_metrics.csv')
        report.save_comparison_csv(out_dir / 'quality_summary_comparison.csv')
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        from cs_rag_security.evaluation import run
        print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
