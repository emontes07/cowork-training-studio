import asyncio
from copy import deepcopy
import json
from pathlib import Path

from fastmcp import Client
from jsonschema import Draft202012Validator
from pydantic import ValidationError
import pytest

from main import mcp
from studio.schemas.demo_pack import Audience, ContextFact, DemoFile, Payoff, SeededItem, Tension
from studio.tools.demo_validation import get_demo_pack_schema, validate_demo_pack
from studio.tools.demo_rendering import render_demo_guide


@pytest.fixture
def function_demo():
    return json.loads((Path(__file__).parent / "fixtures/demo_pack_function.json").read_text())


@pytest.fixture
def prompt_demo():
    return json.loads((Path(__file__).parent / "fixtures/demo_pack_prompt.json").read_text())


def mutate(spec, path, value):
    parts = [int(part) if part.isdigit() else part for part in path.split(".")]
    target = spec
    for part in parts[:-1]:
        target = target[part]
    target[parts[-1]] = value


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


@pytest.fixture
def small_demo():
    return {
        "schema_version": "1.0", "mode": "prompt_pack", "title": "Invented review",
        "as_of_date": "2026-11-18", "default_minutes": 10,
        "audience": {"industry": "Operations"},
        "context": {"business_model": [], "kpis": [], "pressures": [], "facts": [], "assumptions": []},
        "company": {"name": "Vellum Kite", "description": "All parties are fictional."},
        "presenter": {"role": "Facilitator"}, "source_prompt": "  Review a fictional delivery.\n",
        "cast": [], "tensions": [], "payoffs": [], "files": [],
        "scenarios": [{
            "id": "review", "function": "Operations", "title": "Check delivery", "persona": "Coordinator",
            "business_context": "An invented handoff", "input_file_ids": [], "prompt": "Review the invented handoff.",
            "expected_outputs": [], "payoff_ids": [], "talk_track": "Describe the result.",
            "follow_ups": ["Check the source.", "Review the handoff."],
        }],
        "run_of_show": [{"minutes": 10, "action": "Review the handoff.", "scenario_id": "review"}],
        "cleanup": ["Remove the fictional materials."],
        "disclaimer": "All people and data are fictional. Real customer names are used only as context.",
    }


def test_demo_missing_conditional_fields_and_unknown_agenda_reference(small_demo):
    assert validate_demo_pack(small_demo)["valid"]
    small_demo["run_of_show"][0]["scenario_id"] = "missing"
    result = validate_demo_pack(small_demo)
    assert [item["path"] for item in result["errors"]] == ["run_of_show.0.scenario_id"]
    small_demo["run_of_show"][0]["scenario_id"] = "review"
    del small_demo["source_prompt"]
    assert validate_demo_pack(small_demo)["errors"][0]["code"] == "missing_source_prompt"
    small_demo["mode"] = "function_pack"
    assert {"missing_prefix", "scenario_count", "output_formats"} <= {
        item["code"] for item in validate_demo_pack(small_demo)["errors"]
    }


def test_demo_validation_warnings_and_text_fallback_are_top_level(small_demo):
    async def check():
        async with Client(mcp) as client:
            result = await client.call_tool_mcp("validate_demo_pack", {"spec": small_demo})
            assert not result.isError and result.structuredContent == validate_demo_pack(small_demo)
            assert set(result.structuredContent) == {"valid", "errors", "warnings", "stats"}
            assert json.loads(result.content[0].text) == result.structuredContent
    asyncio.run(check())


def test_demo_renderer_escapes_prompt_keeps_presenter_notes_closed_and_returns_readme(small_demo):
    from test_rendering import parse

    prompt = '  <script>alert("fictional")</script>\n& <b>Do not execute</b>  '
    small_demo["scenarios"][0]["prompt"] = prompt
    result = render_demo_guide(small_demo)
    assert result["filename"] == "invented-review-demo-guide.html"
    page = parse(result["html"])
    assert page.pre_text == [prompt]
    assert sum(tag == "script" for tag, _ in page.tags) == 1
    notes = [attrs for tag, attrs in page.tags if tag == "details" and "presenter-payoffs" in attrs.get("class", "")]
    assert len(notes) == 1 and "open" not in notes[0]
    assert "context--facts" in page.ids and "context--assumptions" in page.ids
    assert "Demo pack approach adapted from work by Shailesh Mittal and Giovanna; see CREDITS.md" in result["readme_md"]
    small_demo["scenarios"][0]["input_file_ids"] = ["missing"]
    rejected = render_demo_guide(small_demo)
    assert set(rejected) == {"errors", "stats", "warnings"}


