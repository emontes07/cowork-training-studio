import json
from copy import deepcopy
from pathlib import Path
from typing import Literal, TypedDict


class RequiredInput(TypedDict):
    name: str
    description: str
    example: str


class SessionFormat(TypedDict):
    id: str
    name: str
    description: str
    status: Literal["available", "coming_soon"]
    best_for: list[str]
    required_inputs: list[RequiredInput]
    default_duration_minutes: int
    produced_by_skill: Literal["build-training-lab"] | None


_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "session_formats.json"
with _DATA_PATH.open(encoding="utf-8") as data_file:
    _SESSION_FORMATS: list[SessionFormat] = json.load(data_file)


def list_session_formats(id: str | None = None) -> list[SessionFormat]:
    """Return a JSON list of available and planned Cowork training formats.

    Call before choosing a format or gathering inputs for a training skill.
    Each item includes id, name, description, best_for, required_inputs
    (name, description, example), default_duration_minutes, status, and produced_by_skill.
    Only html_lab is available, through the shipped build-training-lab skill.
    Other formats are coming_soon with no skill; do not offer them as available.
    Omit id to return all formats. Supply an exact, case-sensitive id to return
    a one-item list. An unknown id raises an error. This tool returns metadata only;
    it does not write content, create files, or save or send anything.
    """
    formats = _SESSION_FORMATS
    if id is not None:
        formats = [session_format for session_format in formats if session_format["id"] == id]
        if not formats:
            raise ValueError(
                f"Unknown session format id: {id!r}. "
                "Call list_session_formats without an id for valid IDs."
            )
    return deepcopy(formats)
