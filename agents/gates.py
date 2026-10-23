"""Human approval gates for the CrewAI runner (HA-02, HA-09).

Approvals are JSON records written by a person. This module only reads and
validates them: no code path here or in the runner creates or signs one, and
an agent's output is never parsed as a decision.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGE_DIR = ROOT / "openspec" / "changes" / "wallet-demo-grupo3"
SCOPE_FILES = (
    ROOT / "docs" / "hackaton" / "criterios-de-aceptacion.md",
    CHANGE_DIR / "proposal.md",
    *sorted((CHANGE_DIR / "specs").glob("*/spec.md")),
)
DEFAULT_SCOPE_APPROVAL = ROOT / "evidence" / "scope_approval.json"
DEFAULT_FINAL_APPROVAL = ROOT / "evidence" / "final_approval.json"

APPROVED = "APPROVED"
REJECTED = "REJECTED"
CLOCK_SKEW = timedelta(minutes=5)
AGENT_APPROVER = re.compile(
    r"\b(agent[e]?s?|crew\s*ai|llm|gpt|copilot|bot|model[o]?|assistant|asistente)\b",
    re.IGNORECASE,
)
ROLE_NAMES = {
    "product owner",
    "arquitecto/a",
    "ai engineer",
    "qa & security",
    "presenter / timekeeper",
}


@dataclass(frozen=True)
class GateResult:
    passed: bool
    code: str
    reason: str
    record: dict | None = field(default=None, repr=False)

    def as_dict(self) -> dict:
        return {"passed": self.passed, "code": self.code, "reason": self.reason}


def compute_scope_version(files: tuple[Path, ...] | list[Path] | None = None) -> str:
    digest = hashlib.sha256()
    for path in files if files is not None else SCOPE_FILES:
        digest.update(path.name.encode("utf-8") + b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return f"wallet-demo-grupo3@{digest.hexdigest()[:12]}"


def evidence_digest(outputs: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for name in sorted(outputs):
        digest.update(name.encode("utf-8") + b"\0" + outputs[name].encode("utf-8") + b"\0")
    return digest.hexdigest()


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _read_record(path: Path, label: str) -> tuple[dict | None, GateResult | None]:
    path = Path(path)
    if not path.is_file():
        return None, GateResult(
            False, "MISSING", f"Falta el registro humano de {label}: {path}. Sin decision no se continua."
        )
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, GateResult(False, "INVALID", f"Registro de {label} ilegible: {error}")
    if not isinstance(record, dict):
        return None, GateResult(False, "INVALID", f"El registro de {label} debe ser un objeto JSON.")
    return record, None


def _validate_common(record: dict, label: str, scope_version: str) -> GateResult | None:
    for key in ("scopeVersion", "decision", "approver", "approverType", "timestamp"):
        if not isinstance(record.get(key), str) or not record[key].strip():
            return GateResult(False, "INVALID", f"Campo obligatorio ausente en {label}: {key}.")
    if record["approverType"] != "HUMAN":
        return GateResult(False, "AGENT_APPROVER", f"{label}: approverType debe ser HUMAN.")
    approver = record["approver"].strip()
    if AGENT_APPROVER.search(approver) or approver.lower() in ROLE_NAMES:
        return GateResult(
            False, "AGENT_APPROVER", f"{label}: el aprobador debe ser una persona, no un agente o rol."
        )
    stamp = _parse_timestamp(record["timestamp"])
    if stamp is None:
        return GateResult(False, "INVALID", f"{label}: timestamp ISO 8601 con zona horaria requerido.")
    if stamp > datetime.now(timezone.utc) + CLOCK_SKEW:
        return GateResult(False, "INVALID", f"{label}: timestamp en el futuro.")
    if record["decision"] not in (APPROVED, REJECTED):
        return GateResult(False, "INVALID", f"{label}: decision debe ser APPROVED o REJECTED.")
    if record["decision"] == REJECTED:
        return GateResult(False, "REJECTED", f"{label} rechazada por {approver}.")
    if record["scopeVersion"] != scope_version:
        return GateResult(
            False,
            "VERSION_MISMATCH",
            f"{label} aprueba {record['scopeVersion']}, pero la version vigente es {scope_version}.",
        )
    return None


def check_scope_approval(path: Path, scope_version: str) -> GateResult:
    record, failure = _read_record(path, "aprobacion de alcance")
    if failure:
        return failure
    failure = _validate_common(record, "Aprobacion de alcance", scope_version)
    return failure or GateResult(True, "APPROVED", "Alcance aprobado por una persona.", record)


def check_final_approval(
    path: Path,
    scope_version: str,
    reviewed_digest: str,
    scope_approval: dict | None = None,
) -> GateResult:
    record, failure = _read_record(path, "aprobacion final")
    if failure:
        return failure
    failure = _validate_common(record, "Aprobacion final", scope_version)
    if failure:
        return failure
    refs = record.get("evidenceRefs")
    if not isinstance(refs, list) or not refs or not all(isinstance(r, str) and r.strip() for r in refs):
        return GateResult(False, "INVALID", "Aprobacion final: evidenceRefs debe listar la evidencia revisada.")
    gaps = record.get("unresolvedGaps")
    if not isinstance(gaps, list) or not all(isinstance(g, str) for g in gaps):
        return GateResult(False, "INVALID", "Aprobacion final: unresolvedGaps debe ser una lista (puede ser vacia).")
    if record.get("reviewedDigest") != reviewed_digest:
        return GateResult(
            False,
            "STALE_EVIDENCE",
            "Aprobacion final: reviewedDigest no coincide con las entregas de esta ejecucion.",
        )
    if scope_approval:
        initial = _parse_timestamp(scope_approval.get("timestamp"))
        if initial and _parse_timestamp(record["timestamp"]) < initial:
            return GateResult(False, "INVALID", "Aprobacion final anterior a la aprobacion de alcance.")
    return GateResult(True, "APPROVED", "Entrega aprobada por el Product Owner humano.", record)


def decide_readiness(
    *, mode: str, deliverables_complete: bool, final_gate: GateResult | None
) -> tuple[bool, str]:
    """`ready` solo con ejecucion real, entregas completas y aprobacion humana final."""
    if mode != "real":
        return False, "DRY_RUN_COMPLETE"
    if not deliverables_complete:
        return False, "BLOCKED_ROLE"
    if final_gate is None or final_gate.code == "MISSING":
        return False, "AWAITING_FINAL_APPROVAL"
    if final_gate.passed:
        return True, "READY"
    if final_gate.code == "REJECTED":
        return False, "FINAL_REJECTED"
    return False, "FINAL_APPROVAL_INVALID"
