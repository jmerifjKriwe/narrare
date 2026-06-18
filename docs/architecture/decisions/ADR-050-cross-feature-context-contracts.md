# ADR-050 — Cross-Feature Context Contracts (KB Envelope, Ref Lifecycle, kb_pinned Governance)

> **Status:** ✅ Accepted
> **Date:** 2026-06-18
> **Deciders:** Architecture Specialist
> **Supersedes:** —
> **Related:** ADR-022 (LLM Wiki), ADR-025 (Feature Adoption), ADR-037 (Prompt Surface Manifest), ADR-040 (KG/Voice SSOT), ADR-044 (Staged Consistency), CONSTRAINTS.md RULE-03/RULE-06/RULE-22, CR-AUFG-04
>
> ---
>
> **Ratification note (2026-06-18):** Ratified ✅ Accepted by the
> Architecture Specialist ahead of Backend-Phase C2. Gate review
> confirmed:
> 1. **Contracts exist on disk** (graph was stale; verified via file
>    reads): `KBContextEnvelope`/`RenderedKBContext`/`ProvenanceField`/
>    `OmissionReason` in `context/_kb_envelope.py` (re-exported from
>    `context/contracts.py`); `KBEntityLifecycleObserver`/
>    `CrossFeatureRefIndex`/`RefIntegrityIssue`/
>    `ContradictionPromotionPolicy`/`TimelineRefConsumer`/
>    `StoryboardRefConsumer`/`ChapterFrontmatterRefConsumer` in
>    `context/integration_contracts.py`; `VoiceProfileConsumer` in
>    `profiles/contracts.py`.
> 2. **Variable registry (P1-D) applied**: `kb_pinned`, `kb_timelines`,
>    `kb_systems` in `SYSTEM_VARS` + `CURATED_KB` classification;
>    `character_voice_profiles` reclassified `LABEL_REQUIRED` /
>    `PROJECT_WRITING_PROFILE` (aligns with ADR-040 §1).
> 3. **Tests present & coherent**: `tests/unit/core/context/
>    test_kb_envelope.py`, `test_integration_contracts.py`,
>    `tests/unit/core/profiles/test_contracts.py` cover structural
>    Protocol compatibility, immutability/hashability, disjoint
>    promotion sets, and the generation/checking-same-provider contract.
> 4. **Additive / non-breaking**: all four decisions are additive —
>    new Protocols, no DB column changes (hard-delete policy
>    preserved), no ADR-040 supersede, single classification tightening
>    is a deliberate RULE-22 alignment.
> 5. Each decision has a 5-whys root cause, ≥3 evaluated alternatives,
>    and a sustainability check.
>
> Caveat: test *execution* was permission-blocked in this session
> (pytest not on the bash allow-list); tests were verified statically
> (read). Test-green confirmation is tracked under the Gate 12
> "✅ Implemented" status, separate from this acceptance.
> The ADR remains ✅ **Accepted** (decision in effect) but NOT yet
> ✅ Implemented (Phase C/D pending per Gate 12).

---

## Context

### Triggering review

CR-AUFG-04 surfaced four cross-feature coherence gaps in the
KB-context pipeline. This ADR specifies the contracts that close
those gaps. Each gap is documented with its **root cause** (not its
symptom), at least **two alternatives**, and an explicit
**sustainability check**.

### Gap P1-A — KB Context Envelope (CR-AUFG-04-01)

**Symptom:** Provenance metadata on `KBContextEntry` (source,
evidence, confidence, review_status, freshness) and `KBEntity`
(source, review_status, confidence, status) is silently dropped by
every render path.

**Root cause (5-whys):**

1. *Why is provenance lost?* The renderers (`PromptContext._format_kb_entries`,
   `writing/_helpers.format_entities`, `writing/context_wiki.format_entities_with_wiki`,
   `writing/_tier3_processor.apply_tier3`, `writing/_voice_profiles.extract_voice_profiles`)
   emit only `### Type: Name\nContent`.
2. *Why do they emit only that?* Each renderer was written when
   provenance fields did not yet exist on the source data classes.
3. *Why weren't they updated when provenance was added?* No contract
   forced them to. `KBContextEntry` got `source/evidence/confidence/review_status/freshness`
   in CR-AUFG-04 with a comment "track data provenance for
   cross-feature coherence" — but there is no Protocol that says
   "every renderer of this type must preserve or explicitly omit
   these fields."
