# Azure infrastructure (planned)

Infrastructure-as-code and deployment are deferred to M4.

Reserved Azure names:

| Resource | Name |
| --- | --- |
| Container App | `ca-training-studio-mcp` |
| Resource group | `rg-training-studio-mcp` |

The container listens on `0.0.0.0:8000` by default with
`MCP_TRANSPORT=streamable-http` and the MCP endpoint at `/mcp`.
There is no database, storage account, managed secret, or Microsoft Graph
dependency in M1. No Azure resources are provisioned by this scaffold.

M1 has no authentication and is for local/trusted testing, not public production
ingress. Deployment must explicitly address network exposure and platform-level
access controls without adding tenant-data access to the MCP server.
