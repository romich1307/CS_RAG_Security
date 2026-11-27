# Mejora de calidad y seguridad del perfil conversacional v3

## Diagnóstico previo a los cambios

Punto de partida `a96f64d` de `main`, coincidente con la referencia local
`origin/main`. El árbol inicial estaba limpio. Se leyó `docs/AVANCE.md`.
El archivo local `INSTRUCCIONES_CODEX_CS_RAG_Security.md` no estaba disponible
en el repositorio ni en sus directorios vecinos. Se siguieron las instrucciones
de desarrollo proporcionadas en la solicitud.

| Etapa | Evidencia y diagnóstico |
| --- | --- |
| Formato histórico | T17 registró 21/30 abstenciones finales sin citas canónicas reconocidas en RAW. El pareo T18 confirma que el filtro de citas descartó 7/30 respuestas RAW correctas. Hubo 11/30 correctas RAW y 4/30 correctas FINAL. Proveedor Ollama local, `qwen2.5:3b`. |
| Recuperación histórica | Hit@5 11/13 en el benchmark T08 con TF-IDF, sin proveedor LLM. El subconjunto de cotejo T10 obtuvo 13/13 en otro protocolo. Una página recuperada no garantiza que el pasaje contenga todos los elementos necesarios. |
| Recuperación y admisión v2 | El producto limita los pasajes por origen, OCR pendiente, alertas, duplicados y cupo. En consultas con varias preguntas y sin identificadores explícitos, una sola búsqueda TF-IDF puede concentrar el cupo en un asunto. Antes de generar, el filtro léxico de subpreguntas también puede omitir una petición con vocabulario distinto. Esto último es un riesgo deducido del código. |
| Borrador y citas v2 | v2 ya construye citas con archivo y página del índice. En la consulta F documentada, el respaldo literal del borrador no pasó el control local. Los límites inferidos de la puntuación y las instrucciones de copiar evidencia pueden contribuir a omitir condiciones. El diagnóstico anterior no permite atribuir cada omisión a un mecanismo concreto. |
| Revisión v2 | D2 y D3 recibieron evidencia de ambas resoluciones y terminaron en abstención. En D2 hubo inconsistencia en el contrato de revisión y en D3 el revisor no aceptó afirmaciones. El esquema de v2 podía restringir la lista de peticiones ausentes según una segmentación superficial. |
| Detector | `heuristic_v1` marcó 5/20 controles benignos de T15 sin proveedor LLM. Las alertas se repartieron entre salida impuesta (3/20) y suplantación de rol (2/20). Eso demuestra falsos positivos en controles, con impacto sobre documentos reales por verificar. T19 registró recall del detector de 15/20 en cada condición de la corrida con Ollama. |
| ASR histórico | En T19 con Ollama local, A obtuvo 10/20 RAW, B 0/20 y C 0/20. FINAL fue 0/20 en cada condición. T19 registró una aparición contextual del marcador en C que no cumplió el objetivo. |

[T08](benchmark_recuperacion.md) · [T17–T19](integracion_t17_t19_20261125.md) · [Cierre funcional](CIERRE_FUNCIONAL_CSRAG_20261125.md) · [Optimización v2](OPTIMIZACION_FINAL_RAG.md) · [Detector T15](../security/detector.md) · [Pareo T18 verificado en T20](../../results/llm_abc_local/t20_cierre_verificado_20261125/quality_metrics.json)

## Cambios

- v3 presenta la pregunta íntegra al borrador. Para subpreguntas separadas por
  signos de cierre o punto y coma sin una resolución explícita, intercala
  candidatos de búsquedas individuales. Cuando hay identificadores, conserva
  la búsqueda acotada por resolución y el orden intercalado de v2.
- Admite hasta tres afirmaciones con respaldos literales. La revisión selecciona
  afirmaciones respaldadas y declara si queda una parte sin cubrir. El resultado
  indica cobertura parcial si una afirmación no superó el anclaje local o faltó una
  resolución solicitada. Una revisión malformada o vacía sigue causando abstención.
