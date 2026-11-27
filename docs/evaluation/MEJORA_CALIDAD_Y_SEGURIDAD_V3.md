# Mejora de calidad y seguridad del perfil conversacional v3

## Diagnóstico previo a los cambios

Punto de partida `a96f64d` de `main`, coincidente con la referencia local
`origin/main`. El árbol inicial estaba limpio. Se leyó `docs/AVANCE.md`.
El archivo local `INSTRUCCIONES_CODEX_CS_RAG_Security.md` no estaba disponible
en el repositorio ni en sus directorios vecinos. Se siguieron las instrucciones
de desarrollo proporcionadas en la solicitud.

| Etapa | Evidencia y diagnóstico |
| --- | --- |
| Formato histórico | T17 registró 21/30 abstenciones finales por ausencia de citas canónicas reconocidas en RAW. La expresión regular histórica podía descartar contenido correcto. T18 registra 11/30 correctas RAW y 4/30 correctas FINAL. Proveedor Ollama local, `qwen2.5:3b`. |
| Recuperación histórica | Hit@5 11/13 en el benchmark T08 con TF-IDF, sin proveedor LLM. El subconjunto de cotejo T10 obtuvo 13/13 en otro protocolo. Una página recuperada no garantiza que el pasaje contenga todos los elementos necesarios. |
| Recuperación y admisión v2 | El producto limita los pasajes por origen, OCR pendiente, alertas, duplicados y cupo. En consultas con varias preguntas y sin identificadores explícitos, una sola búsqueda TF-IDF puede concentrar el cupo en un asunto. Antes de generar, el filtro léxico de subpreguntas también puede omitir una petición con vocabulario distinto. Esto último es un riesgo deducido del código. |
| Borrador y citas v2 | v2 ya construye citas con archivo y página del índice. En la consulta F documentada, el respaldo literal del borrador no pasó el control local. Los límites inferidos de la puntuación y las instrucciones de copiar evidencia pueden contribuir a omitir condiciones. El diagnóstico anterior no permite atribuir cada omisión a un mecanismo concreto. |
| Revisión v2 | D2 y D3 recibieron evidencia de ambas resoluciones y terminaron en abstención. En D2 hubo inconsistencia en el contrato de revisión y en D3 el revisor no aceptó afirmaciones. El esquema de v2 podía restringir la lista de peticiones ausentes según una segmentación superficial. |
| Detector | `heuristic_v1` marcó 5/20 controles benignos de T15 sin proveedor LLM. Las alertas se repartieron entre salida impuesta (3/20) y suplantación de rol (2/20). Eso demuestra falsos positivos en controles, con impacto sobre documentos reales por verificar. T19 registró recall del detector de 15/20 en cada condición de la corrida con Ollama. |
| ASR histórico | En T19 con Ollama local, A obtuvo 10/20 RAW, B 0/20 y C 0/20. FINAL fue 0/20 en cada condición. T19 registró una aparición contextual del marcador en C que no cumplió el objetivo. |

Fuentes. [T08](benchmark_recuperacion.md) · [T17–T19](integracion_t17_t19_20261125.md) · [Cierre funcional](CIERRE_FUNCIONAL_CSRAG_20261125.md) · [Optimización v2](OPTIMIZACION_FINAL_RAG.md) · [Detector T15](../security/detector.md)

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
vigencia no certificable. No se comparó semánticamente contra todas las
preguntas históricas, y la misma persona implementó el cambio y preparó la
muestra. La revisión humana independiente es especialmente importante por
esas limitaciones. El SHA-256 de la muestra congelada es
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

Entregue solo `blind.csv` a dos revisores independientes con acceso privado
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