4. *Why is no Protocol enforcing this?* RULE-22 §1, §2 require shared
   data identification and change/deletion behaviour per shared
   source, but the rule does not name a concrete interface for the
   rendering boundary.
5. *Why does that matter?* Because the LLM cannot reason about
   provenance it never receives, and downstream audit tooling
   (Context Inspector, CONS-001 evidence) cannot trace which facts
   were authoritative vs inferred. ADR-044 fixed this *for the
   Timeline→Consistency consumer* via `TimelineEventEnvelope`. Every
   other consumer is still lossy.

### Gap P1-B — Storyboard ↔ KB ↔ Timeline ref lifecycle (CR-AUFG-04-06)

**Symptom:** When a KB entity is renamed, deprecated, or hard-deleted,
no consumer is notified. JSON `{id, name}` refs in
`timeline_events.character_refs` and `timeline_events.location_ref`
become silently stale. Chapter frontmatter refs become dangling.
Storyboard planned-beats free text references become stale.

**Root cause (5-whys):**

1. *Why do refs become stale?* No cascade from KB lifecycle changes
   to consumers.
2. *Why no cascade?* `KBRepository` exposes only `update()` and
   hard `delete()`. There is no `rename()`, `deprecate()`, or
   tombstone mechanism.
3. *Why no rename/deprecate?* The original KB design assumed
   entities are immutable in identity (slug is unique, name is
   display). Rename was treated as "update the name field."
4. *Why was that assumption wrong?* Because consumers store hybrid
   JSON `{id, name}` to avoid an extra lookup at read time, and
   free-text references (frontmatter, planned beats) store names
   only. Both classes of consumer assume the name is stable.
5. *Why does that matter?* Because without an explicit lifecycle
   contract, each consumer invents its own staleness handling (or
   none). Timeline's `enrich_timeline_envelopes` does name-based
   matching and reports `unknown` — but that's only one consumer
   and only at consistency-check time, not at write time.

ADR-044 partially closed this for the **Consistency consumer**: the
`kb_entity_status` field on `TimelineEventEnvelope` reports
`active/deprecated/unknown`. But:

* It is read-side only (consumed at check time, not at write time).
* It covers Timeline refs only, not Chapter frontmatter or
  Storyboard planned beats.
* It cannot distinguish `unknown` (lookup miss) from `deleted`
  (hard-deleted without tombstone) because the KB has no tombstone
  concept.

### Gap P1-C — Voice Profile consumer SSOT (CR-AUFG-04-09)

**Symptom:** `VoiceProfileProvider` Protocol exists (ADR-040 §1
Layer 1) but has **0 callers** in the codebase.
`WritingContextAssembler.assemble()` line 200 still calls
`extract_voice_profiles(entities)` directly via the backward-compat
shim in `writing/_voice_profiles.py`.

**Root cause (5-whys):**

1. *Why does the assembler bypass the provider?* ADR-040 Layer 4
   ("Wire WritingPipeline sub-pipelines") was specified but not
   implemented as a discrete follow-up.
2. *Why not?* The Layer 1 module shipped (`core/profiles/` exists
   with `assembly.py`, `contracts.py`, `models.py`,
   `_voice_extraction.py`, `_freshness.py`), and the ADR was marked
   ✅ Accepted on that basis. The ADR's own Implementation Plan
   lists Layers 4–7 as subsequent work, but no follow-up ADR or
   feature spec captured that work.
3. *Why did the ADR close without Layer 4?* ADR-040's Gate 12
   verification was scoped to "P2 architecture spec complete"
   (Layer 8 docs) — not to consumer wiring.
4. *Why was consumer wiring deferred?* Because at the time,
   `extract_voice_profiles` already worked, and the
   backward-compat shim made the gap invisible.
5. *Why does that matter now?* Because WRITE-010 (Voice Consistency
   Checker) and ANAL-008 (Character Voice Profiling) will reach for
   voice data via the same shortcut, duplicating freshness policy
   at every call site. The SSOT exists in code but not in
   consumption.

### Gap P1-D — `kb_pinned` governance (CR-AUFG-04-12)

**Symptom:** `WritingContext` produces a `kb_pinned` variable.
`variable_registry.SYSTEM_VARS` does not list it.
`variable_taxonomy._classification_overrides` does not classify it.
The Prompt Surface Manifest (ADR-037) has no entry for it.

**Root cause (5-whys):**

1. *Why is `kb_pinned` unregistered?* It was added to
   `WritingContext.to_prompt_variables()` before RULE-22 §4
   (variable registration) was enforced.
