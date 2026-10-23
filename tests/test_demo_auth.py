from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen as client_urlopen
from unittest.mock import patch

import demo_auth
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


KYC_OK = {"id": "kyc_1", "wallet_id": "wallet_1", "scenario": "APPROVED", "status": "ACTIVE"}


class AuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.users_file = Path(self.tmp.name) / "users.json"
        self.server = demo_server.DemoHTTPServer(
            ("127.0.0.1", 0), demo_server.DemoRequestHandler, users_path=self.users_file
        )
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), thread.join(timeout=2)))
        # PBKDF2 con 200k rondas es lento en pruebas.
        patcher = patch.object(demo_auth, "PBKDF2_ROUNDS", 1000)
        patcher.start()
        self.addCleanup(patcher.stop)

    def post(self, path: str, body: dict) -> tuple[int, dict]:
        request = Request(f"{self.base}{path}", data=json.dumps(body).encode(), method="POST",
                          headers={"Content-Type": "application/json"})
        try:
            with client_urlopen(request) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def register(self, document="TEST-ANA-001", password="482915", status=KYC_OK, code=201):
        with patch("demo_server.urlopen", return_value=Fake(status, code)) as upstream:
            result = self.post("/api/auth/register", {"document": document, "password": password})
        return result, upstream

    def login(self, document="TEST-ANA-001", password="482915", kyc_status="ACTIVE"):
        with patch("demo_server.urlopen", return_value=Fake({**KYC_OK, "status": kyc_status})) as upstream:
            return self.post("/api/auth/login", {"document": document, "password": password}), upstream

    def test_register_then_login_without_registering_again(self) -> None:
        (status, body), _ = self.register()
        self.assertEqual((status, body["registered"], body["status"]), (201, True, "ACTIVE"))
        (status, body), upstream = self.login()
        self.assertEqual((status, body["walletId"]), (200, "wallet_1"))
        self.assertTrue(upstream.call_args.args[0].full_url.endswith("/kyc/verifications/kyc_1"))
        self.assertNotIn("hash", json.dumps(body))

    def test_already_registered_user_cannot_register_again(self) -> None:
        self.register()
        (status, body), upstream = self.register()
        self.assertEqual((status, body["error"]), (409, "USER_EXISTS"))
        upstream.assert_not_called()

    def test_unknown_user_is_told_to_register(self) -> None:
        (status, body), upstream = self.login(document="TEST-NADIE-9")
        self.assertEqual((status, body["error"]), (404, "USER_NOT_FOUND"))
        upstream.assert_not_called()

    def test_wrong_password_then_temporary_lock(self) -> None:
        self.register()
        for left in (4, 3, 2, 1, 0):
            (status, body), _ = self.login(password="999111")
            self.assertEqual((status, body["error"]), (401, "INVALID_CREDENTIALS"))
            self.assertIn(f"restantes: {left}", body["message"])
        (status, body), upstream = self.login(password="482915")
        self.assertEqual((status, body["error"]), (429, "TOO_MANY_ATTEMPTS"))
        upstream.assert_not_called()

    def test_password_policy_and_test_prefix_are_enforced_before_the_mock(self) -> None:
        for password in ("12345", "1234567", "abcdef", "111111", "123456", ""):
            (status, body), upstream = self.register(password=password)
            self.assertEqual((status, body["ruleCode"]), (400, "DEMO-IN-05"), password)
            upstream.assert_not_called()
        (status, body), upstream = self.register(document="12345678")
        self.assertEqual((status, body["ruleCode"]), (400, "DEMO-IN-02"))
        upstream.assert_not_called()

    def test_extra_fields_are_rejected(self) -> None:
        status, body = self.post("/api/auth/register", {"document": "TEST-A-1", "password": "482915", "admin": 1})
        self.assertEqual((status, body["ruleCode"]), (400, "DEMO-IN-01"))

    def test_rejected_kyc_is_not_stored_so_the_user_can_retry(self) -> None:
        (status, body), _ = self.register(status={**KYC_OK, "status": "REJECTED"})
        self.assertEqual((status, body["registered"], body["status"]), (201, False, "REJECTED"))
        (status, body), _ = self.login()
        self.assertEqual(status, 404)

    def test_unavailable_kyc_is_passed_through(self) -> None:
        (status, body), _ = self.register(status={"error": "KYC_UNAVAILABLE"}, code=503)
        self.assertEqual((status, body["error"]), (503, "KYC_UNAVAILABLE"))

    def test_login_refreshes_status_from_the_mock(self) -> None:
        self.register(status={**KYC_OK, "status": "PENDING"})
        (status, body), _ = self.login(kyc_status="ACTIVE")
        self.assertEqual((status, body["status"]), (200, "ACTIVE"))
        stored = json.loads(self.users_file.read_text(encoding="utf-8"))
        self.assertEqual(next(iter(stored.values()))["status"], "ACTIVE")

    def test_only_a_salted_hash_is_stored_never_the_password_or_document(self) -> None:
        self.register(document="TEST-ANA-001", password="482915")
        raw = self.users_file.read_text(encoding="utf-8")
        self.assertNotIn("482915", raw)
        self.assertNotIn("TEST-ANA-001", raw)
        record = next(iter(json.loads(raw).values()))
        self.assertTrue(demo_auth.verify_password("482915", record["salt"], record["hash"]))
        self.assertFalse(demo_auth.verify_password("000111", record["salt"], record["hash"]))

    def test_users_persist_across_server_restarts(self) -> None:
        self.register()
        reloaded = demo_auth.UserStore(self.users_file)
        self.assertIsNotNone(reloaded.get(demo_auth.user_key("TEST-ANA-001")))

    def test_evidence_never_contains_password_or_document(self) -> None:
        self.register()
        self.login(password="000999")
        self.login()
        exported = json.dumps(self.server.evidence.export())
        for secret in ("482915", "000999", "TEST-ANA-001"):
            self.assertNotIn(secret, exported)
        self.assertIn("USER_REGISTERED", exported)
        self.assertIn("LOGIN_FAILED", exported)
        self.assertIn("USER_LOGIN", exported)


if __name__ == "__main__":
    unittest.main()
