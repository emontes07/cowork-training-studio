# Cowork Training Studio

A stateless MCP server for Microsoft 365 Copilot Cowork training workflows.
**Skills own judgment, MCP owns consistency.** Skills write content; Cowork's
own tools save and send it.

M4b ships LabSpec **2.1**, retaining **2.0** support:
`get_lab_spec_schema` -> `validate_lab_spec` -> `render_lab_page`.
The result is one self-contained HTML page, returned to Cowork rather than
saved by the server. Plugin **0.1.3** adds three workshop blueprints and a checked
learner/facilitator pack workflow, backed by the five-tool Azure server.
Version 2 replaces M2's scenario/lab contract; v1 specs are rejected.

M5a adds the server-only **DemoPackSpec 1.0** pipeline below: eight tools locally,
but Azure and plugin 0.1.3 still expose the five M4b tools. `demo_pack` remains
`coming_soon` until the M5b skill/release; this checkpoint is not deployed.

No authentication, secrets, Microsoft Graph calls, telemetry integration,
tenant-data access, or generated-content storage. Use fictional Zava-style
scenarios only. This unauthenticated scaffold is for local/trusted testing,
not public production use.

## Setup

Use Python 3.13 (also used by the container). From the repository root:

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r server/requirements.txt pytest
```

FastMCP 2.14.7 and the MCP SDK 1.30.0 are pinned exactly, following the reference
implementation's FastMCP 2.x baseline and including the SDK's stateless-stream
cleanup fix. Background tasks are disabled and FastMCP's internal worker backend
is forced to in-process memory in code. No request content is persisted.
Other transitive dependencies are resolved by pip; this is not a full lockfile.

## Run locally

### STDIO (default)

```sh
source .venv/bin/activate
cd server
python main.py
```

STDIO is intended for an MCP client launching the process, not for typing
ordinary text into the terminal. `MCP_TRANSPORT=stdio` can also be set explicitly.

### Streamable HTTP

```sh
source .venv/bin/activate
cd server
MCP_TRANSPORT=streamable-http PORT=8000 python main.py
```

`MCP_TRANSPORT=http` is an alias for streamable HTTP. The server listens on
`0.0.0.0:$PORT` (default `8000`) at `/mcp`, with stateless HTTP enabled so replicas
do not require sticky sessions.
Unsupported transports and invalid HTTP ports fail explicitly.

In another terminal:

```sh
curl -i http://127.0.0.1:8000/mcp/
```

An HTTP response proves a listener is reachable, not that an MCP exchange
succeeded. Depending on headers and path normalization, a simple GET can return
`200`, `404`, `405`, `406`, or a redirect. To follow a trailing-slash redirect:

```sh
curl -i -L http://127.0.0.1:8000/mcp/
```

On macOS, prefer **`127.0.0.1` rather than `localhost`**: `localhost` may resolve
to IPv6 `::1`, while this server's `0.0.0.0` binding is IPv4. Do not use
`0.0.0.0` as the client URL. Stop the server with Ctrl+C.

## MCP Inspector

Install Node.js/npm separately if needed. From the repository root, with the
Python environment activated:

```sh
npx @modelcontextprotocol/inspector python server/main.py
```

For HTTP, start the HTTP server first, then launch Inspector:

```sh
npx @modelcontextprotocol/inspector
```

Open the displayed local Inspector URL, choose **Streamable HTTP**, and connect
to `http://127.0.0.1:8000/mcp`. Keep Inspector's local security defaults; its
local proxy token is not server authentication. Use **List Tools**, then call
`list_session_formats` with `{}` or `{"id":"html_lab"}`. The story pipeline exposes
`get_lab_spec_schema` (no arguments), `validate_lab_spec` (`{"spec": ...}`),
and `render_lab_page` (`{"spec": ..., "theme_id": "microsoft"}`).

## Tool contract

`list_session_formats(id: str | None = None)` returns a JSON list:

- No ID: all four formats in catalog order.
- Exact, case-sensitive ID: a one-item list, never a bare object.
- Unknown or empty ID: an explicit tool error.

Each entry includes `id`, `name`, `description`, `best_for`,
`required_inputs` (a list of `name`, `description`, `example` objects),
`default_duration_minutes`, `status`, and `produced_by_skill`.
`html_lab` is `available` through the shipped `build-training-lab` skill.
`word_guide`, `demo_pack`, and `prompt_a_thon` are `coming_soon`, not available
yet, with `produced_by_skill: null`. Planned formats remain discoverable but
must not be offered as ready-to-use capabilities.

