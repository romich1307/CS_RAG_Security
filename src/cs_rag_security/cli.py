import argparse
import json
from pathlib import Path
from cs_rag_security.ingestion import audit, load_pages, chunks
from cs_rag_security.retrieval import Index


def main():
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['audit', 'index', 'query', 'chat', 'evaluate', 'quality', 'audit-experiment', 'paper-artifacts'])
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
    p.add_argument('--runs', nargs='+', default=None, help='Rutas a corridas para auditoría o artefactos de artículo')
    p.add_argument('--security-metrics', default=None, help='Ruta a archivo de métricas de seguridad T19')
    p.add_argument('--force', action='store_true', help='Sobrescribir directorio de salida')
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
    elif args.command == 'audit-experiment':
        from cs_rag_security.evaluation.audit_experiment import audit_experiments
        run_targets = args.runs or ['results/llm_baseline', 'results/offline_20261117_final', 'results/piloto_ollama_pr7.json']
        audit_rep = audit_experiments(run_targets, annotations_path=args.annotations, mapping_path=args.mapping)
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        audit_rep.save_json(out_dir / 'audit_report.json')
        audit_rep.save_markdown(out_dir / 'audit_report.md')
        print(json.dumps(audit_rep.to_dict(), ensure_ascii=False, indent=2))
    elif args.command == 'paper-artifacts':
        from cs_rag_security.evaluation.paper import generate_paper_artifacts
        result = generate_paper_artifacts(
            output_dir=args.output,
            run_paths=args.runs,
            annotations_path=args.annotations,
            mapping_path=args.mapping,
            traces_path=args.traces,
            security_metrics_path=args.security_metrics,
            force=args.force,
        )
        print(json.dumps(result['manifest'], ensure_ascii=False, indent=2))
    else:
        from cs_rag_security.evaluation import run
        print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
