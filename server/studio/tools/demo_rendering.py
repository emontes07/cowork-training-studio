import html
from pathlib import Path
import re
from typing import Any, NotRequired, TypedDict
import unicodedata

from jinja2 import FileSystemLoader

from studio.schemas.demo_pack import DemoPackSpec
from studio.strings import STRINGS
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


def _md(text: str) -> str:
    escaped = html.escape(text, quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>-])", r"\\\1", escaped).replace("\r", "").replace("\n", "<br>")


def _readme(pack: DemoPackSpec) -> str:
    ui = STRINGS[pack.locale]
    cast = {member.id: member for member in pack.cast}
    lines = [
        f"# {_md(pack.title)}",
        "",
        f"{ui['scenario_label']} {_md(pack.company.name)} - {_md(pack.company.description)}",
        "",
        f"## {ui['files']}",
        "",
        f"| {ui['file']} | {ui['purpose']} | {ui['audience']} |",
        "| --- | --- | --- |",
        *[f"| {_md(file.filename)} | {_md(file.purpose)} | {ui[f'audience_{file.audience}']} |" for file in pack.files],
        "",
        f"## {ui['readme_seeded']}",
        "",
        *[
            f"- {ui[f'kind_{item.kind}']}: {_md(item.subject)}; {ui['fictional_sender']} {_md(cast[item.from_cast_id].name)}, "
            f"{_md(cast[item.from_cast_id].role)}; {ui['day_offset']} {item.day_offset} {ui['from']} {pack.as_of_date}."
            for item in pack.seeded_items
        ],
        "",
        f"## {ui['fictional_cast']}",
        "",
        *[
            f"- {_md(member.name)}: {_md(member.role)} "
            f"({ui['external_lower']}: {ui['bool_true'] if member.external else ui['bool_false']}; "
            f"{ui['executive_lower']}: {ui['bool_true'] if member.executive else ui['bool_false']})."
            for member in pack.cast
        ],
        "",
        f"## {ui['readme_payoffs']}",
        "",
        *[
            f"- {_md(payoff.id)} / {_md(payoff.scenario_id)}: {_md(payoff.finding)} "
            f"({ui['evidence_file']}: {_md(payoff.evidence_file_id)}; "
            f"{ui['buried']}: {ui['bool_true'] if payoff.buried else ui['bool_false']})."
            for payoff in pack.payoffs
        ],
        "",
        f"## {ui['demo_flow']}",
        "",
        f"1. {ui['flow_prepare']}",
        f"2. {ui['flow_run']}",
        f"3. {ui['flow_finish']}",
        "",
        f"## {ui['cleanup']}",
        "",
        *[f"- [ ] {_md(action)}" for action in pack.cleanup],
        "",
        f"## {ui['disclaimer']}",
        "",
        _md(pack.disclaimer),
        "",
        f"## {ui['credits']}",
        "",
        ui["credits_line"],
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
        spec=pack, ui=STRINGS[pack.locale], theme=_THEMES["microsoft"], stats=validation["stats"],
        words=words, seconds={identifier: round(count * 60 / 150, 1) for identifier, count in words.items()},
        files={file.id: file for file in pack.files},
        cast={member.id: member for member in pack.cast},
        payoffs={payoff.id: payoff for payoff in pack.payoffs},
    )
    return {
        "html": page, "filename": f"{pack.audience.prefix or slug}-demo-guide.html",
        "readme_md": _readme(pack), "stats": validation["stats"], "warnings": validation["warnings"],
    }
