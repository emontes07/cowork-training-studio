from pathlib import PurePosixPath
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Slug = Annotated[Text, Field(pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")]
Level = Literal["basic", "intermediate", "advanced"]
Mode = Literal["chat", "plan", "edit", "agent", "researcher", "analyst", "cowork", "other"]
FileKind = Literal["source", "checkpoint", "answer_key", "worksheet", "extra"]
CalloutType = Literal["tip", "warning", "important", "note", "instructor", "real_world", "stretch"]
Minutes = Annotated[int, Field(gt=0)]
Locale = Literal["en", "es"]


def nonblank_prompt(value: str) -> str:
    if not value.strip():
        raise ValueError("Prompts must not be empty or whitespace-only.")
    return value


def safe_url(value: str) -> str:
    if not value or any(character.isspace() or ord(character) < 32 for character in value):
        raise ValueError("URLs must be nonempty and contain no whitespace or controls.")
    if "\\" in value or value.startswith("//"):
        raise ValueError("Use an explicit http/https URL or a relative path, not a network path.")
    parts = urlsplit(value)
    if parts.scheme not in {"", "http", "https", "mailto"}:
        raise ValueError("URLs allow only https, http, mailto, or relative paths.")
    if parts.scheme in {"http", "https"} and not parts.hostname:
        raise ValueError("HTTP URLs must include a host.")
    if parts.scheme == "mailto" and not parts.path:
        raise ValueError("Mailto URLs must include an address.")
    if parts.username is not None or parts.password is not None:
        raise ValueError("URLs must not contain credentials.")
    return value


PromptText = Annotated[str, Field(min_length=1), AfterValidator(nonblank_prompt)]
SafeURL = Annotated[str, AfterValidator(safe_url)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Company(Contract):
    name: Text
    is_fictional: bool
    description: Text


class Narrative(Contract):
    role: Text
    situation: Text
    trigger: Text
    deadline: Text
    leave_with: Annotated[list[Text], Field(min_length=3, max_length=7)]


class ThroughLine(Contract):
    name: Text
    location: Text
    description: Text
    headings: list[Text] = Field(default_factory=list)


class LabFile(Contract):
    id: Slug
    filename: Text
    kind: FileKind
    purpose: Text
    used_in: list[Slug]
    href: SafeURL | None = None
    audience: Literal["learner", "facilitator"] = "learner"

    @field_validator("filename")
    @classmethod
    def relative_filename(cls, value: str) -> str:
        if (
            value.startswith("/")
            or any(character in value for character in "\\:?#")
            or any(ord(character) < 32 for character in value)
            or ".." in PurePosixPath(value).parts
            or value in {".", ".."}
            or value.endswith("/")
        ):
            raise ValueError("Filename must be a relative file path, not a URL or parent traversal.")
        return value


class SetupMode(Contract):
    name: Text
    description: Text


class Setup(Contract):
    steps: list[Text]
    ground_rules: list[Text]
    modes: list[SetupMode]


class Prompt(Contract):
    label: Text
    mode: Mode
    text: PromptText


class Challenge(Contract):
    task: Text
    hint: str
    answer: Text


class KeyFact(Contract):
    kind: Literal["number", "quote", "clause", "fact"]
    text: Text
    source_file: str | None = Field(default=None, description="ID or exact filename of a declared file.")
    section: str | None = Field(default=None, description="Section number, for example 2.1; missing clause sections warn.")


class Expected(Contract):
    summary: Text
    key_facts: list[Text | KeyFact]


class Callout(Contract):
    type: CalloutType
    text: Text


class Step(Contract):
    id: Slug
    title: Text
    minutes: Minutes
    goal: Text
    uses: Text
    level: Literal["basic", "intermediate", "advanced", "challenge"]
    intro: Text
    prompts: Annotated[list[Prompt], Field(max_length=4)]
    challenge: Challenge | None = None
    expected: Expected | None = None
    fallback: Text | None = None
    carries_forward: Text | None = None
    callouts: list[Callout]
    self_check: list[Text]


class Chapter(Contract):
    id: Slug
    title: Text
    minutes: Minutes
    format: Literal["interactive", "guided", "individual", "demo", "group"]
    story_so_far: Text
    builds_on: list[Slug]
    you_will_add: Text
    checkpoint_file_id: Slug | None = None
    steps: Annotated[list[Step], Field(min_length=1, max_length=6)]


class Troubleshooting(Contract):
    problem: Text
    fix: Text


class GlossaryEntry(Contract):
    term: Text
    definition: Text


class LabSpec(Contract):
    """LabSpec 2.0/2.1: one fictional story with optional typed evidence."""

    schema_version: Literal["2.0", "2.1"]
    locale: Locale = "en"
    title: Text
    subtitle: Text
    audience: Text
    duration_minutes: Minutes
    skill_level: Level
    products: Annotated[list[Text], Field(min_length=1)]
    functional_area: Text
    company: Company
    theme_id: Slug = "microsoft"
    narrative: Narrative
    through_line: ThroughLine | None = None
    files: list[LabFile]
    setup: Setup
    chapters: Annotated[list[Chapter], Field(min_length=2, max_length=10)]
    troubleshooting: list[Troubleshooting]
    glossary: list[GlossaryEntry]
    disclaimer: Text

    @model_validator(mode="after")
    def versioned_file_urls(self) -> Self:
        if self.schema_version == "2.1":
            for index, file in enumerate(self.files):
                if file.href is not None and urlsplit(file.href).scheme not in {"", "https"}:
                    raise ValueError(f"files.{index}.href: LabSpec 2.1 allows only HTTPS URLs or relative paths.")
        return self
