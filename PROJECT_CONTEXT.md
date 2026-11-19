# Cowork Training Studio

## Purpose

A remote-capable MCP server that helps Microsoft 365 Copilot Cowork users build
customer training content: HTML lab pages, Word guides, and demo packs. Customer
training describes the audience, not permission to ingest customer data.

**Skills own judgment, MCP owns consistency.**

Cowork skills write and refine content. The MCP server returns reusable
templates, schemas, validation results, and rendered HTML as capabilities are
added. Cowork's own tools save files and send messages; this server never does.

## Current checkpoint: M5b

The M1 tool is `list_session_formats`, backed by a bundled JSON catalog:
`html_lab`, `word_guide`, `demo_pack`, and `prompt_a_thon`.
It returns a JSON list, optionally filtered by an exact ID, and raises an error
for an unknown ID. `html_lab` and `demo_pack` are available through the shipped
`build-training-lab` and `build-demo-pack` skills; the other two formats are planned.
M2 added `get_lab_spec_schema`, `validate_lab_spec`, and `render_lab_page`.
M3a replaces the v1 scenario/lab model with **LabSpec 2.0**: one narrative,
an optional through-line artifact, linked chapters and steps, checkpoints,
mode-labeled prompts, hidden challenges, and reference sections. Version 1
is intentionally unsupported. Pydantic v2 provides strict contracts; validation
is deterministic and Jinja templates autoescape all spec text.
Rendering returns a single offline-capable HTML page, never a saved file.
M3b adds warning-only learner-voice lint, correct summary plurals, and a shorter,
learner-facing golden sample ending in a personal Cowork skill creation/reuse
activity. Skill creation stays in Cowork, with a saved-prompt fallback.
M3c-M3f added Cowork packaging, Azure hosting, flat structured tool results and
safe request metadata logging. M4a adds **LabSpec 2.1**, retaining 2.0 compatibility
and the exact 84,022-byte golden page. M4b adds the read-only `get_blueprint` tool,
deploys 2.1 to Azure and releases plugin **0.1.3** with the same manifest ID.
The 137-line skill now fixes every warning, builds checked learner/facilitator
packs with Cowork's own tools, and offers a ZIP after saving the exact HTML.
Local tests: 254 before M4b, 268 after. Both fixtures validate with zero issues.

M5a adds **DemoPackSpec 1.0**, `get_demo_pack_schema`, `validate_demo_pack` and
`render_demo_guide`: eight tools, with deployment deferred until M5b.
Tests: 268 before, 355 after; both lab and both demo fixtures are 0/0, and the
lab golden remains byte-identical. Demo results are top-level objects with
matching JSON text; rendering returns HTML and `readme_md`, never saved assets.
`demo_pack` remained `coming_soon`; M5a did not deploy or change plugin 0.1.3.
The customer-context disclaimer sentence is required only for a named audience;
the fictional-people/data sentence remains mandatory for every pack.
See [credits](CREDITS.md) for the approved source-approach attribution.

M5b makes `demo_pack` available via the 126-line `build-demo-pack` skill and
releases plugin **0.1.4** with the same manifest ID and eight sanitized tools.
The lab skill is 141 lines; both require real Office inputs where appropriate,
exact connector tool names, checked files and a ZIP offer. Demo seeding is
optional, confirmed, presenter-owned only, with no chats or other recipients.
Azure revision **`cowork-training-studio-mcp--0000005`** serves 100% of traffic;
identity/registry/environment/ingress are unchanged, with 0.25 CPU, 0.5Gi,
min 1/max 2 and zero secrets. Tests: **355 -> 359**; all four fixtures are 0/0
and the golden remains 84,022 identical bytes. Live smoke and package checks pass;
actual Cowork Office-file creation, ZIP and seeding remain to be tested in Cowork.

`get_blueprint()` returns `{blueprints: [...]}` summaries; an exact
`blueprint_id` returns detail fields directly, never under `result`. Unknown IDs
fail explicitly. Shapes are `app_deep_dive` (60 minutes),
`prompt_to_agent_ladder` (90), and `domain_super_day` (300 including breaks).
The super-day's `chapter_outline` is its agenda; lab slots reference matching
`lab_outlines` IDs, titles and durations. Build all five labs separately as
`html_lab`; the closing challenge moves to `prompt_a_thon` only when it ships.
Blueprints are generic metadata, not ready-to-render specs or created assets.

