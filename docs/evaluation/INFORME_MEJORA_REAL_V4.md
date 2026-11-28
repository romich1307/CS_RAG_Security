# Mejora de calidad documental v4

## Pérdidas de T18 y causa comprobada

El cruce usa la clave corrida, pregunta y condición entre las 60 anotaciones, la correspondencia ciega y las 30 trazas de T17. Se seleccionaron los siete pares con RAW anotada como correcta y FINAL distinta de correcta. En los siete se generó un borrador con Ollama local `qwen2.5:3b`; la respuesta FINAL fue una abstención anotada como inadecuada. El validador registró `citas_invalidas_o_ausentes`, cero coincidencias de la expresión canónica y cero alertas del detector. El cero de citas inválidas significa que el parser no reconoció una cita para validar. Puede coexistir con una referencia errada en prosa.

| Sufijo de ID ciego | Brazo | Hallazgo en RAW | Tratamiento técnicamente justificado |
| --- | --- | --- | --- |
| 01 | B | PDF y página correctos en prosa. El texto desarrolla el límite y el supuesto de convalidación. La anotación declara sustento completo. | Construir la cita desde un pasaje ya verificado. |
| 05 | B | La respuesta identifica el plan correcto, pero la referencia en prosa escribe un nombre de PDF con un dígito omitido. La anotación marca la cita fuera de contexto y sin sustento. | Rechazar la referencia original. Emitir una cita solo tras anclar la afirmación al pasaje correcto. |
| 14 | A | Sin cita. La respuesta identifica el plan y añade una formulación de alcance ambiguo y motivaciones accesorias. | Exigir anclaje y revisar alcance antes de publicar. |
| 15 | B | PDF y página correctos en prosa. La anotación confirma el retiro automático y la tolerancia adicional. | Construir la cita desde un pasaje ya verificado. |
| 17 | B | Artículo, PDF y página correctos en prosa. La enumeración está respaldada según la anotación. | Construir la cita desde un pasaje ya verificado. |
| 18 | B | PDF y página correctos en prosa. La equivalencia consta en el pasaje. | Construir la cita desde un pasaje ya verificado. |
| 19 | A | Sin cita. La respuesta contiene el supuesto solicitado y agrega otros supuestos y trámite. La anotación reconoce corrección del contenido pedido. | Conservar solo afirmaciones pertinentes verificadas y citar su pasaje. |

Cuatro de los siete casos tienen un defecto de formato con cita documental adjudicada como válida. Los otros tres requieren resolver ausencia o error de atribución. En A/B no había control de cobertura independiente capaz de explicar la decisión observada ni descarte por detector en estas trazas. Esta auditoría conserva el juicio histórico y distingue corrección de contenido, pertinencia y atribución.

La procedencia de selección y causas está en `results/llm_abc_local/t17_ollama_20261121_r2/evaluacion/{t17_anotaciones_t18.csv,t17_correspondencia_privada.json}`, `results/llm_abc_local/t17_ollama_20261121_r2/traces.json` y su contrapartida privada `privado/private_traces.json`. La traza pública tiene SHA-256 `d89b0b1c8bc8d72dbc7d62cc78595f7986034a79daa59ac352f14269e77dbb3c`, que coincide con el manifiesto T20. Las dos copias privadas consultadas son idénticas por SHA-256 `616ef6d8fda77e6f73a50c79d1fe87863bb7640ea21af573fe9ec5925cc8560d`. Se conservan fuera de Git.

## Intervención