2. *Why wasn't it added when RULE-22 landed?* The ratcheted
   baseline absorbed the existing gap rather than blocking.
3. *Why was it absorbed?* Because the baseline tracks "legacy gaps
   with an owner and cleanup target" — but no owner or target was
   recorded for `kb_pinned`.
4. *Why no owner?* Because the variable is producer-only in
   practice: no bundled prompt template uses `{{kb_pinned}}`.
5. *Why does that matter?* Two failure modes. (a) If a future
   template uses `{{kb_pinned}}`, it will be flagged as
   unregistered and block CI; the team will not know whether to
   register it or remove the producer. (b) The same gap exists for
   `kb_timelines`, `kb_systems`, and `character_voice_profiles`
   (which is in `SYSTEM_VARS` but not in
   `_classification_overrides` despite ADR-040 §1 declaring it a
   `PROJECT_WRITING_PROFILE` variable). The ambiguity is
   contagious.

### Gap P2 — i18n tone drift (CR-AUFG-04-13)

**Symptom:** Bundled `universal/{de,fr}/system.md` prompts mix
formality registers within the same file. DE: "Du bist Narrares
Fähigkeit" (informal Du) vs "folgen Sie immer den
Autorenanweisungen" (formal Sie). FR: "Tu es la capacité" (informal
tu) vs "suivez toujours les instructions" (formal vous).

This is a **documentation/platform** task, not an architecture
decision. It is recorded here for cross-reference and dispatched
to the documentation backlog (see Phase D handoff).

### FIND-009 status clarification

**Old statement (now stale):** "Timeline not consumed by the
consistency pipeline; provenance lost."

**Verified current state (2026-06-18):**

* ADR-044 is ✅ Implemented (not Proposed). The code exists:
  `core/agents/fact_extractor_agent.py`, `core/agents/fact_extractor_types.py`
  (`ExtractedFact`, `TimelineEventEnvelope`,
  `FactExtractorProtocol`), `apps/api/narrare/consistency/timeline_envelope.py`,
  `apps/api/narrare/consistency/consistency_orchestrator.py`. INDEX.md
  and `docs/_shared/CURRENT_STATE.md` §53 confirm.
* The Consistency consumer (CONS-001) **does** consume Timeline data
  via `TimelineEventEnvelope` with full provenance. FIND-009 is
  resolved **for CONS-001**.
* FIND-009 is **not** resolved for other consumers:
  - Writing/Prompt context (`WritingContextAssembler`,
    `PromptContext._format_kb_entries`) still emits flat text.
  - KB↔Timeline/Storyboard ref lifecycle has no write-side cascade
    (Gap P1-B).
  - Generische temporal reasoning über Feature-Grenzen hinweg
    ist nicht Teil von ADR-044.

**Therefore:** FIND-009 is split into two findings:

* **FIND-009a (resolved):** Timeline→Consistency provenance
  preservation. Closed by ADR-044.
* **FIND-009b (open):** KB→Consumer ref lifecycle (rename,
  deprecate, delete, tombstone) across Timeline, Storyboard,
  Chapter frontmatter. Closed by this ADR's P1-B contract.

---

## Decision Drivers

- **RULE-03** — Contracts before implementation. The renderers and
  ref consumers exist; they need Protocols to bind to.
- **RULE-06** — One responsibility per file. Cross-feature ref
  lifecycle is its own concern, separate from KB CRUD.
- **RULE-07** — `core/` owns the vocabulary; Backend owns the
  enforcement.
- **RULE-22** — Cross-feature coherence gate. Every shared data
  source needs change/delete behaviour documented.
- **ADR-040 §1 Decision A** — Voice extraction must be a strategy
  behind the profile contract. Layer 4 wiring is the unfinished half.
- **ADR-044** — `TimelineEventEnvelope` is the precedent: structured
  IR beats compact text. The same pattern applies to KB context
  rendering.
- **Sustainability** — Each contract must hold when WRITE-010,
  ANAL-008, or a future feature adds another consumer.

---

## Decision 1 — KBContextEnvelope Protocol (closes P1-A)

### Options Considered

#### Option A — Centralised renderer with one wire format

Replace every renderer (`_format_kb_entries`, `format_entities`,
`format_entities_with_wiki`, `apply_tier3`, `extract_voice_profiles`)
with a single canonical `KBContextRenderer` that emits one wire
format (e.g. always XML-tagged blocks with all provenance fields).

**Pros:**

- Maximum uniformity — every prompt sees the same shape.
- Easiest to audit (one function to grep).

