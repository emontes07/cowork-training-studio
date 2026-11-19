import json
from difflib import SequenceMatcher
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

_DIGITS = r"\b\d+(?:[.,]\d+)*\b"
_UNITS = (
    r"units?|items?|orders?|packs?|cases?|products?|sales|dollars?|euros?|pounds?|"
    r"USD|EUR|GBP|CAD|AUD|kg|g|mg|km|cm|mm|lbs?|liters?|litres?|"
    r"hours?|days?|weeks?|months?|minutes?|seconds?"
)
_QUANTITIES = re.compile(
    rf"[$\u00a3\u20ac]\s*\d|\b(?:USD|EUR|GBP|CAD|AUD)\s*\d|"
    rf"{_DIGITS}\s*(?:%|\b(?:percent|percentage|{_UNITS})\b)", re.I,
)
_NUMBER_VALUES = re.compile(
    rf"{_DIGITS}|\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion)\b", re.I,
)
_CALCULATIONS = re.compile(r"\b(?:calculate|divide|multiply|sum|total|cost|rate)\b", re.I)
_MEASURES = re.compile(rf"\b(?:{_UNITS}|revenue|profit|margin|balance|inventory|quantity|amount|values?)\b", re.I)
_RISK_WORDS = re.compile(r"\b(?:forecasts?|variances?|contracts?)\b", re.I)
# Literal, case-insensitive authoring hints; the space in "consume " avoids "consumer".
_LEARNER_VOICE_TERMS = (
    "MCP server", "consume ", "tenant path", "do not claim", "if supplied", "JSON", "schema",
)
_RESERVED_IDS = frozenset({
    "overview", "setup", "capstone", "agenda", "files", "story-map", "troubleshooting",
    "glossary", "disclaimer",
})
_SECTION_NUMBER = re.compile(r"(?:section\s+)?(\d+(?:\.\d+)*(?:\([a-z0-9]+\))*)", re.I)
_SECTION_REFERENCE = re.compile(r"\bsection\s+(\d+(?:\.\d+)*(?:\([a-z0-9]+\))*)", re.I)
_QUOTED_TEXT = re.compile(r'''"([^"\n]+)"|\u201c([^\u201d\n]+)\u201d|(?<!\w)'([^'\n]+)'(?!\w)|\u2018([^\u2019\n]+)\u2019''')
_FILENAME = re.compile(r"\b[\w./-]+\.(?:docx?|xlsx?|pptx?|csv|tsv|txt|md|pdf|html?|json|eml|ics)\b", re.I)
_NAMED_FILE = re.compile(r"\bthe\s+((?:[\w-]+\s+){1,3}(?:log|report|file))\b", re.I)
_GENERIC_FILE_WORDS = frozenset({
    "source", "practice", "current", "input", "output", "provided", "attached",
    "downloaded", "reference", "answer", "key", "new", "original", "same", "updated",
    "latest", "checked", "selected", "supplied", "fictional",
})
_HEADING_NAME = re.compile(
    r'\b(?:heading|section)\s+["\u201c]([^"\u201d]+)["\u201d]|'
    r'["\u201c]([^"\u201d]+)["\u201d]\s+(?:heading|section)\b|'
    r"\b(?:heading|section)\s+([A-Z][\w-]*(?:\s+[A-Z][\w-]*)*)|"
    r"\b([A-Z][\w-]*(?:\s+[A-Z][\w-]*)*)\s+(?:heading|section)\b"
)
_DESTINATION_QUOTE = re.compile(
    r'''\b(?:to|into|under|in)\s+(?:the\s+)?(?P<quote>["'\u201c\u2018][^"'\u201d\u2019\n]+["'\u201d\u2019])''',
    re.I,
)
_CONTAINER = re.compile(r"\byour\s+((?:[\w-]+\s+){0,2}(?:timeline|log|report|tracker|register|sheet|workbook|document))\b", re.I)
_SENSITIVE_DOMAIN = re.compile(r"\b(?:legal|HR|human resources|compliance|privacy|medical)\b", re.I)
_EXPERT = re.compile(r"\b(?:expert|counsel|lawyer|clinician|doctor|specialist|HR adviser|HR advisor)\b", re.I)


def _quoted_text(text: str) -> list[str]:
    return [next(group for group in match.groups() if group is not None) for match in _QUOTED_TEXT.finditer(text)]


def _name_words(text: str) -> str:
    return re.sub(r"[\W_]+", " ", text.casefold()).strip()


def _section_number(value: str | None) -> str | None:
    if value is None:
        return None
    match = _SECTION_NUMBER.fullmatch(value.strip())
    return match.group(1).casefold() if match else None