- v3 ya evita depender de que el modelo redacte citas canónicas. v4 mantiene el renderizado por metadatos y verifica que el pasaje exista, que su archivo y página sean válidos y que corresponda a la resolución nombrada para la petición asignada. El anclaje exige una coincidencia continua con límites léxicos. La normalización se restringe a espacios, NFC, comillas tipográficas y guion opcional invisible. Los filtros de salida se aplican por separado y el revisor todavía comprueba sustento.
- v4 enumera las peticiones explícitas separadas por preguntas, punto y coma o coordinación interrogativa. Recupera en cada ámbito, con o sin una resolución explícita, y alterna pasajes dentro del mismo presupuesto. El borrador asigna declaraciones a las peticiones. El revisor informa qué afirmaciones acepta y qué peticiones se contestaron completamente.
- La decisión global se calcula en Python. Una petición sin afirmación aceptada o sin alguna resolución exigida impide declarar cobertura completa aunque el revisor la marque. El código conserva afirmaciones verificadas si quedan otras peticiones sin respuesta. La estructura se limita a cinco peticiones y declara cobertura parcial si excede ese máximo. La segmentación explícita no garantiza identificar todas las coordinaciones implícitas. El juicio de completitud semántica dentro de una misma petición sigue dependiendo del revisor.
- El umbral, exclusiones de OCR y vigencia, detector heurístico de entrada y guardas de salida se conservan. El borrador debe describir obligaciones documentales sin reproducir imperativos. La prueba de regresión confirma que la normalización evita rechazar un anclaje por la variante tipográfica de las comillas. No se ajustaron las reglas binarias del detector que causaron las alertas benignas de T15; esos falsos positivos siguen abiertos.
- Los mensajes de sistema definen el protocolo y los datos se serializan en un mensaje de usuario. El pipeline trata el texto recuperado como datos y la inferencia no tiene acceso a herramientas de ejecución. Esa separación no garantiza que el LLM ignore toda instrucción incrustada. Se conserva `demo_conversacional_v3` como referencia y la selección de v4 es explícita en Streamlit o mediante `--demo --demo-version 4`.

## Evaluación preespecificada

Se reservaron cinco preguntas nuevas redactadas desde el corpus, con páginas objetivo fijadas antes de inferencia. Hay dos consultas multifuente, una pregunta simple, una petición con evidencia parcial esperada y un control de vigencia. SHA-256 de las consultas `6dd912707a9c941efec2f0ef58823e77bfe7307e028429d9314d661ea4dd27f5`. El cotejo normalizado halló 0/5 duplicados textuales respecto de las 40 preguntas gold y las ocho consultas de piloto y verificación de v3. La novedad semántica y los juicios sobre las páginas requieren confirmación independiente. Los casos de T18 se usaron para diagnóstico, y los contratos se comprobaron mediante pruebas con hechos ficticios y con un control de filtrado existente.

