"""Servidor MCP local (stdio) de solo lectura para el mock del grupo 3 (HA-05).

Las herramientas salen de las entradas `mcp_read_only` del FEATURE_MAP. Toda
llamada pasa por `check_mock_call` antes de tocar la red, el destino es fijo y
la respuesta pasa por `check_mock_response`. No hay escritura, reset, shell ni
URL arbitraria.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from demo_guardrails import (
    ALLOW,
    FEATURE_MAP,
    RESOURCE_ID,
    Feature,
    GuardrailResult,
    check_mock_call,
    check_mock_response,
    classify,
)

BASE_URL = "https://bcp-wallet-mock.yefri.workers.dev/groups/3"
USER_AGENT = "WalletDemo/1.0"
TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 1_000_000
ID_PARAM = "resource_id"


class McpDenied(Exception):
    def __init__(self, rule_code: str, reason: str):
        super().__init__(f"{rule_code}: {reason}")
        self.rule_code = rule_code
        self.reason = reason


class McpUpstreamError(Exception):
    """El mock no respondio con exito; nunca se inventa una respuesta."""


@dataclass(frozen=True)
class ReadOnlyTool:
    name: str
    description: str
    feature: Feature

    @property
    def takes_id(self) -> bool:
        return "{id}" in self.feature.path


def _tool_name(feature: Feature) -> str:
    segments = [part for part in feature.path.split("/") if part and part != "{id}"]
    base = segments[-1]
    if "{id}" in feature.path and base.endswith("s"):
        base = base[:-1]
    return f"get_{base}"


def _build_tools() -> dict[str, ReadOnlyTool]:
    tools: dict[str, ReadOnlyTool] = {}
    for feature in FEATURE_MAP:
        if feature.mcp_read_only and feature.method == "GET" and feature.policy == ALLOW:
            name = _tool_name(feature)
            tools[name] = ReadOnlyTool(
                name,
                f"{feature.functionality}. Solo lectura, grupo 3 ({feature.method} {feature.path}).",
                feature,
            )
    return tools


READ_ONLY_TOOLS: dict[str, ReadOnlyTool] = _build_tools()


def authorize_request(method: str, target: str) -> GuardrailResult:
    """Puerta unica del MCP: ruta mapeada, GET y marcada mcp_read_only."""
    if "://" in target or not target.startswith("/") or "?" in target or "#" in target:
        return GuardrailResult(False, "DEMO-TOOL-01", "Destino arbitrario: solo rutas fijas del grupo 3.")
    verdict = check_mock_call(method, target, confirmed=False)
    if not verdict.allowed:
        return verdict
    feature = classify(method, target)
    if feature is None or method.upper() != "GET" or not feature.mcp_read_only:
        return GuardrailResult(False, "DEMO-TOOL-01", "Operacion fuera de la lista de solo lectura del MCP.")
    return GuardrailResult(True, "", "OK")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def fetch(url: str) -> tuple[int, bytes]:
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        return error.code, error.read(MAX_RESPONSE_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise McpUpstreamError(f"MCP-UPSTREAM: no hubo respuesta del mock ({error}).") from error


def call_tool(name: str, arguments: dict | None = None) -> str:
    tool = READ_ONLY_TOOLS.get(name)
    if tool is None:
        raise McpDenied("DEMO-TOOL-01", f"Herramienta no permitida: {name!r}.")
    arguments = arguments or {}
    allowed_keys = {ID_PARAM} if tool.takes_id else set()
    if set(arguments) - allowed_keys:
        raise McpDenied("DEMO-IN-01", "Argumentos no permitidos para esta herramienta.")

    path = tool.feature.path
    if tool.takes_id:
        resource_id = arguments.get(ID_PARAM)
        if not isinstance(resource_id, str) or not RESOURCE_ID.fullmatch(resource_id):
            raise McpDenied("DEMO-IN-04", "Identificador de recurso invalido.")
        path = path.replace("{id}", resource_id)

    verdict = authorize_request("GET", path)
    if not verdict.allowed:
        raise McpDenied(verdict.rule_code, verdict.reason)

    status, body = fetch(BASE_URL + path)
    if len(body) > MAX_RESPONSE_BYTES:
        raise McpUpstreamError("MCP-UPSTREAM: respuesta demasiado grande.")
    output = check_mock_response(body)
    if not output.allowed:
        raise McpDenied(output.rule_code, output.reason)
    try:
        payload = json.loads(body)
    except ValueError as error:
        raise McpUpstreamError(f"MCP-UPSTREAM: HTTP {status} con JSON invalido.") from error
    if not 200 <= status < 300:
        code = payload.get("error") if isinstance(payload, dict) else None
        raise McpUpstreamError(f"MCP-UPSTREAM: el mock respondio HTTP {status} {code or ''}".strip())
    return json.dumps({"status": status, "body": payload}, ensure_ascii=False)


def _handler(tool: ReadOnlyTool):
    from mcp.server.fastmcp.exceptions import ToolError

    def run(arguments: dict) -> str:
        try:
            return call_tool(tool.name, arguments)
        except (McpDenied, McpUpstreamError) as error:
            raise ToolError(str(error)) from error

    if tool.takes_id:
        def with_id(resource_id: str) -> str:
            return run({ID_PARAM: resource_id})
        return with_id

    def without_id() -> str:
        return run({})
    return without_id


def build_server():
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("wallet-grupo3-readonly")
    for tool in READ_ONLY_TOOLS.values():
        server.add_tool(_handler(tool), name=tool.name, description=tool.description)
    return server


if __name__ == "__main__":
    build_server().run(transport="stdio")
