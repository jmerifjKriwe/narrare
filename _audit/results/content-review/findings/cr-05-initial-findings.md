# CR-05: Finding Index — Current Status

> **Last updated:** 2026-06-12
> **Audit:** Content Review CR-05 consolidation after CR-01 through CR-04 rerun
> **Current-state source:** this file plus the individual `FIND-*.md` files in this directory.

## Open / active findings

| Finding | Status | Priority | Related CR tasks | Current action |
|---|---|---|---|---|
| [FIND-001](FIND-001-output-limits-not-enforced.md): Output token limits configured but not reliably enforced | Open / identified | 🔴 High | CR-AUFG-03-01, CR-AUFG-03-06, CR-AUFG-03-07 | Enforce resolved output limits at the LLM gateway/agent boundary and bind evidence to the same invocation. |
| [FIND-009](FIND-009-timeline-consistency-gap.md): Timeline/graph consistency context remains incomplete | Partially resolved / scope refreshed | 🟡 Medium | CR-AUFG-03-05, CR-AUFG-04-01, CR-AUFG-04-06, CR-AUFG-04-07 | Keep current timeline bridge; add timeline/graph envelope, provenance, stale/deleted reference handling, and typed conflict semantics. |
| [FIND-010](FIND-010-chat-prompt-surface-drift.md): Chat prompt surface drifts across runtime, manifest, and prompt management | Open / identified | 🔴 High | CR-AUFG-02-04, CR-AUFG-04-04, CR-AUFG-04-05 | Align route, manifest path, duplicate templates, prompt IDs, checker rules, and chat system-injection path. |
| [FIND-011](FIND-011-timeline-analysis-bypasses-template.md): Timeline analysis bypasses governed template | Open / identified | 🔴 High | CR-AUFG-04-08 | Route runtime timeline generation through PromptComposer/governed planning template or explicitly mark the template non-routeable. |

## Resolved / historical findings

These remain closed. Do not reopen them from stale CR wording unless new code evidence contradicts the resolution.

| Finding | Status | Resolution |
|---|---|---|
| Legacy FIND-001: Missing PromptComposer template targets | ✅ Resolved / file deleted | Route table governs routeable/context-required/non-routeable intents. Current open FIND-001 is a new output-limit enforcement finding. |
| Legacy FIND-002: Production inline prompt fallbacks | ✅ Resolved / file deleted | Old consistency/extraction inline fallbacks removed. `writing_graph_prompts.py` fallback remains a CR-02 task to keep test/bare-bones-only or fail-fast in production. |
| [FIND-003](FIND-003-mem0-preference-injection-not-wired.md): mem0 preference DI not wired | ✅ Resolved | API prompt DI now creates `PreferenceService` when mem0 and provider credentials are available. Remaining CR-03 preference issue is enriched-context alignment, not this old DI gap. |
| [FIND-004](FIND-004-output-token-profiles-under-calibrated.md): Output token profiles under-calibrated | ✅ Resolved | Intent profile calibration is complete. Current FIND-001 covers enforcement, not profile coverage. |
| Legacy FIND-005: Template variable registry gaps | ✅ Resolved / file deleted | Variable taxonomy and alias registry exist. |
| Legacy FIND-006: Generated `kb_suggested` not consumed | ✅ Resolved / file deleted | Writing templates consume `kb_suggested`; remaining work is lower-priority/generated-candidate wording and evidence alignment. |
| [FIND-007](FIND-007-project-writing-profile-not-consistently-defined.md): Project writing profile not consistently defined | ✅ Resolved | ProjectWritingProfile is defined and consumed by profile/writing/prompt context paths. Remaining voice/profile freshness work is a CR-04 task, not this old finding. |
| Legacy FIND-008: Cross-feature precedence under-specified | ✅ Resolved / file deleted | RULE-22 and prompt standards define precedence. Remaining work is per-boundary integration contracts. |

## CR-01/CR-02 task-only items not promoted to new FIND files

- CR-01 template-quality tasks remain tracked as `CR-AUFG-01-01` through `CR-AUFG-01-06`.
- CR-02 chat prompt-injection drift is consolidated into FIND-010 because the source-of-truth drift and channel injection must be fixed together.
- CR-02 worldbuilding phase2, temporal-consistency prompt loader, and `writing_graph_prompts.py` fallback concerns remain CR task backlog items unless a later review promotes them to formal finding files.

## Next prompt recommendation

Proceed with **CR-07** next.
