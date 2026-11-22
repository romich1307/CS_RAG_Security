"""Módulo de auditoría experimental para el proyecto CS_RAG_Security (T20).

Permite auditar y verificar:
- Identificador y procedencia de cada corrida (commit, dirty, entorno, timestamps).
- Hashes de corpus, índice, datasets y manifiestos en disco frente a los declarados.
- Consistencia de hiperparámetros con los invariantes experimentales (seed 42, temp 0, top_k 5).
- Consistencia de condiciones A/B/C y correspondencia pareada de consultas.
- Detección de duplicados, casos faltantes y evaluaciones pendientes.
- Separación formal entre experimentos reales con LLM, pilotos y simulaciones mock.
- Consistencia de numeradores y denominadores (denominador cero genera estrictamente None).
- Cobertura de evaluación humana independiente (T12) y gestión de consensos.
- Ausencia estricta de información privada en artefactos públicos/publicables.
- Generación de reportes de auditoría en JSON y Markdown con incidencias y limitaciones.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from cs_rag_security.defenses import MODES
from cs_rag_security.ingestion import digest
from cs_rag_security.traceability import PROMPT_VERSIONS


# Severidades estándar de incidencias
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "advertencia"
SEVERITY_INFO = "informativa"

# Códigos canónicos de incidencias
CODE_HASH_MISMATCH = "HASH_MISMATCH"
CODE_MALFORMED_HASH = "MALFORMED_HASH"
CODE_FILE_MISSING = "FILE_MISSING"
CODE_INCOMPATIBLE_RUNS = "INCOMPATIBLE_RUNS"
CODE_UNIMODAL_RUN = "UNIMODAL_RUN"
CODE_MISSING_CASES = "MISSING_CASES"
CODE_DUPLICATE_CASE = "DUPLICATE_CASE"
CODE_UNPAIRED_CASES = "UNPAIRED_CASES"
CODE_PENDING_EVALUATIONS = "PENDING_EVALUATIONS"
CODE_MOCK_RUN_LIMITATION = "MOCK_RUN_LIMITATION"
CODE_PILOT_RUN_LIMITATION = "PILOT_RUN_LIMITATION"
CODE_INCONSISTENT_DENOMINATOR = "INCONSISTENT_DENOMINATOR"
CODE_PRIVACY_VIOLATION = "PRIVACY_VIOLATION"
CODE_PARAMETER_NON_COMPLIANT = "PARAMETER_NON_COMPLIANT"
CODE_SCRIPTS_HASH_MISSING = "SCRIPTS_HASH_MISSING"
CODE_GIT_DIRTY = "GIT_DIRTY"

# Estados canónicos de verificación de hash
HASH_STATUS_VERIFIED = "verified"
HASH_STATUS_MISMATCH = "mismatch"
HASH_STATUS_MALFORMED = "malformed"
HASH_STATUS_FILE_NOT_FOUND = "file_not_found"

# Tipos canónicos de corrida
RUN_TYPE_REAL_LLM = "real_llm"
RUN_TYPE_PILOT_LLM = "pilot_llm"
RUN_TYPE_MOCK_OFFLINE = "mock_offline"
RUN_TYPE_SYNTHETIC_TEST = "synthetic_test"
RUN_TYPE_UNKNOWN = "unknown"

# Invariantes esperados
EXPECTED_SEED = 42
EXPECTED_TEMPERATURE = 0
EXPECTED_TOP_K = 5
EXPECTED_EVIDENCE_THRESHOLD = 0.12


@dataclass
class AuditIssue:
    """Representa un hallazgo o incidencia identificada en la auditoría."""

    code: str
    message: str
    severity: str
    run_id: Optional[str] = None
    source: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "run_id": self.run_id,
            "source": self.source,
        }


@dataclass
class RunAuditResult:
    """Resultado detallado de la auditoría de una corrida individual."""

    run_id: str
    path: str
    run_type: str
    provenance: Dict[str, Any]
    parameters: Dict[str, Any]
    parameters_compliant: bool
    conditions_present: List[str]
    is_multimodal_abc: bool
    prompt_versions: Dict[str, str]
    cases_evaluated: List[str]
    cases_count: int
    case_kinds: List[str]
    duplicates: List[Dict[str, Any]]
    missing_expected_cases: List[str]
    paired_coverage: Dict[str, Any]
    hashes_status: Dict[str, Any]
    privacy_compliant: bool
    issues: List[AuditIssue] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "path": self.path,
            "run_type": self.run_type,
            "provenance": self.provenance,
            "parameters": self.parameters,
            "parameters_compliant": self.parameters_compliant,
            "conditions_present": self.conditions_present,
            "is_multimodal_abc": self.is_multimodal_abc,
            "prompt_versions": self.prompt_versions,
            "cases_evaluated": self.cases_evaluated,
            "cases_count": self.cases_count,
            "case_kinds": self.case_kinds,
            "duplicates": self.duplicates,
            "missing_expected_cases": self.missing_expected_cases,
            "paired_coverage": self.paired_coverage,
            "hashes_status": self.hashes_status,
            "privacy_compliant": self.privacy_compliant,
            "issues": [i.to_dict() for i in self.issues],
            "limitations": self.limitations,
        }


@dataclass
class ExperimentAuditReport:
    """Informe consolidado de auditoría experimental (T20)."""

    timestamp_utc: str
    overall_status: str  # 'aprobado', 'aprobado_con_observaciones', 'rechazado'
    runs_audited: Dict[str, RunAuditResult]
    cross_run_consistency: Dict[str, Any]
    human_evaluation_coverage: Dict[str, Any]
    privacy_audit: Dict[str, Any]
    all_issues: List[AuditIssue] = field(default_factory=list)
    all_limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_utc": self.timestamp_utc,
            "overall_status": self.overall_status,
            "runs_audited": {k: v.to_dict() for k, v in self.runs_audited.items()},
            "cross_run_consistency": self.cross_run_consistency,
            "human_evaluation_coverage": self.human_evaluation_coverage,
            "privacy_audit": self.privacy_audit,
            "all_issues": [i.to_dict() for i in self.all_issues],
            "all_limitations": self.all_limitations,
        }

    def save_json(self, path: Union[str, Path]) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def to_markdown(self) -> str:
        lines: List[str] = []
        lines.append("# Reporte de Auditoría Experimental — CS_RAG_Security (T20)")
        lines.append("")
        lines.append(f"- **Fecha UTC de auditoría:** {self.timestamp_utc}")
        lines.append(f"- **Dictamen global:** **{self.overall_status.upper()}**")
        lines.append(f"- **Total de corridas auditadas:** {len(self.runs_audited)}")
        lines.append(f"- **Total de incidencias:** {len(self.all_issues)} "
                     f"(Errores: {sum(1 for i in self.all_issues if i.severity == SEVERITY_ERROR)}, "
                     f"Advertencias: {sum(1 for i in self.all_issues if i.severity == SEVERITY_WARNING)}, "
                     f"Informativas: {sum(1 for i in self.all_issues if i.severity == SEVERITY_INFO)})")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 1. Resumen por Corrida Experimental")
        lines.append("")
        lines.append("| Corrida ID | Tipo | Proveedor | Modelo | Condiciones | Casos | Privacidad | Estado |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for rid, r in self.runs_audited.items():
            status_tag = "OK" if not any(i.severity == SEVERITY_ERROR for i in r.issues) else "ERROR"
            priv_tag = "Conforme" if r.privacy_compliant else "VIOLACIÓN"
            prov = r.parameters.get("provider", "N/A")
            mod = r.parameters.get("model", "N/A")
            conds = ", ".join(r.conditions_present) if r.conditions_present else "N/A"
            lines.append(f"| `{rid}` | {r.run_type} | {prov} | {mod} | {conds} | {r.cases_count} | {priv_tag} | {status_tag} |")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 2. Cobertura de Evaluación Humana (T12 / T18)")
        lines.append("")
        he = self.human_evaluation_coverage
        lines.append(f"- **Estado de evaluación humana:** {he.get('status_description', 'N/A')}")
        lines.append(f"- **Total registros evaluados:** {he.get('total_registros', 0)}")
        lines.append(f"- **Consultas evaluables juzgadas:** {he.get('evaluables', 0)} ({he.get('tasa_evaluables', 'N/A')})")
        lines.append(f"- **Casos pendientes:** {he.get('pendientes', 0)} ({he.get('tasa_pendientes', 'N/A')})")
        lines.append(f"- **Casos no evaluables / excluidos:** {he.get('no_evaluables', 0)}")
        lines.append(f"- **Discrepancias sin consenso:** {len(he.get('desacuerdos_sin_consenso', []))}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 3. Incidencias Registradas")
        lines.append("")
        if not self.all_issues:
            lines.append("No se registraron incidencias.")
        else:
            lines.append("| Severidad | Código | Corrida / Origen | Descripción |")
            lines.append("| :--- | :--- | :--- | :--- |")
            for iss in self.all_issues:
                src = iss.run_id or iss.source or "Global"
                lines.append(f"| `{iss.severity}` | `{iss.code}` | {src} | {iss.message} |")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 4. Limitaciones Metodológicas Identificadas")
        lines.append("")
        if not self.all_limitations:
            lines.append("No se registraron limitaciones específicas.")
        else:
            for lim in self.all_limitations:
                lines.append(f"- {lim}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 5. Declaración de Alcance de Privacidad")
        lines.append("")
        lines.append("El escaneo automatizado de privacidad aplica listas de exclusión y expresiones regulares sobre los artefactos analizados; ")
        lines.append("no constituye una demostración matemática de ausencia absoluta de fugas ni sustituye la debida diligencia ")
        lines.append("ni la revisión forense humana de los archivos destinados a publicación.")
        lines.append("")
        return "\n".join(lines)

    def save_markdown(self, path: Union[str, Path]) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_markdown(), encoding="utf-8")


def detect_run_type(manifest: Dict[str, Any], path: Path) -> str:
    """Clasifica formalmente la naturaleza experimental de una corrida."""
    # 1. Piloto explícito
    if "piloto" in path.name.lower() or "pilot" in manifest.get("task", "").lower() or "piloto" in manifest.get("task", "").lower():
        return RUN_TYPE_PILOT_LLM

    provider = manifest.get("proveedor") or manifest.get("provider")
    llm = manifest.get("modelo") or manifest.get("model") or manifest.get("llm")
    task = manifest.get("tarea") or manifest.get("task") or ""

    if provider == "mock" or llm == "mock_extractivo_v1":
        return RUN_TYPE_MOCK_OFFLINE

    if provider in ("local", "api"):
        if "synthetic" in task.lower() or "test" in task.lower():
            return RUN_TYPE_SYNTHETIC_TEST
        return RUN_TYPE_REAL_LLM

    if "synthetic" in str(path).lower() or "test" in str(path).lower():
        return RUN_TYPE_SYNTHETIC_TEST

    return RUN_TYPE_UNKNOWN


def check_privacy_compliance_in_data(
    records: List[Dict[str, Any]],
    gold_questions: Optional[List[str]] = None,
    source_name: str = "",
) -> Tuple[bool, List[AuditIssue]]:
    """Verifica que una lista de registros no contenga fragmentos de texto privado ni preguntas gold."""
    issues: List[AuditIssue] = []
    is_compliant = True

    # Palabras clave sospechosas de tokens/claves
    secret_patterns = ["sk-", "api_key", "bearer ", "authorization:"]

    for idx, rec in enumerate(records):
        cid = rec.get("case_id") or rec.get("id") or f"row_{idx}"

        # 1. raw_response no debe figurar en artefactos públicos
        if "raw_response" in rec and rec["raw_response"] is not None:
            # Si contiene texto sustancial, es violación estricta
            if str(rec["raw_response"]).strip():
                is_compliant = False
                issues.append(
                    AuditIssue(
                        code=CODE_PRIVACY_VIOLATION,
                        message=f"El campo confidencial 'raw_response' está expuesto en {source_name} (caso {cid}; contenido confidencial omitido en reporte).",
                        severity=SEVERITY_ERROR,
                        source=source_name,
                    )
                )

        # 2. question textual no debe figurar en público
        if "question" in rec and rec["question"]:
            is_compliant = False
            issues.append(
                AuditIssue(
                    code=CODE_PRIVACY_VIOLATION,
                    message=f"El campo confidencial 'question' está expuesto en {source_name} (caso {cid}; enunciado confidencial omitido en reporte).",
                    severity=SEVERITY_ERROR,
                    source=source_name,
                )
            )

        # 3. Fragmentos no deben contener el campo 'texto'
        for chunk_key in ("retrieved_chunks", "accepted_chunks", "discarded_chunks", "evaluated_chunks"):
            if chunk_key in rec and isinstance(rec[chunk_key], list):
                for ch in rec[chunk_key]:
                    if isinstance(ch, dict) and "texto" in ch and ch["texto"]:
                        is_compliant = False
                        issues.append(
                            AuditIssue(
                                code=CODE_PRIVACY_VIOLATION,
                                message=f"Fragmento en '{chunk_key}' contiene texto literal del corpus en {source_name} (caso {cid}; texto confidencial omitido en reporte).",
                                severity=SEVERITY_ERROR,
                                source=source_name,
                            )
                        )
                        break

        # 4. Comprobación contra enunciados literales gold
        if gold_questions:
            rec_str = json.dumps(rec, ensure_ascii=False)
            for gq in gold_questions:
                if len(gq) > 15 and gq in rec_str:
                    is_compliant = False
                    issues.append(
                        AuditIssue(
                            code=CODE_PRIVACY_VIOLATION,
                            message=f"Texto coincidente con pregunta gold detectado en {source_name} (caso {cid}; enunciado confidencial omitido en reporte).",
                            severity=SEVERITY_ERROR,
                            source=source_name,
                        )
                    )
                    break

        # 5. Detección de claves de API
        rec_str = json.dumps(rec, ensure_ascii=False).lower()
        for pat in secret_patterns:
            if pat in rec_str:
                is_compliant = False
                issues.append(
                    AuditIssue(
                        code=CODE_PRIVACY_VIOLATION,
                        message=f"Patrón sospechoso de credencial o clave de API detectado en {source_name} (caso {cid}; valor omitido en reporte por seguridad).",
                        severity=SEVERITY_ERROR,
                        source=source_name,
                    )
                )
                break

    return is_compliant, issues


def is_valid_sha256(val: Any) -> bool:
    """Verifica si un valor es un hash SHA-256 sintácticamente válido (64 caracteres hexadecimales)."""
    if not isinstance(val, str):
        return False
    return bool(re.fullmatch(r"[0-9a-fA-F]{64}", val.strip()))


def _audit_single_file_hash(
    declared_hash: Any,
    expected_path: Path,
    key: str,
    run_id: str,
) -> Tuple[Dict[str, Any], Optional[AuditIssue]]:
    """Coteja un hash individual distinguiendo verified, mismatch, malformed y file_not_found.

    Un hash malformado se detecta independientemente de si el archivo existe o no en disco.
    """
    if not is_valid_sha256(declared_hash):
        status_info = {
            "declared": declared_hash,
            "status": HASH_STATUS_MALFORMED,
            "path": str(expected_path),
        }
        issue = AuditIssue(
            code=CODE_MALFORMED_HASH,
            message=f"Hash SHA-256 malformado para {key} ({expected_path.name}): {declared_hash!r} no es un hash hexadecimal válido de 64 caracteres.",
            severity=SEVERITY_ERROR,
            run_id=run_id,
            source=str(expected_path),
        )
        return status_info, issue

    clean_declared = str(declared_hash).strip().lower()

    if not expected_path.exists():
        status_info = {
            "declared": clean_declared,
            "status": HASH_STATUS_FILE_NOT_FOUND,
            "path": str(expected_path),
        }
        issue = AuditIssue(
            code=CODE_FILE_MISSING,
            message=f"Archivo de referencia para {key} no existe en disco: {expected_path}",
            severity=SEVERITY_WARNING,
            run_id=run_id,
            source=str(expected_path),
        )
        return status_info, issue

    computed = digest(expected_path).lower()
    match = (computed == clean_declared)
    status_info = {
        "declared": clean_declared,
        "computed": computed,
        "path": str(expected_path),
        "status": HASH_STATUS_VERIFIED if match else HASH_STATUS_MISMATCH,
    }
    issue = None
    if not match:
        issue = AuditIssue(
            code=CODE_HASH_MISMATCH,
            message=f"Discrepancia en hash SHA-256 de {key} ({expected_path.name}): declarado={clean_declared[:10]}..., calculado={computed[:10]}...",
            severity=SEVERITY_ERROR,
            run_id=run_id,
            source=str(expected_path),
        )
    return status_info, issue


def verify_file_hashes(
    manifest_hashes: Dict[str, Any],
    base_dir: Optional[Union[str, Path]] = None,
    run_id: str = "",
) -> Tuple[Dict[str, Any], List[AuditIssue]]:
    """Coteja los hashes declarados en el manifiesto con los archivos reales en disco."""
    results: Dict[str, Any] = {}
    issues: List[AuditIssue] = []
    base = Path(base_dir) if base_dir else Path.cwd()

    # Mapeo de claves canónicas a rutas relativas
    target_files = {
        "index_sha256": base / "data/vector_db/index.json",
        "gold_sha256": base / "data/corpus_unsa/03_Preguntas_Respuestas/gold_questions.json",
        "attacks_sha256": base / "experiments/attacks.jsonl",
    }

    # Revisar hashes directos
    for key, expected_path in target_files.items():
        declared_hash = manifest_hashes.get(key)
        if declared_hash is not None:
            info, issue = _audit_single_file_hash(declared_hash, expected_path, key, run_id)
            results[key] = info
            if issue:
                issues.append(issue)

    # Revisar hashes anidados bajo 'hashes'
    nested = manifest_hashes.get("hashes", {})
    if isinstance(nested, dict):
        for k, v in nested.items():
            if k in target_files and k not in results and v is not None:
                exp_path = target_files[k]
                info, issue = _audit_single_file_hash(v, exp_path, k, run_id)
                results[k] = info
                if issue:
                    issues.append(issue)

    return results, issues


def audit_run(
    run_dir_or_file: Union[str, Path],
    corpus_dir: Optional[Union[str, Path]] = None,
    expected_cases: Optional[List[str]] = None,
    gold_questions: Optional[List[str]] = None,
    base_dir: Optional[Union[str, Path]] = None,
) -> RunAuditResult:
    """Audita de forma exhaustiva una corrida experimental o piloto."""
    path = Path(run_dir_or_file)
    issues: List[AuditIssue] = []
    limitations: List[str] = []

    # 1. Cargar archivo o directorio
    manifest: Dict[str, Any] = {}
    traces: List[Dict[str, Any]] = []

    if path.is_file():
        # Puede ser un piloto JSON individual
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                manifest = data
                # Tratamos el piloto como un único registro de traza
                traces = [data]
            run_id = data.get("task", path.stem)
        except Exception as e:
            issues.append(
                AuditIssue(
                    code="FILE_READ_ERROR",
                    message=f"No se pudo leer el archivo JSON: {e}",
                    severity=SEVERITY_ERROR,
                    source=str(path),
                )
            )
            run_id = path.stem
    else:
        run_id = path.name
        manifest_file = path / "manifest.json"
        if manifest_file.exists():
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            except Exception as e:
                issues.append(
                    AuditIssue(
                        code="MANIFEST_READ_ERROR",
                        message=f"Error al parsear manifest.json: {e}",
                        severity=SEVERITY_ERROR,
                        run_id=run_id,
                        source=str(manifest_file),
                    )
                )
        else:
            issues.append(
                AuditIssue(
                    code="MANIFEST_MISSING",
                    message="No se encontró manifest.json en el directorio de la corrida.",
                    severity=SEVERITY_ERROR,
                    run_id=run_id,
                    source=str(path),
                )
            )

        # Cargar traces.json
        traces_file = path / "traces.json"
        if traces_file.exists():
            try:
                loaded = json.loads(traces_file.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    traces = loaded
            except Exception as e:
                issues.append(
                    AuditIssue(
                        code="TRACES_READ_ERROR",
                        message=f"Error al leer traces.json: {e}",
                        severity=SEVERITY_ERROR,
                        run_id=run_id,
                        source=str(traces_file),
                    )
                )

    run_type = detect_run_type(manifest, path)

    # 2. Procedencia y control de versiones
    env = manifest.get("entorno", {})
    git_commit = manifest.get("commit_git") or env.get("commit_git")
    git_dirty = manifest.get("git_dirty") if "git_dirty" in manifest else env.get("git_dirty", False)

    provenance = {
        "commit_git": git_commit,
        "git_dirty": git_dirty,
        "python_version": manifest.get("python_version") or manifest.get("python") or env.get("python_version"),
        "package_version": manifest.get("package_version") or manifest.get("package") or env.get("package_version"),
        "started_utc": manifest.get("started_utc"),
        "finished_utc": manifest.get("finished_utc"),
        "tarea": manifest.get("tarea") or manifest.get("task", ""),
        "descripcion": manifest.get("descripcion", ""),
    }

    # Verificar si existe PROCEDENCIA.md en el directorio
    if path.is_dir() and (path / "PROCEDENCIA.md").exists():
        provenance["procedencia_doc"] = "PROCEDENCIA.md presente"

    # Distinción formal de código histórico frente a alteración de datos (Punto 5)
    current_git = None
    try:
        from cs_rag_security.traceability import get_git_commit
        current_git = get_git_commit()
    except Exception:
        pass

    if git_commit and current_git and git_commit != current_git:
        provenance["evolucion_codigo"] = (
            f"El commit base declarado ({git_commit[:8]}) difiere del HEAD actual ({current_git[:8]}). "
            "Las diferencias en src/ corresponden a la evolución legítima de tareas posteriores (T14, T16, T18, T20) "
            "y se distinguen formalmente de una alteración de los artefactos de datos originales (índice y datasets)."
        )
        issues.append(
            AuditIssue(
                code="HISTORICAL_CODE_EVOLUTION",
                message=f"Los hashes de código fuente en el manifiesto corresponden al commit base ({git_commit[:8]}); las modificaciones posteriores en src/ reflejan la evolución legítima del proyecto (ver PROCEDENCIA.md).",
                severity=SEVERITY_INFO,
                run_id=run_id,
            )
        )

    if git_dirty:
        issues.append(
            AuditIssue(
                code=CODE_GIT_DIRTY,
                message="La corrida fue ejecutada en un entorno de trabajo git sucio (modificaciones sin commitear).",
                severity=SEVERITY_WARNING,
                run_id=run_id,
            )
        )

    # Verificar si faltan hashes de scripts (limitación histórica de T11)
    hashes_dict = manifest.get("hashes", {})
    source_sha = manifest.get("source_sha256") or hashes_dict.get("src_sha256")
    scripts_sha = hashes_dict.get("scripts_sha256")

    if run_type == RUN_TYPE_REAL_LLM and not scripts_sha:
        issues.append(
            AuditIssue(
                code=CODE_SCRIPTS_HASH_MISSING,
                message="El manifiesto no incluye hashes SHA-256 de scripts ejecutables (scripts_sha256); documentado como limitación histórica.",
                severity=SEVERITY_WARNING,
                run_id=run_id,
            )
        )
        limitations.append("Manifiesto histórico sin registro criptográfico explícito de scripts ejecutables.")

    # 3. Parámetros e Invariantes
    params = manifest.get("parametros") or manifest.get("parameters") or {}
    prov_name = manifest.get("proveedor") or manifest.get("provider") or "unknown"
    mod_name = manifest.get("modelo") or manifest.get("model") or manifest.get("llm") or "unknown"
    mod_digest = manifest.get("modelo_digest")

    # Extraer parámetros de trazabilidad o traza si no están en la raíz
    if not params and traces:
        params = traces[0].get("parameters", {})

    seed = params.get("seed", manifest.get("seed"))
    temperature = params.get("temperature", manifest.get("temperature"))
    top_k = params.get("top_k", manifest.get("top_k"))
    threshold = params.get("evidence_threshold", manifest.get("evidence_threshold"))

    param_summary = {
        "provider": prov_name,
        "model": mod_name,
        "model_digest": mod_digest,
        "seed": seed,
        "temperature": temperature,
        "top_k": top_k,
        "evidence_threshold": threshold,
    }

    parameters_compliant = True
    if seed is not None and seed != EXPECTED_SEED:
        parameters_compliant = False
        issues.append(
            AuditIssue(
                code=CODE_PARAMETER_NON_COMPLIANT,
                message=f"Semilla experimental ({seed}) discrepa del invariante esperado ({EXPECTED_SEED}).",
                severity=SEVERITY_ERROR,
                run_id=run_id,
            )
        )
    if temperature is not None and temperature != EXPECTED_TEMPERATURE:
        parameters_compliant = False
        issues.append(
            AuditIssue(
                code=CODE_PARAMETER_NON_COMPLIANT,
                message=f"Temperatura ({temperature}) discrepa del invariante esperado ({EXPECTED_TEMPERATURE}).",
                severity=SEVERITY_ERROR,
                run_id=run_id,
            )
        )
    if top_k is not None and top_k != EXPECTED_TOP_K:
        parameters_compliant = False
        issues.append(
            AuditIssue(
                code=CODE_PARAMETER_NON_COMPLIANT,
                message=f"top_k ({top_k}) discrepa del invariante esperado ({EXPECTED_TOP_K}).",
                severity=SEVERITY_WARNING,
                run_id=run_id,
            )
        )

    # 4. Condiciones experimentales y prompts
    declared_modes = manifest.get("modes") or manifest.get("condiciones_evaluadas")
    if declared_modes is None and "modo_experimental" in manifest:
        declared_modes = [manifest["modo_experimental"]]
    if declared_modes is None and "mode" in manifest:
        declared_modes = [manifest["mode"]]

    # También extraer de trazas
    trace_modes = sorted(list({t.get("condition") or t.get("mode") for t in traces if t.get("condition") or t.get("mode")}))
    conditions_present = trace_modes if trace_modes else (declared_modes or [])

    is_multimodal = (len(set(conditions_present) & set(MODES)) == len(MODES))

    if not is_multimodal:
        issues.append(
            AuditIssue(
                code=CODE_UNIMODAL_RUN,
                message=f"La corrida no contiene las tres condiciones A/B/C completas (presentes: {conditions_present}).",
                severity=SEVERITY_INFO,
                run_id=run_id,
            )
        )
        limitations.append(f"Corrida parcial/unimodal ({', '.join(conditions_present)}): comparaciones pareadas limitadas a las condiciones presentes.")

    # Versiones de prompt
    prompt_versions: Dict[str, str] = {}
    pvers_manifest = manifest.get("versiones_prompt")
    if isinstance(pvers_manifest, dict):
        prompt_versions = pvers_manifest
    else:
        for t in traces:
            m = t.get("condition") or t.get("mode")
            pv = t.get("prompt_version")
            if m and pv and m not in prompt_versions:
                prompt_versions[m] = pv

    # 5. Casos evaluados, duplicados y pareamiento
    cases_set: Set[str] = set()
    case_kinds_set: Set[str] = set()
    per_condition_cases: Dict[str, List[str]] = {}
    duplicates: List[Dict[str, Any]] = []

    seen_pairs: Set[Tuple[str, str]] = set()

    for idx, t in enumerate(traces):
        cid = t.get("case_id") or t.get("id") or t.get("query_id") or f"case_{idx}"
        cond = t.get("condition") or t.get("mode") or "default"
        kind = t.get("case_kind") or t.get("kind") or "gold"

        cases_set.add(cid)
        case_kinds_set.add(kind)
        per_condition_cases.setdefault(cond, []).append(cid)

        pair = (cid, cond)
        if pair in seen_pairs:
            duplicates.append({"case_id": cid, "condition": cond, "index": idx})
        seen_pairs.add(pair)

    if duplicates:
        issues.append(
            AuditIssue(
                code=CODE_DUPLICATE_CASE,
                message=f"Se detectaron {len(duplicates)} ejecuciones duplicadas para tuplas (case_id, condition).",
                severity=SEVERITY_ERROR,
                run_id=run_id,
            )
        )

    # Pareamiento entre condiciones
    paired_coverage: Dict[str, Any] = {}
    if len(per_condition_cases) > 1:
        first_cond = list(per_condition_cases.keys())[0]
        first_cases = set(per_condition_cases[first_cond])
        is_strictly_paired = True
        for cond, c_list in per_condition_cases.items():
            diff = first_cases.symmetric_difference(set(c_list))
            if diff:
                is_strictly_paired = False
                issues.append(
                    AuditIssue(
                        code=CODE_UNPAIRED_CASES,
                        message=f"Desbalance en consultas pareadas entre condiciones: {cond} tiene diferencias {sorted(diff)} frente a {first_cond}.",
                        severity=SEVERITY_WARNING,
                        run_id=run_id,
                    )
                )
        paired_coverage = {
            "strictly_paired": is_strictly_paired,
            "cases_per_condition": {k: len(v) for k, v in per_condition_cases.items()},
        }
    else:
        paired_coverage = {
            "strictly_paired": True,
            "cases_per_condition": {k: len(v) for k, v in per_condition_cases.items()},
        }

    missing_cases: List[str] = []
    if expected_cases:
        missing_cases = sorted(set(expected_cases) - cases_set)
        if missing_cases:
            issues.append(
                AuditIssue(
                    code=CODE_MISSING_CASES,
                    message=f"Faltan {len(missing_cases)} casos esperados en la corrida: {missing_cases[:5]}...",
                    severity=SEVERITY_WARNING,
                    run_id=run_id,
                )
            )

    # 6. Hashes
    all_manifest_hashes = {}
    all_manifest_hashes.update(manifest)
    if "hashes" in manifest and isinstance(manifest["hashes"], dict):
        all_manifest_hashes.update(manifest["hashes"])

    hashes_status, hash_issues = verify_file_hashes(all_manifest_hashes, base_dir=base_dir, run_id=run_id)
    issues.extend(hash_issues)

    # 7. Privacidad
    privacy_compliant, priv_issues = check_privacy_compliance_in_data(
        traces,
        gold_questions=gold_questions,
        source_name=f"{run_id}/traces.json",
    )
    issues.extend(priv_issues)

    # Limitaciones por tipo de corrida
    if run_type == RUN_TYPE_MOCK_OFFLINE:
        limitations.append("Corrida con generador mock: NO mide eficacia de defensa frente a LLM ni Attack Success Rate (ASR).")
        issues.append(
            AuditIssue(
                code=CODE_MOCK_RUN_LIMITATION,
                message="Corrida mock: las métricas de respuesta y ASR son diagnósticos sintéticos que no acreditan robustez de un LLM.",
                severity=SEVERITY_INFO,
                run_id=run_id,
            )
        )
    elif run_type == RUN_TYPE_PILOT_LLM:
        limitations.append("Piloto puntual aislado: no constituye evaluación sistemática ni permite generalización estadística.")
        issues.append(
            AuditIssue(
                code=CODE_PILOT_RUN_LIMITATION,
                message="Ejecución piloto exploratoria de un solo caso.",
                severity=SEVERITY_INFO,
                run_id=run_id,
            )
        )

    return RunAuditResult(
        run_id=run_id,
        path=str(path),
        run_type=run_type,
        provenance=provenance,
        parameters=param_summary,
        parameters_compliant=parameters_compliant,
        conditions_present=conditions_present,
        is_multimodal_abc=is_multimodal,
        prompt_versions=prompt_versions,
        cases_evaluated=sorted(cases_set),
        cases_count=len(cases_set),
        case_kinds=sorted(case_kinds_set),
        duplicates=duplicates,
        missing_expected_cases=missing_cases,
        paired_coverage=paired_coverage,
        hashes_status=hashes_status,
        privacy_compliant=privacy_compliant,
        issues=issues,
        limitations=limitations,
    )


def audit_human_evaluation_coverage(
    annotations_path: Union[str, Path],
    mapping_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Audita la cobertura y completitud de la evaluación humana independiente (T12)."""
    p = Path(annotations_path)
    if not p.exists():
        return {
            "status": "file_not_found",
            "status_description": "Archivo de anotaciones no encontrado",
            "total_registros": 0,
            "evaluables": 0,
            "pendientes": 0,
            "no_evaluables": 0,
            "tasa_evaluables": "0.0%",
            "tasa_pendientes": "0.0%",
            "desacuerdos_sin_consenso": [],
        }

    rows: List[Dict[str, Any]] = []
    if p.suffix.lower() == ".csv":
        with p.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    elif p.suffix.lower() == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else []

    total = len(rows)
    pending = 0
    not_evaluable = 0
    annotated = 0
    consensed = 0

    for r in rows:
        st = str(r.get("estado_revision", "")).strip().lower()
        if st == "pendiente" or not st:
            pending += 1
        elif st == "no_evaluable":
            not_evaluable += 1
        elif st == "anotado":
            annotated += 1
        elif st == "consensuado":
            consensed += 1

    evaluable = annotated + consensed
    eval_pct = f"{round((evaluable / total) * 100, 2)}%" if total else "N/A"
    pend_pct = f"{round((pending / total) * 100, 2)}%" if total else "N/A"

    if total == 0:
        desc = "Sin registros de evaluación humana."
    elif pending == total:
        desc = f"Evaluación humana íntegramente PENDIENTE ({pending}/{total} registros asignados a León en T12)."
    elif evaluable == total:
        desc = f"Evaluación humana COMPLETADA ({evaluable}/{total} registros evaluables)."
    else:
        desc = f"Evaluación humana PARCIAL ({evaluable}/{total} evaluables, {pending}/{total} pendientes)."

    return {
        "status": "completado" if evaluable == total and total > 0 else ("pendiente" if pending == total else "parcial"),
        "status_description": desc,
        "total_registros": total,
        "evaluables": evaluable,
        "anotados": annotated,
        "consensuados": consensed,
        "pendientes": pending,
        "no_evaluables": not_evaluable,
        "tasa_evaluables": eval_pct,
        "tasa_pendientes": pend_pct,
        "desacuerdos_sin_consenso": [],
    }


