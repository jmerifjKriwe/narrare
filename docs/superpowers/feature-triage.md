# Feature Triage — v1 to v2

> Created 2026-10-31. Source: `docs/features/INDEX.md` (v1 feature registry) + v2 build plan `docs/superpowers/plans/2026-10-21-v2-build.md`.
> Core scope per build plan: writing, knowledge, chat, setup. Everything else is "re-decide on merit" — this table is that decision.

## Legend

| Symbol | Meaning |
|---|---|
| **build** | Port/build into v2 |
| **later** | Defer (after core features / on demand) |
| **skip** | Do not port |
| **dev-infra** | Dev/governance infrastructure, not a user feature |

## Summary

- **build:** 72
- **later:** 17
- **skip:** 8
- **dev-infra:** 3
- **Total:** 100

## Decisions from the dialog

- Series (SERIES-001..004): do not drop; treat as a **post-MVP program** (may become necessary).
- ONBOARD-001: **full tour** (good overview of highlights), not just slim.
- LEARN-001/002 and INFRA-005: deferred until core features are stable.
- KB-010, WRITE-013, ASSIST-003: dropped (idea / docs only / superseded).

## Core Infrastructure

| ID | Feature | User-facing benefit | Decision |
|---|---|---|---|
| INFRA-001 | LLM Gateway | Unified AI access with retries/model routing; basis for all AI features | **build** |
| INFRA-002 | Unified Prompt System | Adjust prompts globally (genre/style) instead of per feature | **build** |
| INFRA-003 | Context Assembly Pipeline | AI knows characters/world/prior chapters without manual pinning | **build** |
| INFRA-004 | Embedding Store | Semantic search (synonymous terms) | **build** |
| INFRA-005 | Memory Layer (Rejection Learning) | AI learns from accept/reject; after core features are stable | **later** |
| INFRA-006 | A2A Integration | External agents drive Narrare — niche, high effort | **skip** |
| INFRA-007 | Background Tasks | Embeddings/summaries in background, no typing stall | **build** |
| INFRA-008 | MCP Integration | Connect Claude Desktop etc. — niche | **skip** |
| INFRA-009 | Proactive Context Loading | Standalone deprecated; part of KB-005 | **skip** |
| INFRA-010 | Prompting Locally | Power users: own prompts per project | **build** |
| INFRA-011 | AI Feature Stabilization Program | Quality/governance gates (not a user feature) | **dev-infra** |
| INFRA-012 | Prompt Governance Hardening | Quality/governance gates (not a user feature) | **dev-infra** |
| INFRA-013 | AI Invocation Adoption Contract | Quality/governance gates (not a user feature) | **dev-infra** |

## Setup & Onboarding

| ID | Feature | User-facing benefit | Decision |
|---|---|---|---|
| SETUP-001 | Setup Wizard | Guided first-run config (port rest of 5-step wizard) | **build** |
| SETUP-002 | Demo Projects | Real sample project to explore (no blank-page problem) | **build** |
| SETUP-003 | Project Import | Import existing manuscript instead of copy-paste | **build** |
| SETUP-004 | AI Provider Configuration | Provider/creds/model in UI instead of config files | **build** |
| ONBOARD-001 | Onboarding & AI Introduction | Full tour of AI highlights; demos discoverable in dashboard | **build** |

## Writing

| ID | Feature | User-facing benefit | Decision |
|---|---|---|---|
| WRITE-001 | Writing Editor | Writing surface with autosave, word count, extension points | **build** |
| WRITE-002 | AI: New Chapter Generation | First draft from outline/prompt (breaks blank page) | **build** |
| WRITE-003 | AI: Extend Chapter | Seamless continuation at cursor position | **build** |
| WRITE-004 | AI: Rewrite Selection | Rewrite selection (tone/style), 1-3 variants | **build** |
| WRITE-005 | Interactive Writing Session | Conversational co-writing | **build** |
| WRITE-006 | Co-Author Mode | Diff-style changes, granular accept/reject | **build** |
| WRITE-007 | Inline AI Suggestions | Ghost-text autocomplete while typing | **build** |
| WRITE-008 | Multi-Draft Generation | Compare 2-5 variants of a passage (nice-to-have) | **later** |
| WRITE-009 | Writer's Unblock Tools | 3-5 story-direction suggestions when stuck | **build** |
| WRITE-010 | Voice Consistency Checker | Check dialogue against character voice | **build** |
| WRITE-011 | Volume Management | Multiple volumes in one project, shared KB | **build** |
| WRITE-012 | Chapter Summary | Summaries for context/review | **build** |
| WRITE-013 | Writing Workflows | Process docs only, not a feature | **skip** |
| WRITE-014 | Context Inspector | Transparency: what the AI "sees" | **build** |

