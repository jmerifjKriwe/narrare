## Context

Narrare's LLM infrastructure has three connected problems:

1. **Hardcoded model routing**: `core/llm/intents.py` maps ~20 `LLMIntent` values to specific Anthropic models via a Python dict. Every model change requires code + redeploy.
2. **Single-provider assumption**: Provider factories read API keys from env vars (`ANTHROPIC_API_KEY`, etc.). The system assumes one provider for all users. Users who configured OpenRouter or Ollama during setup cannot use their provider for AI features.
3. **No AI settings infrastructure**: The settings module lacks contracts (RULE-03 violation), has no service layer, and stores no user-level AI configuration. `ProjectSettings.model_overrides` is an unvalidated JSON string that nothing reads.

The Setup Wizard (Step 4) already captures a provider + model + API key per user. This is the seed for the configuration system, but it's currently fire-and-forget — the data is stored in `project_settings.ai_provider` / `ai_model` columns but never used by the gateway.

**Existing provider infrastructure**: 6 providers registered in `core/llm/_providers/` (anthropic, openai, google, groq, openrouter, zai, ollama). Provider factories create `pydantic-ai Model` instances but rely on env vars for credentials. `infer_provider()` does prefix-based heuristic mapping — unreliable for multi-provider scenarios (OpenRouter models like `anthropic/claude-sonnet-4-5` cannot be mapped by name alone).

## Goals / Non-Goals

**Goals:**

- Users can configure multiple providers (API key + base URL each) and switch between them
- Users select a default model (provider + model pair) that applies to all AI features
- Users can override the model per category (writing, analysis, kb, planning, extraction, chat, research) and per individual intent
- Users can configure token limits per category/intent with named profiles
- The configuration cascade resolves: project override → user override → user default → error (no fallback)
- Provider is stored explicitly (not inferred from model name) — critical for OpenRouter, Z.AI, OpenCode Go/Zen
- Settings module follows RULE-03 (contracts first) with proper service layer
- Gateway receives resolved `ModelConfig` from external configuration instead of hardcoded lookup

**Non-Goals:**

- Fallback chains (if primary model fails, try another) — future enhancement
- Automatic model recommendation or benchmarking
- Per-user rate limiting or quota management
- Model fine-tuning or custom model upload
- Local/embedded model as automatic fallback (hardware too varied, quality too low)
- Changing the prompt system — this change is about routing, not prompts
- Removing `infer_provider()` entirely — keep as dev/debugging utility, remove from runtime path

## Decisions

### D1: Provider credentials in provider factory, not env vars

**Decision**: Provider factories accept explicit `api_key` and `base_url` parameters. When provided, use those; when omitted, fall back to env vars (for dev/testing).

**Rationale**: Current factories rely on `ANTHROPIC_API_KEY` etc. env vars. With multi-provider per user, credentials come from the database. The factory signature changes from `def(model_id: str) -> Model` to `def(model_id: str, *, api_key: str | None = None, base_url: str | None = None) -> Model`.

**Alternative considered**: Set env vars per request (hacky, thread-unsafe in async). Rejected.

### D2: Explicit provider in model selection, never inferred

**Decision**: Every model selection stores `{provider_name, model_id}` as a pair. The gateway never calls `infer_provider()` at runtime.

**Rationale**: OpenRouter serves `anthropic/claude-sonnet-4-5` via OpenAI-compatible API. A user with direct Anthropic access uses `claude-sonnet-4-5-20251020` via Anthropic API. Same logical model, different provider, different API key, different base URL. Inference from model name is fundamentally unreliable.

### D3: Configuration cascade with no hardcoded fallback

**Decision**: Resolution order is:
```
Project-level intent override → Project-level category override
    → User-level intent override → User-level category override
    → User's default model
    → ConfigurationError("No AI provider configured")
```

No hardcoded default model. The `MODEL_ROUTING` dict is removed from runtime. If a user has no provider configured, the system returns a clear error directing them to Settings.

**Rationale**: Hardcoded defaults assume universal access to a specific provider, which is false. Users who only have OpenRouter cannot fall back to direct Anthropic. The only viable "default" is the user's own configured default model.

### D4: Intent categories for manageable UX

**Decision**: Group 20 intents into 7 categories:

| Category | Intents |
|----------|---------|
| writing | WRITE, EXTEND, REWRITE, CO_AUTHOR |
| analysis | ANALYSE, SENTIMENT, CONSISTENCY, BETA_READ, VOICE |
| kb | KB_CREATE, KB_IMPROVE, KB_EXTRACT |
| planning | PLAN, SUMMARIZE |
| extraction | EXTRACT, SUGGEST |
| chat | CHAT |
| research | RESEARCH |

Users configure defaults per category. Intent-level overrides are optional (expand-on-demand). The UI shows category-level by default, with an "Advanced" mode for per-intent tuning.

**Rationale**: 20 individual model selectors is overwhelming. 7 categories is manageable. Power users can drill down to intent level.

### D5: Storage — new tables for AI settings

**Decision**: Three new/modified storage structures:

