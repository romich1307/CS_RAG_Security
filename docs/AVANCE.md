# Avance

## Fases 0 y 1 — implementación, 2026-11-17
Leídos íntegramente encargo, README_PRIMERO y guía de integración. Inspeccionados
metadatos, relaciones, pendientes y tres páginas reales antes de programar.
Repositorio inicialmente sin commits. Punto de partida local y rama feature/rag-mvp.
Entorno .venv creado con Python del sistema. Implementadas auditoría SHA-256 de los
12 PDF, validación de páginas, exclusión histórica estricta y fragmentación por
párrafos/palabras conservando metadatos. Recuperador TF-IDF coseno identificado como
fallback textual offline: no se ha intentado descargar un modelo de embeddings.
No lee gold para construir índice. Índice privado en data/vector_db.

Hallazgo: 137 páginas piloto (115 OCR + 22 nativas); las 140 páginas del inventario
incluyen 3 históricas. Todos los documentos tienen vigencia no certificada.
Ausentes conocidos: RCU-0435-2017, RCU-0317-2026 y RCU-0590-2023; no se descargan
ni se inventan. La modificatoria de matrícula no reemplaza el texto base.

Comprobaciones y evidencias se añadirán tras ejecutar los comandos.

Validación fases 0–1: `.venv/bin/python -m pytest -q tests/test_integrity.py`:
**2 passed**. `python -m cs_rag_security.cli index`: **2284 fragmentos**,
12 hashes PDF coincidentes; consulta CLI top-2 ejecutada y guardada temporalmente
fuera de Git. Instalación inicial falló por DNS del sandbox; reintento autorizado
instaló pytest 8.3.5 y Streamlit 1.41.1. `requirements.lock.txt` registra dependencias
transitivas efectivamente instaladas en Python 3.14. Índice reconstruible sin red.

## Fase 2 — chatbot
Implementados Streamlit, proveedor mock extractivo visible y adaptador Ollama local
activado explícitamente por variable de modelo. Se rechazan destinos remotos y
redirecciones; no se descargan modelos. Por defecto se abstiene ante consultas de
normativa vigente: no hay fuentes certificadas. Modo documental optativo permite
extractos nativos; OCR pendiente se muestra en recuperación pero no fundamenta la
respuesta. Control de citas verifica archivo/página, no corrección semántica.
Validación: `.venv/bin/python -m pytest -q` → **6 passed**, incluyendo AppTest de
Streamlit con consulta, abstención, mock, fronteras A/B/C y proveedor remoto rechazado.
Limitación: adaptador real aún sin modelo/servidor configurado; no se ejecutó un LLM.

## Fase 3 — ataques controlados
A preserva contexto sin separación; B separa roles y delimita contexto no confiable;
C serializa fragmentos en JSON y excluye los detectados por reglas heurísticas v1.
Dataset independiente `experiments/attacks.jsonl`: 4 ataques con objetivo palabra
CANARIO_CONTROL y 4 controles benignos, incluidos ofuscación Unicode, cita benigna
que produce falsa alarma y ataque indirecto sutil no detectado. No toca fuentes.
Pruebas específicas: `pytest -q tests/test_attacks.py tests/test_pipeline.py` →
**4 passed**. Se prueba explícitamente la falsa alarma y el falso negativo;
no se han alterado las etiquetas para mejorar métricas.

## Fase 4 — evaluación offline
Corrida de referencia: `results/offline_20261117_final/`, mock, seed 42, top-k 5,
40 preguntas gold piloto + 8 casos sintéticos × 3 modos = **144 trazas**.
Mismos hits pareados, índice TF-IDF y parámetros para A/B/C. Colección secundaria
por caso: texto sintético + control benigno, sin mezclar con el índice oficial.
Recuperación documental top-5: **34/40** en cada modo. Diagnóstico del detector:
recall **3/4**, FPR **1/4**. Ninguno de los 4 ataques quedó fuera del top-5 sintético.
Emisión del marcador en extractos mock: A **4/4**, B **4/4**, C **1/4**;
esto NO es ASR de LLM. ASR y exactitud piloto de LLM = null. Vigencia: denominador
certificado **0**, exactitud normativa no estimable. Latencias crudas y medias con
sus denominadores figuran en JSON/CSV; no se presentan como rendimiento de un LLM.
Manifiesto incluye hashes PDF/JSONL/índice/datasets/código, versiones, fechas y
umbrales. Gráfico SVG solo del diagnóstico del detector. Falsa alarma b3 y falso
negativo a4 registrados. Una primera corrida fue interrumpida por reinicio del
servidor (solo manifiesto); se conserva localmente sin usarla como evidencia.
Comandos: `python -m cs_rag_security.cli evaluate --output results/<nombre_nuevo>`.
Validación ampliada: `PYTHONPATH=src .venv/bin/python -m pytest -q` → **9 passed**:
pareado de hits, separación ASR/mock, citas inválidas y no sobrescritura de corridas.
Pendiente batería real: no hay LLM configurado, no se consumen APIs ni se baja modelo.

## Fase 5 — documentación y reproducción
Añadidos README con instalación Linux sin sudo, arquitectura, metodología/fórmulas,
amenazas, límites jurídicos/OCR y evidencias CLI reducidas sin texto PDF. Scripts
run_checks.sh y benchmark.sh; workflow GitHub Actions para Python 3.14 con tests
sin corpus privado. CI está preparado, aún no ejecutado en GitHub (sin push).
Comprobación equivalente local: pytest -m 'not corpus' → **8 passed, 1 deselected**.
`pip check`: **No broken requirements found**. Consulta documental CLI: mock visible,
recupera RCU-0161-2021.pdf p. 3; consulta de matrícula vigente: abstención. Hashes del
código src coinciden con el manifiesto final. `git diff --check` sin errores.

Estado: prototipo offline, interfaz, tres defensas y experimentos reproducibles
implementados. PDF, OCR y gold conservados sin modificaciones; índice privado y
corpus excluidos de Git. Rama local feature/rag-mvp, commits descriptivos por etapa.
Sin push, sin APIs pagadas ni modelos descargados.

Pendientes externos/científicos: configurar y ejecutar modelo local real; registrar
digest/versión del servidor y hardware; ampliar ataques y validar en conjuntos
independientes; revisión humana OCR, fidelidad semántica y vigencia; incorporar los
tres textos ausentes solo tras obtener fuentes verificadas. No se atribuye eficacia
de defensa frente a LLM con los resultados mock disponibles.

## Avance de León — 19 de noviembre de 2026

Se continuó T10, cuya preparación de rúbrica y plantilla se había realizado el
18 de noviembre. Con el paquete de Romina se verificaron los hashes de cinco PDF
y se cotejaron las 15 preguntas mediante extracción de texto y revisión de páginas
renderizadas. La revisión del 20 de noviembre confirmó el respaldo de 14 referencias.
GQ040 está respaldada por la p. 2 de RCU-0284-2023. Para GQ030 se registraron las
pp. 7–8 como evidencia necesaria para una cita completa. Los criterios de la rúbrica
0.2 siguen sujetos a revisión. Véase el [cotejo T10](evaluation/cotejo_t10_20261119.md).


T12 sigue pendiente de respuestas reales del LLM. Estos cambios documentan el
avance del 19 de noviembre y la continuación del pendiente de T10 del día 18.
