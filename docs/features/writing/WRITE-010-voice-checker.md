---
id: WRITE-010
title: "Voice Consistency Checker"
status: stable
area: writing
mvp: false

ui_tooltip: "Check if dialogue matches each character's established voice."
ui_help_short: \
  |   Ensure characters sound like themselves. The Voice Checker analyzes
  |   dialogue against character voice profiles from your Knowledge Base,
  |   flagging inconsistencies and scoring how well each character matches
  |   their established speech patterns.
ui_help_long: |
  ## Voice Consistency Checker

  Characters should sound like themselves — every time they speak. The Voice
  Checker ensures the dialogue in a chapter matches each character's
  established voice.

  **What it checks:**

  For each speaking character in the chapter, it compares their dialogue
  against their stored voice profile (from Character Voice Profiling,
  ANAL-008):

  - Formal vs casual language (register)
  - Vocabulary level and complexity
  - Sentence structure preferences
  - Verbal tics and catchphrases (present where expected, absent where not)
  - Punctuation and formatting habits
  - Emotional register and expression

  **How it works:**
  1. Open a chapter with dialogue in the Editor
  2. Click "Check Voice" in the analysis toolbar
  3. Analysis runs (5–15 seconds)
  4. Results panel shows, per speaking character:
     - Overall match score (0–100%)
     - Color coding: green (good), yellow (fair), red (poor)
     - Specific dialogue lines flagged as inconsistent
     - A short reason for each flag
  5. Click any flagged line to see why it doesn't match

  The checker **flags and scores** — it does not rewrite dialogue. To fix a
  flagged line, select it and use Rewrite (WRITE-004), which can align the
  line to the character's voice profile.

  **Voice profiles:**

  Characters need a voice profile produced by Character Voice Profiling
  (ANAL-008). The more complete the profile, the better the checking. A
  character without a profile is skipped with a "no profile" note (not an
  error).

  **Scores explained:**
  - 90–100%: Excellent match — character sounds consistent
  - 70–89%: Good match — minor inconsistencies
  - 50–69%: Fair match — several flagged lines
  - <50%: Poor match — character doesn't sound like themselves

  **Best practices:**
  - Profile characters with Character Voice Profiling first (ANAL-008)
  - Use during revision, not first draft
  - Low scores don't mean bad writing — intentional voice changes are valid
  - Re-profile after major dialogue revisions, then re-check

  The Voice Checker helps consistency, not creativity. If a character
  intentionally speaks differently in a scene (emotional, disguised, etc.),
  that's your call as the author.
ui_available_in: [editor]

service: analysis/voice_check_service.py
contract: analysis/contracts_voice_check.py#CharacterVoiceCheckerServiceProtocol
router: analysis/router_voice_check.py
prompt: core/prompts/_bundled/analysis/en/voice_check/system.md
requires: [INFRA-001, INFRA-002, KB-001, ANAL-008]
---

# WRITE-010 — Voice Consistency Checker

> **Architecture authority:** [ADR-057](../../architecture/decisions/ADR-057-voice-check-checking-path-contract.md)
> (Voice-Check Checking-Path Contract & `voice_check` Prompt Surface) — ✅
> Implemented. The technical sections below implement that ADR. Status is
> `stable`: implemented across all layers (Core 0/1/2a/2b + Backend 3a/3b/3c +
> Frontend 4) and validated; ADR-056 runtime adoption evidence satisfied.

## What it does

Checks a chapter's dialogue against each speaking character's stored voice
profile (produced by ANAL-008) and reports a per-character match score plus
specific flagged lines with reasons. It is **read-only** — it checks; it does
not profile and does not write to the Knowledge Base. It **flags and scores**;
it does not generate rewrite suggestions (rewrite reuse of WRITE-004 on a
flagged line is a separate, composable step — ADR-057 Decision 5).

## Why it exists

Readers notice when characters don't sound like themselves. A formal professor
suddenly using slang, a teenager talking like a Victorian — these breaks pull
readers out of the story. Voice checking catches these inconsistencies before
readers do, using the deterministic metrics + qualitative profile ANAL-008
already computed and stored.

## How it works (User perspective)

1. Profile characters with Character Voice Profiling (ANAL-008) first
2. Open a chapter with dialogue in the Editor
3. Click "Check Voice" in the analysis toolbar
4. Analysis runs (5–15 seconds)
5. Results panel shows, per speaking character:
   - Match score percentage + color (green/yellow/red)
   - Flagged dialogue lines with a short reason each
6. Click any flagged line to see why it doesn't match
7. To fix a flagged line, select it and run Rewrite (WRITE-004)

Characters without a stored profile are listed as "no profile" (skipped, not
an error). Low scores don't always mean errors — intentional voice changes
are valid. Use your judgment as the author.

## How it works (Technical)

