# Azure infrastructure

M3e uses Azure CLI cloud build for a temporary anonymous demonstration.
Infrastructure-as-code remains deferred. Follow the
[deployment, redeployment and cleanup commands](../docs/cowork-connection-test.md#deploy-to-azure).

Demo resource names:

| Resource | Name |
| --- | --- |
| Container App | `cowork-training-studio-mcp` |
| Resource group | `rg-training-studio-mcp` |
| Container Apps environment | `cae-training-studio-mcp` |

The container listens on `0.0.0.0:8000` by default with
`MCP_TRANSPORT=streamable-http`; `/mcp` and `/mcp/` both serve without redirects.
The build context is `server/`, with a restrictive `.dockerignore`.
Basic ACR holds the cloud-built image; a scoped managed identity pulls it
without registry passwords. There is no database, storage account, stored app
secret, application telemetry or Microsoft Graph dependency.

The westus3 Consumption app has 0.25 vCPU/0.5 GiB and min 1/max 2 replicas for
testing. Environment log collection is disabled. This anonymous public endpoint
is fictional-data-only and **not production ready**. Delete the app and unused
dedicated infrastructure when testing ends; Basic ACR continues billing after
the app is deleted.
