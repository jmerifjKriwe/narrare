<!-- Context: narrare-dev/lookup/feature-index | Priority: high | Source: docs/features/INDEX.md | Updated: 2026-06-06 -->

# Feature Registry — Index

> Complete reference: `docs/features/INDEX.md`
> Load individual feature files only when implementation details are needed.

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Stable — fully implemented, tested, documented |
| 🔨 | In-progress — being implemented now |
| 📋 | Planned — specified, not started |
| 💡 | Idea — not yet specified |
| ⛔ | Deprecated — removed or replaced |

## Core Infrastructure

| ID | Feature | Status |
|----|---------|--------|
| INFRA-001 | LLM Gateway | ✅ |
| INFRA-002 | Unified Prompt System | ✅ |
| INFRA-003 | Context Assembly Pipeline | ✅ |
| INFRA-004 | Embedding Store | ✅ |
| INFRA-005 | Memory Layer (mem0) | ✅ |
| INFRA-010 | Prompting Locally | ✅ |
| INFRA-011 | AI Feature Stabilization Program | ✅ |
| INFRA-012 | Prompt Governance Hardening | 🔨 |
| INFRA-013 | AI Invocation Adoption Contract | 🔨 |

> **AI feature freeze lifted:** INFRA-011 gates passed and the ADR-027 freeze-lift
> review completed on 2026-06-03. New AI-feature work may resume under ratcheted
> governance: no new prompt/adoption warning growth, unapproved architecture
> exceptions, frontend file-size violations, REST-only AI streaming paths, or
> workaround implementations.

## Setup & Onboarding

| ID | Feature | Status |
|----|---------|--------|
| SETUP-001 | Setup Wizard (5-step) | ✅ |
| SETUP-002 | Demo Projects | ✅ |
| SETUP-003 | Project Import | 📋 |
| SETUP-004 | AI Provider Configuration | ✅ |

## Writing

| ID | Feature | Status |
|----|---------|--------|
| WRITE-001 | Writing Editor | ✅ |
| WRITE-002 | AI: New Chapter Generation | ✅ |
| WRITE-003 | AI: Extend Chapter | ✅ |
| WRITE-004 | AI: Rewrite Selection | ✅ |
| WRITE-005 | Interactive Writing Session | ✅ |
| WRITE-006 | Co-Author Mode | 📋 |
| WRITE-007 | Inline AI Suggestions | ✅ |
| WRITE-008 | Multi-Draft Generation | 📋 |
| WRITE-009 | Writer's Block Tools | 📋 |
| WRITE-010 | Voice Consistency Checker | 📋 |
| WRITE-011 | Volume Management | ✅ |
| WRITE-012 | Chapter Summary | ✅ |
| WRITE-014 | Context Inspector | ✅ |

## Chat

| ID | Feature | Status |
|----|---------|--------|
| CHAT-001 | Free-Form Chat | 🔨 |

## Knowledge Base

| ID | Feature | Status |
|----|---------|--------|
| KB-001 | KB Entity CRUD | ✅ |
| KB-002 | Assisted KB Creation (AI-guided creation) | ✅ |
| KB-003 | AI: Improve KB Entry | ✅ |
| KB-004 | AI: KB Consistency Check | ✅ |
| KB-005 | Proactive KB Suggestions | ✅ |
| KB-006 | Worldbuilding Assistant | ✅ |
| KB-007 | Entity Extraction from Chapters | ✅ |
| KB-008 | Knowledge Graph | ✅ |
| KB-009 | KB Entity Merge / Deduplication | ✅ |
| KB-010 | Editor-Integrated Knowledge Graph | 💡 |
| WIKI-001 | LLM Wiki — Precomputed Context Layer | ✅ |

## Analysis

| ID | Feature | Status |
|----|---------|--------|
| ANAL-001 | Beta Reader Simulation | ✅ |
| ANAL-002 | Sentiment Analysis | ✅ |
| ANAL-003 | Readability Analysis | ✅ |
| ANAL-004 | POV Analysis | ✅ |
| ANAL-005 | Coreference Analysis | 📋 |
| ANAL-006 | Sensitivity Review | 📋 |
| ANAL-007 | Author Voice Profiling | 📋 |
| ANAL-008 | Character Voice Profiling | 📋 |
| ANAL-009 | Voice Drift Detection | 📋 |
| ANAL-010 | Literary Analysis Suite | 📋 |
| ANAL-011 | Plot Analysis | 📋 |

## Planning

| ID | Feature | Status |
|----|---------|--------|
| PLAN-001 | Scene Planning | 📋 |
| PLAN-002 | Narrative Gap Analysis | 📋 |
| PLAN-003 | Story Structure Visualization | ✅ |
| PLAN-004 | Timeline Management | 🔨 |
| PLAN-005 | Storyboard View | ✅ |
| PLAN-006 | Character Arc Analysis | ✅ |

> **Note:** PLAN-003 (Structure) and PLAN-005 (Storyboard) were implemented together as a merged feature. PLAN-004 has partial integration (`timeline_position` field) and AI-powered timeline analysis (TimelineAgent) — full timeline management remains future work. PLAN-006 is backend-only with no UI yet.

## AI Assist (Standalone Operations)

| ID | Feature | Status |
|----|---------|--------|
| ASSIST-001 | Plot Consistency Check | 📋 |
| ASSIST-002 | Title Suggestions | 📋 |
| ~~ASSIST-003~~ | ~~Story Chat Assistant~~ | ⛔ |

> **Note:** ASSIST-003 superseded by CHAT-001 (Free-Form Chat).

## Generation, Consistency, Learning, Prompts, IO, Settings, Analytics

| Area | IDs | Stable | In-progress | Planned | Idea | Deprecated |
|------|-----|--------|-------------|---------|------|------------|
| Generation | GEN-001–002 | GEN-001 | — | GEN-002 | — | — |
| Consistency | CONS-001–002 | CONS-001 | — | CONS-002 | — | — |
| Learning | LEARN-001–002 | LEARN-001 | — | LEARN-002 | — | — |
| Prompts | PROMPT-001–002 | Both | — | — | — | — |
| Import/Export | IO-001–003 | — | — | All | — | — |
| Settings | SET-001–005 | SET-001–003, 005 | — | — | — | — |
| Analytics | STATS-001–002 | — | — | Both | — | — |

**Related**: `narrare-dev/lookup/adr-index`, `narrare-dev/lookup/mvp-plan`
