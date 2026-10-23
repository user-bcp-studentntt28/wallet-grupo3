from __future__ import annotations

import contextlib
import io
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main as entrypoint


def run_main(argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = entrypoint.main(argv)
    return code, out.getvalue()


class MainEntrypointTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.missing_approval = Path(self._tmp.name) / "scope_approval.json"
        patcher = patch.object(entrypoint, "SCOPE_APPROVAL", self.missing_approval)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_stages_follow_the_defined_agent_order(self) -> None:
        code, output = run_main(["--check-only", "--skip-tests", "--port", "0"])
        self.assertEqual(code, 0)
        roles = ["Product Owner", "Arquitecto/a", "AI Engineer", "QA & Security", "Presenter / Timekeeper"]
        positions = [output.index(role) for role in roles]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("servidor no iniciado", output)

    def test_missing_human_approval_warns_and_never_fabricates_one(self) -> None:
        code, output = run_main(["--check-only", "--skip-tests", "--port", "0"])
        self.assertEqual(code, 0)
        self.assertIn("ADVERTENCIA", output)
        self.assertIn("MISSING", output)
        self.assertFalse(self.missing_approval.exists())

    def test_strict_blocks_without_human_approval(self) -> None:
        with patch("demo_server.serve") as serve:
            code, output = run_main(["--strict", "--skip-tests", "--port", "0"])
        self.assertEqual(code, 1)
        self.assertIn("No se levanta el servidor", output)
        serve.assert_not_called()

    def test_skipped_tests_are_reported_as_not_executed(self) -> None:
        _, output = run_main(["--check-only", "--skip-tests", "--port", "0"])
        self.assertIn("NO EJECUTADO", output)

    def test_busy_port_blocks_the_server(self) -> None:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            with patch("demo_server.serve") as serve:
                code, output = run_main(["--skip-tests", "--port", str(port)])
        self.assertEqual(code, 1)
        self.assertIn("ya está en uso", output)
        serve.assert_not_called()

    def test_server_starts_after_all_stages_pass(self) -> None:
        with patch("demo_server.serve") as serve:
            code, _ = run_main(["--skip-tests", "--port", "0"])
        self.assertEqual(code, 0)
        serve.assert_called_once_with(0)

    def test_architect_stage_fails_if_reset_is_not_denied(self) -> None:
        import demo_guardrails

        with patch.object(demo_guardrails, "classify", return_value=None):
            stage = entrypoint.stage_architect()
        self.assertEqual(stage.status, entrypoint.FAIL)


if __name__ == "__main__":
    unittest.main()
