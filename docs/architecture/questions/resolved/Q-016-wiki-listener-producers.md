# Q-016 — Wiki Event-Listener Producers: Wire or Remove (ADR-080 follow-up)

> **Status:** ✅ Resolved (2026-08-08) — **Option A** (re-wire producers in-process; closes staleness gap). *Revised from Option B after Product-Owner decision + deeper root-cause analysis.*
> **Blocks:** Nothing (dormant subscriptions — no producer fires them today); implementation is a WIKI-001 follow-up.
> **Raised:** 2026-08-08 · **Revised:** 2026-08-08
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

## Resolution — Option A (re-wire producers in-process; closes the staleness gap)

> **Status:** ✅ Resolved (2026-08-08) — **Option A** chosen (Product-Owner decision).
> **Documentation:** Resolution in this question file + WIKI-001 spec banner correction. No
> full ADR (this is a WIKI-001 follow-up that executes the ADR-080 in-process pattern and the
> ADR-022 design intent — it introduces no new pattern, dependency, or RULE-XX exception per the
> ADR-process trigger table). *Round 1 had resolved this as Option B; revised to Option A after a
> deeper root-cause read surfaced a silent-correctness gap (not merely a UX downgrade) and the
> Product Owner confirmed the auto-regeneration behaviour is the intended UX.*

### Root cause (revised — stronger than Round 1)

Round 1 correctly identified the three subscriptions as **publish-to-nobody** and recommended
removal (Option B). A deeper read changes the *consequence classification*: this is a **silent
correctness gap**, not just a UX downgrade.

Because ADR-080 severed the event chain, an entity edit fires **no** event:

1. The edit → `WikiEventListener.on_kb_entry_updated` is **never invoked** → the entity's
   `WikiSummary` is **neither regenerated nor marked stale** → it stays at `status = fresh`
   holding **OLD content**.
