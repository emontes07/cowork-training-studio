# Cowork Training Studio

A stateless MCP server for Microsoft 365 Copilot Cowork training workflows.
**Skills own judgment, MCP owns consistency.** Skills write content; Cowork's
own tools save and send it.

M3a implements a LabSpec **2.0** story pipeline alongside the M1 format catalog:
`get_lab_spec_schema` -> `validate_lab_spec` -> `render_lab_page`.
The result is one self-contained HTML page, returned to Cowork rather than
saved by the server. Azure deployment and Cowork plugin packaging remain future
milestones. Version 2 replaces M2's scenario/lab contract; v1 specs are rejected.

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
`default_duration_minutes`, and `produced_by_skill`.
The skill mappings are `html-training-lab`, `training-guide`, and
`cowork-demo-pack`; `prompt_a_thon` has `null` because no dedicated skill is
assigned. These skills are not included in M1.

The underlying Python functions stay directly callable. FastMCP may wrap a
list in the MCP structured-content `result` field on the wire. The renderer's
`html`, `filename`, `stats`, and `warnings` are top-level structured content,
as are the validator's `valid`, `errors`, `warnings`, and `stats`. Invalid
renders return top-level `errors`, `stats`, and `warnings` without HTML or a
filename. Both tools also include the same object as JSON in a text block for
clients without structured-content support. The smoke client reads structured
content directly rather than SDK-generated Python model objects.

## Spec-first lab pipeline

1. Call `get_lab_spec_schema` and draft a LabSpec with `schema_version: "2.0"` using fictional content only.
2. Call `validate_lab_spec`. Fix errors; review nonblocking quality warnings.
3. Call `render_lab_page`. Cowork saves the returned `html` using `filename`.

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
and the real-brand denylist remain quality warnings. Numeric rules also detect
digits. These heuristics do not detect or anonymize customer data.

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

### Files are metadata, not generated assets

Each file has a globally unique ID, a relative `filename`, kind, purpose, and
`used_in` chapter IDs. Usage is declared through `used_in` or a chapter's
`checkpoint_file_id`; it is not inferred from prose. Omitted checkpoint IDs are
allowed; supplied IDs must reference a file of kind `checkpoint`.

An optional `href` accepts `https`, `http`, `mailto`, and relative paths;
executable schemes, embedded credentials, controls, and protocol-relative
network paths are rejected. If supplied, it becomes a download link (browser
download behavior depends on URL/origin). Without it, the filename is plain text
labeled **Provided separately**. No link is fabricated from `filename`.
Files and checkpoint states are produced later by the learner or Cowork skills,
not by this server. Links are inert until clicked; no remote assets are embedded.

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

This lists and calls all four tools, retrieves the v2 schema, validates/renders the golden
spec, and verifies invalid input returns no HTML. It never saves the response.

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
