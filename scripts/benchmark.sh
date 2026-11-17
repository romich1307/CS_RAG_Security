#!/usr/bin/env sh
set -eu
# Carpeta nueva obligatoria para evitar sobrescribir evidencia previa.
.venv/bin/python -m cs_rag_security.cli evaluate --output "${1:?Indique una carpeta nueva en results/}"
