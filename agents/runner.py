"""Sequential CrewAI runner with human approval gates (HA-02, HA-03, HA-08, HA-09).

Flow: input guardrail -> Product Owner proposal -> HUMAN scope gate ->
Architect -> AI Engineer -> QA & Security -> Presenter -> HUMAN final gate.
`--dry-run` builds the real agents but uses deterministic stub outputs and
never calls a model or the mock. Dry-run results are never `ready`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from crewai import BaseLLM, Crew, Process

from guardrails.input_check import validate_snapshot

from . import ai_engineer, architect, gates, presenter_timekeeper, product_owner, qa_security
from .mcp_tools import CALL_LOG, McpToolError, allowed_tool_names, build_crewai_tools, call_mcp_tool

ROOT = gates.ROOT
RUNS_DIR = ROOT / "evidence" / "runs"
POLICY_PATH = ROOT / "harness" / "policies" / "allowed_tools.json"
STORIES = (
    "user-onboarding-mvp-completion",
    "payer-low-value-payment-confirmation",
    "merchant-qr-payment-status-visibility",
    "payment-idempotency-protection",
    "payment-failure-reversal-handling",
    "operations-transaction-reconciliation",
)
SOURCES = (
    ROOT / "docs" / "userstories" / "epic" / "peru-wallet-mvp.sp.md",
    *(ROOT / "docs" / "userstories" / "user-stories" / f"{name}.sp.md" for name in STORIES),
    ROOT / "docs" / "hackaton" / "criterios-de-aceptacion.md",
    gates.CHANGE_DIR / "proposal.md",
    gates.CHANGE_DIR / "specs" / "hackathon-agent-workflow" / "spec.md",
)
IMPLEMENTATION_ROLES = (
    ("02_architect", architect),
    ("03_ai_engineer", ai_engineer),
    ("04_qa_security", qa_security),
    ("05_presenter_timekeeper", presenter_timekeeper),
)
MCP_ROLES = {"02_architect", "04_qa_security"}


class CopilotLLM(BaseLLM):
    """CrewAI LLM over the repository's Copilot SDK runtime (no function calling)."""

    def call(self, messages, **kwargs):
        from lab_copilot.runtime import complete_sync

        return complete_sync(messages, self.model)

    def supports_function_calling(self):
        return False


def read_sources(paths: tuple[Path, ...] = SOURCES) -> tuple[str, list[str]]:
    parts, missing = [], []
    for path in paths:
        if path.is_file():
            parts.append(f"### FUENTE: {path.relative_to(ROOT).as_posix()}\n{path.read_text(encoding='utf-8')}")
        else:
            missing.append(str(path))
    return "\n\n".join(parts), missing


def check_tools_policy(tools: list[Any], policy_path: Path = POLICY_PATH) -> None:
    """Reject blocked tools and anything outside the local read-only MCP allow-list."""
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    blocked, allowed = set(policy.get("blocked", [])), set(policy.get("allowed", []))
    mcp_allowed = allowed_tool_names()
    for tool in tools:
        if tool.name in blocked:
            raise PermissionError(f"Herramienta bloqueada por la politica: {tool.name}")
        if tool.name not in allowed and tool.name not in mcp_allowed:
            raise PermissionError(f"Herramienta fuera de la lista permitida: {tool.name}")


def first_content_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped.lstrip("*_> ").strip()
    return ""


def is_blocked(output: str) -> bool:
    return first_content_line(output).upper().startswith("BLOQUEADO")


def _stub_output(role: str, context: str) -> str:
    digest = hashlib.sha256(context.encode("utf-8")).hexdigest()[:12]
    return (
        f"[DRY-RUN] {role}: salida simulada sin llamada a modelo ni al mock.\n"
        f"No es evidencia, no es una aprobacion y no sustituye una ejecucion real. "
        f"Contexto recibido: {len(context)} caracteres (sha256 {digest}).\n"
    )


