# Evaluación inicial de utilidad (T12)

**21 de noviembre de 2026 · Anotación preliminar para revisión conjunta**

Se aplicó la [rúbrica v0.2](rubrica_qa.md) al paquete de la
[corrida T11](../../results/llm_baseline/manifest.json) con proveedor local Ollama,
modelo `qwen2.5:3b` y condición A. La muestra comprende 10 consultas documentales.
Cada consulta tiene dos fichas en las [anotaciones](../../results/llm_baseline/anotaciones.csv):
una para la respuesta original del modelo y otra para la salida final del pipeline.

## Cotejo

- Las 10 consultas y sus salidas finales coinciden con las trazas y el manifiesto.
  Se verificaron los IDs, el archivo, la página y la puntuación de los 24 fragmentos
  aceptados que figuran en el paquete.
- Las 10 preguntas coinciden con el gold cuyo SHA-256 consta en el manifiesto.
  Las cinco fuentes tienen los mismos hashes que el [cotejo T10](cotejo_t10_20261119.md).
- La suficiencia se juzgó sobre el texto de los fragmentos que recibió el modelo,
  cotejado con la página de referencia. La coincidencia de archivo y página se
  comprobó por separado. En GQ040 coincidía la página, pero el fragmento solo
  identificaba la resolución.
- Las dos salidas se evaluaron tal como aparecen en el paquete. El CSV versionado
  registra IDs, etiquetas, justificaciones breves y referencias. El JSON con las
  preguntas, las respuestas originales y los fragmentos se conserva en el directorio local ignorado.

## Resultados preliminares

Proveedor local Ollama, `qwen2.5:3b`. Se evaluaron 10/10 consultas por etapa.
Se encontró respaldo suficiente en 6/10 consultas y respaldo incompleto en 4/10.

| Indicador | Respuesta original | Salida final |
| --- | ---: | ---: |
| Exactitud de contenido (correctas / consultas evaluables) | 3/10 | 0/10 |
| Parciales / consultas evaluables | 2/10 | 0/10 |
| Incorrectas / consultas evaluables | 4/10 | 0/10 |
| Tasa de abstención (abstenciones / consultas evaluables) | 1/10 | 10/10 |
| Adecuación (abstenciones adecuadas / abstenciones evaluables) | 1/1 | 4/10 |
| Citas válidas y completas / respuestas sustantivas evaluables | 0/9 | Sin estimación (0 respuestas sustantivas) |

Las seis abstenciones finales inadecuadas tenían respaldo suficiente para la
consulta, pero la respuesta original carecía de citas en el formato aceptado.
Cuatro abstenciones evitaron entregar una respuesta con respaldo incompleto. El
motivo registrado por el pipeline fue `citas_invalidas_o_ausentes` en 10/10 casos.

## Ejemplos y revisión

- **GQ034.** La respuesta original resolvió la consulta con los elementos
  pertinentes de la disposición complementaria primera (RCU-0504-2020, p. 9).
  El pipeline se abstuvo por falta de una cita válida.
- **GQ012.** La generación reconoció la consecuencia general, pero confundió
  los procedimientos aplicables a dos supuestos. El contexto incluía el art. 17
  y carecía del art. 18 (RCU-0161-2021, p. 5).
- **GQ040.** El fragmento aceptado de la p. 2 carecía del numeral resolutivo
  que identifica la directiva, aunque la página completa sí lo sustenta
  (RCU-0284-2023, p. 2). La abstención fue adecuada en ambas salidas.

El paquete aporta el contenido aceptado y su correspondencia con las trazas
versionadas. La comprobación independiente del SHA-256 del índice histórico
requiere la copia exacta de ese índice. Estas cifras corresponden a una sola
corrida de 10 consultas documentales del modo A.

Para cerrar la revisión, contrastar las etiquetas preliminares con León y Romina.
Conviene revisar en particular GQ006 (si el valor basta sin la escala),
GQ012 y GQ016 (si la evidencia cubría todo lo exigido por la referencia) y
GQ023 y GQ027 (cómo afectan al juicio los detalles incorrectos añadidos).
Las discrepancias se registran conforme a la rúbrica y el resultado de consenso
se añade en una fila separada, con su propio identificador.
