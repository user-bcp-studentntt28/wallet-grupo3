"""Punto de entrada de la demo Wallet Perú (grupo 3).

`python main.py` recorre las cinco etapas en el orden de los agentes definidos
(Product Owner -> Arquitecto/a -> AI Engineer -> QA & Security ->
Presenter / Timekeeper) y, si ninguna falla, levanta el servidor Python.

Cada etapa es una verificación determinista de la responsabilidad de su rol:
no llama a ningún modelo ni inventa una aprobación. La aprobación humana inicial
solo se lee (evidence/scope_approval.json); con --strict su ausencia bloquea.
Para ejecutar los agentes CrewAI usa --crew dry-run o --crew real.
El laboratorio LangGraph anterior vive en lab_main.py.
"""
from __future__ import annotations

import argparse
import py_compile
import socket
import subprocess
import sys
import threading
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCOPE_APPROVAL = ROOT / "evidence" / "scope_approval.json"
FINAL_APPROVAL = ROOT / "evidence" / "final_approval.json"
DEFAULT_PORT = 8000
DEMO_MODULES = ("demo_server.py", "demo_routes.py", "demo_guardrails.py", "demo_evidence.py", "demo_auth.py")
WEB_FILES = ("index.html", "app.js", "styles.css", "vendor/qrcode.js")
SKILLS = ("product_owner", "architect", "ai_engineer", "qa_security", "presenter_timekeeper")
DEMO_TESTS = ("tests.test_demo_routes", "tests.test_demo_guardrails", "tests.test_wallet_demo_server", "tests.test_demo_auth")
AGENT_TESTS_PATTERN = "test_hackaton*.py"

OK, WARN, FAIL, SKIP = "OK", "ADVERTENCIA", "FALLO", "NO EJECUTADO"


@dataclass
class Stage:
    role: str
    status: str = OK
    lines: list[str] = field(default_factory=list)


def stage_product_owner(strict: bool) -> Stage:
    """Alcance: versión vigente y estado de la aprobación humana inicial."""
    from agents import gates

    stage = Stage("Product Owner - alcance y aprobación inicial")
    version = gates.compute_scope_version()
    stage.lines.append(f"Versión de alcance: {version}")
    result = gates.check_scope_approval(SCOPE_APPROVAL, version)
    if result.passed:
        stage.lines.append("Aprobación humana inicial: VIGENTE para esta versión.")
    else:
        stage.status = FAIL if strict else WARN
        stage.lines.append(f"Aprobación humana inicial: {result.code} - {result.reason}")
        stage.lines.append("Una persona debe crear evidence/scope_approval.json (ver docs/hackaton/runner.md).")
    return stage


def stage_architect() -> Stage:
    """Arquitectura: mapa de operaciones del mock y rutas prohibidas."""
    import demo_guardrails as guardrails

    stage = Stage("Arquitecto/a - mapa de endpoints y límites del mock")
    counts = {policy: 0 for policy in (guardrails.ALLOW, guardrails.CONFIRM, guardrails.DENY)}
    for feature in guardrails.FEATURE_MAP:
        counts[feature.policy] += 1
    stage.lines.append(
        f"{len(guardrails.FEATURE_MAP)} operaciones clasificadas: {counts['ALLOW']} permitidas, "
        f"{counts['CONFIRM']} con confirmación humana, {counts['DENY']} prohibidas."
    )
    for method, path in (("POST", "/control/reset"), ("POST", "/payments/{id}/reversals")):
        feature = guardrails.classify(method, path)
        if feature is None or feature.policy != guardrails.DENY:
            stage.status = FAIL
            stage.lines.append(f"{method} {path} debe estar prohibida y no lo está.")
    if stage.status == OK:
        stage.lines.append("Reset y reversos prohibidos; lo no mapeado se deniega por defecto.")
    return stage


def stage_ai_engineer() -> Stage:
    """Implementación: módulos compilan, la web existe y las cinco skills están."""
    stage = Stage("AI Engineer - implementación y skills")
    for name in DEMO_MODULES:
        try:
            py_compile.compile(str(ROOT / name), doraise=True)
        except py_compile.PyCompileError as error:
            stage.status = FAIL
            stage.lines.append(f"{name} no compila: {error.msg.strip()}")
    missing = [f for f in WEB_FILES if not (ROOT / "wallet_demo_web" / f).is_file()]
    missing += [f"agents/skills/{s}.md" for s in SKILLS if not _non_empty(ROOT / "agents" / "skills" / f"{s}.md")]
    if missing:
        stage.status = FAIL
        stage.lines.append(f"Faltan archivos o están vacíos: {', '.join(missing)}")
    if stage.status == OK:
        stage.lines.append(f"{len(DEMO_MODULES)} módulos compilan; web completa; {len(SKILLS)} skills de rol presentes.")
    return stage


