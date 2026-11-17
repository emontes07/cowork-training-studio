"""Verify the live stateless HTTP pipeline using the fictional golden fixture."""

import argparse
import asyncio
from copy import deepcopy
import json
from pathlib import Path

from fastmcp import Client


async def smoke(url: str) -> None:
    fixture = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "zava_story_lab.json"
    spec = json.loads(fixture.read_text(encoding="utf-8"))
    async with Client(url, timeout=30) as client:
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
        assert validation["valid"] and not validation["warnings"], validation
        print("validate_lab_spec:", json.dumps(validation["stats"], sort_keys=True))
        envelope = (await client.call_tool("render_lab_page", {"spec": spec})).structured_content
        assert envelope is not None
        # FastMCP wraps union return schemas in a structured-content result field.
        rendered = envelope["result"]
        assert rendered["html"].count("<html") == 1
        assert rendered["stats"] == validation["stats"]
        print("render_lab_page:", rendered["filename"], "(HTML returned, not saved)")
        invalid = deepcopy(spec)
        del invalid["chapters"]
        envelope = (await client.call_tool("render_lab_page", {"spec": invalid})).structured_content
        assert envelope is not None
        rejected = envelope["result"]
        assert rejected["errors"] and "html" not in rejected
        print("Invalid spec: rejected without HTML")
        print("PASS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/mcp")
    asyncio.run(smoke(parser.parse_args().url))
