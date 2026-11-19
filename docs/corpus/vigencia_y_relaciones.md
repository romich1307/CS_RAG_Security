# Vigencia y relaciones normativas — T06

Este informe documenta las relaciones normativas y los controles comprobados el 19 de noviembre de 2026. Se utilizó el paquete depurado de 17 de noviembre, conservando los PDF, metadatos, OCR y gold originales. El alcance es impedir que antecedentes históricos o relaciones parciales se interpreten como vigencia certificada.

## Corpus comprobado

El ZIP recibido contiene una copia antigua de la colección y un ZIP depurado dentro de 08_Backups. Se utiliza exclusivamente el paquete depurado: 11 PDF oficiales, una resolución histórica, 137 páginas para recuperación, 115 páginas OCR pendientes de revisión y 40 preguntas de evaluación separadas del índice.

Los 12 hashes PDF y el hash del JSONL coinciden con el baseline. El inventario completo de hashes y la comprobación ejecutada están en [validation.json](../../results/normative_policy_20261119/validation.json).

## Relaciones y alcance

Las páginas son físicas del PDF. El texto extraído se contrastó con las imágenes de las páginas relevantes; no se corrigió la transcripción OCR original.

| Fuente y página | Relación | Consecuencia para el sistema |
| --- | --- | --- |
| RCU-0273-2021, p. 2, numerales 1 y 2 | Deja sin efecto RCU-0252-2021; conserva el reglamento aprobado por RCU-0504-2020 y reduce dos créditos del total exigido en planes 2017. | RCU-0252-2021 queda excluida. No interpretar la reducción como eliminación de todas las actividades extracurriculares. |
| RCU-0501-2020, p. 3, artículo 4; RCU-0320-2022, pp. 2–3 | El texto base incluye prácticas como actividades curriculares o requisitos obligatorios de graduación; la modificatoria sustituye la definición del artículo 4. | Mantener base y modificatoria relacionadas. No extender el cambio a todo el reglamento. |
| RCU-0127-2020, pp. 1 y 7; relaciones del inventario | Modificatoria del reglamento de matrícula aprobado por RCU-0435-2017. La tercera disposición final consta en p. 7. | El texto base de 2017 sigue faltando. La modificatoria no se presenta como cobertura completa de matrícula. |
| RCU-0009-2026, pp. 3–4, parte resolutiva | Deroga la tercera disposición final del capítulo VIII y deja sin efecto RCU-0033-2025; forma parte de RCU-0435-2017 y RCU-0127-2020. | El alcance es la disposición identificada. No excluir por completo RCU-0127-2020 ni afirmar que toda matrícula quedó derogada. |
| RCU-0161-2021, p. 2, numerales 1–3 | Aprueba evaluación por competencias y deroga los reglamentos de RCU-0276-2016 y RCU-0207-2019. | Registrar esos antecedentes sin incorporarlos como normativa actual. |
| RCU-0284-2023, p. 2 y anexo pp. 3–4 | Aprueba reconocimiento de créditos; hay diferencia UM-SA/UM-DSA entre resolución y anexo. | Mantener la incidencia de denominación para revisión de citas. No alterar el PDF ni el gold. |

El archivo de relaciones original se declara no exhaustivo. Los restantes documentos del inventario conservan sus advertencias y su estado sin certificación de vigencia; su presencia en la colección oficial no demuestra por sí sola aplicabilidad actual.

## Reglas implementadas

1. Solo admitir rutas directas del directorio oficial y rechazar rutas históricas, externas o con componentes de ascenso.
2. Excluir RCU-0252-2021 por identificador, incluso si unos metadatos posteriores la clasifican incorrectamente como oficial.
3. Excluir documentos marcados para no usar como norma vigente y relaciones que expresamente dejan sin efecto la resolución completa. Una derogación parcial no elimina el documento entero.
4. Conservar en los fragmentos las relaciones declaradas del documento. Los textos base y modificatorios siguen siendo documentos separados, con su procedencia.
5. Mantener normativa_actual_verificada en false. Una consulta actual sin evidencia certificada se abstiene; el modo documental permite consultar fuentes compatibles con los controles de OCR.
6. Bloquear también la resolución histórica en el pipeline si aparece en un índice antiguo. Se conserva la trazabilidad de recuperación, pero el fragmento no se acepta para generación.
7. Reconstruir los índices después de incorporar cambios normativos o reglas nuevas. La modificación de metadatos no transforma por sí sola un índice ya guardado.

Las reglas están en el módulo de normativa, su integración en ingestion y el control del pipeline. Las preguntas y respuestas gold permanecen exclusivamente en evaluación.

## Evidencia ejecutada

El script de validación audita los archivos reales, construye los fragmentos, comprueba la ausencia de históricos y verifica los controles de consulta con proveedor mock:

- 137/137 páginas admitidas pertenecen a la colección oficial; 0/137 son de RCU-0252-2021.
- 2.284 fragmentos reconstruidos.
- Consulta actual sin certificación: abstención; consulta documental de evaluación: respuesta extractiva mock.
- 6/6 controles de índice antiguo bloquean RCU-0252-2021: tres modos A/B/C, con y sin consulta documental.
- Las pruebas incluyen metadatos erróneos, derogación total frente a parcial, persistencia de relaciones y rutas no oficiales.

Estas comprobaciones prueban reglas de datos y flujo del programa. No constituyen medición de eficacia ni exactitud de un LLM.

Desde la raíz del proyecto, con el paquete depurado en data/corpus_unsa:

    python scripts/validate_normative_policy.py --corpus data/corpus_unsa --output results/nueva_validacion_t06

El directorio de salida debe ser nuevo. Para las pruebas, instalar el proyecto con sus dependencias dev y ui y ejecutar python -m pytest.

## Pendientes documentales expresamente conservados

| Documento | Estado | Tratamiento |
| --- | --- | --- |
| RCU-0435-2017 | Falta el reglamento base de matrícula. | Cobertura completa de matrícula pendiente; no inferir requisitos desde la modificatoria. |
| RCU-0317-2026 | Referencia y enlace en metadatos; sin PDF local. | No indexar ni inventar su contenido. |
| RCU-0590-2023 | Referencia y enlace en metadatos; sin PDF local. | No indexar ni inventar su contenido. |

La corrección exhaustiva de OCR y la validación del gold se registran por separado. La certificación jurídica actual y las reformas posteriores quedan fuera de esta comprobación documental. Los controles implementados y su evidencia se someten a revisión del equipo, conservando explícitos esos límites.
