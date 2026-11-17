# Baseline offline v0.1 — CS_RAG_Security

Fecha: 17 de noviembre de 2026
Responsable: Romina Camargo Hilachoque

## Objetivo
Establecer una versión reproducible del prototipo
documental antes de integrar un LLM generativo real.

## Componentes implementados
- Procesamiento e indexación del corpus UNSA.
- Recuperación textual local.
- Interfaz Streamlit.
- Referencias a documentos y páginas.
- Configuraciones experimentales A/B/C.
- Evaluación offline y pruebas automatizadas.

## Resultados preliminares
- Páginas indexadas: 137.
- Fragmentos indexados: 2284.
- Recuperación top-5: 34/40.
- Detección piloto: 3/4 ataques sintéticos.
- Falsos positivos: 1/4 textos benignos.
- Pruebas automatizadas: 9 aprobadas.

## Limitaciones
- El proveedor de generación es mock.
- No se ha medido ASR con un LLM real.
- La recuperación utiliza un índice textual local.
- El OCR y la vigencia normativa requieren revisión.
- Los resultados de seguridad son preliminares.

## Evidencias
- docs/evidencias/baseline_v0.1_pytest.txt
- docs/evidencias/baseline_v0.1_sha256.txt
- results/offline_20261117_final/
- docs/AVANCE.md

## Reproducibilidad
El código se identifica mediante la etiqueta Git
baseline-offline-v0.1.

El corpus original no se publica en GitHub.
Para reproducir las pruebas es necesario disponer
del mismo corpus y verificar sus hashes SHA-256.

## Próxima etapa
Integración de un LLM generativo real y evaluación
controlada de las defensas A/B/C.
