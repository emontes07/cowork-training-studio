import asyncio
from datetime import datetime, timedelta
import json
import logging

import pytest
from starlette.middleware import Middleware
from starlette.testclient import TestClient

import main as server


@pytest.mark.parametrize(("path", "status"), [("/mcp/", 200), ("/missing", 404)])
def test_request_logs_only_safe_metadata(caplog, monkeypatch, path, status):
    clock = iter([10.0, 10.1234])
    monkeypatch.setattr(server, "perf_counter", lambda: next(clock))
    app = server.mcp.http_app(
        path="/mcp", stateless_http=True,
        middleware=[Middleware(server.RequestLogging), Middleware(server.MCPPathAlias)],
    )
    with caplog.at_level(logging.INFO, logger=server._REQUEST_LOG.name):
        with TestClient(app, follow_redirects=False) as client:
            response = client.post(path + "?token=private-query", headers={
                "Accept": "application/json, text/event-stream",
                "User-Agent": "test-client/1.0\nforged-log-line",
                "Authorization": "Bearer private-auth",
                "Cookie": "private-cookie",
            }, json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26", "capabilities": {},
                    "clientInfo": {"name": "private-body", "version": "1.0"},
                },
            })
    assert response.status_code == status
    entries = [record.getMessage() for record in caplog.records if record.name == server._REQUEST_LOG.name]
    assert len(entries) == 1 and len(entries[0].splitlines()) == 1
    record = json.loads(entries[0])
    assert set(record) == {"timestamp", "method", "path", "status", "duration_ms", "user_agent"}
    assert record["timestamp"].endswith("Z")
    assert datetime.fromisoformat(record["timestamp"]).utcoffset() == timedelta(0)
    assert record["method"] == "POST" and record["path"] == path
    assert record["status"] == status and record["duration_ms"] == 123.4
    assert record["user_agent"] == "test-client/1.0\nforged-log-line"
    assert "private-" not in entries[0]
    if status == 200:
        assert "data: " in response.text and "location" not in response.headers


def test_request_failure_is_logged_without_swallowing_exception(caplog):
    async def failing_app(scope, receive, send):
        raise RuntimeError("private-error-detail")

    async def unused():
        raise AssertionError("Unexpected I/O")

    middleware = server.RequestLogging(failing_app)
    with caplog.at_level(logging.INFO, logger=server._REQUEST_LOG.name):
        with pytest.raises(RuntimeError, match="private-error-detail"):
            asyncio.run(middleware({
                "type": "http", "method": "POST", "path": "/mcp", "headers": [],
            }, unused, unused))
    entry = next(record.getMessage() for record in caplog.records if record.name == server._REQUEST_LOG.name)
    assert json.loads(entry)["status"] == 500
    assert "private-error-detail" not in entry
