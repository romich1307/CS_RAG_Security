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
  `results/piloto_ollama_pr7.json` sin inclusión de texto íntegro del corpus ni secretos.

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
