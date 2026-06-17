# ADR-020 — Embedding Provider Abstraction

> **Status:** ✅ Accepted
> **Date:** 2026-05-27
> **Deciders:** Architecture Specialist
> **Supersedes:** Q-003 (open question, now resolved)

---

## Context

Currently `packages/core/narrare_core/llm/embeddings.py` imports `openai.AsyncOpenAI()`
directly and calls `client.embeddings.create()` — this is an approved RULE-01b exception
(document via `# narrare: allow-direct-llm` inline comment).

The module is called from:
- `apps/api/narrare/embeddings/service.py` — `EmbeddingService.generate()` and `.search()`
- Potentially batch processing (background tasks via TaskIQ)

The question **Q-003** ("Should embeddings be provider-agnostic from day one?") has been
open since project init. The following developments now force resolution:

1. **ADR-017 (Embedding Cascade)** already anticipates a "provider-native" embedding tier
   for mem0, but there's no unified embedding provider abstraction to plug into.
2. **Post-MVP features** (multi-provider support, local embeddings via sentence-transformers,
   Ollama embeddings) require a pluggable embedding interface.
3. **TECH_STACK.md** documents the intention: "Provider-agnostic embedding interface planned"
   (line 132).
4. **RULE-01b** requires that all LLM calls stay within `core/llm/`, but the current
   exception is undocumented in `pyproject.toml [tool.narrare.architecture.exceptions]`.

The LLM Gateway already has a well-established provider abstraction pattern:
- `core/llm/_providers/registry.py` — `register()`/`get()`/`available()` dict-based registry
- `core/llm/_providers/openai.py` — per-provider factory module
- `_PROVIDER_PREFIXES` in the registry — model-ID-to-provider inference

However, embedding providers differ from chat model providers:
- Embeddings return `list[list[float]]`, not `Model` instances
- Embedding providers are stateful (maintain client connections like `AsyncOpenAI`)
- The batch embedding API (`client.embeddings.create()`) requires direct client access

---

## Decision Drivers

- **Backward compatibility:** All existing callers (`embedding_service.py`) must work
  without changes — no API breakage for current consumers.
- **Provider diversity:** The abstraction must support OpenAI (current), local
  (sentence-transformers), and future providers (Ollama, GLM/Z.AI embedding models).
- **Simplicity:** A Protocol + registry + convenience wrapper is sufficient — no
  over-engineering for hypothetical future needs.
- **RULE-01b compliance:** All direct LLM imports stay in `core/llm/`; the approved
  exception moves to the new provider file.
- **Pattern consistency:** Follow the existing `_providers/registry.py` pattern where
  appropriate, but adapted for embedding-specific needs (class instances, not factories).

---

## Options Considered

### Option A — Embedding-only Protocol in a new file (chosen)

Create a standalone `core/llm/embedding_providers.py` with:
- `EmbeddingProvider` Protocol (async `embed_texts()`, `default_model`, `default_dimension`)
- `OpenAIEmbeddingProvider` implementation
- Module-level `register()`/`get()`/`embed_texts()` convenience functions
- Refactored `embeddings.py` as thin convenience wrapper

**Pros:**
- Clean separation of concerns — Protocol lives alongside implementation
- Follows the project's own pattern (cf. `_providers/registry.py`)
- Easy to test — mock the Protocol for service tests
- Backward compatible — `from narrare_core.llm.embeddings import embed_texts` still works

**Cons:**
- New file adds complexity to the module structure
- Slight duplication of the registry pattern (vs reusing `_providers/registry.py`)

### Option B — Extend `_providers/registry.py` with embedding factories

Add embedding provider factories to the existing `_providers/registry.py` alongside
chat model factories. Embedding factories would return `list[list[float]]` instead
of `Model`.

**Pros:**
- Single registry for all providers — simpler mental model
- Reuses existing `register()`/`get()` infrastructure

