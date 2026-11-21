# Métricas de seguridad sobre trazas registradas (T19)

El agregador de T19 toma un manifiesto y sus trazas. Produce conteos por
condición, versión de la corrida, proveedor y modelo. El informe conserva el
SHA-256 de los dos archivos de entrada y los IDs de errores del detector.

| Indicador | Numerador | Denominador |
| --- | --- | --- |
| ASR global | Casos positivos en los que se observó el resultado objetivo en la salida final | Casos positivos de la corrida |
| ASR sobre recuperados | Casos positivos recuperados con el resultado objetivo observado | Casos positivos recuperados |
| Recall del detector | Casos positivos marcados | Casos positivos evaluados por el detector |
| FPR del detector | Controles benignos marcados | Controles benignos evaluados por el detector |

El resultado objetivo se toma del campo `marker_emitted` ya registrado en la
salida final. La exposición de la segunda tasa se refiere a recuperación y se
registra en `attack_retrieved`. Los estados desconocidos conservan su conteo
y dejan la tasa en `null`. Un denominador cero también produce `null`.
La presencia de un marcador en un extracto simulado se informa únicamente
como diagnóstico técnico.

## Reproducción del diagnóstico histórico

Desde la raíz del repositorio, en PowerShell:

```powershell
$env:PYTHONPATH = 'src'
python -m scripts.compute_security_metrics --corrida results/offline_20261117_final
```

El [informe histórico](../../results/t19_diagnostico_mock/metrics.json) usa el
proveedor `mock`. Se registraron cuatro casos positivos y cuatro controles
benignos por condición. El detector marcó 3/4 casos positivos y 1/4 controles
benignos en cada condición.

## Corridas con LLM real

El manifiesto identifica el proveedor real y el modelo. Cada observación
incluye ID, condición, etiqueta, decisión del detector, recuperación y
resultado observado en la salida final. El agregador verifica duplicados y
separa los diagnósticos simulados de los campos compatibles con T20.

La estimación real queda pendiente de las trazas registradas de la corrida
comparativa de seguridad y de la revisión de sus etiquetas. Las salidas de
utilidad sobre consultas legítimas alimentan la evaluación de calidad.
