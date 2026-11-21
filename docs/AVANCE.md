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
- **Prompt de C (v3):** Se actualizó la condición experimental `C_defensa_propuesta`
  sustituyendo el ejemplo específico de `RCU-0161-2021.pdf` por el formato genérico
  `[archivo.pdf p. N]` y aclarando explícitamente que deben utilizarse el nombre de archivo
  y número de página reales obtenidos del contexto recuperado (`documentos_no_confiables`).
  Se evitan sesgos hacia resoluciones específicas.
- **Preservación experimental A y B:** Las condiciones A (`A_sin_defensa`) y B
  (`B_defensa_basica`) se mantienen en su versión original (v1) sin modificación alguna,
  garantizando la comparabilidad e integridad metodológica.
- **Seguridad de la interfaz (Streamlit):** Se revisó `app/streamlit_app.py` eliminando
  la exposición de `raw_response` del panel desplegable de trazabilidad. La interfaz
  muestra únicamente la respuesta validada y metadatos seguros de trazabilidad.
  `raw_response` se preserva íntegramente en las trazas (`traces.json`, `traces.csv`) y
  artefactos internos de auditoría para T12.
- **Prueba de regresión de interfaz:** Se añadió en `tests/test_ui.py` una prueba que
  confirma que respuestas rechazadas o no validadas no quedan expuestas en ningún elemento
  visible del chatbot.
- **Validador estricto:** Se mantiene la verificación estricta de pertenencia al
  contexto recuperado admisible (`allowed`), sin adición automática de citas ni
  relajación de seguridad.
- **Verificación:** 38 pruebas unitarias pasando (`PYTHONPATH=src .venv/bin/python -m pytest`).
- **Validación piloto real Ollama:** Consulta piloto independiente ejecutada con Ollama
  y `qwen2.5:3b` sobre `GQ019` con una fuente documental distinta (`RCU-0504-2020.pdf`, p. 4)
  en modo documental C. El modelo generó la cita exacta `[RCU-0504-2020.pdf p. 4]`
  y fue validado sin abstención (`abstained=False`, latencia 26.38 s), verificando la
  viabilidad técnica del formato genérico en esta instancia puntual. No se afirma ausencia
  de sesgo ni eficacia general del prompt C v3 a partir de un único ensayo piloto; la
  evaluación sistemática de desempeño y robustez corresponde a T12. Registrado en
  `results/piloto_ollama_pr7.json` con el ID, la fuente, el resultado de la validación y
  los metadatos de la ejecución. El enunciado y las respuestas solo se guardan en el
  respaldo local del piloto.

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

## Fase 8 — Correcciones de revisión del PR #8 (León)

### 1. Protección de las ejecuciones experimentales (Corrección 1)
- **Directorio único por ejecución**: Se modificó `scripts/run_t11_baseline.py` para generar automáticamente rutas de salida únicas basadas en marcas de tiempo UTC (`results/llm_baseline_<timestamp>`), eliminando la ruta estática por defecto.
- **Protección estricta contra sobrescritura**: La función `ensure_unique_output_dir()` valida la existencia del directorio y lanza `FileExistsError` ante cualquier intento de reutilización o sobrescritura, incluso ante rutas provistas manualmente mediante `--output-dir`.
- **Pruebas automatizadas**: Se implementó la suite `tests/test_t11_baseline.py` (8 pruebas unitarias) que verifica la protección contra sobrescritura, la generación de rutas únicas y la ejecución desacoplada con mock (sin requerir servidor Ollama ni acceso a red).
- **Preservación de evidencias**: Las evidencias y trazas originales de la corrida baseline se conservan íntegramente en el respaldo local `results/llm_baseline_local/`, excluido de control de versiones.

### 2. Procedencia y reproducibilidad (Corrección 2)
- **Preservación histórica del manifiesto**: Se mantiene `results/llm_baseline/manifest.json` original sin alterar sus valores históricos, conservando el registro del commit base `e039e51db5672dcbb8791453846fa5eb8306623c`.
- **Documento de procedencia**: Se elaboró [PROCEDENCIA.md](../results/llm_baseline/PROCEDENCIA.md), explicando que el commit declarado corresponde al código base y que la ejecución utilizó modificaciones locales en `src/cs_rag_security/generation/__init__.py` posteriormente incorporadas formalmente en el commit original del PR #8 (`5a9b7f59eddb5231bbd079d4a857c59c93248b16`).
- **Auditoría y verificación de hashes**: Se verificó que los hashes de los 8 módulos de `src/`, el índice (`index.json`: `0cf3a950...`) y el dataset gold (`gold_questions.json`: `622eb3d7...`) coinciden exactamente con los artefactos de la versión del PR #8 en disco y en el commit `5a9b7f5`.
- **Distinción funcional vs. formato**: Se delimitó con precisión el cambio funcional (extracción de `prompt_eval_count` y `eval_count` a metadatos de tokens) de los cambios de formato (`.gitattributes` para espacios en blanco en CSV).
- **Limitación de versión de script**: Se registró expresamente que el manifiesto histórico no incluía el hash SHA-256 de `scripts/run_t11_baseline.py`, constituyendo una limitación para verificar de forma aislada la versión exacta del script al momento de ejecución, deduciéndose su correspondencia a partir de los artefactos generados y su consolidación en el PR #8.

