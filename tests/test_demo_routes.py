from __future__ import annotations

import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen as client_urlopen
from unittest.mock import patch

import demo_server


class Fake:
    def __init__(self, payload: object, status: int = 200) -> None:
        self.body = json.dumps(payload).encode("utf-8")
        self.status = status
        self.headers = {"Content-Type": "application/json"}

    def __enter__(self) -> "Fake":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, limit: int = -1) -> bytes:
        return self.body if limit < 0 else self.body[:limit]


class RoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = demo_server.DemoHTTPServer(("127.0.0.1", 0), demo_server.DemoRequestHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def call(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        data = json.dumps(body).encode() if body is not None else None
        request = Request(f"{self.base}{path}", data=data, method=method,
                          headers={"Content-Type": "application/json"})
        try:
            with client_urlopen(request) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    payment = {
        "walletId": "wallet-demo", "recipient": "merchant-demo", "amountCents": 1500,
        "qrId": "qr-1", "idempotencyKey": "key-1", "confirmed": True,
    }

    def test_payment_sends_exact_supported_fields_and_idempotency_header(self) -> None:
        with patch("demo_server.urlopen", return_value=Fake({"id": "pay-1", "status": "PENDING"}, 202)) as up:
            status, body = self.call("POST", "/api/payments", self.payment)
        self.assertEqual((status, body["status"]), (202, "PENDING"))
        request = up.call_args.args[0]
        self.assertEqual(request.get_header("Idempotency-key"), "key-1")
        sent = json.loads(request.data)
        self.assertEqual(sent, {"walletId": "wallet-demo", "recipient": "merchant-demo",
                                "amountCents": 1500, "currency": "PEN", "qrId": "qr-1"})
        self.assertNotIn("documento_deuda_id", sent)
        self.assertNotIn("confirmed", sent)

    def test_payment_without_confirmation_never_reaches_mock(self) -> None:
        with patch("demo_server.urlopen") as up:
            status, body = self.call("POST", "/api/payments", {**self.payment, "confirmed": False})
        self.assertEqual((status, body["ruleCode"]), (403, "DEMO-TOOL-03"))
        up.assert_not_called()

    def test_payment_input_validation(self) -> None:
        bad = [
            {**self.payment, "idempotencyKey": ""},
            {**self.payment, "amountCents": 0},
            {**self.payment, "amountCents": 15.5},
            {**self.payment, "amountCents": True},
            {**self.payment, "recipient": "attacker"},
            {**self.payment, "scenario": "HACK"},
            {**self.payment, "documento_deuda_id": "D-1"},
            {**self.payment, "walletId": "../x"},
        ]
        with patch("demo_server.urlopen") as up:
            for payload in bad:
                with self.subTest(payload=payload):
                    status, body = self.call("POST", "/api/payments", payload)
                    self.assertEqual(status, 400)
                    self.assertEqual(body["error"], "GUARDRAIL_BLOCKED")
        up.assert_not_called()

    def test_idempotency_conflict_and_timeout_are_preserved(self) -> None:
        with patch("demo_server.urlopen", return_value=Fake({"error": "IDEMPOTENCY_CONFLICT"}, 409)):
            status, body = self.call("POST", "/api/payments", self.payment)
        self.assertEqual((status, body["error"]), (409, "IDEMPOTENCY_CONFLICT"))
        timeout = {"error": "TIMEOUT_AFTER_PROCESSING", "paymentId": "pay-9", "processed": True}
        with patch("demo_server.urlopen", return_value=Fake(timeout, 504)):
            status, body = self.call("POST", "/api/payments", self.payment)
        self.assertEqual((status, body["paymentId"]), (504, "pay-9"))
        export = json.dumps(self.server.evidence.export())
        self.assertIn("pay-9", export)

    def test_provider_error_is_not_converted_to_success(self) -> None:
        with patch("demo_server.urlopen", return_value=Fake({"error": "PROVIDER_ERROR"}, 503)):
            status, body = self.call("POST", "/api/payments", self.payment)
        self.assertEqual((status, body["error"]), (503, "PROVIDER_ERROR"))

    def test_qr_create_and_resolve(self) -> None:
        with patch("demo_server.urlopen", return_value=Fake({"id": "qr-7", "payload": "qrmock:qr-7"}, 201)) as up:
            status, _ = self.call("POST", "/api/qrs", {"amountCents": 2500})
        self.assertEqual(status, 201)
        self.assertEqual(json.loads(up.call_args.args[0].data),
                         {"merchantId": "merchant-demo", "amountCents": 2500})
        with patch("demo_server.urlopen", return_value=Fake({"error": "QR_EXPIRED"}, 410)):
            status, body = self.call("POST", "/api/qrs/resolve", {"payload": "qrmock:qr-7"})
        self.assertEqual((status, body["error"]), (410, "QR_EXPIRED"))
        status, body = self.call("POST", "/api/qrs/resolve", {"payload": "http://evil"})
        self.assertEqual(status, 400)

    def test_reversal_reset_and_unknown_routes_are_not_exposed(self) -> None:
        with patch("demo_server.urlopen") as up:
            for path in ("/api/payments/pay-1/reversals", "/api/control/reset", "/api/usage"):
                self.assertEqual(self.call("POST", path, {})[0], 405, path)
            self.assertEqual(self.call("GET", "/api/usage")[0], 404)
        up.assert_not_called()

    def test_settlement_alteration_needs_confirmation_and_limited_modes(self) -> None:
        body = {"paymentId": "pay-1", "mode": "AMOUNT", "amountCents": 100}
        with patch("demo_server.urlopen") as up:
            self.assertEqual(self.call("POST", "/api/control/settlements", body)[1]["ruleCode"], "DEMO-TOOL-03")
            self.assertEqual(self.call("POST", "/api/control/settlements",
                                       {**body, "mode": "MISSING", "confirmed": True})[0], 400)
            self.assertEqual(self.call("POST", "/api/control/settlements",
                                       {"paymentId": "pay-1", "mode": "AMOUNT", "confirmed": True})[0], 400)
        up.assert_not_called()
        with patch("demo_server.urlopen", return_value=Fake({"configured": True})) as up:
            self.assertEqual(self.call("POST", "/api/control/settlements", {**body, "confirmed": True})[0], 200)
        self.assertEqual(json.loads(up.call_args.args[0].data), body)

    def test_get_routes_use_fixed_mock_paths(self) -> None:
        cases = {
            "/api/wallets/wallet-demo": "/wallets/wallet-demo",
            "/api/payments/pay-1": "/payments/pay-1",
            "/api/payments/pay-1/receipt": "/payments/pay-1/receipt",
            "/api/support/cases": "/support/cases",
            "/api/ledger": "/ledger",
            "/api/settlements": "/settlements",
            "/api/incidents": "/reconciliations/incidents",
            "/api/reversals/rev-1": "/reversals/rev-1",
        }
        for local, remote in cases.items():
            with self.subTest(local=local), patch("demo_server.urlopen", return_value=Fake({"ok": 1})) as up:
                self.assertEqual(self.call("GET", local)[0], 200)
                request = up.call_args.args[0]
                self.assertEqual(request.full_url, f"{demo_server.MOCK_API_BASE_URL}{remote}")
                self.assertEqual(request.get_method(), "GET")

    def test_history_passes_validated_wallet_and_rejects_traversal(self) -> None:
        with patch("demo_server.urlopen", return_value=Fake([])) as up:
            self.assertEqual(self.call("GET", "/api/payments?walletId=wallet-demo")[0], 200)
            self.assertTrue(up.call_args.args[0].full_url.endswith("/payments?walletId=wallet-demo"))
            self.assertEqual(self.call("GET", "/api/payments?walletId=a%2Fb")[0], 400)
            self.assertEqual(self.call("GET", "/api/wallets/..")[0], 403)

    def test_kyc_decision_requires_human_confirmation(self) -> None:
        with patch("demo_server.urlopen") as up:
            status, body = self.call("POST", "/api/kyc/kyc-1/decision", {"decision": "ACTIVE"})
            self.assertEqual((status, body["ruleCode"]), (403, "DEMO-TOOL-03"))
            self.assertEqual(self.call("POST", "/api/kyc/kyc-1/decision",
                                       {"decision": "MAYBE", "confirmed": True})[0], 400)
        up.assert_not_called()
        with patch("demo_server.urlopen", return_value=Fake({"status": "ACTIVE"})) as up:
            self.assertEqual(self.call("POST", "/api/kyc/kyc-1/decision",
                                       {"decision": "ACTIVE", "confirmed": True})[0], 200)
        self.assertEqual(json.loads(up.call_args.args[0].data), {"decision": "ACTIVE"})

    def test_resolve_callback_and_reconciliation_routes(self) -> None:
        with patch("demo_server.urlopen", return_value=Fake({"id": "pay-1", "status": "SUCCEEDED"})) as up:
            self.assertEqual(self.call("POST", "/api/payments/pay-1/resolve", {"confirmed": True})[0], 200)
            self.assertTrue(up.call_args.args[0].full_url.endswith("/payments/pay-1/resolve"))
            self.assertEqual(self.call("POST", "/api/payments/pay-1/resolve", {})[0], 403)
        with patch("demo_server.urlopen", return_value=Fake({"duplicate": True})) as up:
            self.assertEqual(self.call("POST", "/api/callbacks", {"eventId": "evt-1", "confirmed": True})[0], 200)
            self.assertEqual(json.loads(up.call_args.args[0].data), {"eventId": "evt-1"})
        with patch("demo_server.urlopen", return_value=Fake({"status": "MATCHED", "differences": []})):
            status, body = self.call("POST", "/api/reconciliations", {})
        self.assertEqual((status, body["status"]), (200, "MATCHED"))

    def test_evidence_records_references_without_financial_fields(self) -> None:
        with patch("demo_server.urlopen", return_value=Fake({"id": "pay-evid", "status": "PENDING"}, 202)):
            self.call("POST", "/api/payments", {**self.payment, "qrId": "qr-evid", "idempotencyKey": "evid-key-1"})
        with patch("demo_server.urlopen", return_value=Fake({"id": "pay-evid", "status": "PENDING"}, 200)):
            self.call("POST", "/api/payments", {**self.payment, "qrId": "qr-evid", "idempotencyKey": "evid-key-1"})
        exported = self.server.evidence.export()["events"]
        mine = [e for e in exported if e.get("paymentId") == "pay-evid"]
        self.assertEqual([e["attempt"] for e in mine], ["ORIGINAL", "RETRY"])
        self.assertEqual([e["httpStatus"] for e in mine], ["202", "200"])
        event = mine[0]
        self.assertEqual(event["qrId"], "qr-evid")
        self.assertEqual(event["idempotencyKey"], "evid-key-1")
        self.assertEqual(event["eventType"], "PAYMENT_REQUESTED")
        for forbidden in ("amount", "status", "balance", "scenario", "document"):
            self.assertFalse([k for k in event if forbidden in k.lower().replace("httpstatus", "")], forbidden)

    def test_payment_activation_is_recorded_once_per_succeeded_payment(self) -> None:
        for _ in range(3):
            with patch("demo_server.urlopen", return_value=Fake({"id": "pay-act", "status": "SUCCEEDED"})):
                self.assertEqual(self.call("GET", "/api/payments/pay-act")[0], 200)
        with patch("demo_server.urlopen", return_value=Fake({"id": "pay-pend", "status": "PENDING"})):
            self.call("GET", "/api/payments/pay-pend")
        events = self.server.evidence.export()["events"]
        self.assertEqual(len([e for e in events if e["eventType"] == "PAYMENT_ACTIVATED" and e["paymentId"] == "pay-act"]), 1)
        self.assertFalse([e for e in events if e.get("paymentId") == "pay-pend" and e["eventType"] == "PAYMENT_ACTIVATED"])

    def test_trace_endpoint_only_accepts_known_steps_and_session_header(self) -> None:
        session = "a" * 32
        request = Request(f"{self.base}/api/trace", data=json.dumps({"step": "ONBOARDING_STARTED"}).encode(),
                          method="POST", headers={"Content-Type": "application/json", "X-Demo-Session": session})
        with client_urlopen(request) as response:
            self.assertEqual(response.status, 200)
        self.assertTrue([e for e in self.server.evidence.export()["events"]
                         if e["eventType"] == "ONBOARDING_STARTED" and e.get("sessionId") == session])
        for bad in ({"step": "DROP_TABLE"}, {"step": "ONBOARDING_STARTED", "x": 1}, {"step": "ONBOARDING_STARTED", "walletId": "../x"}):
            self.assertEqual(self.call("POST", "/api/trace", bad)[0], 400, bad)

    def test_support_views_are_traced_as_operator_actions(self) -> None:
        with patch("demo_server.urlopen", return_value=Fake([])):
            self.call("GET", "/api/support/cases")
        events = self.server.evidence.export()["events"]
        self.assertTrue([e for e in events if e["eventType"] == "SUPPORT_CASES_VIEWED" and e["httpStatus"] == "200"])


if __name__ == "__main__":
    unittest.main()
