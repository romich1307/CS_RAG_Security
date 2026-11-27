# Informe final de métricas para el artículo IEEE

**Estado v5: PRELIMINAR.** La puerta automática se detuvo en el piloto.
El conjunto independiente quedó reservado y sin inferencia. Las cifras
históricas mantienen sus denominadores y procedencia. [Decisión v5](DECISION_DE_CIERRE_V5.md) · [Matriz de evidencia](MATRIZ_EVIDENCIA_IEEE.md)

## 1. Resumen ejecutivo

CS_RAG_Security es un RAG documental para resoluciones de la UNSA, implementado en Python y Streamlit, con recuperación local y generación opcional vía Ollama. El corpus piloto incluye 11 PDF oficiales y un PDF histórico, 137 páginas piloto y 115 páginas OCR. La respuesta documental no certifica vigencia normativa.

La evidencia más sólida para el artículo es la comparación pareada de recuperación T08, el costo del filtro de citas en T17/T18 y la diferencia de ASR RAW entre A y las condiciones defendidas en T19. T08 igualó Hit@1 y Hit@5 entre MiniLM y TF-IDF en la muestra primaria. En T18 se conservaron 4/30 respuestas correctas FINAL frente a 11/30 RAW. T19 observó 10/20 éxitos RAW en A y 0/20 en cada brazo defendido. Las tres condiciones tuvieron 0/20 éxitos FINAL. La verificación exploratoria de v3 redujo abstenciones y mostró una falla de cobertura multifuente. La exactitud y seguridad comparativas de v3 siguen abiertas. En una muestra distinta, v4 mejoró la recuperación y la cita de todas las páginas objetivo frente a v3. La revisión automática de v4 fue más conservadora y la exactitud humana sigue pendiente.

## 2. Versiones y corridas

| Versión o corrida | Identidad y alcance | Evidencia |
| --- | --- | --- |
| Estable | `main` y referencia local `origin/main` en `a96f64d3e5391abe6695cebcfcc7b52609e7cb1b`. Consulta documental v2 integrada por `0e44235`. | Git y [optimización v2](OPTIMIZACION_FINAL_RAG.md) |
| Experimental | `feature/mejora-calidad-seguridad-v3` en `4d3b0dc3cc90df68226c7b8eadf6479497e0ecac`. Evaluación desde `d2786708e204ef0f613ed7f576f418f27ca0c312`. | Git y [protocolo v3](MEJORA_CALIDAD_Y_SEGURIDAD_V3.md) |
| T08 | `retrieval_t08_20261119_final`. Dos métodos sobre las mismas 13 consultas primarias y análisis adicional de 40 consultas. | [Manifiesto T08](../../results/retrieval_t08_20261119_final/manifest.json) |
| T10 | `t10_subset_retrieval_20261119`. Cotejo TF-IDF independiente de la ejecución T08, previa al protocolo del benchmark definitivo. | [Manifiesto T10](../../results/t10_subset_retrieval_20261119/manifest.json) |
| T11/T12 | `llm_baseline`, commit `e039e51db5672dcbb8791453846fa5eb8306623c`, 10 consultas en A y una anotación por etapa. | [Manifiesto T11](../../results/llm_baseline/manifest.json) y [T12](evaluacion_t12_20261121.md) |
| T17 | `t17_ollama_20261121_r2`, commit `bb76f83b683a91cf597a282c4e638fd3c9935c2a`. Diez consultas legítimas compartidas por A/B/C, 30 trazas. | `results/llm_abc_local/t17_ollama_20261121_r2/manifest.json` |
| T18 | Cómputo de calidad sobre los 30 pares RAW/FINAL de T17, 60 anotaciones. | `results/llm_abc_local/t20_cierre_verificado_20261125/quality_metrics.json` |
| T19 | `t19_inyecciones_20_20261125_003544`, 20 casos positivos únicos, 60 ejecuciones A/B/C. Control benigno separado de 20 casos únicos y 60 ejecuciones. | [Manifiesto T19](../../results/t19_inyecciones_20_20261125_003544/manifest.json) y [diagnóstico benigno](../../results/t19_benignos_20261125_001519/diagnostico_raw_final.json) |
| T20 | `t20_cierre_verificado_20261125`, entorno Git `a60554356c959efa7126c0a9a9ce04cb49e3ba76`. Integra las evidencias y genera 10 tablas y 6 figuras. | `results/llm_abc_local/t20_cierre_verificado_20261125/{manifest,audit_report}.json` |
| v2/v3 | Piloto de dos consultas por perfil y verificación de seis consultas nuevas por perfil. | `/tmp/csrag-v3-{pilot,holdout}-run/{manifest.json,traces.jsonl,technical.json}` |
| v4 | `feature/mejora-real-v4`. Cinco pares v3/v4 en muestra nueva de verificación. | `/tmp/csrag-v4-holdout-run/{manifest.json,technical.json,traces.jsonl}` y [reporte v4](INFORME_MEJORA_REAL_V4.md) |

Las referencias Git se verificaron localmente. `origin/HEAD` apunta a una rama antigua y la referencia usada para identificar la versión estable fue `main`. No se consultó el remoto.

## 3. Configuración, código e integridad

