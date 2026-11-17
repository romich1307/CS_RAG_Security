# Evidencias de ejecución — 2026-11-17

Se ejecutaron desde la raíz, en .venv con Python 3.14.10:

| Comprobación | Resultado observado |
| --- | --- |
| `PYTHONPATH=src .venv/bin/python -m pytest -q` | 9 passed |
| `.venv/bin/python -m pytest -q -m 'not corpus'` | 8 passed, 1 deselected |
| `.venv/bin/python -m pip check` | No broken requirements found |
| `python -m cs_rag_security.cli audit` | 11 oficiales, 1 histórico, 137 páginas piloto, 115 OCR, 40 gold; hashes PDF coincidentes |
| `python -m cs_rag_security.cli index` | 2284 fragmentos, fallback_textual_tfidf_coseno_v1 |
| Consulta documental, top-3 | Mock visible; recupera RCU-0161-2021.pdf p. 3 y RCU-0501-2020.pdf p. 4 |
| Consulta de requisitos vigentes de matrícula | Abstención por falta de evidencia fiable/vigencia |
| AppTest de Streamlit | Formulario y consulta sin excepciones |
| Evaluación final | 144 trazas: 48 casos por configuración, proveedor mock |
| Verificación de hashes fuente contra manifiesto | Coinciden todos los módulos src |
| `git diff --check` | Sin errores de espacios |

[Evidencia CLI reducida](evidencias/ejecucion.json) preserva etiquetas, citas y
abstención sin copiar texto PDF. [Manifiesto](../results/offline_20261117_final/manifest.json),
[métricas](../results/offline_20261117_final/metrics.json),
[trazas CSV](../results/offline_20261117_final/traces.csv) y
[gráfico SVG](../results/offline_20261117_final/detector.svg) proceden de la ejecución.
El flujo GitHub Actions está escrito; no se ha ejecutado en GitHub ni se hizo push.
No hay evidencia de ejecución de un LLM real, porque no fue configurado.
