# Architecture

```text
+-----------------------------------------------------------+
| Cowork plugin skills (planned packaging)                   |
| Write content, choose the scenario, own editorial judgment |
+-----------------------------+-----------------------------+
                              |
                 +------------+------------------+
                 |                               |
                 v                               v
+--------------------------------+  +-----------------------------+
| Training Studio MCP            |  | Microsoft Learn MCP         |
| M1: session format metadata    |  | Planned second connection   |
| M2+: schemas, validation, HTML |  | Official documentation      |
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

M2 is spec-first: a skill writes LabSpec JSON, calls the validator, fixes reported
issues, and then calls the HTML renderer. Neither validation nor rendering
exists in M1; only the format catalog is implemented.

## Tool surface

| Tool | Status | Input | Output / when to call |
| --- | --- | --- | --- |
| `list_session_formats` | M1, implemented | Optional exact `id` | JSON list of four formats, or one matching format; call before selecting a skill or gathering inputs. Unknown IDs raise an explicit error. |
| LabSpec validation (name TBD) | M2, planned | Fictional LabSpec JSON | Structured validation results before rendering. |
| `render_lab_page` | M2, planned | Valid fictional LabSpec JSON | Self-contained HTML returned to Cowork, never saved by this server. |

Each format includes `id`, `name`, `description`, `best_for`, `required_inputs`
(each with `name`, `description`, and `example`), `default_duration_minutes`, and
`produced_by_skill`. Skill names are routing metadata, not installed skills.
`prompt_a_thon` has no assigned skill yet (`null`).

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

## Data handling

- The application has no durable or per-user storage, secrets, authentication,
  telemetry integration, analytics, or outbound service calls.
- The only retained application content is the immutable bundled format catalog.
  Returned copies are not retained. Ephemeral in-process framework bookkeeping
  is allowed; no request data survives a restart and no runtime disk, database,
  or external storage backend is used.
- Do not submit tenant documents, real customer/person names, emails, calendars,
  credentials, or other sensitive material. M1 accepts only a format ID, not
  customer content; it is not a data-loss-prevention or anonymization service.
- All examples and future demo material must be fictional and use Zava-style
  brands and role labels, never real people or customers.
- Framework diagnostic/access logs may contain connection metadata or errors.
  This server does not implement content logging or telemetry collection.
- No Graph calls, mailbox seeding, calendar writes, or file saves occur here.
  Future demo-pack email/calendar content is returned for Cowork to handle.
- M1 has no authentication. Bindings on `0.0.0.0` are reachable on available
  interfaces; use local/trusted networks only and do not expose this development
  server to the public internet.
