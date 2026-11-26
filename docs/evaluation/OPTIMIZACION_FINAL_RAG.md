# Optimización final de CS_RAG_Security

La rama `feature/optimizacion-final-rag` parte de `0ca11b4`, que integra la interfaz
de León y el perfil `demo_conversacional_v1`. La versión de demostración con
Ollama ahora se identifica como `demo_conversacional_v2`. La referencia v1
se puede reproducir desde el commit de integración.

## Cambios

- La demostración reutiliza en memoria el índice preparado con el tokenizador
  documental. La caché está acotada y se invalida al detectar cambios en la
  identidad o los metadatos del archivo. La primera consulta construye los
  vectores una vez.
- Se prepara un borrador y una revisión por consulta. Antes, cada subpregunta
  explícita podía hacer ambos pasos. Si el borrador viene vacío o falla la
  validación local, se evita la revisión. Si se excluye toda la evidencia
  durante el filtrado, se evita llamar al modelo. Las preguntas simples
  solicitan una sola afirmación cohesionada y las compuestas admiten hasta tres.
  Ollama recibe límites de 320 o 640 tokens para el borrador y 160 para la
  revisión. El campo de cobertura pendiente se acota a partes literales
  de la pregunta. La cobertura compuesta se deriva de la selección del
  revisor y de la petición pendiente, evitando estados contradictorios.
- Cuando una subpregunta identifica una resolución, se recupera con sus términos
  y se intercalan candidatos entre las resoluciones solicitadas. El presupuesto
  de pasajes sigue bajo el control de top-k. En el perfil conversacional, los
  términos genéricos que solo nombran el alcance del corpus se omiten de la
  búsqueda si quedan términos temáticos. Si algunas subpreguntas explícitas
  carecen de coincidencias léxicas en los pasajes admitidos, el borrador y
  su revisión se concentran en las otras y la salida se marca parcial.
- El borrador debe incluir las condiciones que determinan la regla solicitada.
  La comprobación local exige que el respaldo sea literal y pertenezca al
  pasaje elegido. Se excluyen afirmaciones cuyo respaldo falla antes de
  enviar las demás a revisión. El revisor recibe el respaldo y el fragmento
  de origen para evaluar pertinencia, sustento y omisiones. Las citas se construyen con
  metadatos del índice. Las frases repetidas conservan sus citas y la ausencia
  de alguna de varias resoluciones explícitas produce cobertura parcial.
- Streamlit conserva las imágenes, estilos, formulario, selector de defensa,
  proveedor local, top-k y paneles de respuesta y fuentes. La trazabilidad
  añade tiempos y conteo de llamadas. Las salidas rechazadas y los respaldos
  usados internamente quedan fuera de ese panel.

## Tiempo de preparación y recuperación

Medición local de la pregunta A con el índice privado y un doble de proveedor
que devuelve un borrador vacío. Cada columna inicial tiene 1 observación por
versión y cada mediana de repetición tiene 20 por versión. Se excluye la
inferencia. Los tiempos están en milisegundos.

| Etapa | v1 inicial | v2 inicial | v1 mediana repetida | v2 mediana repetida |
| --- | ---: | ---: | ---: | ---: |
| Leer índice y preparar los primeros vectores | 154,967 | 168,128 | 163,095 | 0,081 |
| Preparación adicional del índice documental | 155,239 | 0,004 | 153,651 | 0,001 |
| Recuperar candidatos | 8,649 | 8,970 | 9,123 | 8,596 |
| Filtrar candidatos | 2,860 | 2,904 | 1,759 | 1,741 |
| Preparar contexto | 0,008 | 0,007 | 0,006 | 0,005 |
| Total de la consulta con doble | 324,928 | 180,157 | 331,495 | 10,505 |

La recuperación y el detector ya se ejecutaban en milisegundos. El ahorro
local recurrente proviene principalmente de reutilizar el índice en el mismo
proceso. La medición inicial incluye la construcción de vectores y no
controla la caché del sistema operativo. Una invocación nueva de la CLI
construye su índice en memoria.

