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
incluye la partición, la decisión y los motivos que devolvió el detector.
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
python scripts/audit_benign_detector.py
```

Se puede guardar el informe en una ruta nueva con `--salida`.
El script registra etiquetas e IDs. Los textos permanecen en el archivo de controles.
