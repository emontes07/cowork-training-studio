from copy import deepcopy

import pytest

from studio.schemas.lab_spec import LabSpec
from studio.tools.validation import get_lab_spec_schema, validate_lab_spec


def add_file(spec, **overrides):
    file = {
        "id": "practice-file", "filename": "practice.xlsx", "kind": "source",
        "purpose": "Fictional practice data", "used_in": ["chapter-1"],
    }
    file.update(overrides)
    spec["files"].append(file)
    return file


def codes(spec, key="errors"):
    return {item["code"] for item in validate_lab_spec(spec)[key]}


def test_v2_schema_and_stats(minimal_spec):
    assert LabSpec.model_validate(minimal_spec).theme_id == "microsoft"
    result = validate_lab_spec(minimal_spec)
    assert result == {
        "valid": True, "errors": [], "warnings": [],
        "stats": {
            "chapter_count": 2, "step_count": 4, "prompt_count": 4, "challenge_count": 0,
            "checkpoint_count": 0, "total_minutes": 40,
            "files_by_kind": {"source": 0, "checkpoint": 0, "answer_key": 0, "worksheet": 0, "extra": 0},
        },
    }
    schema = get_lab_spec_schema()
    assert {"schema_version", "chapters", "narrative"} <= set(schema["required"])
    assert schema["properties"]["schema_version"]["const"] == "2.0"


@pytest.mark.parametrize("change", ["missing_version", "v1", "unknown", "missing_chapters", "wrong_type"])
def test_strict_contract_rejects_v1_and_malformed_input(minimal_spec, change):
    if change == "missing_version":
        del minimal_spec["schema_version"]
    elif change == "v1":
        minimal_spec["schema_version"] = "1.0"
    elif change == "unknown":
        minimal_spec["scenarios"] = []
    elif change == "missing_chapters":
        del minimal_spec["chapters"]
    else:
        minimal_spec["duration_minutes"] = "40"
    result = validate_lab_spec(minimal_spec)
    assert not result["valid"]
    assert result["errors"][0]["code"] == "schema_error"
    assert result["stats"]["chapter_count"] == 0
    assert "input" not in result["errors"][0]


@pytest.mark.parametrize("scope", ["chapter", "step", "file"])
def test_globally_unique_ids(minimal_spec, scope):
    duplicate = minimal_spec["chapters"][0]["id"]
    if scope == "chapter":
        minimal_spec["chapters"][1]["id"] = duplicate
    elif scope == "step":
        minimal_spec["chapters"][1]["steps"][0]["id"] = duplicate
    else:
        add_file(minimal_spec, id=duplicate)
    assert "duplicate_id" in codes(minimal_spec)


@pytest.mark.parametrize("identifier", ["overview", "setup", "capstone", "agenda", "files", "story-map", "troubleshooting", "glossary", "disclaimer"])
def test_reserved_ids(minimal_spec, identifier):
    minimal_spec["chapters"][0]["steps"][0]["id"] = identifier
    assert "reserved_id" in codes(minimal_spec)


@pytest.mark.parametrize("scope", ["builds_on", "used_in"])
def test_unknown_chapter_references(minimal_spec, scope):
    if scope == "builds_on":
        minimal_spec["chapters"][1]["builds_on"] = ["missing"]
    else:
        add_file(minimal_spec, used_in=["missing"])
    assert "unknown_chapter" in codes(minimal_spec)


@pytest.mark.parametrize("target", ["chapter-1", "chapter-2"])
def test_cannot_build_on_same_or_later_chapter(minimal_spec, target):
    minimal_spec["chapters"][0]["builds_on"] = [target]
    assert "invalid_chapter_order" in codes(minimal_spec)


@pytest.mark.parametrize("exists", [False, True])
def test_checkpoint_reference_must_exist_and_have_correct_kind(minimal_spec, exists):
    if exists:
        add_file(minimal_spec)
    minimal_spec["chapters"][1]["checkpoint_file_id"] = "practice-file"
    assert "invalid_checkpoint" in codes(minimal_spec)


def test_step_needs_prompt_or_challenge(minimal_spec):
    minimal_spec["chapters"][0]["steps"][0]["prompts"] = []
    assert "empty_step" in codes(minimal_spec)


@pytest.mark.parametrize("answer", [None, "", " "])
def test_challenge_requires_nonblank_answer(minimal_spec, answer):
    step = minimal_spec["chapters"][0]["steps"][0]
    step["level"] = "challenge"
    step["prompts"] = []
    step["challenge"] = {"task": "Review the draft.", "hint": "Check the evidence."}
    if answer is not None:
        step["challenge"]["answer"] = answer
    result = validate_lab_spec(minimal_spec)
    assert not result["valid"]
    assert result["errors"][0]["path"].endswith("challenge.answer")


def test_challenge_level_requires_challenge_even_with_prompts(minimal_spec):
    minimal_spec["chapters"][0]["steps"][0]["level"] = "challenge"
    assert "missing_challenge_answer" in codes(minimal_spec)


