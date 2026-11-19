# Auditoría del corpus UNSA — Etapa 1 (T1)

> Informe automático de inventario y consistencia. No certifica vigencia normativa ni exactitud de respuestas.

## Resumen de la ejecución

| Indicador | Total |
|---|---:|
| `pdf` | 12 |
| `pdf_oficial` | 11 |
| `pdf_historico` | 1 |
| `pdf_sha256_coincidentes` | 12 |
| `entradas_baseline` | 12 |
| `documentos_metadatos` | 14 |
| `registros_extraccion` | 12 |
| `preguntas_gold` | 40 |
| `registros_validacion` | 40 |
| `incidencias_error` | 0 |
| `incidencias_advertencia` | 1 |
| `incidencias_informativas` | 2 |

## Integridad SHA-256 frente a la baseline v0.1

| PDF | Estado |
|---|---|
| `data/corpus_unsa/01B_Historicos/RCU-0252-2021.pdf` | coincide |
| `data/corpus_unsa/01_Corpus_Oficial/RCU-0009-2026.pdf` | coincide |
| `data/corpus_unsa/01_Corpus_Oficial/RCU-0127-2020.pdf` | coincide |
| `data/corpus_unsa/01_Corpus_Oficial/RCU-0161-2021.pdf` | coincide |
| `data/corpus_unsa/01_Corpus_Oficial/RCU-0273-2021.pdf` | coincide |
| `data/corpus_unsa/01_Corpus_Oficial/RCU-0284-2023.pdf` | coincide |
| `data/corpus_unsa/01_Corpus_Oficial/RCU-0320-2022.pdf` | coincide |
| `data/corpus_unsa/01_Corpus_Oficial/RCU-0450-2026.pdf` | coincide |
| `data/corpus_unsa/01_Corpus_Oficial/RCU-0470-2024.pdf` | coincide |
| `data/corpus_unsa/01_Corpus_Oficial/RCU-0501-2020.pdf` | coincide |
| `data/corpus_unsa/01_Corpus_Oficial/RCU-0504-2020.pdf` | coincide |
| `data/corpus_unsa/01_Corpus_Oficial/RCU-0584-2023.pdf` | coincide |

## Metadatos e inclusión documental

Los registros que no están en el paquete NO se consideran automáticamente archivos perdidos.

| ID | PDF identificado | Situación | Vigencia declarada |
|---|---|---|---|
| RCU-0009-2026 | rcu-0009-2026.pdf | presente | {'estado': 'verificacion_juridica_pendiente', 'advertencia': 'No usar para responder artículos completos del Reglamento de Matrícula: PDF escaneado. También deja sin efecto RCU-0033-2025, según ficha oficial.'} |
| RCU-0127-2020 | rcu-0127-2020.pdf | presente | {'estado': 'verificacion_juridica_pendiente', 'advertencia': 'NO es el reglamento de matrícula original: aprueba modificatorias a RCU-0435-2017. Buscar texto base para consultas normativas completas.'} |
| RCU-0161-2021 | rcu-0161-2021.pdf | presente | {'estado': 'verificacion_juridica_pendiente', 'advertencia': 'Contenido extraíble, pero verificar posibles reformas posteriores antes de afirmar vigencia actual.'} |
| RCU-0252-2021 | rcu-0252-2021.pdf | presente | {'estado': 'verificacion_juridica_pendiente', 'advertencia': 'La RCU-0273-2021 dejó esta resolución sin efecto. Conservar como antecedente histórico, no como regla vigente.'} |
| RCU-0273-2021 | rcu-0273-2021.pdf | presente | {'estado': 'verificacion_juridica_pendiente', 'advertencia': 'La disminución aplica al total de créditos exigidos en planes 2017; declara que el reglamento de extracurriculares queda como RCU-0504-2020.'} |
| RCU-0284-2023 | rcu-0284-2023.pdf | presente | {'estado': 'verificacion_juridica_pendiente', 'advertencia': 'Solo páginas 1-2 tienen texto extraíble; páginas 3-6 (directiva) requieren OCR o transcripción verificada.'} |
| RCU-0320-2022 | rcu-0320-2022.pdf | presente | {'estado': 'verificacion_juridica_pendiente', 'advertencia': 'Modifica el artículo 4 para indicar prácticas como actividades curriculares, eliminando la frase sobre requisitos obligatorios de graduación.'} |
| RCU-0450-2026 | rcu-0450-2026.pdf | presente | {'estado': 'verificacion_juridica_pendiente', 'advertencia': 'Documento de 73 páginas escaneadas. Es de alta prioridad para OCR. Según registro oficial, reemplaza RCU-0157-2025.'} |
| RCU-0470-2024 | rcu-0470-2024.pdf | presente | {'estado': 'verificacion_juridica_pendiente', 'advertencia': 'PDF escaneado. Verificar compatibilidad y precedencia frente al reglamento general 2026.'} |
| RCU-0501-2020 | rcu-0501-2020.pdf | presente | {'estado': 'verificacion_juridica_pendiente', 'advertencia': 'PDF escaneado. El artículo 4 debe consultarse junto con su modificación RCU-0320-2022.'} |
| RCU-0504-2020 | rcu-0504-2020.pdf | presente | {'estado': 'verificacion_juridica_pendiente', 'advertencia': 'RCU-0252-2021 fue dejada sin efecto por RCU-0273-2021; distinguir créditos extracurriculares de total de créditos del plan 2017.'} |
| RCU-0584-2023 | rcu-0584-2023.pdf | presente | {'estado': 'verificacion_juridica_pendiente', 'advertencia': 'PDF escaneado. Resolución incluida en la colección institucional de grados/títulos.'} |
| RCU-0317-2026 | rcu-0317-2026.pdf | no_encontrado_inclusion_no_confirmada | {'estado': 'modificaciones_posteriores_no_descartadas', 'advertencia': 'Ficha y PDF público verificados; no se incorporó copia local al ZIP'} |
| RCU-0590-2023 | rcu-0590-2023.pdf | no_encontrado_inclusion_no_confirmada | {'estado': 'modificaciones_posteriores_no_descartadas', 'advertencia': 'Ficha y PDF público verificados; no se incorporó copia local al ZIP'} |