**Cons:**

- Breaks tier-specific optimisations (wiki-compressed summaries,
  pinned bypass, budget truncation cascade).
- Forces token-budget spend on provenance even in tier-1 immediate
  context where it is irrelevant.
- Violates the existing tier semantics documented in
  `WritingContextAssembler`.

#### Option B — Protocol with per-renderer accounting (CHOSEN)

Define `KBContextEnvelope` Protocol in `core/context/contracts.py`.
Each renderer becomes an implementation that returns
`RenderedKBContext(text, preserved_fields, omitted_fields, ...)`.
Wire formats stay tier-specific; what changes is that each renderer
must explicitly account for what it preserves or omits.

**Pros:**

- Preserves tier-specific formats (no regression).
- Forces explicit omission rationale (RULE-22 §1).
- Machine-readable audit trail — `omitted_fields` + `render_path`
  lets CI/tooling detect silent loss.
- Composable with ADR-044's `TimelineEventEnvelope` (which is
  already a high-fidelity instance of this Protocol).

**Cons:**

- More types (`RenderedKBContext`, `ProvenanceField`,
  `OmissionReason`).
- Each renderer must be migrated individually (incremental work).

#### Option C — Static CI checker only

Add a checker that scans renderers and fails CI if they don't
preserve provenance. No runtime Protocol.

**Pros:**

- No runtime overhead.
- Catches regressions.

**Cons:**

- Does not produce a runtime contract that consumers can rely on.
- Cannot express per-tier omission policy.
- Repeats the CR-03 anti-pattern of static-only gates.

### Decision

**Option B.** Protocol with per-renderer accounting. The Protocol
is in `packages/core/narrare_core/context/contracts.py`. Renderers
remain in their current modules (no cross-module move); each one
returns `RenderedKBContext`.

### Rationale

Option A's uniformity is bought at the cost of breaking existing
tier semantics — semantics that exist for good token-budget reasons
and that ADR-022 (LLM Wiki) specifically relies on. Option C cannot
express omission policy (a tier-1 immediate context legitimately
omits provenance; a tier-5 pinned context must not). Option B
captures the contract without prescribing the wire format, which
matches the existing precedent set by `TimelineEventEnvelope`.

### Sustainability check

1. *Correct in 3 months?* Yes. New consumers (WRITE-010, ANAL-008)
   implement the same Protocol; no special cases.
2. *Hard-to-undo coupling?* Reduced. Renderers stay where they are;
   the Protocol is additive.
3. *Simplest correct solution?* Yes. The Protocol is the smallest
   contract that closes the provenance-loss gap.
4. *Design intent clear?* Yes. `ProvenanceField` and
   `OmissionReason` are machine-readable literals; audit tooling
   can compare renderers deterministically.

---

## Decision 2 — Cross-Feature Ref Lifecycle Contracts (closes P1-B and FIND-009b)

### Options Considered

#### Option A — KB-side cascade: KBRepository gains rename/deprecate/tombstone methods that synchronously update every consumer's storage

**Pros:**

- Single source of truth for the cascade.
- Refs are always consistent immediately after the operation.

**Cons:**

- KB module now knows about Timeline, Storyboard, Chapter
  frontmatter storage shapes — violates RULE-05 (module boundaries
  are ownership boundaries) and RULE-07 (KB must not depend on
  consumers).
- Hard delete with synchronous cascade is fragile (one consumer
  failure rolls back the whole operation or leaves partial state).
- Does not match the existing precedent (ADR-044 chose read-side
  enrichment, not write-side cascade).

#### Option B — Observer Protocol + read-side ref index (CHOSEN)

Two contracts in `core/context/integration_contracts.py`:

* `KBEntityLifecycleObserver` — write-side hook. KB calls every
  registered observer on rename/deprecate/delete. Each observer
  adapts to its own storage shape.
* `CrossFeatureRefIndex` — read-side resolver. Consumers and the
  consistency pipeline ask "what is the current status of this ref?"
  and get `active/deprecated/unknown/deleted`.

Plus per-consumer specialisations
(`TimelineRefConsumer`, `StoryboardRefConsumer`,
`ChapterFrontmatterRefConsumer`) that document the consumer-specific
storage shape and policy (e.g. frontmatter is never auto-rewritten
because it is user-authored content per RULE-22 §7).

**Pros:**

- KB module stays free of consumer knowledge (RULE-07).
- Each consumer owns its storage shape and policy.
- Read-side index matches ADR-044's precedent
  (`enrich_timeline_envelopes` is a partial implementation).