def _non_empty(path: Path) -> bool:
    return path.is_file() and bool(path.read_text(encoding="utf-8").strip())


def stage_qa_security(skip_tests: bool, full: bool) -> Stage:
    """QA & Security: pruebas automatizadas y guardrails."""
    stage = Stage("QA & Security - pruebas y guardrails")
    if skip_tests:
        stage.status = SKIP
        stage.lines.append("Pruebas omitidas (--skip-tests): no cuentan como aprobadas.")
        return stage
    commands = [("demo", [sys.executable, "-m", "unittest", *DEMO_TESTS])]
    if full:
        commands.append(
            ("agentes", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", AGENT_TESTS_PATTERN])
        )
    for label, command in commands:
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        tail = [line for line in (run.stderr or run.stdout).strip().splitlines() if line][-3:]
        if run.returncode != 0:
            stage.status = FAIL
            stage.lines.append(f"Pruebas de {label} FALLARON:")
            stage.lines.extend(f"    {line}" for line in tail)
        else:
            stage.lines.append(f"Pruebas de {label}: {tail[-1] if tail else 'OK'}")
    return stage


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def stage_presenter(port: int) -> Stage:
    """Presenter / Timekeeper: puerto libre, guion y estado de la aprobación final."""
    stage = Stage("Presenter / Timekeeper - guion y arranque")
    if port_in_use(port):
        stage.status = FAIL
        stage.lines.append(f"El puerto {port} ya está en uso. Cierra el proceso anterior o usa --port.")
        return stage
    stage.lines.append(f"Demo en http://127.0.0.1:{port}  (guion: docs/hackaton/guion-demo.md)")
    stage.lines.append("Registro con usuario TEST-...; evidencia: docs/hackaton/evidencia-demo.md")
    if not FINAL_APPROVAL.is_file():
        stage.lines.append("Aprobación final del Product Owner: PENDIENTE (la demo no se declara lista sin ella).")
    return stage


def run_crew(mode: str) -> Stage:
    """Opcional: ejecuta los cinco agentes CrewAI en su orden definido."""
    from agents import runner

    stage = Stage(f"CrewAI ({mode}) - cinco roles en orden")
    argv = ["--dry-run"] if mode == "dry-run" else []
    code = runner.main(argv)
    if code == 0:
        stage.lines.append("Runner finalizado.")
    else:
        stage.status = WARN
        stage.lines.append(f"Runner terminó con código {code} (por ejemplo, bloqueado por falta de aprobación humana).")
    return stage


MARKS = {OK: "[OK]", WARN: "[!] ", FAIL: "[X] ", SKIP: "[-] "}


def print_stage(index: int, stage: Stage) -> None:
    print(f"\n{index}. {MARKS[stage.status]} {stage.role}  ->  {stage.status}")
    for line in stage.lines:
        print(f"     {line}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Demo Wallet Perú: etapas por rol y servidor Python.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Puerto del servidor (por defecto {DEFAULT_PORT}).")
    parser.add_argument("--strict", action="store_true", help="Sin aprobación humana inicial vigente, no arranca.")
    parser.add_argument("--skip-tests", action="store_true", help="Omite las pruebas (queda NO EJECUTADO).")
    parser.add_argument("--full", action="store_true", help="Incluye también las pruebas de los agentes CrewAI.")
    parser.add_argument("--crew", choices=("dry-run", "real"), help="Ejecuta además el runner CrewAI antes de servir.")
    parser.add_argument("--check-only", action="store_true", help="Ejecuta las etapas y no levanta el servidor.")
    parser.add_argument("--open", action="store_true", help="Abre el navegador al arrancar.")
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    sys.path.insert(0, str(ROOT))

    print("Wallet Perú - Grupo 3: etapas en el orden de los agentes")
    stages = [
        stage_product_owner(args.strict),
        stage_architect(),
        stage_ai_engineer(),
        stage_qa_security(args.skip_tests, args.full),
        stage_presenter(args.port),
    ]
    if args.crew:
        stages.append(run_crew(args.crew))
    for index, stage in enumerate(stages, start=1):
        print_stage(index, stage)

    if any(stage.status == FAIL for stage in stages):
        print("\nNo se levanta el servidor: hay etapas en FALLO.")
        return 1
    if args.check_only:
        print("\nVerificación terminada (--check-only): servidor no iniciado.")
        return 0

    import demo_server

    if args.open:
        threading.Timer(1.0, webbrowser.open, args=(f"http://127.0.0.1:{args.port}",)).start()
    print()
    demo_server.serve(args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