## Extracción de texto y alertas OCR

Los valores proceden del resumen de extracción, no de una nueva inspección visual.

| PDF | Páginas | Errores OCR | Páginas OCR vacías | Caracteres |
|---|---:|---|---|---:|
| `rcu-0009-2026.pdf` | 4 | 0 | [] | 13106 |
| `rcu-0127-2020.pdf` | 8 | 0 | [8] | 17321 |
| `rcu-0161-2021.pdf` | 6 | 0 | [] | 15830 |
| `rcu-0252-2021.pdf` | 3 | 0 | [] | 8005 |
| `rcu-0273-2021.pdf` | 2 | 0 | [] | 7089 |
| `rcu-0284-2023.pdf` | 6 | 0 | [] | 14151 |
| `rcu-0320-2022.pdf` | 3 | 0 | [] | 10013 |
| `rcu-0450-2026.pdf` | 73 | 0 | [] | 168361 |
| `rcu-0470-2024.pdf` | 10 | 0 | [] | 29212 |
| `rcu-0501-2020.pdf` | 11 | 0 | [] | 28195 |
| `rcu-0504-2020.pdf` | 9 | 0 | [] | 24488 |
| `rcu-0584-2023.pdf` | 5 | 0 | [] | 19814 |

## Preguntas de referencia

Se encontraron **40** preguntas y **40** entradas de validación.
El informe revisa estructura, IDs y posibles referencias ausentes; **no valida** la respuesta contra el contenido del PDF.

## Incidencias automáticas

| Severidad | Categoría | Elemento | Detalle |
|---|---|---|---|
| informativa | metadatos | RCU-0317-2026 | Registro sin PDF local; comprobar si fue excluido o está pendiente, no asumir pérdida. |
| informativa | metadatos | RCU-0590-2023 | Registro sin PDF local; comprobar si fue excluido o está pendiente, no asumir pérdida. |
| advertencia | ocr | rcu-0127-2020.pdf | 1 páginas OCR vacías según el resumen. |

## Limitaciones y siguientes pasos

- Los hashes verifican identidad de bytes, no vigencia normativa.
- La calidad real del OCR no queda certificada por el resumen de extracción; requiere cotejar páginas.
- Los números de página provienen de campos explícitos de las fuentes, sin confirmar su contenido.
- No se verificó la veracidad de las respuestas de referencia contra el PDF.
- Los metadatos de vigencia son declaraciones: falta contrastarlos con fuentes oficiales vigentes.
- No se modifica el corpus, las preguntas ni la baseline.

**Revisión humana pendiente:** contrastar PDF/páginas citadas, posibles errores de OCR, relaciones normativas y una muestra de 10–15 preguntas para calibrar la rúbrica T10.