The underlying Python functions stay directly callable. FastMCP may wrap a
list in the MCP structured-content `result` field on the wire. The renderer's
`html`, `filename`, `stats`, and `warnings` are top-level structured content,
as are the validator's `valid`, `errors`, `warnings`, and `stats`. Invalid
renders return top-level `errors`, `stats`, and `warnings` without HTML or a
filename. Both tools also include the same object as JSON in a text block for
clients without structured-content support. The smoke client reads structured
content directly rather than SDK-generated Python model objects.

## Workshop blueprints

When the learner has no shape in mind, call `get_blueprint()` and offer the three
summaries in `blueprints`. Call again with an exact `blueprint_id` for top-level
`id`, `title`, `default_minutes`, `best_for`, `required_inputs`, `chapter_outline`
(`title`, `minutes`, `purpose`, `step_patterns`), `quality_bar` and `ends_with`.
Unknown IDs raise an explicit error. Results are static, read-only metadata;
they are not complete LabSpecs or created files.

| ID | Minutes | Shape |
| --- | --- | --- |
| `app_deep_dive` | 60 | One role/workflow, raw inputs to deliverable, then a reviewed personal skill tested on new data. |
| `prompt_to_agent_ladder` | 90 | Single prompt, file grounding, multi-step Cowork task, personal skill, optional presenter-led shared skill/agent. |
| `domain_super_day` | 300 | Foundations, three role labs and a prompt-challenge close, with breaks, using one invented company. |

For the super-day, `chapter_outline` is the day agenda, and `lab_outlines`
contains five separate outlines with `id`, `title`, `format_id`, `default_minutes`
and `chapter_outline`. Every lab agenda slot names `lab_id` and matches the lab's
title and duration; non-lab slots are breaks. The day totals 300 minutes including
breaks, and each lab's chapters total its own duration. Build each as a separate
`html_lab`; the closing challenge moves to `prompt_a_thon` only once that format
ships. The optional shared-skill/agent rung has a sharing-plan fallback; no
tenant capabilities are assumed.

## Demo-pack pipeline (M5a, local only)

1. Call `get_demo_pack_schema` and draft `schema_version: "1.0"` with
   `mode: "function_pack"` or `"prompt_pack"`.
2. Call `validate_demo_pack(spec)`: `{valid, errors, warnings, stats}`.
3. Call `render_demo_guide(spec)`: `{html, filename, readme_md, stats, warnings}`.
   Invalid specs return `{errors, stats, warnings}` without output assets.

All three tools return top-level structured content and equivalent JSON text.
`readme_md` is content for `00_DEMO_README.md`; the HTML filename is
`<prefix>-demo-guide.html`, or a title slug when no prefix is present.
The server saves nothing, fetches no public sources, and creates/sends no files,
email, chats or calendar items. Inputs must be built fully before the prompt
pack, never in parallel; the future skill owns those operations.

The strict contract reuses LabSpec's typed `KeyFact`, safe relative/HTTPS hrefs,
voice lint, numeric-evidence heuristic, sensitive-domain predicates and escaped
templates. Structural errors cover all ID references, duplicate IDs, unsafe URLs,
conditional prefixes/source prompts, function-pack filename prefixes, scenario
counts and the four required output formats. `scenario_count` is optional;
function packs default to four. Prefixes are required for function packs or a
named audience, otherwise optional. A prompt pack retains `source_prompt`
verbatim. Missing fact URLs/evidence are permitted so quality warnings can explain
the gap; supplied URLs and references must be valid.

Warnings cover talk tracks outside 150-300 words, missing/unburied payoffs,
unused/evidence-free files, cast/tension quality and dates, ungrounded or repeated
context, customer names in invented records, repeated functions/prompts, seeded
item limits/labels, learner voice, sensitive domains, numeric evidence, duration
totals and disclaimers. Each includes a field path and one-line fix; warnings do
not block rendering. Customer matching normalizes punctuation/case and checks
close spellings, not acronyms, affiliations or semantic identity. These checks
are authoring heuristics, not data-loss prevention or verification of file contents.

