# Narrare — Model Data Reference

> **This document describes how Narrare integrates [models.dev](https://models.dev) as the source of truth for model metadata.**
> It covers where the data lives, what it contains, which features consume it, and how to refresh it.
>
> Repository: <https://github.com/anomalyco/models.dev>
> API: <https://models.dev/api.json>
>
> Maintained by: Documentation Agent

---

## What is models.dev?

[models.dev](https://models.dev) is an **open-source database of AI models** — MIT-licensed, community-maintained. It tracks ~400+ models from 50+ providers with pricing, token limits, modalities, and capability metadata.

**Why did we choose it over the alternatives?**

- **Pricing tables in code** — go stale the moment a provider changes rates.
- **Guessed averages** — inaccurate for cost estimation; GPT-4o and GPT-4o-mini cost wildly different amounts per token.
- **models.dev** — community-curated, standardized format, single `api.json` fetch for everything.

Narrare uses it as a single source of truth for model metadata instead of maintaining our own parallel database.

---

## Local Cache

The API JSON (~2 MB) is fetched on first access and cached locally.

| Property | Value |
|----------|-------|
| **Cache path** | `~/.narrare/cache/models_cache.json` |
| **Format** | Raw JSON, identical to `models.dev/api.json` |
| **TTL** | 24 hours (auto-refreshed on next access after expiry) |
| **On network failure** | Last cache is used — graceful degradation |
| **Manual refresh** | `POST /api/v1/settings/models/refresh` or UI button |

---

## Data Structure

Each provider entry contains a `models` dictionary keyed by model ID. Here is the structure for one provider with one model:

```json
{
  "openai": {
    "id": "openai",
    "name": "OpenAI",
    "models": {
      "gpt-4o": {
        "id": "gpt-4o",
        "name": "OpenAI GPT-4o",
        "family": "gpt",
        "limit": {"context": 128000, "output": 16384},
        "cost": {"input": 2.5, "output": 10, "cache_read": 1.25},
        "modalities": {"input": ["text", "image"], "output": ["text"]}
      }
    }
  }
}
```

### Per-Model Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `string` | Model identifier, e.g. `"gpt-4o"` |
| `name` | `string` | Human-readable display name |
| `family` | `string` | Model family grouping, e.g. `"gpt"`, `"claude-sonnet"` |
| `limit.context` | `int` | Maximum context window in tokens |
| `limit.output` | `int` | Maximum output length in tokens |
| `cost.input` | `float` | Price per 1M input tokens (USD) |
| `cost.output` | `float` | Price per 1M output tokens (USD) |
| `cost.cache_read` | `float` | Price per 1M cached-read tokens, if supported (optional) |
| `cost.cache_write` | `float` | Price per 1M cached-write tokens, if supported (optional) |
| `modalities.input` | `string[]` | Input modalities supported: `text`, `image`, `audio` |
| `modalities.output` | `string[]` | Output modalities supported: `text`, `image`, `audio` |
| `reasoning` | `bool` | Supports reasoning / chain-of-thought |

---

## Features Using models.dev

| Feature | Status | What it uses |
|---------|--------|-------------|
| SET-005 Configurable Token Limits | 📋 planned | Model context/output limits as suggested defaults |
| NTH-01 Cost Estimation | 📋 spec | Per-model prices to estimate cost of `TokenUsage` |
| NTH-03 Registry Validation | 📋 spec | CI check comparing local model registry against models.dev |
| UI "Refresh Model Data" | 📋 spec | Button in Settings to trigger a manual cache refresh |
| STATS-002 Cost Tracking | 💡 idea | Could use models.dev for real-time cost calculation |

---

## Refresh Mechanism

The manual refresh endpoint invalidates the local cache, fetches fresh data from `api.json`, and returns a diff.

```
POST /api/v1/settings/models/refresh

→ 200 { "status": "ok", "new_models": [...], "deprecated": [...] }
→ 502 { "status": "error", "message": "...", "cached_data_from": "2026-05-20" }
```

The UI button in Settings shows the current cache age and lets the user trigger a refresh at any time.

---

## Possible Future Use Cases

Since the full models.dev dataset is available locally, other features can consume it without additional network calls:

- **Model comparison UI** — "Which models have the largest context window? Cheapest per token?" — rendered as a sortable table.
- **Output limit presets** — Use `limit.output` values as maximum boundaries when configuring token profiles.
- **Capability gates in the Gateway** — Check whether a model supports tool-calling or structured output before dispatching.
- **Provider search** — "Show all models under $5/1M output that support image input" — a mini models.dev browser inside Narrare.
- **Deprecation warnings** — If models.dev marks a model as `deprecated`, surface a prompt: "gpt-3.5-turbo is being phased out. Switch to gpt-4o-mini?"

---

## Source Files

| File | Layer | Purpose |
|------|-------|---------|
| `packages/core/narrare_core/llm/cost_rates.py` | Core | Fetcher, local cache, lookup helpers |
| `apps/api/narrare/settings/models_router.py` | Backend | `POST /refresh` endpoint |
| `packages/web/components/settings/ModelDataStatus.tsx` | Frontend | Refresh button + cache age display |
| `scripts/check_model_registry.py` | Platform | CI validator (compares registry vs models.dev) |
| `docs/reference/model-data.md` | Docs | This file |

---

## See Also

- [Auto-Cost Estimation (NTH-01)](../features/NTH-01-cost-estimation.md) — feature spec
- [Model Registry Validation (NTH-03)](../features/NTH-03-registry-validation.md) — feature spec
- [Glossary: Token Budget](../_shared/GLOSSARY.md) — definition of cost-related terms
- [models.dev on GitHub](https://github.com/anomalyco/models.dev) — upstream repository
