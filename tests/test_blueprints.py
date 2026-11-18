import asyncio
from copy import deepcopy
import json

from fastmcp import Client
from jsonschema import Draft202012Validator
import pytest

from main import mcp
from scripts.build_plugin import TOOL_FIELDS, sanitize_tools
from studio.tools.blueprints import get_blueprint

IDS = ["app_deep_dive", "prompt_to_agent_ladder", "domain_super_day"]
BLOCKLIST = ["Kroger", "Coca-Cola", "Newell", "Sysco"]


def test_blueprint_list_contains_only_summaries():
    result = get_blueprint()
    assert set(result) == {"blueprints"}
    assert [item["id"] for item in result["blueprints"]] == IDS
    assert [item["default_minutes"] for item in result["blueprints"]] == [60, 90, 300]
    for item in result["blueprints"]:
        assert set(item) == {"id", "title", "default_minutes", "best_for"}
        detail = get_blueprint(item["id"])
        assert item == {key: detail[key] for key in item}


@pytest.mark.parametrize("identifier", IDS)
def test_blueprint_details_have_generic_content_and_balanced_minutes(identifier):
    result = get_blueprint(identifier)
    assert set(result) == {
        "id", "title", "default_minutes", "best_for", "required_inputs",
        "chapter_outline", "quality_bar", "ends_with",
    } | ({"lab_outlines"} if identifier == "domain_super_day" else set())
    assert result["id"] == identifier
    assert result["required_inputs"] and result["quality_bar"] and result["ends_with"]
    assert sum(chapter["minutes"] for chapter in result["chapter_outline"]) == result["default_minutes"]
    for chapter in result["chapter_outline"]:
        assert chapter["minutes"] > 0 and chapter["purpose"] and chapter["step_patterns"]
    encoded = json.dumps(result).casefold()
    assert all(brand.casefold() not in encoded for brand in BLOCKLIST)
    assert "test on new data" in encoded


def test_super_day_agenda_matches_every_separate_html_lab():
    day = get_blueprint("domain_super_day")
    labs = {lab["id"]: lab for lab in day["lab_outlines"]}
    assert len(labs) == len(day["lab_outlines"]) == 5
    agenda_labs = [slot for slot in day["chapter_outline"] if "lab_id" in slot]
    assert len(agenda_labs) == 5
    assert {slot["lab_id"] for slot in agenda_labs} == set(labs)
    assert sum(slot["minutes"] for slot in day["chapter_outline"]) == day["default_minutes"] == 300
    for slot in day["chapter_outline"]:
        if "lab_id" not in slot:
            assert slot["step_patterns"] == ["break"]
            continue
        lab = labs[slot["lab_id"]]
        assert slot["title"] == lab["title"]
        assert slot["minutes"] == lab["default_minutes"]
        assert sum(chapter["minutes"] for chapter in lab["chapter_outline"]) == lab["default_minutes"]
        assert lab["format_id"] == "html_lab"
        assert 2 <= len(lab["chapter_outline"]) <= 10
    close = next(slot for slot in agenda_labs if slot["lab_id"] == "challenge-close")
    assert "prompt_a_thon" in close["purpose"] and "when that format ships" in close["purpose"]


@pytest.mark.parametrize("identifier", ["missing", "", "APP_DEEP_DIVE"])
def test_unknown_blueprint_fails_explicitly(identifier):
    with pytest.raises(ValueError, match="Unknown blueprint id"):
        get_blueprint(identifier)


def test_blueprint_results_are_not_shared_mutable_state():
    original = deepcopy(get_blueprint("domain_super_day"))
    result = get_blueprint("domain_super_day")
    result["lab_outlines"][0]["chapter_outline"][0]["step_patterns"].clear()
    result["chapter_outline"].clear()
    assert get_blueprint("domain_super_day") == original
    summaries = get_blueprint()
    summaries["blueprints"][0]["best_for"].clear()
    assert get_blueprint()["blueprints"][0]["best_for"]


@pytest.mark.parametrize("identifier", [None, *IDS])
def test_mcp_blueprints_are_top_level_with_equivalent_text_and_sanitized_catalog(identifier):
    async def check():
        async with Client(mcp) as client:
            result = await client.call_tool_mcp(
                "get_blueprint", {} if identifier is None else {"blueprint_id": identifier},
            )
            assert not result.isError
            assert result.structuredContent == get_blueprint(identifier)
            assert len(result.content) == 1
            assert result.content[0].type == "text"
            assert json.loads(result.content[0].text) == result.structuredContent
            tools = await client.list_tools()
            blueprint_tool = next(tool for tool in tools if tool.name == "get_blueprint")
            assert blueprint_tool.annotations.readOnlyHint is True
            Draft202012Validator(blueprint_tool.outputSchema).validate(result.structuredContent)
            sanitized = sanitize_tools([
                tool.model_dump(mode="json", by_alias=True, include=TOOL_FIELDS, exclude_none=True)
                for tool in tools
            ])
            assert len(sanitized) == 5
            for tool in sanitized:
                for key in ("inputSchema", "outputSchema"):
                    Draft202012Validator.check_schema(tool[key])
                    assert not any(term in json.dumps(tool[key]) for term in ('"$ref"', '"$defs"', '"x-'))

    asyncio.run(check())
