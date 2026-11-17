import json
from pathlib import Path
import re
from typing import Any, TypedDict

from pydantic import ValidationError

from studio.schemas.lab_spec import LabSpec, Story


class Issue(TypedDict):
    code: str
    path: str
    message: str


class Stats(TypedDict):
    scenario_count: int
    lab_count: int
    prompt_count: int
    total_minutes: int


class ValidationResult(TypedDict):
    valid: bool
    errors: list[Issue]
    warnings: list[Issue]
    stats: Stats


with (Path(__file__).resolve().parent.parent / "data" / "real_brand_denylist.json").open(
    encoding="utf-8"
) as data_file:
    _REAL_BRANDS: frozenset[str] = frozenset(name.casefold() for name in json.load(data_file))

_RISK_WORDS = re.compile(r"\b(?:numbers?|totals?|forecasts?|variances?|contracts?)\b", re.I)
_RESERVED_IDS = frozenset({"overview", "setup", "capstone"})


def get_lab_spec_schema() -> dict[str, Any]:
    """Return the LabSpec JSON Schema before drafting a fictional training page.

    Describes required fields, nesting, lengths, slug IDs, and allowed enum values.
    All content is plain text. After drafting, call validate_lab_spec for schema
    and cross-field checks; JSON Schema alone does not check duplicate IDs,
    resource URL safety, or instructional quality.
    """
    return LabSpec.model_json_schema()


def validate_lab_spec(spec: dict[str, Any]) -> ValidationResult:
    """Validate fictional LabSpec JSON before rendering; never save or log the spec.

    Returns valid, errors and warnings (code/path/message), and stats containing
    scenario_count, lab_count, prompt_count (including capstone), and total_minutes
    (labs only). Schema errors block rendering and return zero stats; duplicate
    or reserved IDs also block rendering. Quality warnings never block rendering.
    This is not a tenant-data detector; submit only wholly fictional content.
    """
    errors: list[Issue] = []
    warnings: list[Issue] = []
    stats: Stats = {
        "scenario_count": 0, "lab_count": 0, "prompt_count": 0, "total_minutes": 0
    }
    try:
        lab_spec = LabSpec.model_validate(spec)
    except ValidationError as error:
        for item in error.errors(include_input=False, include_url=False):
            errors.append({
                "code": "schema_error",
                "path": ".".join(str(part) for part in item["loc"]) or "$",
                "message": item["msg"],
            })
        return {"valid": False, "errors": errors, "warnings": warnings, "stats": stats}

    seen: set[str] = set()

    def check_id(identifier: str, path: str) -> None:
        if identifier in seen:
            errors.append({
                "code": "duplicate_id", "path": path,
                "message": f"ID '{identifier}' must be unique across all scenarios and labs.",
            })
        if identifier in _RESERVED_IDS:
            errors.append({
                "code": "reserved_id", "path": path,
                "message": f"ID '{identifier}' is reserved for page navigation.",
            })
        seen.add(identifier)

    def check_prompt(prompt: str, path: str) -> None:
        stats["prompt_count"] += 1
        if len(prompt.strip()) < 60:
            warnings.append({
                "code": "short_prompt", "path": path,
                "message": "Prompt is under 60 characters; add task, context, and output requirements.",
            })

    for scenario_index, scenario in enumerate(lab_spec.scenarios):
        stats["scenario_count"] += 1
        scenario_path = f"scenarios.{scenario_index}"
        check_id(scenario.id, f"{scenario_path}.id")
        for field in Story.model_fields:
            if not getattr(scenario.story, field):
                warnings.append({
                    "code": "missing_story_field", "path": f"{scenario_path}.story.{field}",
                    "message": f"Scenario '{scenario.id}' is missing story field '{field}'.",
                })
        for lab_index, lab in enumerate(scenario.labs):
            stats["lab_count"] += 1
            stats["total_minutes"] += lab.minutes
            lab_path = f"{scenario_path}.labs.{lab_index}"
            check_id(lab.id, f"{lab_path}.id")
            for exercise_index, exercise in enumerate(lab.exercises):
                check_prompt(exercise.prompt, f"{lab_path}.exercises.{exercise_index}.prompt")
            if any(_RISK_WORDS.search(exercise.prompt) for exercise in lab.exercises) and not any(
                callout.type in {"warning", "important"} for callout in lab.callouts
            ):
                warnings.append({
                    "code": "missing_risk_callout", "path": f"{lab_path}.callouts",
                    "message": f"Lab '{lab.id}' discusses financial or contract details; add a warning or important callout.",
                })
    if lab_spec.capstone is not None:
        check_prompt(lab_spec.capstone.prompt, "capstone.prompt")
    if lab_spec.company.is_fictional and lab_spec.company.name.casefold() in _REAL_BRANDS:
        warnings.append({
            "code": "real_brand_name", "path": "company.name",
            "message": "Company is marked fictional but matches a real-brand denylist; use an invented Zava-style name.",
        })
    if abs(stats["total_minutes"] - lab_spec.duration_minutes) > lab_spec.duration_minutes * 0.25:
        warnings.append({
            "code": "duration_mismatch", "path": "duration_minutes",
            "message": f"Lab time ({stats['total_minutes']} minutes) differs from session duration ({lab_spec.duration_minutes} minutes) by more than 25%.",
        })
    return {"valid": not errors, "errors": errors, "warnings": warnings, "stats": stats}
