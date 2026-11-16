import pytest

from studio.schemas.lab_spec import LabSpec
from studio.tools.validation import get_lab_spec_schema, validate_lab_spec


def test_schema_and_stats(minimal_spec):
    assert LabSpec.model_validate(minimal_spec).theme_id == "microsoft"
    result = validate_lab_spec(minimal_spec)
    assert result == {
        "valid": True, "errors": [], "warnings": [],
        "stats": {"scenario_count": 2, "lab_count": 4, "prompt_count": 4, "total_minutes": 40},
    }
    assert "scenarios" in get_lab_spec_schema()["required"]


@pytest.mark.parametrize("missing", ["scenarios", "story"])
def test_missing_required_structure(minimal_spec, missing):
    if missing == "story":
        del minimal_spec["scenarios"][0]["story"]
    else:
        del minimal_spec[missing]
    result = validate_lab_spec(minimal_spec)
    assert result["valid"] is False
    assert result["errors"][0]["code"] == "schema_error"
    assert "input" not in result["errors"][0]


@pytest.mark.parametrize("collision", ["scenario", "lab", "cross"])
def test_globally_duplicate_ids(minimal_spec, collision):
    scenarios = minimal_spec["scenarios"]
    if collision == "scenario":
        scenarios[1]["id"] = scenarios[0]["id"]
    elif collision == "lab":
        scenarios[1]["labs"][0]["id"] = scenarios[0]["labs"][0]["id"]
    else:
        scenarios[1]["labs"][0]["id"] = scenarios[0]["id"]
    result = validate_lab_spec(minimal_spec)
    assert result["valid"] is False
    assert result["errors"][0]["code"] == "duplicate_id"


@pytest.mark.parametrize("prompt", ["", " \n\t "])
def test_empty_prompts_are_errors(minimal_spec, prompt):
    minimal_spec["scenarios"][0]["labs"][0]["exercises"][0]["prompt"] = prompt
    result = validate_lab_spec(minimal_spec)
    assert not result["valid"]
    assert result["errors"][0]["path"].endswith(".prompt")


def test_missing_story_fields_are_individual_warnings(minimal_spec):
    minimal_spec["scenarios"][0]["story"] = {"stakeholder": "  "}
    result = validate_lab_spec(minimal_spec)
    assert result["valid"]
    assert len(result["warnings"]) == 5
    for field in ("context", "stakeholder", "time_pressure", "source_material", "deliverable"):
        assert any(
            item["code"] == "missing_story_field"
            and item["path"].endswith(f".{field}")
            and "scenario-1" in item["message"]
            and field in item["message"]
            for item in result["warnings"]
        )


@pytest.mark.parametrize("word", ["numbers", "totals", "forecast", "variance", "contract"])
def test_financial_prompt_needs_risk_callout(minimal_spec, word):
    lab = minimal_spec["scenarios"][0]["labs"][0]
    lab["exercises"][0]["prompt"] += f" Review the {word}."
    assert [item["code"] for item in validate_lab_spec(minimal_spec)["warnings"]] == [
        "missing_risk_callout"
    ]
    for kind in ("warning", "important"):
        lab["callouts"] = [{"type": kind, "text": "Verify the source before acting."}]
        assert validate_lab_spec(minimal_spec)["warnings"] == []


@pytest.mark.parametrize(("length", "warns"), [(59, True), (60, False)])
def test_short_prompt_boundary(minimal_spec, length, warns):
    minimal_spec["scenarios"][0]["labs"][0]["exercises"][0]["prompt"] = "x" * length
    assert bool(validate_lab_spec(minimal_spec)["warnings"]) is warns


def test_real_brand_warning_is_case_insensitive(minimal_spec):
    minimal_spec["company"]["name"] = "  mIcRoSoFt  "
    result = validate_lab_spec(minimal_spec)
    assert result["valid"]
    assert result["warnings"][0]["code"] == "real_brand_name"
    minimal_spec["company"]["is_fictional"] = False
    assert validate_lab_spec(minimal_spec)["warnings"] == []


@pytest.mark.parametrize(("duration", "warns"), [(32, False), (31, True), (53, False), (54, True)])
def test_duration_warning_strictly_over_25_percent(minimal_spec, duration, warns):
    minimal_spec["duration_minutes"] = duration
    assert bool(validate_lab_spec(minimal_spec)["warnings"]) is warns


@pytest.mark.parametrize("url", [
    "javascript:alert(1)", "data:text/html,test", "JaVaScRiPt:alert(1)",
    "java\tscript:alert(1)", "//example.test/path", "\\\\example.test", "https://",
])
def test_unsafe_resource_urls_rejected(minimal_spec, url):
    minimal_spec["resources"] = [{"label": "Reference", "url": url, "note": ""}]
    result = validate_lab_spec(minimal_spec)
    assert not result["valid"]
    assert result["errors"][0]["path"] == "resources.0.url"


@pytest.mark.parametrize("url", [
    None, "https://example.test/guide", "http://example.test/guide",
    "mailto:training@example.test", "./guide.html", "../guide.html", "/guide.html", "#setup",
])
def test_allowed_resource_urls(minimal_spec, url):
    minimal_spec["resources"] = [{"label": "Reference", "url": url, "note": ""}]
    assert validate_lab_spec(minimal_spec)["valid"]


@pytest.mark.parametrize(("field", "value"), [
    ("id", "invalid id"), ("id", "overview"), ("minutes", 0), ("minutes", True),
    ("difficulty", "expert"), ("exercises", []), ("self_check", ["Only one"]),
])
def test_lab_constraints(minimal_spec, field, value):
    minimal_spec["scenarios"][0]["labs"][0][field] = value
    assert not validate_lab_spec(minimal_spec)["valid"]


def test_capstone_is_counted_and_empty_prompt_rejected(minimal_spec):
    minimal_spec["capstone"] = {
        "prompt": "Write an evidence-based reflection on the fictional workshop. Explain your choices and describe one revision.",
        "deliverable": "A reflection", "debrief_questions": ["What changed?"],
    }
    assert validate_lab_spec(minimal_spec)["stats"]["prompt_count"] == 5
    minimal_spec["capstone"]["prompt"] = " "
    assert not validate_lab_spec(minimal_spec)["valid"]
