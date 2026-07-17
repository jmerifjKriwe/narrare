# CR-AUFG-03-10 / 03-11 — mem0-Loop Design Note

> **Type:** Design note (contract-level), NOT an ADR.
> **Author:** Architecture Specialist
> **Date:** 2026-07-17
> **Branch:** `chore/review-06-summary-resolution-fixes`
> **Status:** Contracts written (03-10); 03-11 closed as already-satisfied (no code).
> **Related:** ADR-033 (mem0 governance), ADR-055 (character voice),
> CR-AUFG-07-26 (per-novel DB dismiss), ADR-045 Decision 8 (memory privacy),
> CONSTRAINTS.md RULE-02/03/04/06/07/08/11/22.

This note records the two architectural calls for the cr-06 mem0-loop tasks so
the Core/Backend specialists can implement against a fixed contract without
re-deriving the decisions.

---

## CR-AUFG-03-10 — Consistency-Feedback-Loop zu mem0

### Decision: contract-only (no ADR)

No new ADR is required. Reasoning:
- **No new external dependency** — mem0 is already governed by ADR-033 and
  confined to `core/memory/` (RULE-08).
- **No new prompt surface** — suppression is pure backend filtering
  (RULE-02/02b untouched). No new template variable, no `{{...}}` growth.
- **No cross-module boundary change** — the feature stays inside
  `kb/` (API) + `core/memory/` (Core). Dependency direction is unchanged
  (API → Core, RULE-07).
- **The pattern is already established** by `FeedbackService` /
  `SessionMemoryService` (dual-store best-effort mem0 forward). 03-10 is the
  same pattern applied to a new memory kind.

An ADR would be warranted only if we changed mem0 governance or introduced a
new store. We do neither. RULE-03 contract + this note is sufficient.

### Root cause (2× Why)

- **Symptom:** Re-running a consistency check resurfaces findings the user
  already reviewed and dismissed, even after the 07-26 dismiss.
- **Why?** The 07-26 DB dismiss suppresses by *exact fingerprint*
  (`description::entity_names`). If the LLM rephrases a finding's description
  across runs, the fingerprint shifts and the exact-match suppress misses it.
- **Why (deeper)?** The current suppress mechanism is *structural* (an exact
  string key), not *semantic*. Two findings with identical meaning but
  different wording are not recognised as the same finding.
