# Validación documental piloto del conjunto gold — T1

## Objetivo

Comprobar si las respuestas de referencia de una muestra
de 15 preguntas están respaldadas por los textos y páginas
de los PDF del corpus UNSA.

## Metodología

Se seleccionaron intencionalmente 15 de las 40 preguntas
gold, cubriendo los cinco documentos representados en
el conjunto de evaluación.

Para cada pregunta se comparó:
- La pregunta original.
- La respuesta de referencia.
- El documento y la página PDF citados.
- El texto extraído de dicha página mediante pdftotext.

Los resultados se registraron en:
docs/evidencias/validacion_gold_piloto.csv

Esta revisión fue textual y preliminar. No sustituye el
cotejo visual de todas las páginas ni la verificación
jurídica de vigencia normativa.

## Resultados

| Indicador | Resultado |
|---|---:|
| Preguntas gold totales | 40 |
| Preguntas seleccionadas | 15 |
| Cobertura del conjunto gold | 37,5 % |
| Documentos representados | 5 |
| Respaldo textual completo | 14 |
| Referencias incompletas | 1 |
| IDs duplicados | 0 |

## Hallazgo GQ030

- Documento: RCU-0504-2020.
- Artículo: 28.
- Referencia gold actual: página PDF 8.
- Problema: la sanción de llamada de atención verbal,
  incluida en la respuesta, aparece en la página PDF 7.
- Las restantes sanciones aparecen en la página PDF 8.
- Recomendación: incluir las páginas PDF 7 y 8 como
  evidencia para esta respuesta.
- Estado: corrección documental propuesta, no aplicada
  al conjunto gold original.

## Limitaciones

- No se certificó la vigencia normativa actual.
- No se modificaron los PDF originales.
- No se modificaron las 40 preguntas gold originales.
- La muestra no fue aleatoria ni representa necesariamente
  la distribución temática de los 12 PDF del corpus.
- No se evaluaron respuestas generadas por un LLM.
- El cotejo visual completo continúa pendiente.

## Uso posterior

Esta muestra servirá como material de referencia para
la calibración de la rúbrica T10 preparada por León.

La evaluación humana de respuestas del chatbot deberá
realizarse posteriormente sobre salidas reales del sistema,
distinguiendo las condiciones experimentales A, B y C.
