from __future__ import annotations

import json
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from demo_evidence import DemoEvidenceStore


MOCK_API_BASE_URL = "https://bcp-wallet-mock.yefri.workers.dev/groups/3"
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

    def _request_json(
        self,
        method: str,
        route: str,
        payload: dict[str, object] | None = None,
    ) -> MockResponse:
        body = (
            json.dumps(payload, ensure_ascii=False).encode("utf-8")
            if payload is not None
            else None
        )
        headers = {
            "Accept": "application/json",
            "User-Agent": "WalletDemo/1.0",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{MOCK_API_BASE_URL}{route}",
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
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler_class: type[BaseHTTPRequestHandler],
        bind_and_activate: bool = True,
    ) -> None:
        self.mock_client = MockApiClient()
        self.evidence = DemoEvidenceStore()
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

        self._send_json(
            404,
            {"error": "NOT_FOUND", "message": "La ruta solicitada no existe."},
        )

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path != "/api/kyc":
            self._send_json(
                405,
                {
                    "error": "METHOD_NOT_ALLOWED",
                    "message": "Este endpoint no acepta solicitudes POST.",
                },
            )
            return

        payload = self._read_json_body()
        if payload is None:
            return
        if not isinstance(payload, dict):
            self._send_json(
                400,
                {
                    "error": "INVALID_REQUEST",
                    "message": "El cuerpo debe ser un objeto JSON.",
                },
            )
            return

        allowed_fields = {"documentType", "document", "scenario"}
        if set(payload) - allowed_fields:
            self._send_json(
                400,
                {
                    "error": "INVALID_FIELDS",
                    "message": "La solicitud contiene campos no permitidos.",
                },
            )
            return

        document_type = payload.get("documentType")
        document = payload.get("document")
        scenario = payload.get("scenario")
        if (
            document_type != "TEST"
            or not isinstance(document, str)
            or not document.startswith("TEST-")
            or len(document) > 200
        ):
            self._send_json(
                400,
                {
                    "error": "INVALID_TEST_IDENTITY",
                    "message": "Usa documentType TEST y un documento ficticio con prefijo TEST-.",
                },
            )
            return

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


def main() -> None:
    server = DemoHTTPServer(("127.0.0.1", 8000), DemoRequestHandler)
    print("Wallet Perú demo lista en http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