## Series

| ID | Feature | User-facing benefit | Decision |
|---|---|---|---|
| SERIES-001 | Series Foundation | Multiple novels as a series with shared canon KB (post-MVP program) | **later** |
| SERIES-002 | Series Generation Context | AI gets prior volumes when writing the next one | **later** |
| SERIES-003 | Series Voice Hierarchy | Shared series voice + per-volume nuances | **later** |
| SERIES-004 | Series Cross-Novel Drift | Check a volume against canon/voice for drift | **later** |

## Chat

| ID | Feature | User-facing benefit | Decision |
|---|---|---|---|
| CHAT-001 | Free-Form Chat | Conversation about plot/worldbuilding/craft with story context | **build** |

## Notes

| ID | Feature | User-facing benefit | Decision |
|---|---|---|---|
| NOTES-001 | Scratchpad | Capture thoughts independent of any novel | **build** |

## Knowledge Base

| ID | Feature | User-facing benefit | Decision |
|---|---|---|---|
| KB-001 | KB Entity Management | Structured world (6 types), search, relationships | **build** |
| KB-002 | Assisted KB Creation | AI interview instead of blank forms | **build** |
| KB-003 | AI: Improve KB Entry | Fill gaps, improve entries | **build** |
| KB-004 | AI: KB Consistency Check | Find contradictions in the KB | **build** |
| KB-005 | Proactive KB Suggestions | Auto-suggest relevant entries while writing | **build** |
| KB-006 | Worldbuilding Assistant | Specialized worldbuilding UI + AI | **build** |
| KB-007 | Entity Extraction from Chapters | Extract facts from chapters into the KB automatically | **build** |
| KB-008 | Knowledge Graph Visualization | Visualize relationships (Cytoscape) | **build** |
| KB-009 | KB Entity Merge / Deduplication | Find and merge duplicates | **build** |
| KB-010 | Editor-Integrated Knowledge Graph | Idea only; KB-008 first | **skip** |
| WIKI-001 | LLM Wiki — Precomputed Context Layer | ~85% token reduction; evaluate whether context assembly suffices first | **later** |

## Analysis

| ID | Feature | User-facing benefit | Decision |
|---|---|---|---|
| ANAL-001 | Beta Reader Simulation | AI feedback like a beta reader, instantly | **build** |
| ANAL-002 | Sentiment Analysis | Make emotional arcs visible | **build** |
| ANAL-003 | Readability Analysis | Measure complexity + AI suggestions | **build** |
| ANAL-004 | POV Analysis | Find head-hopping, knowledge leakage | **build** |
| ANAL-005 | Coreference Analysis | Find ambiguous pronouns | **build** |
| ANAL-006 | Sensitivity Review | Flag stereotypes/tropes (optional/sensitive) | **later** |
| ANAL-007 | Author Voice Profiling | Capture author voice for AI generation | **build** |
| ANAL-008 | Character Voice Profiling | Capture character voices | **build** |
| ANAL-009 | Character Voice Drift Detection (Phase 1) | Track voice drift across chapters | **build** |
| ANAL-010 | Literary Analysis Suite | Aggregator suites (single analyses first) | **later** |
| ANAL-011 | Plot Analysis Suite | Aggregator suites (single analyses first) | **later** |

## Planning

