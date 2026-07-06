<!-- Context: narrare-dev/lookup/mvp-plan | Priority: critical | Source: docs/mvp/mvp-plan.md | Updated: 2026-06-12 -->

# MVP Plan & Roadmap

> Complete reference: `docs/mvp/mvp-plan.md`

## Definition of Done (MVP — COMPLETE)

The MVP is complete when a developer can:
1. Clone + `just dev-setup` on clean machine
2. `just dev` → WebUI at `http://localhost:3000`
3. Complete 5-step Setup Wizard
4. See demo content in editor/dashboard
5. Write with autosave
6. Login with dev credentials
7. Settings persist across restarts
8. `just test` — all tests pass (2759+: 2113 backend + 646 frontend)
9. `just check` — all constraints pass
10. Generate chapter draft (WRITE-002), manage KB (KB-001), storyboard (PLAN-003/005), record feedback (LEARN-001)

## Phase Summary

| Phase | Name | Status | Key Milestones |
|-------|------|--------|----------------|
| 0 | Repository Foundation | ✅ COMPLETE | Monorepo, pyproject.toml, justfile, pre-commit, CI, devcontainer |
| 1 | Core Infrastructure | ✅ COMPLETE | `packages/core/`: shared types, LLM Gateway, prompt system, schemas |
| 2 | API Foundation | ✅ COMPLETE | `apps/api/`: FastAPI shell, auth (JWT+argon2), novels, chapters, volumes, settings, migrations |
| 3 | Setup Wizard Backend | ✅ COMPLETE | 5-step wizard, 3 demo projects (EN Fantasy, EN SciFi, DE Fantasy), provider validation |
| 4 | Frontend Foundation | ✅ COMPLETE | Next.js 16 App Router, TipTap editor shell, i18n (en/de/fr), light/dark, all pages |
| 5 | Integration, AI & Polish | ✅ COMPLETE | Full feature stack: writing pipeline, KB, planning, learning, 17 ADRs, 19 migrations |
| 6 | Writing Intelligence | ⏳ IN PROGRESS | WRITE-003 (Extend), WRITE-004 (Rewrite) |

## Phase 6 Details (Current)

**WRITE-003: Extend Chapter**
- Endpoint: `POST /api/v1/writing/chapters/{id}/extend`
- Service: `DraftService.extend()` — SSE streaming
- Lengths: Short (100-200w), Medium (300-500w), Long (500-1000w)
- Frontend: Cursor position extraction, inline continuation, accept/reject controls

**WRITE-004: Rewrite Selection**
- Endpoint: `POST /api/v1/writing/rewrite`
- Modes: tone, style, voice, fix, custom → 1-3 alternatives
- No streaming — response as array
- Frontend: Selection detection, mode selector, comparison UI with inline diff, one-click replace

## Post-MVP Roadmap

| Phase | Focus | Key Features |
|-------|-------|-------------|
| Post-1 | Writing Intelligence | Co-Author (WRITE-006), Inline Suggestions (WRITE-007), Entity Extraction (KB-007), Style Adaptation (LEARN-002) |
| Post-2 | Analysis & Feedback | Beta Reader (ANAL-001), POV (ANAL-004), Voice Profiling (ANAL-007/008), Voice Consistency (WRITE-010) |
| Post-3 | Collaboration & Publishing | Export (IO-001), Import (IO-002), Story Chat (ASSIST-003) |
| Post-4 | Platform & Integrations | MCP Server (Q-001), A2A (Q-002), Embedding Abstraction (Q-003), Stats (STATS-001/002) |

## Pre-Made Architecture Decisions

| Decision | Choice |
|----------|--------|
| Editor | ProseMirror via TipTap v3 |
| Frontend state | TanStack Query v5 (server) + Zustand (client) |
| i18n | next-intl, messages in `messages/{locale}.json` |
| Auth | JWT (access in memory, refresh in httpOnly cookie) |
| Autosave | Debounced on editor change, configurable interval |
| New agents | NarrareAgent pattern (ADR-015) |
| MCP/A2A | Service clients only (RULE-12), no new logic |

**Related**: `narrare-dev/lookup/feature-index`, `narrare-dev/concepts/project-vision`, `narrare-dev/lookup/adr-index`