### 3. Privacidad y material de evaluación T12 (Corrección 3)
- **Saneamiento de artefactos versionados**: Se retiraron de `results/llm_baseline/traces.json` y `traces.csv` los textos literales de las preguntas del gold y las respuestas crudas del LLM (`raw_response`) que reproducen contenido del corpus privado.
- **Conservación de telemetría autorizada**: Se mantienen en Git para las 10 consultas los identificadores (`GQ004`–`GQ040`), las 10 abstenciones con sus causas, latencias exactas de generación y pipeline, tokens de prompt y respuesta, y citas.
- **Delimitación empírica del Modo A**: Se documenta que el resultado de 10 abstenciones obedece a la ausencia de directivas de citación formal en las 10 consultas evaluadas en esta corrida, sin formular generalizaciones sobre consultas futuras o modelos distintos.
- **Trazas completas locales**: Las trazas íntegras con respuestas crudas y textos originales se preservan en almacenamiento local no versionado (`results/llm_baseline_local/`).
- **Preparador local de evaluación T12**: Se desarrolló el script reproducible `scripts/prepare_t12_eval.py`, el cual verifica el hash SHA-256 del índice contra `manifest.json` y extrae los fragmentos textuales exactos desde `data/vector_db/index.json`. Ante cualquier discrepancia de hash o ausencia de identificadores, el script aborta sin inventar evidencia.
- **Rúbrica v0.2 de origin/main y evaluación desacoplada**: Se respeta íntegramente la rúbrica v0.2 y la plantilla de 24 columnas estándar de `origin/main` ([rubrica_qa.md](evaluation/rubrica_qa.md), [plantilla_anotacion_qa.csv](evaluation/plantilla_anotacion_qa.csv)), generando en la preparación local de T12 filas pareadas para evaluar la respuesta del pipeline y la respuesta original del LLM.
- **Material ciego estricto**: `results/t12_evaluacion/t12_material_ciego.json` no contiene respuestas de referencia gold ni fuentes esperadas.
- **Blindaje en `.gitignore`**: Se configuraron exclusiones explícitas para `/results/t12_evaluacion/`, `/results/llm_baseline_local/`, `/results/llm_baseline_*/`, `raw_traces.json` y patrones de paquetes privados/locales.

### 4. Validación final
- **Métricas y telemetría**: Se comprobó que se mantienen exactamente las 10 consultas, 10 abstenciones por falta de citas, las 10 latencias y los tokens reportados.
- **Suite de pruebas**: 45 pruebas pasando exitosamente (`PYTHONPATH=src .venv/bin/python -m pytest`).
- **Verificación de estilo y formato**: `git diff --check` ejecutado sin advertencias.
- **Confidencialidad**: Inspección de diferencias en Git libre de textos de preguntas gold, fragmentos del corpus o credenciales.

Pendientes externos/científicos: configurar y ejecutar modelo local real; registrar
digest/versión del servidor y hardware; ampliar ataques y validar en conjuntos
independientes; revisión humana OCR, fidelidad semántica y vigencia; incorporar los
tres textos ausentes solo tras obtener fuentes verificadas. No se atribuye eficacia
de defensa frente a LLM con los resultados mock disponibles.

## León — T08, 19 de noviembre de 2026

Comparación textual y semántica ejecutada sobre las mismas 137 páginas oficiales
y 2.284 fragmentos. Se fijó el protocolo antes de medir: 13 preguntas cotejadas como
muestra primaria y las 40 originales como análisis exploratorio. MiniLM multilingüe
cuantizado se ejecutó localmente con ONNX, sin generar respuestas ni consumir API.