def test_challenge_only_step_is_valid_and_counted(minimal_spec):
    step = minimal_spec["chapters"][0]["steps"][0]
    step.update(prompts=[], level="challenge", challenge={
        "task": "Review the draft.", "hint": "", "answer": "Retain only supported claims.",
    })
    result = validate_lab_spec(minimal_spec)
    assert result["valid"]
    assert result["stats"]["prompt_count"] == 3
    assert result["stats"]["challenge_count"] == 1


def test_duplicate_filenames(minimal_spec):
    add_file(minimal_spec)
    add_file(minimal_spec, id="other-file", filename="PRACTICE.xlsx")
    assert "duplicate_filename" in codes(minimal_spec)


@pytest.mark.parametrize("rule", ["isolated_chapter", "missing_carry_forward", "thin_chapter"])
def test_chapter_quality_warnings(minimal_spec, rule):
    chapter = minimal_spec["chapters"][1]
    if rule == "isolated_chapter":
        chapter["builds_on"] = []
    elif rule == "missing_carry_forward":
        for step in chapter["steps"]:
            step["carries_forward"] = None
    else:
        chapter["steps"].pop()
    result = validate_lab_spec(minimal_spec)
    assert result["valid"]
    assert codes(minimal_spec, "warnings") == {rule}


@pytest.mark.parametrize("word", ["forecast", "variance", "contract"])
def test_financial_risk_warnings(minimal_spec, word):
    step = minimal_spec["chapters"][0]["steps"][0]
    step["prompts"][0]["text"] += f" Review the {word}."
    assert codes(minimal_spec, "warnings") == {"missing_risk_callout"}
    for kind in ("warning", "important"):
        step["callouts"] = [{"type": kind, "text": "Verify source figures before using them."}]
        assert not codes(minimal_spec, "warnings")


@pytest.mark.parametrize(("field", "text", "warns"), [
    ("prompt", "what two questions should I ask", False),
    ("prompt", "Summarize the result in one sentence.", False),
    ("intro", "Review step 2 and suggest 3 questions about the numbers.", False),
    ("prompt", "divide on-hand units by weekly sales", True),
    ("intro", "Divide on-hand units by weekly sales.", True),
    ("prompt", "Compare 40 units with the checked inventory.", True),
    ("prompt", "Check the $250 budget and the 12.5% rate.", True),
    ("prompt", "Calculate 12 divided by 3.", True),
    ("prompt", "Calculate the sum of two values.", True),
])
def test_numeric_evidence_uses_quantities_and_calculations(minimal_spec, field, text, warns):
    step = minimal_spec["chapters"][0]["steps"][0]
    text += " Use the fictional practice workbook and explain the result clearly."
    if field == "prompt":
        step["prompts"][0]["text"] = text
        path = "chapters.0.steps.0.prompts.0.text"
    else:
        step["intro"] = text
        path = "chapters.0.steps.0.intro"
    warnings = validate_lab_spec(minimal_spec)["warnings"]
    assert {item["code"] for item in warnings} == (
        {"missing_key_facts", "missing_risk_callout"} if warns else set()
    )
    if warns:
        assert [item["path"] for item in warnings if item["code"] == "missing_key_facts"] == [path]
        step["expected"]["key_facts"] = ["Check the result against the fictional source quantities."]
        step["callouts"] = [{"type": "important", "text": "Verify the source and denominator."}]
        assert not validate_lab_spec(minimal_spec)["warnings"]


@pytest.mark.parametrize(("duration", "warns"), [(89, False), (90, True)])
def test_checkpoint_warning_starts_at_third_chapter_and_90_minutes(minimal_spec, duration, warns):
    chapter = deepcopy(minimal_spec["chapters"][1])
    chapter["id"] = "chapter-3"
    chapter["builds_on"] = ["chapter-2"]
    for index, step in enumerate(chapter["steps"]):
        step["id"] = f"step-3-{index}"
    minimal_spec["chapters"].append(chapter)
    minimal_spec["duration_minutes"] = duration
    for chapter in minimal_spec["chapters"]:
        chapter["minutes"] = 30
    warnings = validate_lab_spec(minimal_spec)["warnings"]
    assert ("missing_checkpoint" in {item["code"] for item in warnings}) is warns
    if warns:
        assert [item["path"] for item in warnings] == ["chapters.2.checkpoint_file_id"]
    add_file(minimal_spec, kind="checkpoint", used_in=[])
    minimal_spec["chapters"][2]["checkpoint_file_id"] = "practice-file"
    assert not validate_lab_spec(minimal_spec)["warnings"]


@pytest.mark.parametrize("kind", ["checkpoint", "answer_key"])
def test_unused_file_warning_and_declared_usage(minimal_spec, kind):
    file = add_file(minimal_spec, kind=kind, used_in=[])
    assert codes(minimal_spec, "warnings") == {"unused_file"}
    file["used_in"] = ["chapter-2"]
    assert not codes(minimal_spec, "warnings")
    result = validate_lab_spec(minimal_spec)
    assert result["stats"]["files_by_kind"][kind] == 1
    assert result["stats"]["checkpoint_count"] == (1 if kind == "checkpoint" else 0)


