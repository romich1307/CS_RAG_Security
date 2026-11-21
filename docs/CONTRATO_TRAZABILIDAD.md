# Contrato de Trazabilidad Experimental — CS_RAG_Security (T16)

Este documento establece el contrato formal de trazabilidad experimental para el proyecto
**CS_RAG_Security**, definiendo los esquemas de datos, procedimientos de registro, política
de confidencialidad y directrices de integración para el futuro ejecutor experimental (**T17**).

---

## 1. Propósito y Alcance

El objetivo de la trazabilidad experimental es garantizar la reproducibilidad científica,
la verificabilidad forense de cada inferencia y la comparabilidad rigurosa entre las tres
condiciones experimentales (**A**, **B** y **C**), manteniendo una separación estricta entre
la telemetría pública versionable y el contenido confidencial del corpus UNSA y dataset gold.

Este contrato es implementado en el módulo centralizado:
`src/cs_rag_security/traceability.py`

---

## 2. Auditoría del Estado Previo y Brechas Resueltas

Antes de T16, el sistema presentaba la siguiente trazabilidad parcial:

| Componente | Estado Previo | Brecha Identificada | Solución T16 |
|---|---|---|---|
| **Pipeline** (`pipeline.py`) | Retornaba `retrieved`, `accepted_ids` y `detector_log`. | No registraba orden/ranking explícito de fragmentos, ni clasificaba fragmentos descartados con sus motivos específicos. | `evaluate_retrieved_chunks` asigna `rank` (1..k), `status` y lista exhaustiva de `discard_reasons`. |
| **Generación** (`generation/__init__.py`) | Retornaba tokens y latencias cuando el proveedor los informaba. | No asociaba formalmente la versión del prompt utilizada en cada condición. | Registro canónico de `prompt_version` (A=v1, B=v1, C=v3). |
| **Evaluación** (`evaluation/__init__.py`) | Generaba trazas planas con métricas y diagnóstico de canario. | Mezclaba datos sintéticos y texto de fragmentos en `traces.json`. No auditaba hashes de scripts. | Esquema estructurado y hashes de scripts en el manifiesto. |
| **Runner T11** (`scripts/run_t11_baseline.py`) | Introdujo la separación de trazas locales y saneadas, protegiendo contra sobrescritura. | Específico al baseline A de 10 preguntas gold; manifiesto histórico no incluía `scripts_sha256`. | Funcionalidad abstraída en biblioteca reusable con soporte A/B/C y registro de `scripts_sha256`. |

---

## 3. Esquema Formal de Trazas (`TraceRecord`)

Cada registro de traza representa una ejecución de inferencia para una tupla `(run_id, case_id, mode)`.

### 3.1 Identificadores de Ejecución y Condición
- `run_id` (*str*): Identificador único de la corrida experimental (ej. `run_20261121_120000_exp`).
- `case_id` (*str*): Identificador único del caso evaluado (ej. `GQ004`, `a1_canario`, `b1_control`).
- `id` (*str*): Alias de `case_id` para compatibilidad retrospectiva con herramientas de T11 y T12.
- `case_kind` (*str*): Tipo de escenario: `'gold'`, `'synthetic_attack'`, `'synthetic_benign'`, `'academic'`.
- `condition` / `mode` (*str*): Condición experimental evaluada:
  - `A_sin_defensa`: contexto concatenado sin separación de roles ni filtrado.
  - `B_defensa_basica`: delimitación de contexto no confiable con roles de sistema y usuario.
  - `C_defensa_propuesta`: estructuración JSON, citas obligatorias `[archivo.pdf p. N]` y exclusión heurística.

### 3.2 Versiones de Prompt y Detector
- `prompt_version` (*str*): Versión exacta de las directivas del prompt:
  - `A_sin_defensa` $\rightarrow$ `'v1'` (sin directiva de formato ni defensa).
  - `B_defensa_basica` $\rightarrow$ `'v1'` (directivas de delimitación y advertencia).
  - `C_defensa_propuesta` $\rightarrow$ `'v3'` (formato genérico `[archivo.pdf p. N]` y JSON estructurado).
- `detector_version` (*str*): `'heuristic_v1'`.
- `detector_applied` (*bool*): `True` si el detector actuó como filtro excluyente (Modo C); `False` si operó únicamente como diagnóstico observacional (Modos A y B).
- `detector_suspicious_count` (*int*): Número de fragmentos recuperados marcados como sospechosos.
- `any_detector_suspicious` (*bool*): `True` si al menos un fragmento fue señalado.
- `detector_log` (*list[dict]*): Registro detallado por fragmento con `chunk_id`, `suspicious`, `score` y `reasons`.