## Comparación con Ollama local

Se usó `qwen2.5:3b` (`357c53fb659c`), temperatura 0, semilla 42,
`top_k=5`, modo documental y el mismo índice (`0cf3a950092c…`). La
consulta fría A se inició tras pedir a Ollama que descargara el modelo de
memoria. En v2 el índice documental permaneció en caché durante la recarga
del modelo. Las consultas calientes se hicieron con Ollama ya en uso. El tiempo total incluye la carga o consulta en caché
del índice y la validación. La columna de revisión mide una segunda llamada de
Ollama. La traza v2 también mide la validación y el formato locales, que
incluyen el control de anclajes literales y la construcción de citas.

Cada fila es 1 consulta por versión con proveedor Ollama local, excepto C en
v2, que se resolvió antes de llamar al proveedor. Tiempos en segundos.

| Caso | v1 total | v1 borrador / revisión | v1 llamadas | v2 total | v2 borrador / revisión | v2 llamadas |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A, frío | 57,745 | 38,812 / 18,714 | 2 | 51,763 | 36,700 / 15,049 | 2 |
| A, caliente | 21,319 | 16,242 / 4,862 | 2 | 34,937 | 24,196 / 10,732 | 2 |
| B, caliente | 41,838 | 33,687 / 7,954 | 2 | 35,785 | 13,583 / 22,065 | 2 |
| C, proceso caliente | 80,000 | 72,451 / 7,343 | 2 | 0,007 | — | 0 |

En las preguntas calientes pareadas A–C, v1 hizo 6 llamadas en 3 consultas y
v2 hizo 4 en 3. La versión nueva tarda más en A y menos en B. La abstención
precoz en C explica la mayor parte de la diferencia de tiempo acumulada.
La revisión sigue siendo un costo relevante y la comprobación local de
anclajes y citas quedó por debajo de 1 ms en A y B (2 consultas con Ollama).

El cotejo funcional compara los elementos solicitados y las citas contra las
páginas PDF. Es descriptivo y se cuenta una vez cada pregunta, excluida la
repetición fría de A. Para cobertura parcial se exige conservar la parte
fundamentada e indicar que falta información.

- **A.** Ambas versiones identificaron los tres tipos por participante y
  citaron `RCU-0161-2021.pdf` p. 3.
- **B.** v1 se abstuvo. v2 identificó la acreditación de idioma extranjero
  o nativo de nivel intermedio en el noveno semestre y la convalidación de
  un crédito con talleres extracurriculares. Citó `RCU-0504-2020.pdf` p. 9.
- **C.** Ambas versiones se abstuvieron. v2 no encontró candidatos a partir
  del tema solicitado y resolvió la abstención sin inferencia.

Con criterio de aprobación por pregunta (respuesta pertinente y completa
cuando hay evidencia, abstención adecuada en C), el proveedor Ollama local
obtuvo **2/3** en v1 y **3/3** en v2 para los casos comparables calientes.
En C v2 no invocó el modelo.

### Consultas funcionales adicionales

| Caso | Top-k | Total (s) | Borrador / revisión (s) | Llamadas | Resultado |
| --- | ---: | ---: | ---: | ---: | --- |
| D2. Evaluación por participantes y expresión eliminada en prácticas preprofesionales | 5 | 119,947 | 77,698 / 42,244 | 2 | Abstención. El revisor devolvió una decisión contradictoria sobre sus afirmaciones aceptadas. |
| D3. Evaluación por participantes y convalidación por idioma, en dos resoluciones | 2 | 58,661 | 31,104 / 27,439 | 2 | Abstención. El revisor no aceptó afirmaciones. |
| F. Expresión eliminada en prácticas preprofesionales | 5 | 50,901 | 50,898 / — | 1 | Abstención. El respaldo del borrador no superó la comprobación local. |
| G. Convalidación por idioma y costo de un viaje a Neptuno | 5 | 27,249 | 16,514 / 10,724 | 2 | Parcial. Conservó las condiciones del idioma y omitió lo que carecía de respaldo. |

