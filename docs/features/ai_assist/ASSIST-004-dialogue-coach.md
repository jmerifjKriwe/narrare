---
id: ASSIST-004
title: "Dialogue Coach"
status: in-progress
area: ai_assist
mvp: false

ui_tooltip: "Analyze and improve dialogue for subtext, flow, and character voice."
ui_help_short: |
  AI helps make dialogue more natural and character-authentic.
  Dialogue Coach analyzes your dialogue for common problems and provides improved rewrites.
ui_help_long: |
  Dialogue Coach analyzes your dialogue for common problems -- subtext violations,
  info-dumping, redundancy, and character voice inconsistencies -- and provides both
  analysis and improved rewrites. It helps you write dialogue that sounds natural,
  reveals character, and moves the story forward.

  **Modes**
  - **Analyze**: identify issues, provide suggestions, no rewrites.
  - **Improve**: identify issues AND propose `DialogueAlternative` rewrites.

  **Adaptivity**
  Dialogue Coach is the first feature that visibly uses your full adaptive
  context: your `PreferenceProfile` (LEARN-001) and your `CharacterVoiceProfile`
  per speaking character (ANAL-008). Voice fidelity is prioritised; user
  preferences shape the analysis; avoidance patterns are honoured.

  **Per-call transparency**
  Each call records which signals shaped the result; the LEARN-002 dashboard
  surfaces this for review.

  **Selection**
  Select 1–4 speaking characters' dialogue in the editor, then start the
  coach. Speakers are auto-attributed via deterministic parsing; ambiguous
  attributions are resolved inline by the agent.
ui_available_in: ["editor", "cli", "mcp", "api"]

service: ai_assist/service.py
contract: ai_assist/contracts.py#DialogueCoachServiceProtocol
router: ai_assist/router.py
prompt: core/prompts/_bundled/ai_assist/en/dialogue_coach/system.md
requires: [INFRA-001, INFRA-002, INFRA-005, LEARN-001, LEARN-002, ANAL-008, KB-001]
---

# [ASSIST-004] — Dialogue Coach

> **Detailed 2026-07-19** by [ADR-069](../../architecture/decisions/ADR-069-adaptive-context-dialogue-coach.md).
> ASSIST-004 is the **pilot consumer** of the new `AdaptiveContext` Core
> contract. The dialogue-coach architecture (Core agent + Backend service
> + governed prompt + SSE router + Frontend panel) is fully specified by
> ADR-069; this feature file captures the user-facing contract and the
> developer-reference paths.

## What it does

Dialogue Coach analyses and improves dialogue passages. In **Analyze** mode,
it identifies dialogue problems (subtext violations, exposition dumps,
redundancy, voice mismatches, underspecified statements, over-formal
language, tag overuse) and provides brief suggestions. In **Improve** mode,
it additionally proposes concrete rewrites (`DialogueAlternative`s) that the
user can accept or reject individually.

Dialogue Coach is the first feature that **visibly consumes the
`AdaptiveContext`** — it uses the user's `PreferenceProfile` (LEARN-001) AND
the per-character `CharacterVoiceProfile` (ANAL-008) in one operation,
closing the feedback loop (accept/reject → PreferenceProfile → next coach
call).

## Why it exists

Writing natural, engaging, and character-authentic dialogue is difficult.
Characters often sound the same or deliver clunky exposition. Dialogue Coach
acts as an AI editor specialized in conversations, identifying these flaws
and showing how to fix them.

ASSIST-004 is also the **pilot consumer** of the adaptivity vertical: it
demonstrates the value of `AdaptiveContext` (ADR-069) by visibly using both
user preferences and character voices in its reasoning. Without this pilot,
the adaptivity infrastructure would remain invisible.

## How it works (User perspective)

1. Select a passage of dialogue in the editor (1–4 speaking characters,
   50–5000 characters).