- **Design:** Add a mem0 learning layer that stores each dismissal as a
  semantic memory and, on the next check, retrieves near-duplicate dismissals
  by embedding similarity (mem0's pgvector backend). This sits **on top of**
  the 07-26 exact-fingerprint layer — it does not replace it.

### Alternatives considered

1. **mem0 semantic layer (CHOSEN).** Stores dismissals in mem0 scoped to
   user+project; retrieves by similarity. Pros: catches rephrased findings,
   reuses the established mem0 pattern, local-first (ADR-033). Cons: extra
   mem0 round-trip on each check (mitigated: best-effort, cached, async).
2. **Expand the 07-26 DB table with a description column + pgvector index and
   do SQL similarity.** Pros: no mem0 dependency. Cons: re-implements a
   semantic memory engine that mem0 already provides (violates ADR-033's
   "don't rebuild mem0" rationale, Option D rejected there); spreads
   dismissals across two DB stores with different semantics; requires a new
   migration + embedding pipeline in the API layer. Rejected.
3. **Cross-novel user-scoped learning only (no per-novel).** Rejected as the
   *primary* scope: consistency findings reference one novel's entities/lore,
   so a false positive in novel A is rarely a false positive in novel B.
   Cross-novel learning remains a future retrieve-filter change (the record
   carries `user_id`, so no data migration is needed to broaden the filter).

The mem0 layer wins because it adds the genuinely-missing capability
(semantic matching) without duplicating infrastructure, and it is the
governed home for cross-session learning (ADR-033).

### Scope decision: user-scoped vs novel-scoped

**Storage:** user+project (mirrors `FeedbackCollector` /
`SessionMemoryCollector`: `user_id` → mem0 `user_id`, `project_id` → mem0
`agent_id`). **Retrieval (v1):** scoped to user+project (within-novel
semantic suppression). This is the safe, correct-first scope. Cross-novel
learning is intentionally deferred — see the protocol docstring.

### Privacy

Only the finding *description* (a structural analysis output referencing KB
entities) and linkage metadata are recorded — never raw draft prose. This
matches the `SessionMemoryService` structural-metadata rule (ADR-045 Decision
8, RULE-22). The user's own worldbuilding analysis on a local-first store is
in-scope.

### Contract (written)

- `packages/core/narrare_core/memory/protocols.py` →
  `ConsistencyFeedbackCollector` Protocol (`record_dismissal`,
  `find_similar_dismissals`).
- `packages/core/narrare_core/memory/consistency_models.py` →
  `ConsistencyDismissalRecord` (structured input) + `DismissalMatch`
  (scored retrieval result).
- Public API exported from `packages/core/narrare_core/memory/__init__.py`.

### Integration points (for Core/Backend specialists)

| Hook | File | Function | What to do |
|------|------|----------|------------|
| **Store** (Backend) | `apps/api/narrare/kb/dismissed_service.py` | `DismissedFindingService.dismiss_finding` | After `self._repo.dismiss(...)` succeeds, build a `ConsistencyDismissalRecord` from the request + finding context and call `feedback_memory.record_dismissal(...)`. Inject the memory as an optional ctor dep (`feedback_memory: ConsistencyFeedbackCollector \| None = None`) — mirrors the `session_memory` injection in `writing/service.py`. Best-effort: never let a mem0 failure break the DB dismiss. |
| **Retrieve+suppress** (Backend) | `apps/api/narrare/kb/consistency_service.py` | `KBConsistencyService.check` | After `all_issues` is built (step 5/6, before cache.set), if `self._feedback_memory` is present, for each issue call `find_similar_dismissals(finding_description=issue.description, ...)` and filter/mark issues above threshold. Inject `feedback_memory: ConsistencyFeedbackCollector \| None = None`. **Recommended policy:** filter out suppressed issues + add a `suppressed_count` to the response (auditable, UI can show "N known false positives hidden"). Do NOT grow the prompt (RULE-02). |
| **Service impl** (Core) | `packages/core/narrare_core/memory/consistency_feedback_service.py` (NEW) | `class ConsistencyFeedbackService` | mem0-backed impl of the protocol. Follow `feedback_service.py`/`session_memory_service.py` exactly: ctor takes `mem0_client`; `record_dismissal` translates the record to memory text + metadata and forwards (best-effort, RULE-11); `find_similar_dismissals` calls `mem0.search(...)` scoped to `user_id`+`agent_id` and maps results to `DismissalMatch`. |
| **DI wiring** (Backend) | `apps/api/narrare/kb/dependencies.py` (or equivalent kb deps file) | `_get_consistency_feedback_memory_instance()` | Singleton factory mirroring `writing/deps_writing.py::_get_session_memory_instance()` exactly (mem0 availability check → provider detect → `create_memory_client_sync` → `NullMemoryClient` guard → return `None` on any failure). |

### Sustainability check

1. *Correct in 3 months?* Yes — semantic suppression is additive on top of
   exact-match; neither layer invalidates the other.
2. *Hard-to-undo coupling?* None — optional injected dep; `None` = disabled
   (graceful degradation, RULE-11).
3. *Simplest correct solution?* Yes — reuses mem0 (governed) instead of
   rebuilding similarity; reuses the dual-store best-effort pattern.
4. *Design intent clear?* Yes — protocol docstring + this note document
   scope, privacy, and the relationship to the 07-26 exact-fingerprint layer.

### RULE-XX compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-02/02b | ✅ | Pure backend filtering; no prompt surface growth. |
| RULE-03 | ✅ | Protocol + data models written before service impl. |
| RULE-04 | ✅ | New service in its own file (`consistency_feedback_service.py`); the two new consistency models live in their own file (`consistency_models.py`), split out of `models.py` so that `models.py` stays under the 200-line hard limit. |
| RULE-06 | ✅ | Store hook stays in dismiss service; suppress hook stays in consistency service; mem0 logic stays in Core. One responsibility each. |
| RULE-07 | ✅ | API → Core only; Core never imports `apps/`. |
| RULE-08 | ✅ | mem0 confined to `core/memory/`. |
| RULE-11 | ✅ | All mem0 ops best-effort; never break DB dismiss or consistency check. |
| RULE-22 | ✅ | Stores structural analysis output, not draft prose (ADR-045 D8). |

---

## CR-AUFG-03-11 — Character Voice Memory in mem0

### Decision: NO CONTRACT, NO ADR, NO CODE — already satisfied

**Recommendation: close 03-11 as "already implemented via ADR-055 KB persistence."
mem0 is redundant for character voice. Do not add mem0 machinery.**

### Root-cause test (the load-bearing question)

The cr-03 task premise states: *"Voice-Patterns werden nicht in mem0
persistiert, sodass jede Session das Profil neu erstellt"* ("voice patterns
are not persisted, so every session re-profiles from scratch").

**This premise is false.** Verified against the code:

1. ADR-055 (✅ Accepted + Implemented 2026-06-29) defines the storage
   contract: `VoiceAnalysis` (descriptive + `VoiceMetrics`) persists to
   `KBEntity.metadata["speech"]["voice_analysis"]`.
2. `apps/api/narrare/analysis/character_voice_kb_writer.py::
   persist_voice_analysis()` writes the derived profile to the KB on **every**
   profiling run and bumps `updated_at`.
3. `CharacterVoiceService.analyze()` calls `persist_voice_analysis()` in step 7
   unconditionally — persistence is not optional.
4. The **writing path reads the KB**, not a live profiler:
   `build_character_voice_profile()` → `get_speech_data()` reads
   `metadata["speech"]` → renders into `{{character_voice_profiles}}`.
   It does **not** re-profile. The only live profiling is ANAL-008, an
   explicit user action.
5. Freshness is already tracked: `profiles/_freshness.py::is_stale()` +
   the `updated_at` bump. The voice-check path (ADR-057) reads
   `voice_metrics` via `_extract_voice_metrics()`.

So the cross-session persistence that 03-11 asks for **already exists** in the
KB. The "re-profile from scratch each session" cost does not occur in
generation — generation always reads the persisted KB profile.

### Why mem0 is the wrong tool here

- **mem0 stores natural-language memories for semantic retrieval**, not
  structured `VoiceAnalysis` objects. Storing a structured profile in mem0
  would require serialize-to-text → embed → retrieve → deserialize-back,
  which is lossy and pointless when the KB already holds the authoritative
  structured object.
- **Cross-novel voice sharing is semantically wrong.** A character in novel A
  and a same-named character in novel B are different characters; sharing
  voice profiles across novels would inject the wrong voice. mem0's value
  (cross-context generalisation) is actively harmful here.
- **No problem is solved.** If a profile was never generated (user never ran
  ANAL-008), neither KB nor mem0 has one — mem0 cannot materialise a profile
  that was never computed. If it was generated, the KB already has it.

### Alternatives considered

1. **No-op / close as already-satisfied (CHOSEN).** ADR-055 KB persistence is
   the cross-session voice memory. Document and close.
2. **mem0 cache of derived profiles (rejected).** Redundant with KB; wrong
   storage shape; harmful cross-novel generalisation risk. See above.
3. **KB-native freshness policy (only if a real gap is found later).** If a
   future UX problem surfaces ("stale voice profile degrades generation"),
   the correct fix is a KB-native freshness policy: when
   `is_stale(updated_at)` and the user is generating, surface a soft
   "re-profile" nudge — NOT a mem0 concern. `is_stale()` already exists; this
   is at most a UI/wiring task, deferred until a concrete need appears.

### What the Backend/Core specialists should do for 03-11

**Nothing.** If asked, point at:
- `apps/api/narrare/analysis/character_voice_kb_writer.py::persist_voice_analysis`
- `packages/core/narrare_core/profiles/_voice_extraction.py::
  build_character_voice_profile`
- ADR-055 Decision 1 + Consequences.

And mark 03-11 `resolved / already-implemented` with this note as evidence
(architectural-discipline §7: verify reality, not claims — the persistence
path is read end-to-end above).

### Sustainability check

1. *Correct in 3 months?* Yes — closing avoids building redundant machinery
   that would have to be torn out.
2. *Hard-to-undo coupling?* None — we add nothing.
3. *Simplest correct solution?* Yes — "do nothing" is correct because the
   requirement is already met.
4. *Design intent clear?* Yes — this note records why.

---

## Implementation order (handoff)

1. **Core** — `ConsistencyFeedbackService` in
   `core/memory/consistency_feedback_service.py` (follows
   `feedback_service.py`). Unit tests with `NullMemoryClient` + a fake mem0.
2. **Backend** — DI singleton in kb deps (mirror
   `writing/deps_writing.py::_get_session_memory_instance`).
3. **Backend** — store hook in `dismissed_service.py::dismiss_finding`
   (optional injected dep, after DB persist).
4. **Backend** — retrieve+suppress hook in `consistency_service.py::check`
   (optional injected dep, after issues built). Add `suppressed_count` to
   `ConsistencyCheckResponse` (schema bump — coordinate with frontend on the
   field name, RULE-17).
5. **03-11** — no implementation. Close the audit entry.
