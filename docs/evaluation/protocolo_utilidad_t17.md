# Protocolo de utilidad pareada A/B/C (T17)

Este protocolo fija el brazo de consultas legítimas antes de generar las
respuestas comparables. Las tres condiciones se definen en
[la metodología](../METODOLOGIA.md). La corrida de [T11](../../results/llm_baseline/manifest.json)
sirve como evidencia piloto y punto de partida para la configuración.

## Diseño

| Elemento | Configuración del piloto |
| --- | --- |
| Unidad de comparación | Una consulta documental legítima, con la misma pregunta y evidencia inicial en A, B y C. |
| Muestra | Las 10 consultas documentales fijadas en el manifiesto de T11. Registrar los IDs y hash del gold antes de ejecutar. |
| Índice | La misma instantánea oficial para los tres modos. Registrar el hash y el método de recuperación. |
| Generación | Ollama local, `qwen2.5:3b`, temperatura 0, semilla 42. Verificar y registrar la versión y el digest del modelo efectivo. |
| Recuperación | `top_k=5`, recuperación textual y umbral de evidencia 0.12, conforme a T14. Guardar los mismos IDs ordenados antes del filtrado. |
| Variables de comparación | Condición A, B o C. Registrar versión del prompt y del detector, y la evidencia que se descartó y aceptó en cada condición. |

Las ejecuciones nuevas se agrupan bajo un único identificador de corrida.
Se planifican 30 salidas finales, con tres por pregunta. Las respuestas
originales se conservan en las trazas privadas para un cotejo separado.
La observación de T11 se informa aparte porque corresponde a una corrida
histórica de la condición A.

## Evidencia y evaluación

1. Verificar que corpus, índice, modelo y parámetros coinciden entre los modos
   y que las tres filas de cada pregunta comparten el mismo ranking previo al filtro.
2. Registrar por salida el estado de generación, los fragmentos aceptados y
   descartados, las citas, el motivo de abstención, la latencia y el estado de
   la llamada. Un error de ejecución se consigna como incidencia.
3. Aplicar la [rúbrica v0.2](rubrica_qa.md), registrando calidad, citas y
   adecuación de la abstención. Guardar la correspondencia del identificador
   ciego con la corrida, la pregunta, la condición y el tipo de salida.
4. Comparar las mismas consultas evaluables en cada par de condiciones.
   Informar separados los pares excluidos y sus motivos.

## Resultados que se reportarán

| Indicador | Denominador |
| --- | --- |
| Exactitud de contenido | Consultas legítimas evaluables, incluidas las abstenciones |
| Citas válidas con sustento completo | Respuestas sustantivas evaluables |
| Tasa de abstención | Consultas legítimas evaluables |
| Adecuación de abstención | Abstenciones evaluables |
| Latencia mediana y p95 | Número de mediciones válidas por condición, separando duración de generación y del pipeline |

La corrida se considera completa cuando se puede comprobar la configuración
común y cada consulta tiene sus tres salidas o incidencias documentadas.
La corrida local `t17_ollama_20261121_r1` conservó 30 salidas de Ollama con
`qwen2.5:3b`. Se hizo antes de integrar el contrato T16. Su manifiesto,
trazas y planilla ciega se conservan en el directorio original. Las corridas
canónicas se guardan con IDs nuevos. La revisión con la rúbrica sigue pendiente.

## Ejecutar el piloto

Desde la raíz del repositorio, en PowerShell:

```powershell
$env:PYTHONPATH = 'src'
python -m scripts.run_t17_utility --indice RUTA_INDICE --gold RUTA_GOLD --run-id t17_prueba
```

Se comprueba el SHA-256 de los insumos. Se admite el índice textual oficial
conservado de T08 o la instantánea histórica de T11. Para Ollama, configurar
`RAG_LOCAL_MODEL=qwen2.5:3b` y añadir `--proveedor local`. El ejecutor verifica
la versión del servidor y el digest del modelo instalado antes de generar.

El [contrato T16](../CONTRATO_TRAZABILIDAD.md) genera el manifiesto y las
trazas saneadas en JSON y CSV para T18/T20. El resultado se guarda por corrida
en `results/llm_abc_local/`, ignorado por Git. Las preguntas, las respuestas
originales y el contexto íntegro quedan en `privado/` para el cotejo.

El manifiesto registra por condición la media, mediana, p95 y número de
mediciones válidas, separando la llamada al generador y el tiempo del
pipeline sin la recuperación compartida. Una corrida con errores registra
las incidencias en el manifiesto y termina con código distinto de cero.
El proveedor predeterminado `mock` comprueba el flujo.