2. Open the **Dialogue Coach** tab in the Analysis Panel.
3. Choose a mode: **Analyze** (feedback only) or **Improve** (feedback +
   proposed rewrites).
4. Click **Start Analysis**.
5. SSE-streaming shows progress while the agent runs.
6. View results:
   - **Issues**: categorised by type, severity, speaker; each issue has a
     short explanation and (optionally) a brief suggestion.
   - **Alternatives** (Improve mode only): for each flagged passage, an
     original quote + a rewrite + a rationale. Accept or reject
     individually. Accept applies the rewrite to the editor.
7. Accept/reject decisions are persisted as `FeedbackEvent`s, feeding
   `PreferenceProfile` (LEARN-001 loop).

## How it works (Technical)

**Architectural decisions:** [ADR-069](../../architecture/decisions/ADR-069-adaptive-context-dialogue-coach.md)
(17 decisions covering the dialogue-coach contract, the adaptive context
contract, and the LEARN-002 dashboard recalibration).

**Entry point:** `apps/api/narrare/ai_assist/router.py` →
`POST /api/v1/ai-assist/dialogue-coach` (SSE; per ADR-069 Decision 8 —
single endpoint with `mode` in body).

**Service:** `apps/api/narrare/ai_assist/service.py` →
`DialogueCoachService`. Exposes both `run()` (non-streaming, for future
MCP/A2A) and `stream()` (SSE for WebUI), per ADR-069 Decision 17 / ADR-065.

**Contract:** `DialogueCoachServiceProtocol` in
`apps/api/narrare/ai_assist/contracts.py`.

**LLM Intent:** `LLMIntent.DIALOGUE_COACH` (new; per ADR-069 Decision 5).
Category: `ai_assist`. Default mode: `dialogue_coach`.

**Prompt:** `packages/core/narrare_core/prompts/_bundled/ai_assist/en/dialogue_coach/system.md`
(new governed EN template; Mode 1 PromptComposer per ADR-054; registered in
`prompt-surface-manifest.yaml` + `adoption-registry.yaml` per ADR-069
Decision 10). EN-only by default; output language is controlled via
`{{writing_language}}` and runtime Deps, not by duplicating the template
per locale (RULE-22 §5).

**Agent:** `packages/core/narrare_core/agents/dialogue_coach_agent.py` →
`DialogueCoachAgent` (extends `NarrareAgent[DialogueCoachDeps,
DialogueCoachOutput]`). Structured output validated per ADR-035.

**Output types:** `packages/core/narrare_core/agents/dialogue_coach_types.py`:

- `DialogueCoachDeps` (runtime Deps: `adaptive_context`, `mode`,
  `text_to_analyze`, `characters`, `language`).
- `DialogueCoachOutput` (`mode`, `overall_assessment`, `issues`,
  `alternatives`, `adaptive_summary`).
- `DialogueIssue` (`type`, `severity`, `speaker`, `quote`, `explanation`,
  `suggestion`).
- `DialogueAlternative` (`original_quote`, `rewrite`, `rationale`,
  `applies_to_issue_ids`, `speakers`).
- `DialogueIssueType` (StrEnum: `subtext_violation`, `exposition_dump`,
  `redundancy`, `voice_mismatch`, `underspecified`, `overformal`,
  `tag_overuse`).
- `DialogueSeverity` (StrEnum: `info`, `minor`, `major`, `critical`).

**Streaming:** SSE via `connectSSE` (RULE-20 / ADR-069 Decision 17).
Streaming events: `progress`, `result` (per issue/alternative), `done`,
`error`. Network-disconnect recovery via ADR-052.

**Backend files (per ADR-069 Retrofit-Plan §1):**

- `apps/api/narrare/ai_assist/__init__.py`
- `apps/api/narrare/ai_assist/contracts.py` — `DialogueCoachServiceProtocol`
- `apps/api/narrare/ai_assist/schemas.py` — `DialogueCoachRequest`,
  `DialogueCoachResponse`, `DialogueCoachStreamEvent`
