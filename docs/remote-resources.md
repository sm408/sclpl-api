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

Troubleshooting: install `sclpl-azure-blob` in the same Python environment as
`sclpl`, then confirm the identity has Storage Blob Data Reader for workflows/inputs
and Storage Blob Data Contributor for outputs. `sclpl validate azblob://...` fetches
the workflow but does not download inputs or publish outputs.
