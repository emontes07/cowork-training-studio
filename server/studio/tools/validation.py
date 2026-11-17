import json
from pathlib import Path
import re
from typing import Any, TypedDict, get_args

from pydantic import ValidationError

from studio.schemas.lab_spec import FileKind, LabSpec


class Issue(TypedDict):
    code: str
    path: str
    message: str


class Stats(TypedDict):
    chapter_count: int
    step_count: int
    prompt_count: int
    challenge_count: int
    checkpoint_count: int
    files_by_kind: dict[str, int]
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

_NUMBERS = re.compile(r"\d|\b(?:numbers?|totals?)\b", re.I)
_RISK_WORDS = re.compile(r"\d|\b(?:numbers?|totals?|forecasts?|variances?|contracts?)\b", re.I)
# Literal, case-insensitive authoring hints; the space in "consume " avoids "consumer".
_LEARNER_VOICE_TERMS = (
    "MCP server", "consume ", "tenant path", "do not claim", "if supplied", "JSON", "schema",
)
_RESERVED_IDS = frozenset({
    "overview", "setup", "capstone", "agenda", "files", "story-map", "troubleshooting",
    "glossary", "disclaimer",
})


def get_lab_spec_schema() -> dict[str, Any]:
    """Return the LabSpec 2.0 JSON Schema before drafting a fictional story lab.

    Version 1 is not supported. Draft a narrative, a through-line artifact,
    linked chapters/steps, and file metadata; then call validate_lab_spec for
    reference, ID, URL, and quality checks not fully expressed in JSON Schema.
    All content is plain text. File href links are optional; files are not created.
    """
    return LabSpec.model_json_schema()


