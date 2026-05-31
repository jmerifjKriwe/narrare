<!-- Context: narrare-dev/lookup/feature-index | Priority: high | Source: docs/features/INDEX.md | Updated: 2026-05-30 -->

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

## Knowledge Base

| ID | Feature | Status |
|----|---------|--------|
| KB-001 | KB Entity CRUD | ✅ |
| KB-002 | Assisted KB Creation | ✅ |
| KB-003 | AI: Improve KB Entry | ✅ |
| KB-004 | AI: KB Consistency Check | ✅ |
| KB-005 | Proactive KB Suggestions | ✅ |
| KB-006 | Worldbuilding Assistant | ✅ |
| KB-007 | Entity Extraction from Chapters | ✅ |
| KB-008 | Knowledge Graph | ✅ |
| WIKI-001 | LLM Wiki — Precomputed Context Layer | 🔨 |

## Analysis

| ID | Feature | Status |
|----|---------|--------|
| ANAL-001 | Beta Reader Simulation | ✅ |
| ANAL-002 | Sentiment Analysis | ✅ |
| ANAL-003 | Readability Analysis | 📋 |
| ANAL-004 | POV Analysis | 📋 |
| ANAL-005 | Coreference Analysis | 📋 |
| ANAL-006 | Sensitivity Review | 📋 |
| ANAL-007 | Author Voice Profiling | 📋 |
| ANAL-008 | Character Voice Profiling | 📋 |
| ANAL-009 | Voice Drift Detection | 📋 |
| ANAL-010 | Literary Analysis Suite | 📋 |
| ANAL-011 | Plot Analysis | 📋 |

## Planning, Generation, Consistency, Learning, Prompts, IO, Settings, Analytics

| Area | IDs | Stable | Planned |
|------|-----|--------|---------|
| Planning | PLAN-001–005 | PLAN-003, 005 | PLAN-001, 002, 004 |
| Generation | GEN-001–002 | GEN-001 | GEN-002 |
| Consistency | CONS-001–002 | CONS-001 | CONS-002 |
| Learning | LEARN-001–002 | LEARN-001 | LEARN-002 |
| Prompts | PROMPT-001–002 | Both | — |
| Import/Export | IO-001–003 | — | All |
| Settings | SET-001–005 | SET-001–003, 005 | — |
| Analytics | STATS-001–002 | — | Both |

**Related**: `narrare-dev/lookup/adr-index`, `narrare-dev/lookup/mvp-plan`
