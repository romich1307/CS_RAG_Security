# Documento de Procedencia y Reproducibilidad: Baseline T11 Ollama

Este documento detalla la procedencia técnica, los hashes criptográficos verificados, las limitaciones de identificación de versiones y las condiciones de ejecución experimental de la corrida baseline con LLM real local correspondiente a la tarea **T11**.

---

## 1. Declaración de commit base y versión del PR #8

En el archivo histórico `results/llm_baseline/manifest.json` figura el registro:
- `commit_git`: `e039e51db5672dcbb8791453846fa5eb8306623c`

### Aclaración de procedencia:
1. El commit `e039e51` (`fix(t11): mejorar citas del modo C y preservar raw_response`) corresponde al **código base de la rama** sobre el que se preparó la corrida experimental.
2. Al momento de la ejecución de `scripts/run_t11_baseline.py`, el árbol de trabajo local contenía modificaciones no confirmadas (*uncommitted working tree changes*) en el módulo `src/cs_rag_security/generation/__init__.py`.
3. Dichas modificaciones locales fueron incorporadas formalmente al repositorio en el commit original del PR #8:
   - **Commit original PR #8**: `5a9b7f59eddb5231bbd079d4a857c59c93248b16` (`feat(t11): ejecutar baseline real con Ollama y preparar evaluacion T12`).
4. Por exigencia metodológica y respeto a la auditoría histórica de resultados, los valores originales de `results/llm_baseline/manifest.json` **se conservan íntegramente sin modificar**.

---

## 2. Distinción entre cambios funcionales y de formato

Entre el commit base `e039e51` y el commit de consolidación del PR #8 (`5a9b7f5`), se identifican con precisión los siguientes cambios:

### Cambios funcionales:
- **`src/cs_rag_security/generation/__init__.py`** (líneas 54–63): Se incorporó la extracción y mapeo estructurado del consumo de tokens reportado por Ollama (`prompt_eval_count` -> `prompt_tokens`, `eval_count` -> `completion_tokens`, suma -> `total_tokens`), asignándolo tanto a `metadata['tokens']` como a `metadata['usage']`. Ningún otro módulo de `src/` sufrió alteraciones funcionales.

### Cambios de formato y configuración:
- **`.gitattributes`**: Se incorporó la directiva `results/llm_baseline/*.csv whitespace=-blank-at-eol` para normalizar el tratamiento de espacios al final de línea en celdas CSV vacías, sin impacto en la lógica algorítmica ni en las salidas del sistema.

---

## 3. Auditoría exhaustiva de hashes SHA-256

Se verificaron de manera comprobable los hashes criptográficos registrados en `manifest.json` contrastándolos contra el commit base (`e039e51`), el commit de consolidación del PR #8 (`5a9b7f5`) y los archivos locales en disco:

| Archivo | Hash SHA-256 en `manifest.json` | Hash en commit `e039e51` | Hash en commit `5a9b7f5` | Estado en disco | Coincidencia verificada |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `src/cs_rag_security/__init__.py` | `fd11f4241173faa20e362024e4d9ec24138cd54c97e96afa879688364774d28c` | `fd11f424...` | `fd11f424...` | `fd11f424...` | Coincide con ambos commits y disco |
| `src/cs_rag_security/cli.py` | `98f35351c38f84080feada0c327bbea90eddc07e2779c893a18f7f1533960c85` | `98f35351...` | `98f35351...` | `98f35351...` | Coincide con ambos commits y disco |
| `src/cs_rag_security/defenses/__init__.py` | `0842179a021ff3e14dce85882afb3e7656a357bdd01b06fd6c1b37cd9bd8fd38` | `0842179a...` | `0842179a...` | `0842179a...` | Coincide con ambos commits y disco |
| `src/cs_rag_security/evaluation/__init__.py` | `41794ce4599b38150ce7f3a42eb6fba44ea05d4e6a24a93fbc7e174c1a047618` | `41794ce4...` | `41794ce4...` | `41794ce4...` | Coincide con ambos commits y disco |
| `src/cs_rag_security/generation/__init__.py` | `77fb56bdf83bf844c086d257b9c43b9f2577f819e76a9fde42aa1d8d72643146` | `01bf44ed...` *(código previo a tokens)* | `77fb56bd...` | `77fb56bd...` | Coincide con commit `5a9b7f5` (PR #8) y disco |
| `src/cs_rag_security/ingestion/__init__.py` | `8a8cd78de172b69e4a4aff97058ac83431ae8f672fc5546ca6686dbfcf5cd50f` | `8a8cd78d...` | `8a8cd78d...` | `8a8cd78d...` | Coincide con ambos commits y disco |
| `src/cs_rag_security/pipeline.py` | `08ec7c339bda8d47ad0f9e1b5bd7d6659d9d5bd3cbb2820546a31b21b7c08b37` | `08ec7c33...` | `08ec7c33...` | `08ec7c33...` | Coincide con ambos commits y disco |
| `src/cs_rag_security/retrieval/__init__.py` | `5b1b9468462d1250b9bc2dc62805b4a516300c96b233c3903a022aa68899d185` | `5b1b9468...` | `5b1b9468...` | `5b1b9468...` | Coincide con ambos commits y disco |
| `data/vector_db/index.json` | `0cf3a950092c2c32e1c02dee23c480bc4717dc0b52a2db1aa96c6d4f09c8b2e0` | — *(no en git)* | — *(no en git)* | `0cf3a950...` | Coincide exactamente con el índice local |
| `gold_questions.json` | `622eb3d76e5d56138358d20db376d6e62f61ac378b1c0d41dbc3a543c8210da2` | — *(no en git)* | — *(no en git)* | `622eb3d7...` | Coincide exactamente con el dataset gold |

---

## 4. Política de privacidad y preservación de trazas

Conforme a las reglas del proyecto (`AGENTS.md`):
1. **Artefactos versionados en Git (`results/llm_baseline/`)**:
   - Se redactan/excluyen los textos literales de las preguntas del gold y las respuestas crudas del LLM (`raw_response`) que reproduzcan fragmentos del corpus documental privado.
   - Se conservan estrictamente todos los identificadores de consulta (`GQ004`–`GQ040`), parámetros, tokens (prompt, completion, total), latencias de generación y pipeline, veredictos de abstención, causas de abstención, citas y hashes.
2. **Respaldo local no versionado (`results/llm_baseline_local/`)**:
   - Se conserva la evidencia original completa e inalterada generada por Ollama (incluyendo preguntas literales y textos crudos generados).
   - Este directorio se encuentra estrictamente ignorado por `.gitignore`.
3. **Material para evaluación humana T12**:
   - Se genera localmente mediante el script `scripts/prepare_t12_eval.py` en `results/t12_evaluacion/` (ignorado por `.gitignore`), verificando el hash del índice antes de incorporar los fragmentos textuales exactos para los evaluadores humanos.
   - El preparador exige que el directorio de salida aún no exista. Para una sesión adicional, usa `--output-dir results/t12_evaluacion/sesion_02` y conserva el CSV anotado de la sesión anterior.

---

## 5. Limitaciones metodológicas registradas

1. **Identificación de la versión exacta del script de ejecución**:
   - El manifiesto histórico `manifest.json` calcula y registra exclusivamente los hashes de los módulos de la librería en `src/` (`src_sha256`), el índice y el dataset gold. No calculó ni registró un hash para `scripts/run_t11_baseline.py`.
   - Dado que el script se encontraba en el árbol de trabajo con modificaciones previas a su confirmación en el commit `5a9b7f5`, la versión exacta de las líneas de código del script en el instante de ejecución no está sellada criptográficamente en el manifiesto, deduciéndose de los artefactos resultantes y su consolidación en el PR #8.
2. **Delimitación del comportamiento del Modo A**:
   - En las 10 consultas evaluadas en esta corrida, al no contar con directivas de citación formal en el prompt, el modelo generó respuestas sin citas `[archivo.pdf p. N]`, lo que derivó en abstención por parte del validador estricto del pipeline.
   - Esta observación corresponde estrictamente a la evidencia empírica de estas 10 consultas; no constituye una afirmación de que el modo A produzca inevitablemente abstenciones en cualquier otra consulta o configuración de modelo.
