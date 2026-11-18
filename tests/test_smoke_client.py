import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from studio.tools.formats import list_session_formats
from studio.tools.rendering import render_lab_page
from studio.tools.validation import get_lab_spec_schema, validate_lab_spec


@pytest.mark.parametrize("failure", [None, "session", "golden"])
def test_smoke_redirects_streamed_requests_and_checks_results(monkeypatch, capsys, failure):
    module_spec = importlib.util.spec_from_file_location(
        "smoke_client", Path(__file__).resolve().parents[1] / "scripts" / "smoke_client.py",
    )
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    expected_wire_bytes = []
    tools = {
        "list_session_formats": list_session_formats,
        "get_lab_spec_schema": get_lab_spec_schema,
        "validate_lab_spec": validate_lab_spec,
        "render_lab_page": render_lab_page,
    }

    class Transport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            body = b"".join([chunk async for chunk in request.stream])
            if request.url.path == "/mcp/":
                return httpx.Response(307, headers={"location": "/mcp"})
            message = json.loads(body)
            headers = {}
            if message["method"] == "initialize":
                result = {}
                if failure == "session":
                    headers["mcp-session-id"] = "unexpected-session"
            else:
                name = message["params"]["name"]
                result = tools[name](**message["params"]["arguments"])
                if name == "render_lab_page":
                    if failure == "golden" and "html" in result:
                        result["html"] += "\n"
            wire = json.dumps(result).encode("utf-8")
            if message.get("params", {}).get("name") == "render_lab_page" and "html" in result:
                expected_wire_bytes.append(len(wire))
            return httpx.Response(200, headers=headers, stream=httpx.ByteStream(wire))

    def http_client(**kwargs):
        return httpx.AsyncClient(transport=Transport(), **kwargs)

    class Client:
        def __init__(self, transport, timeout):
            self.url = transport.url
            self.http = transport.httpx_client_factory(follow_redirects=True)

        async def post(self, message):
            async def body():
                yield json.dumps(message).encode("utf-8")

            response = await self.http.post(self.url, content=body())
            response.raise_for_status()
            return response.json()

        async def __aenter__(self):
            await self.post({"method": "initialize"})
            return self

        async def __aexit__(self, *args):
            await self.http.aclose()

        async def list_tools(self):
            return [SimpleNamespace(name=name) for name in tools]

        async def call_tool(self, name, arguments):
            result = await self.post({
                "method": "tools/call", "params": {"name": name, "arguments": arguments},
            })
            return SimpleNamespace(data=result, structured_content=result)

    monkeypatch.setattr(module, "create_mcp_http_client", http_client)
    monkeypatch.setattr(module, "Client", Client)
    if failure:
        message = "Unexpected persistent MCP session" if failure == "session" else "Golden HTML mismatch"
        with pytest.raises(AssertionError, match=message):
            asyncio.run(module.smoke("https://mcp.example.test/mcp/"))
    else:
        asyncio.run(module.smoke("https://mcp.example.test/mcp/"))
        output = capsys.readouterr().out
        assert f"Render HTTP body: {expected_wire_bytes[0]:,} wire bytes" in output
        assert "Golden HTML: exact match" in output and "PASS" in output