Ambos métodos obtienen 11/13 en top-5 primario. En el análisis exploratorio TF-IDF
obtiene 34/40 y MiniLM 30/40. La CLI y el chatbot siguen usando TF-IDF. MiniLM
se ejecuta solo en el benchmark. Se guardaron latencias repetidas, tamaño de índices, versiones,
hashes, errores y reproducción. T08 queda implementada y medida para revisión.
Véase [benchmark T08](evaluation/benchmark_recuperacion.md). La vigencia, el OCR
pendiente y la evaluación humana de respuestas reales conservan sus propios límites.
## León — T06, 19 de noviembre de 2026

Implementación y validación documental de T06 listas para revisión. Se verificó el
paquete depurado completo: 12 hashes PDF coincidentes, 11 PDF oficiales, un histórico,
137 páginas oficiales y 2.284 fragmentos. Se reforzó la exclusión por identificador,
metadatos y relaciones de alcance total y se bloqueó el histórico en índices antiguos.
Las derogaciones parciales conservan su alcance y las relaciones acompañan a los fragmentos.

Se cotejaron las relaciones conocidas con las fuentes disponibles, incluido el
artículo 4 del texto base RCU-0501-2020 y la parte resolutiva de RCU-0009-2026.
Los tres documentos faltantes y la revisión OCR continúan expresamente pendientes.
La consulta actual sin certificación se abstiene; los controles con mock no miden
eficacia de un LLM. Véanse [relaciones y reglas](corpus/vigencia_y_relaciones.md)
y [validación ejecutada](../results/normative_policy_20261119/validation.json).
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

## Romina — T14: Condiciones experimentales A/B/C e invariantes, 21 de noviembre de 2026

- **Auditoría de condiciones experimentales (A, B y C):** Se auditó exhaustivamente la implementación
  de las tres condiciones de acuerdo con el protocolo y la metodología aprobada:
  - Condición A (`A_sin_defensa`): línea base de control sin defensas frente a inyecciones indirectas;
    mensaje único `user` en texto plano; sin exclusión de fragmentos por sospecha heurística.
  - Condición B (`B_defensa_basica`): defensa estándar con separación de roles (`system` v1 + `user`),
    delimitación explícita `\nCONTEXTO NO CONFIABLE:\n` y JSON de fragmentos; sin exclusión heurística.
  - Condición C (`C_defensa_propuesta`): defensa en profundidad con filtrado heurístico activo
    (exclusión de fragmentos sospechosos previa a la generación), aislamiento estricto en JSON
    estructurado `{"pregunta": ..., "documentos_no_confiables": [...]}` y system prompt reforzado (v3).
- **Estrategias completas y no factorial desagregado:** Las condiciones A, B y C comparan estrategias
  de defensa completas e integradas; por diseño metodológico, las diferencias reflejan el efecto
  conjunto de cada condición y no permiten atribuir de forma individual o aislada la mejora a cada
  mecanismo defensivo por separado.
- **Preservación del Prompt C v3:** Se confirmó la conservación estricta del prompt C v3 con formato
  genérico de citación `[archivo.pdf p. N]`, indicando la extracción exclusiva de los campos `archivo`
  y `pagina` de `documentos_no_confiables`, sin nombres de archivo hardcodeados. El cambio elimina
  únicamente el ejemplo fijo de citación (`RCU-0161-2021.pdf`) para no inducir citas hacia una resolución
  específica, sin afirmar que se elimine completamente el sesgo general del LLM. Las condiciones A y B
  se preservan en su versión original v1 intactas.
- **Verificación de invariantes compartidos:**
  - Parámetros del modelo: idéntico proveedor (`mock`, `local` o `api`), modelo, temperatura fijada en `0`
    y semilla fija en `42` configuradas como controles de reproducibilidad (sin afirmar determinismo absoluto
    del hardware o backend), y `top_k=5`.
  - Recuperación e invariante de hits pareados: todas las condiciones consumen exactamente el mismo índice
    (`fallback_textual_tfidf_coseno_v1`) y la misma lista ordenada de hits recuperados por escenario.
  - Filtros comunes de producto: idéntico umbral de evidencia (coseno ≥ 0.12), idéntica exclusión de fragmentos
    con OCR pendiente (`ocr_revision_manual_pendiente=True`), idéntica exclusión de documentos históricos
    (`historical_hit`), e idéntica política de abstención documental si no está verificada la vigencia.
  - Validador común de citas: idéntica función y expresión regular `[archivo.pdf p. N]`, verificación estricta
    de pertenencia a fragmentos admisibles (`allowed`), idéntico mensaje de abstención ante citas inválidas y
    preservación íntegra de `raw_response` en trazas para auditoría.