**`user_providers` (new table)**:
```
id UUID PK
user_id UUID FK → users
provider_name VARCHAR(50) NOT NULL  -- "anthropic", "openrouter", etc.
api_key_encrypted TEXT NOT NULL
base_url VARCHAR(500) NULL          -- for OpenAI-compatible providers
is_active BOOLEAN DEFAULT TRUE
created_at TIMESTAMP
updated_at TIMESTAMP
UNIQUE(user_id, provider_name)
```

**`user_ai_settings` (new table or merge into user_settings)**:
```
user_id UUID PK FK → users
default_provider_id UUID FK → user_providers
default_model VARCHAR(200) NOT NULL
category_overrides JSONB DEFAULT '{}'  -- {"writing": {"provider_id": ..., "model": ...}}
intent_overrides JSONB DEFAULT '{}'    -- {"write": {"provider_id": ..., "model": ...}}
token_limit_profile VARCHAR(20) DEFAULT 'balanced'
token_limit_overrides JSONB DEFAULT '{}' -- {"writing": {"max_tokens": 8000}}
updated_at TIMESTAMP
```

**`project_settings` (modified)** — add equivalent category/intent/token override columns.

**Rationale**: API keys are sensitive (separate table, encrypted). AI settings are complex enough to warrant their own structure. JSONB columns with Pydantic validation give flexibility without schema migration per change.

**Alternative considered**: Single `model_overrides` JSON column (current approach). Rejected because it's unvalidated, doesn't support multi-provider, and mixes concerns.

### D6: API key encryption

**Decision**: API keys are encrypted at rest using Fernet (symmetric encryption). The encryption key is a server-side env var (`NARRARE_ENCRYPTION_KEY`). At runtime, keys are decrypted only when constructing a provider instance — never logged, never returned via API.

**Rationale**: API keys are user secrets. Plaintext storage in the database is unacceptable.

### D7: ModelConfig replacement

**Decision**: Replace the current `ModelConfig` dataclass:
```python
# Old (removed from runtime)
@dataclass(frozen=True, slots=True)
class ModelConfig:
    model: str
    temperature: float = 0.7
    max_tokens: int = 2000
    streams: bool = False
    reason: str = ""
```

With:
```python
@dataclass(frozen=True, slots=True)
class ResolvedModelConfig:
    provider_name: str      # explicit, never inferred
    model_id: str
    temperature: float = 0.7
    max_tokens: int = 2000
    streams: bool = False
```

The `MODEL_ROUTING` dict and `get_model_config()` function are removed. A new `ModelRoutingResolver` in core resolves config from user/project settings.

### D8: Gateway receives resolved config

**Decision**: The gateway's `run()` and `stream()` methods accept a `ResolvedModelConfig` (or the raw `provider_name` + `model_id`) plus credentials, instead of looking up from hardcoded routing.

```python
async def run(
    self,
    *,
    intent: LLMIntent,
    system_prompt: str,
    user_prompt: str,
    config: ResolvedModelConfig,       # NEW: caller provides resolved config
    api_key: str | None = None,        # NEW: per-request credentials
    base_url: str | None = None,       # NEW: for OpenAI-compatible providers
    retry_config: RetryConfig = DEFAULT_RETRY,
) -> LLMResult:
```

The caller (service layer) resolves the config via `ModelRoutingResolver` and passes it to the gateway. The gateway no longer calls `get_model_config()` or `infer_provider()`.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| API key encryption key management — if `NARRARE_ENCRYPTION_KEY` is lost, all user API keys are unrecoverable | Document key rotation; key is env var, not in code; support key rotation via migration |
| JSONB column schemas can drift between Pydantic validation and actual DB content | Validate on read AND write via Pydantic schemas; add DB check constraint if needed |
| Gateway API change is **BREAKING** for all callers | Provide transition: `model_override` param kept temporarily with deprecation warning; full migration in follow-up |
| Provider factory signature change affects all 6+ providers | All providers modified in single PR; backward-compatible via optional kwargs |
| Category/intent override UX complexity | Start with category-level only; add intent-level as "Advanced" toggle |
| Performance: resolving model config per LLM call adds DB query | Cache resolved config in Redis per user+project with TTL; invalidate on settings change |
| Setup Wizard already stores provider in `project_settings.ai_provider` | Migration: move existing provider data from project_settings to new user_providers + user_ai_settings |

## Open Questions

1. **Should `user_ai_settings` be a separate table or merged into `user_settings`?** Separate is cleaner (single responsibility) but adds a JOIN. Leaning toward separate.
2. **How to handle the transition period** when both old `MODEL_ROUTING` and new resolver exist? Suggest: feature flag `USE_RUNTIME_MODEL_ROUTING` defaulting to False, flipped after migration.
3. **Should we cache resolved model config in Redis?** Likely yes for performance, but adds invalidation complexity. Start without cache, add if profiling shows need.
4. **Token limit profile defaults**: What are sensible defaults for "quick", "balanced", "long_texts"? Need to define these explicitly.
