# sclpl upgrade: remaining feature gaps versus alternatives

Assessment date: 2026-09-05. Compared against the revised
[unified upgrade plan](UNIFIED-UPGRADE-PLAN.md), repository code, and official product
documentation. This is a candidate list, not an automatic expansion of release scope.
Priorities are product judgments for sclpl's API-to-data positioning, not vendor claims.

## Comparison rules

- Exclude deliberate deferrals: sandboxing, GUI/TUI/visual editors, hosted control
  planes, scheduling, servers/mock hosting, collaboration/accounts/billing, marketplaces,
  broad connector catalogues, AI generation, and other explicitly deferred work such as
  nested workflow `use` execution and Insomnia import.
- Compare first-class supported behavior. A custom Python function may implement a
  capability without the CLI providing its lifecycle, schema, documentation, or tests.
- Do not count HTTP headers, request chaining, retries, pagination, assertions, unique/null
  checks, in-memory deduplication, or format exports as wholly missing. They exist or
  are already planned. Planned fixtures/contracts/reports/auth are also not new gaps.
- Separate native protocol support from sending a protocol's bytes over ordinary HTTP.
- This is a scoped assessment of relevant documented features, not an exhaustive parity
  claim across every vendor, edition, or protocol.

## Highest-value candidates for the existing product direction