- Write-side hook is async and tolerant — one consumer failure
  produces a `RefIntegrityIssue`, not a rollback.

**Cons:**

- Two contracts instead of one.
- Eventual consistency window between KB change and consumer update
  (mitigated: issues surface in the next consistency check).
- Observers must be registered at app startup (DI discipline).

#### Option C — Read-side only (no write hook)

Drop the observer; rely entirely on `CrossFeatureRefIndex` queried
at consistency-check time.

**Pros:**

- Simplest possible contract — one Protocol.

**Cons:**

- Stale refs persist in consumer storage indefinitely until a check
  runs.
- Cannot trigger user-visible warnings at write/edit time (e.g.
  "this chapter frontmatter references a deprecated entity").
- Rejects the symmetry with ADR-040 Decision 2 (which chose
  enricher + checker, not checker alone).

### Decision

**Option B.** Observer + read-side index. Hard delete remains hard
delete (no tombstone column added to KBEntry); consumers that need
tombstone semantics implement them in their own storage and emit
`RefIntegrityIssue(reason="deleted_ref_without_tombstone")` when
they detect a dangling ref.

### Rationale

Option A's synchronous cascade is seductive but creates the exact
coupling RULE-05 exists to prevent. Option C is too weak: it lets
stale refs fester until someone runs a check. Option B mirrors
ADR-040 Decision 2's pattern (runtime enricher + static checker)
and ADR-044's pattern (read-side enrichment via envelope), so the
codebase has one mental model for cross-feature ref integrity.

### Sustainability check

1. *Correct in 3 months?* Yes. New consumers register an observer
   at DI composition time; no KB changes.
2. *Hard-to-undo coupling?* Reduced. KB does not import consumer
   modules; consumers import only Core Protocols.
3. *Simplest correct solution?* Yes. Two Protocols cover write and
   read sides; per-consumer specialisations are documentation, not
   new types.
4. *Design intent clear?* Yes. Each observer documents its storage
   shape and rewrite policy in its docstring.

### Hard-delete policy

Hard delete stays hard delete. We deliberately do **not** introduce
a `KBEntry.deleted_at` column or tombstone row. Rationale:

* Tombstones grow unbounded and require GC policy.
* Consumers that need tombstone semantics (Timeline, future
  Storyboard ref-store) can implement their own marker.
* The contract surfaces `deleted_ref_without_tombstone` as an error
  issue so users see the consequence and can choose to remap or
  accept.

If user feedback shows hard-delete is too destructive in practice,
a follow-up ADR may introduce soft delete. This ADR does not
prejudge that decision.

---

## Decision 3 — Voice Profile Consumer Contract (closes P1-C)

### Options Considered

#### Option A — Migrate `WritingContextAssembler` to use `VoiceProfileProvider` directly, retire `extract_voice_profiles`

**Pros:**

- Cleanest end state.
- One code path.

**Cons:**

- Forces the assembler to depend on a provider instance via DI,
  changing the assembler's constructor signature (cascading test
  updates).
- Retiring the backward-compat shim breaks any out-of-tree caller.

#### Option B — Add `VoiceProfileConsumer` Protocol; bind generation and checking to the same provider instance per invocation (CHOSEN)

Define `VoiceProfileConsumer` in `profiles/contracts.py`. Both
generation (`WritingContextAssembler`,
`WritingPipeline` sub-pipelines) and checking (WRITE-010 future,
CONS-001 voice-related checks) go through a consumer bound to a
single provider per request scope.

The backward-compat shim `extract_voice_profiles` stays for now but
its docstring already says "New code should use
`ProfileAssembler` instead." This ADR makes that migration a
tracked item rather than a comment.

**Pros:**

- Does not force assembler constructor changes in this ADR.
- Establishes the contract WRITE-010 and ANAL-008 will need.
- Provider/consumer split matches ADR-040 §1's "strategy behind the
  contract" intent.

**Cons:**

- Two contracts (`VoiceProfileProvider`,
  `VoiceProfileConsumer`) instead of one.
- Migration of existing callers is incremental (see Phase C
  acceptance criteria).

#### Option C — Extend ADR-040 with a Layer 4 completion gate, no new Protocol

**Pros:**

- Minimal new surface.

**Cons:**

- ADR-040 Layer 4 was about wiring, not about a checking-side
  contract. WRITE-010 needs the checking projection
  (`assemble_for_checking` returns structured profiles, not text).