@pytest.mark.parametrize(("duration", "warns"), [(32, False), (31, True), (53, False), (54, True)])
def test_duration_warning_strictly_over_25_percent(minimal_spec, duration, warns):
    minimal_spec["duration_minutes"] = duration
    assert ("duration_mismatch" in codes(minimal_spec, "warnings")) is warns


@pytest.mark.parametrize(("length", "warns"), [(59, True), (60, False)])
def test_short_prompt_boundary(minimal_spec, length, warns):
    minimal_spec["chapters"][0]["steps"][0]["prompts"][0]["text"] = "x" * length
    assert ("short_prompt" in codes(minimal_spec, "warnings")) is warns


def test_brand_warning(minimal_spec):
    minimal_spec["company"]["name"] = "  mIcRoSoFt  "
    assert codes(minimal_spec, "warnings") == {"real_brand_name"}


@pytest.mark.parametrize("term", [
    "MCP server", "consume ", "tenant path", "do not claim", "if supplied", "JSON", "schema",
])
def test_learner_voice_warning_is_case_insensitive_and_nonblocking(minimal_spec, term):
    minimal_spec["chapters"][0]["steps"][0]["prompts"][0]["text"] += f" {term.swapcase()}."
    result = validate_lab_spec(minimal_spec)
    assert result["valid"] and result["errors"] == []
    assert result["warnings"] == [{
        "code": "learner_voice", "path": "chapters.0.steps.0.prompts.0.text",
        "message": f"Use learner-facing wording instead of {term!r}.",
    }]


@pytest.mark.parametrize("path", [
    "narrative.situation", "narrative.leave_with.0", "through_line.description",
    "setup.steps.0", "chapters.0.title", "chapters.0.story_so_far", "chapters.0.you_will_add",
    "chapters.0.steps.0.intro", "chapters.0.steps.0.challenge.task",
    "chapters.0.steps.0.callouts.0.text", "files.0.purpose", "files.0.filename",
])
def test_learner_voice_paths_include_file_and_checkpoint_text(minimal_spec, path):
    step = minimal_spec["chapters"][0]["steps"][0]
    step["challenge"] = {"task": "Check the evidence.", "hint": "", "answer": "Keep checked facts."}
    step["callouts"] = [{"type": "important", "text": "Check the evidence."}]
    add_file(minimal_spec, kind="checkpoint")
    minimal_spec["chapters"][1]["checkpoint_file_id"] = "practice-file"
    parts = [int(part) if part.isdigit() else part for part in path.split(".")]
    target = minimal_spec
    for part in parts[:-1]:
        target = target[part]
    target[parts[-1]] = "schema-notes.xlsx"
    result = validate_lab_spec(minimal_spec)
    assert result["valid"]
    assert result["warnings"] == [{
        "code": "learner_voice", "path": path,
        "message": "Use learner-facing wording instead of 'schema'.",
    }]


def test_clean_learner_voice_and_facilitator_notes_do_not_warn(minimal_spec):
    minimal_spec["chapters"][0]["steps"][0]["intro"] = "Review the consumer feedback in the Story sheet."
    minimal_spec["troubleshooting"][0]["fix"] = "Facilitator: check the JSON schema and MCP server."
    assert validate_lab_spec(minimal_spec)["warnings"] == []


@pytest.mark.parametrize("href", [
    "javascript:alert(1)", "data:text/html,test", "JaVaScRiPt:alert(1)",
    "java\tscript:alert(1)", "//example.test/path", "\\\\example.test", "https://",
])
def test_unsafe_href_rejected(minimal_spec, href):
    add_file(minimal_spec, href=href)
    result = validate_lab_spec(minimal_spec)
    assert not result["valid"]
    assert result["errors"][0]["path"] == "files.0.href"


@pytest.mark.parametrize("href", [
    None, "https://example.test/guide", "http://example.test/guide",
    "mailto:training@example.test", "./guide.xlsx", "../guide.xlsx", "/guide.xlsx", "#files",
])
def test_allowed_href(minimal_spec, href):
    add_file(minimal_spec, href=href)
    assert validate_lab_spec(minimal_spec)["valid"]


@pytest.mark.parametrize("filename", ["https://example.test/a.xlsx", "../secret", "/absolute.xlsx", "folder\\file.xlsx"])
def test_filename_is_relative_not_a_link(minimal_spec, filename):
    add_file(minimal_spec, filename=filename)
    assert not validate_lab_spec(minimal_spec)["valid"]


@pytest.mark.parametrize(("field", "value"), [
    ("id", "invalid id"), ("minutes", 0), ("minutes", True), ("level", "expert"),
    ("prompts", [{"label": "Empty", "mode": "chat", "text": " \n "}]),
])
def test_step_constraints(minimal_spec, field, value):
    minimal_spec["chapters"][0]["steps"][0][field] = value
    assert not validate_lab_spec(minimal_spec)["valid"]