@pytest.mark.parametrize("fixture_name", ["function_demo", "prompt_demo"])
def test_demo_fixtures_are_clean_and_schema_valid(request, fixture_name):
    spec = request.getfixturevalue(fixture_name)
    original = deepcopy(spec)
    result = validate_demo_pack(spec)
    assert result["valid"] and result["errors"] == [] and result["warnings"] == []
    Draft202012Validator(get_demo_pack_schema()).validate(spec)
    if fixture_name == "function_demo":
        assert result["stats"] == {
            "scenario_count": 4, "file_count": 4, "cast_count": 7, "tension_count": 4,
            "payoff_count": 8, "buried_payoff_count": 2, "email_count": 3,
            "meeting_count": 1, "total_minutes": 20,
        }
    assert render_demo_guide(spec) == render_demo_guide(spec)
    assert spec == original


@pytest.mark.parametrize("path", [
    "files.0.used_by.0", "files.0.contains_payoffs.0", "scenarios.0.input_file_ids.0",
    "scenarios.0.payoff_ids.0", "payoffs.0.scenario_id", "payoffs.0.evidence_file_id",
    "payoffs.0.evidence.source_file", "seeded_items.0.from_cast_id",
    "tensions.0.owner_cast_id", "run_of_show.1.scenario_id",
])
def test_all_demo_references_resolve(function_demo, path):
    mutate(function_demo, path, "missing")
    result = validate_demo_pack(function_demo)
    assert not result["valid"]
    assert any(item["path"] == path and item["code"] == "unknown_reference" for item in result["errors"])
    assert "html" not in render_demo_guide(function_demo)


@pytest.mark.parametrize(("path", "value", "code"), [
    ("audience.prefix", "BUN", "prefix_mismatch"),
    ("audience.prefix", "zaV", "schema_error"),
    ("audience.prefix", None, "missing_prefix"),
    ("files.0.filename", "people.docx", "filename_prefix"),
    ("scenarios.0.expected_outputs.0.filename", "review.xlsx", "filename_prefix"),
    ("scenario_count", 3, "scenario_count"),
    ("scenarios.0.expected_outputs", [{"format": "docx", "filename": "ZAV_review.docx"}], "output_formats"),
    ("files.0.href", "javascript:alert(1)", "schema_error"),
    ("payoffs.0.evidence.kind", "invented", "schema_error"),
    ("cast.0.id", "controller", "duplicate_id"),
])
def test_demo_structural_errors(function_demo, path, value, code):
    mutate(function_demo, path, value)
    result = validate_demo_pack(function_demo)
    assert not result["valid"]
    assert code in {item["code"] for item in result["errors"]}


def test_declared_scenario_count_overrides_default_and_prompt_source_is_verbatim(function_demo, prompt_demo):
    # Remove one scenario and its dependent records to form a valid three-scenario pack.
    function_demo["scenarios"].pop()
    function_demo["payoffs"] = function_demo["payoffs"][:6]
    function_demo["files"].pop()
    function_demo["run_of_show"] = [row for row in function_demo["run_of_show"] if row.get("scenario_id") != "sales"]
    function_demo["default_minutes"] -= 4
    assert "scenario_count" in {item["code"] for item in validate_demo_pack(function_demo)["errors"]}
    function_demo["scenario_count"] = 3
    assert validate_demo_pack(function_demo)["errors"] == []
    from studio.schemas.demo_pack import DemoPackSpec
    assert DemoPackSpec.model_validate(prompt_demo).source_prompt == prompt_demo["source_prompt"]
    del prompt_demo["source_prompt"]
    assert validate_demo_pack(prompt_demo)["errors"][0]["code"] == "missing_source_prompt"