All people and seeded data must be fictional, including the operating company.
Only public customer names in audience/title/talk tracks and the filename prefix
are permitted; a customer name plus "(demo data)" is not a fictional stand-in.
LabSpec's fictional-only rules are unchanged. Public context facts and assumptions
are shown separately. Seeded messages require a fictional sender label and are
plans for the presenter's own mailbox/calendar only, never cross-user chat relay.

The offline guide reuses lab styles/copy controls and keeps planted payoffs
collapsed even under Expand all. **Printing includes presenter notes**; hidden
content is not access control. Only attendee file hrefs become links; presenter
files never link. Source files are not bundled or fetched.
The [function fixture](tests/fixtures/demo_pack_function.json) and
[prompt fixture](tests/fixtures/demo_pack_prompt.json) both validate at 0/0.
Approaches are credited in [CREDITS.md](CREDITS.md) and every returned README.

## Spec-first lab pipeline

1. Call `get_lab_spec_schema` and draft a LabSpec with `schema_version: "2.1"` using fictional content only; `"2.0"` remains supported.
2. Call `validate_lab_spec`. Fix errors; review nonblocking quality warnings.
3. Call `render_lab_page`. Cowork saves the returned `html` using `filename`.

The shipped skill requires zero errors **and** zero warnings before rendering,
even though warnings remain nonblocking at the server API.

Validation returns `{valid, errors, warnings, stats}`. Issues have `code`, `path`,
and `message`. Schema failures return zero stats. Otherwise stats contain
`chapter_count`, `step_count`, `prompt_count`, `challenge_count`,
`checkpoint_count` (declared checkpoint files), `files_by_kind`, and
`total_minutes` (sum of chapter budgets, not step budgets).

The v2 contract describes a narrative, optional through-line artifact, file
metadata, setup, 2-10 chapters with 1-6 steps each, troubleshooting, glossary,
and disclaimer. Steps have 0-4 mode-labeled prompts and/or a challenge, expected
results with key facts, fallbacks, carry-forward instructions, callouts, and
self-checks. `uses`, `fallback`, and `carries_forward` are plain text.

Errors include malformed structure, blank prompts, globally duplicate file/
chapter/step IDs, duplicate filenames (case-insensitive), invalid chapter
references, same/later `builds_on` references, and invalid checkpoint references.
A step needs a prompt or a challenge; a challenge needs a nonblank answer.
Unknown fields and type coercion are rejected. Reserved IDs are `overview`,
`setup`, `capstone`, `agenda`, `files`, `story-map`, `troubleshooting`, `glossary`,
and `disclaimer`; generated controls use a double-hyphen namespace outside
the accepted slug grammar.

Warnings flag isolated chapters, missing carry-forward steps when a through-line
is declared, chapters with fewer than two steps, numerical prompts without
expected key facts, missing checkpoints from chapter three onward in sessions
of at least 90 minutes, unused checkpoint/answer-key files, and chapter budgets
more than 25% away from session duration. Short prompts, missing risk callouts,
and the real-brand denylist remain quality warnings. Numeric evidence rules
look for digits with units/currency, percentages, or calculation words
(`calculate`, `divide`, `multiply`, `sum`, `total`, `cost`, `rate`) alongside
numbers or named quantities. Explicit arithmetic such as "divide on-hand units
by weekly sales" counts even without a written number. Number words or output
counts alone ("two questions", "one sentence", "3 questions") do not count.
Checks cover prompts and step instructions. Challenge tasks have their own
required answer; forecast/variance/contract risk callouts remain separate. These heuristics do
not detect or anonymize customer data.

The nonblocking `learner_voice` warning flags system wording using the single
`_LEARNER_VOICE_TERMS` constant in [validation.py](server/studio/tools/validation.py):
`MCP server`, `consume ` (with a trailing space), `tenant path`, `do not claim`,
`if supplied`, `JSON`, and `schema`. Matching is literal and case-insensitive,
with one warning per field/term; each warning reports the field path and term,
not the full input text.
Checks cover narrative and through-line text, setup instructions and mode
descriptions, chapter titles/story fields, step titles/goals/uses/intros,
prompt labels/text, challenges, expected results, fallbacks, carry-forward
notes, self-checks, and callout text. File filenames and purposes are checked
once at their source paths, including when reused in checkpoint callouts;
chapter titles also appear in the Files table. IDs, URL targets, troubleshooting
and glossary entries are not scanned. Put technical facilitator guidance in
troubleshooting rather than learner prompts.

