"""Human approval gates: only a valid human record unblocks work (HA-02, HA-09)."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agents import gates

ROOT = Path(__file__).resolve().parents[1]
VERSION = "wallet-demo-grupo3@test"
DIGEST = "abc123"


def stamp(delta: timedelta = timedelta(minutes=-1)) -> str:
    return (datetime.now(timezone.utc) + delta).isoformat()


def scope_record(**overrides):
    record = {
        "scopeVersion": VERSION,
        "decision": "APPROVED",
        "approver": "Maria Quispe",
        "approverType": "HUMAN",
        "timestamp": stamp(timedelta(minutes=-10)),
    }
    return {**record, **overrides}


def final_record(**overrides):
    record = {
        **scope_record(timestamp=stamp()),
        "evidenceRefs": ["evidence/runs/x/report.json"],
        "unresolvedGaps": ["W3 deuda: POSTERIOR"],
        "reviewedDigest": DIGEST,
    }
    return {**record, **overrides}


class GateTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT / "evidence")
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def write(self, name, content):
        path = self.dir / name
        path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
        return path


class ScopeGateTests(GateTestCase):
    def test_valid_human_approval_passes(self):
        result = gates.check_scope_approval(self.write("s.json", scope_record()), VERSION)
        self.assertTrue(result.passed)
        self.assertEqual(result.code, "APPROVED")

    def test_missing_rejected_changed_or_unreadable_block(self):
        cases = {
            "MISSING": self.dir / "absent.json",
            "REJECTED": self.write("r.json", scope_record(decision="REJECTED")),
            "VERSION_MISMATCH": self.write("v.json", scope_record(scopeVersion="wallet-demo-grupo3@old")),
            "INVALID": self.write("bad.json", "{not json"),
        }
        for code, path in cases.items():
            with self.subTest(code=code):
                result = gates.check_scope_approval(path, VERSION)
                self.assertFalse(result.passed)
                self.assertEqual(result.code, code)

    def test_agent_or_role_cannot_be_the_approver(self):
        for approver, kind in (
            ("Product Owner", "HUMAN"),
            ("Product Owner Agent", "HUMAN"),
            ("CrewAI", "HUMAN"),
            ("gpt-6-luna", "HUMAN"),
            ("Maria Quispe", "AGENT"),
            ("Maria Quispe", "agent"),
        ):
            with self.subTest(approver=approver, kind=kind):
                path = self.write("a.json", scope_record(approver=approver, approverType=kind))
                result = gates.check_scope_approval(path, VERSION)
                self.assertFalse(result.passed)
                self.assertEqual(result.code, "AGENT_APPROVER")

    def test_malformed_fields_are_invalid(self):
        for overrides in (
            {"decision": "MAYBE"},
            {"timestamp": "ayer"},
            {"timestamp": "2026-10-23T10:00:00"},
            {"timestamp": stamp(timedelta(days=2))},
            {"approver": ""},
        ):
            with self.subTest(overrides=overrides):
                result = gates.check_scope_approval(self.write("m.json", scope_record(**overrides)), VERSION)
                self.assertFalse(result.passed)
                self.assertEqual(result.code, "INVALID")

    def test_scope_version_changes_with_content(self):
        first = self.write("one.md", "alcance A")
        second = self.write("two.md", "alcance B")
        before = gates.compute_scope_version([first])
        self.assertEqual(before, gates.compute_scope_version([first]))
        self.assertNotEqual(before, gates.compute_scope_version([second]))
        first.write_text("alcance A modificado", encoding="utf-8")
        self.assertNotEqual(before, gates.compute_scope_version([first]))


class FinalGateTests(GateTestCase):
    def check(self, record, digest=DIGEST, scope=None):
        return gates.check_final_approval(self.write("f.json", record), VERSION, digest, scope)

    def test_complete_human_decision_passes(self):
        result = self.check(final_record())
        self.assertTrue(result.passed)
        self.assertEqual(gates.decide_readiness(mode="real", deliverables_complete=True, final_gate=result), (True, "READY"))

    def test_missing_decision_is_not_ready(self):
        result = gates.check_final_approval(self.dir / "none.json", VERSION, DIGEST)
        self.assertEqual(
            gates.decide_readiness(mode="real", deliverables_complete=True, final_gate=result),
            (False, "AWAITING_FINAL_APPROVAL"),
        )

    def test_rejected_decision_is_not_ready(self):
        result = self.check(final_record(decision="REJECTED"))
        self.assertEqual(
            gates.decide_readiness(mode="real", deliverables_complete=True, final_gate=result),
            (False, "FINAL_REJECTED"),
        )

    def test_incomplete_record_or_stale_evidence_is_not_ready(self):
        for label, record, expected in (
            ("sin referencias", final_record(evidenceRefs=[]), "INVALID"),
            ("sin brechas", {k: v for k, v in final_record().items() if k != "unresolvedGaps"}, "INVALID"),
            ("otra version", final_record(scopeVersion="wallet-demo-grupo3@old"), "VERSION_MISMATCH"),
            ("otra entrega", final_record(reviewedDigest="otra"), "STALE_EVIDENCE"),
            ("agente", final_record(approver="QA & Security"), "AGENT_APPROVER"),
        ):
            with self.subTest(label):
                result = self.check(record)
                self.assertFalse(result.passed)
                self.assertEqual(result.code, expected)
                ready, status = gates.decide_readiness(mode="real", deliverables_complete=True, final_gate=result)
                self.assertFalse(ready)
                self.assertEqual(status, "FINAL_APPROVAL_INVALID")

    def test_final_cannot_precede_scope_approval(self):
        scope = scope_record(timestamp=stamp(timedelta(minutes=-1)))
        result = self.check(final_record(timestamp=stamp(timedelta(minutes=-30))), scope=scope)
        self.assertFalse(result.passed)

    def test_dry_run_or_incomplete_deliverables_are_never_ready(self):
        ok = gates.GateResult(True, "APPROVED", "ok")
        self.assertEqual(gates.decide_readiness(mode="dry-run", deliverables_complete=True, final_gate=ok), (False, "DRY_RUN_COMPLETE"))
        self.assertEqual(gates.decide_readiness(mode="real", deliverables_complete=False, final_gate=ok), (False, "BLOCKED_ROLE"))


if __name__ == "__main__":
    unittest.main()