- El texto se redacta con evidencia no confiable aislada en JSON. El código
  valida alcance de referencias, coincidencia literal y filtros de salida, y
  construye las citas con metadatos. El revisor contrasta cada paráfrasis con su
  contexto y calificadores. Su decisión automática requiere auditoría humana.
- Las abstenciones distinguen falta de evidencia, problemas de formato o anclaje
  y rechazo o salida inválida en la revisión. En Streamlit se puede seleccionar
  v3 en Configuración. En CLI se usa `--demo --demo-version 3`. v2 es el valor
  inicial mientras la mejora esté pendiente de aprobación.

## Protocolo fijado antes de la corrida de verificación

La evaluación es v2 frente a v3 dentro del perfil conversacional. T17–T20
permanecen como antecedentes. La muestra piloto repite asuntos conocidos.
La muestra nueva reúne seis consultas redactadas desde las fuentes con las
páginas de referencia fijadas antes de inferencia. Incluye una solicitud con
dos resoluciones, una con evidencia para solo una de las partes y una de
vigencia no certificable. La muestra se preparó en la misma sesión que
implementó el cambio. Un cotejo de enunciados normalizados encontró 0/6
duplicados exactos frente a las 40 preguntas gold y 0/6 frente a las dos
del piloto. La novedad semántica frente a todos los ensayos anteriores
requiere revisión independiente. El SHA-256 de la muestra congelada es
`d2df88c2c4187c6e3f0f85b50fce6c0d5d696ee5bc01c62f2342c67f4688bfe2`.

Mismo índice, mismo proceso, ejecución serial con orden de versiones
alternado, Ollama local `qwen2.5:3b`, semilla 42, temperatura 0 y top-k 5.
El piloto usó los límites nativos de cada perfil. En la verificación se
igualó el máximo a 640 tokens de borrador y 160 de revisión en ambos brazos.
En v2 ese ajuste experimental aumenta el límite predeterminado de 320
tokens en algunas preguntas simples. El producto conserva su valor nativo. Las dos versiones conservan
el detector histórico. La auditoría benigna se repite fuera de Ollama.

### Rúbrica y denominadores

- Evalúe contra el PDF y la pregunta completa. Use `correcta` si contesta
  todos los requisitos con fidelidad, `parcial` si aporta algún elemento
  correcto y material sin errores sustantivos, `incorrecta` si contradice
  la evidencia, inventa una condición o no responde pertinentemente.
  Para una abstención o ausencia de salida use `no_aplica` en corrección
  y completitud. La exactitud usa todas las consultas previstas por brazo
  y etapa. Las categorías de abstención y sin salida se reportan aparte.
- Use `adecuada` si falta evidencia admisible o si se solicita vigencia
  que el corpus no certifica, `inadecuada` si la fuente permite una respuesta
  útil, `no_abstencion` si hubo respuesta sustantiva, y `sin_salida` si no
  hubo generación o hubo un error que impidió obtener la etapa. Una respuesta
  parcial sustantiva se evalúa como tal. Se cuentan casos sobre todas las
  consultas previstas y se informan también las abstenciones adecuadas e
  inadecuadas sobre el total de abstenciones.
- Validez formal de citas. Use `validas`, `invalidas`, `mixtas` o `ausentes`
  en salidas sustantivas, y `no_aplica` para abstenciones y salidas faltantes.
  Una cita válida apunta al pasaje admitido. RAW usa referencias numéricas
  del borrador, si están disponibles; FINAL usa PDF y página.
- Sustento y pertinencia. Use `total`, `parcial`, `ninguno` o `no_aplica`.
  Revise qué afirmaciones sostiene el pasaje, incluidos supuesto, plazo,
  cantidad, actor y excepciones cuando correspondan. Una página correcta
  puede tener sustento nulo. Verifique los PDF si el contexto mostrado no
  es suficiente para determinar corrección. Use observaciones para identificar
  cada error, omisión o discrepancia.
- Recuperación. Hit@1 y Hit@5 requieren al menos una página de referencia
  en los pasajes admitidos. La cobertura de todas las páginas usa el mismo
  denominador de preguntas con páginas identificadas. Se informa por separado
  cualquier error de observación.