| ID | Feature | User-facing benefit | Decision |
|---|---|---|---|
| PLAN-001 | Scene Planning | Plan scenes with goals/conflicts/beats before writing | **build** |
| PLAN-002 | Narrative Gap Analysis | Find missing scenes/threads/transitions | **build** |
| PLAN-003 | Story Structure Visualization | Visualize acts/arcs, reorganize | **build** |
| PLAN-004 | Timeline Management | Time/age/chronology, consistency checks | **build** |
| PLAN-005 | Storyboard View | Plan vs. written, drag&drop, stage columns | **build** |
| PLAN-006 | Character Arc Analysis | Structured character development | **build** |

## AI Assist

| ID | Feature | User-facing benefit | Decision |
|---|---|---|---|
| ASSIST-001 | Plot Consistency Check | Aggregator (single analyses first) | **later** |
| ASSIST-002 | Title Suggestions | Generate titles for novel/chapter/scene | **build** |
| ASSIST-003 | Story Chat Assistant | Superseded by CHAT-001 | **skip** |
| ASSIST-004 | Dialogue Coach | Improve dialogue subtext/flow/voice | **build** |

## Generation

| ID | Feature | User-facing benefit | Decision |
|---|---|---|---|
| GEN-001 | Character/Place Name Generator | Culturally aware, deduplicated names | **build** |
| GEN-002 | Research Assistant | Research in writing context (web integration) | **later** |

## Consistency

| ID | Feature | User-facing benefit | Decision |
|---|---|---|---|
| CONS-001 | Consistency Checker | Contradictions (character/timeline/world/plot) | **build** |
| CONS-002 | Custom Consistency Rules | Custom check rules per story | **later** |

## Learning & Adaptation

| ID | Feature | User-facing benefit | Decision |
|---|---|---|---|
| LEARN-001 | Feedback & Learning Loop | AI learns from accept/reject (depends on INFRA-005) | **later** |
| LEARN-002 | Adaptivity Dashboard | Make adaptivity visible/controllable (depends on INFRA-005) | **later** |

## Prompt Customization

| ID | Feature | User-facing benefit | Decision |
|---|---|---|---|
| PROMPT-001 | File-based Prompt Overrides | Customize prompts via files (version-controllable) | **build** |
| PROMPT-002 | User DB Prompt Templates | Customize prompts in the UI | **build** |
| PROMPT-003 | Prompt Customization UX | Explain variables, preview, live test | **build** |

## Import / Export

| ID | Feature | User-facing benefit | Decision |
|---|---|---|---|
| IO-001 | Manuscript Export | Export manuscript (PDF/ePub/DOCX/MD) | **build** |
| IO-002 | Corpus Analysis Pass | Extract KB from an existing manuscript | **build** |
| IO-003 | External Sync | Two-way sync with an external folder | **later** |

## Internationalization

| ID | Feature | User-facing benefit | Decision |
|---|---|---|---|
| I-Copy-001 | User-Selectable UI Formality (du / Sie) | Choose address register (du/Sie) | **build** |

## Settings & Configuration

| ID | Feature | User-facing benefit | Decision |
|---|---|---|---|
| SET-001 | User Settings | Provider/model/preferences | **build** |
| SET-002 | Project Settings | Project-specific overrides | **build** |
| SET-003 | Per-task Model Configuration | Choose model per task | **build** |
| SET-004 | Keyboard Shortcuts | Customize shortcuts (basic shortcuts first) | **later** |
| SET-005 | Configurable Token Limits | Adjust token budgets | **build** |
| KEYBOARD-001 | Keyboard Consistency | Consistent AI shortcuts (Ctrl+Enter etc.) | **build** |

## Analytics

| ID | Feature | User-facing benefit | Decision |
|---|---|---|---|
| STATS-001 | Writing Statistics | Daily words, streaks, word goal | **build** |
| STATS-002 | AI Cost Tracking | Monthly AI cost by feature/model | **build** |

## Adapter / Integration

| ID | Feature | User-facing benefit | Decision |
|---|---|---|---|
| ADAPTER-001 | MCP (Model Context Protocol) Adapter | MCP/A2A adapters (niche) | **skip** |
| ADAPTER-002 | A2A (Agent-to-Agent) Adapter | MCP/A2A adapters (niche) | **skip** |

