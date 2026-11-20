# Rúbrica de evaluación de respuestas

Versión 0.2 propuesta, revisada el 19 de noviembre de 2026 a partir del cotejo documental de las 15 preguntas compartidas por Romina. La preparación inicial corresponde al 18 de noviembre. El acuerdo entre León y Romina sobre los criterios sigue pendiente. Corresponde a T10 del plan de equipo.

La unidad de anotación es la respuesta final a una consulta legítima, junto con la evidencia que el generador recibió. Cada juicio queda registrado en [la plantilla de anotación](plantilla_anotacion_qa.csv). La [metodología experimental](../METODOLOGIA.md) establece las condiciones A/B/C y las métricas automáticas existentes. Esta rúbrica añade evaluación humana de significado, abstención y citas.

## Material necesario por caso

El evaluador recibe la pregunta original, el tipo de consulta, la respuesta literal final, los fragmentos aceptados para generación con sus identificadores y una referencia a las páginas del PDF que sustentan la respuesta esperada. La referencia conserva requisitos, excepciones, cifras y ámbito de la pregunta. Las páginas procedentes de OCR requieren cotejo con el PDF.

La respuesta de referencia se consulta durante la evaluación. Su procedencia y la revisión del texto deben poder verificarse. En consultas de vigencia también se necesita constancia de revisión de las relaciones normativas pertinentes.

La primera lectura puede ocultar al evaluador el modo A/B/C bajo un identificador de caso. El responsable de la corrida conserva la correspondencia entre ese identificador y la configuración. Al cerrar la anotación, esa correspondencia permite agrupar resultados y auditar la corrida.

## Orden de revisión

1. Verificar que la pregunta, la respuesta final y las fuentes estén disponibles. Si falta material que impide decidir, registrar el caso como `no_evaluable` y describir la incidencia.
2. Establecer si la evidencia aceptada permite responder la pregunta y si el tipo de consulta exige vigencia verificada.
3. Leer la respuesta completa, identificar si responde o se abstiene y asignar la calidad de contenido.
4. Revisar por separado pertenencia y sustento de las citas, así como cualquier afirmación de vigencia.
5. Escribir una justificación con la fuente y página que permitan comprobar el juicio.

Una respuesta basada en un fragmento que fue filtrado merece revisión de soporte, incluso cuando coincide con la referencia. El evaluador debe poder distinguir la evidencia recuperada de la evidencia finalmente aceptada.

## Evidencia disponible

| Valor | Criterio |
| --- | --- |
| `suficiente` | Los fragmentos aceptados contienen la información necesaria, su contenido está verificado y satisfacen las condiciones de la consulta. |
| `insuficiente` | El material del caso permite comprobar que falta una condición necesaria para responder, como una disposición relevante, una revisión de OCR o la vigencia exigida. |
| `sin_verificar` | El evaluador carece del material necesario para decidir si la evidencia era suficiente. El juicio se registra como `no_evaluable`. |

La falta de evidencia del sistema puede justificar una abstención. La falta del expediente para el evaluador deja el juicio pendiente. Si existen pruebas suficientes de que el sistema carecía de evidencia, el caso puede evaluarse aunque su respuesta sea una abstención.

## Tipo de salida y calidad

`tipo_salida` toma el valor `respuesta` cuando se proporciona una contestación sustantiva y `abstencion` cuando el sistema comunica que carece de evidencia adecuada para contestar. Una frase de cautela seguida de una respuesta sustantiva se evalúa como `respuesta`.

| Calidad de respuesta | Criterio |
| --- | --- |
| `correcta` | Resuelve todos los puntos esenciales solicitados, preserva requisitos y excepciones relevantes, y coincide semánticamente con la fuente verificada. Las paráfrasis fieles se aceptan. |
| `parcial` | Contiene información correcta y útil, pero omite un punto necesario. La omisión permite todavía reconocer una respuesta incompleta sin inducir una interpretación equivocada del requisito central. |
| `incorrecta` | Contradice la fuente, inventa una condición, confunde el alcance o introduce una omisión que cambia el sentido de la respuesta. Una afirmación de vigencia sin respaldo también recibe esta etiqueta. |
| `no_aplica` | Se usa cuando la salida es una abstención. La adecuación de esa abstención se califica en su propio campo. |

La calidad semántica y la validez de citas se registran por separado. Una respuesta puede coincidir con los hechos y citar una página equivocada. Su etiqueta de contenido puede ser `correcta`, mientras el defecto queda registrado en los campos de citas.

## Precisiones del cotejo del 19 de noviembre

La primera aplicación documental de la rúbrica está registrada en [el cotejo T10](cotejo_t10_20261119.md) y [los ejercicios de calibración](calibracion_t10_20261119.md).

- Una condición omitida puede justificar `parcial`. Afirmar que esa condición o una excepción no existe cambia el sentido y justifica `incorrecta`.
- Una enumeración correcta puede tener respaldo `parcial` si la cita cubre solo algunos elementos. En GQ030, una enumeración correcta de todas las sanciones con cita exclusiva a la p. 8 recibe sustento `parcial`. Para respaldar la lista completa se requieren las pp. 7–8.
- En GQ040, la p. 2 de RCU-0284-2023 respalda el identificador 003-2023-UM-DSA y el título de la directiva. El anexo confirma la denominación.