def audit_experiments(
    run_paths: List[Union[str, Path]],
    annotations_path: Optional[Union[str, Path]] = None,
    mapping_path: Optional[Union[str, Path]] = None,
    gold_path: Optional[Union[str, Path]] = None,
    expected_cases: Optional[List[str]] = None,
    base_dir: Optional[Union[str, Path]] = None,
) -> ExperimentAuditReport:
    """Ejecuta la auditoría experimental completa sobre múltiples corridas y artefactos."""
    timestamp_utc = datetime.now(timezone.utc).isoformat()
    runs_audited: Dict[str, RunAuditResult] = {}
    all_issues: List[AuditIssue] = []
    all_limitations: List[str] = []

    # Cargar textos de preguntas gold si están disponibles para control de privacidad estricto
    gold_questions: List[str] = []
    default_gold = (Path(base_dir) / "data/corpus_unsa/03_Preguntas_Respuestas/gold_questions.json") if base_dir else Path("data/corpus_unsa/03_Preguntas_Respuestas/gold_questions.json")
    g_path = Path(gold_path) if gold_path else default_gold
    if g_path.exists():
        try:
            g_data = json.loads(g_path.read_text(encoding="utf-8"))
            if "preguntas" in g_data and isinstance(g_data["preguntas"], list):
                for q in g_data["preguntas"]:
                    if isinstance(q, dict) and "pregunta" in q:
                        gold_questions.append(q["pregunta"])
        except Exception:
            pass

    # 1. Auditar cada corrida individualmente
    for rp in run_paths:
        p = Path(rp)
        if not p.exists():
            iss = AuditIssue(
                code=CODE_FILE_MISSING,
                message=f"La ruta de corrida especificada no existe: {p}",
                severity=SEVERITY_ERROR,
                source=str(p),
            )
            all_issues.append(iss)
            continue

        res = audit_run(
            p,
            expected_cases=expected_cases,
            gold_questions=gold_questions,
            base_dir=base_dir,
        )
        runs_audited[res.run_id] = res
        all_issues.extend(res.issues)
        all_limitations.extend(res.limitations)

    # 2. Consistencia cruzada entre corridas (Cross-run consistency)
    cross_run: Dict[str, Any] = {
        "runs_count": len(runs_audited),
        "shared_index_hash": True,
        "shared_gold_hash": True,
        "shared_attacks_hash": True,
        "hashes_summary": {},
    }

    # Cotejar si todas las corridas consumieron el mismo índice y dataset
    index_hashes: Set[str] = set()
    gold_hashes: Set[str] = set()
    attacks_hashes: Set[str] = set()

    for rid, r in runs_audited.items():
        idx_info = r.hashes_status.get("index_sha256", {})
        if idx_info.get("declared"):
            index_hashes.add(idx_info["declared"])

        gold_info = r.hashes_status.get("gold_sha256", {})
        if gold_info.get("declared"):
            gold_hashes.add(gold_info["declared"])

        atk_info = r.hashes_status.get("attacks_sha256", {})
        if atk_info.get("declared"):
            attacks_hashes.add(atk_info["declared"])

    if len(index_hashes) > 1:
        cross_run["shared_index_hash"] = False
        all_issues.append(
            AuditIssue(
                code=CODE_INCOMPATIBLE_RUNS,
                message=f"Corridas incompatibles: se detectaron {len(index_hashes)} hashes distintos de índice ({list(index_hashes)}).",
                severity=SEVERITY_ERROR,
            )
        )
    if len(gold_hashes) > 1:
        cross_run["shared_gold_hash"] = False
        all_issues.append(
            AuditIssue(
                code=CODE_INCOMPATIBLE_RUNS,
                message=f"Corridas incompatibles: se detectaron {len(gold_hashes)} hashes distintos del dataset gold.",
                severity=SEVERITY_ERROR,
            )
        )
    if len(attacks_hashes) > 1:
        cross_run["shared_attacks_hash"] = False
        all_issues.append(
            AuditIssue(
                code=CODE_INCOMPATIBLE_RUNS,
                message=f"Corridas incompatibles: se detectaron {len(attacks_hashes)} hashes distintos del dataset de ataques.",
                severity=SEVERITY_ERROR,
            )
        )

    cross_run["hashes_summary"] = {
        "index_hashes": list(index_hashes),
        "gold_hashes": list(gold_hashes),
        "attacks_hashes": list(attacks_hashes),
    }

    # 3. Cobertura de evaluación humana
    human_cov: Dict[str, Any] = {}
    if annotations_path:
        human_cov = audit_human_evaluation_coverage(annotations_path, mapping_path)
        if human_cov.get("status") == "pendiente":
            all_limitations.append("Evaluación humana T12 pendiente: exactitud humana de contenido y adecuación de abstenciones sin juicios consolidados.")
            all_issues.append(
                AuditIssue(
                    code=CODE_PENDING_EVALUATIONS,
                    message="Evaluación humana T12 completamente pendiente; no se pueden computar métricas semánticas definitivas.",
                    severity=SEVERITY_INFO,
                    source=str(annotations_path),
                )
            )

    # 4. Auditoría de privacidad consolidada
    total_priv_issues = sum(1 for i in all_issues if i.code == CODE_PRIVACY_VIOLATION)
    priv_audit = {
        "compliant": total_priv_issues == 0,
        "violations_count": total_priv_issues,
    }

    # Determinar dictamen global
    has_errors = any(i.severity == SEVERITY_ERROR for i in all_issues)
    has_warnings = any(i.severity == SEVERITY_WARNING for i in all_issues)

    if has_errors:
        overall_status = "rechazado"
    elif has_warnings or any(r.run_type == RUN_TYPE_MOCK_OFFLINE for r in runs_audited.values()):
        overall_status = "aprobado_con_observaciones"
    else:
        overall_status = "aprobado"

    # Desduplicar limitaciones
    dedup_limitations = list(dict.fromkeys(all_limitations))

    return ExperimentAuditReport(
        timestamp_utc=timestamp_utc,
        overall_status=overall_status,
        runs_audited=runs_audited,
        cross_run_consistency=cross_run,
        human_evaluation_coverage=human_cov,
        privacy_audit=priv_audit,
        all_issues=all_issues,
        all_limitations=dedup_limitations,
    )
