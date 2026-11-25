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

El agregador toma `marker_emitted` de la salida final y conserva las claves
de ASR por compatibilidad con T20. Si el indicador registra la aparición
literal del marcador, los valores se interpretan como tasa de aparición.
El cumplimiento del objetivo de cada caso se decide con la rúbrica. La
exposición se registra en `attack_retrieved`. Los estados desconocidos y los
denominadores iguales a cero producen una tasa `null`. El agregado de un
proveedor simulado se informa como diagnóstico técnico.

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

Está disponible el agregado de 20 casos de inyección en A, B y C con
Ollama local. Los 20 controles benignos se evaluaron en una corrida separada
con la misma configuración declarada. El informe compara RAW y FINAL,
distingue las apariciones del marcador de las emisiones exactas y consigna
las abstenciones. La revisión de las salidas guardadas documenta el
cumplimiento del objetivo antes y después del validador por caso y modo.
La recuperación y el marcado están registrados. La llegada al modelo y
la exclusión del fragmento de inyección quedan como datos desconocidos.
[Agregado](../../results/t19_inyecciones_20_20261125_003544/security_metrics.json) · [Revisión por caso](../../results/t19_inyecciones_20_20261125_003544/revision_rubrica_raw_final.json) · [Análisis de errores](../../results/llm_abc/error_analysis.md)

## Auditoría del corpus oficial

El control benigno ejecuta el detector sobre los fragmentos de los PDF del
piloto oficial. El script verifica el texto y los PDF contra el manifiesto
de T08 y devuelve el número de fragmentos evaluados y alertas. El resultado
se conserva en el [JSON de control](../../results/llm_abc/security_metrics_control_oficial.json),
y el [análisis de errores](../../results/llm_abc/error_analysis.md) documenta
los límites y los conteos del diagnóstico histórico.

Desde la raíz del repositorio, en PowerShell:

```powershell
$env:PYTHONPATH = 'src'
python -m scripts.audit_official_controls_t19 --corpus RUTA_CORPUS_OFICIAL
```

La salida estándar permite comparar contra el JSON archivado. Para guardar
otra ejecución se admite `--salida` con una ruta nueva.
