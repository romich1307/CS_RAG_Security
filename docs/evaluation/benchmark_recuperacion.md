# Comparación de recuperación — T08

Se compararon recuperación textual y embeddings multilingües el 19 de noviembre de 2026. El experimento mide la recuperación de fuentes documentales; no genera respuestas ni mide la eficacia de una defensa frente a un LLM.

## Diseño fijado antes de medir

Se utilizaron las mismas 137 páginas oficiales del paquete depurado y los mismos 2.284 fragmentos de 180 palabras con solapamiento de 30. La resolución histórica no forma parte del índice. Los hashes del corpus coinciden con el baseline. Los PDF, OCR y gold se conservan sin modificaciones.

El [protocolo](../../experiments/retrieval_protocol.json) fija una muestra primaria de 13 preguntas con cotejo documental asistido en T10 y un análisis exploratorio de las 40 preguntas originales. La muestra primaria de la corrida excluyó GQ030 por una cita incompleta y GQ040 por una lectura que posteriormente se corrigió en T10. La p. 2 de RCU-0284-2023 sí respalda el identificador de la directiva en GQ040. La selección de 13 preguntas se conserva para interpretar la corrida original. Las 27 preguntas restantes no se presentan como revisión humana completada. Las preguntas y respuestas gold no forman parte de los fragmentos.

Se comparó el TF-IDF/coseno existente con el modelo multilingüe sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2, revisión e8f8c211226b894fcb81acc59f3b34ba3efd5f42 y archivo onnx/model_quint8_avx2.onnx. Es un encoder de 384 dimensiones con mean pooling enmascarado y normalización L2. Los vecinos se buscan por coseno exacto en una matriz local; no se requiere Docker ni una base de datos externa.

