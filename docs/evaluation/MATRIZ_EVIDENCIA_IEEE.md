# Matriz de afirmaciones cuantitativas para IEEE

Los CSV de [proporciones](IEEE_PROPORCIONES_AGREGADAS.csv) y [latencias](IEEE_LATENCIAS_AGREGADAS.csv) son la matriz por cifra. Cada fila identifica corrida, versión o brazo, proveedor, denominador, regla de cómputo y origen. Las tasas observadas incluyen Wilson bilateral al 95 %. Las filas sin estimación conservan el motivo y dejan vacíos el porcentaje y el intervalo.

| Estado | Afirmación admisible | Archivo y campo de evidencia | Alcance y límite |
| --- | --- | --- | --- |
| Confirmada en artefacto | Hit@1 6/13 y Hit@5 11/13 en cada método; Hit@3 TF-IDF 9/13 y MiniLM 11/13. Exploratorio Hit@1 20/40 y 15/40, Hit@5 34/40 y 30/40. | `results/retrieval_t08_20261119_final/{retrieval.csv,metrics.json,manifest.json}`; `primary` y `exploratory_all_original_gold` | CPU local sin LLM. Los 13 primarios se solapan con las 40 consultas. Cotejo asistido. |
| Confirmada en artefacto | Exactitud RAW 11/30 y FINAL 4/30; abstención RAW 4/30 y FINAL 21/30. T18 perdió 7/30 RAW correctas en el control de citas. | `results/llm_abc_local/t20_cierre_verificado_20261125/quality_metrics.json`; `por_origen_respuesta`, `emparejamiento_pipeline_vs_llm` | Ollama local, anotación histórica sin acuerdo interevaluador independiente. T17 tiene 10 consultas compartidas por los tres brazos. |
| Confirmada en artefacto | A, B y C obtuvieron 2/10, 5/10 y 4/10 correctas RAW. FINAL 0/10, 0/10 y 4/10. En C FINAL, 9/9 sustantivas con citas formales y 6/9 con sustento completo. | Mismo `quality_metrics.json`; `cruzado_condicion_origen` | Los denominadores de citas excluyen abstenciones. |
| Confirmada en artefacto | Abstenciones adecuadas 13/25 en ambas etapas, inadecuadas 12/25 y 12/21 FINAL. | Mismo `quality_metrics.json`; `resumen_global` y `por_origen_respuesta.pipeline` | Ollama local. Los dos denominadores responden a cortes distintos. |
| Confirmada en artefacto | ASR RAW A 10/20, B y C 0/20. ASR FINAL 0/20 en cada brazo. | `results/t19_inyecciones_20_20261125_003544/{revision_rubrica_raw_final.json,security_metrics.json}` | Ollama local, escenarios repetidos por brazo. Exposición efectiva no confirmada; no equiparar marcador con éxito. |
| Confirmada en artefacto | Recall 15/20 y FPR 5/20 en controles históricamente etiquetados. | `results/t19_inyecciones_20_20261125_003544/security_metrics.json`; `results/detector_benign_v2/metrics.json` | Diagnóstico heurístico, no eficacia generativa. |
| Confirmada en bytes | T20 cotejado con 6/6 hashes de entradas y 35/35 salidas. | `results/llm_abc_local/t20_cierre_verificado_20261125/manifest.json`; índice histórico en `data/vector_db/t20_verificacion_20261125/data/vector_db/index.json` | Auditoría de procedencia, sin observaciones nuevas. |
| Preliminar | v2/v3, abstenciones 5/6 y 1/6. Hit@1/5 5/5 ambos. Medianas 49,43 s y 62,29 s, n=6. | `csrag-v3-holdout-run/{manifest.json,traces.jsonl,technical.json}`; [informe](MEJORA_CALIDAD_Y_SEGURIDAD_V3.md) | Ollama local. Muestra pequeña. Exactitud y ASR no estimados. Las rutas sin prefijo son expedientes privados locales. |
| Preliminar | v3/v4, Hit@1 2/4 y 4/4; todas las páginas citadas 2/4 y 4/4; abstención 2/5 y 1/5; completa automática 2/5 y 0/5. Medianas 60,95 s y 57,08 s, n=5. | `csrag-v4-holdout-run/{manifest.json,traces.jsonl,technical.json}`; [informe](INFORME_MEJORA_REAL_V4.md) | Ollama local. Este conjunto ya se utilizó como diagnóstico de v5. |
| Preliminar | v5 repite cinco consultas de diagnóstico. Hit@1/3/5 4/4; todas las páginas citadas 2/4; citas formales 4/4 de sustantivas; abstención 1/5; completa automática 1/5. Mediana 33,76 s, n=5. | `csrag-v5-pilot-revision/{manifest.json,technical.json,traces.jsonl}`; [diagnóstico](CIERRE_V5_DIAGNOSTICO_Y_CAMBIOS.md) | Ollama local. Falló la puerta multifuente. Sin comparación confirmatoria. |
| Confirmada en prueba local | 249/250 aprobadas, 0/250 fallidas, 1/250 omitida para v5. | `PYTHONPATH=src .venv/bin/python -m pytest`; [decisión](DECISION_DE_CIERRE_V5.md) | Pruebas de software. MiniLM opcional no configurado. |
| Pendiente | Exactitud humana RAW/FINAL, sustento completo, adecuación de abstenciones y ASR para perfiles exploratorios. Comparación independiente v4/v5. | Hojas ciegas privadas y [decisión de cierre](DECISION_DE_CIERRE_V5.md) | Faltan revisiones independientes y evidencia adversaria comparable. La muestra independiente no se ejecutó. |

Para figuras históricas, conservar T08, T18 y T19 en paneles distintos.
Una figura de abstenciones debe identificar si usa todas las consultas
o solo abstenciones. Citas formales y sustento requieren series separadas.
Las cifras de piloto solo pueden figurar con ese rótulo. Los porcentajes
históricos no se sustituyen. La interpretación y los intervalos detallados
están en el [consolidado](INFORME_FINAL_METRICAS_ARTICULO_IEEE.md).
