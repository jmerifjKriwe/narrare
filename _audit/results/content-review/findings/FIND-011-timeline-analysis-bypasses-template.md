# FIND-011 — Timeline analysis bypasses the governed planning timeline template

Priority: 🔴 High
Status: identified / open
Source: CR-04 §3, §4 (2026-06-12)

## Finding

The repository contains a governed bundled prompt at `packages/core/narrare_core/prompts/_bundled/planning/en/timeline/system.md`, but `TimelineAnalysisService.generate_timeline()` does not use it. Instead, it builds the actual runtime task prompt inline with f-strings and passes that string directly to `TimelineAgent.run()`.

## Evidence

- `packages/core/narrare_core/prompts/_bundled/planning/en/timeline/system.md:1-18` has governed prompt frontmatter and context variables for project, genre, language, and writing language.
- `packages/core/narrare_core/prompts/_bundled/planning/en/timeline/system.md:34-48` expects `chapter_summaries`, `entity_events`, and `culture_guidelines`; `timeline/system.md:50-100` defines timeline-analysis instructions and output shape.
- `apps/api/narrare/planning/timeline_analysis_service.py:117-134` constructs the runtime prompt inline with f-strings for project title, genre, language, and chapter context, then passes it directly to `TimelineAgent.run()`.
- `packages/core/narrare_core/prompts/route_table.py:136` routes `LLMIntent.PLAN` to `planning/outline`, not the timeline template.
- `just check-prompts` can pass because the template file is structurally valid, not because it is used by runtime.

## Root Cause

Timeline planning has a template artifact but lacks a route-level integration contract connecting the feature runtime to that template. This splits the prompt source of truth: reviewers see a standards-compliant template, while the actual service sends a different inline prompt.

## User Impact

- Template/frontmatter improvements to `planning/en/timeline/system.md` may not affect production behavior.
- Output-language, KB relationships, entity events, user preferences, and avoidance constraints defined in the template can be omitted from runtime.
- RULE-02/ADR-026 separation is weakened: feature-specific task instructions live in app-layer service code instead of the PromptComposer cascade.
- Users can receive weaker timeline analysis than the reviewed template promises, especially for long projects where entity events, relationships, and culture/preferences should shape the chronology assessment.

## Sustainable Recommendation

Route timeline analysis through `PromptComposer` using a governed context mode for `LLMIntent.PLAN` or a dedicated timeline intent if architecture approves it. If the current template is not meant to be routeable, mark it explicitly as non-routeable/deprecated and move the runtime instructions into an ADR-026-compliant agent instruction/template path.

Acceptance criteria:

1. Runtime timeline generation uses the same prompt surface that reviewers and prompt-management tools expose.
2. Dynamic chapter summaries and entity events are passed as `PromptContext` variables or agent deps, not assembled as feature instructions in `apps/api`.
3. The prompt-surface manifest records the timeline route or explicit non-routeable rationale.
4. Regression tests prove the bundled timeline template affects the generated system prompt.

## Related CR Task

- `CR-AUFG-04-08`

## Related Findings

- Cross-references FIND-010 because both findings require prompt-surface contract/checker strengthening: existing prompt artifacts are valid, but runtime does not use the audited surface.
