from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

import pytest

from studio.strings import STRINGS
from studio.tools.demo_rendering import render_demo_guide
from studio.tools.demo_validation import get_demo_pack_schema, validate_demo_pack
from studio.tools.rendering import render_lab_page
from studio.tools.validation import get_lab_spec_schema, validate_lab_spec
from test_rendering import PageParser, parse


FIXTURES = Path(__file__).parent / "fixtures"
ENGLISH_HASHES = {
    "zava_story_lab": {
        "html": "938be3ba40c36174d1f3b39b293ebb218b85662e24f8eeb450551ab3a59a078c",
    },
    "legal_notice_lab": {
        "html": "6ec0ff39c009267a2f1a9d0a91ac20954dcf1ba16c53b34969457a59c16c31cb",
    },
    "demo_pack_function": {
        "html": "7d75c57101327f417743c7e356fe41e4a4af0532850c014b5d3425e3d05d86c6",
        "readme_md": "13e7e27dcfa4cb63de73659cf2b29887102568ca779563debf058584a81afc71",
    },
    "demo_pack_prompt": {
        "html": "d643b3588c626023a577ce46ed00d2a4f32549fc51bdbf1ffec7f3260bd92741",
        "readme_md": "a1ff5be43b6bbb3d8257810f6e61a588dcee3daa36d777ab83e721cac28d43ed",
    },
}


def pipeline(name):
    spec = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    if name.startswith("demo_pack"):
        return spec, render_demo_guide, validate_demo_pack, get_demo_pack_schema
    return spec, render_lab_page, validate_lab_spec, get_lab_spec_schema


class VisiblePage(PageParser):
    def __init__(self):
        super().__init__()
        self.ui_text = []
        self.excluded = 0

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        if tag in {"style", "script", "pre"}:
            self.excluded += 1
        attributes = dict(attrs)
        if "aria-label" in attributes:
            self.ui_text.append(attributes["aria-label"])

    def handle_endtag(self, tag):
        super().handle_endtag(tag)
        if tag in {"style", "script", "pre"}:
            self.excluded -= 1

    def handle_data(self, data):
        super().handle_data(data)
        if not self.excluded:
            self.ui_text.append(data)


def authored_strings(value, key=""):
    # Enum badges are UI; author-provided prose must remain untouched, even in English.
    if isinstance(value, dict):
        for field, child in value.items():
            yield from authored_strings(child, field)
    elif isinstance(value, list):
        for child in value:
            yield from authored_strings(child, key)
    elif isinstance(value, str) and key not in {
        "locale", "schema_version", "mode", "format", "function", "kind", "type",
        "level", "skill_level",
    }:
        yield value


@pytest.mark.parametrize("name", ENGLISH_HASHES)
@pytest.mark.parametrize("locale", [None, "en"])
def test_english_outputs_remain_byte_identical(name, locale):
    spec, render, _, _ = pipeline(name)
    if locale is not None:
        spec["locale"] = locale
    result = render(spec)
    for field, digest in ENGLISH_HASHES[name].items():
        assert hashlib.sha256(result[field].encode("utf-8")).hexdigest() == digest


@pytest.mark.parametrize("name", ["zava_story_lab", "legal_notice_lab", "demo_pack_function"])
def test_locale_is_optional_exported_and_invalid_values_fail(name):
    spec, render, validate, schema = pipeline(name)
    contract = schema()
    assert contract["properties"]["locale"]["enum"] == ["en", "es"]
    assert contract["properties"]["locale"]["default"] == "en"
    assert "locale" not in contract["required"]
    spec["locale"] = "fr"
    result = validate(spec)
    assert not result["valid"]
    assert any(issue["code"] == "schema_error" and issue["path"] == "locale" for issue in result["errors"])
    assert "html" not in render(spec)


@pytest.mark.parametrize("name", ENGLISH_HASHES)
def test_spanish_ui_has_no_english_labels_and_keeps_author_content(name):
    spec, render, validate, _ = pipeline(name)
    english = render(spec)
    spec["locale"] = "es"
    original = deepcopy(spec)
    result = render(spec)
    assert validate(spec)["warnings"] == []
    assert spec == original and result["filename"] == english["filename"]
    page = VisiblePage()
    page.feed(result["html"])
    page.close()
    assert ("html", {"lang": "es"}) in page.tags
    assert page.pre_text == parse(english["html"]).pre_text
    assert page.copies and all(button["aria-label"].startswith(STRINGS["es"]["copy_prompt_label"]) for button in page.copies)
    assert all(button["data-copy-target"] in page.ids for button in page.copies)
    text = "\n".join(page.ui_text)
    for authored in sorted(set(authored_strings(spec)), key=len, reverse=True):
        text = text.replace(authored, "")
    for key, label in STRINGS["en"].items():
        if label != STRINGS["es"][key]:
            assert not re.search(r"(?<!\w)" + re.escape(label) + r"(?!\w)", text), (key, label)
    for key in ("clipboard_unavailable", "copied", "copy_success", "select_copy", "copy_failure", "copy_prompt"):
        assert json.dumps(STRINGS["es"][key]) in result["html"]
    if "readme_md" in result:
        assert f"## {STRINGS['es']['files']}" in result["readme_md"]
        assert f"## {STRINGS['es']['demo_flow']}" in result["readme_md"]
        assert STRINGS["es"]["credits_line"] in result["readme_md"]


def test_spanish_optional_labels_and_escaping(minimal_spec):
    spec = minimal_spec
    spec["locale"] = "es"
    spec["files"] = [
        {"id": "source", "filename": "fuente.docx", "kind": "source", "purpose": "Datos",
         "used_in": ["chapter-1"]},
        {"id": "answers", "filename": "respuestas.docx", "kind": "answer_key", "purpose": "Respuestas",
         "used_in": ["chapter-2"], "audience": "facilitator", "href": "https://example.test/private"},
    ]
    step = spec["chapters"][0]["steps"][0]
    prompt = '  Revisa "<script>datos</script>" y conserva los acentos: acci\u00f3n.\n'
    step["prompts"][0]["text"] = prompt
    step["prompts"][0]["label"] = '<img src=x onerror="alert(1)">'
    step["callouts"] = [{"type": kind, "text": "Contenido"} for kind in (
        "tip", "warning", "important", "note", "instructor", "real_world", "stretch",
    )]
    step["challenge"] = {"task": "Comprueba los datos.", "hint": "Revisa la fuente.", "answer": "Respuesta ficticia."}
    result = render_lab_page(spec)
    page = parse(result["html"])
    assert page.pre_text[0] == prompt
    assert sum(tag == "script" for tag, _ in page.tags) == 1
    assert not any(tag == "img" or "onerror" in attrs for tag, attrs in page.tags)
    assert "https://example.test/private" not in result["html"]
    for key in ("provided_separately", "facilitator_only", "show_answer", "file_answer_key", "hint"):
        assert STRINGS["es"][key] in result["html"]
    assert all(STRINGS["es"][f"callout_{callout['type']}"] in result["html"] for callout in step["callouts"])