### 3.3 Fragmentos Recuperados, Aceptados y Descartados
Cada elemento de `retrieved_chunks` y `evaluated_chunks` contiene:
- `rank` (*int*): Posición de recuperación del fragmento (1 a $k$).
- `chunk_id` (*str*): Identificador canónico del fragmento (`archivo:pagina:parrafo:overlap`).
- `documento_id` (*str*): Identificador de la resolución (ej. `RCU-0161-2021`).
- `archivo_pdf` (*str*): Nombre del archivo PDF fuente.
- `pagina_pdf` (*int*): Número de página en el PDF oficial.
- `score` (*float*): Puntuación de similitud calculada por el recuperador.
- `status` (*str*): `'accepted'` si superó todos los controles; `'discarded'` en caso contrario.
- `discard_reasons` (*list[str]*): Lista de motivos de descarte aplicables:
  - `detector_suspicious`: Excluido por reglas heurísticas del detector (sólo en Modo C).
  - `documento_historico`: Excluido por pertenecer a resolución histórica sin vigencia.
  - `score_insuficiente`: Puntuación inferior al umbral de evidencia (0.12).
  - `ocr_revision_pendiente`: Fragmento escaneado con OCR pendiente de cotejo manual.
  - `normativa_no_verificada`: Consulta sobre vigencia normativa actual sin certificación humana.

Listas derivadas:
- `accepted_ids` (*list[str]*): Identificadores de fragmentos en `accepted_chunks`.
- `discarded_ids` (*list[str]*): Identificadores de fragmentos en `discarded_chunks`.
- `retrieved_ids` (*list[str]*): Identificadores de todos los fragmentos recuperados en orden.

### 3.4 Respuestas y Tratamiento de Abstenciones
- `raw_response` (*str | null*): Salida textual cruda devuelta directamente por el generador (LLM o mock).
  > [!CAUTION]
  > `raw_response` es **estrictamente confidencial** y se conserva **únicamente en trazas privadas locales**. Nunca debe incluirse en artefactos versionados en Git.
- `response` (*str*): Salida final post-pipeline (respuesta validada con citas o mensaje oficial de abstención).
- `abstained` (*bool*): `True` si el pipeline emitió abstención formal; `False` si validó la respuesta.
- `abstention_reason` (*str*): Código canónico del motivo de abstención:
  - `evidencia_insuficiente_o_no_fiable`: Sin fragmentos admisibles tras el filtrado.
  - `citas_invalidas_o_ausentes`: La salida del LLM carece de citas formales válidas del contexto aceptado.
  - `rechazo_del_modelo`: El modelo activó rechazo explícito (`refusal` o `content_filter`).
  - `modelo_vacio`: El generador retornó contenido nulo o vacío.
  - `normativa_no_verificada`: Consulta normativa vigente sin certificación.
  - `abstencion_otra`: Otras causas.
  - `""` (cadena vacía) si no hubo abstención.

### 3.5 Validación y Saneamiento de Citas
- `citations_raw` (*list[dict]*): Citas detectadas en `raw_response` (`[{'archivo': str, 'pagina': int}]`). En las trazas privadas locales se conservan todas las citas originales completas para auditoría forense. En artefactos públicos para Git, se sanean conservando **únicamente las referencias válidas que coincidan con fuentes aceptadas** (`allowed_citations`); nunca se publican nombres de archivo, números de página ni textos de citas inválidas o sintéticas propuestas por el modelo.
- `citations_final` (*list[dict]*): Citas detectadas en `response`, filtradas bajo las mismas reglas estrictas de saneamiento.
- `citations_valid` (*bool*): `True` si y solo si la consulta no se abstuvo, existen citas y todas pertenecen estrictamente a `accepted_chunks`.
- `citations_invalid_count` / `invalid_citations_count` (*int*): Conteo cuantitativo de citas inválidas o no autorizadas propuestas por el modelo. Permite registrar cuantitativamente la tasa de alucinación o citas erróneas en Git sin exponer cadenas no autorizadas ni fragmentos confidenciales.
- `allowed_citations` (*list[dict]*): Conjunto de tuplas `(archivo_pdf, pagina_pdf)` permitidas a partir de `accepted_chunks`.

