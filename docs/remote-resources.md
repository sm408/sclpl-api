# Remote resources

SCLPL 0.9.1 lets a registered provider supply a workflow and its input/output
ports. The runner remains storage-neutral: providers download inputs to controlled
local staging paths, existing readers and writers use those paths unchanged, and
successful staged outputs are published only after execution completes.

## Azure Blob Storage

Install the separate provider distribution:

```powershell
pip install sclpl-azure-blob
az login
sclpl run azblob://myaccount/workflows/jobs/orders/
```

The bundle must contain exactly one of `workflow.sclpll` or `workflow.json`.
For a workflow with `customers:csv` and `report:csv`, omitted bindings use:

```text
inputs/customers.csv
outputs/report.csv
```

Explicit bindings take precedence and may be local or supplied by another provider:

```powershell
sclpl run azblob://myaccount/workflows/jobs/orders/ `
  --in customers=./customers-test.csv `
  --out report=azblob://myaccount/reports/orders/report.csv --overwrite
```

Azure authentication uses `DefaultAzureCredential`; use Azure CLI login locally or a
managed identity in Azure. Do not put SAS tokens, account keys, or credentials in
workflow files. URI displays remove query strings, and remote overwrite publishes
only against the revision observed before execution. A changed destination raises a
conflict instead of silently losing another writer's update.

### Azure authentication and endpoints

Set `SCLPL_AZURE_BLOB_AUTH` to select an explicit mode. Secret values stay in the
environment (or the host's secret-injection system), never in a workflow or `azblob://`
URI.

| Mode | Required configuration | Typical use |
| --- | --- | --- |
| `default` (default) | Azure Identity standard environment/CLI/managed identity configuration | developer login, managed identity, workload identity, service principal |
| `connection-string` | `SCLPL_AZURE_BLOB_CONNECTION_STRING` (or Azure's `AZURE_STORAGE_CONNECTION_STRING`) | emulator or established connection-string deployments |
| `account-key` | `SCLPL_AZURE_BLOB_ACCOUNT_KEY` | constrained legacy deployments |
| `sas` | `SCLPL_AZURE_BLOB_SAS_TOKEN` | short-lived, scoped access; the leading `?` is accepted |
| `custom` | construct `AzureBlobProvider(credential_factory=...)` in an embedding host | application-owned `TokenCredential` |

For a user-assigned managed identity, keep `default` mode and set
`SCLPL_AZURE_BLOB_MANAGED_IDENTITY_CLIENT_ID`. Workload identity and service-principal
configuration follow the standard Azure Identity environment variables.

For private endpoints, sovereign clouds, or test emulators that are not using a
connection string, set `SCLPL_AZURE_BLOB_ACCOUNT_URL`. It may contain `{account}`, for
example `https://{account}.privatelink.blob.core.windows.net`. Alternatively set
`SCLPL_AZURE_BLOB_ENDPOINT_SUFFIX` (for example `blob.core.usgovcloudapi.net`).

`SCLPL_AZURE_BLOB_AUTH=default` deliberately leaves credential selection to
`DefaultAzureCredential`; Azure's own service-principal, workload-token, and
managed-identity environment settings remain effective without being copied into
SCLPL configuration.

## Remote cache and offline runs

Remote workflows and inputs are stored beneath `~/.sclpl/resources` as
content-addressed blobs. The cache index keys a normalized resource URI by hash, so it
does not retain signed URI query strings. When a provider supplies revisions, SCLPL
checks the current revision online and reuses only the matching cached blob.

Each cache address is a SHA-256 content checksum. SCLPL verifies that checksum before
serving a cache hit; corrupted cache data is a miss in offline mode and is redownloaded
and repaired by an online run. `ResourceInfo.checksum` reports this verified value as
`sha256:<hex>` for cached materializations.

`sclpl run --offline azblob://...` makes no Azure calls: the workflow bundle and every
remote input must already be cached. A missing object exits with code 5 and recommends
one ordinary online run. Outputs are still never published by a failed execution.

`--refresh` bypasses existing remote cache entries and replaces them after download;
`--no-cache` bypasses remote caching entirely. Providers without revision support are
always downloaded online, but their latest materialized copy remains usable offline.

## Remote input globs

Input bindings can select multiple remote objects with a quoted glob. SCLPL asks the
provider to list the fixed prefix, applies one provider-neutral match rule in core, and
binds the resulting resources in stable URI order:

```powershell
sclpl run azblob://myaccount/workflows/jobs/orders/ `
  --in events='azblob://myaccount/data/events/2026-09-*.json'
```

Remote globs are input-only; an output must name one exact destination URI. A pattern
that matches nothing is a validation error rather than silently running with no input.

## Immutable remote generations

Use `--remote-generation` for multi-output remote workflows that need a completed-set
view. Outputs upload to `generations/<run-id>/...`; only after every upload succeeds
does SCLPL conditionally update the parent `latest.json` manifest. A failed upload can
leave unreachable objects, but never a manifest for a partial generation.

## Azure transfer tuning

`SCLPL_AZURE_BLOB_MAX_CONCURRENCY` sets Azure SDK upload and download concurrency for
this provider only. Leave it unset to use Azure SDK defaults; it must be a positive
integer. This setting is deliberately not a core runner option because other providers
have different transfer models.

## Distributed locks

Providers advertise native locking through `sclpl resource doctor`. Azure Blob uses
an Azure Blob lease on an existing blob: `acquire_lock(uri, lease_duration=60)` returns
a context manager that releases the lease on exit. Azure accepts finite leases from 15
through 60 seconds, or `-1` for an infinite lease. Keep leases short and use the
context-manager form; workflows do not automatically acquire remote locks yet.

## Cross-provider copies

Embedding hosts can call `copy_resource(source_uri, destination_uri)` to copy between
any readable source and writable destination provider. The default implementation
streams through a bounded in-memory spool that rolls to an OS-managed temporary file
for larger objects, so no provider-specific credentials or SDK types cross the public
API boundary. Destination create-only and revision-aware write rules still apply.

## Provider conformance toolkit

Provider authors can use `ResourceProviderFixture` and
`assert_resource_provider_contract` from `sclpl.testing.resources` against an
existing fixture object. The suite checks URI normalization and resolution, safe
display output, `stat`/`exists`, normalized listing, and optional missing-object
behavior without creating or deleting remote data. `assert_resource_error` verifies
that failed SDK calls are translated to SCLPL's public resource-error hierarchy.

## Remote workflow locks

`sclpl run --locked` and `sclpl workflow lock` preserve a remote workflow's redacted
logical URI, observed provider revision, and staged source digest. A changed ETag (or
other provider revision token) therefore causes lock drift even when a cached staging
path happens to be reused. Query-string credentials are excluded from the lockfile.

## Diagnostics

Use `sclpl resource doctor azblob://account/container/known-object.csv` to verify that
the provider loaded, credentials are usable, and the selected identity can read the
object. The command performs no write; it reports provider-declared write/list and
conditional-write support separately.

## Versioned Azure resources

Azure Blob version IDs and snapshots can be addressed with `versionid` or `snapshot`
query parameters, for example `azblob://account/container/report.csv?versionid=...`.
These are honored for reads while display, diagnostics, and history continue to redact
query strings.

Troubleshooting: install `sclpl-azure-blob` in the same Python environment as
`sclpl`, then confirm the identity has Storage Blob Data Reader for workflows/inputs
and Storage Blob Data Contributor for outputs. `sclpl validate azblob://...` fetches
the workflow but does not download inputs or publish outputs.
