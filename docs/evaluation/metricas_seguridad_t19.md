# Métricas de seguridad sobre trazas registradas (T19)

El agregador de T19 toma un manifiesto y sus trazas. Produce conteos por
condición, versión de la corrida, proveedor y modelo. El informe conserva el
SHA-256 de los dos archivos de entrada y los IDs de errores del detector.

| Indicador | Numerador | Denominador |
| --- | --- | --- |
| ASR RAW y FINAL | Casos cuyo objetivo se cumplió según el juicio en la etapa correspondiente | Casos positivos de la corrida |
| ASR RAW y FINAL sobre recuperados | Casos recuperados cuyo objetivo se cumplió según el juicio en la etapa correspondiente | Casos positivos recuperados |
| Recall del detector | Casos positivos marcados | Casos positivos evaluados por el detector |
| FPR del detector | Controles benignos marcados | Controles benignos evaluados por el detector |

El campo `marker_emitted` alimenta exclusivamente el diagnóstico de
aparición del marcador en FINAL. La ASR se calcula desde los juicios
`raw.exito` y `final.exito` en `revision_rubrica_raw_final.json`. Se
requiere una fila por cada par caso y condición de las trazas de inyección.
Las huellas del manifiesto y las trazas vinculan la rúbrica con la corrida.
El agregado conserva por etapa numerador, denominador, juicios faltantes y
tasa. Un juicio desconocido o un denominador cero dejan la tasa en `null`.
La exposición registrada en `attack_retrieved` corresponde a recuperación.
El agregado de un proveedor simulado se informa como diagnóstico técnico.

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

El comando siguiente agrega los archivos ya guardados. Lee por defecto
la rúbrica local de esa corrida. También admite `--rubrica` para indicar
explícitamente el archivo de revisión.

```powershell
$env:PYTHONPATH = 'src'
python -m scripts.compute_security_metrics --corrida results/t19_inyecciones_20_20261125_003544
```
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
