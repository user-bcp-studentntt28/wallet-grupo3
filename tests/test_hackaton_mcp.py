"""Local read-only MCP: discovery, stubbed mock calls, denials and failures (HA-05)."""

import asyncio
import json
import unittest
from unittest.mock import patch

from mcp.server.fastmcp.exceptions import ToolError

import demo_guardrails
import mcp_group3_server as server
from agents import mcp_tools

EXPECTED = {"get_scenarios", "get_wallet", "get_payment"}


def forbidden_fetch(url):
    raise AssertionError(f"No debio haber llamada de red: {url}")


class DiscoveryTests(unittest.TestCase):
    def test_tools_are_exactly_the_read_only_entries_of_the_feature_map(self):
        derived = {
            (f.method, f.path) for f in demo_guardrails.FEATURE_MAP if f.mcp_read_only
        }
        self.assertEqual(derived, {("GET", "/scenarios"), ("GET", "/wallets/{id}"), ("GET", "/payments/{id}")})
        self.assertEqual(set(server.READ_ONLY_TOOLS), EXPECTED)
        for tool in server.READ_ONLY_TOOLS.values():
            self.assertEqual(tool.feature.method, "GET")
            self.assertEqual(tool.feature.policy, demo_guardrails.ALLOW)

    def test_server_lists_only_allowed_tools(self):
        listed = asyncio.run(server.build_server().list_tools())
        self.assertEqual({tool.name for tool in listed}, EXPECTED)

    def test_stdio_discovery_lists_only_allowed_tools(self):
        discovered = mcp_tools.list_mcp_tools()
        self.assertEqual({tool["name"] for tool in discovered}, EXPECTED)

    def test_crewai_tools_wrap_only_the_allow_list(self):
        tools = mcp_tools.build_crewai_tools(
            [{"name": n, "description": "d", "inputSchema": {"properties": {}}} for n in sorted(EXPECTED)],
            caller=lambda name, args: "{}",
        )
        self.assertEqual({tool.name for tool in tools}, EXPECTED)
        with self.assertRaises(mcp_tools.McpToolError):
            mcp_tools.build_crewai_tools(
                [{"name": "execute_shell", "description": "x", "inputSchema": {}}], caller=lambda n, a: ""
            )
        with self.assertRaises(mcp_tools.McpToolError):
            mcp_tools.build_crewai_tools([], caller=lambda n, a: "")


class StubbedCallTests(unittest.TestCase):
    def test_call_consumes_the_mock_response_through_the_fixed_url(self):
        body = json.dumps({"id": "wallet-demo", "status": "ACTIVE", "balance": 69900}).encode()
        with patch.object(server, "fetch", return_value=(200, body)) as fetch:
            result = json.loads(server.call_tool("get_wallet", {"resource_id": "wallet-demo"}))
        fetch.assert_called_once_with("https://bcp-wallet-mock.yefri.workers.dev/groups/3/wallets/wallet-demo")
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["body"]["balance"], 69900)

    def test_scenarios_and_payment_use_their_mapped_routes(self):
        with patch.object(server, "fetch", return_value=(200, b'{"kyc": []}')) as fetch:
            server.call_tool("get_scenarios")
            server.call_tool("get_payment", {"resource_id": "pay_1"})
        self.assertEqual(
            [call.args[0] for call in fetch.call_args_list],
            [server.BASE_URL + "/scenarios", server.BASE_URL + "/payments/pay_1"],
        )

    def test_crewai_tool_returns_the_tool_response(self):
        tools = mcp_tools.build_crewai_tools(
            [{"name": "get_wallet", "description": "d", "inputSchema": {
                "properties": {"resource_id": {"type": "string", "title": "Resource Id"}}}}],
            caller=lambda name, args: json.dumps({"called": name, "args": args}),
        )
        output = json.loads(tools[0].run(resource_id="wallet-demo"))
        self.assertEqual(output, {"called": "get_wallet", "args": {"resource_id": "wallet-demo"}})