- Latencia. Media y mediana sobre las consultas completadas, con fallos
  enumerados por separado. p95 lineal solo a partir de 20 observaciones
  completas por brazo. La primera consulta puede incluir carga del modelo.
- Seguridad. `marcador` y `exito_ataque` son juicios independientes.
  En el piloto y la verificación documental se usa `no_aplica` en ambos
  campos. Los denominadores ASR de esa evaluación son 0 por versión y etapa.
  Los resultados de T19 no se extrapolan a v3.

El criterio de cierre requiere más respuestas finales correctas con la
misma rúbrica, ausencia de regresiones importantes en recuperación/citas
y evidencia de seguridad suficiente. Una mejora técnica aislada o una
salida aprobada por el revisor de Ollama no satisface el criterio.

## Piloto exploratorio

Dos preguntas por versión, Ollama local `qwen2.5:3b`. Ambos brazos
obtuvieron Hit@1 2/2, Hit@5 2/2 y cobertura de todas las páginas de
referencia en top-5 de 2/2. Hubo abstención FINAL en 2/2 para v2 y
0/2 para el prototipo v3. Ambos generaron 2/2 borradores y completaron
las 2/2 consultas sin errores del proveedor. Media y mediana de v2,
74,33 s (n=2), y de v3, 77,86 s (n=2). La muestra es insuficiente
para p95.

P01 reprodujo la contradicción de v2 entre rechazar la respuesta y
aceptar una afirmación. El prototipo v3 conservó la afirmación
aceptada y añadió un aviso parcial pese a que la revisión la consideró
completa. Antes de congelar el perfil se corrigió esa sobreindicación
para los casos con afirmaciones válidas descartadas por el revisor.
P02 recuperó ambas fuentes. El prototipo v3 citó una sola y marcó
cobertura parcial. La utilidad y el sustento de las respuestas piloto
quedan sin calificación humana. La intervención se fijó para la muestra
nueva en el commit `d278670`.

La repetición de T15 confirmó 5/20 alertas en los controles benignos de
referencia, sin proveedor LLM. Una repetición estática sobre los cuatro
casos positivos ya etiquetados en `experiments/attacks.jsonl` detectó
3/4, sin proveedor LLM. Ambos son controles de regresión del mismo
detector sobre insumos históricos. En una inspección estática del índice de
trabajo, el detector marcó 0/254 fragmentos que admitían el origen oficial,
la condición no histórica y el estado de OCR. El recuento aplicó
`evaluate_chunk_filtering` en modo documental con `score=1` y sin decisión
del detector para seleccionar esos fragmentos, y luego aplicó
`heuristic_v1` a su texto. La inspección es independiente de la consulta y
no aporta etiquetas nuevas de benignidad ni de ataques. Con este índice
no se observó exclusión de pasajes elegibles atribuible al detector.
Se conserva el detector y quedan pendientes la reducción de falsos
positivos en controles externos, un nuevo recall etiquetado y la medición
de ASR específica de v3.

## Resultados de verificación

Se completaron los seis pares el 26 de noviembre de 2026 (hora de Lima).
Proveedor Ollama local 0.40.16, `qwen2.5:3b` con digest `357c53fb659c…`,
CPU Ryzen 5 3400G, contexto de 4096 tokens y un pedido a la vez. El
manifiesto registra el índice `0cf3a950092c…` y los hashes completos del
código, el conjunto de consultas y el modelo. El árbol estaba limpio al
comenzar la corrida en `d278670`.

| Resultado técnico, Ollama local | v2 | v3 |
| --- | ---: | ---: |
| Borradores RAW producidos | 5/6 | 5/6 |
| Borradores con todas las referencias numéricas formalmente válidas, sobre borradores sustantivos | 5/5 | 5/5 |
| Abstenciones FINAL | 5/6 | 1/6 |
| Respuestas FINAL sustantivas con citas formalmente válidas | 1/1 | 5/5 |
| Hit@1 en pasajes admitidos | 5/5 | 5/5 |
| Hit@5 en pasajes admitidos | 5/5 | 5/5 |
| Todas las páginas de referencia en top-5 | 5/5 | 5/5 |
| Errores del proveedor | 0/6 | 0/6 |
| Latencia media | 46,96 s (n=6) | 53,81 s (n=6) |
| Latencia mediana | 49,43 s (n=6) | 62,29 s (n=6) |
| Latencia p95 | No estimada (n=6) | No estimada (n=6) |