> Mirrors the established analysis pattern (ANAL-003/004/005/008):
> deterministic measurement + `NarrareAgent` structured output + governed EN
> template + SSE router + panel. Per ADR-021 + ADR-055 + ADR-057.

**Entry point:** `analysis/router_voice_check.py` → `POST /api/v1/analysis/voice-check/{chapter_id}`
(chapter-scoped; mirrors coreference's `/analysis/coreference/{chapter_id}`,
vs character_voice's novel-scoped `/analysis/character-voice/{novel_id}`)
**Service:** `CharacterVoiceCheckerService.check()` in `analysis/voice_check_service.py`
**Contract:** `CharacterVoiceCheckerServiceProtocol` in `analysis/contracts_voice_check.py`
**Agent:** `CharacterVoiceCheckerAgent` (`core/agents/character_voice_checker_agent.py`, `NarrareAgent` with structured output, ONE LLM call)
**Scoring:** pure Core module `core/analysis/voice_check_scoring.py` (deterministic delta + blend)
**LLM Intent:** `LLMIntent.VOICE` (context_mode `voice_check`; ADR-057 adds it to the VOICE route)
**Prompt:** PromptComposer Mode 1 — `_bundled/analysis/en/voice_check/system.md` (governed EN template; ADR-054)

> **Module home: `analysis/`, not `writing/`.** WRITE-010 is a read-only check
> (deterministic delta + LLM qualitative judgment; zero chapter mutation) that
> reuses the analysis Foundation (`DialogueParser`, `VoiceMetricsAnalyzer`).
> It is the same shape as the ANAL-008 sibling. `writing/` is reserved for
> generation/transform operations (WRITE-001..009). The feature keeps its ID
> `WRITE-010` and its "Writing" placement in the registry (user-facing
> taxonomy: a revision-time aid run from the editor); the implementation lives
> in `analysis/` for module cohesion. See ADR-057 Decision 4.

### Implementation status (2026-06-30)

ADR-057 is ✅ **Implemented** (runtime-verified). WRITE-010 is **stable** —
implemented & validated end-to-end:

- ✅ **Core (layers 0/1/2a/2b)** — `CharacterVoiceProfile.voice_metrics` extension
  + builder (`core/profiles/models.py`, `_voice_extraction.py`); `voice_check`
  context_mode on the routeable `LLMIntent.VOICE` (`core/prompts/route_table.py`);
  governed EN template (`core/prompts/_bundled/analysis/en/voice_check/system.md`);
  deterministic scoring module `core/analysis/voice_check_scoring.py`;
  `CharacterVoiceCheckerAgent` (`core/agents/character_voice_checker_agent.py`).
- ✅ **Backend (3a/3b/3c)** — 3a: `contracts_voice_check.py` + `schemas_voice_check.py`
  + voice_profile_adapter fix (voice_metrics surfaced on the checking path); 3b:
  `voice_check_service.py` modularised (RULE-04 split) with the helper modules
  `voice_check_prompt.py`, `voice_check_runtime_content.py`,
  `voice_check_agent_runner.py`, `voice_check_results.py`; 3c: SSE router
  `router_voice_check.py` — `POST /api/v1/analysis/voice-check/{chapter_id}`
  (mounted in `_app/main.py`) + DI factory (`dependencies_voice_check.py`).
- ✅ **Frontend (Layer 4)** — `VoiceCheckPanel` / `Trigger` / `Results` /
  `ResultCard` + `useCharacterVoiceCheck` hook + SSE stream client (`connectSSE`,
  §5.1) + editor wiring (store toggle + mutual-exclusion + toolbar + AI-operation
  inventory) + i18n (en/de/fr, 29–30 keys).
- ✅ **Runtime adoption evidence** — ADR-056 commit-gate probes (agent + service)
  satisfied. `voice_check` is static ✅, runtime ✅, and adopted ✅
  (adoption_debt 5 → 1 — true debt only).

**Validation:** architecture OK (1941 files); pyright 0 errors; backend unit
2534 + core 4814 passed; frontend 2339 tests; AI-UX 44/44; i18n parity; streaming
ratchet 0 new; prompt-structure 49/49.

> **Env caveat (honest disclosure):** integration tests
> (`tests/integration/analysis/test_voice_check_api.py`) exist but were SKIPPED
> locally (test Postgres not running in this environment); CI runs them. The
> validation figures above come from the unit / core / frontend suites that run
> without a live database.

### Checking-path data contract (ADR-057 Decision 1 — closes ADR-055 Risk #1)

The checker reads each character's stored metrics **through the ADR-050
consumer contract**, not via direct KB access. `CharacterVoiceProfile` is
extended with one optional field that the consumer surfaces on the checking
path:

```python
# packages/core/narrare_core/profiles/models.py  (ADR-057)
from dataclasses import dataclass
from narrare_core.kb.schemas.character import VoiceMetrics

@dataclass(frozen=True)
class CharacterVoiceProfile:
    character_id: str
    name: str
    speech_summary: str                       # unchanged — rendered into generation
    updated_at: str | None = None
    is_fresh: bool = True
    # ADR-057: surfaced on the checking path only. None unless the character's
    # speech.voice_analysis exists (ANAL-008). NEVER rendered into generation.
    voice_metrics: VoiceMetrics | None = None
```

- `VoiceProfileConsumer.assemble_for_checking()` (ADR-050) returns
  `list[CharacterVoiceProfile]` where each profile now carries `voice_metrics`
  when ANAL-008 has profiled the character. The signature is unchanged.
- `build_character_voice_profile()` (in `core/profiles/_voice_extraction.py`)
  parses `speech.voice_analysis.voice_metrics` and populates the field.
- The generation path (`assemble_for_generation` →
  `ProjectWritingProfile.formatted_voice_profiles`) is **unchanged** — it
  renders `speech_summary` and never reads `voice_metrics` (the ADR-055
  "metrics never reach generation" constraint is preserved).

This is the implementation that makes ADR-055 Risk #1's tracked deferral and
the ANAL-008 spec's checking-path claim actually true.

### Scoring: hybrid deterministic-delta + LLM qualitative (ADR-057 Decision 2, ADR-021)

```python
# Deterministic delta — pure Core (core/analysis/voice_check_scoring.py)
#   current metrics (VoiceMetricsAnalyzer on this chapter's dialogue)
#   vs. stored metrics (CharacterVoiceProfile.voice_metrics via the consumer)
# → normalized per-metric distance + aggregate metric-delta sub-score

# LLM qualitative judgment (CharacterVoiceCheckerAgent — ONE call)
#   consumes: chapter dialogue + stored DESCRIPTIVE profile + metric-delta
#   produces: per-character qualitative sub-score + flagged lines + reasons

# Overall per-character match score (0–100%) = deterministic BLEND
#   of the metric-delta sub-score + agent qualitative sub-score
#   (the blend is pure logic — reproducible, fully unit-testable)
```

Line-level flags (specific dialogue lines + reasons) come from the agent.
Thresholds: green ≥90%, yellow 70–89%, fair 50–69%, red <50%. A character
without a stored profile yields a graceful "no profile" result (RULE-11).

### Pipeline

```
chapter
  → DialogueParser              (utterances + tag attribution + confidence)
                                [Core: core/analysis/dialogue_parser.py — REUSED from ANAL-008]
  → VoiceMetricsAnalyzer        (current per-character deterministic metrics)
                                [Core: core/analysis/voice_metrics.py — REUSED, ADR-021]
  → VoiceProfileConsumer.       (stored per-character profiles incl. voice_metrics)
    assemble_for_checking()     [Core contract: core/profiles/contracts.py — ADR-050, enriched ADR-057]
  → voice_check_scoring         (deterministic delta: current vs stored, normalized)
                                [Core: core/analysis/voice_check_scoring.py — NEW]
  → CharacterVoiceCheckerAgent  (qualitative judgment + flagged lines + reasons,
                                 consuming dialogue + stored DESCRIPTIVE profile
                                 + metric-delta — ONE LLM call)
                                [Core: core/agents/character_voice_checker_agent.py — NEW]
  → voice_check_scoring (blend) (deterministic overall score per character)
  → per-character result        (match score + flagged lines + reasons)
```

### Foundation (reused, not duplicated)

WRITE-010 reuses the Layer-2 Foundation built for ANAL-008 — justified reuse,
not duplication:

| Component | Location | Reused from |
|-----------|----------|-------------|
| `DialogueParser` | `core/analysis/dialogue_parser.py` | ANAL-008 (ADR-055) |
| `VoiceMetricsAnalyzer` | `core/analysis/voice_metrics.py` | ANAL-008 / ADR-021 |
| `VoiceProfileConsumer` | `core/profiles/contracts.py` | ADR-050 (enriched ADR-057) |

NEW for WRITE-010: `voice_check_scoring.py` (delta + blend),
`character_voice_checker_agent.py` + `character_voice_checker_types.py`
(checker agent).

### Scope boundary (ADR-057 Decision 5)

The checker **flags + scores** only. It does NOT produce rewrite suggestions
(rewrite reuse of WRITE-004 on a flagged line is a separate, composable step).
The checker agent's output type carries `flagged_lines` + `reasons` + `score`
— never `suggested_rewrite`.

### Prerequisites

Requires ANAL-008 voice profiles (`speech.voice_analysis`) in the Knowledge
Base. The generation pipeline already injects `{{character_voice_profiles}}`
into writing prompts as a preventive measure; WRITE-010 adds an active
checking layer that reads the same source via the consumer contract.

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-02/02b | ✅ | `voice_check` prompt = PromptComposer Mode 1 (governed EN template); no inline f-string, no production fallback. |
| RULE-03 | ✅ | `CharacterVoiceCheckerServiceProtocol` + agent Protocol + the `voice_metrics` model extension defined before implementation (ADR-057). |
| RULE-04/06 | ✅ | Modularised: scoring ≠ agent ≠ service ≠ router; one responsibility per file. |
| RULE-07 | ✅ | `analysis → profiles (consumer) → kb.schemas` read-direction only; checker reads via consumer contract, not KB directly. |
| RULE-11 | ✅ | Character without `voice_analysis` → graceful "no profile"; stale profile surfaced with reduced confidence. |
| RULE-13 | ✅ | SSE + non-streaming share the service interface. |
| RULE-22 | ✅ | Cross-feature coherent: producer (ANAL-008) + generation consumer (unchanged) + checking consumer (enriched) defined together (CR-04). |
| ADR-021 | ✅ | Deterministic metric-delta; LLM qualitative only. |
| ADR-050 | ✅ | Reads via `VoiceProfileConsumer.assemble_for_checking()`. |
| ADR-055 | ✅ | Closes Risk #1; reuses routeable VOICE + Foundation; metrics never reach generation. |

## Constraints & Edge Cases

- Requires an ANAL-008 voice profile in KB (create via Character Voice Profiling)
- Character without a profile → graceful "no profile" result (not an error)
- Poor profiles = poor checking (garbage in, garbage out)
- Intentional voice changes may be flagged (author discretion)
- Dialogue attribution errors affect accuracy (the agent resolves ambiguity inline)
- Very short dialogue (<10 lines) = unreliable scores
- Sarcasm, irony, lies not detected by metrics (the agent may surface these)
- LLM availability required (metrics + delta are deterministic; the qualitative
  judgment is not)

## Related Features

- [ANAL-008](../analysis/ANAL-008-voice-character.md) — Produces the voice profiles + metrics this checker reads
- [ANAL-009](../analysis/ANAL-009-voice-drift.md) — Voice drift (will reuse the scoring delta primitive; its stale "map to SpeechPatterns" note is superseded by ADR-055/057)
- [WRITE-004](WRITE-004-rewrite.md) — Rewrite a flagged line to align with the voice profile (composable, separate step)
- [KB-001](../kb/KB-001-entity-management.md) — Stores the voice profiles (`speech.voice_analysis`)
- [ADR-057](../../architecture/decisions/ADR-057-voice-check-checking-path-contract.md) — Checking-path + prompt-surface contract authority

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-06-30` — Spec rewritten against **ADR-057** (voice-check checking-path
  contract + `voice_check` prompt surface). Replaced the earlier stale design
  (writing/ paths, suggested-rewrites scope, hypothetical `VoiceProfile` that
  did not match the live `SpeechPatterns` contract) with: hybrid flag+score
  checker reusing the ANAL-008 Foundation; read-only; checking path through
  the ADR-050 consumer contract via the `CharacterVoiceProfile.voice_metrics`
  extension (closes ADR-055 Risk #1); `voice_check` context_mode; module home
  `analysis/`.
- `2026-06-30` — **ADR-057 → ✅ Accepted** (user approved layer-by-layer
  implementation). Status → `in-progress`. Core layers (0/1/2a/2b) + Backend
  layers (3a contracts/schemas + voice_profile_adapter fix; 3b service
  modularised with the RULE-04 helper split — `voice_check_prompt.py`,
  `voice_check_runtime_content.py`, `voice_check_agent_runner.py`,
  `voice_check_results.py`; 3c SSE router `POST /api/v1/analysis/voice-check/{chapter_id}`
  + DI + app registration) implemented and green (176 analysis unit tests pass;
  integration tests skipped only where no test DB is available). Frontend
  Layer 4 + ADR-056 runtime adoption evidence remain before `stable`. ADR-057
  is Accepted, not yet "✅ Implemented".
- `2026-06-30` — **Status → `stable`** (final Doc Gate). ADR-057 → ✅
  **Implemented**. Frontend Layer 4 landed (`VoiceCheckPanel` / `Trigger` /
  `Results` / `ResultCard` + `useCharacterVoiceCheck` hook + SSE stream client
  + editor wiring + i18n en/de/fr) and the ADR-056 runtime-evidence gate is
  satisfied: `voice_check` is static ✅, runtime ✅, and adopted ✅
  (adoption_debt 5 → 1 — true debt only). Validated: architecture OK (1941
  files), pyright 0 errors, 2534 backend + 4814 core + 2339 frontend tests,
  AI-UX 44/44, i18n parity, streaming ratchet 0 new, prompt-structure 49/49.
  Env caveat: integration tests exist but were skipped locally (no test
  Postgres); CI runs them.