- Without a Protocol, the checking side will invent its own ad-hoc
  access pattern.

### Decision

**Option B.** Add `VoiceProfileConsumer` Protocol. This ADR does
**not** supersede ADR-040; it extends ADR-040 §1 with the consumer
half of the SSOT. ADR-040's status remains ✅ Accepted; this ADR
adds the Layer 4 contract that ADR-040's Implementation Plan
anticipated but did not name.

### Rationale

ADR-040's own Consequences section says: "All 6 WritingPipeline
variants that reference `character_voice_profiles` need updates to
use the new model." That work was scoped but never contracted. The
`VoiceProfileConsumer` Protocol is the contract that makes that
work enforceable. Without it, WRITE-010 will repeat the
`extract_voice_profiles` shortcut.

### Sustainability check

1. *Correct in 3 months?* Yes. WRITE-010 and ANAL-008 implement
   the same consumer contract.
2. *Hard-to-undo coupling?* Reduced. Voice data flows through one
   provider per invocation.
3. *Simplest correct solution?* Yes. The Protocol is additive; the
   existing `ProfileAssembler` already satisfies the generation
   projection.
4. *Design intent clear?* Yes. Producer/consumer split is a
   well-known pattern; the docstrings document the ADR-040 Layer 4
   gap this closes.

---

## Decision 4 — Variable Registry: register `kb_pinned` and siblings (closes P1-D)

### Options Considered

#### Option A — Producer-only documentation

Mark `kb_pinned`, `kb_timelines`, `kb_systems` as
"producer-only" in a docs note. Do not register them.

**Pros:**

- No registry change.

**Cons:**

- Perpetuates the ambiguity. A future template author who writes
  `{{kb_pinned}}` hits a CI failure with no guidance.
- `character_voice_profiles` is already in `SYSTEM_VARS` but
  mis-classified (should be `PROJECT_WRITING_PROFILE` per ADR-040).
  Documentation does not fix mis-classification.

#### Option B — Register all four in their correct classification (CHOSEN)

Add to `variable_registry.SYSTEM_VARS`:

* `kb_pinned`
* `kb_timelines`
* `kb_systems`

Add to `variable_taxonomy._classification_overrides`:

* `kb_pinned` → `CURATED_KB` / `XML_SECTION_REQUIRED`
  (high-priority pinned entities the author has explicitly marked;
  same handling as `kb_characters`).
* `kb_timelines` → `CURATED_KB` / `XML_SECTION_REQUIRED`.
* `kb_systems` → `CURATED_KB` / `XML_SECTION_REQUIRED`.
* `character_voice_profiles` → `PROJECT_WRITING_PROFILE` /
  `LABEL_REQUIRED` (overrides the `SYSTEM_VARS` default of
  `SYSTEM_ONLY`). This aligns the taxonomy with ADR-040 §1
  Decision A which classifies voice profiles under the project
  writing profile provenance.

**Pros:**

- Closes the governance gap completely.
- Aligns taxonomy with ADR-040.
- Future template authors get correct classification by default.

**Cons:**

- Changes the ratcheted baseline (one variable classification
  override moves from `SYSTEM_ONLY` to `LABEL_REQUIRED`). This is
  a deliberate, documented improvement, not a regression.

#### Option C — Register `kb_pinned` only

**Pros:**

- Minimal change.

**Cons:**

- Leaves `kb_timelines`, `kb_systems`,
  `character_voice_profiles` gaps open. The ambiguity is
  contagious; half-fixing it is worse than documenting it.

### Decision

**Option B.** Register all four with correct classifications.

### Rationale

RULE-22 §4 says "no unregistered variables in prompt templates."
The reverse is also true: a producer that emits a variable should
register it so the governance is symmetric. Option A documents the
gap; Option B closes it. Option C half-closes it and leaves the
mis-classification of `character_voice_profiles` untouched.

### Sustainability check

1. *Correct in 3 months?* Yes. Future variables follow the same
   register-at-producer rule.
2. *Hard-to-undo coupling?* None. Registry additions are additive.
3. *Simplest correct solution?* Yes. Four lines added to
   `SYSTEM_VARS`; four entries in `_classification_overrides`.
4. *Design intent clear?* Yes. Each classification matches its
   ADR-040 / RULE-22 §7 precedence source.

---

## Consequences

**Positive:**

* Provenance is preserved or explicitly omitted at every render
  boundary (P1-A).
* KB lifecycle changes notify consumers; stale refs surface as
  typed issues (P1-B).