## AI-UX (CR-AUFG-07)

| ID | Feature | User-facing benefit | Decision |
|---|---|---|---|
| CR-AUFG-07-18 | Standardized Diff View across AI Outputs | Consistent diff UI for all AI changes | **build** |
| CR-AUFG-07-19 | Prompt History | Compare/restore prompt-override versions | **build** |
| CR-AUFG-07-20 | Slash Commands for AI Actions | Slash commands (/continue etc.) in the editor | **build** |
| CR-AUFG-07-21 | SessionPanel Server-side Stop and WebSocket Recovery | Server-side stop, reconnect on disconnect | **build** |
| CR-AUFG-07-22 | Regenerate with Style Variants | Style variants (more lyrical, tighter, ...) on regenerate | **build** |
| CR-AUFG-07-23 | Emotional Intensity Curve | Visualize ANAL-002 intensity data | **build** |
| CR-AUFG-07-24 | AI Feedback Rating Expansion | Ratings in more features (co-author, KB, chat) | **build** |

## Supplementary (not user features)

| File | Kind | Decision |
|---|---|---|
| `remediation/cr-02-prompt-path-retrofit.md` | Prompt path retrofit (CR-02) | **dev-infra** |
| `remediation/cr-08-configuration-effect-drift.md` | Config effect drift (CR-08) | **dev-infra** |
| `remediation/ui-ux-remediation-panel-shell-architecture.md` | Panel shell architecture | **dev-infra** |
| `remediation/ui-ux-remediation-phase-b-ui-primitives.md` | UI primitives phase B | **dev-infra** |
| `auth/auth-flake-fix.md` | Auth flake fix | **skip** |
| `planning/PLAN-004-architecture.md` | Architecture supplement for PLAN-004 | **dev-infra** |

## Implementation status in v2 (as of 2026-10-31)

Cross-check against `app/capabilities/*` and the port ledger in `docs/superpowers/plans/2026-10-21-v2-build.md`. Includes features with partial or divergent implementation to make gaps visible.

| Feature | v2 status | Evidence |
|---|---|---|
| CHAT-001 | partial | one question over KB, streamed answer with sources; no persisted session |
| CONS-001 | ported | consistency findings (ChecksPanel) |
| INFRA-001 | ported | kernel/llm (provider resolution, streaming, audit) |
| INFRA-002 | ported | kernel/prompts (registry, render, overrides) |
| INFRA-003 | partial | context allocation in kernel; 5-tier pipeline not evident |
| INFRA-004 | ported | knowledge documents: upload, chunk, embed, pgvector search, reembed |
| INFRA-007 | partial | durable job lane (extraction/consistency jobs) |
| INFRA-009 | ported as KB-005 | proactive suggestions already cover it |
| INFRA-010 | partial | DB overrides via prompts capability; file-based override not evident |
| IO-001 | not ported | archive export exists (interchange), different scope (manuscript PDF/ePub/DOCX/MD not built) |
| KB-001 | ported | entity CRUD (8 types), relations, merge; UI EntitiesPanel |
| KB-002 | not started | no interview/assisted creation |
| KB-003 | not started | no improve entry |
| KB-004 | ported | consistency check + findings review (ChecksPanel) |
| KB-005 | ported | proactive suggestions endpoint + UI |
| KB-006 | not started | no worldbuilding assistant |
| KB-007 | ported | extraction endpoint + ExtractionPanel |
| KB-008 | partial | relations panel; no graph visualization |
| KB-009 | ported | merge endpoint |
| KB-010 | partial | knowledge dock ("wissen") beside editor; no graph |
| PROMPT-001 | ported | prompts capability overrides |
| PROMPT-002 | ported | prompts capability DB templates + diff |
| SET-001 | partial | locale + provider profiles; minimal user settings surface |
| SET-002 | not started | no project-level overrides evident |
| SET-003 | ported | provider profiles, task assignments, effective task endpoints |
| SET-005 | partial | token limits via task effective endpoints |
| SETUP-001 | partial | create path only (local user + first novel); 5-step wizard/demo/provider UI not ported |
| SETUP-003 | not ported | archive import exists (interchange), different scope (manuscript import not built) |
| WRITE-001 | partial | novels/chapters, TipTap editor, autosave; formatting bar & chapter versions not ported |
| WRITE-003 | partial | one streamed continuation; length options/context controls not ported |

