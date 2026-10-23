"""CrewAI tools that call the local read-only MCP server over stdio (HA-05)."""

from __future__ import annotations

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, create_model

ROOT = Path(__file__).resolve().parents[1]
SERVER_SCRIPT = ROOT / "mcp_group3_server.py"
CALL_LOG: list[dict[str, Any]] = []


class McpToolError(RuntimeError):
    """The MCP call failed or was denied; the failure is reported, never masked."""


def allowed_tool_names() -> frozenset[str]:
    from mcp_group3_server import READ_ONLY_TOOLS

    return frozenset(READ_ONLY_TOOLS)


def _run_sync(coroutine):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coroutine).result()


async def _session_call(action: Callable[[Any], Any]):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=sys.executable, args=[str(SERVER_SCRIPT)], cwd=str(ROOT))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await action(session)


def list_mcp_tools() -> list[dict[str, Any]]:
    async def action(session):
        return (await session.list_tools()).tools

    try:
        tools = _run_sync(_session_call(action))
    except Exception as error:
        raise McpToolError(f"MCP-FAILURE: no se pudo descubrir herramientas ({error}).") from error
    return [{"name": t.name, "description": t.description or "", "inputSchema": t.inputSchema} for t in tools]


def call_mcp_tool(name: str, arguments: dict[str, Any] | None = None) -> str:
    """Invoke one tool through the stdio server; raise McpToolError on denial or failure."""
    entry = {
        "tool": name,
        "arguments": dict(arguments or {}),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    async def action(session):
        return await session.call_tool(name, arguments or {})

    try:
        result = _run_sync(_session_call(action))
        text = "\n".join(part.text for part in result.content if getattr(part, "text", None))
        if result.isError:
            raise McpToolError(text or "MCP-FAILURE: error sin detalle.")
    except McpToolError as error:
        CALL_LOG.append({**entry, "ok": False, "error": str(error)})
        raise
    except Exception as error:
        CALL_LOG.append({**entry, "ok": False, "error": f"MCP-FAILURE: {error}"})
        raise McpToolError(f"MCP-FAILURE: {error}") from error
    if not text:
        CALL_LOG.append({**entry, "ok": False, "error": "MCP-FAILURE: respuesta vacia."})
        raise McpToolError("MCP-FAILURE: respuesta vacia.")
    CALL_LOG.append({**entry, "ok": True, "responseChars": len(text)})
    return text


def _args_schema(name: str, input_schema: dict[str, Any]) -> type[BaseModel]:
    fields: dict[str, Any] = {}
    for key, spec in (input_schema.get("properties") or {}).items():
        if spec.get("type") != "string":
            raise McpToolError(f"MCP-FAILURE: argumento no soportado en {name}: {key}.")
        fields[key] = (str, Field(..., description=spec.get("title", key)))
    return create_model(f"{name}Args", **fields)


class Group3McpTool(BaseTool):
    mcp_tool_name: str
    caller: Callable[[str, dict[str, Any]], str] = Field(exclude=True)

    def _run(self, **kwargs: Any) -> str:
        try:
            return self.caller(self.mcp_tool_name, kwargs)
        except McpToolError as error:
            return f"FALLO MCP (sin datos del mock): {error}"


def build_crewai_tools(
    discovered: list[dict[str, Any]] | None = None,
    caller: Callable[[str, dict[str, Any]], str] = call_mcp_tool,
) -> list[BaseTool]:
    """Wrap only the allow-listed tools; an unexpected tool aborts the setup."""
    allowed = allowed_tool_names()
    discovered = list_mcp_tools() if discovered is None else discovered
    tools: list[BaseTool] = []
    for spec in discovered:
        if spec["name"] not in allowed:
            raise McpToolError(f"MCP-DENIED: el servidor expone una herramienta no permitida: {spec['name']}.")
        tools.append(
            Group3McpTool(
                name=spec["name"],
                description=f"{spec['description']} Devuelve JSON del mock o un fallo explicito.",
                args_schema=_args_schema(spec["name"], spec.get("inputSchema") or {}),
                mcp_tool_name=spec["name"],
                caller=caller,
            )
        )
    if not tools:
        raise McpToolError("MCP-FAILURE: el servidor no expone herramientas.")
    return tools
