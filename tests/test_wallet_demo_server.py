from __future__ import annotations

import json
import re
import threading
import unittest
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen as client_urlopen
from unittest.mock import patch

import demo_server


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.body = body
        self.status = status
        self.headers = {"Content-Type": "application/json; charset=utf-8"}

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, limit: int = -1) -> bytes:
        return self.body if limit < 0 else self.body[:limit]


class WalletDemoServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = demo_server.DemoHTTPServer(
            ("127.0.0.1", 0), demo_server.DemoRequestHandler
        )
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def get(self, path: str) -> tuple[int, bytes]:
        with client_urlopen(f"{self.base_url}{path}") as response:
            return response.status, response.read()

    def post_json(self, path: str, payload: dict[str, object]) -> tuple[int, bytes]:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with client_urlopen(request) as response:
            return response.status, response.read()

    def test_home_page_has_three_sections_and_browser_uses_local_backend(self) -> None:
        status, page = self.get("/")
        self.assertEqual(status, 200)
        html = page.decode("utf-8")
        self.assertIn('id="panel-registro"', html)
        self.assertIn('id="panel-pagos"', html)
        self.assertIn('id="panel-operaciones"', html)

        _, script = self.get("/app.js")
        script_text = script.decode("utf-8")
        self.assertIn('requestJson("/api/scenarios"', script_text)
        self.assertNotIn(demo_server.MOCK_API_BASE_URL, script_text)

    def test_health_is_local_and_identifies_group_three(self) -> None:
        status, body = self.get("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"status": "ok", "group": "3"})

    def test_evidence_export_contains_only_local_nonfinancial_references(self) -> None:
        self.server.evidence.record(
            "PAYMENT_REFERENCE",
            wallet_id="wallet-demo",
            qr_id="qr-demo",
            payment_id="payment-demo",
        )

        status, body = self.get("/api/evidence/export")
        self.assertEqual(status, 200)
        exported = json.loads(body)
        self.assertEqual(exported["scope"], "non-financial-demo-evidence")
        event = next(
            item
            for item in exported["events"]
            if item.get("paymentId") == "payment-demo"
        )
        self.assertEqual(event["walletId"], "wallet-demo")
        self.assertEqual(event["qrId"], "qr-demo")
        self.assertRegex(event["correlationId"], r"^[a-f0-9]{32}$")
        captured_at = datetime.fromisoformat(event["capturedAtLocal"])
        self.assertIsNotNone(captured_at.utcoffset())
        self.assertEqual(
            set(event),
            {
                "eventType",
                "correlationId",
                "capturedAtLocal",
                "walletId",
                "qrId",
                "paymentId",
            },
        )
        serialized = json.dumps(event)
        for forbidden in ("document", "Authorization", "Bearer", "amount", "balance", "status"):
            self.assertNotIn(forbidden, serialized)

    def test_scenarios_call_fixed_group_three_endpoint(self) -> None:
        with patch(
            "demo_server.urlopen",
            return_value=FakeResponse(b'{"scenarios":[{"name":"demo"}]}'),
        ) as upstream:
            status, body = self.get("/api/scenarios")

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["scenarios"][0]["name"], "demo")
        request = upstream.call_args.args[0]
        self.assertEqual(
            request.full_url, f"{demo_server.MOCK_API_BASE_URL}/scenarios"
        )
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("User-agent"), "WalletDemo/1.0")

    def test_kyc_rejects_non_test_identity_without_calling_mock(self) -> None:
        with patch("demo_server.urlopen") as upstream:
            with self.assertRaises(HTTPError) as raised:
                self.post_json(
                    "/api/kyc",
                    {"documentType": "DNI", "document": "12345678"},
                )

        self.assertEqual(raised.exception.code, 400)
        body = json.loads(raised.exception.read())
        self.assertEqual(body["error"], "GUARDRAIL_BLOCKED")
        self.assertEqual(body["ruleCode"], "DEMO-IN-02")
        upstream.assert_not_called()

    def test_guardrail_map_endpoint_publishes_all_operations(self) -> None:
        status, body = self.get("/api/guardrails")
        self.assertEqual(status, 200)
        features = json.loads(body)["features"]
        self.assertEqual(len(features), 32)
        self.assertEqual({f["policy"] for f in features}, {"ALLOW", "CONFIRM", "DENY"})

    def test_kyc_sends_only_supported_test_fields_to_fixed_route(self) -> None:
        result = {
            "id": "kyc-demo",
            "wallet_id": "wallet-demo",
            "scenario": "APPROVED",
            "status": "ACTIVE",
        }
        with patch(
            "demo_server.urlopen",
            return_value=FakeResponse(json.dumps(result).encode(), status=201),
        ) as upstream:
            status, body = self.post_json(
                "/api/kyc",
                {
                    "documentType": "TEST",
                    "document": "TEST-DEMO-001",
                    "scenario": "APPROVED",
                },
            )

        self.assertEqual(status, 201)
        self.assertEqual(json.loads(body), result)
        request = upstream.call_args.args[0]
        self.assertEqual(
            request.full_url, f"{demo_server.MOCK_API_BASE_URL}/kyc/verifications"
        )
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            json.loads(request.data),
            {
                "documentType": "TEST",
                "document": "TEST-DEMO-001",
                "scenario": "APPROVED",
            },
        )
        self.assertNotIn(
            "TEST-DEMO-001",
            json.dumps(self.server.evidence.export()),
        )

    def test_kyc_preserves_rejected_and_manual_review_statuses(self) -> None:
        for scenario, expected_status in (
            ("REJECTED", "REJECTED"),
            ("MANUAL_REVIEW", "PENDING"),
        ):
            with self.subTest(scenario=scenario):
                result = {
                    "id": f"kyc-{scenario.lower()}",
                    "wallet_id": f"wallet-{scenario.lower()}",
                    "scenario": scenario,
                    "status": expected_status,
                }
                with patch(
                    "demo_server.urlopen",
                    return_value=FakeResponse(
                        json.dumps(result).encode("utf-8"), status=201
                    ),
                ):
                    status, body = self.post_json(
                        "/api/kyc",
                        {
                            "documentType": "TEST",
                            "document": "TEST-STATUS-CHECK",
                            "scenario": scenario,
                        },
                    )

                self.assertEqual(status, 201)
                self.assertEqual(json.loads(body)["status"], expected_status)

    def test_kyc_unavailable_status_is_preserved(self) -> None:
        with patch(
            "demo_server.urlopen",
            return_value=FakeResponse(
                b'{"error":"KYC_UNAVAILABLE"}', status=503
            ),
        ):
            with self.assertRaises(HTTPError) as raised:
                self.post_json(
                    "/api/kyc",
                    {
                        "documentType": "TEST",
                        "document": "TEST-DEMO-002",
                        "scenario": "UNAVAILABLE",
                    },
                )

        self.assertEqual(raised.exception.code, 503)
        self.assertEqual(
            json.loads(raised.exception.read()), {"error": "KYC_UNAVAILABLE"}
        )

    def test_kyc_ui_labels_simulation_and_validates_before_fetch(self) -> None:
        _, page = self.get("/")
        page_text = page.decode("utf-8")
        self.assertIn("no es una verificación de identidad real", page_text.lower())
        self.assertIn("UNAVAILABLE", page_text)

        _, script = self.get("/app.js")
        script_text = script.decode("utf-8")
        validation_index = script_text.index('documentValue.startsWith("TEST-")')
        submit_index = script_text.index('requestJson("/api/kyc"')
        self.assertLess(validation_index, submit_index)
        self.assertIn("result.status", script_text)

    def test_upstream_error_status_is_not_converted_to_success(self) -> None:
        with patch(
            "demo_server.urlopen",
            return_value=FakeResponse(
                b'{"error":"PROVIDER_ERROR"}', status=503
            ),
        ):
            with self.assertRaises(HTTPError) as raised:
                self.get("/api/scenarios")

        self.assertEqual(raised.exception.code, 503)
        self.assertEqual(json.loads(raised.exception.read()), {"error": "PROVIDER_ERROR"})

    def test_network_failure_is_reported_as_gateway_error(self) -> None:
        with patch(
            "demo_server.urlopen", side_effect=URLError("connection refused")
        ):
            with self.assertRaises(HTTPError) as raised:
                self.get("/api/scenarios")

        self.assertEqual(raised.exception.code, 502)
        self.assertEqual(
            json.loads(raised.exception.read())["error"], "MOCK_UNAVAILABLE"
        )

    def test_arbitrary_upstream_destination_is_not_a_supported_route(self) -> None:
        with patch("demo_server.urlopen") as upstream:
            with self.assertRaises(HTTPError) as raised:
                self.get("/api/proxy?url=https://attacker.invalid")

        self.assertEqual(raised.exception.code, 404)
        upstream.assert_not_called()

    def test_ui_only_calls_local_backend_and_never_reset_or_reversal_writes(self) -> None:
        _, script = self.get("/app.js")
        text = script.decode("utf-8")
        self.assertNotIn("workers.dev", text)
        self.assertNotIn("/control/reset", text)
        self.assertNotIn("reversals\", \"POST\"", text)
        for path in ("/api/payments", "/api/qrs", "/api/reconciliations", "/api/control/settlements"):
            self.assertIn(path, text)
        self.assertIn('payload.replace(/^qrmock:/, "")', text)
        _, page = self.get("/")
        html = page.decode("utf-8")
        for element in ("pay-confirm", "fac-confirm", "alt-confirm", "kyc-decision-confirm"):
            self.assertIn(f'id="{element}"', html)

    def test_qr_image_library_is_served_locally(self) -> None:
        status, body = self.get("/vendor/qrcode.js")
        self.assertEqual(status, 200)
        self.assertIn(b"QR Code Generator for JavaScript", body)
        self.assertIn(b"MIT license", body)
        _, page = self.get("/")
        self.assertIn(b'src="/vendor/qrcode.js"', page)

    def test_login_gate_validates_before_any_request_and_never_stores_the_password(self) -> None:
        _, page = self.get("/")
        html = page.decode("utf-8")
        self.assertIn('id="login-form"', html)
        self.assertIn('type="password"', html)
        self.assertIn('<main id="app-main" hidden>', html)
        _, script = self.get("/app.js")
        text = script.decode("utf-8")
        gate = text.index('!doc.startsWith("TEST-")')
        digits = text.index("/^\\d{6}$/.test(password)")
        request = text.index('"/api/auth/register" : "/api/auth/login"')
        self.assertLess(gate, request)
        self.assertLess(digits, request)
        self.assertNotIn("localStorage.setItem(\"walletDemoUsers\"", text)
        self.assertNotIn("sessionStorage.setItem(USER_SESSION_KEY, password", text)
        self.assertNotEqual(
            re.search(r'USER_SESSION_KEY = "([^"]+)"', text).group(1),
            re.search(r'getItem\("(walletDemoSession)"\)', text).group(1),
        )

    def test_post_is_rejected_until_a_backend_action_is_implemented(self) -> None:
        with self.assertRaises(HTTPError) as raised:
            client_urlopen(
                f"{self.base_url}/api/scenarios",
                data=b"{}",
                timeout=2,
            )

        self.assertEqual(raised.exception.code, 405)


if __name__ == "__main__":
    unittest.main()