Ollama local `qwen2.5:3b`, semilla 42, temperatura 0, top-k 5, mismos 640/160 tokens máximos de borrador/revisión, mismo índice, proceso, máquina y orden alternado por par. Se aplica la rúbrica de [v3](MEJORA_CALIDAD_Y_SEGURIDAD_V3.md#rúbrica-y-denominadores) a ambas versiones. Hit@k mide alguna página objetivo entre los pasajes admitidos. Se informa por separado si las citas FINAL cubren **todas** las páginas objetivo, sin atribuirles por ello apoyo semántico. La exactitud usa cinco consultas previstas por versión y etapa. El p95 se omite con menos de 20 observaciones válidas por brazo.

```sh
PYTHONPATH=src .venv/bin/python -m pytest
PYTHONPATH=src .venv/bin/python scripts/evaluate_conversational_v4.py \
  --cases /tmp/csrag-v4-holdout.json --output /tmp/csrag-v4-replica
```

La ruta de salida debe ser nueva y privada. Si se replica en el puerto 11435, establecer `RAG_LOCAL_URL=http://127.0.0.1:11435/api/chat`. El manifiesto registra hashes del índice, insumos, ejecutor y código. La corrida original vive en `/tmp/csrag-v4-holdout-run`. Para revisión humana, distribuir solo `blind.csv`; conservar privada `key.csv` hasta adjudicar. La presentación de citas puede revelar etapa por inferencia. Dos revisiones independientes deben clasificar corrección, completitud, citas y abstención según la rúbrica, conservando las discrepancias hasta el consenso.

## Resultados pareados y diagnósticos

Ollama local `qwen2.5:3b` 0.40.16. Las etiquetas de cobertura son del pipeline. Los cuatro casos con páginas incluyen el caso de evidencia parcial y excluyen el control de vigencia. Los intervalos Wilson bilaterales al 95% se encuentran en el [CSV consolidado](IEEE_PROPORCIONES_AGREGADAS.csv).

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

| Caso privado anónimo | v3 FINAL | v4 FINAL |
| --- | --- | --- |
| N01 | completa; RCU-0161-2021 p.5; 57.64 s | parcial; RCU-0161-2021 p.5; 57.08 s |
| N02 | parcial; RCU-0161-2021 p.5; 64.06 s | parcial; RCU-0161-2021 p.5, RCU-0504-2020 p.8; 69.44 s |
| N03 | salida_formato_o_anclaje_invalido; sin cita; 60.95 s | parcial; RCU-0504-2020 p.5, RCU-0161-2021 p.5; 68.95 s |
| N04 | completa; RCU-0504-2020 p.8; 68.79 s | parcial; RCU-0504-2020 p.8; 51.53 s |
| N05 | vigencia_no_certificada; sin cita; 0.00 s | vigencia_no_certificada; sin cita; 0.00 s |

- N02 muestra un defecto de recuperación en v3. La primera resolución restringió la búsqueda de la segunda subpregunta sin identificador. v4 recuperó y citó ambas páginas objetivo.
- N03 muestra un defecto de formato en el borrador de v3. v4 recuperó ambas páginas objetivo y las citó tras revisión. El caso combina cambios de recuperación y generación.
- N04 muestra una clasificación de cobertura inapropiada de v3. La salida marcó completa con una única afirmación aceptada en una pregunta de dos partes. v4 conservó la parte respaldada y marcó parcial.
- **Resultado desfavorable**. En las 4/4 consultas con generación de v4 el revisor dejó vacía la lista de peticiones completas. En N01, ambos brazos citaron la misma página, pero v4 declaró parcial donde v3 declaró completa. En los dos casos multifuente, v4 citó ambas páginas y declaró parcial. La presencia de las páginas no resuelve si se contestaron todas las condiciones. Si la revisión humana confirma contenido completo en algún caso, el aviso parcial será una falsa alerta de cobertura.
- Latencia media v3 50.29 s y v4 49.40 s. Mediana v3 60.95 s y v4 57.08 s, n=5 por brazo. La muestra incluye una abstención sin inferencia. Hubo 7 llamadas para 5 consultas en v3 y 8 para 5 en v4. p95 sin estimación en ambos brazos.

## Seguridad y prueba automatizada

El chequeo defensivo del detector compartido, sin LLM ni contenido ejecutado, confirmó recall 3/4 en los positivos de `experiments/attacks.jsonl` y FPR 5/20 en `experiments/benign_v2.jsonl`. La regresión verifica en ambos perfiles que un control histórico marcado queda fuera del contexto antes de cualquier llamada y que referencias fabricadas, anclajes no verificables y tipos inválidos no se publican. El cambio de selección de pasajes y de prompts puede alterar la exposición y el comportamiento ante entradas hostiles. La batería documental con Ollama tiene cero casos positivos y no estima ASR RAW o FINAL. El alcance de esta verificación permite afirmar continuidad de controles locales. La seguridad comparativa de v4 queda pendiente.

La suite final obtuvo **237/238 aprobadas, 0/238 fallidas y 1/238 omitida**. La omisión corresponde al encoder MiniLM opcional. Los 14 casos nuevos cubren omisiones de peticiones y fuentes, búsqueda mixta, tolerancia a diferencias tipográficas, referencias inválidas, rechazo de revisiones malformadas y filtrado antes de generar. T20 conserva 6/6 hashes de entradas y 35/35 de salidas. El código y las reglas históricas de A/B/C quedan intactos.

## Estado de aprobación

v4 queda **experimental**. Se observaron mejores métricas de recuperación y citación de páginas objetivo y una abstención menos. La completitud automática se volvió más conservadora. La exactitud RAW/FINAL, el sustento, la pertinencia de citas y la adecuación de las abstenciones requieren adjudicación humana de las 20 filas. La comparación de seguridad requiere evidencia de exposición y éxito bajo un protocolo defensivo independiente. El informe para el artículo conserva los resultados históricos y presenta esta corrida en su propio corte. [Consolidado IEEE](INFORME_FINAL_METRICAS_ARTICULO_IEEE.md)

El manifiesto local `/tmp/csrag-v4-holdout-run/manifest.json` tiene SHA-256 `0310f6973af732dfc6f9ff2d70c48971b9a855e18f663e7bf886a2ac8e70f41c`. Coincidieron sus 23/23 hashes de entrada. El agregado `/tmp/csrag-v4-holdout-run/technical.json` tiene SHA-256 `06e0daf6bdf35abe7c20be222e63f6fa3e46a8469ce649bc5b8574fb08109cee`. El manifiesto identifica el commit base de v3 y el árbol de trabajo de v4 al inicio; el código ejecutado queda identificado por hashes. Las trazas, la hoja ciega y su clave quedan fuera del repositorio.
