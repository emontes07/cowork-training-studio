"""Verify the live stateless HTTP pipeline using the fictional golden fixture."""

import argparse
import asyncio
from copy import deepcopy
import json
from pathlib import Path
from time import perf_counter

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
import httpx
from mcp.shared._httpx_utils import create_mcp_http_client


async def smoke(url: str) -> None:
    root = Path(__file__).resolve().parents[1]
    fixture = root / "tests" / "fixtures" / "zava_story_lab.json"
    spec = json.loads(fixture.read_text(encoding="utf-8"))
    initialized = False
    render_responses: list[httpx.Response] = []

    async def inspect_request(request: httpx.Request) -> None:
        if request.method == "POST":
            message = json.loads(await request.aread())
            request.extensions["studio_mcp_method"] = message["method"]
            request.extensions["studio_mcp_tool"] = message.get("params", {}).get("name")

    async def inspect_response(response: httpx.Response) -> None:
        nonlocal initialized
        if response.request.method != "POST" or not response.is_success:
            return
        method = response.request.extensions.get("studio_mcp_method")
        if method == "initialize":
            assert "mcp-session-id" not in response.headers, "Unexpected persistent MCP session"
            initialized = True
        elif method == "tools/call" and response.request.extensions.get("studio_mcp_tool") == "render_lab_page":
            render_responses.append(response)

    def http_client_factory(
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
        follow_redirects: bool = True,
    ) -> httpx.AsyncClient:
        client = create_mcp_http_client(headers=headers, timeout=timeout, auth=auth)
        client.follow_redirects = follow_redirects
        client.event_hooks["request"].append(inspect_request)
        client.event_hooks["response"].append(inspect_response)
        return client

    transport = StreamableHttpTransport(url, httpx_client_factory=http_client_factory)
    async with Client(transport, timeout=30) as client:
        assert initialized, "Initialize response was not observed"
        print("initialize: succeeded; no mcp-session-id")
        names = {tool.name for tool in await client.list_tools()}
        expected = {"list_session_formats", "get_lab_spec_schema", "validate_lab_spec", "render_lab_page"}
        assert names == expected, f"Unexpected tools: {names}"
        print("tools/list:", ", ".join(sorted(names)))
        schema = (await client.call_tool("get_lab_spec_schema", {})).structured_content
        assert schema is not None
        assert {"schema_version", "chapters"} <= set(schema["required"])
        assert schema["properties"]["schema_version"]["const"] == "2.0"
        formats = (await client.call_tool("list_session_formats", {})).data
        assert len(formats) == 4
        print("list_session_formats: 4 formats")
        validation = (await client.call_tool("validate_lab_spec", {"spec": spec})).structured_content
        assert validation is not None
        assert validation["valid"] and not validation["errors"] and not validation["warnings"], validation
        print("validate_lab_spec:", json.dumps(validation["stats"], sort_keys=True))
        started = perf_counter()
        rendered = (await client.call_tool("render_lab_page", {"spec": spec})).structured_content
        elapsed = perf_counter() - started
        assert rendered is not None
        assert {"html", "filename", "stats", "warnings"} == set(rendered), "Render result must be top-level"
        assert rendered["html"].count("<html") == 1
        assert rendered["stats"] == validation["stats"]
        html_bytes = rendered["html"].encode("utf-8")
        assert html_bytes == (root / "examples" / "zava-story-lab.html").read_bytes(), "Golden HTML mismatch"
        assert not rendered["warnings"], rendered["warnings"]
        wire_bytes = sum(response.num_bytes_downloaded for response in render_responses)
        assert wire_bytes > 0, "Render response body was not measured"
        print("render_lab_page:", rendered["filename"], "(HTML returned, not saved)")
        print(f"Golden HTML: exact match ({len(html_bytes):,} UTF-8 bytes)")
        print(f"Render round-trip: {elapsed:.3f} seconds")
        print(f"Render HTTP body: {wire_bytes:,} wire bytes (MCP/SSE included; headers/TLS excluded)")
        invalid = deepcopy(spec)
        del invalid["chapters"]
        rejected = (await client.call_tool("render_lab_page", {"spec": invalid})).structured_content
        assert rejected is not None
        assert rejected["errors"] and "html" not in rejected
        print("Invalid spec: rejected without HTML")
        print("PASS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/mcp/", help="Streamable HTTP MCP endpoint")
    asyncio.run(smoke(parser.parse_args().url))