- **Garantía de variable independiente única:** Se garantizó y verificó que la única diferencia operativa
  entre las condiciones corresponde a los mecanismos de defensa específicos definidos para cada una.
- **Pruebas automatizadas de invariantes:** Se implementó una suite completa de pruebas automatizadas en
  `tests/test_experimental_invariants.py` con 8 pruebas especializadas cubriendo: contrato y metadatos comunes,
  recuperación pareada y reproducibilidad de hits, filtros previos de producto comunes, validador de citas y `raw_response`,
  hiperparámetros del generador (temperatura 0 y semilla 42 como controles de reproducibilidad), manipulación aislada
  de la variable independiente de defensa, preservación de prompt C v3 y diagnóstico del detector registrado en todos los modos.
  Todas las pruebas pasaron satisfactoriamente (62 pasadas, 1 omitida en la suite completa de `pytest`).
- **Matriz comparativa de condiciones:** Documentada formalmente en `docs/METODOLOGIA.md`, tabulando las
  dimensiones operativas, roles, delimitaciones, prompts, filtros y parámetros invariantes.
- **Estado de dependencias y tareas vinculadas:** T11 ya fue ejecutada con Ollama real (la corrida formal corresponde a las diez consultas reales con Ollama del PR #8, en `results/llm_baseline/`; el archivo `results/piloto_ollama_pr7.json` corresponde a un piloto independiente).
  La tarea T12 corresponde a la evaluación humana de esas respuestas (mediante la rúbrica y cotejo de T10), no a
  nuevas ejecuciones del LLM ni a la medición de ASR. La tarea T15 (detector heurístico con reglas avanzadas)
  sigue reservada a León.
- **Restricciones respetadas:** No se modificaron evidencias históricas de T11 ni de T10; no se alteró el corpus
  ni el dataset gold; no se modificó la rúbrica T10; no se ejecutó ni simuló Ollama; no se tocó la lógica del detector
  heurístico (reservado a León en T15); sin APIs pagadas, sin commits, sin push ni merge.

## Fase 9 — T16: Trazabilidad experimental y preparación para T17, 21 de noviembre de 2026
- **Auditoría de trazabilidad previa**:
  - Se auditaron el pipeline (`pipeline.py`), el módulo de generación (`generation/`), la evaluación (`evaluation/`) y el ejecutor de baseline T11 (`scripts/run_t11_baseline.py`).
  - Se identificaron y subsanaron vacíos críticos: el pipeline no registraba motivos específicos de descarte por fragmento ni el ranking de recuperación; las corridas previas no auditaban los hashes SHA-256 de los scripts ejecutables en el manifiesto; y la lógica de protección contra sobrescritura y saneamiento estaba dispersa en scripts aislados.
- **Definición e implementación del módulo de trazabilidad (`cs_rag_security.traceability`)**:
  - Se implementó una biblioteca modular y reutilizable que centraliza constantes, validación de citas, evaluación estructurada de fragmentos, construcción de trazas, sanitización estricta de privacidad mediante listas explícitas de campos autorizados (allowlists) y generación de manifiestos.
  - **Identificadores**: Registro de `run_id`, `case_id`, `case_kind` y condición (`A_sin_defensa`, `B_defensa_basica`, `C_defensa_propuesta`).
  - **Fragmentos y motivos de descarte**: Se implementó `evaluate_retrieved_chunks()`, registrando `rank` (1..k), `score`, estatus (`accepted` / `discarded`) y motivos detallados de exclusión (`detector_suspicious`, `documento_historico`, `score_insuficiente`, `ocr_revision_pendiente`, `normativa_no_verificada`). Se garantiza que los fragmentos aceptados coinciden 100% con los enviados realmente al generador.
  - **Detector desacoplado para T15**: Registro de versión dinámica (`detector_version`, por defecto `heuristic_v1`, configurable dinámicamente para T15), decisiones individuales (`suspicious`, `score`, `reasons`), y su aplicación como filtro exclusivo en el Modo C (manteniéndose como observador diagnóstico en A y B).
  - **Diferenciación de salidas, citas y ausencia de generación**: Estricta separación entre `raw_response` (salida directa del LLM, preservada exclusivamente en almacenamiento local privado) y `response` (salida validada post-pipeline). Se registra el campo booleano `generation_performed` para diferenciar inequívocamente la ausencia previa de generación (`evidencia_insuficiente_o_no_fiable`) de una respuesta vacía del modelo (`modelo_vacio`). Extracción y validación estricta de citas contra los fragmentos aceptados (`citations_raw`, `citations_final`, `citations_valid`, `allowed_citations`) mediante el validador oficial del pipeline sin duplicar ni alterar su semántica.
  - **Parámetros, modelos y versiones de prompt**: Registro de proveedor, modelo, digest sha256 del modelo local (cuando aplique), versión de prompt (A=v1, B=v1, C=v3), latencias desacopladas (generación y pipeline) y tokens (`prompt_tokens`, `completion_tokens`, `total_tokens`), sin inventar metadatos ausentes (quedando como `null` en caso de no ser reportados).
  - **Procedencia exhaustiva**: `build_run_manifest()` calcula y almacena hashes SHA-256 del índice (`index.json`), datasets (`gold_questions.json`, `attacks.jsonl`), código fuente (`src/`) y ahora también de todos los scripts ejecutables (`scripts/`), resolviendo la limitación histórica registrada en el baseline T11.
  - **Separación de privacidad y verificación de Git**: Funciones `sanitize_trace_record()` y `save_experimental_run()` que garantizan que los artefactos versionados para Git (`manifest.json`, `traces.json`, `traces.csv`) excluyan mediante allowlists estrictas todo texto de preguntas gold, `raw_response`, textos de fragmentos y respuestas de dataset gold o ataques. La función `save_experimental_run()` verifica activamente mediante `git check-ignore` que las rutas privadas estén efectivamente ignoradas antes de guardar datos confidenciales.
- **Integración con el pipeline (`pipeline.py`)**:
  - `answer()` delega el registro de fragmentos a `evaluate_retrieved_chunks()` pasando directamente las colecciones reales `kept` y `reliable`, manteniendo total compatibilidad con las claves previas y exponiendo los nuevos campos de auditoría (`evaluated_chunks`, `discarded_chunks`, `prompt_version`, `detector_version`, `detector_applied`).
- **Refactorización sin duplicidad en T11 (`scripts/run_t11_baseline.py`)**:
  - El runner histórico de T11 ahora reutiliza directamente `ensure_unique_output_dir`, `extract_citations`, `determine_abstention_reason` y `get_git_commit` del módulo centralizado de trazabilidad, eliminando duplicación de código sin alterar sus artefactos históricos ni romper su suite de pruebas (`test_t11_baseline.py`).
- **Contrato de integración y documentación para León (`docs/CONTRATO_TRAZABILIDAD.md`)**:
  - Se elaboró una especificación completa del contrato de trazabilidad, definiendo los esquemas JSON y CSV, una tabla explícita de campos obligatorios vs. opcionales, invariantes de inmutabilidad y un ejemplo de integración de extremo a extremo para el futuro runner experimental T17.
- **Corrección a observación de León (PR #10 — Rechazos del proveedor y privacidad en Git)**:
  - Se identificó el flujo de rechazo explícito del proveedor (`refusal`, `finish_reason='refusal'|'content_filter'`), el cual genera en el pipeline el motivo canónico de abstención `rechazo_del_modelo` (`ABSTENTION_REASON_MODEL_REFUSAL`).
  - Cuando el proveedor devuelve un rechazo con texto libre propio (`refusal_msg`), ese detalle confidencial se conserva íntegramente en las trazas privadas (`private_traces.json`, `private_traces.csv`, `raw_traces.json`) y en `raw_response` para auditoría forense.
  - En los artefactos saneados para Git (`traces.json`, `traces.csv`), se implementó la sustitución estricta del texto libre por el mensaje canónico estándar `STANDARD_MODEL_REFUSAL_RESPONSE` (`"Me abstengo: el modelo rechazó la consulta."`), garantizando que ni marcadores sintéticos ni detalles internos del proveedor se filtren en repositorios versionados.
  - Se garantiza que el motivo de abstención (`rechazo_del_modelo`), `abstained=True`, `generation_performed=True` y todos los metadatos operativos (proveedor, modelo, tokens, latencias, hiperparámetros) se preservan intactos para el análisis en T18.
- **Validación automatizada**:
  - Implementada suite exhaustiva `tests/test_traceability.py` (23 pruebas unitarias) con datos sintéticos, cubriendo filtrado multicausal, versiones de prompt, detección dinámica, citas, abstenciones, procedencia, persistencia, verificación activa de `.gitignore`, allowlists de privacidad, y regresión estricta de segregación público/privado ante rechazos del proveedor con marcadores confidenciales.
  - Pruebas adicionales en `tests/test_t11_baseline.py` para garantizar la misma protección en el preparador baseline.
  - 98 pruebas unitarias pasando (`PYTHONPATH=src .venv/bin/python -m pytest`).
  - Verificación de formato y espacios limpia (`git diff --check`).