### 3.6 Parámetros, Telemetría y Tokens
- `provider` (*str*): `'mock'`, `'local'`, `'api'`.
- `model` (*str*): Nombre del modelo (ej. `'qwen2.5:3b'`, `'mock_extractivo_v1'`).
- `model_digest` (*str | null*): Digest criptográfico SHA-256 de la imagen del modelo local en Ollama (si aplica).
- `parameters` (*dict*):
  - `seed`: int (por defecto 42).
  - `temperature`: float (0 para inferencia reproducible).
  - `top_k`: int (5).
  - `documental`: bool (True en evaluación documental provisional).
  - `evidence_threshold`: float (0.12).
- `latency_generation_seconds` (*float | null*): Segundos consumidos exclusivamente por el generador LLM.
- `latency_pipeline_seconds` (*float*): Segundos consumidos por la llamada completa a `answer()`.
- `generation_performed` (*bool*): `True` si se invocó efectivamente al generador; `False` si el pipeline se abstuvo previamente por falta de evidencia o vigencia. Permite diferenciar sin ambigüedad la **ausencia de generación** de una **respuesta vacía devuelta por el modelo**.
- `tokens` (*dict | null*):
  - `prompt_tokens`: int | null.
  - `completion_tokens`: int | null.
  - `total_tokens`: int | null.
  > [!IMPORTANT]
  > Si el proveedor no informa tokens (ej. mock o ciertas llamadas locales), el valor registrado es `null`. **Está terminantemente prohibido inventar o estimar tokens ausentes**.

### 3.7 Especificación de Campos para T17: Obligatorios vs. Opcionales

Para facilitar la implementación del runner experimental en **T17** por parte de León, se formaliza la siguiente distinción:

| Campo | Tipo | Carácter en T17 | Visibilidad Git | Descripción y Regla de Ausencia |
|---|---|---|---|---|
| `run_id` | `str` | **Obligatorio** | Público | Identificador unívoco de la corrida experimental (ej. marca de tiempo UTC). |
| `case_id` | `str` | **Obligatorio** | Público | Identificador del caso evaluado (`GQ004`, `a1_canario`, etc.). |
| `case_kind` | `str` | **Obligatorio** | Público | Tipo de caso: `'gold'`, `'synthetic_attack'`, `'synthetic_benign'`. |
| `condition` / `mode` | `str` | **Obligatorio** | Público | `'A_sin_defensa'`, `'B_defensa_basica'` o `'C_defensa_propuesta'`. |
| `prompt_version` | `str` | **Obligatorio** | Público | Resuelto automáticamente por `traceability`: `'v1'` (A, B) o `'v3'` (C). |
| `provider` | `str` | **Obligatorio** | Público | `'local'`, `'mock'` o `'api'`. |
| `model` | `str` | **Obligatorio** | Público | Nombre del modelo (`qwen2.5:3b`, etc.). |
| `model_digest` | `str \| null` | **Opcional** | Público | Digest SHA-256 de imagen Ollama; `null` si no se dispone. |
| `parameters` | `dict` | **Obligatorio** | Público | Diccionario con `seed`, `temperature`, `top_k`, `documental`, `evidence_threshold`. |
| `generation_performed` | `bool` | **Obligatorio** | Público | `True` si se llamó al modelo; `False` si el pipeline se abstuvo antes. |
| `abstained` | `bool` | **Obligatorio** | Público | `True` si la salida final es abstención formal. |
| `abstention_reason` | `str` | **Obligatorio** | Público | Código canónico o `""` si no hubo abstención. |
| `question` | `str` | **Condicional** | **Sólo Privado** | Obligatorio en traza privada local; **estrictamente excluido** de Git. |
| `raw_response` | `str \| null` | **Condicional** | **Sólo Privado** | Salida cruda del LLM. `null` si no hubo generación; **estrictamente excluido** de Git. |
| `response` | `str` | **Obligatorio** | Saneado en Git | En Git: abstención estándar o redacción `[CONTENIDO_CORPUS_PRIVADO_PROTEGIDO]`. |
| `citations_raw` | `list[dict]` | **Obligatorio** | Saneado en Git | Lista de citas detectadas en texto crudo; en Git solo conserva referencias válidas a fuentes aceptadas. |
| `citations_final` | `list[dict]` | **Obligatorio** | Saneado en Git | Lista de citas en respuesta final; en Git solo conserva referencias válidas. |
| `citations_valid` | `bool` | **Obligatorio** | Público | Pertenencia estricta a fragmentos aceptados sin abstención. |
| `citations_invalid_count` | `int` | **Obligatorio** | Público | Conteo cuantitativo de citas inválidas propuestas por el modelo (sin publicar nombres/páginas). |
| `allowed_citations` | `list[dict]` | **Obligatorio** | Público | Tuplas `(archivo_pdf, pagina_pdf)` admisibles según `accepted_chunks`. |
| `retrieved_chunks` | `list[dict]` | **Obligatorio** | Saneado | Metadatos y ranking (1..$k$); campo `texto` **estrictamente excluido** de Git. |
| `accepted_chunks` | `list[dict]` | **Obligatorio** | Saneado | Fragmentos que superaron filtros; sin `texto` en Git. |
| `discarded_chunks` | `list[dict]` | **Obligatorio** | Saneado | Fragmentos no admisibles con lista `discard_reasons`; sin `texto` en Git. |
| `evaluated_chunks` | `list[dict]` | **Obligatorio** | Saneado | Vista completa evaluada; sin `texto` en Git. |
| `accepted_ids` | `list[str]` | **Obligatorio** | Público | IDs de fragmentos aceptados. |
| `discarded_ids` | `list[str]` | **Obligatorio** | Público | IDs de fragmentos descartados. |
| `retrieved_ids` | `list[str]` | **Obligatorio** | Público | IDs de fragmentos recuperados en orden. |
| `detector_version` | `str` | **Obligatorio** | Público | Versión del detector (`heuristic_v1`, actualizable en T15). |
| `detector_applied` | `bool` | **Obligatorio** | Público | `True` solo en Modo C; `False` en A y B. |
| `detector_suspicious_count` | `int` | **Obligatorio** | Público | Conteo de fragmentos señalados por el detector. |
| `any_detector_suspicious` | `bool` | **Obligatorio** | Público | Booleano si al menos un fragmento fue señalado. |
| `detector_log` | `list[dict]` | **Obligatorio** | Saneado | Diagnóstico por fragmento (`suspicious`, `score`, `reasons`). |
| `latency_generation_seconds` | `float \| null` | **Opcional** | Público | Segundos de inferencia del LLM; `null` si mock o no medido. |
| `latency_pipeline_seconds` | `float` | **Obligatorio** | Público | Segundos totales de ejecución del pipeline. |
| `tokens` | `dict \| null` | **Opcional** | Público | Conteo de tokens (`prompt_tokens`, `completion_tokens`, `total_tokens`); `null` si no informado. |
| `retriever` | `str` | **Obligatorio** | Público | Método del índice (`tfidf_cosine`). |
| `warnings` | `list[str]` | **Obligatorio** | Público | Lista de advertencias institucionales del sistema. |

