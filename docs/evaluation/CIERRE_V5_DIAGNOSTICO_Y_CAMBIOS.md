# Diagnóstico y cambios de v5

## Procedencia y lectura del Word

Se consultaron las dos descargas por nombre exacto. `xdg-user-dir DOWNLOAD`
resolvió a `~/Descargas`. El Markdown tiene SHA-256
`dfc501a33477f96549e6770f7c3dd42fdaeda8cf72ecd24123e628357486f418` y el Word
`8bd413602afbaa46e77d012cb5fc3ebf2663d52ee186c71eb5665fdd1a78e448`.
Se leyeron el plan, el cuerpo del manuscrito, las tablas y las 22 referencias
de sus seis secciones. Se consultaron `AGENTS.md` y `docs/AVANCE.md`. La guía
`INSTRUCCIONES_CODEX_CS_RAG_Security.md` no estaba disponible.

La rama v5 parte de v4 `03e0e3b`. Las referencias locales v3 `4d3b0dc` y
`main` `a96f64d` se conservaron. T08 confirma Hit@5 11/13 por recuperador,
sin LLM. T18 confirma 11/30 correctas RAW y 4/30 FINAL con Ollama
`qwen2.5:3b`. En los siete casos descartados no se reconoció cita canónica.
La mención incorrecta era el nombre de archivo con un dígito omitido. Las
30 trazas de T17 corresponden a 10 consultas compartidas, no 30 preguntas
independientes. T19 confirma ASR RAW 10/20, 0/20, 0/20 y FINAL 0/20 en cada
brazo. La frase del manuscrito que atribuye un registro de exposición a
cada ataque debe precisarse. La rúbrica registra exposición y filtrado
indeterminados para 20/20 casos por brazo. La métrica 9/9 de citas formales
de C FINAL usa solo las respuestas sustantivas. El sustento completo en
esa base fue 6/9. Los indicadores v3/v4 del manuscrito coinciden con
`/tmp/csrag-v4-holdout-run/technical.json`. [Consolidado](INFORME_FINAL_METRICAS_ARTICULO_IEEE.md) · [Matriz](MATRIZ_EVIDENCIA_IEEE.md)

## Rastreo del diagnóstico anterior

Se contrastaron `/tmp/csrag-v4-holdout-run/{traces.jsonl,blind.csv,key.csv}`
y las páginas PDF locales con la [rúbrica](rubrica_qa.md). La hoja
original carece de dictámenes completos. Los cotejos siguientes son
diagnósticos del desarrollador y no etiquetas oficiales.

| Caso | Evidencia y raíz |
| --- | --- |
| N02 v4, plazo | La primera petición y su página correcta llegaron al borrador. El art. 20, p. 5, sitúa la retroalimentación en la siguiente clase programada. El borrador la adelantó a la conclusión de la actividad. El anclaje y el revisor dejaron pasar la paráfrasis. Ambas páginas quedaron citadas en FINAL y el plazo siguió siendo incorrecto. |
| N02 v4, cobertura | La segunda cita documenta el cuarto taller. La etiqueta parcial es compatible con el error temporal, así que este caso no justifica levantarla por simple conteo de fuentes. |
| N03 v4, cobertura y órganos | La evidencia de la RCU-0504-2020, p. 5, asigna a los coordinadores apoyar supervisión. La RCU-0161-2021, p. 5, atribuye la aprobación al departamento académico. Ambas respuestas aparecen en FINAL y la lista de peticiones completas del revisor quedó vacía. El problema confirmado es el aviso de cobertura. |
| N04, presupuesto falso | La pregunta introduce una condición sin respaldo. La afirmación inventada se observó en RAW de v4 y no se publicó en FINAL. La etiqueta completa de v3 coexistió con una sola parte respondida. El art. 19 de la RCU-0161-2021 menciona documentación para acreditar causales. La fuente no autoriza inventar una condición ni declarar su ausencia en todo el corpus. |
| N03 v3, formato | El borrador de la corrida privada no se pudo leer como JSON. La abstención FINAL fue explícita. El exportador anterior podía mostrar estructuras crudas en la ficha RAW. Streamlit también mostraba telemetría saneada en un panel JSON. Son superficies diferentes. |
| N05, disponibilidad | Los dos RAW están ausentes por bloqueo previo de vigencia. Los dos FINAL contienen una abstención explícita. Una etapa ausente no se adjudica como abstención. |

## Cambios

- v5 utiliza la misma recuperación por petición de v4 y conserva umbral,
  OCR, vigencia, origen y detector. Añade admisión conservadora para
  pasajes publicables. Un extracto con sintaxis técnica, metadatos
  inválidos, patrones bloqueados o texto excesivo queda fuera antes del
  modelo y se puede completar el cupo con candidatos siguientes.
- La salida documental se compone de pasajes completos elegidos y
  revisados. El modelo devuelve identificadores, no reescribe entidades,
  cantidades, excepciones o plazos. Las citas se generan desde metadatos
  validados. Una referencia prosaica de borrador deja de ser una
  dependencia del contrato. Una cita formal no garantiza pertinencia
  del párrafo ni suficiencia entre varios fragmentos.
- El selector debe informar una lista por petición, con opción vacía.
  El revisor decide por petición y solo puede conservar candidatos
  elegidos. El código cruza la decisión con las fuentes obligatorias
  y señala las peticiones incompletas por su posición. La pregunta y
  los pasajes se mantienen en JSON de usuario separado del sistema.
- El perfil v5 publica respuesta y citas sin la traza interna.
  Streamlit oculta el panel JSON en v5 y la CLI delimita sus campos.
  El evaluador privado distingue JSON inválido de salida inexistente.
  En v5 RAW representa selección de evidencia, por lo que no es
  directamente equivalente a una paráfrasis libre en v4.
