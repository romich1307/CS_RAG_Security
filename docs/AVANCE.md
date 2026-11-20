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

## Fase 6 — Diagnóstico y corrección de citas para T11 (rama feature/t11-diagnostico-citas)
- **Prompt de C (v2):** Se actualizó la condición experimental `C_defensa_propuesta`
  incorporando instrucción estricta de citación exacta `[archivo.pdf p. N]`, extracción
  exclusiva desde las claves `"archivo"` y `"pagina"` del contexto JSON no confiable,
  y un ejemplo breve representativo (`[RCU-0161-2021.pdf p. 3]`).
- **Preservación experimental A y B:** Las condiciones A (`A_sin_defensa`) y B
  (`B_defensa_basica`) se mantienen en su versión original (v1) para garantizar la
  reproducibilidad e integridad de las comparaciones controladas.
- **Trazabilidad `raw_response`:** El pipeline y el evaluador registran `raw_response`
  con la salida textual íntegra del modelo previa a la validación, preservándose ante
  abstenciones sin sustituir la respuesta final validada (`response`) ni distorsionar
  las métricas de evaluación.
- **Validador estricto:** Se mantiene la verificación estricta de pertenencia al
  contexto recuperado admisible (`allowed`), sin adición automática de citas ni
  relajación de seguridad.
- **Verificación:** 37 pruebas unitarias pasando (`PYTHONPATH=src .venv/bin/python -m pytest`).
  Validación exitosa en consulta real con Ollama y `qwen2.5:3b` en GQ001 modo documental C,
  obteniendo cita exacta válida sin abstención.

## Fase 7 — Ejecución y revisión final de T11 (Baseline Ollama A_sin_defensa)
- **Ejecución experimental:** Ejecutado script reproducible `scripts/run_t11_baseline.py`
  sobre las 10 consultas legítimas seleccionadas del dataset gold (GQ004, GQ006, GQ012,
  GQ016, GQ023, GQ027, GQ034, GQ036, GQ038, GQ040) bajo la condición `A_sin_defensa`
  (baseline de referencia sin defensas), utilizando el modelo local Ollama `qwen2.5:3b`
  (digest `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`),
  `temperature=0`, `seed=42`, `top_k=5`, en modo documental.
- **Validador de citas compartido y asimetría de prompt en Modo A:**
  - El validador estricto de citas (`[archivo.pdf p. N]` perteneciente al contexto admisible)
    opera a nivel de pipeline en `cs_rag_security.pipeline.answer()` y es compartido por
    las tres condiciones experimentales (A, B y C).
  - A diferencia de B y C (v2), el modo `A_sin_defensa` no utiliza instrucciones defensivas
    ni directivas de formato de citas en su prompt, concatenando únicamente la pregunta y
    el texto plano de los fragmentos recuperados en el mensaje de usuario.
  - Al no recibir directiva de citación formal, el LLM generó respuestas sustantivas en lenguaje
    natural sin el patrón `[archivo.pdf p. N]`, provocando que el validador del pipeline
    consigne abstención (`Me abstengo: la salida del modelo carece de citas válidas del contexto.`)
    en las 10 consultas.
  - Esta diferencia metodológica y su efecto se documentan explícitamente sin alterar el
    diseño experimental ni las condiciones del baseline A.
- **Tratamiento metodológico de las abstenciones:**
  - Conforme a la [rúbrica de evaluación QA v0.1](evaluation/rubrica_qa.md), las 10 abstenciones
    no se clasifican automáticamente como respuestas incorrectas; en evaluación humana
    corresponden a `calidad_respuesta = 'no_aplica'`, evaluándose por separado la adecuación
    de la abstención (`abstencion_adecuada`) y la suficiencia de la evidencia (`evidencia_disponible`).
  - La respuesta sustantiva original del modelo se conserva íntegra en el campo `raw_response`,
    permitiendo evaluar su fidelidad factual y contenido en la evaluación cualitativa de T12.
- **Diferenciación y preservación de trazas:**
  - Se confirmó en las 10 trazas que `raw_response` (texto crudo del modelo) y `response`
    (salida validada post-pipeline) están estrictamente diferenciados.
  - Las 10 trazas originales en `results/llm_baseline/traces.json` y `traces.csv` permanecen intactas.
- **Material ciego para T12:**
  - Generados `results/llm_baseline/t12_material_ciego.json` y `results/llm_baseline/t12_evaluacion_ciega.csv`
    con identificadores ciegos (`CIEGO_01` a `CIEGO_10`) para el evaluador humano (León).
  - Se verificó que el material ciego no incluye respuestas gold (`respuesta_referencia`)
    ni referencias esperadas de las fuentes gold, garantizando la evaluación a ciegas.
- **Auditoría de hashes y confidencialidad:**
  - Los hashes registrados en `results/llm_baseline/manifest.json` para los 8 módulos de `src/`,
    el índice (`index.json`) y el gold (`gold_questions.json`) coinciden exactamente con el
    código y artefactos ejecutados.
  - Se verificó que los archivos nuevos no contienen credenciales, rutas privadas ni información
    confidencial que deba ser excluida de publicación.
- **Validación automatizada:**
  - 37 pruebas pasando (`PYTHONPATH=src .venv/bin/python -m pytest`).
  - Verificación de formato y espacios limpia (`git diff --check`).

Pendientes externos/científicos: configurar y ejecutar modelo local real; registrar
digest/versión del servidor y hardware; ampliar ataques y validar en conjuntos
independientes; revisión humana OCR, fidelidad semántica y vigencia; incorporar los
tres textos ausentes solo tras obtener fuentes verificadas. No se atribuye eficacia
de defensa frente a LLM con los resultados mock disponibles.
