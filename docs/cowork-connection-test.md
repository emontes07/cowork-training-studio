# Cowork connection test

Use fictional data only. Anonymous access exposes this development server to
anyone with the endpoint. Keep actual tunnel URLs/IDs and credentials out of Git.
Run commands from the repository root.

## Deploy to Azure

This anonymous, fictional-data-only demo is not production ready. Use a
dedicated resource group and a Consumption environment. Azure builds the
existing Dockerfile in ACR; local Docker is not required. Run `az login` yourself
if needed. Confirm the subscription, resource group and environment before
creating resources; never commit account IDs or credentials.

```sh
SUBSCRIPTION='<subscription-name>'
RG='<resource-group>'
ENVIRONMENT='<environment-name>'
ACR='<globally-unique-registry-name>'
IDENTITY='<pull-identity-name>'
APP='cowork-training-studio-mcp'
SERVER_SOURCE="$(pwd)/server"

az provider register --namespace Microsoft.App --subscription "$SUBSCRIPTION" --wait
az provider register --namespace Microsoft.ContainerRegistry --subscription "$SUBSCRIPTION" --wait
az group create --name "$RG" --location westus3 --subscription "$SUBSCRIPTION"
az containerapp env create --name "$ENVIRONMENT" --resource-group "$RG" \
  --location westus3 --enable-workload-profiles false --logs-destination none \
  --subscription "$SUBSCRIPTION"
az acr create --name "$ACR" --resource-group "$RG" --location westus3 \
  --sku Basic --admin-enabled false --subscription "$SUBSCRIPTION"
az identity create --name "$IDENTITY" --resource-group "$RG" --location westus3 \
  --subscription "$SUBSCRIPTION"
IDENTITY_ID=$(az identity show --name "$IDENTITY" --resource-group "$RG" \
  --subscription "$SUBSCRIPTION" --query id -o tsv)
PRINCIPAL_ID=$(az identity show --name "$IDENTITY" --resource-group "$RG" \
  --subscription "$SUBSCRIPTION" --query principalId -o tsv)
ACR_ID=$(az acr show --name "$ACR" --subscription "$SUBSCRIPTION" --query id -o tsv)
az role assignment create --assignee-object-id "$PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal --role AcrPull --scope "$ACR_ID" \
  --subscription "$SUBSCRIPTION"

az containerapp up --name "$APP" --source "$SERVER_SOURCE" --ingress external --target-port 8000 \
  --resource-group "$RG" --environment "$ENVIRONMENT" --location westus3 \
  --registry-server "$ACR.azurecr.io" --registry-identity "$IDENTITY_ID" \
  --user-assigned "$IDENTITY_ID" \
  --env-vars MCP_TRANSPORT=streamable-http PORT=8000 --subscription "$SUBSCRIPTION"
az containerapp update --name "$APP" --resource-group "$RG" \
  --cpu 0.25 --memory 0.5Gi --min-replicas 1 --max-replicas 2 \
  --subscription "$SUBSCRIPTION"
az containerapp show --name "$APP" --resource-group "$RG" \
  --subscription "$SUBSCRIPTION" --query properties.configuration.ingress.fqdn -o tsv
```

The **absolute server directory** is the build context, never the repository root.
Its `.dockerignore` allows only runtime source/dependencies and excludes caches,
virtual environments, `.env`, logs, tests, ZIPs and Git metadata. The image runs
as non-root. A precreated registry and scoped managed identity avoid registry
passwords and stored Container App secrets; never enable registry admin access.
Environment log collection is disabled. Application host/origin settings are
unchanged.

To redeploy, restore the variables above (including `IDENTITY_ID` and the
absolute `SERVER_SOURCE`) and repeat `az containerapp up`. Do not pass `--output`
to `up`; this extension rejects it. The cloud build creates a new image/revision.
Verify identity, registry, environment, CPU/memory, environment variables,
replica settings and ingress are unchanged. Confirm the healthy ready revision
gets 100% of traffic; the previous revision may briefly show as deprovisioning
with 0%. Never build from the repository root. Then run:

```sh
.venv/bin/python -m scripts.smoke_client --url 'https://<app-fqdn>/mcp/'
```