def _execute(agent, task, mode: str, role: str) -> str:
    if mode == "dry-run":
        return _stub_output(role, task.description)
    result = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False).kickoff()
    return str(result.raw if hasattr(result, "raw") else result)


def _write(run_dir: Path, name: str, text: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / name).write_text(text, encoding="utf-8")


def _approval_summary(result: gates.GateResult) -> str:
    record = result.record or {}
    return (
        f"Aprobacion humana de alcance: version {record.get('scopeVersion')}, aprobada por "
        f"{record.get('approver')} el {record.get('timestamp')}."
    )


def run_pipeline(
    *,
    mode: str,
    scope_version: str,
    scope_approval_path: Path = gates.DEFAULT_SCOPE_APPROVAL,
    final_approval_path: Path = gates.DEFAULT_FINAL_APPROVAL,
    runs_dir: Path = RUNS_DIR,
    sources: tuple[Path, ...] = SOURCES,
    llm: BaseLLM | str | None = None,
    use_mcp: bool = True,
    mcp_tools_factory: Callable[[], list[Any]] = build_crewai_tools,
) -> dict[str, Any]:
    if mode not in ("dry-run", "real"):
        raise ValueError("mode debe ser 'dry-run' o 'real'.")
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"
    run_dir = Path(runs_dir) / run_id
    calls_start = len(CALL_LOG)
    report: dict[str, Any] = {
        "runId": run_id,
        "mode": mode,
        "scopeVersion": scope_version,
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "ready": False,
        "status": "STARTED",
        "tasks": {},
        "scopeGate": None,
        "finalGate": None,
        "mcpTools": [],
        "mcpCalls": [],
        "notes": [],
    }

    def finish(status: str) -> dict[str, Any]:
        report["status"] = status
        report["mcpCalls"] = CALL_LOG[calls_start:]
        report["finishedAt"] = datetime.now(timezone.utc).isoformat()
        run_dir.mkdir(parents=True, exist_ok=True)
        _write(run_dir, "report.json", json.dumps(report, indent=2, ensure_ascii=False))
        report["runDir"] = str(run_dir)
        return report

    for protected in (scope_approval_path, final_approval_path):
        if Path(protected).resolve().is_relative_to(Path(runs_dir).resolve()):
            raise PermissionError("Los registros de aprobacion no pueden vivir en el directorio de salidas.")

    context, missing = read_sources(sources)
    if missing:
        report["notes"].append(f"Fuentes faltantes: {missing}")
        return finish("BLOCKED_INPUT")
    verdict = validate_snapshot(context)
    if not verdict.valid:
        report["notes"].append(f"Guardrail de entrada: {verdict.reason}")
        return finish("BLOCKED_INPUT")

    if mode == "real" and llm is None:
        raise ValueError("El modo real requiere un LLM configurado explicitamente.")
    model: BaseLLM | str = llm if llm is not None else "dry-run-stub"
    if mode == "dry-run" and isinstance(model, str):
        model = CopilotLLM(model="dry-run-stub")

    mcp_tools: list[Any] = []
    if mode == "real" and use_mcp:
        mcp_tools = mcp_tools_factory()
        check_tools_policy(mcp_tools)
        report["mcpTools"] = [tool.name for tool in mcp_tools]
    elif mode == "dry-run":
        report["mcpTools"] = sorted(allowed_tool_names())
        report["notes"].append("Dry-run: herramientas MCP listadas, no invocadas.")

    scope_context = f"VERSION DE ALCANCE VIGENTE: {scope_version}\n\n{context}"
    po_agent = product_owner.create_agent(model)
    po_task = product_owner.create_task(po_agent, scope_context)
    verdict = validate_snapshot(po_task.description)
    if not verdict.valid:
        report["notes"].append(f"Guardrail de entrada: {verdict.reason}")
        return finish("BLOCKED_INPUT")
    po_output = _execute(po_agent, po_task, mode, product_owner.ROLE)
    _write(run_dir, "01_product_owner.md", po_output)
    report["tasks"]["01_product_owner"] = "EJECUTADO" if mode == "real" else "DRY-RUN"

    scope_gate = gates.check_scope_approval(scope_approval_path, scope_version)
    report["scopeGate"] = scope_gate.as_dict()
    if not scope_gate.passed:
        for name, _ in IMPLEMENTATION_ROLES:
            report["tasks"][name] = "NO EJECUTADO (bloqueado por gate de alcance)"
        return finish("BLOCKED_SCOPE")

    outputs: dict[str, str] = {}
    previous = f"PROPUESTA DEL PRODUCT OWNER (no es aprobacion):\n{po_output}"
    for name, module in IMPLEMENTATION_ROLES:
        tools = mcp_tools if name in MCP_ROLES else None
        agent = module.create_agent(model, tools) if name in MCP_ROLES else module.create_agent(model)
        task_context = f"{_approval_summary(scope_gate)}\n\n{previous}\n\n{scope_context}"
        task = module.create_task(agent, task_context)
        verdict = validate_snapshot(task.description)
        if not verdict.valid:
            report["notes"].append(f"Guardrail de entrada en {name}: {verdict.reason}")
            report["tasks"][name] = "NO EJECUTADO (guardrail de entrada)"
            return finish("BLOCKED_INPUT")
        output = _execute(agent, task, mode, module.ROLE)
        outputs[name] = output
        _write(run_dir, f"{name}.md", output)
        report["tasks"][name] = "EJECUTADO" if mode == "real" else "DRY-RUN"
        if is_blocked(output):
            report["notes"].append(f"{module.ROLE} reporto BLOQUEADO; no se ejecutan los roles siguientes.")
            pending = [n for n, _ in IMPLEMENTATION_ROLES if n not in outputs]
            for pending_name in pending:
                report["tasks"][pending_name] = "NO EJECUTADO (rol previo BLOQUEADO)"
            return finish("BLOCKED_ROLE")
        previous = f"ENTREGA DE {module.ROLE}:\n{output}"

    digest = gates.evidence_digest(outputs)
    report["evidenceDigest"] = digest
    report["scopeApproval"] = scope_gate.record
    ready, status = _final_status(mode, outputs, final_approval_path, scope_version, digest, scope_gate.record, report)
    report["ready"] = ready
    return finish(status)