2. On the next write, `WritingContextAssembler` loads the referenced entities' summaries. The
   **raw-data fallback engages only when status ∈ {stale, pending}** (WIKI-001 "How it works —
   fallback"). A stale-but-marked-`fresh` summary is therefore served as **current truth** — the
   AI writes against an outdated character view, with **no signal to the user and no fallback**.

So keeping the chain severed (Option B) does not merely drop a convenience — it **serves
stale content as fresh**. Option A (re-wire the producers against the in-process `EventPublisher`
the lifespan already creates) closes this gap AND restores the WIKI-001 design intent
("update an entity → summary regenerates"; "How it works" steps 1–4).

### §7 verification (reality, not claims)

The publish-to-nobody diagnosis is confirmed and *strengthened* by reading the code:

1. `build_core_wiki_service` (`apps/api/narrare/wiki/dependencies.py:62`) wires the Core
   `WikiService` with **`NullEventBus()`**. `WikiService.mark_all_stale`'s
   `await self._event_bus.publish(...)` (which carries `EventType.WIKI_PROMPT_CHANGED`,
   `core/wiki/service.py:200-212`, unit-tested at `tests/unit/core/wiki/test_service.py:251`) is
   a **no-op**. So the one Core-side producer that *exists* (`wiki.prompt.changed`) is doubly
   broken: published to `NullEventBus` on the Core side AND the lifespan publisher is a separate
   instance nobody publishes to.
2. The lifespan (`_app/lifespan.py:214-220`) creates a **separate** `EventPublisher()` and
   subscribes the listener to IT (`app.state.wiki_event_publisher`). **Nothing publishes** to it
   for `kb.entry.updated` / `chapter.finalized` / `wiki.prompt.changed`.
3. `kb.entry.updated` / `chapter.finalized` have **no producer at all**.
   `EmbeddingHookManager` (`kb/embedding_hooks.py`) is constructed **without** an event bus
   (`kb/dependencies_core.py:73` — `EmbeddingHookManager(embedding_repo=...)`, no publisher).
   The chapter status→`final` transition (`writing/repository.py:update_status`,
   `writing/contracts.py:140`) emits nothing.
4. **The listener module imports and registers cleanly.** `wiki/listeners.py:36` reads
   `except ValueError, TypeError:` — this is **valid Python 3.14** syntax:
   [PEP 758](https://peps.python.org/pep-0758/) (shipped in Python 3.14, the project's runtime)
   permits dropping the grouping parentheses for multiple exception types, so the bare form is
   equivalent to `except (ValueError, TypeError):`. The module imports and the lifespan registers
   `WikiEventListener` without error. **§7 correction (verified):** an earlier version of this
   point claimed a Py2 `SyntaxError` that prevented import — that diagnosis was **disproven by an
   AST parse + runtime import test on the 3.14 interpreter**. Adding the parentheses is purely
   cosmetic; both forms are valid. (The staleness gap is explained entirely by points 1–3 and 5
   below — the missing producers — not by an unimportable listener.)
5. The only working staleness path is **manual** refresh (`wiki/router.py` →
   `APIWikiService.mark_all_stale` → repo). `CURRENT_STATE.md` lists only `embed_source` and
   `generate_band_summary` as active in-process tasks — the wiki generate tasks are not among them.

**Conclusion:** Option A is a deliberate WIKI-001 follow-up, not aspirational cleanup. Wiring the
producers (a) closes the correctness gap, (b) restores the documented UX, (c) turns the dormant
listener into a live consumer again. The fix stays **within ADR-080's in-process boundary**
(producers fire in-process handlers, not queue tasks).

### Alternatives considered

- **Option B — Remove the dormant subscriptions + orphaned enum + correct the docs to
  manual-refresh-only.** *Rejected.* This was the Round-1 choice. It is the smaller code change,
  but it **does not close the correctness gap**: it accepts that an entity edit leaves the
  summary at `fresh` with old content, served as truth with no fallback. Round 1 classified the
  consequence as a "documented-UX downgrade"; the deeper read shows it is a silent staleness bug.
  Removing the listener is also a *misdiagnosis* of §7: §7 forbids **dormant code that looks like
  a feature** — the fix is to make the code *live and correct*, not to delete the feature it
  promised. The Product Owner confirmed automatic regeneration is the intended behaviour, so the
  right move is to deliver it, not to retract it. (The git history + this section preserve
  Option B's analysis for any future re-evaluation.)
- **Option A — Re-wire producers against the in-process `EventPublisher`.** *Chosen.* Closes the
  correctness gap, restores WIKI-001 intent, respects ADR-080 (in-process, no Redis, no TaskIQ).
  The scope is bounded: three producer sites + one constructor wiring + a regression test. The
  listener code and tasks already exist and are transport-independent (they take a
  `wiki_service_factory`) — they become live consumers again. (An earlier version of this scope
  listed a `listeners.py` `SyntaxError` fix; that was disproven — see the §7 correction above.)

### `WIKI_SYNC_REQUESTED` enum — decision: remove it

The orphaned `WIKI_SYNC_REQUESTED` member (`packages/core/narrare_core/events/types.py:43`) had
its producer (`_publish_wiki_sync_event`) and consumer (`on_wiki_sync_requested`) removed in
PR #157. **Option A does not re-introduce either** — the three granular events
(`kb.entry.updated` / `chapter.finalized` / `wiki.prompt.changed`) fully cover the regeneration
triggers. `WIKI_SYNC_REQUESTED` therefore stays orphaned under Option A too. Per §7, orphaned
domain vocabulary that *looks* like a supported event is misleading → **remove it** (drop the
member + ratchet the count assertion in `tests/unit/core/events/test_event_types.py`). This is a
code change executed by the Core specialist; it needs no ADR (no contract/pattern change — a dead
enum value is removed).

### Sustainability check

1. *Correct in 3 months?* Yes — entity/chapter/prompt changes regenerate summaries in-process;
   the served summary always reflects the latest source. No silent staleness.
2. *Hard-to-undo coupling?* None — producers publish to the existing `EventPublisher` Protocol;
   a multi-worker future (per ADR-080 Review Trigger) re-plugs the bus at the Protocol without
   touching producers.
3. *Simplest correct solution?* Yes — re-uses the existing listener, tasks, factory, and
   `EventPublisher`. No new abstraction, no Redis, no TaskIQ.
4. *Understandable to next dev?* Yes — the chain matches the WIKI-001 "How it works" diagram and
   the (revised) banner; the ADR-080 in-process boundary is explicit.

### Compliance

- **ADR-080** ✅ — producers fire in-process handlers; no Redis, no TaskIQ, no broker.
- **ADR-022 (WIKI-001)** ✅ — restores the documented auto-regeneration design intent.
- **RULE-06** ✅ — producers are thin "emit event" seams at the lifecycle transition; the
  listener/tasks/repo each keep one responsibility (see handoff for the publish-point placement
  decision).
- **RULE-07** ✅ — dependency direction unchanged (router → service → repo); Core publishes via
  the injected bus Protocol, API producers publish via the in-process `EventPublisher`.
- **RULE-08** ✅ — the `EventPublisher` is the single in-process event adapter; no external broker.
- **RULE-11** ✅ — producer publish is non-blocking and logged; listener already swallows handler
  failures without propagating (graceful degradation — summary stays `pending`, raw-data fallback
  active).

### Implementation handoff → Core specialist

See the **HANDOFF** block at the bottom of this file.

---

> **Status:** ✅ Resolved (2026-08-08) — **Option A**: re-wire producers for
> `kb.entry.updated` / `chapter.finalized` / `wiki.prompt.changed` against the in-process
> `EventPublisher` (closes the silent staleness gap; restores WIKI-001 intent; ADR-080
> in-process boundary respected). Remove the orphaned `WIKI_SYNC_REQUESTED` enum member. (The
> `listeners.py` `SyntaxError` previously listed here was **disproven** — the
> `except ValueError, TypeError:` line is valid Python 3.14 per PEP 758; see §7 correction.)
> Option B retained as the rejected alternative (leaves the correctness gap open).

### Known scope edge / Follow-up (deferred — not a blocker for Option A)

Restoring a wiki-prompt *revision* (`restore_revision` → `self._core.save_override`) does **not**
publish `wiki.prompt.changed` (that publish lives only in `save_override_recorded`), so a revision
restore won't auto-trigger wiki regeneration. Producer #3 was scoped to the prompt-override *save*
path, so this edge was intentionally left. Deferred follow-up, not a blocker for Option A.

---

## HANDOFF → Core specialist

> **Spec:** This question file (Q-016, Option A) + WIKI-001 + ADR-080 + ADR-022.
> **No ADR** — executes the existing in-process pattern; no new dependency/pattern/RULE-XX
> exception. **No contracts change** — the `EventPublisher` already exposes `subscribe`/typed
> dispatch; `DomainEvent`/`EventType` already exist. This is producer wiring + a bug fix + a dead
> enum removal.

### Goal
Turn the dormant `WikiEventListener` subscriptions into LIVE consumers again by wiring the three
producers against the in-process `EventPublisher` the lifespan already creates
(`app.state.wiki_event_publisher`). Close the silent staleness gap: entity edit → summary marked
stale → regenerated.

### Architecture (RULE-06 / RULE-07 / ADR-080)

**All three producers live in the API layer and publish to the single lifespan `EventPublisher`.**
This keeps Core free of the API publisher (RULE-07) and respects ADR-080 (in-process dispatch,
no Redis, no TaskIQ).

```
kb entry update   ─→ KBService.update()          ──publish("kb.entry.updated")──→ EventPublisher
chapter → final   ─→ writing status→final path   ──publish("chapter.finalized")──→ EventPublisher
wiki prompt save  ─→ prompts save_override path  ──publish("wiki.prompt.changed")─→ EventPublisher
                                                          │ (in-process, ADR-080)
                                                          ▼
                                          WikiEventListener.{on_kb_entry_updated,
                                            on_chapter_finalized, on_wiki_prompt_changed}
                                                          │
                                                          ▼
                                          wiki/tasks.run_wiki_*  (existing, transport-independent)
```

**Publish-point placement (RULE-06 decision):**
- `kb.entry.updated` — publish from **`KBService`** (the lifecycle owner), NOT from
  `EmbeddingHookManager`. Rationale: `EmbeddingHookManager` is named/responsible for *embedding*
  dispatch; adding domain-event publishing there is a RULE-06 dual-responsibility stretch with a
  misleading class name. `KBService` already orchestrates the update (it calls the embedding hook
  + lifecycle dispatcher) and is the natural owner of "an entity changed". Thread the
  `EventPublisher` into `get_kb_service` (`kb/dependencies_core.py`) from `app.state`.
  *(The Round-2 brief flagged "EmbeddingHookManager constructed without EventPublisher" as the
  broken link — the link IS broken, but the RULE-06-clean fix-point is `KBService`, one hop up the
  same call chain. Confirm the exact publish call-site where `embedding_hooks.on_entry_updated()`
  is invoked.)*
- `chapter.finalized` — publish from the chapter **status→`final`** transition
  (`writing/repository.py:update_status` is the repo seam; the service that calls it is the
  publish point). Emit only on the transition INTO `final`, not on every status write.
- `wiki.prompt.changed` — publish from the **API prompt-override save path**
  (`prompts/service.py:save_override` or `history_service.py:save_override_recorded`), only when
  the overridden prompt is in the `wiki` category. Do NOT re-route Core's existing
  `core/wiki/service.py` publish to the API publisher (that would cross Core→API, RULE-07). Leave
  the Core `NullEventBus` publish as a harmless no-op, or remove it if it is now fully superseded
  (specialist's call — keep the `core/wiki/test_service.py:251` assertion honest either way).

**Wiring the publisher to the services:** the lifespan stores the publisher on
`app.state.wiki_event_publisher`. The API service factories resolve it from `app.state` via the
`Request` (the existing `app.state` access pattern used by `bind_writing_session_singletons`).
The `EventPublisher` constructor signature does not change — services receive it as a dependency
(typed against the existing publisher; consider a thin `Protocol` if one does not exist, but do
NOT over-engineer — the concrete `EventPublisher` is fine for an in-process single-user app).

### Must-fix bugs (found during §7 verification — fix while making the listener live)
1. ~~**`wiki/listeners.py` `SyntaxError`:** `except ValueError, TypeError:` was claimed to be
   Python-2 syntax that prevents import.~~ **Disproven — resolved as not-a-bug.** The line is
   valid Python 3.14 syntax ([PEP 758](https://peps.python.org/pep-0758/) allows dropping the
   grouping parentheses for multiple exception types); the module imports and the listener
   registers cleanly (verified by AST parse + runtime test on the 3.14 interpreter). See the §7
   correction above. Adding the parentheses is cosmetic only.

### Enum cleanup
2. **Remove `WIKI_SYNC_REQUESTED`** from `packages/core/narrare_core/events/types.py:43` (orphaned
   under Option A too — no producer, no consumer). Ratchet the count assertion in
   `tests/unit/core/events/test_event_types.py`. Keep `KB_ENTRY_UPDATED`, `CHAPTER_FINALIZED`,
   `WIKI_PROMPT_CHANGED` (now live).

### Producer details
3. Construct the payloads the listener already decodes (see `WikiEventListener`):
   - `kb.entry.updated` → `{entity_id, novel_id}`
   - `chapter.finalized` → `{chapter_id, novel_id}`
   - `wiki.prompt.changed` → `{novel_id?, prompt_version}` (the listener tolerates a missing
     `novel_id` only for prompt-change — verify the producer supplies what the listener needs; if
     `wiki.prompt.changed` must mark a *specific* novel stale, the prompt-save path must resolve
     `novel_id` or the listener must mark-all across novels — **clarify this with the Coordinator
     if the prompt save has no novel context**).
4. Publish is **non-blocking and logged** (RULE-11): wrap in try/except, log on failure, never
   let a publish failure abort the user's save (mirror `EmbeddingHookManager`'s non-blocking
   pattern). Dispatch is synchronous-in-process via `_dispatch`, so prefer `asyncio.create_task`
   for the downstream LLM generation the listener triggers — **verify** the listener/tasks path
   does not block the request (the tasks use a fresh session via the factory; confirm they are
   awaited off the request path, consistent with ADR-080's `_INFLIGHT_TASKS` GC-guard pattern in
   `embedding_hooks.py`).

### Test plan (closes the correctness gap — the regression that proves the fix)
- **Primary regression:** entity edit → `WikiSummary` for that entity transitions to `stale` (or
  is regenerated to `fresh` with new content) → on the next context assembly the served summary
  reflects the edit (NOT the old `fresh` content). This is the exact gap; assert it end-to-end.
- Unit: each producer publishes the right event type + payload (FakePublisher spy).
- Unit: `_uuid_from_payload` round-trips valid/invalid payloads (the
  `except ValueError, TypeError:` clause is valid Python 3.14 per PEP 758 — no syntax fix needed).
- Integration: `kb.entry.updated` → `run_wiki_generate_entity` runs (TestModel) → summary
  persisted `fresh`; `chapter.finalized` → chapter summary generated; `wiki.prompt.changed` →
  `mark_all_stale` runs.
- `just check` green (architecture gate — the enum removal may trip a count checker; ratchet the
  baseline with a comment pointing here). `just test` green. Confirm no remaining reference to
  `WIKI_SYNC_REQUESTED`.

### Risks / trade-offs (accepted)
- In-process LLM generation on every entity edit / chapter finalize has a latency/cost footprint
  for a single-user local-first app (often a slow local LLM). Mitigated by: the listener's
  existing debounce window (`WikiEventListener._is_debounced`), the tasks' idempotency
  (skip-if-fresh) + retry/backoff, and graceful degradation (failure → status stays `pending` →
  raw-data fallback). This is the WIKI-001 design trade-off the Product Owner accepted.
- If generation is too aggressive, a future tweak can split "mark stale" (cheap, always) from
  "regenerate" (debounced) — but that is out of scope for Option A; ship the full chain first.