## Contradictions / tensions with the v2 implementation

- Build plan (`docs/superpowers/plans/2026-10-21-v2-build.md`) states core scope = writing, knowledge, chat, setup and lists consistency, prompts, analytics, import/export, adapters, analysis, planning, series, notes, wiki and adaptive features as "outside core scope". In practice v2 already ships prompts, settings, consistency checks, extraction, merge, suggestions and a knowledge dock — core has expanded. The triage "build" decisions for these are already being realized; the build plan scope statement is stale and should be reconciled.
- KB-010 is marked "skip" (idea), and the build plan parks it. However v2 ships an editor-integrated knowledge dock (`wissen` route beside the editor) that partially delivers KB-010 intent (entities beside the editor) without the graph. "skip" may be too strong; consider "partial via dock".
- WRITE-013 and KB-010 are marked "skip" while the build plan calls them "parked" (not now, but revisitable). "skip" implies never; align wording or keep as a conscious deviation.
- IO-001 and SETUP-003 are marked "build" but v2 export/import are archive interchange (data portability), not manuscript export/import. Manuscript IO remains unbuilt; the archive feature is a v2-native addition outside the v1 feature list.
- KB-008 marked "build" (graph visualization) but v2 has only a relations panel, no graph viz. Partial.
- KB-002/003/006 marked "build" but none is built (no interview, improve, or worldbuilding assistant).
- SET-002 marked "build" but v2 settings is user-level only; no project-level overrides evident.
- Many "build" items (ANAL-*, PLAN-*, STATS-*, CONS-002, GEN-002, etc.) sit outside the stated core scope and have no v2 home. They need explicit prioritization before implementation; the triage alone does not schedule them.
- INFRA-009 marked "skip" (merged into KB-005) — consistent: v2 suggestions endpoint exists.
## Shortlist: "build" (core port order)

INFRA-001, INFRA-002, INFRA-003, INFRA-004, INFRA-007, INFRA-010, SETUP-001, SETUP-002, SETUP-003, SETUP-004, ONBOARD-001, WRITE-001, WRITE-002, WRITE-003, WRITE-004, WRITE-005, WRITE-006, WRITE-007, WRITE-009, WRITE-010, WRITE-011, WRITE-012, WRITE-014, CHAT-001, NOTES-001, KB-001, KB-002, KB-003, KB-004, KB-005, KB-006, KB-007, KB-008, KB-009, ANAL-001, ANAL-002, ANAL-003, ANAL-004, ANAL-005, ANAL-007, ANAL-008, ANAL-009, PLAN-001, PLAN-002, PLAN-003, PLAN-004, PLAN-005, PLAN-006, ASSIST-002, ASSIST-004, GEN-001, CONS-001, PROMPT-001, PROMPT-002, PROMPT-003, IO-001, IO-002, I-Copy-001, SET-001, SET-002, SET-003, SET-005, KEYBOARD-001, STATS-001, STATS-002, CR-AUFG-07-18, CR-AUFG-07-19, CR-AUFG-07-20, CR-AUFG-07-21, CR-AUFG-07-22, CR-AUFG-07-23, CR-AUFG-07-24

(72 features)

## Deferred (later)

INFRA-005, WRITE-008, SERIES-001, SERIES-002, SERIES-003, SERIES-004, WIKI-001, ANAL-006, ANAL-010, ANAL-011, ASSIST-001, GEN-002, CONS-002, LEARN-001, LEARN-002, IO-003, SET-004

(17 features)

## Dropped (skip)

INFRA-006, INFRA-008, INFRA-009, WRITE-013, KB-010, ASSIST-003, ADAPTER-001, ADAPTER-002

(8 features)
