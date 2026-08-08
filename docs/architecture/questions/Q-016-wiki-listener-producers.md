# Q-016 — Wiki Event-Listener Producers: Wire or Remove (ADR-080 follow-up)

> **Status:** 🟡 Open
> **Blocks:** Nothing (dormant subscriptions — no producer fires them today)
> **Raised:** 2026-08-08
> **Source:** PR #157 review follow-up (ADR-080 — remove Redis & TaskIQ)

---

## Question

Decide: wire producers for `kb.entry.updated` / `chapter.finalized` /
`wiki.prompt.changed`, or remove the dormant `WikiEventListener`
subscriptions in `apps/api/narrare/wiki/listeners.py`?

## Context

ADR-080 removed the Redis event bus, the dormant `EventListener`, and the
publish-to-nobody `_publish_content_event` traffic. The review follow-up
(PR #157) additionally removed the dead `_publish_wiki_sync_event` path
(`apps/api/narrare/kb/embedding_hooks.py`) and the `wiki.sync.requested`
subscription (lifespan) — that path could never fire (`EmbeddingHookManager`
is constructed **without** `event_bus`). `on_wiki_sync_requested` and its
test file (`test_embedding_hooks_wiki_sync.py`) were removed with it.

The remaining `WikiEventListener` subscriptions (`kb.entry.updated`,
`chapter.finalized`, `wiki.prompt.changed`) are still registered in the
lifespan against the in-process `EventPublisher`, but no producer is known
to fire them today — they are dormant. Deleting them is an option; wiring
real producers would re-enable automatic wiki regeneration over KB /
chapter / prompt changes (the WIKI-001 intent), but that is scope beyond
the ADR-080 removal and must be a deliberate decision.

Related: the `WIKI_SYNC_REQUESTED` enum member in
`packages/core/narrare_core/events/types.py` is now orphaned (no
subscription, no publisher). It is **kept** as domain vocabulary — the
count assertion in `tests/unit/core/events/test_event_types.py` includes it
and is unaffected — but its fate belongs to this same decision.

## Options

- **A — Wire producers:** connect real publishers for `kb.entry.updated` /
  `chapter.finalized` / `wiki.prompt.changed` to restore automatic wiki
  regeneration. Larger scope; a WIKI-001 feature decision, not an ADR-080
  cleanup.
- **B — Remove the dormant subscriptions:** delete the
  `WikiEventListener` registration (and the listener, if nothing else
  consumes it) and the orphaned `WIKI_SYNC_REQUESTED` member. Smallest
  cleanup; loses the (currently non-functional) auto-regeneration hook.

## Affected Areas

- `apps/api/narrare/wiki/listeners.py` — `WikiEventListener`
- `apps/api/narrare/_app/lifespan.py` — subscription registration
- `packages/core/narrare_core/events/types.py` — `WIKI_SYNC_REQUESTED` enum member
- `tests/unit/core/events/test_event_types.py` — count assertion (unchanged either way)

## Related

- ADR-080 — Remove Redis & TaskIQ for Single-User Deployment (in-process execution boundary)
- WIKI-001 — LLM Wiki (Precomputed Context Layer)
- `docs/architecture/implementation-plans/INFRA-remove-redis.md`

---

> **Status:** 🟡 Open — follow-up to ADR-080 / PR #157; blocks nothing while dormant