def validate_lab_spec(spec: dict[str, Any]) -> ValidationResult:
    """Validate fictional LabSpec 2.0 before rendering; never save or log the spec.

    Returns valid, errors/warnings (code/path/message), and chapter_count,
    step_count, prompt_count, challenge_count, checkpoint_count (declared files),
    files_by_kind, and total_minutes (chapters) within stats. Schema errors
    return zero stats. Reference errors block rendering; quality warnings do not.
    Learner-voice warnings name the field and system term, not its full text.
    File usage is declared via used_in/checkpoint_file_id, not inferred from prose.
    This is not a tenant-data detector; submit only wholly fictional content.
    """
    errors: list[Issue] = []
    warnings: list[Issue] = []
    stats: Stats = {
        "chapter_count": 0, "step_count": 0, "prompt_count": 0, "challenge_count": 0,
        "checkpoint_count": 0, "files_by_kind": dict.fromkeys(get_args(FileKind), 0),
        "total_minutes": 0,
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

    def issue(target: list[Issue], code: str, path: str, message: str) -> None:
        target.append({"code": code, "path": path, "message": message})

    def check_id(identifier: str, path: str) -> None:
        if identifier in seen:
            issue(errors, "duplicate_id", path, f"ID '{identifier}' must be unique across files, chapters, and steps.")
        if identifier in _RESERVED_IDS:
            issue(errors, "reserved_id", path, f"ID '{identifier}' is reserved for page navigation.")
        seen.add(identifier)

    def check_voice(text: str | None, path: str) -> None:
        if text is None:
            return
        folded = text.casefold()
        for term in _LEARNER_VOICE_TERMS:
            if term.casefold() in folded:
                issue(warnings, "learner_voice", path, f"Use learner-facing wording instead of {term!r}.")

    for field in ("role", "situation", "trigger", "deadline"):
        check_voice(getattr(lab_spec.narrative, field), f"narrative.{field}")
    for index, outcome in enumerate(lab_spec.narrative.leave_with):
        check_voice(outcome, f"narrative.leave_with.{index}")
    if lab_spec.through_line:
        for field in ("name", "location", "description"):
            check_voice(getattr(lab_spec.through_line, field), f"through_line.{field}")
    for field in ("steps", "ground_rules"):
        for index, text in enumerate(getattr(lab_spec.setup, field)):
            check_voice(text, f"setup.{field}.{index}")
    for index, mode in enumerate(lab_spec.setup.modes):
        check_voice(mode.description, f"setup.modes.{index}.description")

    chapter_positions = {chapter.id: index for index, chapter in enumerate(lab_spec.chapters)}
    files = {file.id: file for file in lab_spec.files}
    referenced_files = {
        chapter.checkpoint_file_id for chapter in lab_spec.chapters if chapter.checkpoint_file_id
    }
    filenames: set[str] = set()
    for index, file in enumerate(lab_spec.files):
        path = f"files.{index}"
        check_id(file.id, f"{path}.id")
        check_voice(file.filename, f"{path}.filename")
        check_voice(file.purpose, f"{path}.purpose")
        stats["files_by_kind"][file.kind] += 1
        if file.filename.casefold() in filenames:
            issue(errors, "duplicate_filename", f"{path}.filename", "File names must be unique (case-insensitive).")
        filenames.add(file.filename.casefold())
        for reference_index, chapter_id in enumerate(file.used_in):
            if chapter_id not in chapter_positions:
                issue(errors, "unknown_chapter", f"{path}.used_in.{reference_index}", f"Unknown chapter '{chapter_id}'.")
        if file.kind in {"checkpoint", "answer_key"} and not file.used_in and file.id not in referenced_files:
            issue(warnings, "unused_file", path, f"File '{file.id}' is never referenced by used_in or checkpoint_file_id.")
    stats["checkpoint_count"] = stats["files_by_kind"]["checkpoint"]

    for index, chapter in enumerate(lab_spec.chapters):
        stats["chapter_count"] += 1
        stats["total_minutes"] += chapter.minutes
        path = f"chapters.{index}"
        check_id(chapter.id, f"{path}.id")
        for field in ("title", "story_so_far", "you_will_add"):
            check_voice(getattr(chapter, field), f"{path}.{field}")
        for reference_index, chapter_id in enumerate(chapter.builds_on):
            reference_path = f"{path}.builds_on.{reference_index}"
            if chapter_id not in chapter_positions:
                issue(errors, "unknown_chapter", reference_path, f"Unknown chapter '{chapter_id}'.")
            elif chapter_positions[chapter_id] >= index:
                issue(errors, "invalid_chapter_order", reference_path, f"Chapter '{chapter.id}' may only build on earlier chapters.")
        if index > 0 and not chapter.builds_on:
            issue(warnings, "isolated_chapter", f"{path}.builds_on", f"Chapter '{chapter.id}' is isolated: name an earlier chapter to build on.")
        if chapter.checkpoint_file_id is not None:
            checkpoint = files.get(chapter.checkpoint_file_id)
            if checkpoint is None or checkpoint.kind != "checkpoint":
                issue(errors, "invalid_checkpoint", f"{path}.checkpoint_file_id", "Checkpoint reference must name an existing file of kind checkpoint.")
        elif lab_spec.duration_minutes >= 90 and index >= 2:
            issue(warnings, "missing_checkpoint", f"{path}.checkpoint_file_id", f"Chapter '{chapter.id}': learners who fall behind cannot rejoin without a checkpoint.")
        if len(chapter.steps) < 2:
            issue(warnings, "thin_chapter", f"{path}.steps", f"Chapter '{chapter.id}' is thin: add a connected follow-up step.")
        if lab_spec.through_line and not any(step.carries_forward for step in chapter.steps):
            issue(warnings, "missing_carry_forward", f"{path}.steps", f"Chapter '{chapter.id}' does not write into the through-line artifact.")
        for step_index, step in enumerate(chapter.steps):
            stats["step_count"] += 1
            step_path = f"{path}.steps.{step_index}"
            check_id(step.id, f"{step_path}.id")
            for field in ("title", "goal", "uses", "intro", "fallback", "carries_forward"):
                check_voice(getattr(step, field), f"{step_path}.{field}")
            for check_index, text in enumerate(step.self_check):
                check_voice(text, f"{step_path}.self_check.{check_index}")
            for callout_index, callout in enumerate(step.callouts):
                check_voice(callout.text, f"{step_path}.callouts.{callout_index}.text")
            if step.expected:
                check_voice(step.expected.summary, f"{step_path}.expected.summary")
                for fact_index, text in enumerate(step.expected.key_facts):
                    check_voice(text, f"{step_path}.expected.key_facts.{fact_index}")
            if not step.prompts and step.challenge is None:
                issue(errors, "empty_step", step_path, "A step needs at least one prompt or a challenge.")
            if step.level == "challenge" and step.challenge is None:
                issue(errors, "missing_challenge_answer", f"{step_path}.challenge", "A challenge-level step needs a challenge with an answer.")
            if step.challenge:
                stats["challenge_count"] += 1
                for field in ("task", "hint", "answer"):
                    check_voice(getattr(step.challenge, field), f"{step_path}.challenge.{field}")
            for prompt_index, prompt in enumerate(step.prompts):
                stats["prompt_count"] += 1
                prompt_path = f"{step_path}.prompts.{prompt_index}.text"
                check_voice(prompt.text, prompt_path)
                check_voice(prompt.label, f"{step_path}.prompts.{prompt_index}.label")
                if len(prompt.text.strip()) < 60:
                    issue(warnings, "short_prompt", prompt_path, "Prompt is under 60 characters; add task, context, and output requirements.")
                if _NUMBERS.search(prompt.text) and (step.expected is None or not step.expected.key_facts):
                    issue(warnings, "missing_key_facts", prompt_path, f"Step '{step.id}' mentions numbers or totals but supplies no expected key facts.")
            if any(_RISK_WORDS.search(prompt.text) for prompt in step.prompts) and not any(
                callout.type in {"warning", "important"} for callout in step.callouts
            ):
                issue(warnings, "missing_risk_callout", f"{step_path}.callouts", f"Step '{step.id}' discusses numerical or financial details; add a warning or important callout.")
    if lab_spec.company.is_fictional and lab_spec.company.name.casefold() in _REAL_BRANDS:
        issue(warnings, "real_brand_name", "company.name", "Company is marked fictional but matches a real-brand denylist; use an invented Zava-style name.")
    if abs(stats["total_minutes"] - lab_spec.duration_minutes) * 4 > lab_spec.duration_minutes:
        issue(warnings, "duration_mismatch", "duration_minutes", f"Chapter time ({stats['total_minutes']} minutes) differs from session duration ({lab_spec.duration_minutes} minutes) by more than 25%.")
    return {"valid": not errors, "errors": errors, "warnings": warnings, "stats": stats}
