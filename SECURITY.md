# Security policy

## Data handling

Cowork Training Studio is stateless: it stores no customer or tenant data,
holds no secrets, and makes no Microsoft Graph calls. There is no runtime
disk, database, or external storage for request content. Ephemeral in-process
memory is allowed, but request data does not survive a restart.

Never put real customer or tenant data, real person names, credentials, or
secrets in specs, fixtures, examples, logs, or issue reports. Use wholly fictional
Zava-style brands and generic role labels instead.

DemoPackSpec 1.0 has one narrow exception: public audience context may be supplied,
with customer names only in audience/title/talk tracks and the filename prefix.
The operating company and every seeded record must still be fictional; lab specs,
fixtures, examples and issue reports remain wholly fictional. The server does
not fetch public sources, and its name-matching warnings are not data-loss
prevention or anonymization.

Skills write content; Cowork's own tools handle saving and sending with the
user's permissions. This server does not save generated content or access
tenant services.

## Reporting issues

Report security issues through
[GitHub Issues](https://github.com/emontes07/cowork-training-studio/issues).
This repository and its issues are public. Include the affected version,
expected and observed behavior, and reproduction steps using fictional data
only. Never include customer data, credentials, or secrets in a report.

If a credential is exposed, revoke or rotate it through its provider; do not
copy it into an issue.

## Deployment boundary

This is a public, customer-deployable accelerator, not a hosted service.
The M1 server has no application authentication and is intended for
local or trusted-network testing. A public source repository does not make an
unauthenticated deployment safe: review platform-level access controls,
network exposure, and diagnostic-log handling before deploying it.
