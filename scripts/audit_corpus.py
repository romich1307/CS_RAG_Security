#!/usr/bin/env python3
"""Auditoría estática, reproducible y de solo lectura del corpus UNSA.

Uso desde la raíz del repositorio:
    python scripts/audit_corpus.py

Escribe ÚNICAMENTE el JSON de resultados y un informe Markdown fuera de data/.
No interpreta la vigencia jurídica ni certifica la exactitud semántica de OCR/citas.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/corpus_unsa"
BASELINE = ROOT / "docs/evidencias/baseline_v0.1_sha256.txt"
OUT_JSON = ROOT / "results/corpus_audit/summary.json"
OUT_MD = ROOT / "docs/AUDITORIA_CORPUS.md"

PDF_RE = re.compile(r"RCU-\d{4}-\d{4}(?:\.pdf)?", re.IGNORECASE)
HEX_RE = re.compile(r"^[a-fA-F0-9]{64}$")


def issue(items: list, severity: str, category: str, subject: str, detail: str) -> None:
    items.append({"severidad": severity, "categoria": category, "elemento": str(subject), "detalle": detail})


def load(path: Path, default, issues: list):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        issue(issues, "error", "datos", str(path.relative_to(ROOT)), str(exc))
        return default


def as_records(data, key: str | None, name: str, issues: list) -> list[dict]:
    if key:
        if not isinstance(data, dict) or not isinstance(data.get(key), list):
            issue(issues, "error", "estructura", name, f"Se esperaba una lista en '{key}'.")
            return []
        data = data[key]
    if not isinstance(data, list):
        issue(issues, "error", "estructura", name, "Se esperaba una lista.")
        return []
    if not all(isinstance(entry, dict) for entry in data):
        issue(issues, "error", "estructura", name, "Hay elementos que no son objetos JSON.")
    return [entry for entry in data if isinstance(entry, dict)]


def basename(value) -> str:
    if not isinstance(value, str):
        return ""
    return value.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1].strip()


def pdf_identifier(value) -> str:
    """Devuelve un nombre PDF identificable, si se reconoce; no lo inventa."""
    if not isinstance(value, str):
        return ""
    candidate = basename(value)
    if candidate.lower().endswith(".pdf"):
        return candidate.lower()
    found = PDF_RE.search(value)
    return ((found.group(0)[:-4] if found.group(0).lower().endswith(".pdf") else found.group(0)) + ".pdf").lower() if found else ""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_baseline(issues: list) -> dict[str, str]:
    expected = {}
    try:
        lines = BASELINE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        issue(issues, "error", "integridad", "baseline", "No existe el manifiesto SHA-256.")
        return expected
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        match = re.match(r"^([a-fA-F0-9]{64})\s+\*?(.+)$", line)
        if not match:
            issue(issues, "error", "integridad", f"línea {number}", "Formato SHA-256 no reconocido.")
            continue
        digest, filename = match.groups()
        normalized = Path(filename.strip().replace("\\", "/")).as_posix()
        if normalized in expected:
            issue(issues, "error", "integridad", normalized, "Entrada duplicada en la baseline.")
        expected[normalized] = digest.lower()
    return expected


def count_or_none(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, list):
        return len(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def truthy(value) -> bool:
    return value is True or (isinstance(value, str) and value.strip().casefold() in {"si", "sí", "true", "1", "yes"}) or value == 1


def declared_in_package(value) -> bool:
    """Reconoce tanto una marca afirmativa como una ruta PDF declarada."""
    if truthy(value):
        return True
    if not isinstance(value, str):
        return False
    return basename(value).lower().endswith(".pdf")


def metadata_status(document: dict, pdf_by_name: dict) -> tuple[str, bool, str]:
    """Clasifica una entrada sin consultar el sistema de archivos (testeable)."""
    name = next((x for x in (
        pdf_identifier(document.get("archivo_pdf")),
        pdf_identifier(document.get("archivo_local")),
        pdf_identifier(document.get("archivo_en_paquete")),
        pdf_identifier(document.get("id")),
    ) if x), "")
    present = bool(name and name in pdf_by_name)
    declared = declared_in_package(document.get("archivo_en_paquete"))
    situation = (
        "presente" if present else
        "no_encontrado_declarado_incluido" if declared else
        "no_encontrado_inclusion_no_confirmada"
    )
    return name, present, situation


def record_ids(records: list[dict], name: str, issues: list) -> dict:
    id_counts = Counter(str(r.get("id", "")).strip() for r in records)
    for identifier, total in id_counts.items():
        if not identifier:
            issue(issues, "advertencia", name, "sin ID", f"{total} registros sin id.")
        elif total > 1:
            issue(issues, "error", name, identifier, f"ID repetido {total} veces.")
    return {str(r["id"]).strip(): r for r in records if str(r.get("id", "")).strip()}


def referenced_pdf_names(value) -> set[str]:
    """Identifica nombres de PDF/RCU en las fuentes; no certifica su contenido."""
    names = set()
    if isinstance(value, dict):
        for item in value.values():
            names.update(referenced_pdf_names(item))
    elif isinstance(value, list):
        for item in value:
            names.update(referenced_pdf_names(item))
    elif isinstance(value, str):
        for found in PDF_RE.findall(value):
            names.add(pdf_identifier(found))
        # Nombres PDF no necesariamente RCU en rutas de fuentes.
        for found in re.findall(r"[A-Za-z0-9_.-]+\.pdf", value, re.IGNORECASE):
            names.add(pdf_identifier(found))
    return {n for n in names if n}


def page_numbers(value) -> list[int]:
    """Extrae solo campos explícitos de página. No infiere números del texto."""
    output = []
    if isinstance(value, list):
        for item in value:
            output.extend(page_numbers(item))
    elif isinstance(value, dict):
        for key, item in value.items():
            key_normalized = str(key).casefold().replace("á", "a").replace("_", "")
            if key_normalized.startswith(("pagina", "page")):
                if isinstance(item, int) and not isinstance(item, bool):
                    output.append(item)
                elif isinstance(item, str) and item.strip().isdigit():
                    output.append(int(item.strip()))
                elif isinstance(item, list):
                    for number in item:
                        if isinstance(number, int) and not isinstance(number, bool):
                            output.append(number)
                        elif isinstance(number, str) and number.strip().isdigit():
                            output.append(int(number.strip()))
            else:
                output.extend(page_numbers(item))
    return output


def run_audit() -> dict:
    issues = []
    pdf_files = sorted((CORPUS / "01_Corpus_Oficial").glob("*.pdf")) + sorted((CORPUS / "01B_Historicos").glob("*.pdf"))
    pdf_paths = {str(p.relative_to(ROOT)): p for p in pdf_files}
    pdf_by_name = {p.name.lower(): p for p in pdf_files}
    if len(pdf_by_name) != len(pdf_files):
        issue(issues, "error", "inventario", "archivos", "Hay PDF distintos con el mismo nombre base.")
    for path in pdf_files:
        if path.stat().st_size == 0:
            issue(issues, "error", "inventario", path.name, "PDF de 0 bytes.")

    baseline = read_baseline(issues)
    integrity = []
    for rel, path in sorted(pdf_paths.items()):
        found = sha256(path)
        original = baseline.get(rel)
        status = "coincide" if original == found else ("sin_baseline" if original is None else "no_coincide")
        integrity.append({"archivo": rel, "estado": status, "sha256": found})
        if status != "coincide":
            issue(issues, "error", "integridad", rel, status)
    for rel in sorted(set(baseline) - set(pdf_paths)):
        issue(issues, "error", "integridad", rel, "Registrado en baseline pero ausente del corpus actual.")

    documents = as_records(load(CORPUS / "04_Metadatos/documents.json", {}, issues), "documentos", "documents.json", issues)
    gold = as_records(load(CORPUS / "03_Preguntas_Respuestas/gold_questions.json", {}, issues), "preguntas", "gold_questions.json", issues)
    validations = as_records(load(CORPUS / "03_Preguntas_Respuestas/validacion_referencias.json", [], issues), None, "validacion_referencias.json", issues)
    extraction = as_records(load(CORPUS / "05_Texto_Procesado/resumen_extraccion.json", [], issues), None, "resumen_extraccion.json", issues)
    doc_meta = []
    mapped_meta = Counter()
    for document in documents:
        name, present, situation = metadata_status(document, pdf_by_name)
        if present:
            mapped_meta[name] += 1
        doc_meta.append({
            "id": document.get("id"), "pdf": name or None, "situacion": situation,
            "archivo_en_paquete_declarado": document.get("archivo_en_paquete"),
            "estado_inclusion_rag": document.get("estado_inclusion_rag"),
            "vigencia_declarada": document.get("vigencia"),
            "no_certificado_vigente": document.get("no_certificado_vigente_al_2026_11_17"),
            "apto_para_rag_con_restricciones": document.get("apto_para_rag_con_restricciones"),
        })
        if situation == "no_encontrado_declarado_incluido":
            issue(issues, "error", "metadatos", str(document.get("id")), "Declarado incluido en paquete, pero el PDF no está presente.")
        elif situation == "no_encontrado_inclusion_no_confirmada":
            issue(issues, "informativa", "metadatos", str(document.get("id")), "Registro sin PDF local; comprobar si fue excluido o está pendiente, no asumir pérdida.")
        if present and truthy(document.get("usar_como_norma_vigente")) and truthy(document.get("no_certificado_vigente_al_2026_11_17")):
            issue(issues, "advertencia", "vigencia", str(document.get("id")), "Marcado para uso vigente pero también como no certificado vigente; requiere revisión humana.")
    for pdfname in sorted(pdf_by_name):
        count = mapped_meta[pdfname]
        if count == 0:
            issue(issues, "advertencia", "metadatos", pdfname, "No se identificó un registro de metadatos para este PDF.")
        elif count > 1:
            issue(issues, "advertencia", "metadatos", pdfname, f"{count} registros parecen referirse a este PDF; revisar si es duplicidad.")

    extract_by_name = {}
    for entry in extraction:
        name = pdf_identifier(entry.get("archivo"))
        if name in extract_by_name:
            issue(issues, "advertencia", "extraccion", name, "Registro de extracción duplicado.")
        if name:
            extract_by_name[name] = entry
        else:
            issue(issues, "advertencia", "extraccion", str(entry.get("archivo")), "No se pudo identificar un nombre PDF.")
    extraction_rows = []
    for name in sorted(pdf_by_name):
        entry = extract_by_name.get(name)
        if not entry:
            issue(issues, "advertencia", "extraccion", name, "No existe un registro de extracción para este PDF.")
            extraction_rows.append({"archivo": name, "registro": "ausente"})
            continue
        count = count_or_none(entry.get("paginas"))
        err = count_or_none(entry.get("paginas_ocr_error"))
        empty = count_or_none(entry.get("paginas_ocr_vacias"))
        chars = count_or_none(entry.get("chars_total"))
        extraction_rows.append({
            "archivo": name, "paginas_reportadas": count,
            "paginas_ocr": entry.get("paginas_ocr"), "paginas_pdf_texto": entry.get("paginas_pdf_texto"),
            "paginas_ocr_error": entry.get("paginas_ocr_error"),
            "paginas_ocr_vacias": entry.get("paginas_ocr_vacias"),
            "chars_total": entry.get("chars_total")
        })
        if err is not None and err > 0:
            issue(issues, "advertencia", "ocr", name, f"{err} páginas con error OCR según el resumen.")
        if empty is not None and empty > 0:
            issue(issues, "advertencia", "ocr", name, f"{empty} páginas OCR vacías según el resumen.")
        if chars == 0:
            issue(issues, "advertencia", "ocr", name, "Resumen reporta 0 caracteres; revisar PDF manualmente.")
        if count is None:
            issue(issues, "advertencia", "ocr", name, "Número total de páginas no interpretable.")
    for name in sorted(set(extract_by_name) - set(pdf_by_name)):
        issue(issues, "advertencia", "extraccion", name, "Hay un resumen de extracción sin PDF local correspondiente.")

    gold_by_id = record_ids(gold, "preguntas", issues)
    validations_by_id = record_ids(validations, "validaciones", issues)
    for name in sorted(set(gold_by_id) - set(validations_by_id)):
        issue(issues, "advertencia", "validaciones", name, "Pregunta sin registro de validación con el mismo ID.")
    for name in sorted(set(validations_by_id) - set(gold_by_id)):
        issue(issues, "advertencia", "validaciones", name, "Validación sin pregunta con el mismo ID.")
    normalized_questions = Counter(" ".join(str(g.get("pregunta", "")).casefold().split()) for g in gold)
    repeated = {q: c for q, c in normalized_questions.items() if q and c > 1}
    if repeated:
        issue(issues, "advertencia", "preguntas", "duplicados", f"{len(repeated)} preguntas con texto repetido; revisar equivalencias.")

    question_rows = []
    for q in gold:
        qid = str(q.get("id", "sin-id"))
        sources = q.get("fuentes")
        mentioned = sorted(referenced_pdf_names(sources))
        pages = sorted(set(page_numbers(sources)))
        missing = [n for n in mentioned if n not in pdf_by_name]
        if missing:
            issue(issues, "advertencia", "referencias", qid, "PDF referenciados no presentes: " + ", ".join(missing))
        if not mentioned:
            issue(issues, "advertencia", "referencias", qid, "No se pudo identificar el PDF en 'fuentes'; revisar su esquema manualmente.")
        if not pages:
            issue(issues, "informativa", "referencias", qid, "No se encontraron campos numéricos explícitos de páginas; validar cita manualmente.")
        if len(mentioned) == 1:
            record = extract_by_name.get(mentioned[0], {})
            max_page = count_or_none(record.get("paginas"))
            for page in pages:
                if page < 1 or max_page is not None and page > max_page:
                    issue(issues, "advertencia", "referencias", qid, f"Página {page} fuera del rango físico 1..{max_page}; revisar numeración.")
        question_rows.append({
            "id": qid, "tipo": q.get("tipo"), "fuentes_pdf_detectadas": mentioned,
            "paginas_numericas_detectadas": pages, "referencias_ausentes": missing,
            "apta_recuperacion_declarada": q.get("apta_para_evaluar_recuperacion_documental_piloto"),
            "apta_vigencia_declarada": q.get("apta_para_evaluar_respuesta_normativa_vigente"),
            "estado_validacion_declarado": q.get("estado_validacion_2026_11_17"),
            "tiene_validacion_registrada": qid in validations_by_id,
            "cita_contrastada_con_pdf": False,
        })
    if len(gold) != len(validations):
        issue(issues, "advertencia", "validaciones", "conteo", f"{len(gold)} preguntas frente a {len(validations)} registros de validación.")

    return {
        "version_auditoria": "1.0", "politica": "solo lectura; validacion estructural, no legal ni semantica",
        "conteos": {
            "pdf": len(pdf_files), "pdf_oficial": sum("01_Corpus_Oficial" in str(p) for p in pdf_files),
            "pdf_historico": sum("01B_Historicos" in str(p) for p in pdf_files),
            "pdf_sha256_coincidentes": sum(r["estado"] == "coincide" for r in integrity),
            "entradas_baseline": len(baseline), "documentos_metadatos": len(documents),
            "registros_extraccion": len(extraction), "preguntas_gold": len(gold),
            "registros_validacion": len(validations),
            "incidencias_error": sum(x["severidad"] == "error" for x in issues),
            "incidencias_advertencia": sum(x["severidad"] == "advertencia" for x in issues),
            "incidencias_informativas": sum(x["severidad"] == "informativa" for x in issues),
        },
        "integridad": integrity, "metadatos": doc_meta, "extraccion": extraction_rows,
        "preguntas": question_rows, "incidencias": issues,
        "limitaciones": [
            "Los hashes verifican identidad de bytes, no vigencia normativa.",
            "La calidad real del OCR no queda certificada por el resumen de extracción; requiere cotejar páginas.",
            "Los números de página provienen de campos explícitos de las fuentes, sin confirmar su contenido.",
            "No se verificó la veracidad de las respuestas de referencia contra el PDF.",
            "Los metadatos de vigencia son declaraciones: falta contrastarlos con fuentes oficiales vigentes.",
            "No se modifica el corpus, las preguntas ni la baseline."
        ]
    }


def generate_markdown(result: dict) -> str:
    c = result["conteos"]
    lines = [
        "# Auditoría del corpus UNSA — Etapa 1 (T1)", "",
        "> Informe automático de inventario y consistencia. No certifica vigencia normativa ni exactitud de respuestas.", "",
        "## Resumen de la ejecución", "",
        "| Indicador | Total |", "|---|---:|",
    ]
    for key, value in c.items():
        lines.append(f"| `{key}` | {value} |")
    lines += ["", "## Integridad SHA-256 frente a la baseline v0.1", "",
              "| PDF | Estado |", "|---|---|"]
    for row in result["integridad"]:
        lines.append(f"| `{row['archivo']}` | {row['estado']} |")
    lines += ["", "## Metadatos e inclusión documental", "",
              "Los registros que no están en el paquete NO se consideran automáticamente archivos perdidos.", "",
              "| ID | PDF identificado | Situación | Vigencia declarada |", "|---|---|---|---|"]
    for row in result["metadatos"]:
        lines.append("| {} | {} | {} | {} |".format(
            str(row["id"]).replace("|", "/"), str(row["pdf"] or "—").replace("|", "/"),
            row["situacion"], str(row["vigencia_declarada"] or "—").replace("|", "/")))
    lines += ["", "## Extracción de texto y alertas OCR", "",
              "Los valores proceden del resumen de extracción, no de una nueva inspección visual.", "",
              "| PDF | Páginas | Errores OCR | Páginas OCR vacías | Caracteres |", "|---|---:|---|---|---:|"]
    for row in result["extraccion"]:
        lines.append("| `{}` | {} | {} | {} | {} |".format(
            row["archivo"], row.get("paginas_reportadas", "—"),
            row.get("paginas_ocr_error", "—"), row.get("paginas_ocr_vacias", "—"), row.get("chars_total", "—")))
    lines += ["", "## Evidencia de revisión manual", "",
              "La evidencia manual se guarda por separado: regenerar este informe no la modifica.", "",
              "- [Verificación visual de RCU-0127-2020, página 8](evidencias/revision_visual_rcu_0127_2020_p8.md)",
              "- [Validación textual piloto de 15 preguntas gold](VALIDACION_GOLD_PILOTO.md)", ""]
    lines += ["", "## Preguntas de referencia", "",
              f"Se encontraron **{c['preguntas_gold']}** preguntas y **{c['registros_validacion']}** entradas de validación.",
              "El informe revisa estructura, IDs y posibles referencias ausentes; **no valida** la respuesta contra el contenido del PDF.", "",
              "## Incidencias automáticas", "",
              "| Severidad | Categoría | Elemento | Detalle |", "|---|---|---|---|"]
    for entry in result["incidencias"]:
        lines.append("| {} | {} | {} | {} |".format(*[
            str(entry[key]).replace("|", "/").replace("\n", " ")
            for key in ("severidad", "categoria", "elemento", "detalle")]))
    if not result["incidencias"]:
        lines.append("| — | — | — | Sin incidencias automáticas detectadas. |")
    lines += ["", "## Limitaciones y siguientes pasos", ""]
    lines.extend(f"- {description}" for description in result["limitaciones"])
    lines += ["", "**Revisión humana pendiente:** cotejo independiente de los PDF y páginas citadas, vigencia y relaciones normativas. La muestra piloto de 15 preguntas ya tiene una validación textual preliminar documentada; GQ030 sigue pendiente de completar su referencia antes de usarla en T10.", ""]
    return "\n".join(lines)


def main() -> None:
    result = run_audit()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT_MD.write_text(generate_markdown(result), encoding="utf-8")
    summary = result["conteos"]
    print(f"PDF: {summary['pdf']} | SHA-256 coincidentes: {summary['pdf_sha256_coincidentes']}")
    print(f"Metadatos: {summary['documentos_metadatos']} | Gold: {summary['preguntas_gold']} | Validaciones: {summary['registros_validacion']}")
    print(f"Incidencias: {summary['incidencias_error']} errores, {summary['incidencias_advertencia']} advertencias, {summary['incidencias_informativas']} informativas")
    print(f"Informe: {OUT_MD.relative_to(ROOT)}")
    print(f"Datos: {OUT_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
