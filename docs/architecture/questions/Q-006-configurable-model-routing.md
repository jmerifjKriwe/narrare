# Q-006 — Should Model Routing be configurable per user/project/intent?

> **Status:** ✅ Resolved
> **Blocks:** ~~Advanced model preferences, self-hosted LLM support, fallback chains~~
> **Raised:** 2026-05-12 (Tech Stack Audit)
> **Resolved:** 2026-05-14

## Context

INFRA-001 (LLM Gateway) promises "You can switch providers anytime" and
"configured in Settings → AI Provider". Currently only API keys are configurable.
The model-to-intent mapping is hardcoded in `core/llm/intents.py` as
`MODEL_ROUTING` — a Python dictionary. Changing the model for any intent requires
a code change and redeploy.

This blocks several important scenarios:

| Scenario | Current | Needed |
|---|---|---|
| User wants GLM instead of Claude for writing | ❌ Code change | ✅ Settings UI |
| Self-hosted user only has Ollama | ❌ Code change | ✅ Config: all intents → local |
| Claude down → fallback to GPT-4o | ❌ Total blockage | ✅ Fallback chain per intent |
| Cost-sensitive user wants Haiku everywhere | ❌ Code change | ✅ Project-level override |
| A/B test: Claude vs GLM for writing | ❌ Not possible | ✅ Config-based switching |

## Analysis

### Current State

`intents.py` has a hardcoded dict mapping `LLMIntent` → `ModelConfig`:

```python
MODEL_ROUTING: dict[LLMIntent, ModelConfig] = {
    LLMIntent.WRITE: ModelConfig(model="claude-sonnet-4-5-20251020", ...),
    LLMIntent.ANALYSE: ModelConfig(model="claude-haiku-3-5-20241022", ...),
}
```

`infer_provider()` in `registry.py` is a heuristic string matcher
(`if lower.startswith("claude"): return "anthropic"`). This is fragile with
new model names.

### Proposed Direction: Configuration Cascade

```
User input (Settings UI)
       ↓
Project-Level Config (DB, per novel)
       ↓
User-Level Config (DB, per user)
       ↓
ENV Variables (NARRARE_WRITE_MODEL, etc.)
       ↓
defaults.yaml (bundled, editable)
       ↓
Hardcoded Dict (current state = ultimate fallback)
```

Each layer can override the one above. The bottom layer (current hardcoded dict)
is always the safe fallback.

### Data Model Sketch

```sql
model_routing_overrides (
    id UUID PK,
    user_id UUID NULL,           -- null = global default
    project_id UUID NULL,        -- null = user-level
    intent VARCHAR(50) NOT NULL, -- "write", "analyse", etc.
    model VARCHAR(100) NOT NULL, -- "claude-sonnet-4-5-20251020"
    temperature FLOAT NULL,      -- null = use default
    max_tokens INTEGER NULL,     -- null = use default
    fallback_model VARCHAR(100) NULL,  -- null = no fallback
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
)
```

### Gateway Changes

```python
async def get_model_config(
    intent: LLMIntent,
    user_id: UUID | None = None,
    project_id: UUID | None = None,
) -> ModelConfig:
    # 1. Check DB for project-level override
    # 2. Check DB for user-level override
    # 3. Check ENV variables
    # 4. Fall back to hardcoded defaults
```

### Fallback Chain

```python
@dataclass(frozen=True, slots=True)
class ModelConfig:
    model: str
    fallback_model: str | None = None  # NEW
    temperature: float = 0.7
    max_tokens: int = 2000
    streams: bool = False
    reason: str = ""
```

If primary model fails, try `fallback_model`. If both fail → `LLMGatewayError`.

### Related Features

- INFRA-001 (LLM Gateway) — the gateway itself
- SET-001 (Setup Wizard) — should include model preference step
- INFRA-005 (Memory Layer) — memory-aware model selection

### Estimated Effort

| Part | Effort |
|---|---|
| DB table + migration | 2h |
| Resolver in `intents.py` | 3h |
| Gateway adaptation (fallback chain) | 2h |
| Settings UI (Frontend) | 4h |
| Tests | 4h |
| ADR + Docs | 2h |
| **Total** | ~2 days |

## Resolution

**Implemented as runtime configuration cascade with multi-provider support.**

### Decision Summary

- **Configuration cascade implemented:** Project override → User override → User default → `ConfigurationError`. No hardcoded fallback — users must configure at least one provider.
- **No hardcoded fallback:** The `MODEL_ROUTING` dict and `get_model_config()` have been removed from `intents.py`. There is no "safe fallback" — the only viable default is the user's own configured default model.
- **Provider stored explicitly:** Every model selection stores `{provider_id, model_id}` as a pair. The provider is never inferred from the model name. This is critical for OpenRouter and Z.AI scenarios where model names are ambiguous.
- **7 intent categories** group 20 intents for manageable UX. Users configure per-category defaults with optional per-intent overrides via an "Advanced" toggle.
- **Multi-provider support:** Users can register multiple AI providers (OpenAI, Anthropic, OpenRouter, Ollama, Z.AI, etc.) with encrypted API keys. Each provider stores an API key (Fernet-encrypted at rest) and optional base URL.
- **New tables:** `user_providers` (encrypted API keys), `user_ai_settings` (default model, overrides, token limits), JSONB columns on `project_settings` for project-level overrides.
- **Frontend UI:** Settings → AI Providers (manage providers), Settings → AI Model & Routing (default model, category/intent overrides), Token Limit Profiles (quick/balanced/long_texts/custom).
- **Token limit profiles:** Named profiles (quick, balanced, long_texts, custom) with per-category and per-intent overrides for `max_tokens` and `temperature`.

### References

- See ADR-001 update (runtime config resolution section)
- OpenSpec change: `openspec/changes/configurable-model-routing/`
- Design decisions: D1–D8 in the OpenSpec design doc
- Migration: `alembic/versions/0004_ai_settings.py`

### What was NOT implemented (future)

- Fallback chains (if primary model fails, try another) — remains a future enhancement
- Automatic model recommendation or benchmarking
- Per-user rate limiting or quota management
