# Avance

## Fases 0 y 1 — implementación, 2026-11-17
Leídos íntegramente encargo, README_PRIMERO y guía de integración. Inspeccionados
metadatos, relaciones, pendientes y tres páginas reales antes de programar.
Repositorio inicialmente sin commits. Punto de partida local y rama feature/rag-mvp.
Entorno .venv creado con Python del sistema. Implementadas auditoría SHA-256 de los
12 PDF, validación de páginas, exclusión histórica estricta y fragmentación por
párrafos/palabras conservando metadatos. Recuperador TF-IDF coseno identificado como
fallback textual offline: no se ha intentado descargar un modelo de embeddings.
No lee gold para construir índice. Índice privado en data/vector_db.

Hallazgo: 137 páginas piloto (115 OCR + 22 nativas); las 140 páginas del inventario
incluyen 3 históricas. Todos los documentos tienen vigencia no certificada.
Ausentes conocidos: RCU-0435-2017, RCU-0317-2026 y RCU-0590-2023; no se descargan
ni se inventan. La modificatoria de matrícula no reemplaza el texto base.

Comprobaciones y evidencias se añadirán tras ejecutar los comandos.

Validación fases 0–1: `.venv/bin/python -m pytest -q tests/test_integrity.py`:
**2 passed**. `python -m cs_rag_security.cli index`: **2284 fragmentos**,
12 hashes PDF coincidentes; consulta CLI top-2 ejecutada y guardada temporalmente
fuera de Git. Instalación inicial falló por DNS del sandbox; reintento autorizado
instaló pytest 8.3.5 y Streamlit 1.41.1. `requirements.lock.txt` registra dependencias
transitivas efectivamente instaladas en Python 3.14. Índice reconstruible sin red.

## Fase 2 — chatbot
Implementados Streamlit, proveedor mock extractivo visible y adaptador Ollama local
activado explícitamente por variable de modelo. Se rechazan destinos remotos y
redirecciones; no se descargan modelos. Por defecto se abstiene ante consultas de
normativa vigente: no hay fuentes certificadas. Modo documental optativo permite
extractos nativos; OCR pendiente se muestra en recuperación pero no fundamenta la
respuesta. Control de citas verifica archivo/página, no corrección semántica.
Validación: `.venv/bin/python -m pytest -q` → **6 passed**, incluyendo AppTest de
Streamlit con consulta, abstención, mock, fronteras A/B/C y proveedor remoto rechazado.
Limitación: adaptador real aún sin modelo/servidor configurado; no se ejecutó un LLM.
