#!/usr/bin/env sh
set -eu
# Ejecutar desde la raíz del repositorio.
PYTHONPATH=src .venv/bin/python -m pytest -q
.venv/bin/python -m cs_rag_security.cli audit
