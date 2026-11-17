# Cowork Training Studio

A stateless MCP server for Microsoft 365 Copilot Cowork training workflows.
**Skills own judgment, MCP owns consistency.** Skills write content; Cowork's
own tools save and send it.

M2 implements a spec-first lab pipeline alongside the M1 format catalog:
`get_lab_spec_schema` -> `validate_lab_spec` -> `render_lab_page`.
The result is one self-contained HTML page, returned to Cowork rather than
saved by the server. Azure deployment and Cowork plugin packaging remain future
milestones.

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
`list_session_formats` with `{}` or `{"id":"html_lab"}`. M2 adds
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
success/failure union is also wrapped in `result` on the wire; the smoke client
uses `structured_content` rather than SDK-generated Python model objects.

## Spec-first lab pipeline

1. Call `get_lab_spec_schema` and draft a LabSpec using fictional content only.
2. Call `validate_lab_spec`. Fix errors; review nonblocking quality warnings.
3. Call `render_lab_page`. Cowork saves the returned `html` using `filename`.

Validation returns `{valid, errors, warnings, stats}`. Issues have `code`, `path`,
and `message`. Schema failures return zero stats; otherwise stats count
scenarios, labs, prompts (including the capstone), and total lab minutes.
Errors include malformed structure, blank prompts, unsafe resource URLs, and
IDs duplicated across scenarios/labs. IDs `overview`, `setup`, and `capstone`
are reserved for navigation. Unknown fields and type coercion are rejected.

The scenario `story` object is required; each of its five strings may be
omitted or blank. Every missing/blank field produces its own warning naming the
scenario and field, and is omitted from the rendered story. Other warnings flag
short prompts (under 60 characters), missing risk callouts, a fictional company
matching the small real-brand denylist, and lab duration more than 25% away from
session duration. These heuristics do not detect or anonymize customer data.

Resource URLs accept `https`, `http`, `mailto`, and relative paths; executable
schemes, embedded credentials, controls, and protocol-relative network paths
are rejected. Links are inert until clicked; no remote assets are embedded.

Rendering success returns `{html, filename, stats, warnings}`. Failure returns
`{errors, stats, warnings}` with **no HTML or filename**. Only the `microsoft`
theme is bundled; an optional `theme_id` overrides the spec theme, and unknown
themes fail explicitly. All spec text is escaped, including prompts and link
labels. Filenames are ASCII title slugs, falling back to `training-lab.html`
when the title has no ASCII letters or digits.

The page has native collapsible scenarios/labs, active section navigation,
copy buttons, all seven callout types, expand/collapse controls, mobile
navigation, and print styling. It requires no CDN, font downloads, or network
requests. Clipboard failures select the prompt and show manual copy guidance.
Self-check selections are transient; no browser storage is used.

### Golden sample

Open [the rendered Zava finance lab](examples/zava-finance-lab.html) in a browser.
It is generated from [the fictional fixture](tests/fixtures/zava_finance_lab.json):
two scenarios, six labs, seven prompts, and 60 minutes. The capstone is completed
within the final lab. Its original prompts contain all fictional source rows;
no external workbook download is required.

Regenerate the checked-in sample from the repository root (a developer action,
not a server capability):

```sh
PYTHONPATH=server python - <<'PY'
import json
from pathlib import Path
from studio.tools.rendering import render_lab_page

spec = json.loads(Path("tests/fixtures/zava_finance_lab.json").read_text())
result = render_lab_page(spec)
assert "html" in result, result
Path("examples/zava-finance-lab.html").write_text(result["html"], encoding="utf-8")
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

This lists the four tools, retrieves the schema, validates/renders the golden
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
