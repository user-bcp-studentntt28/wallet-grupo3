from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from demo_auth import DEFAULT_PATH as USERS_PATH, UserStore, alias_for, hash_password, user_key, verify_password
from demo_evidence import DemoEvidenceStore
from demo_guardrails import (
    RESOURCE_ID,
    check_kyc_input,
    check_mock_call,
    check_mock_response,
    check_password,
    public_feature_map,
)
from demo_routes import KYC_SCENARIOS, Plan, RouteError, plan_get, plan_post


MOCK_API_BASE_URL = "https://bcp-wallet-mock.yefri.workers.dev/groups/3"
DEFAULT_PORT = 8000
REQUEST_TIMEOUT_SECONDS = 8
MAX_RESPONSE_BYTES = 1_048_576
WEB_ROOT = Path(__file__).resolve().parent / "wallet_demo_web"


@dataclass(frozen=True)
class MockResponse:
    status_code: int
    body: bytes
    content_type: str = "application/json; charset=utf-8"


def _json_response(status_code: int, payload: dict[str, str]) -> MockResponse:
    return MockResponse(
        status_code=status_code,
        body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )


def _bounded_response(status_code: int, body: bytes, content_type: str) -> MockResponse:
    if len(body) > MAX_RESPONSE_BYTES:
        return _json_response(
            502,
            {
                "error": "MOCK_RESPONSE_TOO_LARGE",
                "message": "La respuesta del mock excede el límite permitido.",
            },
        )
    return MockResponse(status_code, body, content_type)


class MockApiClient:
    def get_scenarios(self) -> MockResponse:
        return self._request_json("GET", "/scenarios")

    def create_kyc(self, payload: dict[str, object]) -> MockResponse:
        return self._request_json("POST", "/kyc/verifications", payload)

    def execute(self, plan: Plan) -> MockResponse:
        return self._request_json(
            plan.method,
            plan.mock_path,
            plan.payload,
            plan.confirmed,
            plan.headers,
            plan.query,
        )

    def _request_json(
        self,
        method: str,
        route: str,
        payload: dict[str, object] | None = None,
        confirmed: bool = False,
        extra_headers: dict[str, str] | None = None,
        query: dict[str, str] | None = None,
    ) -> MockResponse:
        decision = check_mock_call(method, route, confirmed)
        if not decision.allowed:
            return _json_response(
                403,
                {
                    "error": "GUARDRAIL_BLOCKED",
                    "ruleCode": decision.rule_code,
                    "message": decision.reason,
                },
            )

        response = self._send_request(method, route, payload, extra_headers, query)
        output = check_mock_response(response.body)
        if not output.allowed:
            return _json_response(
                502,
                {
                    "error": "GUARDRAIL_BLOCKED",
                    "ruleCode": output.rule_code,
                    "message": output.reason,
                },
            )
        return response

    def _send_request(
        self,
        method: str,
        route: str,
        payload: dict[str, object] | None = None,
        extra_headers: dict[str, str] | None = None,
        query: dict[str, str] | None = None,
    ) -> MockResponse:
        body = (
            json.dumps(payload, ensure_ascii=False).encode("utf-8")
            if payload is not None
            else None
        )
        headers = {
            "Accept": "application/json",
            "User-Agent": "WalletDemo/1.0",
            **(extra_headers or {}),
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        url = f"{MOCK_API_BASE_URL}{route}"
        if query:
            url += "?" + urlencode(query)
        request = Request(
            url,
            data=body,
            headers=headers,
            method=method,
        )

        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return _bounded_response(
                    response.status,
                    response.read(MAX_RESPONSE_BYTES + 1),
                    response.headers.get(
                        "Content-Type", "application/json; charset=utf-8"
                    ),
                )
        except HTTPError as error:
            return _bounded_response(
                error.code,
                error.read(MAX_RESPONSE_BYTES + 1),
                error.headers.get(
                    "Content-Type", "application/json; charset=utf-8"
                ),
            )
        except TimeoutError:
            return _json_response(
                504,
                {
                    "error": "MOCK_TIMEOUT",
                    "message": "El mock grupo 3 no respondió dentro del tiempo límite.",
                },
            )
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                return _json_response(
                    504,
                    {
                        "error": "MOCK_TIMEOUT",
                        "message": "El mock grupo 3 no respondió dentro del tiempo límite.",
                    },
                )
            return _json_response(
                502,
                {
                    "error": "MOCK_UNAVAILABLE",
                    "message": "No se pudo conectar con el mock grupo 3.",
                },
            )


class DemoHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    # En Windows SO_REUSEADDR permite que dos procesos compartan el puerto.
    allow_reuse_address = os.name != "nt"

    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler_class: type[BaseHTTPRequestHandler],
        bind_and_activate: bool = True,
        users_path: Path | None = None,
    ) -> None:
        self.mock_client = MockApiClient()
        self.evidence = DemoEvidenceStore()
        self.users = UserStore(users_path)
        super().__init__(
            server_address, request_handler_class, bind_and_activate=bind_and_activate
        )