Both `/mcp` and `/mcp/` serve MCP directly with no redirect. Successful
initialize responses have no `mcp-session-id`.

For testing, min 1/max 2 avoids scale-to-zero discovery delays. At westus3 USD
list rates, 730 hours of one 0.25-vCPU/0.5-GiB replica plus Basic ACR is about
**$11/month idle to $25/month continuously active**; two continuously active
replicas are about **$45/month**. Shared free grants can lower this; outbound
traffic, extra registry storage and builds can add cost. Check
[current Azure pricing](https://azure.microsoft.com/pricing/details/container-apps/).

Delete the app when testing ends:

```sh
az containerapp delete --name "$APP" --resource-group "$RG" --subscription "$SUBSCRIPTION"
```

Deleting the app leaves the environment, registry and identity. The registry
continues billing. After confirming the group contains only disposable demo
resources, delete the dedicated group:

```sh
az group delete --name "$RG" --subscription "$SUBSCRIPTION"
```

## Optional temporary tunnel

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

The temporary Streamable HTTP endpoint is `https://<tunnel-host>/mcp/`.
Preserve the public Host/Origin headers. No `ALLOWED_HOSTS` change was needed
for either the tunnel or Azure; server host/origin settings remain unchanged.

```sh
.venv/bin/python -m scripts.smoke_client --url 'https://<tunnel-host>/mcp/'
```

Pass: initialize has no session ID, all eight tools are available, blueprint
summaries and details return top-level objects, the golden
spec has zero errors/warnings, and rendered HTML matches the committed example
byte-for-byte, and both demo fixtures validate/render at 0/0. The client prints render round-trip time and actual downloaded
HTTP-body bytes (MCP/SSE included; headers/TLS excluded), not a JSON-size estimate.

## Plugin package

Cowork connects through an uploaded plugin package, not a manual MCP connection.
In the existing server virtual environment, install the separate, pinned
[build-only requirements](../requirements-build.txt), then build:

```sh
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python -m scripts.build_plugin --mcp-url 'https://<app-fqdn>/mcp'
```

Build against the **Azure URL**, not an expiring tunnel.
The ZIP lands at `dist/cowork-training-studio-0.1.5.zip`; `--out <directory>`
changes the output directory. The script prints its SHA-256 and root-level file
list, fetches the live server's eight tool descriptions/schemas, and generates
the original TS icons with Pillow. No tool catalog is hand-written.
Names and descriptions are unchanged. By default, local schema references are
inlined, definitions/extensions/nonstandard keywords and titles are removed,
outputs are generic objects, and the four `spec` inputs direct the caller to
`get_lab_spec_schema` or `get_demo_pack_schema` as appropriate. The server still
enforces the full contracts.
Unsupported, unresolved or cyclic input references fail the build explicitly.
For raw-schema comparison without overwriting the deployable package:

```sh
.venv/bin/python -m scripts.build_plugin --mcp-url 'https://<app-fqdn>/mcp' \
  --raw-schemas --out dist/raw
```

The source template uses a fixed app ID and contains only a URL placeholder.
`dist/` is ignored; keep custom output directories out of Git too.

Upload in Cowork plugin settings. **Rebuild when the server URL changes**;
packages built with an expired tunnel will not connect. Package validation does
not prove tenant upload permission or successful Cowork execution.
The manifest uses `/mcp` without a trailing slash; either endpoint now works
without redirecting. Keep the same manifest ID when rebuilding.

The [build-training-lab skill](../plugin/skills/build-training-lab/SKILL.md) is
143 lines (limit 150). It offers blueprint choices, writes LabSpec 2.1 and fixes
all validation warnings. Cowork builds `learner/` sources/checkpoints and
`facilitator/` keys/run-of-show notes, then adds learner-relative hrefs, validates
and renders again, and saves the exact returned HTML at the pack root. It
re-reads every file, checks quote/clause placements and sections, verifies dates
and calculations with code, reports counts/fixes and offers a ZIP.
The server does not create files, mail, calendar items or ZIPs.

The [build-demo-pack skill](../plugin/skills/build-demo-pack/SKILL.md) is 128 lines.
It gathers inputs once, separates public facts/assumptions, requires 0/0, builds
Office sources before the prompt pack, and saves the exact guide and README.
Only `files/` is shared; guide/README/payoffs and `presenter/` stay private.
Optional email/meeting seeding requires confirmation, targets only the presenter
and never creates chats or sends to others. Both skills use discovered connector
tool names exactly, verify saved files with code and offer a ZIP. Both set
`locale` from the content language (`es` for Spanish) and avoid numbered titles.

M5c release verification: revision `0000006` serves 100% of traffic with all
settings unchanged from `0000005` except the image/revision. The built 0.1.5 ZIP
is **15,370 bytes**, SHA-256
`11e675eb7d77d6e847c7f8dec1e1ec0fe3cd329296f3148b70af2e5a25cfd581`.
It has four root files (manifest, catalog and two icons) plus the two skill files.
The manifest validates against the official Teams 1.28 schema; eight tools are
sanitized and all four spec parameters remain plain objects. Local tests: 395.
Live checks cover Spanish rendering and title-numbering warnings. Browser checks
cover Spanish copy success, reset, manual fallback and hidden presenter answers.
The existing 0.1.4 ZIP remains unchanged.

## Cowork checklist

| Test | Prompt/action | Pass condition |
| --- | --- | --- |
| A | "List the session formats you support" | Four formats returned; HTML lab and demo pack are available via their shipped skills. Word guide and prompt-a-thon remain coming soon. |
| A2 | "Help me choose a workshop shape" | Three blueprint choices; selected outline has the declared duration. Build super-day lab outlines as five separate HTML labs. |
| B | "Build me a 30-minute, 2-chapter story lab for Copilot in Excel for a fictional bakery chain; validate it, then render it and save the page to my files" | Zero validation errors; Cowork saves the page; the saved HTML opens offline. |
| C | During B, inspect the save step and record how Cowork handles the HTML. | Record whether it writes the tool result directly, retypes/reconstructs the HTML, or the behavior cannot be determined. Do not infer this from MCP smoke success. |
| D | "Create the practice pack and zip it" | Learner links resolve relative to the guide, facilitator keys/notes stay separate and unlinked, quote/calculation checks report counts, and the ZIP comes from Cowork's tools. |
| E | "Set up a Copilot demo with fictional inputs" | One input round with defaults; real Office files; 0/0 validation; exact HTML/README; payoff/date/number/link checks; share only files/. |
| F | Opt in to presenter-only demo seeding. | Explicit confirmation; correct fictional label/date; own mailbox/calendar only; no other recipients or chats; cleanup limited to created demo items. |

Observed: tunnel and Azure remote MCP smoke passed; golden HTML matched at
84,022 bytes. The 0.1.0 tunnel plugin installed and its connector showed
"available", but Cowork loaded none of its tools. Logs contained redirect-only
requests, but without timestamps/user-agent they cannot establish Cowork
attribution. Version 0.1.1 completed a real 60-minute Cowork lab run:
specification, three validation rounds ending at zero errors/warnings, render
and save. Cowork had to parse the render result as text. Version 0.1.2 exposes
render fields at the top level of structured content while retaining a text
fallback. M4b's 0.1.3 release adds five-tool discovery, blueprints and the pack
workflow; local and Azure smoke checks pass with the same golden bytes.
M5b's 0.1.4 adds the demo skill and eight-tool deployment; local and live checks
pass with all four fixtures at 0/0 and the same golden bytes.
M5c's 0.1.5 adds Spanish labels and title-numbering guidance, preserving English
lab/demo HTML and README bytes.
**Test both skills' Office-file, direct-write, pack/ZIP and optional seeding
workflows in Cowork with 0.1.5**; protocol and package checks do not prove those
live Cowork actions.

## Stop

Press Ctrl+C in the tunnel terminal, then in the server terminal:

```sh
devtunnel delete <tunnel-id>
```

Temporary tunnels normally delete themselves when hosting stops, so "not found"
after Ctrl+C means the tunnel is already gone. If an assistant launched detached
processes, use the specific host/server PIDs from its handoff with `kill <pid>`
instead of Ctrl+C, then delete the tunnel. Never use name-based process killing.
