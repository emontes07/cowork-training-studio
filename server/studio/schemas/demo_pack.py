from datetime import date
import re
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import AfterValidator, Field

from studio.schemas.lab_spec import Contract, KeyFact, LabFile, Minutes, PromptText, SafeURL, Slug, Text


def iso_date(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Use an ISO date in YYYY-MM-DD form.")
    date.fromisoformat(value)
    return value


def https_url(value: str) -> str:
    if urlsplit(value).scheme != "https":
        raise ValueError("Use an HTTPS URL.")
    return value


def demo_file_url(value: str) -> str:
    if urlsplit(value).scheme not in {"", "https"}:
        raise ValueError("Use an HTTPS URL or relative path, as in LabSpec 2.1.")
    return value


DateText = Annotated[str, AfterValidator(iso_date), Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
HTTPS = Annotated[SafeURL, AfterValidator(https_url)]
FileURL = Annotated[SafeURL, AfterValidator(demo_file_url)]
Filename = Annotated[Text, AfterValidator(LabFile.relative_filename)]
Prefix = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
InputFormat = Literal["docx", "xlsx", "pptx", "csv", "md"]
OutputFormat = Literal["xlsx", "docx", "pptx", "html"]


class Audience(Contract):
    customer_name: Text | None = None
    customer_website: HTTPS | None = None
    prefix: Prefix | None = None
    industry: Text


class ContextFact(Contract):
    text: Text
    source_url: HTTPS | None = None


class PublicContext(Contract):
    business_model: list[Text]
    kpis: list[Text]
    pressures: list[Text]
    facts: list[ContextFact]
    assumptions: list[Text]


class DemoCompany(Contract):
    name: Text
    description: Text


class Presenter(Contract):
    role: Text


class CastMember(Contract):
    id: Slug
    name: Text
    role: Text
    external: bool
    executive: bool


class Tension(Contract):
    id: Slug
    problem: Text
    due_date: DateText
    slipping: bool
    owner_cast_id: Slug | None = None


class Payoff(Contract):
    id: Slug
    finding: Text
    scenario_id: Slug
    evidence_file_id: Slug
    buried: bool
    evidence: KeyFact | None = None


class DemoFile(Contract):
    id: Slug
    filename: Filename
    format: InputFormat
    purpose: Text
    used_by: list[Slug]
    contains_payoffs: list[Slug]
    href: FileURL | None = None
    audience: Literal["presenter", "attendee"] = "presenter"


class ExpectedOutput(Contract):
    format: OutputFormat
    filename: Filename


class Scenario(Contract):
    id: Slug
    function: Literal["HR", "Finance", "Marketing", "Sales", "Operations", "Legal", "IT", "Customer service", "Other"]
    title: Text
    persona: Text
    business_context: Text
    input_file_ids: list[Slug]
    prompt: PromptText
    expected_outputs: list[ExpectedOutput]
    payoff_ids: list[Slug]
    talk_track: Text
    follow_ups: Annotated[list[Text], Field(min_length=2, max_length=2)]


class SeededItem(Contract):
    id: Slug
    kind: Literal["email", "meeting"]
    from_cast_id: Slug
    subject: Text
    day_offset: int
    importance: Literal["normal", "high"] | None = None
    body: PromptText


class RunOfShowItem(Contract):
    minutes: Minutes
    action: Text
    scenario_id: Slug | None = None


class DemoPackSpec(Contract):
    """DemoPackSpec 1.0; fictional records with separate audience context."""

    schema_version: Literal["1.0"]
    mode: Literal["function_pack", "prompt_pack"]
    title: Text
    as_of_date: DateText
    default_minutes: Minutes
    scenario_count: Annotated[int, Field(gt=0)] | None = None
    audience: Audience
    context: PublicContext
    company: DemoCompany
    presenter: Presenter
    source_prompt: PromptText | None = None
    cast: list[CastMember]
    tensions: list[Tension]
    payoffs: list[Payoff]
    files: list[DemoFile]
    scenarios: Annotated[list[Scenario], Field(min_length=1)]
    seeded_items: list[SeededItem] = Field(default_factory=list)
    run_of_show: list[RunOfShowItem]
    cleanup: list[Text]
    disclaimer: Text