### LabSpec 2.1 consistency warnings

`chapters[].steps[].expected.key_facts` accepts the existing strings or typed
objects: `{kind, text, source_file?, section?}`. `kind` must be `number`, `quote`,
`clause`, or `fact`; unknown kinds are schema errors. A quote/clause should name
an exact `files[].id` or `files[].filename` in `source_file`; a clause should
have a section number such as `2.1` (or `Section 2.1`). Missing, blank or unknown
sources and missing/non-numeric clause sections **warn**, never block rendering.
Only `text` appears in the expected-facts list.

The deterministic checks return field paths and one-line fixes:

- **Headings/containers:** optional `through_line.headings` checks quoted
  destinations and explicitly named quoted/capitalized headings in
  `carries_forward` (also rendered as "Lands in"). Without headings, heading-list
  matching is skipped. Named containers such as "your timeline" still warn if
  absent from the declared running document, headings or files.
- **Files:** common document filenames and concrete "the X log/report/file"
  phrases in `uses`, setup and challenges must identify declared files or the
  running document. Generic "the source file" is not treated as a missing named
  file. A new workbook already named in `through_line.location` need not also
  be a provided file. This is a conservative prose check, not a dependency graph.
- **Quotes:** quoted overview/company/narrative/through-line wording that shares
  a case-sensitive contiguous run of **25+ characters** with a typed quote/clause
  but differs from it warns "quote differs from the key fact". Exact matches
  are accepted; unquoted paraphrases and semantic similarity are not inferred.
- **Clauses:** missing section numbers warn at the key fact; learner references
  such as "Section 9.2" warn when no clause fact declares that number.
- **Sensitive domains:** legal, HR/human resources, compliance, privacy and
  medical in `functional_area` or `audience` require wording "not professional
  advice" in ground rules/disclaimer, a step connecting interpretations or
  uncertainty to questions for an expert, and fictional-party wording. These
  are text-marker checks, not professional or safety judgments.

All consistency findings are warnings; structural types and unsafe URLs remain
errors. The wholly invented [legal fixture](tests/fixtures/legal_notice_lab.json)
demonstrates 2.1 with zero errors/warnings. The original 2.0 golden fixture still
validates without warnings and renders the same 84,022 bytes.

### Files are metadata, not generated assets

Each file has a globally unique ID, a relative `filename`, kind, purpose, and
`used_in` chapter IDs. Usage is declared through `used_in` or a chapter's
`checkpoint_file_id`; it is not inferred from prose. Omitted checkpoint IDs are
allowed; supplied IDs must reference a file of kind `checkpoint`.

In 2.1 an optional `href` accepts HTTPS or relative paths; 2.0 retains HTTP(S),
mailto and relative paths. In both versions,
executable schemes, embedded credentials, controls, and protocol-relative
network paths are rejected. If supplied, it becomes a download link (browser
download behavior depends on URL/origin) with `target="_blank"` and
`rel="noopener noreferrer"`. Without it, the filename is plain text
labeled **Provided separately**. No link is fabricated from `filename`.
`audience` defaults to `learner`. Files marked `facilitator` appear under
**Answer keys**, marked **Facilitator only**, and are never linked, including in
checkpoint callouts. This presentation rule is not access control on the URL.
Files and checkpoint states are produced later by the learner or Cowork skills,
not by this server. Links are inert until clicked; no remote assets are embedded.

### Facilitator pack workflow (plugin 0.1.3)

After clean validation, Cowork builds the practice files from the typed key facts,
with learner permission. It saves sources, fresh test inputs and chapter-start
checkpoints under `<lab-slug>/learner/`, and answer keys plus
`facilitator-notes.md` under `<lab-slug>/facilitator/`. The notes contain a
chapter run of show, handouts, dates and expected answers.

Only saved learner files receive relative `learner/<filename>` hrefs; keys and
notes use `audience: "facilitator"` and no href. The skill validates again,
re-renders and saves the **exact** returned HTML at `<lab-slug>/<lab-slug>.html`,
aligning the folder to the returned filename. Cowork re-reads every file, checks
verbatim quote/clause placements and section numbers, verifies dates and numeric
calculations with code, checks relative links and reports counts and corrections.
Mismatched practice files are fixed to match the canonical facts, not vice versa.

