from __future__ import annotations

import unittest
from unittest.mock import patch

import demo_guardrails as guardrails
import demo_server

# Operaciones declaradas en el OpenAPI del grupo 3 (v0.2.0).
OPENAPI_OPERATIONS = {
    ("GET", "/health"), ("GET", "/scenarios"), ("GET", "/openapi.json"),
    ("POST", "/kyc/verifications"), ("GET", "/kyc/verifications/{id}"),
    ("POST", "/kyc/verifications/{id}/decision"), ("GET", "/wallets/{id}"),
    ("POST", "/payments"), ("GET", "/payments"), ("GET", "/payments/{id}"),
    ("GET", "/payments/{id}/receipt"), ("GET", "/provider/payments/{id}"),
    ("GET", "/reversals/{id}"), ("POST", "/payments/{id}/resolve"),
    ("POST", "/payments/{id}/reversals"), ("POST", "/qrs"), ("POST", "/qrs/resolve"),
    ("POST", "/callbacks/payments"), ("GET", "/control/events"), ("GET", "/ledger"),
    ("GET", "/support/cases"), ("GET", "/settlements"), ("GET", "/reconciliations/incidents"),
    ("POST", "/control/events/{id}/deliver"), ("POST", "/control/provider/{id}/complete"),
    ("POST", "/control/settlements"), ("POST", "/reconciliations"), ("POST", "/control/reset"),
    ("GET", "/groups"), ("GET", "/usage"), ("GET", "/logs"), ("GET", "/usage/all"),
}


class FeatureMapTests(unittest.TestCase):
    def test_every_openapi_operation_is_classified_exactly_once(self) -> None:
        mapped = [(f.method, f.path) for f in guardrails.FEATURE_MAP]
        self.assertEqual(len(mapped), len(set(mapped)))
        self.assertEqual(set(mapped), OPENAPI_OPERATIONS)

    def test_every_feature_has_criteria_task_and_valid_policy(self) -> None:
        for feature in guardrails.FEATURE_MAP:
            with self.subTest(feature=feature.path):
                self.assertIn(
                    feature.policy, {guardrails.ALLOW, guardrails.CONFIRM, guardrails.DENY}
                )
                self.assertTrue(feature.criteria)
                self.assertTrue(feature.task)

    def test_mcp_read_only_tools_are_never_mutating(self) -> None:
        for feature in guardrails.FEATURE_MAP:
            if feature.mcp_read_only:
                self.assertEqual(feature.method, "GET")
                self.assertEqual(feature.policy, guardrails.ALLOW)


class RouteGuardrailTests(unittest.TestCase):
    def test_reset_and_reversals_are_always_denied(self) -> None:
        for method, path in (
            ("POST", "/control/reset"),
            ("POST", "/payments/pay-1/reversals"),
        ):
            for confirmed in (False, True):
                result = guardrails.check_mock_call(method, path, confirmed)
                self.assertFalse(result.allowed)
                self.assertEqual(result.rule_code, "DEMO-TOOL-02")

    def test_unmapped_operation_is_denied_by_default(self) -> None:
        for method, path in (("DELETE", "/payments/pay-1"), ("GET", "/admin"), ("PUT", "/qrs")):
            result = guardrails.check_mock_call(method, path, True)
            self.assertEqual(result.rule_code, "DEMO-TOOL-01")

    def test_confirmation_is_required_for_state_changing_operations(self) -> None:
        for method, path in (
            ("POST", "/payments"),
            ("POST", "/kyc/verifications/kyc-1/decision"),
            ("POST", "/control/settlements"),
        ):
            self.assertEqual(
                guardrails.check_mock_call(method, path).rule_code, "DEMO-TOOL-03"
            )
            self.assertTrue(guardrails.check_mock_call(method, path, True).allowed)

    def test_path_traversal_and_odd_ids_are_rejected(self) -> None:
        for path in ("/payments/..", "/wallets/a%2Fb", "/wallets/" + "a" * 101):
            result = guardrails.check_mock_call("GET", path)
            self.assertFalse(result.allowed, path)
            self.assertEqual(result.rule_code, "DEMO-IN-04")

    def test_read_routes_with_valid_ids_are_allowed(self) -> None:
        self.assertTrue(guardrails.check_mock_call("GET", "/wallets/wallet-demo").allowed)
        self.assertTrue(guardrails.check_mock_call("GET", "/openapi.json").allowed)


class InputAndOutputGuardrailTests(unittest.TestCase):
    def test_kyc_input_rules(self) -> None:
        valid = {"documentType": "TEST", "document": "TEST-001"}
        self.assertTrue(guardrails.check_kyc_input(valid).allowed)
        cases = {
            "DEMO-IN-01": [[], {**valid, "extra": 1}],
            "DEMO-IN-02": [
                {"documentType": "DNI", "document": "TEST-1"},
                {"documentType": "TEST", "document": "12345678"},
                {"documentType": "TEST", "document": "TEST-" + "x" * 200},
                {"documentType": "TEST", "document": 5},
            ],
            "DEMO-IN-03": [
                {"documentType": "TEST", "document": "TEST-4111111111111111"},
                {"documentType": "TEST", "document": "TEST-ghp_" + "a" * 24},
            ],
        }
        for code, payloads in cases.items():
            for payload in payloads:
                with self.subTest(code=code, payload=str(payload)[:30]):
                    self.assertEqual(guardrails.check_kyc_input(payload).rule_code, code)

    def test_output_guardrail_blocks_secrets_and_card_numbers(self) -> None:
        self.assertTrue(guardrails.check_mock_response(b'{"status":"ACTIVE"}').allowed)
        for body in (b'{"token":"ghp_' + b"a" * 24 + b'"}', b'{"card":"4111111111111111"}'):
            self.assertEqual(guardrails.check_mock_response(body).rule_code, "DEMO-OUT-01")


class ClientGuardrailIntegrationTests(unittest.TestCase):
    def test_client_blocks_denied_route_without_network_call(self) -> None:
        client = demo_server.MockApiClient()
        with patch("demo_server.urlopen") as upstream:
            response = client._request_json("POST", "/control/reset", {})
        self.assertEqual(response.status_code, 403)
        self.assertIn(b"DEMO-TOOL-02", response.body)
        upstream.assert_not_called()

    def test_client_blocks_unconfirmed_payment_without_network_call(self) -> None:
        client = demo_server.MockApiClient()
        with patch("demo_server.urlopen") as upstream:
            response = client._request_json("POST", "/payments", {"amountCents": 100})
        self.assertEqual(response.status_code, 403)
        self.assertIn(b"DEMO-TOOL-03", response.body)
        upstream.assert_not_called()

    def test_client_blocks_sensitive_upstream_response(self) -> None:
        class Leaky:
            status = 200
            headers = {"Content-Type": "application/json"}

            def __enter__(self) -> "Leaky":
                return self

            def __exit__(self, *_: object) -> None:
                return None

            def read(self, limit: int = -1) -> bytes:
                return b'{"secret":"ghp_' + b"a" * 24 + b'"}'

        with patch("demo_server.urlopen", return_value=Leaky()):
            response = demo_server.MockApiClient().get_scenarios()
        self.assertEqual(response.status_code, 502)
        self.assertIn(b"DEMO-OUT-01", response.body)
        self.assertNotIn(b"ghp_", response.body)


if __name__ == "__main__":
    unittest.main()
