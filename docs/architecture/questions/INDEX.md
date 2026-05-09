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
| [Q-001](Q-001-mcp-auth-strategy.md) | How does MCP authenticate against the API? | 🟡 | `apps/mcp/` | init |
| [Q-002](Q-002-a2a-streaming.md) | Does A2A protocol require streaming support? | 🟡 | `apps/a2a/` | init |
| [Q-003](Q-003-embedding-provider.md) | Should embeddings be provider-agnostic from day one? | 🟡 | `core/llm/embeddings.py` | init |

---

## Resolved Questions

| ID | Question | Resolution | ADR |
|----|---------|-----------|-----|
| [Q-004](Q-004-celery-vs-arq.md) | Celery vs arq for background tasks? | → arq | ADR-007 |
| [Q-005](Q-005-resolved.md) | Does pydantic-ai support GLM-5.1 via z.ai? | → Yes, OpenAI-compatible | — |