The skill offers a ZIP of the complete pack for facilitators; learners receive
the HTML and learner subtree together, not the facilitator answers. There is no
server-side file/ZIP, mail or calendar creation. Folder labels and absent links
are not access control. Actual saving, code execution and ZIP creation depend on
Cowork's available tools; unavailable operations must be reported as unverified.

Rendering success returns `{html, filename, stats, warnings}`. Failure returns
`{errors, stats, warnings}` with **no HTML or filename**. Only the `microsoft`
theme is bundled; an optional `theme_id` overrides the spec theme, and unknown
themes fail explicitly. All spec text is escaped, including prompts and link
labels. Filenames are ASCII title slugs, falling back to `training-lab.html`
when the title has no ASCII letters or digits.

The page has a leave-with hero, computed agenda, grouped files table, chapter
story headers, rejoin checkpoints, collapsible steps, mode badges, copy buttons,
expected key facts, hidden challenge answers, fallback tips, and a story-map
table. Expand all opens chapters/steps without revealing challenge answers.
Printing includes answers and restores the original open/closed state afterward.
Active navigation, mobile layout, and all seven callout styles remain offline.
Clipboard failures select the prompt and show manual copy guidance.
Self-check selections are transient; no browser storage is used.

### Golden sample

Open [the rendered Zava story lab](examples/zava-story-lab.html) in a browser.
It is generated from [the fictional fixture](tests/fixtures/zava_story_lab.json):
Zava Outdoor's Summit Packs QBR, five chapters, ten steps, twenty prompts, one
prompt-free challenge, and 90 minutes. Every step after chapter one explicitly
uses an earlier output. The QBR Story sheet carries evidence into PowerPoint,
then into a saved prompt, the personal Cowork skill `summit-qbr-review`, and a
prior-quarter replay. M3b shortens the prompts into learner voice while retaining
the original fictional data, named inputs, checkpoints and numerical checks.

All ten file entries omit `href`: workbook/checkpoint/answer-key assets are
**not bundled**. The first prompt contains the complete fictional source TSV
for manual setup; a facilitator or Cowork skill must provide checkpoint states.
In the final chapter, learners review the skill draft, approve saving it in
Cowork, invoke it by name on FY28-Q1, and compare the results with the key facts.
If personal skill creation is unavailable, they save and reuse the prompt
manually instead. This is a learner activity, not a skill installed by the server.

The golden-page regression test enforces **400 KB = 400,000 UTF-8 bytes** and
prints the measured size even under `pytest -q`. It also records the size in
pytest's test properties. No size optimization is applied in M3a.

Regenerate the checked-in sample from the repository root (a developer action,
not a server capability):

```sh
PYTHONPATH=server python - <<'PY'
import json
from pathlib import Path
from studio.tools.rendering import render_lab_page

spec = json.loads(Path("tests/fixtures/zava_story_lab.json").read_text())
result = render_lab_page(spec)
assert "html" in result, result
Path("examples/zava-story-lab.html").write_text(result["html"], encoding="utf-8")
PY
```

## Validate

From the repository root, with the environment activated:

```sh
pytest -q
python -c "import json;json.load(open('server/studio/data/session_formats.json'))"
docker build -t training-studio-mcp ./server
```

With the HTTP server running in another terminal:

```sh
python scripts/smoke_client.py
```

This lists and calls all eight local tools, checks blueprint summaries/details,
validates/renders the golden lab and both demo fixtures, and verifies invalid
lab input returns no HTML. It never saves the response. This checkout's smoke
client and catalog builder expect eight tools; the five-tool M4b Azure deployment
will not satisfy them until M5b. Do not rebuild plugin 0.1.3 from this checkout.

Docker must be installed with a running engine for the build. To run the image:

```sh
docker run --rm -p 127.0.0.1:8000:8000 training-studio-mcp
```

The container uses a non-root user and defaults to streamable HTTP on port 8000.

## Design and roadmap

- [Project context and milestones](PROJECT_CONTEXT.md)
- [Architecture and data boundaries](docs/architecture.md)
- [Azure deployment placeholder](infra/README.md)
- [Reference implementation](https://github.com/emontes07/inventory-mcp-copilot)