## Adecuación de la abstención

`abstencion_adecuada` toma `si` cuando la evidencia era insuficiente para el tipo de consulta y el sistema explica el límite sin añadir una respuesta no sustentada. Toma `no` cuando existía evidencia suficiente para contestar y el sistema se abstuvo. En salidas sustantivas se usa `no_aplica`.

Si el sistema afirma abstenerse y luego proporciona un requisito sustantivo, se aplica la evaluación de respuesta. El contenido añadido se coteja con las fuentes.

## Citas y vigencia

| Campo | Valores y criterio |
| --- | --- |
| `cita_pertenece_contexto` | `si` si todas las citas apuntan a archivo y página presentes en los fragmentos aceptados. `no` si al menos una queda fuera. `sin_citas` si una respuesta sustantiva carece de citas. `no_aplica` si una abstención carece de citas. |
| `cita_sustenta_respuesta` | `completa` si las páginas citadas respaldan todas las afirmaciones esenciales. `parcial` si respaldan una parte. `ninguna` si las citas carecen de sustento para lo afirmado. `sin_citas` si una respuesta sustantiva carece de citas. `no_aplica` si una abstención carece de citas. |
| `error_vigencia` | `si` si la respuesta presenta como vigente una disposición sin verificación suficiente, o generaliza una modificatoria fuera de su alcance verificado. `no` si la respuesta respeta el estado documental y las comprobaciones disponibles. |

Cuando una abstención incluye una cita, se comprueba la pertenencia y si el texto respalda la explicación del límite. La mera presencia del formato `[archivo.pdf p. N]` verifica únicamente un aspecto de la referencia. La lectura de la página establece el sustento.

Una consulta documental puede preguntar qué dice un texto en una fecha determinada. Se evalúa ese contenido con su ámbito temporal. Una consulta sobre requisitos actuales requiere vigencia verificada. Las incidencias de OCR y documentos base ausentes se tratan conforme al [modelo de amenaza y límites](../AMENAZAS.md).

## Ejemplos para discutir la rúbrica

Los siguientes supuestos ilustran el criterio. La primera calibración documental con preguntas del paquete T10 está enlazada en la sección anterior. La revisión conjunta de sus etiquetas queda pendiente.

| Supuesto | Anotación |
| --- | --- |
| Se preguntan dos requisitos y la respuesta explica ambos con citas que los respaldan. | `respuesta`, `correcta`, pertenencia `si`, sustento `completa`. |
| Se preguntan dos aspectos independientes y la respuesta explica correctamente solo uno. | `respuesta`, `parcial`. La justificación identifica la omisión. |
| La respuesta cambia un plazo o elimina una excepción que altera el requisito central. | `respuesta`, `incorrecta`. |
| La respuesta afirma vigencia actual sin la revisión necesaria. | `respuesta`, `incorrecta`, `error_vigencia=si`. |
| La evidencia aceptada es insuficiente y el sistema explica por qué se abstiene. | `abstencion`, calidad `no_aplica`, adecuación `si`. |
| La evidencia es suficiente y el sistema se abstiene. | `abstencion`, calidad `no_aplica`, adecuación `no`. |
| Falta la respuesta literal o el evaluador carece de las fuentes para comprobarla. | `estado_revision=no_evaluable`, incidencia registrada y etiquetas de calidad vacías. |

## Uso de la plantilla

El CSV contiene únicamente la cabecera. Se agrega una fila por juicio de un evaluador sobre una respuesta. Dos evaluadores que revisan la misma respuesta comparten `corrida_id` y `caso_ciego_id` y reciben identificadores de evaluación distintos.

| Columna | Contenido |
| --- | --- |
| `evaluacion_id` | Identificador único de la anotación. |
| `corrida_id` | Identificador de la corrida de procedencia. |
| `caso_ciego_id` | Identificador de respuesta que permite ocultar el modo durante la primera anotación. |
| `pregunta_id` | Identificador de la pregunta legítima de referencia. |
| `evaluador_id` | Identificador de la persona que evalúa. |
| `rubrica_version` | Versión aplicada, actualmente `0.2` propuesta. |
| `referencia_caso` | Ruta o identificador que permite consultar la pregunta y su referencia verificada. |
| `referencia_salida` | Ruta o identificador del registro con la respuesta final literal. |
| `referencia_contexto` | Ruta o identificador del conjunto de fragmentos aceptados para generación. |
| `referencia_manifiesto` | Registro que identifica modelo, proveedor, corpus y parámetros de la corrida. |
| `tipo_consulta` | `documental` o `vigencia_actual`, según lo que pide la pregunta. |
| `evidencia_disponible` | `suficiente`, `insuficiente` o `sin_verificar`. |
| `estado_revision` | `pendiente`, `anotado`, `consensuado` o `no_evaluable`. |
| `tipo_salida` | `respuesta` o `abstencion`. |
| `calidad_respuesta` | `correcta`, `parcial`, `incorrecta` o `no_aplica`. |
| `abstencion_adecuada` | `si`, `no` o `no_aplica`. |
| `cita_pertenece_contexto` | `si`, `no`, `sin_citas` o `no_aplica`. |
| `cita_sustenta_respuesta` | `completa`, `parcial`, `ninguna`, `sin_citas` o `no_aplica`. |
| `error_vigencia` | `si` o `no`. |
| `justificacion` | Explicación breve de la etiqueta, con el aspecto correcto, la omisión o el error concreto. |
| `referencia_fuente` | Identificador del documento y página cotejados, o referencia a la incidencia que impidió evaluar. |
| `incidencia` | Problema de datos o ejecución que afecta al juicio, cuando lo haya. |
| `revisado_por` | Identificador de quien revisó o resolvió una discrepancia, cuando corresponda. |
| `fecha_revision` | Fecha de la anotación en formato `AAAA-MM-DD`. |

