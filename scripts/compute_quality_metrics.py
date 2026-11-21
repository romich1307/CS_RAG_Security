"""Script para computar métricas de calidad de respuestas (T18).

Permite procesar archivos de evaluación humana según la rúbrica oficial T10 v0.2
y generar informes agregados en JSON y CSV compatibles con T20 y el futuro artículo.
"""

import argparse
import json
import sys
from pathlib import Path

# Añadir src al path si se ejecuta como script directo
src_dir = Path(__file__).resolve().parent.parent / 'src'
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from cs_rag_security.evaluation.quality import evaluate_quality, TARGET_PIPELINE, TARGET_LLM_RAW, CONDITIONS


def format_pct(rate_percent, numerator, denominator):
    if denominator == 0 or rate_percent is None:
        return "N/A (0/0)"
    return f"{rate_percent}% ({numerator}/{denominator})"


def main():
    parser = argparse.ArgumentParser(
        description="Calcula métricas de calidad de respuestas a partir de anotaciones humanas (T18)."
    )
    parser.add_argument(
        '--annotations',
        type=str,
        default='docs/evaluation/plantilla_anotacion_qa.csv',
        help='Ruta al archivo CSV o JSON de anotaciones humanas.',
    )
    parser.add_argument(
        '--mapping',
        type=str,
        default=None,
        help='Ruta al archivo JSON de mapeo ciego (asocia caso_ciego_id con condición experimental A/B/C y target).',
    )
    parser.add_argument(
        '--traces',
        type=str,
        default=None,
        help='Ruta a archivo de trazas experimentales T16 (JSON o CSV) para fundamentar motivos de abstención.',
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Directorio de salida donde escribir quality_metrics.json, quality_metrics.csv y quality_summary_comparison.csv.',
    )
    parser.add_argument(
        '--no-consensus',
        action='store_true',
        help='Desactiva la resolución de consenso (evalúa todas las filas sin priorizar estado consensuado).',
    )

    args = parser.parse_args()

    ann_path = Path(args.annotations)
    if not ann_path.exists():
        print(f"Error: Archivo de anotaciones no encontrado: {ann_path}", file=sys.stderr)
        sys.exit(1)

    print(f"=== CS_RAG_Security — Evaluación de Calidad de Respuestas (T18) ===")
    print(f"Cargando anotaciones desde: {ann_path}")

    report = evaluate_quality(
        annotations=ann_path,
        blind_mapping=args.mapping,
        resolve_consensus=not args.no_consensus,
        traces_source=args.traces,
    )

    res = report.resumen_global
    acc = res.get('contabilidad_casos', {})
    print("\n--- Resumen de Casos ---")
    print(f"Total registros cargados:     {acc.get('total_anotaciones', 0)}")
    print(f"Casos evaluados (completos):  {acc.get('casos_evaluables', 0)}")
    print(f"Casos pendientes de revisión: {acc.get('casos_pendientes', 0)}")
    print(f"Casos no evaluables:          {acc.get('casos_no_evaluables', 0)}")

    cal = res.get('calidad_contenido', {})
    ex_h = cal.get('exactitud_humana_contenido', {})
    parc = cal.get('tasa_respuestas_parciales', {})
    inc = cal.get('tasa_respuestas_incorrectas', {})

    print("\n--- Calidad de Contenido (sobre total de consultas evaluables) ---")
    print(f"Exactitud humana (correctas): {format_pct(ex_h.get('rate_percent'), ex_h.get('numerator'), ex_h.get('denominator'))}")
    print(f"Respuestas parciales:         {format_pct(parc.get('rate_percent'), parc.get('numerator'), parc.get('denominator'))}")
    print(f"Respuestas incorrectas:       {format_pct(inc.get('rate_percent'), inc.get('numerator'), inc.get('denominator'))}")

    abst = res.get('abstencion_y_adecuacion', {})
    t_abs = abst.get('tasa_abstencion', {})
    adeq = abst.get('adecuacion_abstenciones', {})
    inad = abst.get('tasa_abstenciones_inadecuadas', {})

    print("\n--- Abstención y Adecuación ---")
    print(f"Tasa de abstención:           {format_pct(t_abs.get('rate_percent'), t_abs.get('numerator'), t_abs.get('denominator'))}")
    print(f"Adecuación de abstenciones:   {format_pct(adeq.get('rate_percent'), adeq.get('numerator'), adeq.get('denominator'))}")
    print(f"Abstenciones inadecuadas:     {format_pct(inad.get('rate_percent'), inad.get('numerator'), inad.get('denominator'))}")

    cit = res.get('validez_y_sustento_citas', {})
    val_cit = cit.get('citas_validas_completas', {})
    pert = cit.get('pertenencia_contexto', {}).get('citas_pertenecen_si', {})
    sust = cit.get('sustento_factual', {}).get('sustento_completo', {})
    brecha = cit.get('brecha_pertenencia_sin_sustento', {}).get('total_pertenecen_sin_sustento_completo', {})

    print("\n--- Validez y Sustento de Citas (sobre respuestas sustantivas) ---")
    print(f"Citas válidas y completas:    {format_pct(val_cit.get('rate_percent'), val_cit.get('numerator'), val_cit.get('denominator'))}")
    print(f"Pertenecen al contexto:       {format_pct(pert.get('rate_percent'), pert.get('numerator'), pert.get('denominator'))}")
    print(f"Sustento factual completo:    {format_pct(sust.get('rate_percent'), sust.get('numerator'), sust.get('denominator'))}")
    print(f"Brecha (en contexto sin sust):{format_pct(brecha.get('rate_percent'), brecha.get('numerator'), brecha.get('denominator'))}")

    # Separación Pipeline vs LLM Raw
    pipe_slice = report.por_origen_respuesta.get(TARGET_PIPELINE, {})
    raw_slice = report.por_origen_respuesta.get(TARGET_LLM_RAW, {})
    if pipe_slice.get('contabilidad_casos', {}).get('casos_evaluables', 0) > 0 or raw_slice.get('contabilidad_casos', {}).get('casos_evaluables', 0) > 0:
        print("\n--- Comparación Pipeline vs LLM Raw ---")
        p_acc = pipe_slice.get('calidad_contenido', {}).get('exactitud_humana_contenido', {})
        r_acc = raw_slice.get('calidad_contenido', {}).get('exactitud_humana_contenido', {})
        p_abs = pipe_slice.get('abstencion_y_adecuacion', {}).get('tasa_abstencion', {})
        r_abs = raw_slice.get('abstencion_y_adecuacion', {}).get('tasa_abstencion', {})
        print(f"Pipeline exactitud:  {format_pct(p_acc.get('rate_percent'), p_acc.get('numerator'), p_acc.get('denominator'))} | Abstención: {format_pct(p_abs.get('rate_percent'), p_abs.get('numerator'), p_abs.get('denominator'))}")
        print(f"LLM Raw exactitud:   {format_pct(r_acc.get('rate_percent'), r_acc.get('numerator'), r_acc.get('denominator'))} | Abstención: {format_pct(r_abs.get('rate_percent'), r_abs.get('numerator'), r_abs.get('denominator'))}")

    # Si se especificó directorio de salida, guardar archivos
    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        json_path = out_dir / 'quality_metrics.json'
        csv_path = out_dir / 'quality_metrics.csv'
        comp_path = out_dir / 'quality_summary_comparison.csv'

        report.save_json(json_path)
        report.save_csv(csv_path)
        report.save_comparison_csv(comp_path)
        print(f"\nResultados guardados exitosamente en:\n  - {json_path}\n  - {csv_path}\n  - {comp_path}")


if __name__ == '__main__':
    main()
