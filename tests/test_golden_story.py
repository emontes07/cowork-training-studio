import asyncio
import json
from pathlib import Path

import pytest

from studio.schemas.lab_spec import LabSpec
from studio.tools.rendering import render_lab_page
from studio.tools.validation import validate_lab_spec
from test_rendering import parse

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def golden_spec():
    return json.loads((ROOT / "tests" / "fixtures" / "zava_story_lab.json").read_text(encoding="utf-8"))


def test_golden_story_contract_and_render(golden_spec):
    assert LabSpec.model_validate(golden_spec).schema_version == "2.0"
    validation = validate_lab_spec(golden_spec)
    assert validation["valid"] and validation["errors"] == [] and validation["warnings"] == []
    assert validation["stats"] == {
        "chapter_count": 5, "step_count": 10, "prompt_count": 20, "challenge_count": 1,
        "checkpoint_count": 3, "total_minutes": 90,
        "files_by_kind": {"source": 2, "checkpoint": 3, "answer_key": 1, "worksheet": 1, "extra": 3},
    }
    result = render_lab_page(golden_spec)
    assert result["warnings"] == []
    page = parse(result["html"])
    assert sum(tag == "html" for tag, _ in page.tags) == 1
    for chapter in golden_spec["chapters"]:
        assert chapter["id"] in page.ids
        assert sum(step["minutes"] for step in chapter["steps"]) == chapter["minutes"]
        assert all(step["id"] in page.ids for step in chapter["steps"])
    assert len(page.ids) == len(set(page.ids))
    assert len(page.copies) == validation["stats"]["prompt_count"]
    assert result["html"].count("Behind? Jump in here") == 3
    assert len(page.answer_parents) == 1
    assert page.answer_parents[0][-1]["class"] == "answer"
    assert "open" not in page.answer_parents[0][-1]
    assert not any(file.get("href") for file in golden_spec["files"])
    assert not any("download" in attrs for _, attrs in page.tags)
    assert sum(
        "provided-separately" in attrs.get("class", "").split() for _, attrs in page.tags
    ) == len(golden_spec["files"]) + 3
    assert not any(
        attrs.get("src") or attrs.get("href")
        for tag, attrs in page.tags if tag in {"script", "link", "img", "iframe"}
    )
    assert result["html"] == (ROOT / "examples" / "zava-story-lab.html").read_text(encoding="utf-8")


def test_golden_page_within_size_budget(golden_spec, capsys, record_property):
    result = render_lab_page(golden_spec)
    assert "html" in result
    size_bytes = len(result["html"].encode("utf-8"))
    record_property("rendered_html_bytes", size_bytes)
    with capsys.disabled():
        print(f"\nRendered story HTML: {size_bytes:,} bytes; budget: 400,000 bytes")
    assert size_bytes <= 400_000, (
        f"Rendered golden page is {size_bytes:,} bytes; exceeds 400 KB (400,000 bytes)."
    )


@pytest.mark.parametrize("valid", [True, False])
def test_raw_mcp_results_are_top_level_with_text_fallback(golden_spec, valid):
    from fastmcp import Client
    from main import mcp

    if not valid:
        del golden_spec["chapters"]

    async def check():
        async with Client(mcp) as client:
            for name in ("validate_lab_spec", "render_lab_page"):
                raw = await client.call_tool_mcp(name, {"spec": golden_spec})
                assert raw.isError is False
                structured = raw.structuredContent
                assert structured is not None and "result" not in structured
                assert len(raw.content) == 1 and raw.content[0].type == "text"
                assert json.loads(raw.content[0].text) == structured
                if name == "validate_lab_spec":
                    assert set(structured) == {"valid", "errors", "warnings", "stats"}
                    assert structured["valid"] is valid
                elif valid:
                    assert set(structured) == {"html", "filename", "stats", "warnings"}
                    assert structured["filename"].endswith(".html")
                    assert structured["html"].encode() == (ROOT / "examples/zava-story-lab.html").read_bytes()
                else:
                    assert set(structured) == {"errors", "warnings", "stats"}
                    assert structured["errors"]

    asyncio.run(check())
