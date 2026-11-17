import json
from pathlib import Path
import re
from typing import Any, TypedDict
import unicodedata

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from studio.schemas.lab_spec import LabSpec
from studio.tools.validation import Issue, Stats, validate_lab_spec


class RenderSuccess(TypedDict):
    html: str
    filename: str
    stats: Stats
    warnings: list[Issue]


class RenderFailure(TypedDict):
    errors: list[Issue]
    stats: Stats
    warnings: list[Issue]


_STUDIO = Path(__file__).resolve().parent.parent
with (_STUDIO / "data" / "themes" / "microsoft.json").open(encoding="utf-8") as data_file:
    _THEMES: dict[str, dict[str, str]] = {"microsoft": json.load(data_file)}

_TEMPLATES = Environment(
    loader=FileSystemLoader(_STUDIO / "templates" / "lab"),
    autoescape=True,
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)
_FILE_LABELS = {
    "source": "Source files",
    "checkpoint": "Checkpoints - Only if you fall behind",
    "answer_key": "Answer keys",
    "worksheet": "Worksheets",
    "extra": "Extra references",
}


def render_lab_page(spec: dict[str, Any], theme_id: str | None = None) -> RenderSuccess | RenderFailure:
    """Validate fictional LabSpec 2.0 and return one self-contained story lab page.

    Success returns html, filename, stats, and quality warnings. Invalid specs
    or unsupported themes return errors, stats, and warnings with NO html.
    theme_id overrides spec.theme_id; only microsoft is supported.
    All spec text is escaped, prompts stay paste-ready, and CSS/JS are inline.
    File hrefs become links; absent hrefs are labeled Provided separately.
    No files are created or saved; Cowork must save the returned HTML itself.
    """
    result = validate_lab_spec(spec)
    if not result["valid"]:
        return {
            "errors": result["errors"], "stats": result["stats"],
            "warnings": result["warnings"],
        }
    lab_spec = LabSpec.model_validate(spec)
    chosen_theme = lab_spec.theme_id if theme_id is None else theme_id
    if chosen_theme not in _THEMES:
        return {
            "errors": [{
                "code": "unknown_theme", "path": "theme_id",
                "message": "Unsupported theme; only 'microsoft' is available.",
            }],
            "stats": result["stats"], "warnings": result["warnings"],
        }
    title_ascii = unicodedata.normalize("NFKD", lab_spec.title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", title_ascii.lower()).strip("-") or "training-lab"
    elapsed = 0
    time_ranges: dict[str, tuple[int, int]] = {}
    for chapter in lab_spec.chapters:
        time_ranges[chapter.id] = (elapsed, elapsed + chapter.minutes)
        elapsed += chapter.minutes
    html = _TEMPLATES.get_template("base.html.j2").render(
        spec=lab_spec,
        theme=_THEMES[chosen_theme],
        stats=result["stats"],
        time_ranges=time_ranges,
        chapters_by_id={chapter.id: chapter for chapter in lab_spec.chapters},
        files_by_id={file.id: file for file in lab_spec.files},
        file_groups=[
            (label, [file for file in lab_spec.files if file.kind == kind])
            for kind, label in _FILE_LABELS.items()
        ],
    )
    return {
        "html": html, "filename": f"{slug}.html",
        "stats": result["stats"], "warnings": result["warnings"],
    }
