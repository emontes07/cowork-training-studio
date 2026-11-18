import asyncio
import builtins
from copy import deepcopy
from html.parser import HTMLParser
import io
import os
import re
import tempfile

import pytest

from studio.tools.rendering import render_lab_page
from studio.tools.validation import get_lab_spec_schema, validate_lab_spec


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.ids = []
        self.copies = []
        self.pre_text = []
        self.in_pre = False
        self.details_stack = []
        self.answer_parents = []

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
        if tag == "details":
            self.details_stack.append(attributes)
        if "challenge-answer" in attributes.get("class", "").split():
            self.answer_parents.append(list(self.details_stack))

    def handle_endtag(self, tag):
        if tag == "pre":
            self.in_pre = False
        if tag == "details":
            self.details_stack.pop()

    def handle_data(self, data):
        if self.in_pre:
            self.pre_text[-1] += data


def parse(html):
    parser = PageParser()
    parser.feed(html)
    parser.close()
    return parser


def test_rendered_shape_and_anchors(minimal_spec):
    result = render_lab_page(minimal_spec)
    assert "html" in result
    page = parse(result["html"])
    assert sum(tag == "html" for tag, _ in page.tags) == 1
    assert len(page.ids) == len(set(page.ids))
    for chapter in minimal_spec["chapters"]:
        assert chapter["id"] in page.ids
        assert all(step["id"] in page.ids for step in chapter["steps"])
    assert len(page.copies) == result["stats"]["prompt_count"]
    assert all(button["aria-label"] and button["data-copy-target"] in page.ids for button in page.copies)
    assert sum("data-mode" in attrs for _, attrs in page.tags) == result["stats"]["prompt_count"]
    assert all(
        attrs["href"][1:] in page.ids
        for tag, attrs in page.tags if tag == "a" and attrs.get("href", "").startswith("#")
    )
    assert not any(
        attrs.get("src") or attrs.get("href") for tag, attrs in page.tags if tag in {"script", "link", "img", "iframe"}
    )
    assert sum(tag == "script" for tag, _ in page.tags) == 1
    chapters = [attrs for tag, attrs in page.tags if tag == "details" and "chapter" in attrs.get("class", "").split()]
    assert "open" in chapters[0] and "open" not in chapters[1]


def test_summary_counters_pluralize_singular_and_zero(minimal_spec):
    html = render_lab_page(minimal_spec)["html"]
    assert "4 steps / 4 prompts / 0 challenges" in html
    assert "2 steps / select to expand or collapse" in html
    for chapter in minimal_spec["chapters"]:
        chapter["steps"] = chapter["steps"][:1]
    minimal_spec["chapters"][0]["steps"][0].update(prompts=[], challenge={
        "task": "Check the evidence.", "hint": "", "answer": "Keep checked facts.",
    })
    html = render_lab_page(minimal_spec)["html"]
    assert "2 steps / 1 prompt / 1 challenge" in html
    assert html.count("1 step / select to expand or collapse") == 2
    assert "1 steps" not in html and "1 prompts" not in html and "1 challenges" not in html


def test_multiple_builds_on_links_have_only_comma_separators(minimal_spec):
    chapter = deepcopy(minimal_spec["chapters"][1])
    chapter["id"] = "chapter-3"
    chapter["builds_on"] = ["chapter-1", "chapter-2"]
    for index, step in enumerate(chapter["steps"]):
        step["id"] = f"step-3-{index}"
    minimal_spec["chapters"].append(chapter)
    minimal_spec["chapters"][0]["title"] = "Start & review"
    html = render_lab_page(minimal_spec)["html"]
    builds_on = re.findall(r"<dt>Builds on</dt><dd>(.*?)</dd>", html, re.S)
    assert builds_on[-1].strip() == (
        '<a href="#chapter-1">Start &amp; review</a>, <a href="#chapter-2">Chapter 2</a>'
    )


def test_all_prompt_text_and_story_content_are_escaped(minimal_spec):
    injected = '  <script>alert("fictional")</script>\n& <b>Not HTML</b> </pre>  '
    step = minimal_spec["chapters"][0]["steps"][0]
    step["prompts"][0]["text"] = injected
    step["prompts"][0]["label"] = "<img src=x onerror=alert(1)>"
    step["expected"]["key_facts"] = ["<script>fact</script>"]
    step["fallback"] = "<script>fallback</script>"
    step["carries_forward"] = "<script>artifact</script>"
    step["callouts"] = [{"type": "note", "text": "<script>callout</script>"}]
    minimal_spec["title"] = '<img src=x onerror="alert(1)">'
    minimal_spec["subtitle"] = '" onload="alert(1)'
    minimal_spec["narrative"]["role"] = "<script>role</script>"
    minimal_spec["through_line"]["name"] = "<script>sheet</script>"
    minimal_spec["chapters"][0]["story_so_far"] = "<script>story</script>"
    minimal_spec["disclaimer"] = "<script>disclaimer</script>"
    result = render_lab_page(minimal_spec)
    assert "html" in result
    assert "&lt;script&gt;" in result["html"]
    page = parse(result["html"])
    assert page.pre_text[0] == injected
    assert sum(tag == "script" for tag, _ in page.tags) == 1
    assert not any(tag == "img" or "onload" in attrs or "onerror" in attrs for tag, attrs in page.tags)


