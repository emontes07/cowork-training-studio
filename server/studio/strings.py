import json
from pathlib import Path


with (Path(__file__).parent / "data" / "ui_strings.json").open(encoding="utf-8") as source:
    _TABLE: dict[str, dict[str, str]] = json.load(source)

STRINGS: dict[str, dict[str, str]] = {
    locale: {key: translations[locale] for key, translations in _TABLE.items()}
    for locale in ("en", "es")
}