class DemoRequestHandler(BaseHTTPRequestHandler):
    server: DemoHTTPServer

    _static_files = {
        "/": ("index.html", "text/html; charset=utf-8"),
        "/index.html": ("index.html", "text/html; charset=utf-8"),
        "/styles.css": ("styles.css", "text/css; charset=utf-8"),
        "/app.js": ("app.js", "text/javascript; charset=utf-8"),
        "/vendor/qrcode.js": ("vendor/qrcode.js", "text/javascript; charset=utf-8"),
    }

    def do_GET(self) -> None:
        path = urlsplit(self.path).path

        if path in self._static_files:
            file_name, content_type = self._static_files[path]
            body = (WEB_ROOT / file_name).read_bytes()
            self._send_bytes(200, body, content_type)
            return

        if path == "/api/health":
            self._send_json(200, {"status": "ok", "group": "3"})
            return

        if path == "/api/scenarios":
            self.server.evidence.record("SCENARIOS_LOOKUP")
            response = self.server.mock_client.get_scenarios()
            self._send_bytes(
                response.status_code, response.body, response.content_type
            )
            return

        if path == "/api/guardrails":
            body = json.dumps(
                {"features": public_feature_map()}, ensure_ascii=False
            ).encode("utf-8")
            self._send_bytes(200, body, "application/json; charset=utf-8")
            return

        if path == "/api/evidence/export":
            body = json.dumps(
                self.server.evidence.export(), ensure_ascii=False, indent=2
            ).encode("utf-8")
            self._send_bytes(
                200,
                body,
                "application/json; charset=utf-8",
                {
                    "Content-Disposition": (
                        'attachment; filename="wallet-demo-evidence.json"'
                    )
                },
            )
            return

        try:
            plan = plan_get(path, urlsplit(self.path).query)
        except RouteError as error:
            self._reject(error)
            return
        if plan is not None:
            self._run_plan(plan)
            return

        self._send_json(
            404,
            {"error": "NOT_FOUND", "message": "La ruta solicitada no existe."},
        )

    def _reject(self, error: RouteError) -> None:
        self.server.evidence.record("GUARDRAIL_DENIED", rule_code=error.rule_code)
        self._send_json(
            400,
            {
                "error": "GUARDRAIL_BLOCKED",
                "ruleCode": error.rule_code,
                "message": error.message,
            },
        )

    def _run_plan(self, plan: Plan) -> None:
        response = self.server.mock_client.execute(plan)
        self._record_plan_evidence(plan, response)
        self._send_bytes(response.status_code, response.body, response.content_type)

    def _session_id(self) -> str | None:
        value = self.headers.get("X-Demo-Session", "")
        return value if re.fullmatch(r"[a-f0-9]{32}", value) else None

    def _record_plan_evidence(self, plan: Plan, response: MockResponse) -> None:
        try:
            data = json.loads(response.body)
        except ValueError:
            data = None
        if response.status_code == 403 and isinstance(data, dict):
            rule_code = data.get("ruleCode")
            if isinstance(rule_code, str):
                self.server.evidence.record("GUARDRAIL_DENIED", rule_code=rule_code)
            return

        def safe(value: object) -> str | None:
            return value if isinstance(value, str) and RESOURCE_ID.fullmatch(value) else None

        payload = plan.payload or {}
        body = data if isinstance(data, dict) else {}

        payment_path = re.fullmatch(r"/payments/([A-Za-z0-9_-]+)", plan.mock_path)
        if plan.method == "GET" and payment_path and body.get("status") == "SUCCEEDED":
            self.server.evidence.record_once(
                "PAYMENT_ACTIVATED",
                payment_path.group(1),
                payment_id=payment_path.group(1),
                session_id=self._session_id(),
            )
        if plan.event is None:
            return

        key = plan.headers.get("Idempotency-Key")
        path_event = re.search(r"/events/([A-Za-z0-9_-]+)/deliver", plan.mock_path)
        path_payment = re.search(r"/payments/([A-Za-z0-9_-]+)/resolve|/provider/([A-Za-z0-9_-]+)/complete", plan.mock_path)
        self.server.evidence.record(
            plan.event,
            wallet_id=safe(payload.get("walletId")),
            qr_id=safe(payload.get("qrId")) or safe(body.get("id") if plan.event.startswith("QR_") else None),
            payment_id=safe(body.get("paymentId"))
            or safe(body.get("id") if plan.event.startswith("PAYMENT_") else None)
            or safe(payload.get("paymentId"))
            or (safe(next((g for g in path_payment.groups() if g), None)) if path_payment else None),
            event_id=safe(payload.get("eventId")) or (path_event.group(1) if path_event else None),
            idempotency_key=safe(key),
            attempt=self.server.evidence.note_attempt(key) if safe(key) else None,
            http_status=response.status_code,
            session_id=self._session_id(),
        )

    def _handle_trace(self, body: object) -> None:
        steps = {
            "ONBOARDING_STARTED", "ONBOARDING_STEP_COMPLETED", "ONBOARDING_COMPLETED",
            "CHECKOUT_STARTED", "CHECKOUT_CONFIRMED",
        }
        if not isinstance(body, dict) or set(body) - {"step", "walletId"} or body.get("step") not in steps:
            self._reject(RouteError("Paso de traza no permitido."))
            return
        wallet = body.get("walletId")
        if wallet is not None and not (isinstance(wallet, str) and RESOURCE_ID.fullmatch(wallet)):
            self._reject(RouteError("walletId no es un identificador válido.", "DEMO-IN-04"))
            return
        self.server.evidence.record(body["step"], wallet_id=wallet, session_id=self._session_id())
        self._send_json(200, {"recorded": body["step"]})

    def _auth_error(self, status: int, error: str, message: str, rule_code: str | None = None) -> None:
        payload = {"error": error, "message": message}
        if rule_code:
            payload["ruleCode"] = rule_code
            self.server.evidence.record("GUARDRAIL_DENIED", rule_code=rule_code)
        self._send_json(status, payload)

    def _handle_register(self, body: object) -> None:
        if not isinstance(body, dict) or set(body) - {"document", "password", "scenario"}:
            self._auth_error(400, "GUARDRAIL_BLOCKED", "La solicitud contiene campos no permitidos.", "DEMO-IN-01")
            return
        scenario = body.get("scenario")
        if scenario is not None and scenario not in KYC_SCENARIOS:
            self._auth_error(400, "GUARDRAIL_BLOCKED", "Escenario KYC no permitido.", "DEMO-IN-01")
            return
        kyc_input = {"documentType": "TEST", "document": body.get("document")}
        for check in (check_kyc_input(kyc_input), check_password(body.get("password"))):
            if not check.allowed:
                self._auth_error(400, "GUARDRAIL_BLOCKED", check.reason, check.rule_code)
                return
        document, password = body["document"], body["password"]
        key = user_key(document)
        if self.server.users.get(key):
            self._auth_error(409, "USER_EXISTS", "Ya estás registrado: ingresa con tu clave.")
            return

        kyc_payload: dict[str, object] = {"documentType": "TEST", "document": document}
        if scenario is not None:
            kyc_payload["scenario"] = scenario
        response = self.server.mock_client.create_kyc(kyc_payload)
        try:
            data = json.loads(response.body)
        except ValueError:
            data = None
        if response.status_code != 201 or not isinstance(data, dict):
            self._send_bytes(response.status_code, response.body, response.content_type)
            return
        record = {"alias": alias_for(document), "kycId": data.get("id"), "walletId": data.get("wallet_id"),
                  "status": data.get("status")}
        public = {**record, "registered": data.get("status") in ("ACTIVE", "PENDING")}
        if public["registered"]:
            salt, digest = hash_password(password)
            self.server.users.add(key, {**record, "salt": salt, "hash": digest})
            self.server.evidence.record("USER_REGISTERED", wallet_id=record["walletId"], session_id=self._session_id())
        self._send_json(201, public)

    def _handle_login(self, body: object) -> None:
        if not isinstance(body, dict) or set(body) - {"document", "password"}:
            self._auth_error(400, "GUARDRAIL_BLOCKED", "La solicitud contiene campos no permitidos.", "DEMO-IN-01")
            return
        check = check_kyc_input({"documentType": "TEST", "document": body.get("document")})
        password = body.get("password")
        if not check.allowed or not isinstance(password, str) or not 0 < len(password) <= 64:
            self._auth_error(400, "GUARDRAIL_BLOCKED", check.reason if not check.allowed else "Ingresa tu clave.",
                             check.rule_code or "DEMO-IN-05")
            return
        key = user_key(body["document"])
        users = self.server.users
        wait = users.locked_seconds(key)
        if wait:
            self._auth_error(429, "TOO_MANY_ATTEMPTS", f"Demasiados intentos. Espera {wait} s e inténtalo de nuevo.")
            return
        record = users.get(key)
        if record is None:
            self._auth_error(404, "USER_NOT_FOUND", "No estás registrado: usa Registrarme.")
            return
        if not verify_password(password, record["salt"], record["hash"]):
            left = users.register_failure(key)
            self.server.evidence.record("LOGIN_FAILED", session_id=self._session_id())
            self._auth_error(401, "INVALID_CREDENTIALS", f"Clave incorrecta. Intentos restantes: {left}.")
            return
        users.clear_failures(key)
        kyc = self.server.mock_client._request_json("GET", f"/kyc/verifications/{record['kycId']}")
        try:
            kyc_data = json.loads(kyc.body)
        except ValueError:
            kyc_data = None
        if kyc.status_code != 200 or not isinstance(kyc_data, dict):
            self._send_bytes(kyc.status_code, kyc.body, kyc.content_type)
            return
        users.update_status(key, kyc_data.get("status"))
        self.server.evidence.record("USER_LOGIN", wallet_id=record["walletId"], session_id=self._session_id())
        self._send_json(200, {"alias": record["alias"], "kycId": record["kycId"],
                              "walletId": record["walletId"], "status": kyc_data.get("status")})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path in ("/api/auth/register", "/api/auth/login"):
            body = self._read_json_body()
            if body is not None:
                (self._handle_register if path.endswith("register") else self._handle_login)(body)
            return
        if path == "/api/trace":
            body = self._read_json_body()
            if body is not None:
                self._handle_trace(body)
            return
        if path != "/api/kyc":
            body = self._read_json_body()
            if body is None:
                return
            try:
                plan = plan_post(path, body) if isinstance(body, dict) else None
            except RouteError as error:
                self._reject(error)
                return
            if plan is None:
                self._send_json(
                    405,
                    {
                        "error": "METHOD_NOT_ALLOWED",
                        "message": "Este endpoint no acepta solicitudes POST.",
                    },
                )
                return
            self._run_plan(plan)
            return

        payload = self._read_json_body()
        if payload is None:
            return

        decision = check_kyc_input(payload)
        if not decision.allowed:
            self.server.evidence.record("GUARDRAIL_DENIED", rule_code=decision.rule_code)
            self._send_json(
                400,
                {
                    "error": "GUARDRAIL_BLOCKED",
                    "ruleCode": decision.rule_code,
                    "message": decision.reason,
                },
            )
            return

        document = payload["document"]
        scenario = payload.get("scenario")
        allowed_scenarios = {
            "APPROVED",
            "REJECTED",
            "MANUAL_REVIEW",
            "UNAVAILABLE",
        }
        if scenario is not None and (
            not isinstance(scenario, str) or scenario not in allowed_scenarios
        ):
            self._send_json(
                400,
                {
                    "error": "INVALID_SCENARIO",
                    "message": "Selecciona un escenario KYC permitido.",
                },
            )
            return

        mock_payload: dict[str, object] = {
            "documentType": "TEST",
            "document": document,
        }
        if scenario is not None:
            mock_payload["scenario"] = scenario

        self.server.evidence.record("KYC_ATTEMPT")
        response = self.server.mock_client.create_kyc(mock_payload)
        try:
            kyc_data = json.loads(response.body)
        except ValueError:
            kyc_data = None
        if isinstance(kyc_data, dict):
            wallet = kyc_data.get("wallet_id")
            if isinstance(wallet, str) and RESOURCE_ID.fullmatch(wallet):
                self.server.evidence.record("KYC_RESULT", wallet_id=wallet)
        self._send_bytes(
            response.status_code, response.body, response.content_type
        )

    def _read_json_body(self) -> object | None:
        content_length = self.headers.get("Content-Length")
        try:
            length = int(content_length) if content_length is not None else 0
        except ValueError:
            self._send_json(
                400,
                {
                    "error": "INVALID_CONTENT_LENGTH",
                    "message": "La longitud de la solicitud no es válida.",
                },
            )
            return None
        if length <= 0:
            self._send_json(
                400,
                {"error": "EMPTY_REQUEST", "message": "Envía un objeto JSON."},
            )
            return None
        if length > 16_384:
            self._send_json(
                413,
                {
                    "error": "REQUEST_TOO_LARGE",
                    "message": "La solicitud excede el tamaño permitido.",
                },
            )
            return None
        try:
            return json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(
                400,
                {"error": "INVALID_JSON", "message": "El cuerpo no es JSON válido."},
            )
            return None

    def _send_json(self, status_code: int, payload: dict[str, str]) -> None:
        response = _json_response(status_code, payload)
        self._send_bytes(
            response.status_code, response.body, response.content_type
        )

    def _send_bytes(
        self,
        status_code: int,
        body: bytes,
        content_type: str,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; base-uri 'none'; "
            "frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(body)


def serve(port: int = DEFAULT_PORT) -> None:
    server = DemoHTTPServer(("127.0.0.1", port), DemoRequestHandler, users_path=USERS_PATH)
    print(f"Wallet Perú demo lista en http://127.0.0.1:{port}  (Ctrl+C para detener)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        server.server_close()


def main() -> None:
    serve()


if __name__ == "__main__":
    main()