* Voice profile data flows through one provider per invocation;
  WRITE-010 and ANAL-008 inherit the contract (P1-C).
* Variable governance is symmetric: every produced variable is
  registered (P1-D).
* FIND-009 is split into resolved (CONS-001) and open
  (cross-feature ref lifecycle) halves, each with a clear owner.

**Negative / Tradeoffs:**

* Four new Protocols and several supporting types
  (`KBContextEnvelope`, `RenderedKBContext`, `ProvenanceField`,
  `OmissionReason`, `KBEntityLifecycleObserver`,
  `CrossFeatureRefIndex`, `RefIntegrityIssue`,
  `ContradictionPromotionPolicy`, `TimelineRefConsumer`,
  `StoryboardRefConsumer`, `ChapterFrontmatterRefConsumer`,
  `VoiceProfileConsumer`).
* Renderers must be migrated to return `RenderedKBContext`
  (incremental; see Phase B acceptance criteria).
* Backend services must register observers at DI composition
  (discipline; CI test should verify registration).
* Hard delete stays destructive — users who delete a KB entity
  will see error issues in the next consistency check, not silent
  rewrites.

**Constraints introduced:**

* RULE-22 §1, §2 — every renderer of KB context implements
  `KBContextEnvelope`; every consumer of KB refs implements
  `KBEntityLifecycleObserver`.
* RULE-03 — Protocols in `core/context/contracts.py` and
  `core/context/integration_contracts.py` exist before any Backend
  enforcement lands.
* RULE-07 — Core owns vocabulary; Backend owns enforcement and
  observer registration.

---

## Implementation Plan

This ADR specifies contracts only. Implementation is phased:

### Phase B (Core) — Acceptance criteria

* [ ] `KBContextEnvelope` Protocol + `RenderedKBContext` exist in
      `core/context/contracts.py` (DONE in this ADR).
* [ ] `KBEntityLifecycleObserver`, `CrossFeatureRefIndex`,
      `RefIntegrityIssue`, `ContradictionPromotionPolicy`,
      `TimelineRefConsumer`, `StoryboardRefConsumer`,
      `ChapterFrontmatterRefConsumer` exist in
      `core/context/integration_contracts.py` (DONE in this ADR).
* [ ] `VoiceProfileConsumer` Protocol exists in
      `core/profiles/contracts.py` (DONE in this ADR).
* [ ] `variable_registry.SYSTEM_VARS` includes `kb_pinned`,
      `kb_timelines`, `kb_systems`.
* [ ] `variable_taxonomy._classification_overrides` classifies
      `kb_pinned`, `kb_timelines`, `kb_systems` as `CURATED_KB` and
      `character_voice_profiles` as `PROJECT_WRITING_PROFILE`.
* [ ] Unit tests verify Protocol structural compatibility for each
      new type.
* [ ] Unit tests verify `RenderedKBContext` is frozen and hashable.

### Phase C (Backend) — Acceptance criteria

* [ ] `KBRepository` (or a new `KBLifecycleService`) calls every
      registered `KBEntityLifecycleObserver` on rename/deprecate/delete.
* [ ] Timeline service registers a `TimelineRefConsumer` that
      updates hybrid JSON refs on rename and marks `status: deprecated`
      on deprecate.
* [ ] Storyboard service registers a `StoryboardRefConsumer` that
      scans `planned_beats` and `outline_notes` for stale name refs
      and emits `RefIntegrityIssue` (no rewrite).
* [ ] Chapter service registers a `ChapterFrontmatterRefConsumer`
      that scans frontmatter for stale name refs and emits issues
      (no rewrite).
* [ ] `WritingContextAssembler.assemble` migrated to consume
      `VoiceProfileConsumer` instead of calling
      `extract_voice_profiles` directly.
* [ ] Each renderer migrated to return `RenderedKBContext`:
  - [ ] `PromptContext._format_kb_entries`
  - [ ] `writing/_helpers.format_entities`
  - [ ] `writing/context_wiki.format_entities_with_wiki`
  - [ ] `writing/_tier3_processor.apply_tier3`
  - [ ] `writing/_voice_profiles.extract_voice_profiles`
        (or its replacement)
* [ ] Integration tests verify observer notification on
      rename/deprecate/delete end-to-end.
* [ ] Integration tests verify `RefIntegrityIssue` promotion per
      `ContradictionPromotionPolicy`.

### Phase D (Docs/Platform) — Acceptance criteria

