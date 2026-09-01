---
tags:
  - concept
---

# Secrets

`state/secrets.py`. Credentials, stored somewhere that is actually a secret.

## The defect it closes

`app/core/secrets.py:38` fell back to **base64** when a keyring was unavailable, and said
nothing. Base64 is not encryption; it is an encoding a person can undo in their head. A
user who believed their token was protected had it stored in plain sight.

That is [[Why a Rewrite|defect 4]], and it is the one that was a *safety* problem rather
than a capability gap.

## Three backends, and no fourth

1. **The OS keyring** — Keychain, Credential Manager, Secret Service. The right answer:
   it is already what the user's other tools use, and already unlocked when they are
   logged in.
2. **An encrypted file** — Fernet, key at `0600`. For a server with no keyring daemon,
   which is a real situation rather than a mistake.
3. **Nothing** — refuse, and name both installs.

```
no secure place to keep a secret is available
  - pip install 'sclpl[keyring]'   -- uses the OS keyring
  - pip install 'sclpl[crypto]'    -- an encrypted file, for a server
  - sclpl will not fall back to anything weaker, so nothing is stored
```

**Refusing is the whole point.** A fallback weaker than what the user asked for, applied
without telling them, is worse than an error — an error is visible the first time, and a
weak store is invisible until it matters.

> Installed is not the same as usable. `keyring` falls back to a `fail.Keyring` on a
> machine with no daemon, and that raises on the first write. It is checked *before* use,
> so the encrypted file gets its turn rather than the user getting an exception from
> inside somebody else's package.

## The key is created at `0600`, not chmod'd to it

```python
handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
```

Not written and then fixed. Between those two calls the key would be world-readable, and
a key anyone can read is not a key. A key found with loose permissions is refused rather
than used anyway.

## Reading is not storing

`SCLPL_SECRET_<NAME>` is read when nothing is stored — for CI, where there is no keyring,
no interactive session to unlock one, and the secret arrives as an environment variable
anyway.

Reading one is not the same as *writing* one somewhere weak. Where a secret comes from
and where it is kept are different questions, and the refusal is about the second.

## In a workflow

```
@step fetch
  get {{base}}/orders
  header Authorization: Bearer {{secret('api-token')}}
```

`secret()` fails loudly when there is none. A request authenticated with an empty string
gets a 401 that reads as "the credential was wrong", which sends the reader somewhere
else entirely. `has_secret()` is for a workflow that wants to do something different
rather than fail.

## Environments are namespaces

```bash
sclpl secret set token --env staging
```

One store with prefixed keys, not a store per environment: the keyring has one namespace
per service anyway, and two stores would mean two things to unlock.

## Redaction

[[Invariants#9 Secrets never reach a log, a label, or a trace]]. It happens **in the
reporter**, keyed on the set of resolved values — so `secret()` can return the real thing
and every sink still shows it redacted.

That placement is the guarantee. A component that forgets to redact cannot leak, because
it never had the opportunity; asking every emitter to redact correctly fails the first
time someone adds one.

→ [[Run History]], [[The Terminal Layer#Redaction lives here]]
