import asyncio
import builtins
import importlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from studio.tools.formats import list_session_formats


def test_catalog_is_complete_and_json_serializable():
    formats = list_session_formats()

    assert [item["id"] for item in formats] == [
        "html_lab",
        "word_guide",
        "demo_pack",
        "prompt_a_thon",
    ]
    assert json.loads(json.dumps(formats)) == formats
    for item in formats:
        assert set(item) == {
            "id",
            "name",
            "description",
            "status",
            "best_for",
            "required_inputs",
            "default_duration_minutes",
            "produced_by_skill",
        }
        assert item["name"] and item["description"]
        assert item["best_for"] and all(item["best_for"])
        assert isinstance(item["default_duration_minutes"], int)
        assert item["default_duration_minutes"] > 0
        assert item["status"] in {"available", "coming_soon"}
        assert item["produced_by_skill"] in {"build-training-lab", "build-demo-pack", None}
        assert item["required_inputs"]
        input_names = [field["name"] for field in item["required_inputs"]]
        assert len(input_names) == len(set(input_names))
        for field in item["required_inputs"]:
            assert set(field) == {"name", "description", "example"}
            assert all(isinstance(value, str) and value for value in field.values())


def test_format_skills_are_shipped_and_planned_formats_are_unavailable():
    skills = Path(__file__).resolve().parents[1] / "plugin" / "skills"
    for item in list_session_formats():
        skill = item["produced_by_skill"]
        if skill is not None:
            assert (skills / skill / "SKILL.md").is_file(), f"Unshipped skill: {skill}"
            assert item["status"] == "available"
        else:
            assert item["status"] == "coming_soon"
            assert "not available yet; planned" in item["description"].casefold()
    assert list_session_formats("html_lab")[0]["produced_by_skill"] == "build-training-lab"
    assert list_session_formats("demo_pack")[0]["produced_by_skill"] == "build-demo-pack"
    assert all(
        list_session_formats(identifier)[0]["produced_by_skill"] is None
        for identifier in ("word_guide", "prompt_a_thon")
    )


@pytest.mark.parametrize("id", [None, "html_lab", "demo_pack"])
def test_format_catalog_satisfies_live_mcp_output_schema(id):
    from fastmcp import Client
    from main import mcp

    async def check():
        async with Client(mcp) as client:
            result = await client.call_tool_mcp("list_session_formats", {"id": id})
            assert result.isError is False
            assert result.structuredContent == {"result": list_session_formats(id)}

    asyncio.run(check())


@pytest.mark.parametrize("id", ["html_lab", "word_guide", "demo_pack", "prompt_a_thon"])
def test_filter_returns_one_item_list(id):
    assert list_session_formats(id) == [
        item for item in list_session_formats() if item["id"] == id
    ]
    assert len(list_session_formats(id)) == 1


@pytest.mark.parametrize("id", ["missing", "", "HTML_LAB"])
def test_unknown_filter_raises_explicit_error(id):
    with pytest.raises(ValueError, match="Unknown session format id"):
        list_session_formats(id)


@pytest.mark.parametrize("id", [None, "html_lab"])
def test_result_mutation_does_not_change_loaded_catalog(id):
    original = list_session_formats()
    result = list_session_formats(id)
    result[0]["required_inputs"][0]["example"] = "Changed by caller"
    result[0]["best_for"].clear()
    result.clear()

    assert list_session_formats() == original


def test_calls_do_not_reload_data_or_depend_on_working_directory(monkeypatch, tmp_path):
    def unexpected_open(*args, **kwargs):
        raise AssertionError("Catalog must be loaded once at import, not per call")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "open", unexpected_open)

    assert len(list_session_formats()) == 4
    assert list_session_formats("html_lab")[0]["id"] == "html_lab"


def test_server_registration_keeps_tool_directly_callable():
    importlib.import_module("main")

    assert callable(list_session_formats)
    assert list_session_formats("html_lab")[0]["id"] == "html_lab"


