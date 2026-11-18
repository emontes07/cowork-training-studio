# Architecture

```text
+-----------------------------------------------------------+
| Cowork plugin: build-training-lab                          |
| Write content, choose the scenario, own editorial judgment |
+-----------------------------+-----------------------------+
                              |
                 +------------+------------------+
                 |                               |
                 v                               v
+--------------------------------+  +-----------------------------+
| Training Studio MCP            |  | Microsoft Learn MCP         |
| M1: session format metadata    |  | Planned second connection   |
| M3a: story contract and HTML   |  | Official documentation      |
| No tenant data or persistence  |  | learn.microsoft.com/api/mcp |
+--------------------------------+  +-----------------------------+

+--------------------------------+
| Cowork built-in tools          |
| Save/send with user permission |
+----------------+---------------+
                 |
                 v
       OneDrive / Outlook / Teams

No connection from Training Studio MCP to Microsoft Graph or tenant services.
```

## Responsibilities

**Skills own judgment, MCP owns consistency.** Skills draft training content;
the server supplies deterministic building blocks. Cowork's own tools handle
file creation, saving, sharing, and sending with the user's permissions. The
server does not call either Microsoft Graph or Microsoft Learn MCP. The future
plugin connects independently to both MCP servers.

The pipeline is spec-first: a skill writes LabSpec 2.1 (or 2.0) JSON, calls the validator, fixes reported
errors, reviews warnings, and then calls the HTML renderer. All three tools are
implemented alongside the M1 format catalog.

## Tool surface

| Tool | Status | Input | Output / when to call |
| --- | --- | --- | --- |
| `list_session_formats` | M1, implemented | Optional exact `id` | JSON list of four formats, or one matching format; call before selecting a skill or gathering inputs. Unknown IDs raise an explicit error. |
| `get_lab_spec_schema` | M4a, v2.1 | None | JSON Schema for drafting fictional LabSpec 2.0/2.1; v1 is rejected. |
| `validate_lab_spec` | M3a, v2 | `spec` object | `{valid, errors, warnings, stats}`; call before rendering. |
| `render_lab_page` | M3a, v2 | `spec`, optional `theme_id` | `{html, filename, stats, warnings}` on success; `{errors, stats, warnings}` with no HTML on failure. |

Each format includes `id`, `name`, `description`, `best_for`, `required_inputs`
(each with `name`, `description`, and `example`), `default_duration_minutes`,
`status`, and `produced_by_skill`. Only `html_lab` is `available`, routed to the
shipped `build-training-lab` skill. Word guides, demo packs and prompt-a-thons
are planned, `coming_soon`, with no assigned skill (`null`).

## Lab pipeline

[The Pydantic contract](../server/studio/schemas/lab_spec.py) checks strict types,
required version/structure, collection bounds, nonblank prompts and challenge
answers, relative filenames, and safe optional file hrefs. Narrative and chapter
story fields are nonblank in v2. The optional through-line identifies the artifact
that chapters extend; this is metadata, not runtime state.

[Validation](../server/studio/tools/validation.py) adds globally unique file/
chapter/step IDs, earlier-chapter dependency checks, declared file usage,
checkpoint kind checks, duplicate filenames, and quality warnings. It does not
infer dependency edges from prose; conservative missing-file references only warn.
Empty `builds_on` after the first
chapter is a warning; unknown/same/later chapter references are errors.
No prompts and no challenge is an error. Challenge-level steps require an
answered challenge, even when they also contain prompts.

