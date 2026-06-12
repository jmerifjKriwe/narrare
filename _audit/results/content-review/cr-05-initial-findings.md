# Content Review CR-05 – Findings Consolidation

Audit date: 2026-06-12
Scope: consolidate CR-01 through CR-04 findings after the approved rerun.
Method: graph-first discovery, required Narrare context loaded, CR-00 through CR-04 outputs reviewed, then targeted verification of the open finding evidence.

## 1. Current formal findings

| FIND | Priority | Status | Source reviews | Consolidated scope |
|---|---|---|---|---|
| [FIND-001](findings/FIND-001-output-limits-not-enforced.md) | 🔴 High | Open / identified | CR-03 | Output profiles and budget evidence exist, but resolved limits are not reliably enforced at the actual `agent.run()` / `agent.run_stream()` boundary. Supersedes the old resolved FIND-004 calibration issue without reopening it. |
| [FIND-009](findings/FIND-009-timeline-consistency-gap.md) | 🟡 Medium | Partially resolved / scope refreshed | CR-04 | Timeline events now reach consistency prompts, but provenance, graph-edge metadata, stale/deleted references, and typed conflict behavior remain incomplete. |
| [FIND-010](findings/FIND-010-chat-prompt-surface-drift.md) | 🔴 High | Open / identified | CR-02, CR-04 | Chat route, manifest template path, duplicate templates, prompt management IDs, and chat injection follow-up must be reconciled under one prompt-surface contract. |
| [FIND-011](findings/FIND-011-timeline-analysis-bypasses-template.md) | 🔴 High | Open / identified | CR-04 | Timeline analysis has a governed bundled template, but runtime generation still sends an inline service-built prompt. |

## 2. Consolidation decisions

- Legacy FIND-001/FIND-002/FIND-005/FIND-006/FIND-008 remain closed/deleted as recorded in the finding index; do not recreate them from stale wording.
- Legacy FIND-003, FIND-004, and FIND-007 remain resolved. Their files are retained as historical status records and are cross-referenced in the finding index to avoid duplicate reopenings.
- CR-01 produced prompt-quality tasks (`CR-AUFG-01-01` through `CR-AUFG-01-06`) but no separate formal FIND file in this consolidation pass. Those tasks are template-level improvements unless later evidence shows a broader root cause.
- CR-02 produced adoption-drift tasks. The chat-related part is consolidated into FIND-010. Worldbuilding phase2, temporal-consistency prompt loading, and writing-graph fallback tasks remain CR task backlog items rather than duplicate finding files in this pass.
- CR-03's formal new finding is FIND-001. Other CR-03 items remain tracked as related CR tasks unless promoted by a later review.
- CR-04's formal new findings are FIND-010 and FIND-011; FIND-009 was refreshed rather than duplicated.

## 3. Newly discovered findings in this CR-05 pass

No additional finding was discovered during consolidation. CR-05 updated the existing finding files and status index for coherence, root cause, evidence, user impact, sustainable recommendation, and CR task linkage.

## 4. Next prompt recommendation

Proceed with **CR-07** next, per the approved content-review run order.