def _final_status(mode, outputs, final_path, scope_version, digest, scope_record, report):
    complete = len(outputs) == len(IMPLEMENTATION_ROLES)
    if mode != "real":
        report["finalGate"] = {"passed": False, "code": "NOT_EVALUATED", "reason": "Dry-run: nunca es ready."}
        return gates.decide_readiness(mode=mode, deliverables_complete=complete, final_gate=None)
    final_gate = gates.check_final_approval(final_path, scope_version, digest, scope_record)
    report["finalGate"] = final_gate.as_dict()
    return gates.decide_readiness(mode=mode, deliverables_complete=complete, final_gate=final_gate)


def finalize(
    run_dir: Path,
    final_approval_path: Path = gates.DEFAULT_FINAL_APPROVAL,
    scope_version: str | None = None,
) -> dict[str, Any]:
    """Re-evaluate the human final gate over a saved run; no model call."""
    run_dir = Path(run_dir)
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    version = scope_version or report["scopeVersion"]
    outputs = {
        name: (run_dir / f"{name}.md").read_text(encoding="utf-8")
        for name, _ in IMPLEMENTATION_ROLES
        if (run_dir / f"{name}.md").is_file()
    }
    if report.get("scopeVersion") != version:
        report["finalGate"] = {
            "passed": False,
            "code": "VERSION_MISMATCH",
            "reason": "La ejecucion corresponde a otra version de alcance.",
        }
        ready, status = False, "FINAL_APPROVAL_INVALID"
    elif report.get("status") == "BLOCKED_SCOPE" or (report.get("scopeGate") or {}).get("passed") is not True:
        report["finalGate"] = {"passed": False, "code": "SCOPE_NOT_APPROVED", "reason": "Sin aprobacion de alcance."}
        ready, status = False, "BLOCKED_SCOPE"
    else:
        digest = gates.evidence_digest(outputs)
        ready, status = _final_status(
            report["mode"], outputs, final_approval_path, version, digest, report.get("scopeApproval"), report
        )
        report["evidenceDigest"] = digest
    report.update(ready=ready, status=status, finalizedAt=datetime.now(timezone.utc).isoformat())
    _write(run_dir, "report.json", json.dumps(report, indent=2, ensure_ascii=False))
    return report