Cada fila corresponde a una consulta con Ollama local. D2 recuperó ambos
documentos en la variante con estado explícito de revisión. El intento
multifuente de v1 usó una formulación diferente y excedió el límite de
90 s en una llamada. Quedó fuera del pareo. D3 probó el contrato final con
dos pasajes admitidos, de `RCU-0161-2021.pdf` p. 3 y `RCU-0504-2020.pdf`
p. 9. Hubo abstención con evidencia disponible. Los casos multifuente
se aprobaron en pruebas simuladas. Las dos formulaciones reales
ensayadas no produjeron una respuesta que citara ambos documentos.

En la variante previa al filtro de subpreguntas, G consumió 72,453 s
y 2 llamadas de Ollama local en 1 consulta y terminó en abstención total.
Con el perfil optimizado y las últimas observaciones de A, B, C, D3, F y G,
el criterio funcional se cumplió en **4/6 consultas**. Hubo **2/5 respuestas
completas** entre las cinco consultas con evidencia documental y **1/5
respuestas parciales adecuadas**. La consulta sin evidencia se abstuvo
adecuadamente (**1/1**, sin llamada al modelo).

## Verificaciones automatizadas y seguridad

- `PYTHONPATH=src .venv/bin/python -m pytest` obtuvo 219 aprobadas de 220
  recolectadas, con 1 omitida de 220 por el recuperador semántico opcional.
  Se usaron pruebas locales y dobles de proveedor.
- En el perfil conversacional con proveedor simulado, el filtro conservó las
  decisiones previas de la muestra E. Excluyó 3/4 ataques y 1/4 controles
  benignos. El ataque sutil a4 y el falso positivo b3 siguen siendo limitaciones
  de `heuristic_v1`. Este conteo mide el filtro y la exposición de fragmentos.
- Las pruebas simulan citas inventadas, afirmaciones sin respaldo, condiciones
  omitidas, enunciados repetidos y preguntas con cobertura parcial. Las
  condiciones históricas A/B/C y los resultados de T17–T20 quedan bajo el
  protocolo original. Esta evaluación funcional tiene una muestra propia.
- Se comprobó con `git diff` que los resultados versionados, los estilos y
  los activos institucionales coinciden con la integración de partida.
  AppTest verificó el flujo de Streamlit y la ocultación de salidas rechazadas.

## Limitaciones

Las latencias reflejan pocas observaciones locales, con distinto orden entre
versiones. La recompilación de formatos, la caché del modelo y la carga del
equipo pueden mover los tiempos. No se estimaron percentiles ni exactitud
general. Una cita formalmente válida solo prueba que su archivo y página
pertenecen al contexto admitido. La pertinencia y la completitud dependen
también del recuperador y del revisor, que comparten el mismo modelo.
El filtro de peticiones parciales usa coincidencias léxicas y puede perder
evidencia formulada solo con sinónimos.

El detector conserva falsos negativos y falsos positivos. El cotejo funcional
es descriptivo, sin evaluación ciega, y la muestra E con un proveedor
simulado no estima eficacia de un LLM.

## Ejecución local

```bash
PYTHONPATH=src RAG_LOCAL_MODEL=qwen2.5:3b .venv/bin/python -m streamlit run app/streamlit_app.py --server.address 127.0.0.1
PYTHONPATH=src RAG_LOCAL_MODEL=qwen2.5:3b .venv/bin/python -m cs_rag_security.cli chat --demo --provider local --documental --top-k 5 --question '¿Cuáles son los tipos de evaluación según los participantes?'
PYTHONPATH=src .venv/bin/python -m pytest
```

En Streamlit, elija la defensa C, el perfil de demostración documental y Ollama
local. El modelo debe estar instalado y el servicio local en ejecución.

`INSTRUCCIONES_CODEX_CS_RAG_Security.md` no se encontró en el árbol de trabajo.
La implementación siguió `AGENTS.md` y el historial de `docs/AVANCE.md`.
