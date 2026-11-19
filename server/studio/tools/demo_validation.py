from datetime import date
from difflib import SequenceMatcher
import re
from typing import Any, TypedDict

from pydantic import ValidationError

from studio.schemas.demo_pack import DemoPackSpec
from studio.tools.validation import (
    Issue, _needs_numeric_evidence, _section_number,
    has_expert_questions, has_fictional_parties, learner_voice_issues,
)


class DemoStats(TypedDict):
    scenario_count: int
    file_count: int
    cast_count: int
    tension_count: int
    payoff_count: int
    buried_payoff_count: int
    email_count: int
    meeting_count: int
    total_minutes: int


class DemoValidationResult(TypedDict):
    valid: bool
    errors: list[Issue]
    warnings: list[Issue]
    stats: DemoStats


def talk_track_words(text: str) -> int:
    return len(text.split())


def _normalized(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold()))


def _customer_name_in(text: str, customer: str) -> bool:
    customer_words = _normalized(customer).split()
    while len(customer_words) > 1 and customer_words[-1] in {"inc", "llc", "ltd", "corp", "corporation", "company", "co"}:
        customer_words.pop()
    name = "".join(customer_words)
    words = _normalized(text).split()
    if name in "".join(words):
        return True
    # Conservative near-spellings, not inferred abbreviations or semantic identity.
    if len(name) < 6:
        return False
    for size in {max(1, len(customer_words) - 1), len(customer_words), len(customer_words) + 1}:
        for index in range(len(words) - size + 1):
            candidate = "".join(words[index:index + size])
            if SequenceMatcher(None, name, candidate, autojunk=False).ratio() >= 0.9:
                return True
    return False


def get_demo_pack_schema() -> dict[str, Any]:
    """Return DemoPackSpec 1.0 JSON Schema before drafting a fictional demo pack.

    Choose function_pack or prompt_pack; keep public audience context separate
    from fictional companies, cast and records. Draft inputs before scenario
    prompts, then call validate_demo_pack and render_demo_guide.
    Conditional requirements, references and quality checks are enforced by the
    validator. Missing fact sources and quantitative evidence are warnings.
    The server never creates files, mail, chats or calendar items.
    """
    return DemoPackSpec.model_json_schema()