---

## 4. Procedencia y Manifiesto (`RunManifest`)

El archivo `manifest.json` acompaña a cada corrida y acredita su reproducibilidad:

```json
{
  "run_id": "run_20261121_120000_exp",
  "tarea": "T17_evaluacion_experimental",
  "descripcion": "Evaluación pareada A/B/C sobre dataset gold y batería sintética",
  "condiciones_evaluadas": ["A_sin_defensa", "B_defensa_basica", "C_defensa_propuesta"],
  "versiones_prompt": {
    "A_sin_defensa": "v1",
    "B_defensa_basica": "v1",
    "C_defensa_propuesta": "v3"
  },
  "proveedor": "local",
  "modelo": "qwen2.5:3b",
  "modelo_digest": "sha256:357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b",
  "parametros": {
    "temperature": 0,
    "seed": 42,
    "top_k": 5,
    "documental": true,
    "evidence_threshold": 0.12
  },
  "entorno": {
    "commit_git": "2d7bf20...",
    "git_dirty": false,
    "python_version": "3.14.10",
    "package_version": "0.1.0",
    "dependency_versions": {
      "pytest": "8.3.5",
      "streamlit": "1.41.1"
    }
  },
  "hashes": {
    "index_sha256": "0cf3a950...",
    "gold_sha256": "622eb3d7...",
    "attacks_sha256": "5c6c06de...",
    "src_sha256": {
      "src/cs_rag_security/pipeline.py": "...",
      "src/cs_rag_security/traceability.py": "..."
    },
    "scripts_sha256": {
      "scripts/run_t11_baseline.py": "..."
    }
  },
  "started_utc": "2026-11-21T15:00:00Z",
  "finished_utc": "2026-11-21T15:15:00Z",
  "detector_version": "heuristic_v1",
  "casos_evaluados": ["GQ004", "..."],
  "total_casos": 10,
  "total_trazas_esperadas": 30
}
```

---

## 5. Política Estricta de Privacidad y Segregación de Archivos

Para cumplir con las normas del proyecto (sin volcado de texto PDF, OCR ni enunciados gold a repositorios públicos):