- `apps/api/narrare/ai_assist/service.py` — `DialogueCoachService`
- `apps/api/narrare/ai_assist/router.py` — SSE endpoint
- `apps/api/narrare/ai_assist/dependencies.py` — DI factories
- `apps/api/narrare/ai_assist/_agent_runner.py` — agent invocation helper
- `apps/api/narrare/ai_assist/_prompt.py` — PromptComposer call helper
- `apps/api/narrare/ai_assist/_speaker_attribution.py` —
  `DialogueParser` wrapper (reuses ADR-055 D3 infrastructure)
- `apps/api/narrare/ai_assist/_runtime_content.py` — AdaptiveContext →
  template variables mapping
- `apps/api/narrare/ai_assist/_results.py` — agent output → API response
  mapping

**Adaptive context consumption:**

The service calls `AdaptiveContextProvider.get_context(user_id, project_id)`
to obtain the adaptive bundle. The bundle's `voice_profiles_text` (rendered
from `ProjectWritingProfile.formatted_voice_profiles`) is passed as
`DialogueCoachDeps.adaptive_context.voice_profiles_text` AND injected into
the governed prompt via `{{character_voice_profiles}}` (existing registered
variable). `preference_text` flows via `{{user_preferences}}`;
`style_constraints_text` via `{{style_constraints}}`;
`avoidance_patterns_text` via `{{avoidance_patterns}}`. The active
`AdaptiveWeights` are summarised in the prompt as a steering hint.

**Hard constraint (ADR-055/057, ADR-069 Decision 6):** `voice_metrics` are
NEVER read by ASSIST-004. Only the descriptive `speech_summary` is consumed.
This preserves the "metrics never reach generation" boundary even when
the coach proposes rewrites.

**Speaker attribution (ADR-069 Decision 7):** Reuses
`core/analysis/dialogue_parser.py` (deterministic; ADR-055 D3) for
attribution. Residual ambiguous speakers are resolved inline by the
`DialogueCoachAgent` in its single LLM call (no ANAL-005 Coreference
runtime coupling).

**Frontend (per ADR-069 Retrofit-Plan §1):**

- `packages/web/components/analysis/dialogue-coach/DialogueCoachPanel.tsx`
- `packages/web/components/analysis/dialogue-coach/DialogueModeSelector.tsx`
- `packages/web/components/analysis/dialogue-coach/DialogueIssueList.tsx`
- `packages/web/components/analysis/dialogue-coach/DialogueIssueCard.tsx`
- `packages/web/components/analysis/dialogue-coach/DialogueAlternativeList.tsx`
- `packages/web/components/analysis/dialogue-coach/DialogueAlternativeCard.tsx`
  (renamed from `DialogueInlineDiff` per ADR-069 Decision 9 — simple
  before/after block, no char-level diff)
- `packages/web/components/analysis/dialogue-coach/DialogueCoachProgress.tsx`
- `packages/web/components/analysis/dialogue-coach/DialogueCoachEmptyState.tsx`
- `packages/web/hooks/dialogue-coach/useDialogueCoach.ts` (uses
  `useAIOperation` per ADR-043)
- `packages/web/hooks/dialogue-coach/useDialogueCoachAccept.ts`
- `packages/web/lib/api/dialogue-coach.ts` (SSE client)
- `packages/web/types/dialogue-coach.ts` (RULE-17 field-by-field match
  with backend Pydantic schema)

**Panel placement:** Tab in the existing Analysis Panel (per ADR-069
Decision 16). Uses `frontend-design`, `vercel-composition-patterns`, and
`web-design-guidelines` skills at implementation time.

**i18n namespace:** `studio.dialogueCoach` (registered in `request.ts`;
present in `packages/i18n/messages/{en,de,fr}/`).

**Evals (RULE-18b evidence, per ADR-069 Retrofit-Plan §5):**

