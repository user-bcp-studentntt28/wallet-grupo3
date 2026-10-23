"""Role skills are real files loaded into every CrewAI agent (HA-08)."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from crewai import BaseLLM

from agents import (
    ai_engineer,
    architect,
    common,
    presenter_timekeeper,
    product_owner,
    qa_security,
)

ROOT = Path(__file__).resolve().parents[1]
ROLES = {
    "product_owner": product_owner,
    "architect": architect,
    "ai_engineer": ai_engineer,
    "qa_security": qa_security,
    "presenter_timekeeper": presenter_timekeeper,
}
BOUNDARY_MARKERS = (
    "## Fuentes propias del rol",
    "## Responsabilidades",
    "## Entregable",
    "## Límites de la demo",
    "documento_deuda_id",
    "autoridad financiera",
    "DEMO-TOOL",
)


class OfflineLLM(BaseLLM):
    def call(self, messages, **kwargs):
        raise AssertionError("These tests must not call a model.")

    def supports_function_calling(self):
        return False


class SkillFileTests(unittest.TestCase):
    def test_one_non_empty_skill_per_role_with_required_sections(self):
        self.assertEqual(set(common.SKILL_NAMES), set(ROLES))
        for name in ROLES:
            with self.subTest(skill=name):
                text = common.load_skill(name)
                for marker in BOUNDARY_MARKERS:
                    self.assertIn(marker, text)
                self.assertIn("REVERSED", text)

    def test_role_specific_rules(self):
        po = common.load_skill("product_owner")
        self.assertIn("NO puedes aprobar tu propia propuesta", po)
        self.assertIn("PENDIENTE DE APROBACION HUMANA", po)
        qa = common.load_skill("qa_security")
        for label in ("APROBADO", "FALLIDO", "NO EJECUTADO", "BLOQUEADO"):
            self.assertIn(label, qa)
        for name in ROLES:
            self.assertIn("HA-", common.load_skill(name))
        self.assertIn("W1-W6", po)

    def test_skills_are_distinct(self):
        texts = {common.load_skill(name) for name in ROLES}
        self.assertEqual(len(texts), len(ROLES))


class SkillLoadingTests(unittest.TestCase):
    def setUp(self):
        self.llm = OfflineLLM(model="offline-test")

    def test_each_backstory_contains_its_own_skill_and_aligned_rules(self):
        for name, module in ROLES.items():
            with self.subTest(role=name):
                agent = module.create_agent(self.llm)
                self.assertIn(common.load_skill(name), agent.backstory)
                for other in ROLES:
                    if other != name:
                        self.assertNotIn(common.load_skill(other), agent.backstory)
                for fragment in (
                    "PENDING",
                    "SUCCEEDED",
                    "REJECTED",
                    "REVERSED",
                    "410",
                    "QR_EXPIRED",
                    "503",
                    "PROVIDER_ERROR",
                    "504",
                    "TIMEOUT_AFTER_PROCESSING",
                    "documento_deuda_id",
                ):
                    self.assertIn(fragment, agent.backstory)

    def test_missing_unreadable_or_empty_skill_fails_explicitly(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "evidence") as tmp:
            skills = Path(tmp)
            with patch.object(common, "SKILLS_DIR", skills):
                for module in ROLES.values():
                    with self.assertRaises(common.SkillError):
                        module.create_agent(self.llm)
                (skills / "product_owner.md").write_text("  \n", encoding="utf-8")
                with self.assertRaises(common.SkillError):
                    product_owner.create_agent(self.llm)
                (skills / "architect.md").write_bytes(b"\xff\xfe\x00\xff")
                with self.assertRaises(common.SkillError):
                    architect.create_agent(self.llm)
                (skills / "ai_engineer.md").mkdir()
                with self.assertRaises(common.SkillError):
                    ai_engineer.create_agent(self.llm)

    def test_unknown_skill_name_is_rejected(self):
        with self.assertRaises(common.SkillError):
            common.load_skill("../common")

    def test_role_instructions_do_not_ask_for_reversals(self):
        for module in ROLES.values():
            text = module.INSTRUCTIONS.lower()
            self.assertNotIn("falla/reverso", text)
            self.assertNotIn("reverso repetido", text)


if __name__ == "__main__":
    unittest.main()
