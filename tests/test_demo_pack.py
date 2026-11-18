import asyncio
import json

from fastmcp import Client
from jsonschema import Draft202012Validator
from pydantic import ValidationError
import pytest

from main import mcp
from studio.schemas.demo_pack import Audience, ContextFact, DemoFile, Payoff, SeededItem, Tension
from studio.tools.demo_validation import get_demo_pack_schema


def test_demo_schema_exports_typed_evidence_and_strict_objects_through_mcp():
    schema = get_demo_pack_schema()
    Draft202012Validator.check_schema(schema)
    assert schema["properties"]["schema_version"]["const"] == "1.0"
    assert schema["additionalProperties"] is False
    assert schema["$defs"]["KeyFact"]["properties"]["kind"]["enum"] == ["number", "quote", "clause", "fact"]

    async def check():
        async with Client(mcp) as client:
            result = await client.call_tool_mcp("get_demo_pack_schema", {})
            assert not result.isError and result.structuredContent == schema
            assert result.content[0].type == "text"
            assert json.loads(result.content[0].text) == schema
    asyncio.run(check())


@pytest.mark.parametrize("href", ["http://example.test/a", "mailto:a@example.test", "javascript:alert(1)", "//example.test/a"])
def test_demo_href_policy_rejects_non_https_schemes(href):
    with pytest.raises(ValidationError):
        DemoFile(id="source", filename="source.csv", format="csv", purpose="Invented evidence",
                 used_by=[], contains_payoffs=[], href=href)


def test_missing_sources_and_evidence_are_structurally_optional():
    assert ContextFact(text="Public context needs a source.").source_url is None
    assert Payoff(id="finding", finding="Check 600 units.", scenario_id="review",
                  evidence_file_id="source", buried=True).evidence is None
    assert Audience(industry="Procurement").prefix is None


@pytest.mark.parametrize("due_date", ["2026-02-30", "20261118", "2026-11-18T00:00:00"])
def test_demo_dates_require_real_iso_calendar_dates(due_date):
    with pytest.raises(ValidationError):
        Tension(id="delay", problem="A fictional delivery is slipping.", due_date=due_date, slipping=True)


def test_seeded_items_exclude_chats_and_preserve_verbatim_body():
    values = dict(id="request", kind="email", from_cast_id="coordinator",
                  subject="Fictional practice", day_offset=0, body="  Verbatim body\n")
    assert SeededItem(**values).body == values["body"]
    with pytest.raises(ValidationError):
        SeededItem(**{**values, "kind": "chat"})