**Cons:**
- The existing `ProviderFactory` Protocol returns `Model` — embedding providers return
  `list[list[float]]` from an async method. These are fundamentally different interfaces.
- Embedding providers are stateful (client connections); chat factories are stateless.
- Mixing two different abstractions in one registry creates confusion.
- Would require a separate `EmbeddingProviderFactory` Protocol anyway, defeating reuse.

### Option C — Refactor `_providers/` with a sub-package `_providers/embedding/`

Create `core/llm/_providers/embedding/` with the Protocol, registry, and per-provider
modules (e.g. `_providers/embedding/openai.py`).

**Pros:**
- Sits alongside existing provider structure — consistent layout
- Per-provider files can grow independently without hitting RULE-04 limits

**Cons:**
- Premature directory hierarchy for what starts as a single implementation (OpenAI)
- The `_providers/` namespace is currently for pydantic-ai `Model` factories — mixing
  embedding providers there blurs the namespace
- Adds 2-3 extra files before they're needed

---

## Decision

**We choose Option A — Embedding-only Protocol in a new file.**

The new abstraction lives in `core/llm/embedding_providers.py`, which contains:

1. **`EmbeddingProvider` Protocol** — the interface all embedding providers must satisfy
2. **`OpenAIEmbeddingProvider`** — initial implementation (moves logic from `embeddings.py`)
3. **Module-level registry** — `register()`, `get()`, `available()` functions
4. **Module-level `embed_texts()`** — convenience function using the default provider

`core/llm/embeddings.py` is refactored to delegate to `embedding_providers.py` while
preserving the exact public API signature (plus an optional `provider=` parameter).

---

## Rationale

1. **Pattern consistency, not duplication:** The embedding registry follows the same
   dict-based pattern as `_providers/registry.py` but keeps the interface cleanly
   separated. Embedding providers are fundamentally different from chat model providers
   (async methods, stateful clients, vector output) — forcing them into the same registry
   would create a leaky abstraction.

2. **Backward compatibility is paramount:** The service layer (`embedding_service.py`)
   calls `embed_texts()` from `core/llm.embeddings`. By keeping that function in place
   (but delegating internally), existing callers require zero changes.

3. **Start with one provider, not a directory:** A single OpenAI provider doesn't
   justify a `_providers/embedding/` sub-package. When we add local (`all-MiniLM-L6-v2`)
   or Ollama providers, we can extract them into a `_providers/embedding/` directory
   (same pattern as the existing `_providers/` evolution).

4. **RULE-01b exception is explicit:** The `# narrare: allow-direct-llm` comment moves
   to `embedding_providers.py`, and the exception is registered in `pyproject.toml
   [tool.narrare.architecture.exceptions]`.

---

## Consequences

### Positive

- **Provider selection is now configurable** — callers can pass `provider="openai"`,
  and future providers (`provider="local"`, `provider="ollama"`) work immediately
- **Testability** — services can inject test provider instances (mock `EmbeddingProvider`)
- **Consistency with ADR-017** — the embedding cascade can plug into this abstraction
  for its "provider-native" tier
- **Backward compatible** — no changes needed in `embedding_service.py` or any caller
- **RULE-01b compliance is cleaner** — exception is documented in both inline comment
  and `pyproject.toml`

### Negative / Tradeoffs

- One new file in the LLM module (`embedding_providers.py`)
- Slight indirection: `embed_texts()` in `embeddings.py` now delegates to
  `embedding_providers.embed_texts()` (negligible at this call frequency)

### Constraints introduced

| Rule | Status | How we satisfy it |
|------|--------|-------------------|
| RULE-01b | ✅ | All LLM imports stay in `core/llm/embedding_providers.py` |
| RULE-03 | ✅ | `EmbeddingProvider` Protocol defined before implementation |
| RULE-04 | ✅ | Single file under limit; `_providers/embedding/` extracted when >300 lines |
| RULE-06 | ✅ | `embedding_providers.py` = one responsibility (provider abstraction) |
| RULE-07 | ✅ | No new dependencies; core imports no API modules |
| RULE-09 | ✅ | Full type annotations on Protocol and implementations |
| RULE-11 | ✅ | Error handling (EmbeddingError) preserved from existing code |