def test_tasks_disabled_memory_only_and_tool_calls_write_no_files(monkeypatch, tmp_path):
    import fastmcp

    monkeypatch.setattr(fastmcp.settings.docket, "url", "redis://127.0.0.1:1/0")
    server = importlib.reload(importlib.import_module("main"))

    assert server.mcp._support_tasks_by_default is False
    assert fastmcp.settings.docket.url == "memory://"
    tools = asyncio.run(server.mcp.get_tools())
    assert tools["list_session_formats"].task_config.mode == "forbidden"

    working_directory = tmp_path / "working"
    temporary_directory = tmp_path / "temporary"
    working_directory.mkdir()
    temporary_directory.mkdir()
    monkeypatch.chdir(working_directory)
    for variable in ("TMPDIR", "TMP", "TEMP"):
        monkeypatch.setenv(variable, str(temporary_directory))
    monkeypatch.setattr(tempfile, "tempdir", str(temporary_directory))

    def unexpected_file_access(*args, **kwargs):
        raise AssertionError("Tool calls must not open or create files")

    # Also catch temporary files that would be deleted before a directory check.
    with monkeypatch.context() as no_file_io:
        no_file_io.setattr(builtins, "open", unexpected_file_access)
        no_file_io.setattr(io, "open", unexpected_file_access)
        no_file_io.setattr(os, "open", unexpected_file_access)
        formats = list_session_formats()
        filtered = list_session_formats("html_lab")

    assert len(formats) == 4
    assert len(filtered) == 1
    assert list(working_directory.iterdir()) == []
    assert list(temporary_directory.iterdir()) == []


@pytest.mark.parametrize("transport", [None, "stdio"])
def test_stdio_is_default_and_does_not_read_http_port(monkeypatch, transport):
    server = importlib.import_module("main")
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)
    if transport is not None:
        monkeypatch.setenv("MCP_TRANSPORT", transport)
    monkeypatch.setenv("PORT", "not-an-http-port")
    calls = []
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: calls.append(kwargs))

    server.main()

    assert calls == [{"transport": "stdio"}]


@pytest.mark.parametrize("transport", ["http", "streamable-http"])
@pytest.mark.parametrize("port", [None, "8123"])
def test_http_aliases_use_stateless_transport(monkeypatch, transport, port):
    server = importlib.import_module("main")
    monkeypatch.setenv("MCP_TRANSPORT", transport)
    monkeypatch.delenv("PORT", raising=False)
    if port is not None:
        monkeypatch.setenv("PORT", port)
    calls = []
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: calls.append(kwargs))

    server.main()

    middleware = calls[0].pop("middleware")
    assert [item.cls for item in middleware] == [server.RequestLogging, server.MCPPathAlias]
    assert calls == [
        {
            "transport": "streamable-http",
            "host": "0.0.0.0",
            "port": 8000 if port is None else int(port),
            "path": "/mcp",
            "stateless_http": True,
            "uvicorn_config": {"timeout_graceful_shutdown": 5, "access_log": False},
        }
    ]


@pytest.mark.parametrize("path", ["/mcp", "/mcp/"])
def test_http_paths_initialize_without_redirect_or_session(path):
    from starlette.middleware import Middleware
    from starlette.testclient import TestClient

    server = importlib.import_module("main")
    app = server.mcp.http_app(
        path="/mcp", stateless_http=True,
        middleware=[Middleware(server.MCPPathAlias)],
    )
    with TestClient(app, follow_redirects=False) as client:
        response = client.post(path, headers={
            "Accept": "application/json, text/event-stream",
        }, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26", "capabilities": {},
                "clientInfo": {"name": "endpoint-test", "version": "1.0"},
            },
        })
        assert response.status_code == 200
        assert "location" not in response.headers
        assert "mcp-session-id" not in response.headers
        data = next(line[6:] for line in response.text.splitlines() if line.startswith("data: "))
        assert json.loads(data)["result"]["serverInfo"]["name"] == "Cowork Training Studio"
        assert client.get("/not-mcp").status_code == 404


@pytest.mark.parametrize(
    ("transport", "port", "message"),
    [
        ("sse", "8000", "MCP_TRANSPORT must be"),
        ("streamable-http", "0", "PORT must be"),
        ("streamable-http", "65536", "PORT must be"),
        ("streamable-http", "invalid", "invalid literal"),
    ],
)
def test_invalid_runtime_configuration_fails_before_startup(
    monkeypatch, transport, port, message
):
    server = importlib.import_module("main")
    monkeypatch.setenv("MCP_TRANSPORT", transport)
    monkeypatch.setenv("PORT", port)

    def unexpected_run(**kwargs):
        raise AssertionError("Invalid configuration must not start a server")

    monkeypatch.setattr(server.mcp, "run", unexpected_run)

    with pytest.raises(ValueError, match=message):
        server.main()