- Se mantienen dos llamadas como máximo con el mismo presupuesto.
  El temporizador distingue selección, revisión y comprobaciones.
  El detector histórico no se ajustó. Sus falsos positivos siguen
  abiertos y ningún candidato marcado se rehabilita para generar.

## Regresiones y puerta de calidad

Se ejecutaron siete pruebas iniciales antes de exponer v5. Fallaron
7/7 porque el selector de versiones rechazaba 5. La reproducción de
defectos de v4 procede además de la traza privada y de las páginas
cotejadas, sin depender de ese fallo de enrutamiento. Las pruebas
posteriores cubren el plazo literal, cantidades, actores y excepciones,
ambas resoluciones, premisa sin respaldo, referencia inexistente,
tipos y estructuras inválidas, vigencia, filtrado antes de generar,
una obligación legítima y las interfaces Streamlit y CLI.

La puerta exige suite verde, corrección del plazo y cobertura de las
dos peticiones en N02, respuesta multifuente completa en N03, parte
documental y aviso explícito en N04, control de vigencia sin llamada
en N05 y ausencia de exposición de traza interna. El piloto incluye
las cinco consultas históricas de v3/v4 solo como regresión. El
conjunto nuevo queda separado y se ejecuta únicamente si la puerta
se cumple. El objetivo de 20–30 consultas no es factible en este
ciclo local con el tiempo de ejecución observado. Una muestra
reducida solo permitiría una comparación exploratoria.

## Resultados del piloto de desarrollo

| Caso | Primera implementación v5 | Segunda implementación v5 | Resultado de la puerta |
| --- | --- | --- | --- |
| N01 | Completa, una fuente | Completa, una fuente | El pasaje conserva atributos de validez y órgano. |
| N02 | Parcial, una fuente | Parcial, una fuente | Conserva el plazo literal de la siguiente clase. Omite el cuarto taller aunque el art. 31, RCU-0504-2020 p. 8, llegó a ambos contextos. |
| N03 | Parcial, dos fuentes | Parcial, una fuente | Primero se conservaron ambos órganos sin declarar completa. Tras exigir un campo por petición, el selector dejó la segunda lista vacía pese al pasaje del departamento académico. |
| N04 | Parcial, una fuente | Parcial, una fuente | Conserva el registro y evita afirmar un requisito sin respaldo. |
| N05 | Vigencia bloqueada | Vigencia bloqueada | Cero llamadas en esta consulta por implementación. |

Proveedor Ollama local 0.40.16, `qwen2.5:3b`, digest
`357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`.
Son dos ejecuciones de desarrollo sobre las mismas cinco preguntas
usadas para el diagnóstico v4. Los casos se cuentan una vez por ejecución.
El cambio entre ambas exigió una lista por petición en selección y
eliminó la instrucción heredada del revisor que pedía otro campo.
Cumplir el tipo de salida no forzó una selección sustantiva correcta.

En el segundo piloto se recibieron 4/5 selecciones RAW y se publicaron
4/5 respuestas FINAL. Hit@1, Hit@3 y Hit@5 fueron 4/4 según página objetivo
entre pasajes admitidos. Se admitieron todas las páginas objetivo en
top-5 en 4/4, pero solo se citaron todas en 2/4. Las citas fueron
formalmente válidas en 4/4 respuestas sustantivas. La salida FINAL
registró 1/5 abstenciones y 1/5 completa automática. Exactitud y
sustento con adjudicación independiente siguen pendientes.

Latencia media 28,62 s y mediana 33,76 s sobre cinco consultas, incluida
la abstención precoz. Hubo ocho llamadas para cinco consultas. En
cuatro llamadas de cada etapa, la mediana de selección fue 24,74 s
y de revisión 9,87 s. p95 sin estimación. Los valores no establecen
ventaja pareada de latencia frente a v4.

La primera reproducción usó un ejecutor temporal y su traza privada
se conserva en `/tmp/csrag-v5-pilot-run`. La revisión instrumentada
se ejecutó mediante el siguiente comando.

```sh
RAG_LOCAL_URL=http://127.0.0.1:11435/api/chat PYTHONPATH=src .venv/bin/python \
  scripts/evaluate_conversational_v5.py --phase pilot \
  --cases /tmp/csrag-v4-holdout.json --output /tmp/csrag-v5-pilot-revision
```

La réplica requiere un nombre de salida nuevo. El manifiesto del piloto
revisado selló 39 insumos, cotejados 39/39 antes de añadir al ejecutor
el control de aprobación explícita. El código de inferencia evaluado
permanece igual. El cambio posterior exige un `qualification.json`
que apruebe el hash de un piloto reproducido con el mismo ejecutor.
SHA-256 del manifiesto
`0e9fbf5173e7918ad62df7a4f0437b50ead84f47d5ca20706b0a276c76109e6a`,
y del agregado
`93ad10bad9b76f88e880e0ab688597e15c6249b73b341bb34085071d3312a4b2`.
Los artefactos se guardan en `/tmp/csrag-v5-pilot-revision`.

El conjunto reservado tiene cinco consultas y SHA-256
`ec6d6f65f71ad2a1a9e6de95402011f8b654e64181be67bae03e2d2543f65efe`.
No se envió al modelo. La comparación y la adjudicación futuras se
prepararon en `scripts/evaluate_conversational_v5.py` y
`scripts/adjudicate_conversational_v5.py`. Las dos copias ciegas
disponibles corresponden únicamente al segundo piloto y la clave
se conserva aparte. El adjudicador compara dos hojas pareadas,
exige resolución de discrepancias y separa faltantes y errores
de formato de las abstenciones.

[Decisión de cierre](DECISION_DE_CIERRE_V5.md)
