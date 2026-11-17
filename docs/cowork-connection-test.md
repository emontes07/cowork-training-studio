# Temporary Cowork connection test

Use fictional data only. Anonymous access exposes this development server to
anyone with the endpoint. Keep actual tunnel URLs/IDs and credentials out of Git.
Run commands from the repository root.

## Start

```sh
command -v devtunnel
# If missing, install yourself:
brew install --cask devtunnel
devtunnel user login
```

Server terminal:

```sh
MCP_TRANSPORT=streamable-http PORT=8000 .venv/bin/python server/main.py
```

Tunnel terminal (initially owner-only):

```sh
devtunnel host -p 8000 --expiration 8h --host-header unchanged --origin-header unchanged
```

Another terminal, using the ID printed by the host:

```sh
devtunnel access create <tunnel-id> --anonymous --expiration 8h
devtunnel access list <tunnel-id> --json
```

The host's `--expiration 8h` is an **inactivity window**, not a fixed cutoff.
The anonymous access entry has a fixed eight-hour expiry; check its timestamp.
If you started with `--allow-anonymous`, run `devtunnel access reset <tunnel-id>`
before creating the expiring entry so no unlimited anonymous entry remains.
Do not share login output or access tokens.

## Endpoint and remote smoke

Connect Cowork using the Streamable HTTP endpoint:
`https://<tunnel-host>/mcp/`. The preserved headers keep redirects on the public
host instead of `localhost`. No `ALLOWED_HOSTS` change was needed in this test;
server host/origin settings remain unchanged.

```sh
.venv/bin/python -m scripts.smoke_client --url 'https://<tunnel-host>/mcp/'
```

Pass: initialize has no session ID, all four tools are available, the golden
spec has zero errors/warnings, and rendered HTML matches the committed example
byte-for-byte. The client prints render round-trip time and actual downloaded
HTTP-body bytes (MCP/SSE included; headers/TLS excluded), not a JSON-size estimate.

## Cowork checklist

| Test | Prompt/action | Pass condition |
| --- | --- | --- |
| A | "List the session formats you support" | Four formats returned: HTML lab, Word guide, demo pack, prompt-a-thon. |
| B | "Build me a 30-minute, 2-chapter story lab for Copilot in Excel for a fictional bakery chain; validate it, then render it and save the page to my files" | Zero validation errors; Cowork saves the page; the saved HTML opens offline. |
| C | During B, inspect the save step and record how Cowork handles the HTML. | Record whether it writes the tool result directly, retypes/reconstructs the HTML, or the behavior cannot be determined. Do not infer this from MCP smoke success. |

Observed: remote MCP smoke passed; golden HTML matched at 84,022 bytes.
Cowork A/B/C have **not yet been observed**. In particular, direct-write versus
retyping is pending the learner's Cowork run; no content-saving code was added.

## Stop

Press Ctrl+C in the tunnel terminal, then in the server terminal:

```sh
devtunnel delete <tunnel-id>
```

Temporary tunnels normally delete themselves when hosting stops, so "not found"
after Ctrl+C means the tunnel is already gone. If an assistant launched detached
processes, use the specific host/server PIDs from its handoff with `kill <pid>`
instead of Ctrl+C, then delete the tunnel. Never use name-based process killing.
