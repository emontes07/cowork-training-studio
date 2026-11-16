import os

import fastmcp
from fastmcp import FastMCP

from studio.tools.formats import list_session_formats
from studio.tools.validation import get_lab_spec_schema, validate_lab_spec

# Disable queued work and keep framework bookkeeping in-process, never external.
fastmcp.settings.docket.url = "memory://"
mcp = FastMCP(
    "Cowork Training Studio",
    auth=None,
    tasks=False,
    instructions=(
        "Provide consistent training formats for Cowork skills. "
        "Use fictional Zava-style scenarios only; never submit tenant data, "
        "real customer or person names, credentials, or secrets. "
        "Skills write content; Cowork built-ins save and send it."
    ),
)
mcp.tool(list_session_formats, task=False)
mcp.tool(get_lab_spec_schema, task=False)
mcp.tool(validate_lab_spec, task=False)


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
            # FastMCP defaults to zero grace; allow active requests to finish.
            uvicorn_config={"timeout_graceful_shutdown": 5},
        )
    else:
        raise ValueError("MCP_TRANSPORT must be stdio, http, or streamable-http.")


if __name__ == "__main__":
    main()