@pytest.mark.parametrize(("path", "value", "code"), [
    ("scenarios.0.talk_track", "word " * 40, "talk_track_length"),
    ("scenarios.0.payoff_ids", [], "scenario_without_payoff"),
    ("scenarios.0.input_file_ids", [], "payoff_input"),
    ("payoffs.1.buried", False, "buried_payoffs"),
    ("files.0.contains_payoffs", [], "file_without_payoffs"),
    ("cast.5.external", False, "missing_external"),
    ("cast.4.executive", False, "missing_executive"),
    ("tensions.0.slipping", False, "missing_slipping_tension"),
    ("tensions.0.due_date", "2026-11-17", "past_due_date"),
    ("context.facts.0.source_url", None, "missing_fact_source"),
    ("cast.0.name", "Zava Athletic Supply CFO", "customer_in_seeded_data"),
    ("company.name", "Zava Athletic Supply (demo data)", "customer_in_seeded_data"),
    ("seeded_items.0.body", "A request from Zava Athletics Supply.", "customer_in_seeded_data"),
    ("scenarios.1.function", "HR", "duplicate_function"),
    ("seeded_items.0.body", "Missing the fictional sender label.", "seeded_sender_label"),
    ("seeded_items.0.day_offset", 31, "seeded_date_range"),
    ("seeded_items.0.day_offset", -31, "seeded_date_range"),
    ("scenarios.0.prompt", "Read the JSON schema.", "learner_voice"),
    ("scenarios.0.talk_track", "Explain the MCP server.", "learner_voice"),
    ("files.0.purpose", "Read the tenant path.", "learner_voice"),
    ("payoffs.2.evidence", None, "missing_numeric_evidence"),
    ("payoffs.1.evidence.section", None, "clause_section"),
    ("payoffs.1.evidence.source_file", None, "key_fact_source"),
    ("default_minutes", 21, "run_of_show_minutes"),
    ("disclaimer", "A demonstration.", "demo_disclaimer"),
])
def test_demo_quality_warnings_never_block_rendering(function_demo, path, value, code):
    mutate(function_demo, path, value)
    result = validate_demo_pack(function_demo)
    assert result["valid"] and not result["errors"]
    matches = [item for item in result["warnings"] if item["code"] == code]
    assert matches and all(item["path"] and item["message"] and "\n" not in item["message"] for item in matches)
    assert "html" in render_demo_guide(function_demo)
    if code == "talk_track_length":
        assert "40 words" in matches[0]["message"]
    if code == "customer_in_seeded_data":
        assert all(item["message"] == "Use a fictional stand-in company; keep the customer name in the audience/title only." for item in matches)


@pytest.mark.parametrize("change", ["unused_payoff", "unused_file", "cast_size", "tension_count", "duplicate_assumption", "empty_context", "similar_prompts"])
def test_remaining_demo_quality_groups(function_demo, change):
    if change == "unused_payoff":
        function_demo["scenarios"][0]["payoff_ids"].pop()
    elif change == "unused_file":
        function_demo["scenarios"][0]["input_file_ids"].clear()
    elif change == "cast_size":
        for index in range(3):
            function_demo["cast"].append({**function_demo["cast"][0], "id": f"extra-{index}", "name": f"Invented helper {index}"})
    elif change == "tension_count":
        function_demo["tensions"] = function_demo["tensions"][:2]
    elif change == "duplicate_assumption":
        function_demo["context"]["assumptions"] = [function_demo["context"]["facts"][0]["text"].upper()]
    elif change == "empty_context":
        function_demo["context"] = dict.fromkeys(function_demo["context"], [])
    else:
        function_demo["scenarios"][1]["prompt"] = function_demo["scenarios"][0]["prompt"]
    result = validate_demo_pack(function_demo)
    assert result["valid"]
    assert change in {item["code"] for item in result["warnings"]}


@pytest.mark.parametrize(("kind", "total"), [("email", 9), ("meeting", 6)])
def test_demo_seeded_item_limits(function_demo, kind, total):
    item = next(item for item in function_demo["seeded_items"] if item["kind"] == kind)
    function_demo["seeded_items"] = [{**item, "id": f"seed-{index}"} for index in range(total)]
    result = validate_demo_pack(function_demo)
    assert result["valid"]
    assert "seeded_item_count" in {item["code"] for item in result["warnings"]}


@pytest.mark.parametrize("missing", ["missing_advice_note", "missing_expert_questions", "missing_fictional_parties"])
def test_demo_sensitive_domain_safeguards(function_demo, missing):
    if missing == "missing_advice_note":
        function_demo["disclaimer"] = function_demo["disclaimer"].replace("not professional advice", "review before use")
    elif missing == "missing_expert_questions":
        function_demo["scenarios"][0]["prompt"] = "Read the invented policy and compare it with the roster."
    else:
        function_demo["company"]["description"] = "An invented supplier of recreational equipment."
    result = validate_demo_pack(function_demo)
    assert result["valid"]
    assert missing in {item["code"] for item in result["warnings"]}


@pytest.mark.parametrize(("words", "warns"), [(149, True), (150, False), (300, False), (301, True)])
def test_talk_track_exact_boundaries(function_demo, words, warns):
    function_demo["scenarios"][0]["talk_track"] = "word " * words
    assert ("talk_track_length" in {i["code"] for i in validate_demo_pack(function_demo)["warnings"]}) is warns


@pytest.mark.parametrize(("length", "warns"), [(79, False), (80, True)])
def test_prompt_similarity_exact_contiguous_threshold(function_demo, length, warns):
    function_demo["scenarios"][2]["prompt"] = "x" * length + "A"
    function_demo["scenarios"][3]["prompt"] = "x" * length + "B"
    assert ("similar_prompts" in {i["code"] for i in validate_demo_pack(function_demo)["warnings"]}) is warns


