from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, field_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Slug = Annotated[Text, Field(pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")]
Level = Literal["basic", "intermediate", "advanced"]
CalloutType = Literal["tip", "warning", "important", "note", "instructor", "real_world", "stretch"]
Minutes = Annotated[int, Field(gt=0)]


def nonblank_prompt(value: str) -> str:
    if not value.strip():
        raise ValueError("Prompts must not be empty or whitespace-only.")
    return value


Prompt = Annotated[str, Field(min_length=1), AfterValidator(nonblank_prompt)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Company(Contract):
    name: Text
    is_fictional: bool
    description: Text


class Resource(Contract):
    label: Text
    url: str | None
    note: str

    @field_validator("url")
    @classmethod
    def safe_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value or any(character.isspace() or ord(character) < 32 for character in value):
            raise ValueError("Resource URLs must be nonempty and contain no whitespace or controls.")
        if "\\" in value or value.startswith("//"):
            raise ValueError("Use an explicit http/https URL or a relative path, not a network path.")
        parts = urlsplit(value)
        if parts.scheme not in {"", "http", "https", "mailto"}:
            raise ValueError("Resource URLs allow only https, http, mailto, or relative paths.")
        if parts.scheme in {"http", "https"} and not parts.hostname:
            raise ValueError("HTTP resource URLs must include a host.")
        if parts.scheme == "mailto" and not parts.path:
            raise ValueError("Mailto resource URLs must include an address.")
        if parts.username is not None or parts.password is not None:
            raise ValueError("Resource URLs must not contain credentials.")
        return value


class Story(Contract):
    context: str = ""
    stakeholder: str = ""
    time_pressure: str = ""
    source_material: str = ""
    deliverable: str = ""

    @field_validator("*")
    @classmethod
    def strip_story_field(cls, value: str) -> str:
        return value.strip()


class Exercise(Contract):
    instruction: Text
    prompt: Prompt
    expected_outcome: Text


class Callout(Contract):
    type: CalloutType
    text: Text


class Lab(Contract):
    id: Slug
    title: Text
    goal: Text
    minutes: Minutes
    difficulty: Level
    source: Text
    context: Text
    exercises: Annotated[list[Exercise], Field(min_length=1, max_length=4)]
    callouts: list[Callout]
    self_check: Annotated[list[Text], Field(min_length=2)]


class Scenario(Contract):
    id: Slug
    title: Text
    story: Story
    labs: Annotated[list[Lab], Field(min_length=2, max_length=5)]


class Capstone(Contract):
    prompt: Prompt
    deliverable: Text
    debrief_questions: Annotated[list[Text], Field(min_length=1)]


class LabSpec(Contract):
    """Fictional, spec-first training page. All content is plain text, not HTML."""

    title: Text
    subtitle: Text
    audience: Text
    duration_minutes: Minutes
    skill_level: Level
    products: Annotated[list[Text], Field(min_length=1)]
    functional_area: Text
    company: Company
    theme_id: Slug = "microsoft"
    objectives: Annotated[list[Text], Field(min_length=3, max_length=6)]
    prerequisites: list[Text]
    resources: list[Resource]
    ground_rules: list[Text]
    scenarios: Annotated[list[Scenario], Field(min_length=2, max_length=4)]
    capstone: Capstone | None = None
