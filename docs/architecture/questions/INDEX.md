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
| [Q-003](Q-001-to-Q-004.md#q-003--embedding-provider-abstraction-from-day-one) | Should embeddings be provider-agnostic from day one? | 🟡 | `core/llm/embeddings.py` (post-MVP) | init |

---

## Resolved Questions

| ID | Question | Resolution | ADR |
|----|---------|-----------|-----|
| [Q-004](Q-001-to-Q-004.md#q-004--celery-vs-arq-for-background-tasks) | Celery vs arq for background tasks? | → TaskIQ | ADR-007 |
| [Q-005](Q-005-resolved.md) | Does pydantic-ai support GLM-5.1 via z.ai? | → Yes, OpenAI-compatible | — |
| [Q-006](Q-006-configurable-model-routing.md) | Should Model Routing be configurable per user/project/intent? | → Runtime cascade with multi-provider support | ADR-001 (updated) |
| [Q-007](Q-007-writing-context-data-loader.md) | Writing Context Data Loader | → Resolved via `WritingContextAssembler` | — |
| [Q-008](Q-008-auth-store-hydration.md) | Auth Store wird nach Page Reload nicht rehydriert | → Resolved via `AuthProvider.tsx` in Root Layout | — |