class DenialTests(unittest.TestCase):
    def test_unlisted_tools_are_denied_before_any_network_call(self):
        with patch.object(server, "fetch", side_effect=forbidden_fetch):
            for name in ("control_reset", "post_payments", "execute_shell", "http_get", "create_reversal", "get_ledger"):
                with self.subTest(tool=name), self.assertRaises(server.McpDenied) as raised:
                    server.call_tool(name, {})
                self.assertEqual(raised.exception.rule_code, "DEMO-TOOL-01")

    def test_invalid_ids_and_extra_arguments_are_denied(self):
        with patch.object(server, "fetch", side_effect=forbidden_fetch):
            for bad in ("../control/reset", "a/b", "x?y=1", "", "a" * 101, 5):
                with self.subTest(resource_id=bad), self.assertRaises(server.McpDenied) as raised:
                    server.call_tool("get_wallet", {"resource_id": bad})
                self.assertEqual(raised.exception.rule_code, "DEMO-IN-04")
            for extra in ({"url": "https://evil.example"}, {"resource_id": "w", "method": "POST"}):
                with self.subTest(extra=extra), self.assertRaises(server.McpDenied) as raised:
                    server.call_tool("get_wallet", extra)
                self.assertEqual(raised.exception.rule_code, "DEMO-IN-01")
            with self.assertRaises(server.McpDenied):
                server.call_tool("get_scenarios", {"resource_id": "x"})

    def test_gate_reports_the_rule_code_of_each_forbidden_operation(self):
        cases = {
            ("POST", "/control/reset"): "DEMO-TOOL-02",
            ("POST", "/payments/pay_1/reversals"): "DEMO-TOOL-02",
            ("GET", "/usage/all"): "DEMO-TOOL-02",
            ("POST", "/payments"): "DEMO-TOOL-03",
            ("POST", "/control/settlements"): "DEMO-TOOL-03",
            ("GET", "/ledger"): "DEMO-TOOL-01",
            ("GET", "/nope"): "DEMO-TOOL-01",
            ("GET", "https://evil.example/groups/3/scenarios"): "DEMO-TOOL-01",
            ("GET", "//evil.example/x"): "DEMO-TOOL-01",
            ("GET", "/scenarios?x=1"): "DEMO-TOOL-01",
            ("GET", "/wallets/..%2Fx"): "DEMO-IN-04",
        }
        for (method, target), code in cases.items():
            with self.subTest(method=method, target=target):
                verdict = server.authorize_request(method, target)
                self.assertFalse(verdict.allowed)
                self.assertEqual(verdict.rule_code, code)
        self.assertTrue(server.authorize_request("GET", "/wallets/wallet-demo").allowed)

    def test_denials_over_real_stdio_transport_need_no_network(self):
        for name, arguments, fragment in (
            ("control_reset", {}, "Unknown tool"),
            ("get_wallet", {"resource_id": "../control/reset"}, "DEMO-IN-04"),
        ):
            with self.subTest(tool=name), self.assertRaises(mcp_tools.McpToolError) as raised:
                mcp_tools.call_mcp_tool(name, arguments)
            self.assertIn(fragment, str(raised.exception))
        self.assertFalse(mcp_tools.CALL_LOG[-1]["ok"])


class FailureTests(unittest.TestCase):
    def test_failures_are_errors_not_invented_success(self):
        cases = (
            (server.McpUpstreamError("MCP-UPSTREAM: sin respuesta"), None),
            (None, (503, b'{"error": "PROVIDER_ERROR"}')),
            (None, (404, b'{"error": "NOT_FOUND"}')),
            (None, (200, b"<html>no json</html>")),
            (None, (200, b"x" * (server.MAX_RESPONSE_BYTES + 1))),
        )
        for error, response in cases:
            with self.subTest(error=error, response=response and response[0]):
                patcher = patch.object(server, "fetch", side_effect=error, return_value=response)
                with patcher, self.assertRaises(server.McpUpstreamError):
                    server.call_tool("get_payment", {"resource_id": "pay_1"})

    def test_response_with_secret_is_blocked_by_the_output_rule(self):
        leaked = json.dumps({"note": "sk-" + "a" * 30}).encode()
        with patch.object(server, "fetch", return_value=(200, leaked)):
            with self.assertRaises(server.McpDenied) as raised:
                server.call_tool("get_scenarios")
        self.assertEqual(raised.exception.rule_code, "DEMO-OUT-01")

    def test_mcp_server_surfaces_failure_as_tool_error(self):
        with patch.object(server, "fetch", return_value=(503, b'{"error": "PROVIDER_ERROR"}')):
            with self.assertRaises(ToolError) as raised:
                asyncio.run(server.build_server().call_tool("get_wallet", {"resource_id": "wallet-demo"}))
        self.assertIn("HTTP 503", str(raised.exception))

    def test_crewai_tool_reports_failure_explicitly(self):
        def failing(name, arguments):
            raise mcp_tools.McpToolError("MCP-FAILURE: servidor caido")

        tools = mcp_tools.build_crewai_tools(
            [{"name": "get_scenarios", "description": "d", "inputSchema": {"properties": {}}}], caller=failing
        )
        output = tools[0].run()
        self.assertTrue(output.startswith("FALLO MCP"))
        self.assertNotIn('"status": 200', output)

    def test_stdio_client_failure_is_reported(self):
        with patch.object(mcp_tools, "SERVER_SCRIPT", mcp_tools.ROOT / "no_existe.py"):
            with self.assertRaises(mcp_tools.McpToolError):
                mcp_tools.call_mcp_tool("get_scenarios")


class AgentToolUseTests(unittest.TestCase):
    def test_crewai_agent_invokes_the_tool_and_receives_its_response(self):
        from crewai import BaseLLM, Crew, Process

        from agents import qa_security

        turns, prompts = [], []

        class ScriptedLLM(BaseLLM):
            def call(self, messages, **kwargs):
                turns.append(1)
                prompts.append(json.dumps(messages))
                if len(turns) == 1:
                    return "Thought: Consulto escenarios.\nAction: get_scenarios\nAction Input: {}"
                return "Thought: I now know the final answer\nFinal Answer: listo"

            def supports_function_calling(self):
                return False

        calls = []

        def caller(name, arguments):
            calls.append((name, arguments))
            return json.dumps({"status": 200, "body": {"payments": ["PROVIDER_ERROR_STUB"]}})

        tools = mcp_tools.build_crewai_tools(
            [{"name": "get_scenarios", "description": "d", "inputSchema": {"properties": {}}}], caller=caller
        )
        agent = qa_security.create_agent(ScriptedLLM(model="scripted"), tools)
        task = qa_security.create_task(agent, "Prueba de humo MCP.")
        Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False).kickoff()
        self.assertEqual(calls, [("get_scenarios", {})])
        self.assertIn("PROVIDER_ERROR_STUB", prompts[1])


if __name__ == "__main__":
    unittest.main()
