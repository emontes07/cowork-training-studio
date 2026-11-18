import json
from copy import deepcopy
from pathlib import Path
from typing import NotRequired, TypedDict


class BlueprintSummary(TypedDict):
    id: str
    title: str
    default_minutes: int
    best_for: list[str]


class ChapterOutline(TypedDict):
    title: str
    minutes: int
    purpose: str
    step_patterns: list[str]
    lab_id: NotRequired[str]


class LabOutline(TypedDict):
    id: str
    title: str
    format_id: str
    default_minutes: int
    chapter_outline: list[ChapterOutline]


class Blueprint(BlueprintSummary):
    required_inputs: list[str]
    chapter_outline: list[ChapterOutline]
    quality_bar: list[str]
    ends_with: str
    lab_outlines: NotRequired[list[LabOutline]]


class BlueprintResult(TypedDict, total=False):
    blueprints: list[BlueprintSummary]
    id: str
    title: str
    default_minutes: int
    best_for: list[str]
    required_inputs: list[str]
    chapter_outline: list[ChapterOutline]
    quality_bar: list[str]
    ends_with: str
    lab_outlines: list[LabOutline]


_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "blueprints.json"
with _DATA_PATH.open(encoding="utf-8") as data_file:
    _BLUEPRINTS: list[Blueprint] = json.load(data_file)


def get_blueprint(blueprint_id: str | None = None) -> BlueprintResult:
    """Choose a proven fictional workshop shape before drafting a LabSpec.

    Omit blueprint_id to return {blueprints: [{id, title, default_minutes, best_for}]}.
    Pass an exact, case-sensitive ID to return its fields at the top level:
    id, title, default_minutes, best_for, required_inputs, chapter_outline,
    quality_bar and ends_with. Unknown IDs raise an error.
    domain_super_day also returns lab_outlines: chapter_outline is its day agenda
    including breaks; each lab slot names a lab_id and matching title/duration.
    Build each lab_outline separately as html_lab, including the challenge close
    until prompt_a_thon ships. These are outlines, not valid LabSpecs or assets.
    Follow get_lab_spec_schema next. No files, mail or calendar items are created.
    """
    if blueprint_id is None:
        return {"blueprints": [
            BlueprintSummary(
                id=item["id"], title=item["title"],
                default_minutes=item["default_minutes"], best_for=deepcopy(item["best_for"]),
            )
            for item in _BLUEPRINTS
        ]}
    for blueprint in _BLUEPRINTS:
        if blueprint["id"] == blueprint_id:
            result = BlueprintResult(
                id=blueprint["id"], title=blueprint["title"],
                default_minutes=blueprint["default_minutes"], best_for=deepcopy(blueprint["best_for"]),
                required_inputs=deepcopy(blueprint["required_inputs"]),
                chapter_outline=deepcopy(blueprint["chapter_outline"]),
                quality_bar=deepcopy(blueprint["quality_bar"]), ends_with=blueprint["ends_with"],
            )
            if "lab_outlines" in blueprint:
                result["lab_outlines"] = deepcopy(blueprint["lab_outlines"])
            return result
    raise ValueError(
        f"Unknown blueprint id: {blueprint_id!r}. "
        "Call get_blueprint without an id for valid IDs."
    )
