# Auditoría de falsos positivos del detector (T15)

Se evaluó `heuristic_v1` sobre los [20 controles benignos de T13](modelo_amenaza.md).
La unidad de análisis es un fragmento. Cada alerta corresponde a un falso
positivo porque la etiqueta esperada de todos los controles es benigna.

| Partición | Marcados / evaluados | Tasa |
| --- | ---: | ---: |
| Desarrollo | 3/10 | 30 % |
| Verificación | 2/10 | 20 % |
| Total | 5/20 | 25 % |

El diagnóstico se ejecuta localmente, sin proveedor LLM. El
[registro por caso](../../results/detector_benign_v2/metrics.json)
incluye la partición, la decisión, el puntaje y los motivos de cada caso.
El puntaje cuenta reglas activadas. El SHA-256 identifica los bytes
auditados. El archivo de controles se conserva con saltos de línea LF.
Las cinco alertas se concentran en trámites y terminología técnica.

| Motivo | Falsos positivos | Lectura documental |
| --- | ---: | --- |
| Salida impuesta | 3/20 | Obligaciones administrativas dirigidas a estudiantes, solicitantes u oficinas. |
| Suplantación de rol | 2/20 | Encabezados y avisos citados en documentación técnica. |

Estos resultados sirven para revisar el costo de las reglas sobre textos
legítimos. Igualmente se necesita medir la sensibilidad antes de ajustar
los criterios de exclusión. Para comparar alternativas se conserva la
versión de referencia y se fija una revisión adicional con casos que
no se usaron para elegir el ajuste.

## Reproducción

Desde la raíz del repositorio, en PowerShell:

```powershell
$env:PYTHONPATH = 'src'
New-Item -ItemType Directory -Force 'results/detector_benign_local' | Out-Null
python scripts/audit_benign_detector.py --salida 'results/detector_benign_local/metrics.json'
```

Para repetir la auditoría, elige una ruta nueva en `--salida`. Si omites
ese argumento, el informe se imprime en la terminal. Los textos de los
fragmentos permanecen en el archivo de controles.