def _needs_numeric_evidence(text: str) -> bool:
    # Named operands also count: "divide on-hand units by weekly sales".
    return bool(
        _QUANTITIES.search(text)
        or (_CALCULATIONS.search(text) and (_NUMBER_VALUES.search(text) or _MEASURES.search(text)))
    )


def learner_voice_issues(text: str, path: str) -> list[Issue]:
    return [
        {"code": "learner_voice", "path": path, "message": f"Use learner-facing wording instead of {term!r}."}
        for term in _LEARNER_VOICE_TERMS if term.casefold() in text.casefold()
    ]


def has_expert_questions(text: str) -> bool:
    return bool(
        _EXPERT.search(text) and re.search(r"\bquestions?\b", text, re.I)
        and re.search(r"\b(?:interpretations?|interpret|inferences?|inferred|assumptions?|uncertainties|uncertainty)\b", text, re.I)
    )


def has_fictional_parties(text: str) -> bool:
    return bool(re.search(
        r"\b(?:all|every)\s+(?:named\s+)?(?:parties|party|people|person|organizations|organization)\s+(?:(?:are|is|must be)\s+)?fictional\b|"
        r"\b(?:only fictional|fictional (?:parties|people|organizations) only)\b", text, re.I,
    ))


def get_lab_spec_schema() -> dict[str, Any]:
    """Return the LabSpec 2.1 JSON Schema before drafting a fictional story lab.

    schema_version accepts 2.0 and 2.1; version 1 is not supported.
    Draft a narrative, a through-line artifact,
    linked chapters/steps, and file metadata; then call validate_lab_spec for
    reference, ID, URL, and quality checks not fully expressed in JSON Schema.
    All content is plain text. File href links are optional; files are not created.
    """
    return LabSpec.model_json_schema()


