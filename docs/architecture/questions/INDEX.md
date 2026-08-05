# Open Questions — Index

> Location: `docs/architecture/questions/INDEX.md`
> Maintained by: Architecture Agent

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| 🔴 | Blocking — blocks specific implementation |
| 🟡 | Open — needs resolution before relevant phase |
| 🔵 | In Discussion |
| ✅ | Resolved — see question file for resolution |
| 🗄️ | Archived |

---

## Active Questions

| ID | Question | Status | Blocks | Raised |
|----|---------|--------|--------|--------|
| [Q-001](Q-001-to-Q-004.md#q-001--how-does-mcp-authenticate-against-the-api) | How does MCP authenticate against the API? | 🟡 | `apps/mcp/` (post-MVP) | init |
| [Q-002](Q-001-to-Q-004.md#q-002--does-a2a-require-streaming-support) | Does A2A protocol require streaming support? | 🟡 | `apps/a2a/` (post-MVP) | init |
| [Q-003](Q-001-to-Q-004.md#q-003--embedding-provider-abstraction-from-day-one) | Should embeddings be provider-agnostic from day one? | ✅ | `core/llm/embeddings.py` | init |
| [Q-011](Q-011-distribution-strategy.md) | Wie wird Narrare für nicht-technische Nutzer zugänglich? | 🟡 | Zielgruppen-Positionierung, Post-MVP Distribution | 2026-06-03 |
| [Q-015](Q-015-user-selectable-copy-tone.md) | User-selectable UI copy tone (familiar vs. neutral) | 🟡 | Nothing (default in PRODUCT.md) | 2026-08-05 |

---

## Resolved Questions

| ID | Question | Resolution | ADR |
|----|---------|-----------|-----|
| [Q-003](Q-001-to-Q-004.md#q-003--embedding-provider-abstraction-from-day-one) | Should embeddings be provider-agnostic from day one? | → Embedding Provider Protocol abstraction | ADR-020 |
| [Q-004](Q-001-to-Q-004.md#q-004--celery-vs-arq-for-background-tasks) | Celery vs arq for background tasks? | → TaskIQ | ADR-007 |
| [Q-005](Q-005-resolved.md) | Does pydantic-ai support GLM-5.1 via z.ai? | → Yes, OpenAI-compatible | — |
| [Q-006](Q-006-configurable-model-routing.md) | Should Model Routing be configurable per user/project/intent? | → Runtime cascade with multi-provider support | ADR-001 (updated) |
| [Q-007](Q-007-writing-context-data-loader.md) | Writing Context Data Loader | → Resolved via `WritingContextAssembler` | — |
| [Q-008](Q-008-auth-store-hydration.md) | Auth Store wird nach Page Reload nicht rehydriert | → Resolved via `AuthProvider.tsx` in Root Layout | — |
| [Q-009](Q-009-to-Q-010.md#q-009--should-chat-conversations-be-project-scoped-or-user-scoped) | Should Chat Conversations Be Project-Scoped or User-Scoped? | → Project-scoped (Option A) | ADR-024 |
| [Q-010](Q-009-to-Q-010.md#q-010--should-the-chat-prompt-support-defr-from-day-one-or-english-only-v1) | Should the Chat Prompt Support DE/FR from Day One or English-Only v1? | → English-only v1 (Option A) | ADR-024 |
| [Q-012](Q-012-prompt-variable-ux.md) | Wie erklären wir dem Nutzer Prompt-Variablen und ermöglichen Reset-to-Default? | → Option A (Manifest) via PROMPT-003 (Post-MVP) | — |
| [Q-013](Q-013-i18n-tone-drift.md) | i18n Tone Drift in Bundled Universal/Meta Prompts (DE/FR) | → universal/{de,fr} aligned to Du/tu (matching meta prompts); §8 Formality Register added to prompt-content-standards.md | — |
| [Q-014](Q-014-cascade-policy-location.md) | Sollte die Model-Routing-Cascade-Logik in Core oder API leben? | → Cascade bleibt in API (Protocol in core, DB-Impl in API ist korrekt per RULE-07) | — |
