from datetime import UTC, datetime
import json
import logging
import os
from time import perf_counter

import fastmcp
from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from studio.tools.formats import list_session_formats
from studio.tools.rendering import render_lab_page
from studio.tools.validation import get_lab_spec_schema, validate_lab_spec

# Disable queued work and keep framework bookkeeping in-process, never external.
fastmcp.settings.docket.url = "memory://"
mcp = FastMCP(
    "Cowork Training Studio",
    auth=None,
    tasks=False,
    instructions=(
        "Provide consistent training formats and a spec-first lab pipeline for Cowork skills. "
        "Call get_lab_spec_schema, draft a LabSpec, validate_lab_spec, then render_lab_page. "
        "Use fictional Zava-style scenarios only; never submit tenant data, "
        "real customer or person names, credentials, or secrets. "
        "Skills write content; Cowork built-ins save and send it."
    ),
)
mcp.tool(list_session_formats, task=False)
mcp.tool(get_lab_spec_schema, task=False)
mcp.tool(validate_lab_spec, task=False)
mcp.tool(render_lab_page, task=False)

_REQUEST_LOG = logging.getLogger("uvicorn.error.studio.requests")


class RequestLogging:
    """Log HTTP metadata only, without buffering requests or streaming responses."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = perf_counter()
        status = 500

        async def record_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, record_status)
        finally:
            user_agent = next(
                (value.decode("latin-1") for name, value in scope["headers"] if name.lower() == b"user-agent"),
                "",
            )
            _REQUEST_LOG.info(json.dumps({
                "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "method": scope["method"],
                "path": scope["path"],
                "status": status,
                "duration_ms": round((perf_counter() - started) * 1000, 3),
                "user_agent": user_agent,
            }))


class MCPPathAlias:
    """Serve the trailing-slash alias through the same MCP handler."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] == "/mcp/":
            scope = {**scope, "path": "/mcp", "raw_path": b"/mcp"}
        await self.app(scope, receive, send)


def main() -> None:
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport in {"http", "streamable-http"}:
        port = int(os.environ.get("PORT", "8000"))
        if not 1 <= port <= 65535:
            raise ValueError("PORT must be between 1 and 65535.")
        mcp.run(
            transport="streamable-http",
            host="0.0.0.0",
            port=port,
            path="/mcp",
            stateless_http=True,
            middleware=[Middleware(RequestLogging), Middleware(MCPPathAlias)],
            # FastMCP defaults to zero grace; allow active requests to finish.
            uvicorn_config={"timeout_graceful_shutdown": 5, "access_log": False},
        )
    else:
        raise ValueError("MCP_TRANSPORT must be stdio, http, or streamable-http.")


if __name__ == "__main__":
    main()