| ID | Missing or incompletely specified feature | Existing coverage and exact gap | Suggested fit |
|---|---|---|---|
| P1 | Incremental extraction across successful runs | Pagination moves within one run; resume repairs one interrupted run. Neither defines persistent `updated_since`/ID watermarks, overlap windows, late-arriving records, or bounded backfill state. Commit a watermark only after validated output publication. dlt documents these incremental cursor behaviors. [Source](https://dlthub.com/docs/general-usage/incremental/cursor) | High: extend C/D/G identity, completeness, and publication infrastructure |
| P2 | Declarative append/replace/merge output modes | Exports, SQLite joins, and in-memory dedupe do not define a common sink-level primary-key/upsert policy across runs. Add explicit key/conflict rules and transactional merge for supported sinks; do not imply CSV can perform database upserts in place. dlt provides append, replace, and merge dispositions. [Source](https://dlthub.com/docs/general-usage/incremental-loading) | High: E/G, paired with P1; scope initially to SQLite and versioned file datasets |
| P3 | OAuth authorization-code + PKCE and refresh-token lifecycle | B5 specifies client credentials. User-authorized integrations need interactive authorization followed by secure noninteractive refresh, rotation, expiry, and revocation handling. Postman supports authorization-code/PKCE flows and refresh tokens. [Source](https://learning.postman.com/docs/use/send-requests/authorization/oauth-20/) | High where target APIs require user consent: B5 extension |
| P4 | Mutual TLS and custom trust stores | The plan mentions TLS/proxy profiles but lacks explicit client certificate/key/chain, password references, custom CA bundles, and certificate-aware connection-pool isolation. Postman exposes CA and client certificates. [Source](https://learning.postman.com/docs/getting-started/installation/settings/certificates) | High for internal/enterprise APIs: B/D |
| P5 | Explicit cookie/session lifecycle | Pooled HTTPX clients may already retain cookies; that is not a defined session API. Specify named isolated cookie jars, login/request sharing, reset/disable behavior, expiry, and optional protected persistence. Never let replay fixtures become live session credentials. Postman exposes cookie management and request controls. [Source](https://learning.postman.com/docs/use/send-requests/response-data/cookies/) | High correctness value for session-auth APIs: B/D |
| P6 | Parameterized test datasets and matrices | E3 supports individual manifests and inputs, and workflows can loop. Missing: CSV/JSON-driven test cases, environment/input matrices, stable case IDs, per-case isolation/results, and filtering failed cases. Bruno documents CSV/JSON data-driven runs. [Source](https://docs.usebruno.com/testing/automate-test/data-driven-testing) | High, modest extension to E3/E4 rather than another runner |
| P7 | Test setup and teardown lifecycle | Input isolation and notification hooks do not provide create-resource/test/delete-resource cleanup semantics. Specify scoped setup, best-effort teardown after assertion failure or cooperative cancellation, and separate cleanup failure reporting; no guarantee after force-kill. Postman documents setup/test/teardown sequences for performance runs. [Source](https://learning.postman.com/docs/tests-and-scripts/performance-testing/performance-test-configuration) | High for integration regression tests: E/G; reuse ordinary workflow steps |
| P8 | Freshness and aggregate data-quality contracts | Existing assertions cover shape, unique/null values, ranges, and row counts. Missing: first-class maximum data age, accepted null fractions, cross-table integrity, and baseline-relative volume/distribution checks. Great Expectations documents these quality dimensions. [Source](https://docs.greatexpectations.io/docs/reference/learn/data_quality_use_cases/dq_use_cases_lp) | High for trustworthy reports: E/F; start with freshness and relative volume, explicit tolerances |

## Useful interoperability and testing candidates

| ID | Missing or incompletely specified feature | Existing coverage and exact gap | Suggested fit |
|---|---|---|---|
| P9 | Named AWS SigV4 signing | Generic HMAC extension points do not implement AWS canonicalization, region/service scope, temporary security tokens, or presigned requests. Postman has a dedicated AWS Signature auth workflow. [Source](https://learning.postman.com/docs/use/send-requests/authorization/aws-signature) | Medium: optional signer in B6; prioritize when AWS APIs are a target |
| P10 | First-class GraphQL workflows | HTTP can send a GraphQL JSON body, but the plan lacks operation documents/variables, schema validation/introspection, and an explicit `errors`-with-HTTP-200 policy. Postman has dedicated GraphQL support. [Source](https://learning.postman.com/v11/docs/use/send-requests/protocols/protocols) | Medium to high for SaaS extraction: HTTP-backed adapter and contracts, no new scheduler |
| P11 | XML/SOAP response interpretation and contracts | Raw XML can travel over HTTP; the missing surface is namespace-aware extraction, XPath/XSD validation where supported, SOAP fault interpretation, and safe XML parser settings. Postman documents SOAP request support, but that alone is not evidence of every XML feature proposed here. [Source](https://learning.postman.com/v11/docs/use/send-requests/protocols/protocols) | Medium for legacy integrations: codec/contract plugin; define a bounded subset |
| P12 | API latency assertions and bounded load profiles | Reports record timings and J3 benchmarks sclpl itself. Neither defines a user command to test a target API's p95 latency/error rate under fixed/ramping load. Postman supports virtual-user profiles and performance pass conditions. [Source](https://learning.postman.com/docs/postman-cli/postman-cli-monitoring) | Medium: latency assertions first; a full load generator is a much larger separate decision |
| P13 | Schema-generated positive/negative tests | OpenAPI import and contract snapshots check authored cases. Missing: generate invalid/boundary requests, exercise stateful sequences, and reproduce generated failures using a seed. Schemathesis exposes positive/negative generation, seeds, and stateful cases. [Source](https://schemathesis.readthedocs.io/en/latest/reference/cli/) | Medium: integrate an established generator through CI before writing a new engine |
| P14 | Outbound cURL/code export | I1 imports cURL; it does not export a selected resolved request as sanitized cURL or Python. This helps debugging and handing reproductions to API owners. Postman generates cURL, raw HTTP, Python, and other snippets. [Source](https://learning.postman.com/docs/sending-requests/create-requests/generate-code-snippets) | Medium, relatively narrow: I; secret references and shell-specific quoting are mandatory |
| P15 | Non-HTTP RPC/message workflows | Native gRPC and WebSocket/MQTT sessions need different connection, message, cancellation, fixture, and assertion semantics. Postman supports these protocols. This is genuine protocol breadth beyond the current HTTP runner, not missing REST behavior. [Source](https://learning.postman.com/docs/use/send-requests/create-requests/request-basics) | Lower for the current API-to-file wedge; assess as protocol plugins only when demand justifies it |

## Recommended selection

The largest functional omission for recurring data jobs is P1 together with P2:
incremental extraction plus explicit sink update semantics. Build them together so
watermark advancement, output commit, process coordination, and resume agree.

P3–P5 close real authentication/connectivity gaps. Select auth methods from target
customer APIs; broad historical auth parity is not an objective by itself. P6–P8
strengthen testing and trust with less architectural expansion than new protocols.

P10 is a natural HTTP extension for SaaS APIs. P9/P11/P14 can be bounded adapters. P12
should begin with latency contracts rather than an entire load-testing platform, and
P13 is a good integration opportunity. P15 has the greatest risk of widening the product
before its core use cases are proven.

None of P1–P15 is counted as committed unified-release scope merely because it appears
here. The requested output publication, process locking, data fidelity, completeness,
and early secret-leak work has been incorporated into the main plan with task IDs.