def mcp_smoke(output: Path) -> dict[str, Any]:
    """One real read-only call to GET /scenarios through the stdio MCP server."""
    text = call_mcp_tool("get_scenarios")
    record = {
        "tool": "get_scenarios",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "response": json.loads(text),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return record


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Runner CrewAI secuencial con gates humanos.")
    parser.add_argument("--dry-run", action="store_true", help="Sin LLM ni mock; salidas simuladas deterministas.")
    parser.add_argument("--scope-version", help="Version de alcance (por defecto, hash de proposal/spec/criterios).")
    parser.add_argument("--scope-approval", type=Path, default=gates.DEFAULT_SCOPE_APPROVAL)
    parser.add_argument("--final-approval", type=Path, default=gates.DEFAULT_FINAL_APPROVAL)
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    parser.add_argument("--model", help="Modelo Copilot (por defecto COPILOT_MODEL o gpt-6-luna).")
    parser.add_argument("--no-mcp", action="store_true", help="Modo real sin herramientas MCP.")
    parser.add_argument("--print-scope-version", action="store_true")
    parser.add_argument("--finalize", type=Path, metavar="RUN_DIR", help="Reevaluar el gate final de una ejecucion.")
    parser.add_argument("--mcp-smoke", action="store_true", help="Una llamada real GET /scenarios via MCP stdio.")
    return parser


EXIT_OK = {"READY", "DRY_RUN_COMPLETE"}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    os.environ.setdefault("CREWAI_TELEMETRY_OPT_OUT", "true")
    os.environ.setdefault("OTEL_SDK_DISABLED", "true")
    version = args.scope_version or gates.compute_scope_version()
    if args.print_scope_version:
        print(version)
        return 0
    if args.mcp_smoke:
        try:
            record = mcp_smoke(ROOT / "evidence" / "mcp_live_scenarios.json")
        except McpToolError as error:
            print(f"FALLO MCP: {error}", file=sys.stderr)
            return 1
        print(json.dumps(record["response"], ensure_ascii=False))
        return 0
    if args.finalize:
        report = finalize(args.finalize, args.final_approval, args.scope_version)
    else:
        _load_env()
        mode = "dry-run" if args.dry_run else "real"
        llm = None
        if mode == "real":
            llm = CopilotLLM(model=args.model or os.getenv("COPILOT_MODEL", "gpt-6-luna"))
        try:
            report = run_pipeline(
                mode=mode,
                scope_version=version,
                scope_approval_path=args.scope_approval,
                final_approval_path=args.final_approval,
                runs_dir=args.runs_dir,
                llm=llm,
                use_mcp=not args.no_mcp,
            )
        except Exception as error:
            print(f"ERROR: {type(error).__name__}: {error}", file=sys.stderr)
            return 1
    print(json.dumps({k: report.get(k) for k in ("runId", "mode", "status", "ready", "scopeGate", "finalGate", "runDir")},
                     indent=2, ensure_ascii=False))
    return 0 if report["status"] in EXIT_OK else 2


if __name__ == "__main__":
    raise SystemExit(main())
