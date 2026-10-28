# ADR-102 — Provider profiles, per-task assignment and tiered key storage

> **Status:** 🔄 Proposed
> **Date:** 2026-10-28
> **Deciders:** Product owner
> **Supersedes:** none — amends the provider model in the v2 architecture spec
> (§4, §12.2), which stays the authority

---

## Context

The v2 spec assumed one provider per process, declared in a hand-edited
`llm/_providers/catalog.yaml` (spec §2), so that "adding a provider is one catalog
entry" (§4, §12.2). The WP2a design (2026-10-26, approved 2026-10-27) measured that
assumption against the product: every user brings their own model and key, the
model set moves faster than this repository, and a process-wide environment
variable cannot name which configuration an audited call used.

Facts that forced the change:

- One provider per process means every user of a process shares it; the product is
  local-first with one fixed local user today and a hosted future (ADR-101).
- Prices, context windows and output limits change monthly; a hand-maintained
  catalog ages between releases.
- An API key is a secret. It cannot sit in plaintext beside the row that uses it,
  and it cannot live only in a process environment.

---

## Decision Drivers

- The audit must name the configuration a call used (`LlmCall.profile_id`).
- A vendor change (Groq, OpenRouter, a local service) must not need a release.
- A stored key must never be readable from the database file alone.
- No second broker or vault process (spec §9: Postgres is the only server).

---

## Options Considered

### Option A — keep the hand-edited catalog, one provider per process

**Pros:** no schema, no settings surface, spec unchanged.

**Cons:** every user of a process shares one provider and key; the audit cannot
name a configuration; every vendor change is a release.

### Option B — per-user profile rows, a vendored model snapshot, tiered key storage

**Pros:** providers become data; the audit names profile and cost; vendors on the
OpenAI chat shape need no code.

**Cons:** a settings capability and UI; a secret-store decision (spec §8 boundary);
a snapshot to refresh.

### Option C — keys in the environment or a plaintext column

**Pros:** simplest to read and debug.

**Cons:** one key per process, not per user; a plaintext column leaks with every
database copy; no hint display without reading the key itself.

---

## Decision

**We choose Option B.** A user owns `ProviderProfile` rows
(`app/kernel/llm/models.py`): `kind` is `fake` or `openai-chat`, plus `base_url`,
`model`, optional `context_window` / `max_output_tokens` / `temperature` /
`request_timeout`, and a key. `TaskAssignment` names one profile per task key —
`writing.continuation`, `chat.ask`, `knowledge.extract-entities`,
`knowledge.check-consistency` route; `settings.test` is audit-only
(`app/kernel/llm/resolution.py`). Resolution is exact task key → prefix → the
user's default → environment → `fake`. A new vendor on the OpenAI chat shape is a
profile row and no code; a new API shape is an adapter plus one `PROFILE_KINDS`
value.

Model metadata comes from a vendored models.dev snapshot
(`app/kernel/llm/data/models.json`, refreshed by
`python -m app.kernel.llm.data.refresh`); an entry the snapshot does not know
prices a call as `NULL`, never as zero.

A key has two storage tiers (`app/kernel/secrets.py`): the OS keychain first,
behind a usability probe that rejects a `NullKeyring` backend, or one whose read
probe raises; otherwise Fernet under `NARRE_SECRET_KEY` in the row.
`NARRE_KEYRING=off` forces the Fernet tier. Neither tier available raises
`NoKeyStoreError` and creates no row (HTTP 503). The plaintext key exists only in
the create response; the stored hint is its last four characters.

---

## Rationale

The keychain is a second store, which spec §8 reserves to the product owner. The
three statements, as §8 asks for them:

1. **The failure it prevents:** a stored API key readable from the database file
   alone — every backup, sync copy and laptop carry the key in the clear.
2. **The effort it creates per change:** none for ordinary changes; the tier
   boundary lives in `app/kernel/secrets.py` and is invisible to callers.
3. **The cheaper alternative:** a plaintext column (Option C) — rejected because
   it fails statement 1 outright.

The owner approved the crossing in the WP2a design acceptance of 2026-10-27; this
record is its dated trace.

---

## Consequences

**Positive:**
- Providers are data: a new vendor on a known API shape is a `/settings` row.
- `LlmCall.profile_id` names the configuration a call used; `cost_usd` names its
  cost (the two columns are specified in the WP2a design's goals).
- E2E pins the Fernet tier with a fixed test key and `NARRE_KEYRING=off`
  (`app/kernel/testing/stack.py`), so no test touches a developer's keychain.

**Negative / Tradeoffs:**
- Reversing the key tiers means re-encrypting or re-prompting every stored key —
  expensive enough to belong in an ADR rather than in a diff.
- A vendored snapshot can lag a new model; the price is then `NULL` until a
  refresh, not wrong.

**Constraints introduced:**
- Spec §4 and §12.2 are amended on this point: "adding a provider is one catalog
  entry" became "adding a provider is one profile row".

---

## Implementation Notes

Profiles and assignments: `app/kernel/llm/profiles.py`; resolution cascade:
`app/kernel/llm/resolution.py`; the OpenAI chat adapter: `app/kernel/llm/openai_chat.py`;
costs and limits: `app/kernel/llm/catalog.py`; the settings surface:
`app/capabilities/settings/`.

---

## Review Trigger

- [ ] When the hosted multi-user model is decided (ADR-101's open question) — key
      storage per user then needs a second look.
- [ ] When a provider with an API shape other than OpenAI chat is wanted — the
      adapter-plus-`PROFILE_KINDS` path gets its first real exercise.
- [ ] When a keyring backend misbehaves on a supported platform — the probe's
      read-only design gets re-checked against a write-failure case.
