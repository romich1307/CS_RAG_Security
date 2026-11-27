# Decisión de cierre v5

**Puerta de calidad no superada.** El perfil experimental se conserva
para reproducir los hallazgos. La selección predeterminada sigue en v2.
v4 conserva su condición de referencia experimental. Falta evidencia
de exactitud o seguridad comparativa para promover v4 o v5.

| Dimensión | Resultado y decisión |
| --- | --- |
| Regresión automatizada | 249/250 aprobadas, 0/250 fallidas y 1/250 omitida por encoder MiniLM opcional. Se verificaron CLI, Streamlit, contrato de citas, vigencia y filtrado antes de la generación con pruebas locales. |
| Plazo y premisa falsa | El piloto con Ollama local preservó el plazo literal en N02 y no publicó la premisa falsa de N04. Son resultados de regresión. |
| Cobertura | El segundo piloto con Ollama local omitió una fuente obligatoria en 2/2 casos multifuente de regresión. En ambos casos la página estaba admitida. No se aprobó la puerta. |
| Citas | Válidas formalmente en 4/4 respuestas sustantivas del segundo piloto con Ollama local. Cobertura total de páginas objetivo en 2/4 consultas con referencia. Sustento independiente pendiente. |
| Latencia | Mediana 33,76 s y media 28,62 s en el segundo piloto con Ollama local, n=5. Se hicieron 8 llamadas. La muestra y el estado de caché no permiten declarar una mejora pareada. |
| Seguridad | Se conservaron reglas y exclusiones. Las regresiones estáticas del detector compartido observan recall 3/4 y FPR 5/20, sin LLM. No se estimó ASR de v5. El cambio de presentación y selección merece verificación independiente antes de aprobar seguridad. |
| Independencia | Se reservó la muestra nueva y se verificó el bloqueo de su ejecución por falta de dictamen de aprobación. Las 10 filas ciegas disponibles corresponden al piloto. Exactitud humana y comparación independiente quedan pendientes. |

Para cerrar el artículo se puede utilizar la evidencia histórica T08,
T17–T18, T19 y T20 con sus denominadores y limitaciones indicados en
el [consolidado IEEE](INFORME_FINAL_METRICAS_ARTICULO_IEEE.md). v3,
v4 y el piloto v5 pueden aparecer como exploración, conservando cada
protocolo y haciendo explícita la falta de validación de calidad.
El contraste de ASR RAW histórico respalda un efecto en la batería
ensayada. El coste de utilidad de la validación final está documentado.
El corpus piloto y el producto carecen de certificación de vigencia.
La evaluación carece de base para una recomendación de producción.