def test_hidden_challenge_answer_does_not_create_copy_button(minimal_spec):
    step = minimal_spec["chapters"][0]["steps"][0]
    step.update(prompts=[], level="challenge", challenge={
        "task": "Check the evidence independently.", "hint": "Review the source.",
        "answer": "<script>Only an escaped answer</script>",
    })
    result = render_lab_page(minimal_spec)
    page = parse(result["html"])
    assert len(page.copies) == result["stats"]["prompt_count"] == 3
    assert len(page.answer_parents) == 1
    assert page.answer_parents[0][-1]["class"] == "answer"
    assert "open" not in page.answer_parents[0][-1]
    assert len(page.answer_parents[0]) == 3
    assert "&lt;script&gt;Only an escaped answer&lt;/script&gt;" in result["html"]
    assert "Show answer" in result["html"]


@pytest.mark.parametrize("href", [None, "./checkpoint.xlsx", "https://example.test/checkpoint.xlsx"])
def test_file_links_and_checkpoint_callouts(minimal_spec, href):
    minimal_spec["files"] = [{
        "id": "entry-file", "filename": "checkpoint.xlsx", "kind": "checkpoint",
        "purpose": "A checked starting state", "used_in": ["chapter-2"],
    }]
    if href is not None:
        minimal_spec["files"][0]["href"] = href
    minimal_spec["chapters"][1]["checkpoint_file_id"] = "entry-file"
    result = render_lab_page(minimal_spec)
    assert "html" in result
    assert result["html"].count("Behind? Jump in here") == 1
    page = parse(result["html"])
    downloads = [attrs for tag, attrs in page.tags if tag == "a" and "download" in attrs]
    if href is None:
        assert downloads == []
        assert sum(
            "provided-separately" in attrs.get("class", "").split() for _, attrs in page.tags
        ) == 2
    else:
        assert len(downloads) == 2
        assert all(link["href"] == href and link["download"] == "checkpoint.xlsx" for link in downloads)
        assert all(link["target"] == "_blank" and link["rel"] == "noopener noreferrer" for link in downloads)
        assert not any("provided-separately" in attrs.get("class", "").split() for _, attrs in page.tags)
    assert "Only if you fall behind" in result["html"]


def test_facilitator_checkpoint_is_unlinked_everywhere_and_grouped_as_answer_key(minimal_spec):
    minimal_spec["files"] = [{
        "id": "facilitator-file", "filename": "facilitator.xlsx", "kind": "checkpoint",
        "purpose": "Facilitator starting state", "used_in": ["chapter-2"],
        "audience": "facilitator", "href": "https://example.test/private.xlsx",
    }]
    minimal_spec["chapters"][1]["checkpoint_file_id"] = "facilitator-file"
    html = render_lab_page(minimal_spec)["html"]
    assert "private.xlsx" not in html
    assert html.count("Facilitator only") == 2
    assert "Answer keys" in html
    assert "Checkpoints - Only if you fall behind" not in html


def test_legal_links_facilitator_grouping_and_typed_facts_are_escaped(legal_spec):
    legal_spec["files"][0]["href"] = 'https://example.test/source?a=1&b="quoted"'
    fact = legal_spec["chapters"][0]["steps"][0]["expected"]["key_facts"][0]
    fact["text"] = "<b>Original fictional wording & evidence</b>"
    result = render_lab_page(legal_spec)
    assert result["warnings"] == []
    html = result["html"]
    page = parse(html)
    links = [attrs for tag, attrs in page.tags if tag == "a" and "download" in attrs]
    assert len(links) == 1
    assert links[0]["href"] == legal_spec["files"][0]["href"]
    assert links[0]["target"] == "_blank" and links[0]["rel"] == "noopener noreferrer"
    assert '&amp;b=&#34;quoted&#34;' in html
    assert "<li>&lt;b&gt;Original fictional wording &amp; evidence&lt;/b&gt;</li>" in html
    assert "Facilitator only" in html
    assert html.index("Answer keys") < html.index("renewal-answer-key.txt")
    assert legal_spec["files"][2]["href"] not in html
    assert "Provided separately" in html


def test_agenda_uses_chapter_minutes_and_missing_optionals_omit_cleanly(minimal_spec):
    minimal_spec["chapters"][0]["minutes"] = 11
    minimal_spec["chapters"][1]["minutes"] = 17
    minimal_spec["through_line"] = None
    result = render_lab_page(minimal_spec)
    assert "html" in result
    assert "<td>0-11</td>" in result["html"] and "<td>11-28</td>" in result["html"]
    assert "None" not in result["html"]
    for label in ("What you leave with", "One story, 2 chapters", "The story so far", "Builds on", "You will add",
                  "Wording varies; the substance should match", "The story in one table", "Troubleshooting", "Glossary"):
        assert label in result["html"]


@pytest.mark.parametrize("invalid", ["schema", "duplicate", "url", "theme"])
def test_invalid_specs_never_return_html(minimal_spec, invalid):
    if invalid == "schema":
        del minimal_spec["chapters"]
    elif invalid == "duplicate":
        minimal_spec["chapters"][1]["id"] = minimal_spec["chapters"][0]["id"]
    elif invalid == "url":
        minimal_spec["files"] = [{
            "id": "unsafe-file", "filename": "unsafe.xlsx", "kind": "source",
            "purpose": "Unsafe link", "used_in": [], "href": "javascript:alert(1)",
        }]
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


def test_rendering_is_deterministic_without_mutating_spec(minimal_spec):
    original = deepcopy(minimal_spec)
    assert render_lab_page(minimal_spec) == render_lab_page(minimal_spec)
    assert minimal_spec == original


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