- `evals/dialogue_coach/test_analyze_basic.py`
- `evals/dialogue_coach/test_improve_basic.py`
- `evals/dialogue_coach/test_voice_fidelity_weight_effect.py` — proves
  that changing `voice_fidelity` weight from 1.0 → 0.1 measurably
  changes the count of `voice_mismatch` issues detected (the
  configuration-effect-integrity evidence RULE-18b requires).
- `evals/dialogue_coach/test_preferences_respected.py`

## Constraints & Edge Cases

- **Best used on 2–4 speaking characters.** More characters reduce
  fidelity accuracy (Edge Case E10 — service blocks with 422 if >4).
- **Selection length:** 50–5000 characters (E7, E8).
- **Monologues or internal thoughts** are not well-supported (use
  Voice Checker instead).
- **Voice metrics are not used.** Per ADR-055/057 and ADR-069 Decision 6,
  only the descriptive `speech_summary` is consumed. Drift detection is
  ANAL-009's job.
- **Speaker attribution is best-effort.** The deterministic
  `DialogueParser` handles tagged dialogue; the agent resolves ambiguous
  speakers inline. Unattributable lines may be flagged with
  `speaker=None` or `speaker=<unknown>`.
- **Missing character profile:** If a speaking character has no
  `voice_analysis` in the KB, the coach notes this and provides
  analysis without voice-fidelity checks for that character (Edge Case
  E5; graceful per RULE-11).
- **Output validation failure:** If the LLM returns invalid JSON, ADR-035
  output validation triggers a retry with schema hint; on second failure
  an SSE error event is emitted (Edge Case E14).
- **Network disconnect during SSE:** ADR-052 session-recovery applies;
  user sees a reconnect banner (Edge Case E15).
- **Improve mode rewrites are full-string replacements.** Accept applies
  by finding `original_quote` in the chapter text and replacing it (per
  ADR-069 Decision 9). No char-level diff.
- **Disabled adaptivity:** If `AdaptiveSettings.enabled = False`, the
  coach still runs but without adaptive context (degraded, not broken).
  The output's `adaptive_summary` notes "adaptivity disabled".

## Related Features

- [LEARN-001](../learning/LEARN-001-feedback-loop.md) — Source of
  `PreferenceProfile`; destination of coach `FeedbackEvent`s
- [LEARN-002](../learning/LEARN-002-style-adaptation.md) — Adaptivity
  Dashboard; visualises coach's adaptive activity
- [ANAL-008](../analysis/ANAL-008-voice-character.md) — Source of
  `CharacterVoiceProfile` (descriptive `speech_summary` only)
- [WRITE-010](../writing/WRITE-010-voice-checker.md) — Voice Check uses
  `voice_metrics` (checking path); ASSIST-004 deliberately does not
- [KB-001](../kb/KB-001-entity-management.md) — Source of character
  entities for speaker matching
- [ADR-069](../../architecture/decisions/ADR-069-adaptive-context-dialogue-coach.md) —
  Architectural decisions for this feature
- [ADR-038](../../architecture/decisions/ADR-038-ai-invocation-adoption-contract.md) —
  The enricher pattern this feature consumes
- [ADR-055](../../architecture/decisions/ADR-055-character-voice-contract.md) —
  Voice boundary preserved (descriptive vs. metric)
- [ADR-057](../../architecture/decisions/ADR-057-voice-check-checking-path-contract.md) —
  The metrics-never-reach-generation rule honoured
- [ADR-065](../../architecture/decisions/ADR-065-rule-13-two-method-run-stream-contract.md) —
  The two-method run/stream contract this service follows

## Status & History

- `2026-05-19` — Added to registry as planned feature (rough sketch).
- `2026-07-19` — **Detailed** against [ADR-069](../../architecture/decisions/ADR-069-adaptive-context-dialogue-coach.md).
  Implementation paths filled in; technical section enriched; the
  feature is now specified as the pilot consumer of the
  `AdaptiveContext` contract. Status changed `planned → in-progress`.
