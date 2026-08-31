---
tags:
  - concept
---

# Secrets

**M9.** #todo — this note is ahead of the code.

## The defect it replaces

`app/core/secrets.py:38` silently fell back to base64 when a keyring was unavailable.
Base64 is not encryption. A user who believed their credentials were protected had them
stored in plain sight, and nothing said so. That is [[Why a Rewrite|defect 4]].

## The rule

**Keyring-first, and no base64 fallback.** If the keyring is unavailable, `sclpl` says
so and refuses, rather than storing the secret in a way that looks safe and is not.

Refusing is the whole point. A fallback that is weaker than what the user asked for,
applied without telling them, is worse than an error.

## Redaction

[[Invariants#9 Secrets never reach a log, a label, or a trace]]. Redaction lives in
`render/redact.py` and is applied **in the reporter**, keyed on the set of resolved
secret values.

That placement is deliberate. A component that forgets to redact cannot leak, because it
never had the opportunity — every event passes through one writer, and the writer
redacts. The alternative, asking every emitter to redact correctly, fails the first time
someone adds an emitter.

Secrets never appear in a fixture, a snapshot, or a log. That is a test-suite rule as
well as a runtime one.

→ [[state]], [[The Terminal Layer#Redaction lives here]]