def validate_demo_pack(spec: dict[str, Any]) -> DemoValidationResult:
    """Validate DemoPackSpec 1.0 before rendering a fictional presenter guide.

    Returns top-level valid, errors, warnings and stats, with path/fix messages.
    Structural and reference errors block rendering; quality warnings do not.
    Keep real customer names in audience/title/talk tracks and filename prefixes,
    not fictional records. This is a conservative authoring check, not a privacy
    guarantee. No source URLs are fetched and nothing is saved, sent or seeded.
    """
    errors: list[Issue] = []
    warnings: list[Issue] = []
    stats = DemoStats(
        scenario_count=0, file_count=0, cast_count=0, tension_count=0, payoff_count=0,
        buried_payoff_count=0, email_count=0, meeting_count=0, total_minutes=0,
    )
    try:
        pack = DemoPackSpec.model_validate(spec)
    except ValidationError as error:
        for item in error.errors(include_input=False, include_url=False):
            errors.append({
                "code": "schema_error", "path": ".".join(str(part) for part in item["loc"]) or "$",
                "message": f"{item['msg']}; correct this field to match get_demo_pack_schema.",
            })
        return {"valid": False, "errors": errors, "warnings": warnings, "stats": stats}

    def issue(target: list[Issue], code: str, path: str, message: str) -> None:
        target.append({"code": code, "path": path, "message": message})

    def reference(value: str | None, allowed: set[str], path: str, collection: str) -> None:
        if value is not None and value not in allowed:
            issue(errors, "unknown_reference", path, f"Unknown reference {value!r}; use an existing {collection} ID.")

    cast = {item.id: item for item in pack.cast}
    files = {item.id: item for item in pack.files}
    scenarios = {item.id: item for item in pack.scenarios}
    payoffs = {item.id: item for item in pack.payoffs}
    seen: set[str] = set()
    for collection in ("cast", "tensions", "payoffs", "files", "scenarios", "seeded_items"):
        for index, item in enumerate(getattr(pack, collection)):
            if item.id in seen:
                issue(errors, "duplicate_id", f"{collection}.{index}.id", "Use an ID unique across all demo-pack collections.")
            seen.add(item.id)
    stats.update(
        scenario_count=len(pack.scenarios), file_count=len(pack.files), cast_count=len(pack.cast),
        tension_count=len(pack.tensions), payoff_count=len(pack.payoffs),
        buried_payoff_count=sum(item.buried for item in pack.payoffs),
        email_count=sum(item.kind == "email" for item in pack.seeded_items),
        meeting_count=sum(item.kind == "meeting" for item in pack.seeded_items),
        total_minutes=sum(item.minutes for item in pack.run_of_show),
    )
    prefix = pack.audience.prefix
    customer = pack.audience.customer_name
    if (pack.mode == "function_pack" or customer) and prefix is None:
        issue(errors, "missing_prefix", "audience.prefix", "Supply exactly three uppercase letters for this pack.")
    if customer:
        expected_prefix = re.sub(r"[^a-zA-Z]", "", customer)[:3].upper()
        if prefix != expected_prefix:
            issue(errors, "prefix_mismatch", "audience.prefix",
                  f"Use the first three letters of customer_name, with spaces/nonletters removed: {expected_prefix!r}.")
    if pack.mode == "prompt_pack" and pack.source_prompt is None:
        issue(errors, "missing_source_prompt", "source_prompt", "Include the original demo prompt verbatim for prompt_pack.")
    if pack.mode == "function_pack" and len(pack.scenarios) != (pack.scenario_count or 4):
        issue(errors, "scenario_count", "scenarios", "Supply four scenarios, or set scenario_count to the intended positive count.")

    def filename_check(filename: str, path: str) -> None:
        if pack.mode == "function_pack" and prefix and not filename.startswith(f"{prefix}_"):
            issue(errors, "filename_prefix", path, f"Start the filename with {prefix}_.")

    for index, file in enumerate(pack.files):
        path = f"files.{index}"
        filename_check(file.filename, f"{path}.filename")
        for i, identifier in enumerate(file.used_by):
            reference(identifier, set(scenarios), f"{path}.used_by.{i}", "scenarios")
        for i, identifier in enumerate(file.contains_payoffs):
            reference(identifier, set(payoffs), f"{path}.contains_payoffs.{i}", "payoffs")
        if not any(file.id in scenario.input_file_ids for scenario in pack.scenarios):
            issue(warnings, "unused_file", path, "Use this file in a scenario input_file_ids list or remove it.")
        if not file.contains_payoffs:
            issue(warnings, "file_without_payoffs", f"{path}.contains_payoffs", "List the payoffs planted in this file.")
        warnings.extend(learner_voice_issues(file.purpose, f"{path}.purpose"))
    for index, scenario in enumerate(pack.scenarios):
        path = f"scenarios.{index}"
        for field, allowed in (("input_file_ids", set(files)), ("payoff_ids", set(payoffs))):
            for i, identifier in enumerate(getattr(scenario, field)):
                reference(identifier, allowed, f"{path}.{field}.{i}", "files" if field == "input_file_ids" else "payoffs")
        for i, output in enumerate(scenario.expected_outputs):
            filename_check(output.filename, f"{path}.expected_outputs.{i}.filename")
        if pack.mode == "function_pack" and {output.format for output in scenario.expected_outputs} != {"xlsx", "docx", "pptx", "html"}:
            issue(errors, "output_formats", f"{path}.expected_outputs", "List all four output formats: xlsx, docx, pptx and html.")
        words = talk_track_words(scenario.talk_track)
        if not 150 <= words <= 300:
            issue(warnings, "talk_track_length", f"{path}.talk_track",
                  f"Talk track has {words} words; use 150-300 words for 60-120 seconds at 150 words/minute.")
        if not scenario.payoff_ids:
            issue(warnings, "scenario_without_payoff", f"{path}.payoff_ids", "Plant and reference at least one payoff for this scenario.")
        for i, identifier in enumerate(scenario.payoff_ids):
            if identifier in payoffs and payoffs[identifier].scenario_id != scenario.id:
                issue(warnings, "payoff_scenario", f"{path}.payoff_ids.{i}", "Use a payoff assigned to this scenario.")
        for field in ("prompt", "talk_track"):
            warnings.extend(learner_voice_issues(getattr(scenario, field), f"{path}.{field}"))
        if pack.mode == "function_pack":
            for earlier_index, earlier in enumerate(pack.scenarios[:index]):
                if earlier.function == scenario.function:
                    issue(warnings, "duplicate_function", f"{path}.function", "Use a different function to broaden the function pack.")
                if SequenceMatcher(None, earlier.prompt, scenario.prompt, autojunk=False).find_longest_match().size >= 80:
                    issue(warnings, "similar_prompts", f"{path}.prompt",
                          f"Prompt shares at least 80 consecutive characters with scenarios.{earlier_index}.prompt; tailor the task and wording.")
    for index, payoff in enumerate(pack.payoffs):
        path = f"payoffs.{index}"
        reference(payoff.scenario_id, set(scenarios), f"{path}.scenario_id", "scenarios")
        reference(payoff.evidence_file_id, set(files), f"{path}.evidence_file_id", "files")
        scenario = scenarios.get(payoff.scenario_id)
        if scenario and payoff.id not in scenario.payoff_ids:
            issue(warnings, "unused_payoff", path, "Add this payoff to its scenario payoff_ids.")
        if scenario and payoff.evidence_file_id not in scenario.input_file_ids:
            issue(warnings, "payoff_input", f"{path}.evidence_file_id", "Include the evidence file in this scenario input_file_ids.")
        evidence_file = files.get(payoff.evidence_file_id)
        if evidence_file and payoff.id not in evidence_file.contains_payoffs:
            issue(warnings, "payoff_file", f"{path}.evidence_file_id", "List this payoff in its evidence file contains_payoffs.")
        if _needs_numeric_evidence(payoff.finding) and payoff.evidence is None:
            issue(warnings, "missing_numeric_evidence", f"{path}.evidence", "Add typed evidence with the checked quantities behind this finding.")
        if payoff.evidence:
            evidence = payoff.evidence
            if evidence.source_file:
                reference(evidence.source_file, set(files) | {f.filename for f in pack.files}, f"{path}.evidence.source_file", "files (ID or exact filename)")
                if evidence_file and evidence.source_file not in {evidence_file.id, evidence_file.filename}:
                    issue(warnings, "evidence_source_mismatch", f"{path}.evidence.source_file", "Name the same source as evidence_file_id.")
            elif evidence.kind in {"quote", "clause"}:
                issue(warnings, "key_fact_source", f"{path}.evidence.source_file", "Name the declared evidence file for this quote or clause.")
            if evidence.kind == "clause" and _section_number(evidence.section) is None:
                issue(warnings, "clause_section", f"{path}.evidence.section", "Add the clause section number, for example 2.1.")
    if stats["buried_payoff_count"] < 2:
        issue(warnings, "buried_payoffs", "payoffs", "Plant at least two buried findings and mark them buried: true.")
    if not 6 <= len(pack.cast) <= 9:
        issue(warnings, "cast_size", "cast", "Use a fictional cast of six to nine people.")
    if not any(item.external for item in pack.cast):
        issue(warnings, "missing_external", "cast", "Include at least one fictional external party.")
    if not any(item.executive for item in pack.cast):
        issue(warnings, "missing_executive", "cast", "Include at least one fictional executive.")
    if not 3 <= len(pack.tensions) <= 5:
        issue(warnings, "tension_count", "tensions", "Include three to five dated tensions.")
    if not any(item.slipping for item in pack.tensions):
        issue(warnings, "missing_slipping_tension", "tensions", "Mark at least one tension as slipping.")
    for index, tension in enumerate(pack.tensions):
        reference(tension.owner_cast_id, set(cast), f"tensions.{index}.owner_cast_id", "cast")
        if date.fromisoformat(tension.due_date) < date.fromisoformat(pack.as_of_date):
            issue(warnings, "past_due_date", f"tensions.{index}.due_date", "Move the deadline to as_of_date or later, or update the pack date.")
    for index, item in enumerate(pack.run_of_show):
        reference(item.scenario_id, set(scenarios), f"run_of_show.{index}.scenario_id", "scenarios")
    for index, fact in enumerate(pack.context.facts):
        if fact.source_url is None:
            issue(warnings, "missing_fact_source", f"context.facts.{index}.source_url", "Add an HTTPS public source URL or move this statement to assumptions.")
    fact_texts = {_normalized(fact.text) for fact in pack.context.facts}
    for index, assumption in enumerate(pack.context.assumptions):
        if _normalized(assumption) in fact_texts:
            issue(warnings, "duplicate_assumption", f"context.assumptions.{index}", "Keep this statement only in facts, or rewrite the distinct assumption.")
    if customer and not any(pack.context.model_dump().values()):
        issue(warnings, "empty_context", "context", "Add a light public-context summary, separating sourced facts from assumptions.")
    if customer:
        record_fields = [("company.name", pack.company.name), ("company.description", pack.company.description)]
        for collection, fields in (
            ("cast", ("name", "role")), ("tensions", ("problem",)),
            ("payoffs", ("finding",)), ("files", ("purpose",)),
            ("scenarios", ("persona", "business_context", "prompt")),
            ("seeded_items", ("subject", "body")), ("run_of_show", ("action",)),
        ):
            for index, item in enumerate(getattr(pack, collection)):
                record_fields.extend((f"{collection}.{index}.{field}", getattr(item, field)) for field in fields)
        for index, payoff in enumerate(pack.payoffs):
            if payoff.evidence:
                record_fields.append((f"payoffs.{index}.evidence.text", payoff.evidence.text))
        for index, scenario in enumerate(pack.scenarios):
            record_fields.extend((f"scenarios.{index}.follow_ups.{i}", text) for i, text in enumerate(scenario.follow_ups))
        for path, text in record_fields:
            if _customer_name_in(text, customer):
                issue(warnings, "customer_in_seeded_data", path,
                      "use a fictional stand-in company; keep the customer name in the audience/title only")
    for kind, count, limit in (("email", stats["email_count"], 8), ("meeting", stats["meeting_count"], 5)):
        if count > limit:
            issue(warnings, "seeded_item_count", "seeded_items", f"Reduce {kind} items to at most {limit}; currently {count}.")
    for index, item in enumerate(pack.seeded_items):
        path = f"seeded_items.{index}"
        reference(item.from_cast_id, set(cast), f"{path}.from_cast_id", "cast")
        if abs(item.day_offset) > 30:
            issue(warnings, "seeded_date_range", f"{path}.day_offset", "Keep seeded dates within 30 days of as_of_date.")
        sender = cast.get(item.from_cast_id)
        if sender:
            label = f"[Demo scenario message \u2014 from {sender.name}, {sender.role}]"
            if not item.body.splitlines() or item.body.splitlines()[0] != label:
                issue(warnings, "seeded_sender_label", f"{path}.body", f"Start the body with the exact label line {label!r}.")
    sensitive = any(s.function in {"HR", "Legal"} for s in pack.scenarios) or bool(
        re.search(r"\b(?:health\w*|medical|legal|finance advice|financial advice)\b", pack.audience.industry, re.I)
    )
    if sensitive:
        if "not professional advice" not in pack.disclaimer.casefold():
            issue(warnings, "missing_advice_note", "disclaimer", "Add 'practice exercise, not professional advice'.")
        if not any(has_expert_questions(" ".join([s.prompt, s.business_context, *s.follow_ups])) for s in pack.scenarios):
            issue(warnings, "missing_expert_questions", "scenarios", "Turn interpretations or uncertainty into questions for an expert, separate from source text.")
        if not has_fictional_parties(f"{pack.disclaimer} {pack.company.description}"):
            issue(warnings, "missing_fictional_parties", "disclaimer", "State that all parties are fictional.")
    if stats["total_minutes"] != pack.default_minutes:
        issue(warnings, "run_of_show_minutes", "run_of_show",
              f"Agenda totals {stats['total_minutes']} minutes; adjust it to default_minutes ({pack.default_minutes}).")
    disclaimer = _normalized(pack.disclaimer)
    if not (
        re.search(r"\ball people and data are fictional\b", disclaimer)
        and (not customer or re.search(r"\breal customer names are used only (?:as|for) context\b", disclaimer))
    ):
        required_disclaimer = "All people and data are fictional."
        if customer:
            required_disclaimer += " Real customer names are used only as context."
        issue(warnings, "demo_disclaimer", "disclaimer", f"State '{required_disclaimer}'")
    return {"valid": not errors, "errors": errors, "warnings": warnings, "stats": stats}