Se eligió una variante cuantizada de unos 118 MB para CPU, antes de observar sus resultados. La [ficha del modelo](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) describe la arquitectura y pooling. La ejecución utiliza [ONNX Runtime](https://onnxruntime.ai/docs/api/python/api_summary.html). Los archivos descargados se verifican por SHA-256 y el codificador no realiza descargas durante las consultas.

## Muestra primaria: 13 preguntas

| Método | Hit@1 | Hit@3 | Hit@5 | Mediana ms | p95 ms | n búsquedas |
| --- | --- | --- | --- | --- | --- | --- |
| TF-IDF/coseno | 6/13 | 9/13 | 11/13 | 5.177 | 6.268 | 65 |
| MiniLM ONNX quint8 | 6/13 | 11/13 | 11/13 | 8.475 | 12.721 | 65 |

Hit@k cuenta preguntas con al menos una fuente documento/página entre los k fragmentos. Su denominador es el número de preguntas únicas; las cinco repeticiones de latencia no multiplican ese denominador. La revisión humana de los criterios de T10 sigue pendiente antes de aceptar resultados científicos definitivos.

## Análisis exploratorio: 40 preguntas originales

| Método | Hit@1 | Hit@3 | Hit@5 | Mediana ms | p95 ms | n búsquedas |
| --- | --- | --- | --- | --- | --- | --- |
| TF-IDF/coseno | 20/40 | 28/40 | 34/40 | 5.192 | 6.345 | 200 |
| MiniLM ONNX quint8 | 15/40 | 28/40 | 30/40 | 8.269 | 11.703 | 200 |

Este análisis incluye GQ030 y GQ040 con las referencias originales del conjunto de 40 preguntas. El protocolo y el manifiesto documentan la selección aplicada el 19 de noviembre. Una corrida posterior debe generar su propio manifiesto.

## Costes y condiciones

| Medida | TF-IDF | MiniLM ONNX |
| --- | --- | --- |
| Construcción y serialización medidas, segundos | 0.091 — construcción | 38.639 — carga, embeddings y serialización |
| Artefactos de índice, bytes | 1939686 | 5468544 |
| Matriz de embeddings float32, bytes | No aplica | 3508224 |
| Pesos y archivos del encoder, bytes, separados del índice | No aplica | 127540164 |

El JSON textual conserva fragmentos y reconstruye TF-IDF al cargar. El almacén semántico conserva fragmentos y matriz NPY; al cargar solo codifica las consultas nuevas. Los tamaños corresponden a esos formatos diferentes, no a una comparación abstracta de compresión. Se comprobó la recarga del almacén con el modelo real.

Hardware: 12th Gen Intel(R) Core(TM) i5-12500H; 16782307328 bytes de RAM; CPUExecutionProvider con cuatro hilos ONNX. Python 3.12.14. Versiones de dependencias, hashes y configuración en el [manifiesto](../../results/retrieval_t08_20261119_final/manifest.json).

Latencias: tres consultas de calentamiento por método, cinco repeticiones por pregunta y orden intercalado y mezclado con semilla 42. Incluyen vectorización de la consulta y búsqueda; excluyen carga e indexación. Se informa mediana y p95 con interpolación lineal. La construcción se midió una vez por método y no es una distribución de rendimiento.

El encoder admite 128 tokens. 77/2284 fragmentos exceden ese límite y se truncan; ambos métodos reciben el mismo texto de entrada, pero el modelo ve ese prefijo. No se ajustó la fragmentación tras ver los resultados.

## Análisis de errores

- GQ038 y GQ039: MiniLM recupera RCU-0320-2022 p. 2 en top-3; TF-IDF no la incluye en top-5. El fallo textual aparece asociado a pasajes de otros reglamentos con términos compartidos.
- GQ016: la fuente RCU-0161-2021 p. 5 pasa de posición 4 con TF-IDF a posición 2 con MiniLM. Es una mejora de ranking en este caso.
- GQ006: TF-IDF recupera RCU-0161-2021 p. 4 en primera posición; MiniLM devuelve páginas de otros documentos y falla en top-5. La cercanía temática no garantiza conservar la cifra o regla pedida.
- GQ035: TF-IDF encuentra RCU-0504-2020 p. 9 en top-5. MiniLM prioriza pasajes sobre idioma de resoluciones distintas. Este caso exige separar afinidad semántica de pertinencia de la fuente.
- En las 40 preguntas, GQ005, GQ018, GQ028, GQ031 y GQ033 son otros aciertos textuales en top-5 que el encoder pierde. GQ029 es un acierto semántico adicional.

Los identificadores, páginas y posiciones están en [retrieval.csv](../../results/retrieval_t08_20261119_final/retrieval.csv) y [ranked_hits.json](../../results/retrieval_t08_20261119_final/ranked_hits.json). Las causas descritas son interpretaciones de las trazas, no pruebas de causalidad del OCR, truncación o entrenamiento.

## Decisión del recuperador

TF-IDF sigue siendo el recuperador de la CLI y del chatbot. Empató en top-5 de la muestra primaria, obtuvo más aciertos top-5 en el análisis exploratorio y requirió menos tiempo de consulta y preparación. MiniLM se ejecuta únicamente mediante el script del benchmark T08. Si se incorpora en el futuro a la CLI o al chatbot, habrá que calibrar su umbral de relevancia con un conjunto de validación antes de usarlo en el pipeline.

Un enfoque híbrido puede estudiarse con otra evaluación independiente. No se ajustó un híbrido ni se seleccionaron modelos adicionales sobre estas mismas preguntas para mejorar las cifras.

## Reproducción

Con Python 3.12 y el paquete depurado en data/corpus_unsa, desde la raíz del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,ui,semantic]"
.\.venv\Scripts\python.exe scripts/download_embedding_model.py --output data/vector_db/models/minilm-multilingual-int8
$env:PYTHONPATH = ".;src"
.\.venv\Scripts\python.exe scripts/retrieval_benchmark.py --corpus data/corpus_unsa --model-directory data/vector_db/models/minilm-multilingual-int8 --index-directory data/vector_db/t08_nueva --output results/t08_nueva
$env:RAG_EMBEDDING_MODEL = "data/vector_db/models/minilm-multilingual-int8"
.\.venv\Scripts\python.exe -m pytest -q
```

La descarga explícita pesa aproximadamente 128 MB con tokenizador y configuración. Si el modelo ya existe localmente, omitir la descarga y usar su carpeta. El modelo y los índices son privados/locales y están ignorados por Git. Los directorios de salida e índice deben ser nuevos; --reuse-index permite volver a consultar un índice compatible sin recodificar los documentos.

## Alcance y limitaciones

La comparación utiliza los mismos documentos y preguntas en ambos recuperadores, con trazas CSV/JSON, medidas de coste y análisis de errores. Sus resultados requieren revisión del equipo. Las 115 páginas OCR conservan revisión pendiente, la vigencia no está certificada y no se han evaluado respuestas de un LLM.