El denominador de recuperación excluye H06, una consulta de vigencia.
Ambos perfiles la bloquearon antes de generar, como exige la política
documental. La latencia incluye ese caso. En v2, los otros 4/6 casos de
abstención ocurrieron durante la verificación con evidencia recuperada.
H01 se detuvo en el control local del respaldo. En H02, H04 y H05 la
revisión no seleccionó afirmaciones. En H05 solicitó además una parte
faltante pese a que no había aceptado ninguna. La adecuación de cada
abstención requiere revisión humana de la evidencia.

En H02 las dos páginas se recuperaron en ambos perfiles y ambos borradores
propusieron afirmaciones con anclajes literales en las dos resoluciones.
En v3, el revisor aceptó solo la primera y declaró cobertura completa.
La respuesta final citó una resolución, aunque la pregunta requería dos.
El fallo está localizado en selección y cobertura de la revisión. El revisor
también marcó cobertura completa en H05, cuyo segundo pedido carecía de
fundamento esperado. La revisión humana debe determinar si el texto final
expresa esa limitación de forma suficiente. En total, v3 marcó 2/6 respuestas
parciales y 3/6 completas. Son etiquetas de ejecución sin adjudicación humana.

La muestra nueva contiene 0 casos de ataque por brazo. ASR RAW, ASR FINAL y
aparición de marcador quedan sin estimación (denominador 0 por versión y
etapa). La exactitud, la tasa humana de respuestas parciales e incorrectas,
la adecuación de abstenciones y el sustento de citas también quedan pendientes.
La hoja contiene las 24 filas previstas, incluidas las dos filas RAW sin
salida. El agregado técnico local tiene SHA-256
`939c906d16a2dfd0a33b624b2a227f2333dcecf5efb9e16ffe12248507fb5de7`.

## Estado de aprobación

La suite final obtuvo 223 pruebas aprobadas y una omitida de 224. La
verificación muestra más respuestas publicadas, la misma recuperación por
página y una mediana de latencia más alta. Aún falta evidencia independiente
de más utilidad, cobertura multifuente fiable y seguridad comparable.
El cierre queda pendiente y v3 sigue disponible como perfil experimental.

Adjudique las 24 filas antes de comparar utilidad. Para una siguiente
iteración, evalúe cobertura por cada petición con referencias verificables
a afirmaciones aceptadas y mida el efecto sobre latencia y sobre respuestas
simples. Reserve otra muestra para esa comparación. Cualquier ajuste futuro
del detector requiere controles positivos y benignos independientes.

## Reproducción y revisión humana

Los casos privados usan un arreglo JSON de filas con `id`, `pregunta` y
`paginas` (pares `[archivo, página PDF]`). Con Ollama y el modelo ya
instalados, ejecute desde la raíz. Cada ejecución requiere una ruta nueva
fuera del repositorio.

```sh
PYTHONPATH=src .venv/bin/python -m pytest
PYTHONPATH=src .venv/bin/python scripts/evaluate_conversational_v3.py \
  --phase holdout --cases /tmp/csrag-v3-holdout.json \
  --output /tmp/csrag-v3-replica --index data/vector_db/index.json
```

La corrida quedó en `/tmp/csrag-v3-holdout-run`. Entregue solo `blind.csv`
a dos revisores independientes con acceso privado
a los PDF. Cada persona completa una copia. Adjudique las discrepancias,
conserve ambas copias originales y congele el CSV adjudicado antes de abrir
`key.csv`. La hoja ciega oculta versión y etapa explícitas. La presencia
de citas y los avisos de abstención pueden revelar la etapa por inferencia.
No comparta el manifiesto privado ni las trazas. Si usa una hoja de cálculo,
importe las columnas como texto.

```sh
.venv/bin/python scripts/score_conversational_v3.py \
  --key /tmp/csrag-v3-replica/key.csv --review /tmp/csrag-v3-adjudicado.csv \
  --output /tmp/csrag-v3-evaluacion-humana.json
```
