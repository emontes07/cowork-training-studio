import asyncio
import builtins
from copy import deepcopy
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import tempfile

import pytest

from studio.schemas.lab_spec import LabSpec
from studio.tools.rendering import render_lab_page
from studio.tools.validation import get_lab_spec_schema, validate_lab_spec

ROOT = Path(__file__).resolve().parents[1]


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.ids = []
        self.copies = []
        self.pre_text = []
        self.in_pre = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.tags.append((tag, attributes))
        if "id" in attributes:
            self.ids.append(attributes["id"])
        if tag == "button" and "copy-button" in attributes.get("class", "").split():
            self.copies.append(attributes)
        if tag == "pre":
            self.in_pre = True
            self.pre_text.append("")

    def handle_endtag(self, tag):
        if tag == "pre":
            self.in_pre = False

    def handle_data(self, data):
        if self.in_pre:
            self.pre_text[-1] += data


@pytest.fixture
def golden_spec():
    return json.loads((ROOT / "tests" / "fixtures" / "zava_finance_lab.json").read_text())


def parse(html):
    parser = PageParser()
    parser.feed(html)
    parser.close()
    return parser


def test_golden_schema_stats_and_rendered_shape(golden_spec):
    assert LabSpec.model_validate(golden_spec).company.name == "Zava Supply Co."
    validation = validate_lab_spec(golden_spec)
    assert validation["valid"] and not validation["warnings"]
    result = render_lab_page(golden_spec)
    assert "html" in result
    assert result["stats"] == {
        "scenario_count": 2, "lab_count": 6, "prompt_count": 7, "total_minutes": 60,
    }
    assert result["filename"] == "zava-finance-from-close-to-cfo-summary.html"
    page = parse(result["html"])
    assert sum(tag == "html" for tag, _ in page.tags) == 1
    assert len(page.ids) == len(set(page.ids))
    for scenario in golden_spec["scenarios"]:
        assert scenario["id"] in page.ids
        assert all(lab["id"] in page.ids for lab in scenario["labs"])
    assert len(page.copies) == result["stats"]["prompt_count"]
    assert all(button["aria-label"] and button["data-copy-target"] in page.ids for button in page.copies)
    assert all(
        attrs["href"][1:] in page.ids
        for tag, attrs in page.tags if tag == "a" and attrs.get("href", "").startswith("#")
    )
    assert not any(
        attrs.get("src") or attrs.get("href") for tag, attrs in page.tags if tag in {"script", "link"}
    )
    assert sum(tag == "script" for tag, _ in page.tags) == 1
    assert {attrs["class"] for tag, attrs in page.tags if tag == "aside" and "callout-" in attrs.get("class", "")} == {
        f"callout callout-{kind}" for kind in ("tip", "warning", "important", "note", "instructor", "real-world", "stretch")
    }


def test_all_prompts_preserve_exact_text_and_escape_markup(minimal_spec):
    injected = '  <script>alert("fictional")</script>\n& <b>Not HTML</b> </pre>  '
    minimal_spec["scenarios"][0]["labs"][0]["exercises"][0]["prompt"] = injected
    minimal_spec["title"] = '<img src=x onerror="alert(1)">'
    minimal_spec["subtitle"] = '" onload="alert(1)'
    minimal_spec["company"]["description"] = "<script>company</script>"
    minimal_spec["scenarios"][0]["story"]["stakeholder"] = "<script>story</script>"
    minimal_spec["scenarios"][0]["labs"][0]["callouts"] = [
        {"type": "note", "text": "<script>callout</script>"}
    ]
    result = render_lab_page(minimal_spec)
    assert "html" in result
    assert "&lt;script&gt;" in result["html"]
    page = parse(result["html"])
    assert page.pre_text[0] == injected
    assert sum(tag == "script" for tag, _ in page.tags) == 1
    assert not any(tag == "img" or "onload" in attrs or "onerror" in attrs for tag, attrs in page.tags)


def test_blank_stakeholder_renders_with_warning_and_no_empty_row(minimal_spec):
    minimal_spec["scenarios"][0]["story"]["stakeholder"] = " "
    result = render_lab_page(minimal_spec)
    assert "html" in result
    assert "None" not in result["html"]
    assert result["html"].count("<dt>Stakeholder</dt>") == 1
    assert any(
        warning["code"] == "missing_story_field"
        and "scenario-1" in warning["message"]
        and "stakeholder" in warning["message"]
        for warning in result["warnings"]
    )


@pytest.mark.parametrize("invalid", ["schema", "duplicate", "url", "theme"])
def test_invalid_specs_never_return_html(minimal_spec, invalid):
    if invalid == "schema":
        del minimal_spec["scenarios"]
    elif invalid == "duplicate":
        minimal_spec["scenarios"][1]["id"] = minimal_spec["scenarios"][0]["id"]
    elif invalid == "url":
        minimal_spec["resources"] = [{"label": "Unsafe", "url": "javascript:alert(1)", "note": ""}]
    else:
        minimal_spec["theme_id"] = "unknown"
    result = render_lab_page(minimal_spec)
    assert "html" not in result and "filename" not in result
    assert result["errors"]


def test_theme_override_and_no_path_loading(minimal_spec):
    minimal_spec["theme_id"] = "unknown"
    assert "html" in render_lab_page(minimal_spec, "microsoft")
    assert "html" not in render_lab_page(minimal_spec, "../../secret")
    assert "html" not in render_lab_page(minimal_spec, "")


def test_golden_output_is_deterministic_and_current(golden_spec):
    original = deepcopy(golden_spec)
    result = render_lab_page(golden_spec)
    assert result == render_lab_page(golden_spec)
    assert golden_spec == original
    assert result["html"] == (ROOT / "examples" / "zava-finance-lab.html").read_text()


def test_pipeline_writes_no_files(monkeypatch, tmp_path, minimal_spec):
    working = tmp_path / "working"
    temporary = tmp_path / "temporary"
    working.mkdir()
    temporary.mkdir()
    monkeypatch.chdir(working)
    monkeypatch.setattr(tempfile, "tempdir", str(temporary))
    for variable in ("TMPDIR", "TMP", "TEMP"):
        monkeypatch.setenv(variable, str(temporary))
    original_builtin_open, original_io_open, original_os_open = builtins.open, io.open, os.open

    def guarded_open(original):
        def open_readonly(file, mode="r", *args, **kwargs):
            assert not any(flag in mode for flag in "wax+"), "Unexpected file write"
            return original(file, mode, *args, **kwargs)
        return open_readonly

    def os_open_readonly(path, flags, *args, **kwargs):
        assert not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        return original_os_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open(original_builtin_open))
    monkeypatch.setattr(io, "open", guarded_open(original_io_open))
    monkeypatch.setattr(os, "open", os_open_readonly)
    get_lab_spec_schema()
    assert validate_lab_spec(minimal_spec)["valid"]
    assert "html" in render_lab_page(minimal_spec)
    assert list(working.iterdir()) == [] and list(temporary.iterdir()) == []


def test_all_registered_tools_forbid_background_tasks():
    from main import mcp

    tools = asyncio.run(mcp.get_tools())
    assert set(tools) == {
        "list_session_formats", "get_lab_spec_schema", "validate_lab_spec", "render_lab_page",
    }
    assert all(tool.task_config.mode == "forbidden" for tool in tools.values())
