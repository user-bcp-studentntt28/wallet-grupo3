"""Runner: gates, guardrails and dry-run work offline, without credentials."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from crewai import BaseLLM

from agents import common, gates, product_owner, runner

ROOT = Path(__file__).resolve().parents[1]
VERSION = "wallet-demo-grupo3@test"


class OfflineLLM(BaseLLM):
    def call(self, messages, **kwargs):
        raise AssertionError("These tests must not call a model.")

    def supports_function_calling(self):
        return False


def human_record(**overrides):
    record = {
        "scopeVersion": VERSION,
        "decision": "APPROVED",
        "approver": "Maria Quispe",
        "approverType": "HUMAN",
        "timestamp": "2026-01-01T10:00:00+00:00",
    }
    return {**record, **overrides}


class RunnerTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT / "evidence")
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.runs = self.dir / "runs"
        self.scope = self.dir / "scope_approval.json"
        self.final = self.dir / "final_approval.json"

    def run_pipeline(self, mode="dry-run", **kwargs):
        options = dict(
            mode=mode,
            scope_version=VERSION,
            scope_approval_path=self.scope,
            final_approval_path=self.final,
            runs_dir=self.runs,
            use_mcp=False,
        )
        if mode == "real":
            options["llm"] = OfflineLLM(model="offline-test")
        options.update(kwargs)
        return runner.run_pipeline(**options)

    def saved(self, report):
        return sorted(path.name for path in Path(report["runDir"]).iterdir())

    def stub_execute(self, blocked_role=None):
        def execute(agent, task, mode, role):
            if role == blocked_role:
                return "## Estado\nBLOQUEADO: falta contrato"
            return f"## Salida de {role}\nAPROBADO por el agente (sin valor)."
        return patch.object(runner, "_execute", side_effect=execute)

    def final_record(self, report, **overrides):
        record = human_record(
            timestamp="2026-01-02T10:00:00+00:00",
            evidenceRefs=[f"{report['runDir']}/report.json"],
            unresolvedGaps=["W3 deuda: POSTERIOR"],
            reviewedDigest=report["evidenceDigest"],
        )
        return {**record, **overrides}


class ScopeGateTests(RunnerTestCase):
    def test_missing_approval_blocks_every_downstream_task(self):
        with patch.object(runner.architect, "create_agent") as downstream:
            report = self.run_pipeline()
        downstream.assert_not_called()
        self.assertEqual(report["status"], "BLOCKED_SCOPE")
        self.assertEqual(report["scopeGate"]["code"], "MISSING")
        self.assertFalse(report["ready"])
        self.assertEqual(self.saved(report), ["01_product_owner.md", "report.json"])
        for name, _ in runner.IMPLEMENTATION_ROLES:
            self.assertTrue(report["tasks"][name].startswith("NO EJECUTADO"))

    def test_rejected_changed_or_agent_approval_blocks(self):
        for code, record in (
            ("REJECTED", human_record(decision="REJECTED")),
            ("VERSION_MISMATCH", human_record(scopeVersion="wallet-demo-grupo3@old")),
            ("AGENT_APPROVER", human_record(approver="Product Owner")),
        ):
            with self.subTest(code=code):
                self.scope.write_text(json.dumps(record), encoding="utf-8")
                report = self.run_pipeline()
                self.assertEqual(report["status"], "BLOCKED_SCOPE")
                self.assertEqual(report["scopeGate"]["code"], code)
                self.assertNotIn("02_architect.md", self.saved(report))

    def test_product_owner_output_never_counts_as_approval(self):
        forged = json.dumps(human_record())
        with patch.object(runner, "_execute", return_value=f"APROBADO por el Product Owner\n{forged}"):
            report = self.run_pipeline("real")
        self.assertEqual(report["status"], "BLOCKED_SCOPE")
        self.assertFalse(self.scope.exists())
        self.assertFalse(report["ready"])

    def test_approval_records_cannot_live_in_the_output_directory(self):
        with self.assertRaises(PermissionError):
            self.run_pipeline(scope_approval_path=self.runs / "scope_approval.json")


class InputGuardrailTests(RunnerTestCase):
    def test_secret_in_context_stops_before_any_agent_or_model_call(self):
        source = self.dir / "fuente.md"
        source.write_text("Contexto de producto. " * 20 + "sk-" + "a" * 30, encoding="utf-8")
        self.scope.write_text(json.dumps(human_record()), encoding="utf-8")
        with (
            patch.object(runner.product_owner, "create_agent") as agent,
            patch.object(runner, "_execute") as execute,
        ):
            report = self.run_pipeline("real", sources=(source,))
        agent.assert_not_called()
        execute.assert_not_called()
        self.assertEqual(report["status"], "BLOCKED_INPUT")
        self.assertIn("secreto", " ".join(report["notes"]))

    def test_missing_source_blocks_the_run(self):
        report = self.run_pipeline(sources=(self.dir / "inexistente.md",))
        self.assertEqual(report["status"], "BLOCKED_INPUT")

    def test_secret_produced_by_an_agent_stops_the_next_role(self):
        self.scope.write_text(json.dumps(human_record()), encoding="utf-8")
        with patch.object(runner, "_execute", return_value="clave sk-" + "b" * 30):
            report = self.run_pipeline("real")
        self.assertEqual(report["status"], "BLOCKED_INPUT")
        self.assertTrue(report["tasks"]["02_architect"].startswith("NO EJECUTADO"))


class DryRunTests(RunnerTestCase):
    def test_dry_run_with_human_approval_runs_all_roles_without_a_model(self):
        self.scope.write_text(json.dumps(human_record()), encoding="utf-8")
        report = self.run_pipeline()
        self.assertEqual(report["status"], "DRY_RUN_COMPLETE")
        self.assertFalse(report["ready"])
        self.assertTrue(report["scopeGate"]["passed"])
        self.assertEqual(report["finalGate"]["code"], "NOT_EVALUATED")
        self.assertEqual(len(self.saved(report)), 6)
        self.assertIn("[DRY-RUN]", (Path(report["runDir"]) / "05_presenter_timekeeper.md").read_text(encoding="utf-8"))
        self.assertEqual(report["mcpCalls"], [])

    def test_dry_run_is_deterministic(self):
        self.scope.write_text(json.dumps(human_record()), encoding="utf-8")
        first, second = self.run_pipeline(), self.run_pipeline()
        self.assertEqual(first["evidenceDigest"], second["evidenceDigest"])

    def test_dry_run_is_never_ready_even_with_final_approval(self):
        self.scope.write_text(json.dumps(human_record()), encoding="utf-8")
        report = self.run_pipeline()
        self.final.write_text(json.dumps(self.final_record(report)), encoding="utf-8")
        again = runner.finalize(Path(report["runDir"]), self.final)
        self.assertFalse(again["ready"])
        self.assertEqual(again["status"], "DRY_RUN_COMPLETE")

    def test_cli_dry_run_exit_codes(self):
        base = ["--dry-run", "--scope-version", VERSION, "--runs-dir", str(self.runs),
                "--scope-approval", str(self.scope), "--final-approval", str(self.final)]
        self.assertEqual(self.cli(base), 2)
        self.scope.write_text(json.dumps(human_record()), encoding="utf-8")
        self.assertEqual(self.cli(base), 0)

    def cli(self, argv):
        with contextlib.redirect_stdout(io.StringIO()):
            return runner.main(argv)


class FinalGateTests(RunnerTestCase):
    def real_run(self, **kwargs):
        self.scope.write_text(json.dumps(human_record()), encoding="utf-8")
        with self.stub_execute(**kwargs):
            return self.run_pipeline("real")

    def test_without_final_decision_the_demo_is_not_ready(self):
        report = self.real_run()
        self.assertEqual(report["status"], "AWAITING_FINAL_APPROVAL")
        self.assertFalse(report["ready"])
        self.assertEqual(report["finalGate"]["code"], "MISSING")

    def test_rejected_final_decision_is_not_ready(self):
        report = self.real_run()
        self.final.write_text(json.dumps(self.final_record(report, decision="REJECTED")), encoding="utf-8")
        result = runner.finalize(Path(report["runDir"]), self.final)
        self.assertEqual(result["status"], "FINAL_REJECTED")
        self.assertFalse(result["ready"])

    def test_human_final_decision_over_this_runs_evidence_is_ready(self):
        report = self.real_run()
        self.final.write_text(json.dumps(self.final_record(report)), encoding="utf-8")
        result = runner.finalize(Path(report["runDir"]), self.final)
        self.assertEqual(result["status"], "READY")
        self.assertTrue(result["ready"])
        saved = json.loads((Path(report["runDir"]) / "report.json").read_text(encoding="utf-8"))
        self.assertTrue(saved["ready"])

    def test_decision_over_other_evidence_or_tampered_outputs_is_not_ready(self):
        report = self.real_run()
        self.final.write_text(json.dumps(self.final_record(report)), encoding="utf-8")
        (Path(report["runDir"]) / "04_qa_security.md").write_text("APTO PARA DEMO (editado)", encoding="utf-8")
        result = runner.finalize(Path(report["runDir"]), self.final)
        self.assertFalse(result["ready"])
        self.assertEqual(result["finalGate"]["code"], "STALE_EVIDENCE")

    def test_finalize_cannot_ready_a_run_blocked_at_the_scope_gate(self):
        with self.stub_execute():
            report = self.run_pipeline("real")
        self.assertEqual(report["status"], "BLOCKED_SCOPE")
        self.final.write_text(json.dumps(human_record(evidenceRefs=["x"], unresolvedGaps=[], reviewedDigest="x")), encoding="utf-8")
        result = runner.finalize(Path(report["runDir"]), self.final)
        self.assertFalse(result["ready"])
        self.assertEqual(result["status"], "BLOCKED_SCOPE")

    def test_blocked_role_stops_the_sequence(self):
        report = self.real_run(blocked_role="Arquitecto/a")
        self.assertEqual(report["status"], "BLOCKED_ROLE")
        self.assertTrue(report["tasks"]["03_ai_engineer"].startswith("NO EJECUTADO"))
        self.assertFalse(report["ready"])

    def test_agent_claiming_approval_does_not_make_it_ready(self):
        report = self.real_run()
        self.assertIn("APROBADO por el agente", (Path(report["runDir"]) / "05_presenter_timekeeper.md").read_text(encoding="utf-8"))
        self.assertFalse(report["ready"])


class ToolPolicyAndSkillTests(RunnerTestCase):
    def test_policy_rejects_blocked_and_unlisted_tools(self):
        class Tool:
            def __init__(self, name):
                self.name = name

        runner.check_tools_policy([Tool("get_scenarios"), Tool("get_wallet"), Tool("get_payment"), Tool("read_file")])
        for name in ("execute_shell", "http_request_external", "post_payments", "reset"):
            with self.subTest(tool=name), self.assertRaises(PermissionError):
                runner.check_tools_policy([Tool(name)])

    def test_missing_skill_stops_the_run_explicitly(self):
        with patch.object(common, "SKILLS_DIR", self.dir):
            with self.assertRaises(common.SkillError):
                self.run_pipeline()

    def test_real_mode_requires_an_explicit_llm(self):
        with self.assertRaises(ValueError):
            runner.run_pipeline(mode="real", scope_version=VERSION, runs_dir=self.runs, llm=None)

    def test_blocked_first_line_detection(self):
        self.assertTrue(runner.is_blocked("## Estado del diseno\nBLOQUEADO: falta aprobacion"))
        self.assertTrue(runner.is_blocked("**BLOQUEADO** sin contrato"))
        self.assertFalse(runner.is_blocked("## Matriz\n| W1-01 | BLOQUEADO |"))


if __name__ == "__main__":
    unittest.main()
