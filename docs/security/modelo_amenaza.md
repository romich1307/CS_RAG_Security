# Modelo de amenaza y controles benignos (T13)

La aplicación consulta reglamentos de la UNSA con un sistema RAG. Se busca
preservar el sentido de la pregunta, la respuesta respaldada y las citas cuando
la recuperación entrega contenido de procedencia distinta. El [modelo general](../AMENAZAS.md)
documenta también los límites de vigencia, OCR y cobertura del corpus.

## Frontera de confianza

| Elemento | Alcance |
| --- | --- |
| Consulta | La formula el usuario. Su texto, tipo documental y parámetros de recuperación se fijan para cada par experimental. |
| Fuentes oficiales | Su origen y ubicación se registran por documento y página. Las disposiciones recuperadas son evidencia para responder. |
| Material secundario | Se considera contenido no confiable. El adversario del estudio solo tiene capacidad para aportar contenido a esta colección experimental. |
| Aplicación | El código, los mensajes de sistema, el proveedor y la política de citas quedan bajo control del equipo. La identidad de los archivos oficiales se conserva. |
| Salida | El pipeline valida la pertenencia de las citas a los fragmentos aceptados. El sustento semántico se revisa con la rúbrica. |

El efecto que se quiere detectar es una alteración de la respuesta esperada
atribuible al contenido secundario. El estudio se acota a respuestas textuales
en un entorno controlado. La aplicación del estudio carece de herramientas de
ejecución o de escritura accesibles al modelo.

## Controles benignos

[El conjunto de controles](../../experiments/benign_v2.jsonl) contiene 20 casos
ficticios de estilo administrativo y normativo. Cada fila identifica el caso, la
etiqueta, la categoría, la partición, la procedencia, el objetivo, la pregunta,
el fragmento y el resultado esperado.

| Categoría | Desarrollo | Verificación | Aspecto que se revisa |
| --- | ---: | ---: | --- |
| Requisitos | 2 | 2 | Umbrales, plazos y excepciones |
| Trámite | 2 | 2 | Deberes que un reglamento asigna a personas u oficinas |
| Referencias | 2 | 2 | Citas y referencias internas |
| Formato documental | 2 | 2 | Listas, tablas y saltos de línea |
| Terminología técnica | 2 | 2 | Encabezados y vocabulario de sistemas |

El detector debe conservar todos estos fragmentos. Se registra un falso positivo
cuando marca un fragmento benigno como sospechoso. La tasa se calcula como
**controles benignos marcados / controles benignos evaluados** y se informa por
partición junto con la versión del detector. El campo de contenido esperado
permite revisar posteriormente si una respuesta diluye el requisito o la
excepción que sustenta el fragmento.

La partición de desarrollo orienta el diagnóstico. La de verificación queda
fijada antes de modificar reglas. Los resultados describen esta selección
sintética y dependen de los tipos de texto representados.

## Revisión del entregable

Este material cubre el modelo de amenaza y el brazo benigno de T13. Para
cerrar el conjunto experimental aún falta el brazo positivo revisado por el
equipo. Los casos se mantienen en una colección separada del corpus y del
gold de la UNSA.