def validate_lab_spec(spec: dict[str, Any]) -> ValidationResult:
    """Validate fictional LabSpec 2.0 or 2.1; never save or log the spec.

    Returns valid, errors/warnings (code/path/message), and chapter_count,
    step_count, prompt_count, challenge_count, checkpoint_count (declared files),
    files_by_kind, and total_minutes (chapters) within stats. Schema errors
    return zero stats. Reference errors block rendering; quality warnings do not.
    Learner-voice warnings name the field and system term, not its full text.
    File usage counts use used_in/checkpoint_file_id; prose references are warning-only.
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
    typed_facts = [
        (f"chapters.{chapter_index}.steps.{step_index}.expected.key_facts.{fact_index}", fact)
        for chapter_index, chapter in enumerate(lab_spec.chapters)
        for step_index, step in enumerate(chapter.steps) if step.expected
        for fact_index, fact in enumerate(step.expected.key_facts) if not isinstance(fact, str)
    ]
    sections = {
        number for _, fact in typed_facts if fact.kind == "clause"
        if (number := _section_number(fact.section)) is not None
    }
    file_sources = {file.id for file in lab_spec.files} | {file.filename for file in lab_spec.files}
    artifact_names = [_name_words(value) for file in lab_spec.files for value in (file.id, Path(file.filename).stem)]
    if lab_spec.through_line:
        artifact_names.extend(_name_words(value) for value in (
            lab_spec.through_line.name, lab_spec.through_line.location,
        ))
    expert_questions_present = False

    def issue(target: list[Issue], code: str, path: str, message: str) -> None:
        target.append({"code": code, "path": path, "message": message})

    def check_id(identifier: str, path: str) -> None:
        if identifier in seen:
            issue(errors, "duplicate_id", path, f"ID '{identifier}' must be unique across files, chapters, and steps.")
        if identifier in _RESERVED_IDS:
            issue(errors, "reserved_id", path, f"ID '{identifier}' is reserved for page navigation.")
        seen.add(identifier)

    def check_text(text: str | None, path: str) -> None:
        if text is None:
            return
        warnings.extend(learner_voice_issues(text, path))
        for number in dict.fromkeys(_SECTION_REFERENCE.findall(text)):
            if number.casefold() not in sections:
                issue(warnings, "unknown_section", path,
                      f"Section {number} has no clause key fact; add a clause fact with that section or correct the reference.")

    def declared_artifact(name: str) -> bool:
        words = _name_words(name)
        return any(f" {words} " in f" {artifact} " for artifact in artifact_names)

    def check_files(text: str, path: str) -> None:
        # Mask declared filenames first, including names with spaces and subdirectories.
        remaining = text
        for file in sorted(lab_spec.files, key=lambda item: len(item.filename), reverse=True):
            remaining = re.sub(r"(?<![\w./-])(?:\./)?" + re.escape(file.filename) + r"(?![\w/-]|\.\w)",
                               " ", remaining, flags=re.I)
        missing = dict.fromkeys(_FILENAME.findall(remaining))
        for name in missing:
            if declared_artifact(name):
                continue
            issue(warnings, "unknown_file", path,
                  f"File '{name}' is not declared; add it to files[] or use a declared filename.")
        for match in _NAMED_FILE.finditer(text):
            name = match.group(1)
            qualifiers = _name_words(name).split()[:-1]
            specific = [word for word in qualifiers if word not in _GENERIC_FILE_WORDS]
            if specific and not declared_artifact(" ".join(specific)):
                issue(warnings, "unknown_file", path,
                      f"'{name}' is not a declared file or running document; add it to files[] or name the provided artifact.")

    def check_destination(text: str, path: str) -> None:
        if lab_spec.through_line and lab_spec.through_line.headings:
            headings = {_name_words(name) for name in lab_spec.through_line.headings}
            candidates = [
                next(group for group in match.groups() if group is not None)
                for match in _HEADING_NAME.finditer(text)
            ]
            # Quoted destinations also support "Add this to 'Evidence'".
            for match in _DESTINATION_QUOTE.finditer(text):
                candidates.extend(_quoted_text(match.group("quote")))
            for name in dict.fromkeys(candidates):
                if _name_words(name) not in headings and not declared_artifact(name):
                    issue(warnings, "unknown_heading", path,
                          f"Heading '{name}' is not declared; use a through_line.headings entry or declare this heading.")
        for match in _CONTAINER.finditer(text):
            name = match.group(1)
            if not declared_artifact(name) and not (
                lab_spec.through_line and _name_words(name) in {_name_words(h) for h in lab_spec.through_line.headings}
            ):
                issue(warnings, "unknown_container", path,
                      f"'your {name}' is not declared; name the running document or a declared file.")

    for field in ("role", "situation", "trigger", "deadline"):
        check_text(getattr(lab_spec.narrative, field), f"narrative.{field}")
    for index, outcome in enumerate(lab_spec.narrative.leave_with):
        check_text(outcome, f"narrative.leave_with.{index}")
    check_text(lab_spec.company.description, "company.description")
    check_text(lab_spec.disclaimer, "disclaimer")
    overview_fields = [("company.description", lab_spec.company.description)]
    overview_fields.extend(
        (f"narrative.{field}", getattr(lab_spec.narrative, field))
        for field in ("role", "situation", "trigger", "deadline")
    )
    if lab_spec.through_line:
        overview_fields.extend(
            (f"through_line.{field}", getattr(lab_spec.through_line, field))
            for field in ("name", "location", "description")
        )
    canonical_quotes = [(path, fact.text) for path, fact in typed_facts if fact.kind in {"quote", "clause"}]
    for path, text in overview_fields:
        for quote in _quoted_text(text):
            if any(quote == canonical for _, canonical in canonical_quotes):
                continue
            for fact_path, canonical in canonical_quotes:
                if SequenceMatcher(None, quote, canonical, autojunk=False).find_longest_match().size >= 25:
                    issue(warnings, "quote_drift", path,
                          f"The quote differs from the key fact at {fact_path}.text; copy that fact's text verbatim.")
                    break
    if lab_spec.through_line:
        for field in ("name", "location", "description"):
            check_text(getattr(lab_spec.through_line, field), f"through_line.{field}")
    for field in ("steps", "ground_rules"):
        for index, text in enumerate(getattr(lab_spec.setup, field)):
            check_text(text, f"setup.{field}.{index}")
            check_files(text, f"setup.{field}.{index}")
    for index, mode in enumerate(lab_spec.setup.modes):
        check_text(mode.description, f"setup.modes.{index}.description")

    chapter_positions = {chapter.id: index for index, chapter in enumerate(lab_spec.chapters)}
    files = {file.id: file for file in lab_spec.files}
    referenced_files = {
        chapter.checkpoint_file_id for chapter in lab_spec.chapters if chapter.checkpoint_file_id
    }
    filenames: set[str] = set()
    for index, file in enumerate(lab_spec.files):
        path = f"files.{index}"
        check_id(file.id, f"{path}.id")
        check_text(file.filename, f"{path}.filename")
        check_text(file.purpose, f"{path}.purpose")
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
            check_text(getattr(chapter, field), f"{path}.{field}")
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
                check_text(getattr(step, field), f"{step_path}.{field}")
            check_files(step.uses, f"{step_path}.uses")
            if step.carries_forward:
                check_destination(step.carries_forward, f"{step_path}.carries_forward")
            for check_index, text in enumerate(step.self_check):
                check_text(text, f"{step_path}.self_check.{check_index}")
            for callout_index, callout in enumerate(step.callouts):
                check_text(callout.text, f"{step_path}.callouts.{callout_index}.text")
            if step.expected:
                check_text(step.expected.summary, f"{step_path}.expected.summary")
                for fact_index, fact in enumerate(step.expected.key_facts):
                    fact_path = f"{step_path}.expected.key_facts.{fact_index}"
                    if isinstance(fact, str):
                        check_text(fact, fact_path)
                    else:
                        check_text(fact.text, f"{fact_path}.text")
                        if fact.kind == "clause" and _section_number(fact.section) is None:
                            issue(warnings, "clause_section", f"{fact_path}.section",
                                  "Add the clause's section number, for example 2.1.")
                        if fact.kind in {"quote", "clause"}:
                            source = fact.source_file.strip() if fact.source_file else ""
                            if source not in file_sources:
                                issue(warnings, "key_fact_source", f"{fact_path}.source_file",
                                      "Set source_file to the ID or exact filename of a declared file.")
            if not step.prompts and step.challenge is None:
                issue(errors, "empty_step", step_path, "A step needs at least one prompt or a challenge.")
            if step.level == "challenge" and step.challenge is None:
                issue(errors, "missing_challenge_answer", f"{step_path}.challenge", "A challenge-level step needs a challenge with an answer.")
            if step.challenge:
                stats["challenge_count"] += 1
                for field in ("task", "hint", "answer"):
                    check_text(getattr(step.challenge, field), f"{step_path}.challenge.{field}")
                    check_files(getattr(step.challenge, field), f"{step_path}.challenge.{field}")
            for prompt_index, prompt in enumerate(step.prompts):
                stats["prompt_count"] += 1
                prompt_path = f"{step_path}.prompts.{prompt_index}.text"
                check_text(prompt.text, prompt_path)
                check_text(prompt.label, f"{step_path}.prompts.{prompt_index}.label")
                if len(prompt.text.strip()) < 60:
                    issue(warnings, "short_prompt", prompt_path, "Prompt is under 60 characters; add task, context, and output requirements.")
            # Challenge tasks already have a required answer instead of key facts.
            evidence_fields = [
                (f"{step_path}.{field}", getattr(step, field))
                for field in ("title", "goal", "uses", "intro", "fallback", "carries_forward")
            ]
            evidence_fields.extend(
                (f"{step_path}.prompts.{index}.text", prompt.text)
                for index, prompt in enumerate(step.prompts)
            )
            step_text = " ".join(text for _, text in evidence_fields if text)
            if step.challenge:
                step_text += " " + step.challenge.task
            if has_expert_questions(step_text):
                expert_questions_present = True
            numerical_fields = [
                path for path, text in evidence_fields if text is not None and _needs_numeric_evidence(text)
            ]
            if step.expected is None or not step.expected.key_facts:
                for field_path in numerical_fields:
                    issue(warnings, "missing_key_facts", field_path, f"Step '{step.id}' uses quantities or calculations but supplies no expected key facts.")
            if (numerical_fields or any(_RISK_WORDS.search(prompt.text) for prompt in step.prompts)) and not any(
                callout.type in {"warning", "important"} for callout in step.callouts
            ):
                issue(warnings, "missing_risk_callout", f"{step_path}.callouts", f"Step '{step.id}' discusses numerical or financial details; add a warning or important callout.")
    if lab_spec.company.is_fictional and lab_spec.company.name.casefold() in _REAL_BRANDS:
        issue(warnings, "real_brand_name", "company.name", "Company is marked fictional but matches a real-brand denylist; use an invented Zava-style name.")
    if abs(stats["total_minutes"] - lab_spec.duration_minutes) * 4 > lab_spec.duration_minutes:
        issue(warnings, "duration_mismatch", "duration_minutes", f"Chapter time ({stats['total_minutes']} minutes) differs from session duration ({lab_spec.duration_minutes} minutes) by more than 25%.")
    if _SENSITIVE_DOMAIN.search(f"{lab_spec.functional_area} {lab_spec.audience}"):
        safeguards = " ".join([lab_spec.disclaimer, *lab_spec.setup.ground_rules])
        if "not professional advice" not in safeguards.casefold():
            issue(warnings, "missing_advice_note", "disclaimer",
                  "Add 'practice exercise, not professional advice' to the disclaimer or ground rules.")
        if not expert_questions_present:
            issue(warnings, "missing_expert_questions", "chapters",
                  "Add a step that turns interpretations or uncertainty into questions for an expert, separate from the source text.")
        fictional_text = f"{safeguards} {lab_spec.company.description}"
        if not lab_spec.company.is_fictional or not has_fictional_parties(fictional_text):
            issue(warnings, "missing_fictional_parties", "setup.ground_rules",
                  "State that all parties are fictional and mark company.is_fictional true.")
    return {"valid": not errors, "errors": errors, "warnings": warnings, "stats": stats}
