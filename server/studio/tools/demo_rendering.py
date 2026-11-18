import html
from pathlib import Path
import re
from typing import Any, NotRequired, TypedDict
import unicodedata

from jinja2 import FileSystemLoader

from studio.schemas.demo_pack import DemoPackSpec
from studio.tools.demo_validation import DemoStats, talk_track_words, validate_demo_pack
from studio.tools.rendering import _TEMPLATES, _THEMES
from studio.tools.validation import Issue


class DemoRenderResult(TypedDict):
    stats: DemoStats
    warnings: list[Issue]
    html: NotRequired[str]
    filename: NotRequired[str]
    readme_md: NotRequired[str]
    errors: NotRequired[list[Issue]]


_TEMPLATE_ROOT = Path(__file__).resolve().parent.parent / "templates"
_DEMO_TEMPLATES = _TEMPLATES.overlay(loader=FileSystemLoader([
    _TEMPLATE_ROOT / "demo", _TEMPLATE_ROOT / "lab",
]))
_CREDITS = "Demo pack approach adapted from work by Shailesh Mittal and Giovanna; see CREDITS.md"


def _md(text: str) -> str:
    escaped = html.escape(text, quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>-])", r"\\\1", escaped).replace("\r", "").replace("\n", "<br>")


def _readme(pack: DemoPackSpec) -> str:
    cast = {member.id: member for member in pack.cast}
    lines = [
        f"# {_md(pack.title)}",
        "",
        f"Scenario: {_md(pack.company.name)} - {_md(pack.company.description)}",
        "",
        "## Files",
        "",
        "| File | Purpose | Audience |",
        "| --- | --- | --- |",
        *[f"| {_md(file.filename)} | {_md(file.purpose)} | {file.audience} |" for file in pack.files],
        "",
        "## Seeded items (presenter mailbox/calendar only; not created or sent)",
        "",
        *[
            f"- {item.kind}: {_md(item.subject)}; fictional sender {_md(cast[item.from_cast_id].name)}, "
            f"{_md(cast[item.from_cast_id].role)}; day offset {item.day_offset} from {pack.as_of_date}."
            for item in pack.seeded_items
        ],
        "",
        "## Fictional cast",
        "",
        *[f"- {_md(member.name)}: {_md(member.role)} (external: {member.external}; executive: {member.executive})." for member in pack.cast],
        "",
        "## Presenter-only planted payoffs",
        "",
        *[
            f"- {_md(payoff.id)} / {_md(payoff.scenario_id)}: {_md(payoff.finding)} "
            f"(evidence file: {_md(payoff.evidence_file_id)}; buried: {payoff.buried})."
            for payoff in pack.payoffs
        ],
        "",
        "## Three-step demo flow",
        "",
        "1. With presenter permission, build and check all fictional input files fully before the prompt pack; never in parallel.",
        "2. Follow the run of show, run each scenario prompt, and compare outputs with the planted evidence.",
        "3. Use the follow-ups, debrief the findings, then complete cleanup in the presenter workspace.",
        "",
        "## Cleanup",
        "",
        *[f"- [ ] {_md(action)}" for action in pack.cleanup],
        "",
        "## Disclaimer",
        "",
        _md(pack.disclaimer),
        "",
        "## Credits",
        "",
        _CREDITS,
        "",
    ]
    return "\n".join(lines)


def render_demo_guide(spec: dict[str, Any]) -> DemoRenderResult:
    """Validate DemoPackSpec and return an offline presenter guide plus README text.

    Success has top-level html, filename, readme_md, stats and warnings. Save
    readme_md as 00_DEMO_README.md using Cowork tools. Errors return errors,
    stats and warnings with no HTML/README. Prompts stay verbatim and all spec
    content is escaped. Only attendee file hrefs become links. Presenter notes
    are collapsed, not access-controlled; do not share the guide as an attendee
    handout. No files, mail, chats or calendar items are created or sent.
    """
    validation = validate_demo_pack(spec)
    if not validation["valid"]:
        return {"errors": validation["errors"], "stats": validation["stats"], "warnings": validation["warnings"]}
    pack = DemoPackSpec.model_validate(spec)
    title_ascii = unicodedata.normalize("NFKD", pack.title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", title_ascii.lower()).strip("-") or "demo"
    words = {scenario.id: talk_track_words(scenario.talk_track) for scenario in pack.scenarios}
    page = _DEMO_TEMPLATES.get_template("guide.html.j2").render(
        spec=pack, theme=_THEMES["microsoft"], stats=validation["stats"],
        words=words, seconds={identifier: round(count * 60 / 150, 1) for identifier, count in words.items()},
        files={file.id: file for file in pack.files},
        cast={member.id: member for member in pack.cast},
        payoffs={payoff.id: payoff for payoff in pack.payoffs},
    )
    return {
        "html": page, "filename": f"{pack.audience.prefix or slug}-demo-guide.html",
        "readme_md": _readme(pack), "stats": validation["stats"], "warnings": validation["warnings"],
    }
