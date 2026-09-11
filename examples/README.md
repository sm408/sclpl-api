# Examples

Every `.sclpll` file in this directory is validated by the integration suite. The
network-facing workflows use placeholder hosts so `sclpl validate` works offline; pass
`--var base=...` when running them against a real API.

| Example | Pattern |
|---|---|
| `orders.sclpll` | Larger order workflow with modes, pagination, joins, and reports |
| `playbook-01.sclpll` | Paginated API to CSV |
| `playbook-02.sclpll` | API rows joined with local SQLite |
| `01-http-to-json.sclpll` | Minimal HTTP call to JSON |
| `02-cursor-pagination.sclpll` | Cursor pagination |
| `03-token-pagination.sclpll` | Header-token pagination |
| `04-link-header-pagination.sclpll` | RFC Link-header pagination |
| `05-offset-pagination.sclpll` | Offset pagination |
| `06-clean-and-profile.sclpll` | Fill nulls, filter, profile |
| `07-join-and-aggregate.sclpll` | Join and aggregate |
| `08-branching-quality-gate.sclpll` | Conditional quality gate |
| `09-foreach-enrichment.sclpll` | Bounded foreach enrichment |
| `10-parallel-and-gate.sclpll` | Parallel branches plus a gate |
| `11-cache-retry-and-secret.sclpll` | Cache, retry, and secret interpolation |
| `12-text-plugin-library.sclpll` | Text plugin helpers |
| `13-python-script.sclpll` | Registered, SHA-256-pinned Python script as a JSON-connected workflow step |