Errors and warnings contain `code`, `path`, and `message`, not copies of the input.
Stats contain `chapter_count`, `step_count`, `prompt_count`, `challenge_count`,
`checkpoint_count` (declared checkpoint files), `files_by_kind`, and
`total_minutes` (chapter budgets). Schema errors return zero stats. Duration
warnings use a strict greater-than-25% threshold. Other warnings cover thin or
isolated chapters, absent carry-forward steps, numerical prompts without expected
key facts, missing late-session checkpoints, unused checkpoint/answer-key entries,
short prompts, risk callouts, the brand denylist, and learner-facing system
vocabulary. The voice lint reports a field path and matched term without
blocking rendering; it includes file names/purposes used in the Files table
and checkpoint callouts. Its scope and literal case-insensitive vocabulary
are documented in [README.md](../README.md#spec-first-lab-pipeline).
Quality rules are authoring
aids, not proof that a spec is safe or contains no tenant data.

M4a accepts string or typed key facts (`number`, `quote`, `clause`, `fact`).
Quote/clause source references and clause section numbers are warning-only
requirements. Optional `through_line.headings` enables destination matching;
other warnings cover undeclared containers/files, overview quote drift with a
25-character contiguous match, unknown section references and sensitive-domain
safeguards. See [check scopes and examples](../README.md#labspec-21-consistency-warnings).
No source assets are read to perform these checks.

[Rendering](../server/studio/tools/rendering.py) validates first, selects a bundled
theme by exact ID, and renders local Jinja templates with autoescape enabled for
every template, including `.html.j2` files. Spec content is never interpreted as
HTML, JS, CSS, or a template path. File href schemes are checked separately
because escaping alone cannot make a `javascript:` link safe.

The output contains inline CSS and vanilla JS only. Computed agenda ranges use
chapter budgets. Tables group files by kind and map steps to inputs, modes, and
carry-forward outputs. Checkpoint callouts reference the declared starting-state
file. If a file has no href, the filename is plain text labeled "Provided
separately"; no broken download is invented and no asset is fetched or created.
2.1 limits hrefs to HTTPS or relative paths; 2.0 keeps its legacy URL policy.
Learner links open in a new tab with `noopener noreferrer`. Optional file
`audience` defaults to learner; facilitator files are grouped under Answer keys,
marked "Facilitator only", and never linked. Existing default/no-href markup
and the 84,022-byte golden page are unchanged.

IDs are stable from the spec; internal IDs use double hyphens, outside the
accepted slug grammar. IntersectionObserver and native details toggles maintain
active navigation. Agenda, file, and story-map links open their target chapters/
steps. Hidden challenge answers do not steal the active nav state. Expand all
opens chapters/steps without revealing answers; print expansion includes answers
and restores the prior state. Copy uses prompt text content, not HTML;
unavailable clipboard APIs produce visible manual-copy guidance. Mobile
navigation and keyboard focus states are included. No browser storage or
telemetry is used.

The public
[finance guide](https://emontes07.github.io/Learning/Instructions/Demos/29-Zava%20Finance.html)
and [close-to-deck guide](https://emontes07.github.io/Learning/Instructions/Demos/31-Zava%20Finance.html)
were structure and tone references only: chapter continuity, a running artifact,
checkpoints, mode labels, challenge answers, reference tables, and learner voice.
Templates, fictional figures, and fixture content are original, not copied from
those guides. The M3a golden example contains no workbook assets; Cowork skills
or a facilitator must create and provide them separately.
M3b's final activity asks learners to review and save a personal Cowork skill,
then invoke it by name; the server does not create, install, or execute that
skill. A saved-prompt fallback covers environments without skill creation.

## Runtime

[The entrypoint](../server/main.py) registers an ordinary, directly importable
[tool function](../server/studio/tools/formats.py). The bundled JSON catalog loads
once per process using a module-relative path. Each call returns a deep copy so
callers cannot mutate future results. Invalid or missing bundled data fails
at import rather than silently returning an empty catalog.

`MCP_TRANSPORT` defaults to `stdio`; `http` and `streamable-http` both select
streamable HTTP at `0.0.0.0:$PORT/mcp`, with `PORT` defaulting to `8000`.
Stateless HTTP mode avoids persistent MCP sessions and sticky-session routing
across Azure Container Apps replicas. FastMCP 2.14.7 and MCP SDK 1.30.0 are pinned
exactly; this SDK includes the stateless-stream cleanup fix. FastMCP still starts
an internal worker, but `tasks=False` and the tool's `task=False` forbid background
tasks. Its backend is forced to `memory://` in code, not left to environment
configuration. Ordinary tool calls are not queued or retained as task results.
`auth=None` prevents inherited framework settings from enabling authentication.
The container runs as a non-root user. STDIO keeps protocol output on stdout;
diagnostics go to stderr. HTTP shutdown allows five seconds for active requests
to finish instead of FastMCP's zero-second grace default.

HTTP request logs are single-line JSON on stderr: UTC `timestamp`, `method`,
`path` (without a query string), `status`, `duration_ms`, and `user_agent`.
Streaming responses are not buffered; duration runs through request completion.
The original requested path is logged before the trailing-slash alias is applied.
Bodies, query strings, tokens, cookies and authorization headers are not logged.
JSON escaping prevents control characters in user-agent/path from creating
extra log lines. The default Uvicorn access log is disabled to avoid duplicate
lines that could include query strings. Unexpected exceptions still propagate;
the metadata log records a 500 if no response status was sent.

## Data handling

- The application has no durable or per-user storage, secrets, authentication,
  telemetry integration, analytics, or outbound service calls.
- Retained application content consists only of bundled catalogs, denylist,
  theme data, and static templates.
  Returned copies are not retained. Ephemeral in-process framework bookkeeping
  is allowed; no request data survives a restart and no runtime disk, database,
  or external storage backend is used.
- Do not submit tenant documents, real customer/person names, emails, calendars,
  credentials, or other sensitive material. The pipeline accepts author-supplied fictional
  specs; neither the schema nor the small brand denylist is a data-loss-prevention
  or anonymization service.
- All examples and future demo material must be fictional and use Zava-style
  brands and role labels, never real people or customers.
- Framework diagnostic/access logs may contain connection metadata or errors.
  This server does not implement content logging or telemetry collection.
- No Graph calls, mailbox seeding, calendar writes, or file saves occur here.
  Future demo-pack email/calendar content is returned for Cowork to handle.
- The server has no authentication. Bindings on `0.0.0.0` are reachable on available
  interfaces; use local/trusted networks only and do not expose this development
  server to the public internet.
