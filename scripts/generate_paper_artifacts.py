#!/usr/bin/env python3
"""Script reproducible para la generación de artefactos del artículo científico (T20).

Uso:
    python scripts/generate_paper_artifacts.py [--output results/paper_artifacts_<timestamp>]
                                               [--runs results/llm_baseline results/offline_20261117_final]
                                               [--annotations results/t12_evaluacion/t12_evaluacion_ciega.csv]
                                               [--mapping results/t12_evaluacion/t12_material_ciego.json]
                                               [--force]
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Agregar src al path si se ejecuta como script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cs_rag_security.evaluation.paper import generate_paper_artifacts


def main():
    default_out = f"results/paper_artifacts_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    parser = argparse.ArgumentParser(
        description="Generación reproducible de tablas, figuras, auditoría y manifiesto para el artículo científico (T20)."
    )
    parser.add_argument(
        "--output",
        default=default_out,
        help=f"Directorio de salida (por defecto: {default_out}).",
    )
    parser.add_argument(
        "--runs",
        nargs="+",
        default=[
            "results/llm_baseline",
            "results/offline_20261117_final",
            "results/piloto_ollama_pr7.json",
        ],
        help="Rutas a directorios o archivos de corridas experimentales a auditar.",
    )
    parser.add_argument(
        "--annotations",
        default="results/t12_evaluacion/t12_evaluacion_ciega.csv",
        help="Ruta a archivo de anotaciones de evaluación humana (T12).",
    )
    parser.add_argument(
        "--mapping",
        default="results/t12_evaluacion/t12_material_ciego.json",
        help="Ruta a archivo JSON de mapeo ciego de casos (T12).",
    )
    parser.add_argument(
        "--traces",
        default="results/llm_baseline/traces.json",
        help="Ruta a archivo de trazas de telemetría de referencia.",
    )
    parser.add_argument(
        "--security-metrics",
        default=None,
        help="Ruta opcional a métricas de seguridad T19 (si disponibles).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Permitir sobrescribir el directorio de salida si ya existe.",
    )

    args = parser.parse_args()

    print(f"=== Generando artefactos del artículo científico (T20) ===")
    print(f"Directorio de salida: {args.output}")
    print(f"Corridas de entrada: {args.runs}")
    print(f"Anotaciones humanas: {args.annotations}")

    try:
        res = generate_paper_artifacts(
            output_dir=args.output,
            run_paths=args.runs,
            annotations_path=args.annotations if Path(args.annotations).exists() else None,
            mapping_path=args.mapping if Path(args.mapping).exists() else None,
            traces_path=args.traces if Path(args.traces).exists() else None,
            security_metrics_path=args.security_metrics,
            force=args.force,
        )
    except FileExistsError as e:
        print(f"\n[ERROR DE PROTECCIÓN CONTRA SOBRESCRITURA] {e}", file=sys.stderr)
        sys.exit(1)

    print("\n✓ Generación exitosa:")
    print(f"  - Reporte de auditoría: {args.output}/audit_report.json y .md")
    print(f"  - Tablas científicas (CSV y MD): {len(res['tables_saved'])} tablas en {args.output}/tables/")
    print(f"  - Figuras científicas (SVG y PNG): {len(res['figures_saved'])} figuras en {args.output}/figures/")
    print(f"  - Manifiesto con hashes: {args.output}/manifest.json")
    print(f"  - Documentación: {args.output}/DOCUMENTACION_REPRODUCCION.md")
    print(f"  - Dictamen auditoría global: {res['manifest']['auditoria_resumen']['dictamen_global']}")


if __name__ == "__main__":
    main()