def test_customer_names_only_in_approved_context_and_close_variants_warn(function_demo):
    for variant in ("ZAVA-ATHLETIC-SUPPLY", "Zava Athletics Supply", "Zava Athletic Supply Inc."):
        function_demo["company"]["name"] = variant
        result = validate_demo_pack(function_demo)
        assert any(i["code"] == "customer_in_seeded_data" and i["path"] == "company.name" for i in result["warnings"])
    function_demo["company"]["name"] = "Vellum Kite Outfitters"
    function_demo["scenarios"][0]["talk_track"] += " For the Zava Athletic Supply audience."
    assert validate_demo_pack(function_demo)["warnings"] == []


@pytest.mark.parametrize(("disclaimer", "warns"), [
    ("All people and data are fictional.", False),
    ("A demonstration.", True),
])
def test_unnamed_prompt_pack_requires_only_fictional_disclaimer(prompt_demo, disclaimer, warns):
    assert not prompt_demo["audience"].get("customer_name")
    prompt_demo["disclaimer"] = disclaimer
    result = validate_demo_pack(prompt_demo)
    assert result["valid"] and result["errors"] == []
    assert result["warnings"] == ([{
        "code": "demo_disclaimer", "path": "disclaimer",
        "message": "State 'All people and data are fictional.'",
    }] if warns else [])


def test_named_function_pack_still_requires_customer_context_disclaimer(function_demo):
    assert function_demo["audience"]["customer_name"]
    function_demo["disclaimer"] = function_demo["disclaimer"].replace(
        "Real customer names are used only as context.", ""
    ).strip()
    result = validate_demo_pack(function_demo)
    assert result["valid"] and result["errors"] == []
    assert result["warnings"] == [{
        "code": "demo_disclaimer", "path": "disclaimer",
        "message": "State 'All people and data are fictional. Real customer names are used only as context.'",
    }]


def test_demo_guide_links_only_attendee_files_and_readme_is_escaped(function_demo):
    from test_rendering import parse
    function_demo["company"]["description"] += " <script>unsafe</script> [link](javascript:bad)"
    function_demo["files"][1]["href"] = 'https://example.test/a?x=1&y="quoted"'
    rendered = render_demo_guide(function_demo)
    page = parse(rendered["html"])
    links = [attrs for tag, attrs in page.tags if tag == "a"]
    assert not any(link.get("href") == function_demo["files"][0]["href"] for link in links)
    attendee = next(link for link in links if link.get("download") == function_demo["files"][1]["filename"])
    assert attendee["href"] == function_demo["files"][1]["href"]
    assert attendee["target"] == "_blank" and attendee["rel"] == "noopener noreferrer"
    assert sum("presenter-payoffs" in attrs.get("class", "") and "open" not in attrs for tag, attrs in page.tags if tag == "details") == 4
    assert len(page.ids) == len(set(page.ids))
    assert all(link["href"][1:] in page.ids for link in links if link.get("href", "").startswith("#"))
    assert page.pre_text[:4] == [scenario["prompt"] for scenario in function_demo["scenarios"]]
    assert "context--facts" in page.ids and "context--assumptions" in page.ids
    assert "<script>unsafe</script>" not in rendered["readme_md"]
    assert "[link](javascript:bad)" not in rendered["readme_md"]
    assert "Demo pack approach adapted from work by Shailesh Mittal and Giovanna; see CREDITS.md" in rendered["readme_md"]


@pytest.mark.parametrize("name", ["get_demo_pack_schema", "validate_demo_pack", "render_demo_guide"])
def test_all_demo_tools_return_top_level_structured_results_and_text(function_demo, name):
    async def check():
        from scripts.build_plugin import TOOL_FIELDS, sanitize_tools
        async with Client(mcp) as client:
            arguments = {} if name == "get_demo_pack_schema" else {"spec": function_demo}
            result = await client.call_tool_mcp(name, arguments)
            assert not result.isError and result.structuredContent is not None
            assert "result" not in result.structuredContent
            assert result.content[0].type == "text"
            assert json.loads(result.content[0].text) == result.structuredContent
            tools = await client.list_tools()
            tool = next(tool for tool in tools if tool.name == name)
            assert tool.annotations.readOnlyHint
            Draft202012Validator(tool.outputSchema).validate(result.structuredContent)
            catalog = sanitize_tools([tool.model_dump(mode="json", by_alias=True, include=TOOL_FIELDS, exclude_none=True) for tool in tools])
            assert len(catalog) == 8
            for entry in catalog:
                for key in ("inputSchema", "outputSchema"):
                    Draft202012Validator.check_schema(entry[key])
                    assert not any(term in json.dumps(entry[key]) for term in ('"$ref"', '"$defs"', '"x-'))
                if entry["name"] in {"validate_demo_pack", "render_demo_guide"}:
                    assert entry["inputSchema"]["properties"]["spec"] == {
                        "type": "object", "additionalProperties": True,
                        "description": "Call get_demo_pack_schema first and follow it",
                    }
    asyncio.run(check())