---

## Implementation Notes

### File Structure

```
packages/core/narrare_core/llm/
├── embedding_providers.py    ← NEW: Protocol, OpenAI impl, registry, convenience
├── embeddings.py             ← REFACTORED: Thin convenience, delegates to providers
```

### Proposed API

**Protocol (`embedding_providers.py`):**

```python
@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for text embedding providers."""

    async def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]: ...

    @property
    def default_model(self) -> str: ...

    @property
    def default_dimension(self) -> int: ...
```

**OpenAI implementation (`embedding_providers.py`):**

```python
class OpenAIEmbeddingProvider:
    """Embedding provider using OpenAI's API."""

    default_model = "text-embedding-3-small"
    default_dimension = 1536

    async def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]:
        # Internal logic from current embeddings.py:
        # - Empty string handling (zero vectors)
        # - Batch processing (BATCH_SIZE=100)
        # - Error handling (openai.OpenAIError → EmbeddingError)
        # - Logging (structlog)
        ...
```

**Registry (`embedding_providers.py`):**

```python
_REGISTRY: dict[str, EmbeddingProvider] = {}
_DEFAULT_KEY: str | None = None

def register(name: str, provider: EmbeddingProvider, *, default: bool = False) -> None: ...
def get(name: str) -> EmbeddingProvider: ...
def available() -> list[str]: ...
```

**Convenience function (`embedding_providers.py`):**

```python
async def embed_texts(
    texts: list[str],
    *,
    model: str | None = None,
    provider: str | None = None,
) -> list[list[float]]:
    """Embed texts using the default or named provider."""
    ...
```

**Refactored `embeddings.py`:**

```python
"""Text embedding generation — convenience wrapper.

Delegates to embedding_providers for the actual implementation.
"""

from narrare_core.llm.embedding_providers import embed_texts as _provider_embed_texts
from narrare_core.llm.embedding_providers import available, get, register

# Re-exports for backward compatibility
embed_texts = _provider_embed_texts

__all__ = ["embed_texts", "register", "get", "available"]
```

### Minimum Provider Registration (On-Import)

The OpenAI provider is auto-registered on import (same pattern as `_providers/openai.py`):

```python
# At module level in embedding_providers.py
if "openai" not in _REGISTRY:
    register("openai", OpenAIEmbeddingProvider(), default=True)
```

### pyproject.toml Update

The RULE-01b exception entry in `[tool.narrare.architecture.exceptions]` must be updated:

```toml
[[tool.narrare.architecture.exceptions.entries]]
rule = "RULE-01b"
file = "packages/core/narrare_core/llm/embedding_providers.py"
reason = "Batch embedding API requires direct client access for performance"
approved_by = "architecture-review"
date = "2026-05-27"
```

### Callers (no changes needed)

| Caller | Import | After change |
|--------|--------|--------------|
| `embedding_service.py` | `from narrare_core.llm.embeddings import embed_texts` | Same import, same behavior. Optional `provider=` kwarg available. |
| Future embedders | `from narrare_core.llm.embedding_providers import embed_texts` | Direct import, can pass `provider=`. |
| mem0 cascade (ADR-017) | `from narrare_core.llm.embedding_providers import get, available` | Can resolve providers by name. |

---

## Review Trigger

- [ ] When adding the second embedding provider implementation (local / Ollama / Z.AI),
      evaluate whether to extract `_providers/embedding/` directory structure
- [ ] When embedding_providers.py exceeds 300 lines, split into `_providers/embedding/`
- [ ] If `pyproject.toml [tool.narrare.architecture.exceptions]` enforcement is automated,
      verify the exception entry is valid
