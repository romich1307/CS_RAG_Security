# CS_RAG_Security

Prototipo académico de **consulta documental UNSA** que recupera información de documentos PDF y responde en español mediante **Ollama (`qwen2.5:3b`)**, con referencias al archivo y la página. Incluye las condiciones experimentales de defensa A/B/C y un perfil de demostración conversacional.

> **Aviso:** es un prototipo académico no oficial. Las respuestas no certifican la vigencia de las normas de la UNSA.

## Iniciar el chatbot (Arch Linux)

**Requisitos:** tener Ollama con `qwen2.5:3b`, el entorno `.venv` instalado y el índice local `data/vector_db/index.json` disponible.

**Terminal 1 — comprobar Ollama:**

```bash
ollama list
```

Debe aparecer `qwen2.5:3b`. Si el servidor de Ollama no está funcionando, inícialo con `ollama serve` y deja esa terminal abierta. Si ya está ejecutándose como servicio, no necesitas iniciarlo de nuevo.

**Terminal 2 — iniciar Streamlit:**

```bash
cd ~/Proyectos/CS_RAG_Security
PYTHONPATH=src RAG_LOCAL_MODEL=qwen2.5:3b \
  .venv/bin/python -m streamlit run app/streamlit_app.py \
  --server.address 127.0.0.1
```

Abre **http://localhost:8501** en tu navegador (o la dirección local que muestre Streamlit).

En la interfaz selecciona:

- **Defensa:** `C Defensa propuesta`.
- **Proveedor:** `Ollama local` (no `Mock local`).
- **Configuración → Perfil:** `Demostración documental`.
- **Consulta documental provisional:** activada.
- **Top K:** `5`.

Introduce tu pregunta y pulsa **Consultar**. Para detener Streamlit usa `Ctrl+C` en su terminal.

## Primera instalación (solo si falta el entorno)

Desde la raíz del repositorio:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip install -e .
```

El corpus documental se mantiene localmente en `data/corpus_unsa/` y **no se descarga desde Git**. Si falta el índice, y tienes el corpus necesario, puedes prepararlo con:

```bash
PYTHONPATH=src .venv/bin/python -m cs_rag_security.cli audit
PYTHONPATH=src .venv/bin/python -m cs_rag_security.cli index
```

No reconstruyas el índice para una ejecución normal si ya existe: esto podría alterar el índice operativo y no reproduce necesariamente el índice histórico de los experimentos.

## Probar desde la terminal (opcional)

```bash
cd ~/Proyectos/CS_RAG_Security
PYTHONPATH=src RAG_LOCAL_MODEL=qwen2.5:3b \
  .venv/bin/python -m cs_rag_security.cli chat \
  --demo --provider local --documental --top-k 5 \
  --question '¿Cuáles son los tipos de evaluación según los participantes?'
```

## Ejecutar las pruebas

```bash
cd ~/Proyectos/CS_RAG_Security
PYTHONPATH=src .venv/bin/python -m pytest -q
```

Una prueba del recuperador semántico opcional puede omitirse si su modelo no está instalado.

## Alcance y documentación

- `Mock local` sirve para examinar fragmentos, **no** para generar respuestas de un LLM.
- El perfil conversacional redacta respuestas a partir de fragmentos aceptados y muestra citas de PDF/página. Puede abstenerse cuando no encuentra respaldo suficiente.
- Las condiciones A/B/C del estudio se conservan separadas del perfil de demostración. La condición A es solo para evaluación controlada.
- El sistema presenta limitaciones conocidas en consultas multifuente, falsos positivos del detector y precisión general; no debe afirmarse que siempre responde correctamente.
- [Arquitectura](docs/ARQUITECTURA.md)
- [Metodología y métricas](docs/METODOLOGIA.md)
- [Informe de optimización](docs/evaluation/OPTIMIZACION_FINAL_RAG.md)
- [Informe de cierre funcional](docs/evaluation/CIERRE_FUNCIONAL_CSRAG_20261125.md)

**Privacidad:** no publicar el corpus, los índices locales, las respuestas RAW confidenciales ni los resultados privados de evaluación.
