# Resultados

La corrida de referencia es `offline_20261117_final/`: proveedor **mock**, seed 42,
top-k 5. Contiene manifiesto, métricas, trazas CSV/JSON y gráfico SVG del detector.
No contiene texto PDF, preguntas ni respuestas gold.

Una corrida anterior (`offline_20261117/`, solo local) fue interrumpida por reinicio
del servidor y solo dejó el manifiesto. No representa resultados completos.
`offline_20261117_completa/` y `offline_20261117_v2/` son comprobaciones intermedias
locales. Se conserva la corrida final en Git; las intermedias permanecen ignoradas.
La latencia varía entre ejecuciones. La exactitud semántica y ASR de LLM no fueron
medidas: aparecen como null. La emisión del marcador en un extracto mock es un
control de filtrado y no equivale al éxito de un ataque sobre un LLM.
