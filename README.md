# CS_RAG_Security

Prototipo académico no oficial para investigar inyección indirecta de instrucciones
en consultas documentales UNSA. Funciona localmente con recuperación TF-IDF
(fallback textual, sin embeddings) y proveedor **mock extractivo** por defecto.
No ofrece asesoría normativa ni certifica vigencia. El mock muestra extractos:
no constituye una respuesta generada por un LLM.

## Instalación Linux sin sudo

Entorno probado: Python 3.14.10. Dependencias directas fijadas en pyproject.toml;
requirements.lock.txt contiene las versiones transitivas de la instalación probada.
La instalación requiere acceso a PyPI; una vez instalada, la batería mock es offline.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip install -e .
.venv/bin/python -m cs_rag_security.cli audit
.venv/bin/python -m cs_rag_security.cli index
PYTHONPATH=src .venv/bin/python -m pytest -q
.venv/bin/python -m cs_rag_security.cli query --question '¿Qué regula la evaluación por competencias?' --top-k 5
.venv/bin/python -m cs_rag_security.cli chat --question '¿Qué regula la evaluación por competencias?' --documental
.venv/bin/python -m streamlit run app/streamlit_app.py --server.address 127.0.0.1
```

Corpus privado esperado en `data/corpus_unsa/`; no se descarga ni versiona.
Audit verifica los 12 SHA-256 PDF y las 137 páginas oficiales del JSONL piloto.
Sin corpus pueden ejecutarse los tests con fixtures; el test de integridad real se
omite. El índice privado se reconstruye en `data/vector_db/index.json`.
`PYTHONPATH=src` permite utilizar el núcleo sin instalar dependencias adicionales.

## Uso

La aplicación muestra fuente PDF, página, fragmentos, puntuación y decisiones del
detector. Seleccione consulta documental para obtener extractos de texto nativo.
Sin esa selección se requiere vigencia verificada y se abstiene con el corpus
actual. El OCR pendiente puede verse como evidencia recuperada provisional, pero
no se usa para fundamentar respuestas. No se infieren números de artículos.

Tres modos: `A_sin_defensa` (solo experimento controlado), `B_defensa_basica`
(roles y contexto no confiable) y `C_defensa_propuesta` (JSON y filtro heurístico).
El detector tiene falsos positivos y falsos negativos documentados; no garantiza
seguridad. Las tres variantes comparten controles de evidencia y citas.

## Experimentos reproducibles

```bash
.venv/bin/python -m cs_rag_security.cli evaluate --output results/mi_corrida --top-k 5
```

Utilice una carpeta nueva por corrida. Produce CSV, JSON, SVG y manifiesto con
hashes, modelos, versiones, seed, top-k, tamaños y limitaciones. Corrida ejecutada:
[results/offline_20261117_final](results/offline_20261117_final/).
40 preguntas piloto y 8 escenarios sintéticos, pareados en A/B/C. ASR y exactitud
LLM figuran como null con mock. Gold se lee exclusivamente en evaluación.

## LLM local opcional

El adaptador usa el protocolo `/api/chat` de un servidor Ollama ya instalado y un
modelo local ya disponible. No instala servidores ni descarga modelos. Active
explícitamente; no se admiten direcciones remotas ni APIs pagadas:

```bash
export RAG_LOCAL_URL=http://127.0.0.1:11434/api/chat
export RAG_LOCAL_MODEL=nombre_del_modelo_ya_instalado
.venv/bin/python -m cs_rag_security.cli chat --provider local --documental --question '¿Qué indica el texto sobre evaluación?'
.venv/bin/python -m cs_rag_security.cli evaluate --provider local --output results/corrida_local_real
```

`.env.example` documenta las variables: el programa no carga archivos .env por sí
solo. El servidor real no fue probado en esta sesión. Antes de publicar resultados
reales, registre también digest del modelo, versión del servidor y hardware.

## Documentación

- [Arquitectura](docs/ARQUITECTURA.md)
- [Metodología y métricas](docs/METODOLOGIA.md)
- [Amenazas y límites](docs/AMENAZAS.md)
- [Bitácora y pendientes](docs/AVANCE.md)
- [Evidencias ejecutadas](docs/EVIDENCIAS.md)

Los PDF, OCR, gold e índice están excluidos de Git. No se ha hecho push.
