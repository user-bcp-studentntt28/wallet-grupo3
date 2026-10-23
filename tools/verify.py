"""Check the current CrewAI agents offline, not the legacy LangGraph pipeline."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    print(f"Python: {sys.executable}", flush=True)
    if importlib.util.find_spec("crewai") is None:
        print(
            "Falta CrewAI en este entorno Python.\n"
            f'Instala las dependencias con:\n"{sys.executable}" -m pip install '
            f'-r "{ROOT / "requirements-hackaton.txt"}"',
            file=sys.stderr,
        )
        return 1

    env = {
        **os.environ,
        "CREWAI_TELEMETRY_OPT_OUT": "true",
        "CREWAI_TRACING_ENABLED": "false",
        "OTEL_SDK_DISABLED": "true",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_hackaton*.py",
            "-v",
        ],
        cwd=ROOT,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        print("Fallo la verificacion de CrewAI.", file=sys.stderr)
        return result.returncode
    print(
        "Checks de agentes CrewAI aprobados, sin llamadas externas: skills, gates "
        "humanos, runner en dry-run y MCP local (con el mock simulado). No valida "
        "el pipeline LangGraph, la web ni una ejecucion real con modelo."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