### 5.1 Artefactos Versionables en Git (`results/<run_id>/`)
1. `manifest.json`: Manifiesto público de procedencia y hashes.
2. `traces.json`: Trazas saneadas mediante `sanitize_trace_record()`:
   - Excluye el campo `question`.
   - Excluye el campo `raw_response`.
   - Elimina el campo `texto` de todos los fragmentos (`retrieved_chunks`, `accepted_chunks`, etc.).
   - Sanea citas: filtra `citations_raw`, `citations_final` y `response` para no publicar nombres de archivo, páginas ni textos de citas inválidas propuestas por el modelo, conservando únicamente las referencias válidas del contexto y el conteo en `citations_invalid_count`.
   - Anonimiza respuestas afirmativas de dataset gold como `[CONTENIDO_CORPUS_PRIVADO_PROTEGIDO]`.
   - Conserva toda la telemetría, identificadores, puntuaciones, listas de citas válidas y motivos de descarte.
3. `traces.csv`: Tabla plana para análisis estadístico con 29 columnas estándar (incluye `citations_invalid_count`), libre de textos de fuentes o nombres de archivos sintéticos.

### 5.2 Artefactos Privados Locales (`results/<run_id>_local/`)
Directorio excluido de Git por `.gitignore` (`/results/*_local*/`):
1. `manifest.json`: Manifiesto con indicador de copia privada.
2. `private_traces.json`: Trazas completas con `question`, `raw_response` y fragmentos con `texto` íntegro.
3. `raw_traces.json`: Respaldo retrospectivo para evaluadores humanos y preparación de material ciego (T12).
4. `private_traces.csv`: Tabla con metadatos completos.

---

## 6. Guía de Integración para León en T17

El runner experimental de **T17** debe consumir directamente este módulo evitando duplicar código.

### Flujo recomendado para T17:

```python
from pathlib import Path
from datetime import datetime, timezone
from cs_rag_security.retrieval import Index
from cs_rag_security.pipeline import answer
from cs_rag_security.traceability import (
    build_run_manifest,
    build_trace_record,
    save_experimental_run,
    PROMPT_VERSIONS,
)

# 1. Configuración de corrida
RUN_ID = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
OUTPUT_DIR = Path('results') / RUN_ID
PRIVATE_DIR = Path('results') / f"{RUN_ID}_local"

idx = Index.load('data/vector_db/index.json')
cases = [{'id': 'GQ004', 'pregunta': '¿...?'}]  # gold o sintéticos
modes = ['A_sin_defensa', 'B_defensa_basica', 'C_defensa_propuesta']

raw_traces = []
started_utc = datetime.now(timezone.utc).isoformat()

# 2. Bucle de ejecución pareada
for case in cases:
    hits = idx.search(case['pregunta'], k=5)
    for mode in modes:
        res = answer(
            index=idx,
            question=case['pregunta'],
            mode=mode,
            provider='local',
            k=5,
            documental=True,
            seed=42,
            hits=hits,  # Mismos hits pareados entre A/B/C
        )
        trace = build_trace_record(
            run_id=RUN_ID,
            case_id=case['id'],
            mode=mode,
            pipeline_result=res,
            case_kind='gold',
            question=case['pregunta'],
            provider='local',
            model='qwen2.5:3b',
            seed=42,
            top_k=5,
            documental=True,
        )
        raw_traces.append(trace)

finished_utc = datetime.now(timezone.utc).isoformat()

# 3. Manifiesto de procedencia
manifest = build_run_manifest(
    run_id=RUN_ID,
    task_name='T17_evaluacion_experimental',
    description='Evaluación pareada de defensas A/B/C con modelo local',
    evaluated_cases=[c['id'] for c in cases],
    modes=modes,
    provider='local',
    model='qwen2.5:3b',
    started_utc=started_utc,
    finished_utc=finished_utc,
)

# 4. Persistencia segregada (saneado en Git, completo en local)
save_experimental_run(
    output_dir=OUTPUT_DIR,
    manifest=manifest,
    raw_traces=raw_traces,
    private_dir=PRIVATE_DIR,
    redact_gold_response=True,
)
```

### Invariantes Obligatorios para T17:
1. **Inmutabilidad**: `OUTPUT_DIR` y `PRIVATE_DIR` deben ser rutas únicas; si existen, `ensure_unique_output_dir` lanzará `FileExistsError`.
2. **Hits pareados**: Para evaluar fielmente las defensas, se debe pasar la misma lista `hits` a las tres condiciones A, B y C por cada caso.
3. **No inventar metadatos**: Si Ollama no devuelve tokens, `tokens` permanece `None`.
4. **Privacidad**: Nunca realizar commit de archivos ubicados en `PRIVATE_DIR` ni subir `raw_response` con fragmentos textuales.