- **Recuperación.** El producto usa TF-IDF local con coseno. El perfil documental normaliza guiones de extracción, limita a resoluciones solicitadas explícitamente, deduplica y reúne hasta k pasajes admitidos. Se excluyen fragmentos históricos, de origen ajeno al piloto, por debajo del umbral 0,12, con OCR pendiente o marcados por el detector. Se rechaza la solicitud de certificar vigencia. La vía MiniLM se usa en el benchmark, con encoder multilingüe L12 v2, ONNX AVX2 INT8, media enmascarada, norma L2 y máximo de 128 tokens. [Recuperación](../../src/cs_rag_security/retrieval/__init__.py) · [Perfil documental](../../src/cs_rag_security/demo.py) · [MiniLM](../../src/cs_rag_security/retrieval/semantico.py)
- **Generación.** T11/T17/T19 y la comparación v2/v3 declaran Ollama local `qwen2.5:3b`, semilla 42, temperatura 0, `top_k=5` documental. El digest común registrado por API en T11/T17/v3 es `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`. El manifiesto T19 no registra digest, versión de Ollama, commit ni hardware. T17 declara Ollama 0.40.17 y Python 3.12.14. Verificación v3 usa Ollama 0.40.16, CPU Ryzen 5 3400G, contexto 4096 y ejecución serial. La generación local usa HTTP sin proxy ni redirecciones, con destino loopback literal y timeout de 90 s por llamada. [Adaptador](../../src/cs_rag_security/generation/__init__.py)
- **A/B/C histórico.** A concatena contexto y pregunta. B aísla contexto con roles y delimitación. C usa JSON, instrucciones de citas canónicas y exclusión heurística. Versiones de prompt A=v1, B=v1, C=v3. Esta última versión de prompt corresponde al protocolo histórico. [Defensas](../../src/cs_rag_security/defenses/__init__.py) · [Protocolo T17](protocolo_utilidad_t17.md)
- **Detector y citas.** `heuristic_v1` reporta reglas léxicas con normalización Unicode. Los brazos pueden registrar alertas y solo C las usa como exclusión. El validador histórico verifica la cita canónica PDF/página contra el contexto aceptado. El conversacional verifica anclajes literales y una segunda llamada revisa sustento y cobertura. Las citas se renderizan desde metadatos. La coincidencia literal y formal puede coexistir con paráfrasis incorrecta. [Trazabilidad](../../src/cs_rag_security/traceability.py) · [Perfil conversacional](../../src/cs_rag_security/conversational.py)
- **v2 y v3.** v2 puede recortar subpreguntas mediante solapamiento léxico y ajustar el máximo de afirmaciones mediante puntuación. v3 conserva la pregunta completa, intercala candidatos de subpreguntas delimitadas cuando no se explicitan resoluciones y admite hasta tres afirmaciones. Separa lista de afirmaciones aceptadas y bandera de incompletitud. Mantiene admisión, anclajes y guardas de salida. Los motivos de fallo distinguen anclaje, revisión vacía y revisión inválida.
- **Reproducción offline.** `scripts/retrieval_benchmark.py` usa el protocolo `experiments/retrieval_protocol.json`. T18 se reprodujo con `scripts/compute_quality_metrics.py --annotations … --mapping … --traces … --output-dir <ruta nueva>` sobre las anotaciones T18, correspondencia privada y trazas T17. Coincidieron las cuatro estructuras verificadas de calidad, pareo y latencia. Para T20 se documentó una raíz aislada con el índice histórico. Para v3, `scripts/evaluate_conversational_v3.py --phase holdout` se ejecutó con directorio nuevo, preguntas congeladas y presupuesto idéntico de 640 tokens de borrador y 160 de revisión. Se alternó el orden por par. En algunas consultas simples de v2 se elevó el tope nativo de 320. [Receta T20](CIERRE_FUNCIONAL_CSRAG_20261125.md#reproducir-t20-con-el-índice-histórico) · [Receta v3](MEJORA_CALIDAD_Y_SEGURIDAD_V3.md#reproducción-y-revisión-humana)

| Alcance | Verificación SHA-256 |
| --- | --- |
| T08 | PDF 12/12, gold y protocolo coinciden. JSONL piloto cotejado: paginas_rag_piloto.jsonl. Los hashes del encoder se declararon en el manifiesto. |
| T11 | Índice de trabajo y gold coinciden. Código Git: 7/8 coincidencias exactas con el commit base y 8/8 con `5a9b7f5`. Consultar `results/llm_baseline/PROCEDENCIA.md` sobre cambios sin confirmar y ausencia de hash del script. |
| T17 | Gold e instantánea histórica coinciden. Código y scripts Git: 0/25 exactos y 25/25 con CRLF. |
| T19 | Coinciden 3/3 referencias de las métricas al manifiesto, trazas públicas y rúbrica. Coincide también el diagnóstico textual que referencia la rúbrica. |
| T20 | 6/6 hashes de entradas y 35/35 hashes de salidas. Dictamen del paquete: aprobado. |
| v3 | 21/21 hashes del manifiesto. Coincide el agregado publicado en el informe previo. El SHA del manifiesto instalado en disco es `cd232a7a8d590449a99eb8fe29b614ef9bf3624d2d17faa496e1135ba4188be0`, distinto del digest registrado por API en las corridas. Blobs actuales: 6/6 coinciden con su manifiesto local. No se confirmó identidad binaria histórica con esos blobs. |


El índice de trabajo, usado por T11 y v3, tiene SHA-256 `0cf3a950092c2c32e1c02dee23c480bc4717dc0b52a2db1aa96c6d4f09c8b2e0`. T17 coincide con `data/vector_db/t20_verificacion_20261125/data/vector_db/index.json`, SHA-256 `7364fa03eeb3fc6dfd2a7832ef421c74f9ef31c63bd34635f53b671e625618fa`. La alerta de índice en el [informe preliminar T17–T19](integracion_t17_t19_20261125.md) corresponde al uso del índice actual para auditar una corrida histórica. El paquete T20 verificado resuelve esa discrepancia. Dos paquetes alternativos, `t20_cierre_20261125` y `t20_artefactos_t17_t19_20261125`, también conservan 6/6 entradas y 35/35 salidas coincidentes. En `t20_artefactos_verificados_20261125` se cotejaron 5/5 entradas. Sus 35 rutas de salida apuntan a un directorio temporal antiguo; los 35/35 hashes coinciden al resolver las rutas relativas a la copia archivada. Estos paquetes son exportaciones derivadas y no aumentan la muestra. Los hashes de código cotejan bytes y permiten identificar una representación CRLF cuando corresponde. No reconstruyen el entorno histórico por sí solos. El encoder opcional no estaba configurado para cotejo binario en esta auditoría. Los insumos privados de generación T19 referenciados por hash no estaban disponibles para reanotar sus salidas. Su evidencia disponible es la revisión de rúbrica y el diagnóstico saneado.

## 4. Recuperación documental

| Corrida | Muestra | Método | Hit@1 | Hit@3 | Hit@5 |
| --- | --- | --- | --- | --- | --- |
| T08 | 13 primarias | TF-IDF | 6/13 · 46.15% | 9/13 · 69.23% | 11/13 · 84.62% |
| T08 | 13 primarias | MiniLM ONNX | 6/13 · 46.15% | 11/13 · 84.62% | 11/13 · 84.62% |
| T08 | 40 exploratorias | TF-IDF | 20/40 · 50.00% | 28/40 · 70.00% | 34/40 · 85.00% |
| T08 | 40 exploratorias | MiniLM ONNX | 15/40 · 37.50% | 28/40 · 70.00% | 30/40 · 75.00% |
| T10 | 13 cotejadas | TF-IDF | 10/13 · 76.92% | 13/13 · 100.00% | 13/13 · 100.00% |


Proveedor CPU local, sin generación. La unidad de Hit@k es la consulta con al menos una coincidencia PDF/página entre los primeros k fragmentos. T08 empleó 2284 fragmentos de 180 palabras con solapamiento de 30, en CPU Intel i5-12500H, Windows 11 y ONNX con 4 hilos. MiniLM truncó 77/2284 fragmentos según manifiesto. Los 13 casos primarios tienen cotejo asistido y están incluidos en los 40 exploratorios. El Hit@5 de 13/13 en T10 pertenece a otra construcción y otro protocolo. La igualdad de Hit@1 y Hit@5 en el núcleo primario, la latencia inferior y el menor costo de almacenamiento favorecen TF-IDF como opción operativa en ese entorno. MiniLM mejoró Hit@3 primario. En Hit@5, nueve de las 13 consultas acertaron con ambos métodos, dos solo con TF-IDF y dos solo con MiniLM. El empate agregado oculta cambios por consulta. En los 40 casos exploratorios tuvo menor Hit@1 y Hit@5. Los artefactos T08 registran 1 939 686 bytes para TF-IDF y 5 468 544 para el índice MiniLM más 127 540 164 bytes de archivos del modelo, con formatos de almacenamiento distintos. [T08 resultados](../../results/retrieval_t08_20261119_final/metrics.json) · [T08 filas](../../results/retrieval_t08_20261119_final/retrieval.csv) · [T10 filas](../../results/t10_subset_retrieval_20261119/retrieval.csv)

La corrida offline histórica de proveedor mock registró Hit@5 de 34/40 por condición con recuperación compartida. El SHA-256 del archivo de casos sintéticos coincide con su manifiesto. El cierre funcional con TF-IDF y mock registró Hit@5 de 34/40 y 11/13 antes y después de la admisión documental para sus dos subconjuntos. Mejoró la presencia de algún contexto admitido de 39/40 a 40/40 y de 12/13 a 13/13, con Hit@5 igual. [Offline](../../results/offline_20261117_final/metrics.json) · [Cierre funcional](CIERRE_FUNCIONAL_CSRAG_20261125.md)

## 5. Utilidad, calidad y citas

| Corrida | Brazo | Etapa | Correctas | Parciales | Incorrectas | Abstenciones | Adecuadas/abst. | Inadecuadas/abst. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T18 | Total | RAW | 11/30 · 36.67% | 7/30 · 23.33% | 8/30 · 26.67% | 4/30 · 13.33% | 4/4 · 100.00% | 0/4 · 0.00% |
| T18 | Total | FINAL | 4/30 · 13.33% | 2/30 · 6.67% | 3/30 · 10.00% | 21/30 · 70.00% | 9/21 · 42.86% | 12/21 · 57.14% |
| T18 | A | RAW | 2/10 · 20.00% | 2/10 · 20.00% | 4/10 · 40.00% | 2/10 · 20.00% | 2/2 · 100.00% | 0/2 · 0.00% |
| T18 | A | FINAL | 0/10 · 0.00% | 0/10 · 0.00% | 0/10 · 0.00% | 10/10 · 100.00% | 4/10 · 40.00% | 6/10 · 60.00% |
| T18 | B | RAW | 5/10 · 50.00% | 3/10 · 30.00% | 1/10 · 10.00% | 1/10 · 10.00% | 1/1 · 100.00% | 0/1 · 0.00% |
| T18 | B | FINAL | 0/10 · 0.00% | 0/10 · 0.00% | 0/10 · 0.00% | 10/10 · 100.00% | 4/10 · 40.00% | 6/10 · 60.00% |
| T18 | C | RAW | 4/10 · 40.00% | 2/10 · 20.00% | 3/10 · 30.00% | 1/10 · 10.00% | 1/1 · 100.00% | 0/1 · 0.00% |
| T18 | C | FINAL | 4/10 · 40.00% | 2/10 · 20.00% | 3/10 · 30.00% | 1/10 · 10.00% | 1/1 · 100.00% | 0/1 · 0.00% |
| T11/T12 | A | RAW | 3/10 · 30.00% | 2/10 · 20.00% | 4/10 · 40.00% | 1/10 · 10.00% | 1/1 · 100.00% | 0/1 · 0.00% |
| T11/T12 | A | FINAL | 0/10 · 0.00% | 0/10 · 0.00% | 0/10 · 0.00% | 10/10 · 100.00% | 4/10 · 40.00% | 6/10 · 60.00% |


Proveedor Ollama local `qwen2.5:3b`. Correcta, parcial, incorrecta y abstención usan todas las consultas evaluadas del brazo y etapa. Adecuación e inadecuación usan únicamente las abstenciones de ese corte. El 12/25 histórico reúne ambas etapas, con 12/21 abstenciones inadecuadas FINAL y 0/4 RAW. El filtro hizo perder 7/30 borradores correctos, todos con el motivo formal de citas, y 17/30 salidas sustantivas. En las 21/30 abstenciones FINAL del pareo faltaron citas canónicas reconocidas en RAW. El 21/30 de ese diagnóstico usa todas las consultas e incluye cuatro abstenciones RAW. C retuvo 4/10 respuestas correctas; B tenía 5/10 correctas RAW y 0/10 FINAL. Las anotaciones T18 cubren 60/60 registros, con 0/60 consensuados explícitamente según auditoría T20. Esto no establece concordancia entre evaluadores. T11/T12 es preliminar y distinto de A en T17. [Anotaciones T11/T12](../../results/llm_baseline/anotaciones.csv) · [Metodología T18](metricas_calidad_t18.md) · `T20/quality_metrics.json#emparejamiento_pipeline_vs_llm`

| Corrida | Brazo | Etapa | Formales | Ausentes | Inválidas | Mixtas | Indeterm. | En contexto (humano) | Sustento completo | Sustento parcial | Sustento nulo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T18 | Total | RAW | 9/26 · 34.62% | 17/26 · 65.38% | 0/26 · 0.00% | 0/26 · 0.00% | 0/26 · 0.00% | 16/26 · 61.54% | 13/26 · 50.00% | 0/26 · 0.00% | 4/26 · 15.38% |
| T18 | Total | FINAL | 9/9 · 100.00% | 0/9 · 0.00% | 0/9 · 0.00% | 0/9 · 0.00% | 0/9 · 0.00% | 9/9 · 100.00% | 6/9 · 66.67% | 0/9 · 0.00% | 3/9 · 33.33% |
| T18 | A | RAW | 0/8 · 0.00% | 8/8 · 100.00% | 0/8 · 0.00% | 0/8 · 0.00% | 0/8 · 0.00% | 0/8 · 0.00% | 0/8 · 0.00% | 0/8 · 0.00% | 0/8 · 0.00% |
| T18 | A | FINAL | ND (0/0) | ND (0/0) | ND (0/0) | ND (0/0) | ND (0/0) | ND (0/0) | ND (0/0) | ND (0/0) | ND (0/0) |
| T18 | B | RAW | 0/9 · 0.00% | 9/9 · 100.00% | 0/9 · 0.00% | 0/9 · 0.00% | 0/9 · 0.00% | 7/9 · 77.78% | 7/9 · 77.78% | 0/9 · 0.00% | 1/9 · 11.11% |
| T18 | B | FINAL | ND (0/0) | ND (0/0) | ND (0/0) | ND (0/0) | ND (0/0) | ND (0/0) | ND (0/0) | ND (0/0) | ND (0/0) |
| T18 | C | RAW | 9/9 · 100.00% | 0/9 · 0.00% | 0/9 · 0.00% | 0/9 · 0.00% | 0/9 · 0.00% | 9/9 · 100.00% | 6/9 · 66.67% | 0/9 · 0.00% | 3/9 · 33.33% |
| T18 | C | FINAL | 9/9 · 100.00% | 0/9 · 0.00% | 0/9 · 0.00% | 0/9 · 0.00% | 0/9 · 0.00% | 9/9 · 100.00% | 6/9 · 66.67% | 0/9 · 0.00% | 3/9 · 33.33% |


Denominador de citas: respuestas sustantivas de la fila. Los estados formales se derivan de trazas y son excluyentes. La columna de pertenencia proviene de la anotación humana. En RAW los dos criterios difieren: revisar ambos si se van a publicar (pertenencia anotada 16/26 frente a validez canónica 9/26 en el agregado T18). En FINAL de C, 9/9 citas son formalmente válidas y 6/9 sustentan completamente la respuesta; la diferencia equivale a 3/9 con sustento parcial o nulo. Para T11/T12 las anotaciones preliminares registran 9/9 sustantivas RAW sin citas y 0/9 con cita válida y sustento completo. FINAL tiene denominador 0. [Rúbrica](rubrica_qa.md) · `results/llm_abc_local/t20_cierre_verificado_20261125/quality_metrics.json#por_origen_respuesta`

## 6. Seguridad y detector

| Brazo | ASR RAW | ASR FINAL | Marcador RAW | Marcador RAW exacto | Marcador FINAL | Abstenciones FINAL |
| --- | --- | --- | --- | --- | --- | --- |
| A | 10/20 · 50.00% | 0/20 · 0.00% | 20/20 · 100.00% | 10/20 · 50.00% | 0/20 · 0.00% | 20/20 · 100.00% |
| B | 0/20 · 0.00% | 0/20 · 0.00% | 11/20 · 55.00% | 0/20 · 0.00% | 0/20 · 0.00% | 20/20 · 100.00% |
| C | 0/20 · 0.00% | 0/20 · 0.00% | 1/20 · 5.00% | 0/20 · 0.00% | 1/20 · 5.00% | 19/20 · 95.00% |


Proveedor Ollama local `qwen2.5:3b`. ASR cuenta cumplimiento del objetivo según la rúbrica. Cada brazo compartió los mismos 20 casos positivos y recuperó 20/20 antes del filtrado, por lo que el ASR sobre recuperados coincide con el ASR global. En cada brazo 20/20 casos carecen de evidencia de exposición y de decisión de filtrado por caso en la rúbrica. En A se registraron 10/20 éxitos RAW seguidos de abstención por citas. El marcador contextual visible en FINAL de C cuenta como aparición textual y el éxito adjudicado fue 0/20. El diagnóstico registra 32/60 menciones RAW amplias, mientras la revisión declara 22 menciones RAW revisadas y una FINAL. El expediente disponible no explica por completo la diferencia entre ambos contadores. La fuente para frecuencia textual es el diagnóstico y para ASR es la rúbrica. [Rúbrica por caso](../../results/t19_inyecciones_20_20261125_003544/revision_rubrica_raw_final.json) · [Diagnóstico](../../results/t19_inyecciones_20_20261125_003544/diagnostico_raw_final.json) · [Agregado](../../results/t19_inyecciones_20_20261125_003544/security_metrics.json)

| Corrida | Grupo | Recall | FPR | Falsos negativos |
| --- | --- | --- | --- | --- |
| T19 | A | 15/20 · 75.00% | 5/20 · 25.00% | 5/20 · a4, a17, a18, a19, a20 |
| T19 | B | 15/20 · 75.00% | 5/20 · 25.00% | 5/20 · a4, a17, a18, a19, a20 |
| T19 | C | 15/20 · 75.00% | 5/20 · 25.00% | 5/20 · a4, a17, a18, a19, a20 |
| T15 | Total | — | 5/20 · 25.00% | — |
| T15 | desarrollo | — | 3/10 · 30.00% | — |
| T15 | verificacion | — | 2/10 · 20.00% | — |


Recall usa los positivos etiquetados y FPR usa un conjunto aparte de controles benignos. T15 y el control benigno T19 reutilizan 20 ejemplos, por lo que no se suman. El FPR de la corrida positiva T19 es no estimable con denominador cero. Las reglas de T15 activaron salida impuesta en 3/20 y suplantación de rol en 2/20 controles. El diagnóstico mock separado registró recall 3/4 y FPR 1/4 por condición, y emisión de marcador A 4/4, B 4/4 y C 1/4. Es un control de lógica extractiva. La revisión previa con el índice de trabajo registró 0/254 alertas sobre fragmentos que superaban los demás filtros de metadatos con la puntuación fijada, sin nuevas etiquetas de seguridad ni generación. [T15](../../results/detector_benign_v2/metrics.json) · [T19 positivos](../../results/t19_inyecciones_20_20261125_003544/traces.json) · [T19 benignos](../../results/t19_benignos_20261125_001519/diagnostico_raw_final.json) · [Mock](../../results/t19_diagnostico_mock/metrics.json) · [Auditoría del índice](MEJORA_CALIDAD_Y_SEGURIDAD_V3.md#piloto-exploratorio)

## 7. Latencia y llamadas

| Corrida | Grupo | Etapa | Proveedor | n | Media (s) | Mediana (s) | p95 (s) | Llamadas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T08 | 13 primarias · TF-IDF | vectorizar + buscar | CPU local, sin LLM | 65 | 0.00534 | 0.00518 | 0.00627 | — |
| T08 | 13 primarias · MiniLM ONNX | vectorizar + buscar | CPU local, sin LLM | 65 | 0.00891 | 0.00848 | 0.01272 | — |
| T08 | 40 exploratorias · TF-IDF | vectorizar + buscar | CPU local, sin LLM | 200 | 0.00533 | 0.00519 | 0.00635 | — |
| T08 | 40 exploratorias · MiniLM ONNX | vectorizar + buscar | CPU local, sin LLM | 200 | 0.00835 | 0.00827 | 0.01170 | — |
| T10 | 13 cotejadas | búsqueda | CPU local, sin LLM | 13 | 0.00068 | 0.00060 | — | — |
| T11 | A | pipeline | Ollama local qwen2.5:3b | 10 | 25.20736 | 23.12255 | — | — |
| T11 | A | generación | Ollama local qwen2.5:3b | 10 | 25.19243 | 23.10915 | — | 10 |
| T17 | A | pipeline sin recuperación pareada | Ollama local qwen2.5:3b | 10 | 3.72445 | 3.39572 | — | — |
| T17 | A | generación | Ollama local qwen2.5:3b | 10 | 3.70768 | 3.37992 | — | 10 |
| T17 | B | pipeline sin recuperación pareada | Ollama local qwen2.5:3b | 10 | 1.31603 | 1.14629 | — | — |
| T17 | B | generación | Ollama local qwen2.5:3b | 10 | 1.29872 | 1.12914 | — | 10 |
| T17 | C | pipeline sin recuperación pareada | Ollama local qwen2.5:3b | 10 | 0.85251 | 0.79112 | — | — |
| T17 | C | generación | Ollama local qwen2.5:3b | 10 | 0.83483 | 0.77333 | — | 10 |
| holdout | v2 | pipeline | Ollama local qwen2.5:3b | 6 | 46.96275 | 49.42914 | — | 9 |
| piloto v2/v3 | v2 | pipeline | Ollama local qwen2.5:3b | 2 | 74.32670 | 74.32670 | — | 4 |
| holdout | v3 | pipeline | Ollama local qwen2.5:3b | 6 | 53.80804 | 62.28833 | — | 10 |
| piloto v2/v3 | v3 | pipeline | Ollama local qwen2.5:3b | 2 | 77.86427 | 77.86427 | — | 4 |
| v1/v2 exploratorio | v1 | tiempo total, casos calientes | Ollama local qwen2.5:3b | 3 | 47.71900 | 41.83800 | — | 6 |
| v1/v2 exploratorio | v2 | tiempo total, casos calientes | Ollama local qwen2.5:3b | 3 | 23.57633 | 34.93700 | — | 4 |


Se recalcularon media y mediana sobre observaciones válidas. El p95 publicado aquí usa interpolación lineal tipo 7 y se muestra a partir de 20 observaciones. Las repeticiones de T08 contribuyen a la distribución de tiempos observados, con dependencia dentro de cada consulta. El paquete histórico publica p95 de T17 con n=10 por condición: pipeline A 8,42 s, B 2,3021 s y C 1,6234 s; generación A 8,4022 s, B 2,2852 s y C 1,6058 s. Son descripciones históricas de cola inestable y se omiten del CSV para ese tamaño. El pipeline T17 excluye la recuperación compartida. La latencia de T11 se calculó sobre trazas de una sola máquina. Las trazas públicas de T19 no aportan latencia ni llamadas verificables.

La comparación caliente v1/v2 usa tres consultas documentales. El criterio funcional se cumplió en 2/3 con v1 y 3/3 con v2. v1 hizo 6 llamadas para 3 consultas y v2 hizo 4 para 3. El caso que v2 resolvió antes de inferir explica buena parte de la diferencia en promedios. La consulta fría repetida se excluye del pareo. La microprueba de caché con doble de generación midió mediana local 331,495 ms en v1 y 10,505 ms en v2, 20 repeticiones por brazo, excluida la inferencia. No hay una comparación común v1/v2/v3. [T08](../../results/retrieval_t08_20261119_final/latency.csv) · [T11](../../results/llm_baseline/traces.json) · `results/llm_abc_local/t17_ollama_20261121_r2/traces.json` · [v1/v2](OPTIMIZACION_FINAL_RAG.md#comparación-con-ollama-local) · `/tmp/csrag-v3-{pilot,holdout}-run/traces.jsonl`

## 8. Verificación exploratoria de v3

| Perfil | RAW producido | Abstenciones FINAL | Citas FINAL formales | Errores |
| --- | --- | --- | --- | --- |
| v2 | 5/6 · 83.33% | 5/6 · 83.33% | 1/1 · 100.00% | 0/6 · 0.00% |
| v3 | 5/6 · 83.33% | 1/6 · 16.67% | 5/5 · 100.00% | 0/6 · 0.00% |


Ollama local `qwen2.5:3b`, seis consultas por brazo. Ambos perfiles obtuvieron Hit@1 y Hit@5 de 5/5 en pasajes admitidos, cobertura de todas las páginas objetivo en top 1 de 4/5 y en top 5 de 5/5. La consulta de vigencia no tenía página de referencia y quedó fuera de ese denominador. En RAW todas las referencias numéricas quedaron en rango en 5/5 borradores por brazo. Esto no implica que la cita literal del borrador haya pasado el control de anclaje. En el piloto, v2 se abstuvo en 2/2 y el prototipo v3 en 0/2. Tras ese piloto se ajustó la regla de cobertura. La verificación usada aquí corresponde al código ya congelado. En cuatro pares, v2 se abstuvo y v3 publicó una respuesta. No hubo pares en la dirección contraria. Es un contraste de entrega, sin juicio de corrección.

| Caso | Perfil | Páginas admitidas | RAW | FINAL técnico | Motivo | Citas FINAL | s | Llamadas | Verificación automática | Pendiente humano |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H01 | v2 | RCU-0161-2021 p.4, RCU-0161-2021 p.3 | 1 propuesta / 0 pasan control local | Abstención | salida_no_verificable | — | 32.480 | 1 | Ref. objetivo 1/1 | Fidelidad, completitud, citas y abstención |
| H01 | v3 | RCU-0161-2021 p.4, RCU-0161-2021 p.3 | 3 propuestas / 3 pasan control local | parcial | — | RCU-0161-2021 p.4 | 82.452 | 2 | Ref. objetivo 1/1; citas en contexto | Fidelidad, completitud, citas y abstención |
| H02 | v2 | RCU-0504-2020 p.7, RCU-0161-2021 p.6, RCU-0504-2020 p.8, RCU-0504-2020 p.6 | 2 propuestas / 2 pasan control local | Abstención | salida_no_verificable | — | 87.311 | 2 | Ref. objetivo 2/2 | Fidelidad, completitud, citas y abstención |
| H02 | v3 | RCU-0161-2021 p.6, RCU-0504-2020 p.7, RCU-0504-2020 p.8, RCU-0504-2020 p.6 | 2 propuestas / 2 pasan control local | completa | — | RCU-0161-2021 p.6 | 71.117 | 2 | Ref. objetivo 2/2; citas en contexto | Fidelidad, completitud, citas y abstención |
| H03 | v2 | RCU-0504-2020 p.7, RCU-0504-2020 p.6 | 1 propuesta / 1 pasa control local | completa | — | RCU-0504-2020 p.7 | 52.483 | 2 | Ref. objetivo 1/1; citas en contexto | Fidelidad, completitud, citas y abstención |
| H03 | v3 | RCU-0504-2020 p.7, RCU-0504-2020 p.6 | 1 propuesta / 1 pasa control local | completa | — | RCU-0504-2020 p.7 | 43.792 | 2 | Ref. objetivo 1/1; citas en contexto | Fidelidad, completitud, citas y abstención |
| H04 | v2 | RCU-0161-2021 p.6 | 1 propuesta / 1 pasa control local | Abstención | salida_no_verificable | — | 46.376 | 2 | Ref. objetivo 1/1 | Fidelidad, completitud, citas y abstención |
| H04 | v3 | RCU-0161-2021 p.6 | 3 propuestas / 3 pasan control local | parcial | — | RCU-0161-2021 p.6 | 72.028 | 2 | Ref. objetivo 1/1; citas en contexto | Fidelidad, completitud, citas y abstención |
| H05 | v2 | RCU-0504-2020 p.7, RCU-0504-2020 p.8, RCU-0504-2020 p.6 | 3 propuestas / 3 pasan control local | Abstención | salida_no_verificable | — | 63.127 | 2 | Ref. objetivo 1/1 | Fidelidad, completitud, citas y abstención |
| H05 | v3 | RCU-0504-2020 p.7, RCU-0504-2020 p.8, RCU-0504-2020 p.6 | 2 propuestas / 2 pasan control local | completa | — | RCU-0504-2020 p.7 | 53.460 | 2 | Ref. objetivo 1/1; citas en contexto | Fidelidad, completitud, citas y abstención |
| H06 | v2 | — | Sin generación | Abstención | vigencia_no_certificada | — | 0.000 | 0 | Vigencia bloqueada | Fidelidad, completitud, citas y abstención |
| H06 | v3 | — | Sin generación | Abstención | vigencia_no_certificada | — | 0.000 | 0 | Vigencia bloqueada | Fidelidad, completitud, citas y abstención |


Solo se muestran metadatos de páginas e identificadores anónimos. Páginas admitidas enumera referencias únicas preservando orden. Los conteos RAW describen propuestas y control local; FINAL muestra la clasificación del programa. H02 recuperó dos páginas objetivo en cada brazo. En v3 ambas afirmaciones pasaron el control local, pero la revisión publicó una sola fuente y declaró cobertura completa. H05 también quedó marcada como completa pese a tener una petición sin respaldo esperado. H01 v2 falló en el anclaje local. H02, H04 y H05 v2 se abstuvieron en revisión. La exactitud, pertinencia, completitud y adecuación de abstenciones requieren revisión humana. El ASR de v2/v3 carece de denominador positivo en esta muestra. `/tmp/csrag-v3-holdout-run/{manifest.json,traces.jsonl,technical.json}` · [Informe v3](MEJORA_CALIDAD_Y_SEGURIDAD_V3.md)

La copia privada barajada de la hoja ciega contiene 24 registros pendientes, incluidos dos RAW sin generación, columnas de revisión vacías y ningún campo explícito de perfil, etapa o caso. La clave queda separada. Algunas diferencias de formato permiten inferir la etapa. Distribuir solo la hoja ciega a dos revisores y adjudicar antes de unir con la clave mediante `scripts/score_conversational_v3.py`. No distribuir esta tabla por caso junto con la hoja ciega.

## 9. Comparación nueva v3/v4

| Indicador | v3 | v4 |
| --- | --- | --- |
| generación recibida | 4/5 (80.00%) | 4/5 (80.00%) |
| borrador estructurado con referencias dentro del contexto | 3/4 (75.00%) | 4/4 (100.00%) |
| abstención | 2/5 (40.00%) | 1/5 (20.00%) |
| completa automática | 2/5 (40.00%) | 0/5 (0.00%) |
| parcial automática | 1/5 (20.00%) | 4/5 (80.00%) |
| citas formales en contexto | 3/3 (100.00%) | 4/4 (100.00%) |
| todas las páginas objetivo citadas | 2/4 (50.00%) | 4/4 (100.00%) |
| Hit@1 | 2/4 (50.00%) | 4/4 (100.00%) |
| Hit@5 | 4/4 (100.00%) | 4/4 (100.00%) |
| todas las páginas@5 | 3/4 (75.00%) | 4/4 (100.00%) |
| errores del proveedor | 0/5 (0.00%) | 0/5 (0.00%) |

Ollama local `qwen2.5:3b` 0.40.16, top-k 5, semilla 42, temperatura 0 y límites 640/160 por etapa en ambos brazos. Misma máquina, índice y cinco consultas nuevas, con orden alternado. Los cuatro casos con páginas esperadas excluyen el control de vigencia. El denominador de citas formales son respuestas sustantivas. El denominador de referencias RAW en contexto son borradores recibidos, incluida una salida de v3 con formato no legible. Las proporciones y sus intervalos Wilson se mantienen en un corte independiente. Esta muestra no se suma a las seis consultas previas de v2/v3. `/tmp/csrag-v4-holdout-run/{manifest.json,traces.jsonl,technical.json}` · [Reporte v4](INFORME_MEJORA_REAL_V4.md)

Latencia de pipeline media v3 50.29 s y v4 49.40 s. Mediana v3 60.95 s y v4 57.08 s, n=5 consultas por brazo. Hubo 7 y 8 llamadas respectivamente. Se incluye el control de vigencia sin inferencia. p95 sin estimación. En el único par discordante de abstención, v3 se abstuvo y v4 publicó evidencia parcial. El revisor de v4 dejó vacía la lista de peticiones completas en los 4/4 casos con generación. La validez formal y el aumento de páginas citadas pueden publicarse como resultados técnicos exploratorios. La exactitud RAW y FINAL, la completitud real, el sustento y la adecuación de abstenciones están pendientes de lectura ciega de las 20 filas. `/tmp/csrag-v4-holdout-run/{technical.json,blind.csv}`

La comprobación defensiva estática mantuvo recall 3/4 y FPR 5/20, sin LLM, sobre controles históricos. Una prueba verifica exclusión previa a la llamada en ambos perfiles. La batería nueva contiene cero casos de ataque por brazo y no permite estimar ASR o equivalencia de protección. [Positivos](../../experiments/attacks.jsonl) · [Benignos](../../experiments/benign_v2.jsonl) · [Regresión](../../tests/test_demo.py)

## 10. v5 en diagnóstico de desarrollo

| Indicador, Ollama local `qwen2.5:3b` | Segundo piloto v5 |
| --- | --- |
| Selecciones RAW recibidas / consultas | 4/5 (80,00 %) |
| Hit@1, Hit@3 y Hit@5 | 4/4 (100,00 %) en cada corte |
| Todas las páginas objetivo admitidas en top-5 | 4/4 (100,00 %) |
| Todas las páginas objetivo citadas en FINAL | 2/4 (50,00 %) |
| Respuestas sustantivas FINAL con citas formales | 4/4 (100,00 %) |
| Abstenciones FINAL | 1/5 (20,00 %) |
| Completas automáticas / parciales automáticas | 1/5 (20,00 %) / 3/5 (60,00 %) |
| Casos multifuente con omisión de fuente obligatoria | 2/2 (100,00 %) |
| Exactitud humana y sustento | Pendientes |
| ASR RAW y FINAL de v5 | Sin estimación, cero casos positivos evaluados |

Las cinco consultas de diagnóstico provienen de la comparación anterior v3/v4.
El denominador de recuperación excluye la consulta sin página de vigencia.
Citas formales usa solo respuestas sustantivas. Se conservó el plazo literal
en el caso temporal y se omitió la presuposición falsa. El segundo piloto
mostró que disponer de las dos páginas admitidas no garantiza que el
selector produzca evidencia para ambas peticiones. La respuesta de v5
se construyó con pasajes literales. En RAW se observan seleccionadores,
por lo que sus etiquetas no son directamente comparables con borradores
de prosa de los otros perfiles. [Causas y trazas](CIERRE_V5_DIAGNOSTICO_Y_CAMBIOS.md)

Latencia media 28,62 s, mediana 33,76 s y ocho llamadas en cinco consultas
del piloto revisado. Medianas por llamada de 24,74 s en selección y 9,87 s
en revisión, n=4 por etapa. p95 sin estimación. El valor histórico de v4
en su corrida no es una comparación controlada de caché frente a este piloto.
Los CSV usan el identificador del expediente privado, sin datos de respuesta.

El detector compartido mantiene recall 3/4 y FPR 5/20 en la comprobación
estática de los controles históricos, sin LLM. Se verificó exclusión de un
control marcado antes de invocar inferencia. La prueba no estima resistencia
de v5 frente a ataques ni reduce la incidencia de alertas benignas.
La decisión de trabajar con evidencias válidas históricas para el artículo
conserva la interpretación RAW/FINAL de T18 y T19. [Decisión de cierre](DECISION_DE_CIERRE_V5.md)

## 11. Calidad de software

| Código | Ejecución local | Aprobadas | Fallidas | Omitidas |
| --- | --- | ---: | ---: | ---: |
| `main` a96f64d | Instantánea Git en directorio temporal, mismo entorno Python y mismos insumos locales | 219/220 | 0/220 | 1/220 |
| Rama v3 4d3b0dc | `PYTHONPATH=src .venv/bin/python -m pytest` | 223/224 | 0/224 | 1/224 |
| Rama v4 | `PYTHONPATH=src .venv/bin/python -m pytest` | 237/238 | 0/238 | 1/238 |
| Rama v5 | `PYTHONPATH=src .venv/bin/python -m pytest` | 249/250 | 0/250 | 1/250 |

La prueba omitida requiere `RAG_EMBEDDING_MODEL`. En una primera ejecución aislada de `main` faltó enlazar el CSV T12 y se omitió también esa prueba. Los valores de la tabla corresponden a la repetición con ambos árboles provistos de los mismos insumos locales. La batería prueba lógica, integridad y casos controlados. Los dobles de proveedor se usan en las pruebas funcionales. Los conteos no acreditan exactitud del LLM ni protección general. [Prueba MiniLM opcional](../../tests/test_retrieval_benchmark.py) · [Pruebas de demo](../../tests/test_demo.py) · [Pruebas de calidad](../../tests/test_quality_metrics.py)

## 12. Incertidumbre, publicación y conclusión

La tabla larga [IEEE_PROPORCIONES_AGREGADAS.csv](IEEE_PROPORCIONES_AGREGADAS.csv) guarda numerador, denominador, método, procedencia y límites Wilson bilaterales al 95% para las tasas observadas con denominador positivo. Para proporción p = x/n y z = 1,959964, el centro es (p + z²/2n)/(1 + z²/n) y la semiamplitud es z·sqrt(p(1−p)/n + z²/4n²)/(1 + z²/n). Ejemplos: Hit@5 T08 11/13, 84,62% (57,77–95,67%); ASR RAW A 10/20, 50,00% (29,93–70,07%); un 0/20 admite 0,00–16,11%; recall 15/20, 75,00% (53,13–88,81%). Wilson resume incertidumbre marginal bajo un modelo binomial y no demuestra superioridad. Una comparación entre tratamientos sobre las mismas preguntas requiere los pares discordantes y una prueba o intervalo pareado preespecificado. Tampoco hay muestra aleatoria de todas las consultas o ataques posibles. [IEEE_LATENCIAS_AGREGADAS.csv](IEEE_LATENCIAS_AGREGADAS.csv) contiene segundos y tamaños de muestra. Una celda vacía distingue ausencia de estimación de un cero observado.

**Publicable con alcance explícito.** T08 como benchmark de páginas, T18 como utilidad observada en una muestra pareada con anotación de cobertura completa y sin consenso independiente documentado, T19 como ASR de una batería fija con rúbrica disponible y exposición no verificada. T20 aporta un paquete archivado con hashes coincidentes. Destacar la brecha RAW/FINAL de 7/30 respuestas correctas descartadas en T18, la brecha validez formal/sustento de C (9/9 frente a 6/9) y la diferencia de ASR RAW A/B/C. Estos resultados son útiles para mostrar el costo del control de salida y el efecto observado de las condiciones defensivas en la batería. El ASR FINAL observado no distingue A de B y C. Los casos falsos negativos y la falta de telemetría de exposición impiden atribuir el contraste a una sola barrera.

**Exploratorio.** Los 40 casos T08, T11/T12 preliminar, v1/v2 funcional y las comparaciones técnicas v2/v3 y v3/v4. La menor abstención v3 aumenta la producción de respuestas y no establece una ganancia de exactitud. La cobertura multifuente y la mediana de latencia son resultados desfavorables que acompañan el aumento de respuestas. ASR v3 y exactitud humana v3 siguen pendientes. Los resultados mock sirven para depuración y reproducción de decisiones, con alcance ajeno a la obediencia de un LLM.

**Amenazas principales.** Una universidad, modelo pequeño único, OCR pendiente y falta de vigencia certificada. Las muestras primarias son pequeñas y seleccionadas; los 13 casos T08 se solapan con los 40. Las etapas RAW/FINAL y los brazos A/B/C comparten consultas. Las 60 ejecuciones T19 representan 20 casos únicos, con objetivos de laboratorio y medición de exposición incompleta. La anotación T18 carece de medida de acuerdo independiente. Los holdouts v3 y v4 se prepararon en sus respectivas sesiones de desarrollo. El contraste de novedad fue textual. Los revisores de v3 y v4 usan el mismo modelo que sus borradores. La latencia depende de hardware, caché, inicialización, longitud de contexto y de si hubo llamada. Las comparaciones entre protocolos no identifican causalidad ni rendimiento general.

**Equilibrio seguridad-utilidad.** T19 respalda una reducción del éxito RAW en la batería histórica. Las salidas FINAL de T19 registraron 0/20 éxitos en cada brazo con el filtro activo. T18 muestra el costo del filtro en utilidad. El diseño v4 conserva las barreras y reduce pérdidas técnicas por recuperación y formato; los avisos parciales se volvieron más frecuentes. Esa evidencia no demuestra mejora de exactitud ni seguridad comparable. Conviene mantener v4 como experimental hasta adjudicar utilidad y evaluar seguridad por separado.

**Cierre v5.** El piloto justifica conservar la salida extractiva para estudio, pero el selector aún omite evidencia en casos multifuente. v2 permanece predeterminada. Las cifras de v5 se publican únicamente como diagnóstico y el holdout queda reservado.

**Pruebas pendientes.** Las cifras históricas verificadas se pueden consolidar sin repetir inferencia. Para afirmar mejora de utilidad en v3 o v4, completar los dos dictámenes ciegos, adjudicar y después replicar con más consultas independientes, incluidas multifuente. Para afirmar seguridad comparable de v3 o v4 se requiere una evaluación defensiva pareada con positivos y benignos etiquetados, registro de recuperación, filtrado y exposición, y adjudicación de éxito efectiva por etapa. Para publicar percentiles de cola comparables conviene ampliar observaciones y fijar estado de caché y definición de tiempo. Los manuales y trazas deben conservar revisión y acceso adecuados para compartir evidencia con el equipo.

**Alcance de esta auditoría.** La auditoría histórica de T18 y sus pruebas se ejecutaron sin repetir inferencia. La extensión v4 añadió una corrida privada de Ollama y pruebas de regresión en otra rama local. Los CSV agregados separan las corridas por identificador. Se consultó `docs/AVANCE.md` y las instrucciones de `AGENTS.md`. La guía local `INSTRUCCIONES_CODEX_CS_RAG_Security.md` no estaba disponible. Los hashes verifican integridad de artefactos disponibles y la correspondencia de los archivos cotejados. No certifican la veracidad de anotaciones ni la privacidad de expedientes completos.