The reference implementation is
[inventory-mcp-copilot](https://github.com/emontes07/inventory-mcp-copilot).
Its `server/requirements.txt` specifies `fastmcp>=2.0.0`, without an exact pin.
This scaffold uses Python 3.13 locally and in its container. Authentication is
explicitly disabled rather than inherited from FastMCP environment settings.

## Runtime decision

Runtime decision: FastMCP 2.14.7, tasks disabled, memory backend; revisit when a
worker-free FastMCP release supports the fixed MCP SDK.

Both `fastmcp==2.14.7` and `mcp==1.30.0` are pinned. The SDK includes the
stateless-transport stream-cleanup fix absent from the SDK allowed by FastMCP
2.13.3. FastMCP 2.14.7 still starts an internal worker, but background tasks
are explicitly forbidden and its backend is forced to `memory://` in code.
Normal tool calls are not queued or stored as task results.

"Stateless/no-storage" means no customer or tenant data persisted, no runtime
disk/database/external storage, and no request data surviving a restart.
Ephemeral in-process memory, including framework bookkeeping, is acceptable.
Streamable HTTP uses stateless mode with no persistent MCP session ID, so
requests can reach different Azure Container Apps replicas without sticky
sessions. The bundled catalog is static application content, not runtime storage.

## Spec-first design

The spec-first workflow is:

1. A model, guided by a skill, writes **LabSpec JSON** using fictional data.
2. The server validates the spec and returns actionable validation results.
3. The skill corrects the spec until it has zero errors and warnings.
4. Cowork uses its built-in tools to create practice files from the key facts,
   under `<lab-slug>/learner/` and `<lab-slug>/facilitator/` (keys and notes).
5. The skill sets relative learner hrefs and facilitator audiences and validates
   again to zero issues. The server renders deterministic, self-contained HTML.
6. Cowork saves `<lab-slug>/<lab-slug>.html` unchanged, re-reads the files and
   checks quotes, dates and numbers with tools.
   The guide and learner subtree travel together; the full pack stays with
   facilitators. Directory labels are not access control.

The server is not an autonomous author and does not make editorial or business
judgments. Validation and rendering must remain separate, testable operations.

### LabSpec contract decisions

- `schema_version` is required and accepts `"2.0"` or `"2.1"`. Unknown fields and type
  coercion are rejected; there is no v1 compatibility layer.
- File, chapter, and step IDs are globally unique slugs. Reserved IDs include
  M2's `overview`, `setup`, `capstone` plus `agenda`, `files`, `story-map`,
  `troubleshooting`, `glossary`, and `disclaimer`. Generated control IDs use a
  double-hyphen namespace that spec slugs cannot use.
- `builds_on` may name only earlier chapters. An empty list after chapter one
  is a nonblocking isolated-chapter warning, not a schema error.
- Omitted `checkpoint_file_id` is allowed. A supplied reference must exist and
  have kind `checkpoint`; long sessions warn when later chapters lack one.
- File usage counts use `used_in` or `checkpoint_file_id`. Filenames are relative
  paths, unique case-insensitively; missing prose references warn.
- Optional file `href` allows HTTPS or relative paths in 2.1; 2.0 retains HTTP(S),
  mailto and relative paths. No executable schemes, credentials, controls or
  network paths. Learner links open with `noopener noreferrer`; absent hrefs
  keep "Provided separately". `audience` defaults to `learner`; `facilitator`
  files appear under Answer keys, marked "Facilitator only", never linked.
- `expected.key_facts` accepts existing strings or `{kind, text, source_file?,
  section?}` objects; kinds are `number`, `quote`, `clause`, `fact`. Missing or
  unknown quote/clause sources and missing clause section numbers are warnings,
  not schema errors. Sources match an exact file ID or filename; unknown kinds
  remain schema errors. Only the fact's `text` is rendered.
- Optional `through_line.headings` enables carry-forward heading checks.
  Warning-only heuristics also check undeclared containers/files, overview quote
  drift (a shared contiguous run of at least 25 characters), undeclared section
  references, and sensitive-domain safeguards: professional-advice disclaimer,
  questions for an expert, and fictional-party wording. See
  [check scopes](README.md#labspec-21-consistency-warnings); no broad NLP or
  source-file inspection is performed.
- The sample contains metadata only. Real workbooks, checkpoints, answer keys,
  decks, and skill files are authored later by Cowork skills or the learner.
- `uses`, `fallback`, and `carries_forward` are plain text. Steps need a prompt
  or a challenge; challenge-level steps require a challenge with a nonblank
  answer. Expected results may be null; numerical prompts without key facts warn.
- Stats count chapters, steps, prompts, challenges, declared checkpoint files,
  and files by kind. Total minutes sum chapter budgets. Schema failures return
  zero stats; cross-field errors retain computed stats.
- Unknown themes fail explicitly; only `microsoft` is bundled. All content stays
  plain text, HTML-escaped. The renderer never executes or includes spec HTML.
- The original golden story is a 90-minute Zava Outdoor / Summit Packs QBR:
  five chapters, ten steps, twenty prompts, one challenge, and three checkpoint
  entries. Every later step consumes an earlier output. The final chapter saves
  a prompt, asks Cowork to create the personal `summit-qbr-review` skill, approves
  saving it after review, and invokes it on a prior quarter. If skill creation
  is unavailable, the learner reuses the saved prompt manually.
- The rendered sample is developer-generated, never saved by the MCP server.
  The HTML budget is 400,000 UTF-8 bytes; the regression test prints the actual
  measurement. M3a deliberately does not optimize the page size.
- The small real-brand denylist is a quality heuristic, not data-loss prevention.
  `is_fictional` is an author declaration, not proof that data is fictional.

## Non-negotiable boundaries

- Stateless: no runtime disk/database/external storage, durable user/session
  records, generated file storage, or persisted request content. Ephemeral
  in-process memory is allowed; nothing from requests survives a restart.
  The packaged format catalog is read-only application data, not customer storage.
- No tenant data: never submit real documents, mail, calendar content, person
  names, credentials, or secrets. LabSpecs remain wholly fictional.
  DemoPackSpec alone permits public customer names in audience/title/talk tracks
  and the filename prefix, never seeded records; its company must be a fictional
  stand-in. Public context is author-supplied metadata, not fetched by the server.
- Fictional data only: use invented Zava-style brands and generic role labels.
  Do not disguise real customer or personal data as a fictional scenario.
- No Microsoft Graph calls, outbound business-service calls, secrets, telemetry,
  or application authentication.
- No saving, sending, mailbox/calendar mutation, or tenant access. Cowork owns
  those actions and their permission boundary.
- Keep tool functions pure and importable; register them separately in the
  FastMCP entrypoint. Load static data once, and do not expose mutable shared data.
- M1 is for local/trusted testing. Public deployment needs an explicit platform
  access/exposure decision; no production security is implied by this scaffold.

## Roadmap

| Milestone | Scope |
| --- | --- |
| M1 | Scaffold, format catalog, `list_session_formats`, tests, container, and documentation. |
| M2 | Implemented: LabSpec schema, validation, `render_lab_page`, and fictional golden sample. |
| M3a | Implemented: LabSpec 2.0 story model, narrative renderer, and original connected QBR sample. |
| M3b | Implemented: learner-voice sample, personal Cowork skill activity, voice lint, and summary plurals. |
| M3c-M3f | Implemented: Cowork connector/package, Azure hosting, and first-run polish. |
| M3 remaining | Themes and a prompt library; blueprints shipped in M4b. |
| M4a | Implemented: additive LabSpec 2.1, typed facts, consistency warnings, and file links. |
| M4b | Implemented: five-tool server, tested blueprint agendas, facilitator-pack skill, plugin 0.1.3 and Azure redeployment. |
| M4 remaining | ThreadScript schema. |
| M5a | Implemented locally: DemoPackSpec 1.0, structural/quality validator, presenter HTML/README, fictional fixtures and eight-tool catalog. No deployment/release. |
| M5b | Implemented: demo-pack skill/availability, Office-file lab guidance, Azure revision 0000005 and plugin 0.1.4. |
| Future | [Microsoft Learn MCP](https://learn.microsoft.com/api/mcp) as a second, independent connection. |

## Layout

- [server/](server/): FastMCP entrypoint, pure tools, and packaged static data.
- [tests/](tests/): direct tool-function tests, without a running server.
- [infra/](infra/): Azure deployment and redeployment guidance.
- [docs/architecture.md](docs/architecture.md): boundaries and planned flow.
- [docs/prompts/](docs/prompts/): reserved for future development prompts.
- [examples/zava-story-lab.html](examples/zava-story-lab.html): generated offline story guide.
- [scripts/smoke_client.py](scripts/smoke_client.py): live HTTP pipeline verification.

See [README.md](README.md) for running, inspection, and validation commands.