* [ ] CONS-001 spec updated: FIND-009 split into 009a (resolved)
      and 009b (open, closed by this ADR's P1-B).
* [ ] PLAN-004 spec updated: cross-link to this ADR's
      `TimelineRefConsumer` contract.
* [ ] PLAN-005 spec updated: cross-link to this ADR's
      `StoryboardRefConsumer` contract.
* [ ] KB-001 spec updated: KB lifecycle (rename/deprecate/delete)
      now emits observer events.
* [ ] i18n tone drift (P2): correct `universal/{de,fr}/system.md`
      formality mismatch. Tracked as docs backlog item, not a code
      change.
* [ ] `docs/architecture/decisions/INDEX.md` updated with ADR-050.
* [ ] `docs/_shared/CURRENT_STATE.md` updated with FIND-009 split
      and ADR-050 entry.
* [ ] Platform CI checker (new) verifies that every renderer of KB
      context returns `RenderedKBContext` (static AST scan, mirrors
      ADR-046 checker pattern).

### Dependency order

```
Phase B (Core contracts + variable registry)
        ↓
Phase C (Backend observers + renderer migration + voice consumer wiring)
        ↓
Phase D (Docs + platform checker + i18n tone fix)
```

Phase B is prerequisite for Phase C. Phase D's docs can proceed in
parallel with Phase C; the platform checker depends on Phase C
completion.

---

## ADR Implementation Completeness Gate (Gate 12)

This ADR is **not** ✅ Implemented until:

* [ ] All Phase B acceptance criteria met.
* [ ] All Phase C acceptance criteria met.
* [ ] All Phase D acceptance criteria met.
* [ ] No renderer of KB context bypasses `KBContextEnvelope`.
* [ ] No consumer of KB refs bypasses `KBEntityLifecycleObserver`.
* [ ] No caller of voice profile data bypasses
      `VoiceProfileConsumer`.
* [ ] `kb_pinned`, `kb_timelines`, `kb_systems`,
      `character_voice_profiles` registered and classified.
* [ ] FIND-009 split documented in CONS-001 spec.

---

## Review Trigger

* [ ] When WRITE-010 (Voice Consistency Checker) is implemented —
      verify it uses `VoiceProfileConsumer.assemble_for_checking`.
* [ ] When ANAL-008 (Character Voice Profiling) is implemented —
      same.
* [ ] When a third KB-context renderer is added — verify it
      implements `KBContextEnvelope`.
* [ ] When user feedback indicates hard-delete is too destructive —
      consider a follow-up ADR for soft delete / tombstone column.
* [ ] When a non-writing feature (analysis, planning) needs to
      observe KB lifecycle — verify the observer contract covers it.
* [ ] After 6 months — assess whether `RenderedKBContext.omitted_fields`
      is actually consumed by audit tooling; if not, simplify.

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-03 | ✅ | Four Protocols defined before implementation. |
| RULE-06 | ✅ | Cross-feature ref lifecycle is its own concern (`integration_contracts.py`); KB envelope is its own concern (`contracts.py`); voice consumer is its own concern (`profiles/contracts.py`). |
| RULE-07 | ✅ | All contracts in `core/`. Enforcement in Backend. No Core→apps imports. |
| RULE-09 | ✅ | All Protocols fully typed; `Literal` enums for machine-readable audit fields. |
| RULE-11 | ✅ | `RenderedKBContext.omitted_fields` makes omission explicit; no silent loss. |
| RULE-22 | ✅ | Cross-feature coherence gate satisfied: shared data identified (P1-A), change/delete behaviour contracted (P1-B), variable registration closed (P1-D), precedence preserved (P1-C maintains ADR-040 precedence). |
| RULE-20 | ✅ | No half-implementations: Phase B/C/D acceptance criteria are explicit and gate the ADR's ✅ Implemented status. |

---

## Cross-References

* ADR-022 — LLM Wiki (predecessor for compressed-context rendering;
  `format_entities_with_wiki` is a `KBContextEnvelope` implementation
  candidate).
* ADR-025 — Feature Adoption Infrastructure (ContextAssembler base).
* ADR-037 — Prompt Surface Manifest (variable registration;
  `kb_pinned` registration closes a manifest gap).
* ADR-040 — KG/Voice SSOT (this ADR's P1-C extends ADR-040 §1 with
  the consumer-side contract).
* ADR-044 — Staged Consistency (this ADR's P1-B generalises ADR-044's
  `TimelineEventEnvelope` pattern to all consumers).
* CR-AUFG-04 — triggering review.