En filas `pendiente` y `no_evaluable`, las etiquetas que todavía se desconocen quedan vacías. Un campo vacío conserva el estado pendiente. `no_aplica` se reserva a las condiciones definidas por esta rúbrica.

Las referencias a archivos evitan duplicar el texto de los reglamentos y las preguntas de evaluación en el CSV. El expediente local conserva el contenido necesario para reproducir cada juicio.

## Calibración y revisión

La primera revisión utiliza entre 10 y 15 preguntas con sus fuentes cotejadas. León aplica la rúbrica y Romina revisa las ambigüedades y los criterios antes de emplearla en la comparación A/B/C. Se registra la selección de preguntas y cualquier cambio de versión. Si cambia un criterio después de etiquetar respuestas, se identifica qué anotaciones requieren revisión.

La anotación inicial se conserva al resolver un desacuerdo. Se agrega una fila de consenso con su propio `evaluacion_id`, el mismo identificador de caso y `estado_revision=consensuado`. Para el resumen se elige una única evaluación final por respuesta. Las anotaciones duplicadas de la misma respuesta sirven para revisar acuerdos y diferencias.

## Indicadores humanos propuestos

Los resúmenes se calculan sobre una sola etiqueta final por respuesta, con proveedor y modelo identificados. Se informa el número total de consultas, evaluables, pendientes y no evaluables. La exactitud textual automática ya descrita en la metodología conserva su definición.

- **Exactitud humana de contenido** = respuestas de calidad `correcta` / consultas legítimas evaluables. El denominador incluye las abstenciones.
- **Citas válidas por respuesta** = respuestas sustantivas con pertenencia `si` y sustento `completa` / respuestas sustantivas evaluables. Las respuestas sin citas están en el denominador.
- **Tasa de abstención** = abstenciones / consultas legítimas evaluables.
- **Adecuación de abstenciones** = abstenciones adecuadas / abstenciones evaluables. Se informa también cuántas abstenciones fueron inadecuadas.
- Se reportan además conteos de respuestas parciales, incorrectas y errores de vigencia. Las respuestas parciales conservan su etiqueta propia.

Todo porcentaje se acompaña de numerador y denominador. Un denominador cero se reporta como `null` o «sin estimación». Las salidas del proveedor mock permiten comprobar el procedimiento de anotación. La evaluación de calidad del LLM utiliza respuestas generadas por el proveedor real.

## Compatibilidad con la implementación actual

En la revisión local del 18 de noviembre de 2026, `pipeline.answer` devuelve `question`, `response`, `retrieved`, `accepted_ids`, `provider`, `mode` y `documental`, entre otros campos. Una captura de esa salida permite consultar la respuesta final y reconstruir los fragmentos aceptados.

El indicador `abstained` refleja decisiones del pipeline. El evaluador también lee la salida literal porque el modelo puede expresar una abstención en su texto. Las citas se cotejan con los fragmentos cuyos identificadores están en `accepted_ids`.

El comando `chat` imprime la salida del pipeline en JSON. La función `evaluation.run`, utilizada por `evaluate`, guarda actualmente IDs, diagnósticos y métricas en `traces.json` y `traces.csv`. Para completar el expediente de anotación se necesita conservar además la respuesta literal final y el contexto aceptado, con un manifiesto que identifique la corrida. Esta rúbrica describe el requisito para la siguiente ejecución.

## Estado de este entregable

- Rúbrica y plantilla preparadas el 18 de noviembre. Precisiones de la versión 0.2 propuestas el 19 de noviembre.
- Cotejo asistido de las 15 preguntas realizado con los cinco PDF recibidos. La revisión del 20 de noviembre dejó 14 referencias confirmadas, incluida GQ040. GQ030 requiere las pp. 7–8 como evidencia de respaldo completo.
- Primera aplicación documental de criterios realizada. Revisión de León y acuerdo con Romina pendientes antes de fijar las etiquetas de calibración.
- Primera evaluación humana de respuestas reales (T12) pendiente de la corrida con LLM.
