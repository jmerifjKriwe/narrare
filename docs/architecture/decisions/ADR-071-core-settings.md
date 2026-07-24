# ADR-071 — CoreSettings: Centralised Configuration for the Core Package

> **Status:** ✅ Implemented
> **Date:** 2026-07-24
> **Deciders:** Architecture Specialist
> **Supersedes:** —
> **Related:** ADR-001 (LLM Gateway / provider factory pattern), ADR-060 (transport retry at provider layer), ADR-064 (mem0 governed defaults), RULE-05/06/07/18b

---

## Context

The Core package (`packages/core/narrare_core/`) has **no centralised settings
model**. Configuration is read ad-hoc via `os.environ.get()` at each call site.
A grep found **14 scattered `os.environ.get()` calls** in Core:

| File | Env var(s) | Count |
|------|-----------|-------|
| `llm/_providers/openai.py` | `OPENAI_API_KEY` | 1 |
| `llm/_providers/anthropic.py` | `ANTHROPIC_API_KEY` | 1 |
| `llm/_providers/others.py` | `GOOGLE_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY` | 4 |
| `llm/_providers/ollama.py` | `OLLAMA_BASE_URL` | 1 |
| `llm/_providers/zai.py` | `ZAI_API_KEY` (×2) | 2 |
| `llm/_providers/registry.py` | `NARRARE_E2E_TEST` | 1 |
| `llm/_transport_retry.py` | `NARRARE_LLM_TRANSPORT_MAX_RETRIES` | 1 |
| `llm/embedding_providers.py` | `DEFAULT_EMBEDDING_MODEL` | 1 |
| `memory/availability.py` | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_BASE_URL`, `ANTHROPIC_BASE_URL` | 2 calls |
| `crypto.py` | `NARRARE_ENCRYPTION_KEY` | 1 |

The API app (`apps/api/narrare/_app/settings_model.py`) already has a
well-structured `Settings(BaseSettings)` model for app-level config (DB, Redis,
Auth, SMTP, etc.). But Core has no equivalent.

### Problems this causes

1. **Inconsistent config reading** — some values live in API `Settings`, some
   in `os.environ` reads inside Core. There is no single source of truth for
   what env vars the Core package needs.

2. **No validation at startup for Core-level config** — env vars are read
   lazily at call time with string fallbacks. A typo in an env var name is
   silently swallowed (returns the default), not caught at startup.

3. **Duplicate reading** — `NARRARE_ENCRYPTION_KEY` is defined in **both** API
   `Settings` (`encryption_key` field, alias `NARRARE_ENCRYPTION_KEY`) **and**
   `core/crypto.py` (`os.environ.get("NARRARE_ENCRYPTION_KEY", "")`). The API
   lifespan even contains a **workaround** that writes the Settings value back
   into `os.environ` so Core can read it:

   ```python
   # apps/api/narrare/_app/lifespan.py:180
   if settings.encryption_key and not os.environ.get("NARRARE_ENCRYPTION_KEY"):
       os.environ["NARRARE_ENCRYPTION_KEY"] = settings.encryption_key
   ```

   This is an architectural smell: the API app manually syncs config into
   `os.environ` so Core can re-read it. (Architectural-discipline §4: bypassing
   an abstraction "just to make it work".)

4. **Poor testability** — tests must `patch.dict(os.environ, ...)` to control
   Core behaviour, rather than injecting a typed, validated settings object.

5. **Divergent defaults for the same concept** — API `Settings` has
   `default_embedding_model: str = "text-embedding-3-small"` (a plain field),
   while Core's `embedding_providers.py` reads `os.environ.get(
   "DEFAULT_EMBEDDING_MODEL", self.default_model)`. Two different config paths
   for the same concept, with no guarantee they agree.

### Root-cause chain (≥2× "Why")

- **Symptom:** ~14 scattered `os.environ.get()` calls in Core; duplicate
  encryption-key reading; lifespan workaround.
- **Why #1 — why are env vars read ad-hoc?** Core never got a settings model.
  The API app got one (`settings_model.py`), but Core was left reading env vars
  directly because "it works" and pydantic-settings was only added as a Core
  dependency later. **RC1 — missing infrastructure:** the centralised config
  abstraction was never extended into Core.
- **Why #2 — why does the lifespan sync encryption key into os.environ?**
  Because `core/crypto.py` reads `os.environ` directly and has no other input
  channel. The API app holds the value in `Settings` but Core cannot receive
  it without either (a) passing it as a parameter on every call, or (b) the
  env-var bridge. Option (b) was chosen as the path of least resistance.
  **RC2 — no injection seam:** Core has no settings object to receive
  configuration; the env-var bridge is the workaround for the missing seam.

The architecturally correct solution addresses RC1 (build the missing
infrastructure) and RC2 (provide the injection seam), eliminating the workaround.

---

## Decision Drivers

- **RULE-05 (module boundaries):** Core owns its own configuration; it must
  not depend on the API app's `Settings` class (RULE-07).
- **RULE-06 (one responsibility per file):** A `settings.py` file has the
  "Config" role — settings/constants only.
- **RULE-07 (dependency direction):** `core/` never imports from `apps/`.
  CoreSettings must live in Core; the API app may depend on it, never the
  reverse.
- **RULE-18b (configuration effect integrity):** ADR-060 moved transport retry
  to the provider layer as a governed default. CoreSettings must be compatible
  with this governance pattern — it is the typed mirror of the governed
  values, not a replacement for the per-value effect tests.
- **ADR-001 (provider factory pattern):** Factories accept explicit
  `api_key`/`base_url` kwargs for per-user credentials. CoreSettings provides
  the **fallback** values (operator env vars); it must not change the factory
  Protocol signature.
- **ADR-060 (transport retry at provider layer):** `get_transport_max_retries()`
  is the established pattern for a module-level governed accessor. CoreSettings
  follows the same pattern.
- **ADR-064 (mem0 governed defaults):** `_PROVIDER_DEFAULT_MODELS` are governed
  defaults. CoreSettings does not replace governed defaults that are
  intentionally hardcoded with rationale; it centralises **env-var-backed**
  config.
- **Testability:** Replace `patch.dict(os.environ, ...)` with typed settings
  injection.
- **pydantic-settings is already a Core dependency** — no new dependency
  (`packages/core/pyproject.toml` lists `pydantic-settings==2.14.2`).

---

## Options Considered

### Option A — CoreSettings standalone in Core; API Settings composes it

`CoreSettings(BaseSettings)` lives in `packages/core/narrare_core/settings.py`.
The API `Settings` class nests it as a sub-model
(`core: CoreSettings = Field(default_factory=CoreSettings)`), sharing the same
`.env` file. The API app accesses core config via `settings.core.*`; Core
modules access it via a standalone `get_core_settings()` accessor.

**Pros:**
- Single `get_settings()` call in the API app yields both app-level and
  core-level config.
- The `.env` file path is shared (API Settings passes it to the nested
  CoreSettings).
- Core is self-contained — it has its own settings model and accessor.

**Cons:**
- pydantic-settings nested models introduce env-var prefix complexity. If
  CoreSettings has `encryption_key` with alias `NARRARE_ENCRYPTION_KEY`, nesting
  it inside API `Settings` may require prefix handling
  (`NARRARE_CORE__ENCRYPTION_KEY` or similar) unless aliases are carefully
  managed. This is a known pydantic-settings friction point for nested
  `BaseSettings` models.
- Two cached instances exist (one nested in API `Settings`, one from
  `get_core_settings()`). They read the same source so values match, but the
  redundancy is a minor confusion risk.
- The composition couples the API `Settings` class to Core's config shape —
  a Core config change ripples into the API Settings model.

### Option B — CoreSettings standalone in Core; API Settings remains separate (no composition)  [RECOMMENDED]

`CoreSettings(BaseSettings)` lives in `packages/core/narrare_core/settings.py`
with its own `get_core_settings()` cached accessor. The API `Settings` class
**remains separate** — it keeps app-level config (DB, Redis, Auth, SMTP) and
**removes** fields that CoreSettings now owns (`encryption_key`,
`default_embedding_model`, `memory_llm_model`, `memory_embedding_model`). When
the API app needs core-level config, it calls `get_core_settings()`.

Both `CoreSettings` and API `Settings` read the same `.env` file (project root)
and the same env vars. CoreSettings computes the project-root `.env` path
relative to its own file location (same pattern as API `settings_model.py`),
so no cross-package path dependency exists.

**Pros:**
- **Clean separation of concerns.** CoreSettings owns core config; API Settings
  owns app config. No nested-model prefix friction.
- **RULE-07 clean.** Core does not import from apps; the API app imports
  `get_core_settings` from Core (downward dependency). No composition coupling.
- **Single accessor in Core.** `get_core_settings()` is the one place Core
  modules get config — mirroring the established `get_transport_max_retries()`
  pattern (ADR-060).
- **Eliminates the encryption-key workaround.** CoreSettings owns
  `NARRARE_ENCRYPTION_KEY`; `core/crypto.py` reads from `get_core_settings()`;
  the lifespan `os.environ` bridge is removed; API Settings drops the duplicate
  `encryption_key` field.
- **Testability.** Tests construct `CoreSettings(openai_api_key="test-key",
  ...)` directly and override the cached accessor
  (`get_core_settings.cache_clear()` or a test fixture). Strictly better than
  `patch.dict(os.environ, ...)`.
- **Sustainable.** Adding a new Core env var = add a field to CoreSettings. No
  changes to API Settings. No risk of the two models diverging on the same
  concept.

**Cons:**
- The API app has two accessors (`get_settings()` for app config,
  `get_core_settings()` for core config). This is a minor cognitive cost,
  mitigated by clear naming.
- CoreSettings must independently locate the `.env` file (computed relative to
  its own file path). This duplicates the `BASE_DIR` logic from API
  `settings_model.py` (4 lines), which is acceptable for package independence.

### Option C — Extend API Settings; pass values into Core as function parameters

Keep all config in the API `Settings` class. Core functions receive config
values as parameters from the API app.

**Pros:** Single settings class for the whole app.

**Cons:**
- **Violates RULE-07.** Core would depend on the API `Settings` class (or
  receive untyped primitives). Either Core imports from `apps/` (forbidden),
  or every Core function signature grows a config parameter (intrusive).
- **Breaks Core reusability.** Core must be usable by MCP, A2A, CLI without
  the API app (RULE-12, 4-client model). If Core depends on API Settings, it
  cannot be used by other clients.
- **Rejected.** This is the status quo's failure mode dressed up as a
  "centralisation" — it centralises in the wrong layer.

### Option D — Status quo (do nothing)

**Pros:** No implementation work.

**Cons:**
- The 14 `os.environ.get()` calls remain scattered.
- The encryption-key workaround remains.
- No startup validation for Core config.
- Poor testability persists.
- Violates architectural-discipline §0 (build proper solutions) and §4 (no
  workarounds — the lifespan env-var bridge is a workaround).

---

## Decision

**We choose Option B.**

`CoreSettings(BaseSettings)` is a standalone pydantic-settings model in
`packages/core/narrare_core/settings.py`. It centralises all env-var-backed
Core configuration. A cached `get_core_settings()` accessor provides the
singleton (mirroring `get_settings()` in the API app and
`get_transport_max_retries()` from ADR-060). Core modules read from
`get_core_settings()` instead of `os.environ.get()`. The API `Settings` class
remains separate and **removes** fields that CoreSettings now owns.

### 1. Module structure

```
packages/core/narrare_core/
├── settings.py          ← NEW: CoreSettings(BaseSettings) + get_core_settings()
├── crypto.py            ← reads from get_core_settings() instead of os.environ
├── llm/
│   ├── _providers/      ← factories read fallback keys from get_core_settings()
│   ├── _transport_retry.py  ← reads from get_core_settings()
│   ├── embedding_providers.py  ← reads from get_core_settings()
│   └── _providers/registry.py  ← reads e2e_test from get_core_settings()
└── memory/
    └── availability.py  ← reads from get_core_settings()
```

`settings.py` is a "Config" role file per RULE-06 (settings/constants only).
It must stay under the 200-line config-file hard limit (RULE-04). If it
approaches the limit, split by concern into a `settings/` package
(`settings/providers.py`, `settings/transport.py`, etc.) — but a single file
is the starting point.

### 2. CoreSettings ↔ API Settings relationship

**Standalone, no composition.** CoreSettings lives in Core; API Settings lives
in the API app. The dependency arrow is one-way: `apps/api` may import
`get_core_settings` from Core; Core never imports from `apps/api` (RULE-07).

The API `Settings` class **removes** these fields (now owned by CoreSettings):
- `encryption_key` (alias `NARRARE_ENCRYPTION_KEY`) → `CoreSettings.encryption_key`
- `default_embedding_model` → `CoreSettings.default_embedding_model`
- `memory_llm_model` → stays in API Settings (app-level operational default for
  the memory service, not a Core provider credential) — see §5 below
- `memory_embedding_model` → stays in API Settings (same rationale)

When the API app needs core-level config (e.g., the encryption key for
`core.crypto.encrypt()`), it does **not** read `os.environ` — it calls
`get_core_settings()` or, more commonly, simply calls `core.crypto.encrypt()`
which reads CoreSettings internally.

### 3. Env-var ownership

| Env var | Owner | CoreSettings field | Notes |
|---------|-------|-------------------|-------|
| `OPENAI_API_KEY` | CoreSettings | `openai_api_key: str \| None` | Provider fallback (per-user key from DB takes precedence per ADR-001) |
| `ANTHROPIC_API_KEY` | CoreSettings | `anthropic_api_key: str \| None` | Provider fallback |
| `GOOGLE_API_KEY` | CoreSettings | `google_api_key: str \| None` | Provider fallback |
| `GEMINI_API_KEY` | CoreSettings | `gemini_api_key: str \| None` | Alias fallback for Google |
| `GROQ_API_KEY` | CoreSettings | `groq_api_key: str \| None` | Provider fallback |
| `OPENROUTER_API_KEY` | CoreSettings | `openrouter_api_key: str \| None` | Provider fallback |
| `ZAI_API_KEY` | CoreSettings | `zai_api_key: str \| None` | Provider fallback |
| `OLLAMA_BASE_URL` | CoreSettings | `ollama_base_url: str` | Default `http://localhost:11434` |
| `OPENAI_BASE_URL` | CoreSettings | `openai_base_url: str \| None` | Memory provider detection uses this |
| `ANTHROPIC_BASE_URL` | CoreSettings | `anthropic_base_url: str \| None` | Memory provider detection uses this |
| `NARRARE_ENCRYPTION_KEY` | CoreSettings | `encryption_key: str` | **Canonical source.** API Settings duplicate removed. |
| `NARRARE_LLM_TRANSPORT_MAX_RETRIES` | CoreSettings | `llm_transport_max_retries: int` | Governed default (ADR-060). Default 2. |
| `DEFAULT_EMBEDDING_MODEL` | CoreSettings | `default_embedding_model: str` | Default `text-embedding-3-small`. API Settings duplicate removed. |
| `NARRARE_E2E_TEST` | CoreSettings | `e2e_test: bool` | E2E test mode flag. Read in registry + API lifespan/rate-limiter. |

**Stays in API Settings** (app-level operational config, not Core provider
credentials):
- `memory_llm_model`, `memory_embedding_model` — these are app-level defaults
  for the memory *service* (which model mem0 uses internally). They are not
  provider API keys or Core transport config. They stay in API Settings. (If
  a future need arises to centralise them, a follow-up ADR can move them.)
- All DB, Redis, Auth, SMTP, WebSocket, token-limit, CSRF, cost-rates, and
  dev-user config.

### 4. Provider factory consumption pattern

**The factory Protocol (ADR-001) is unchanged.** Factories still accept
`(model_id, *, api_key, base_url)`. The only change is the **fallback source**:

```python
# BEFORE (openai.py):
resolved_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")

# AFTER (openai.py):
from narrare_core.settings import get_core_settings
resolved_key = api_key if api_key is not None else get_core_settings().openai_api_key
```

Credential resolution precedence (unchanged from ADR-001):
1. `api_key` kwarg (per-user credential from DB) — takes precedence.
2. `CoreSettings.<provider>_api_key` (operator env-var fallback).
3. Defer to pydantic-ai (no resolvable credential — dev/test path).

The gateway does **not** hold CoreSettings. Factories read it themselves,
exactly as they read `get_transport_max_retries()` today (ADR-060 precedent).
This is the least disruptive change and keeps the factory Protocol stable.

### 5. Encryption key canonical source

**CoreSettings is canonical.** `core/crypto.py` reads
`get_core_settings().encryption_key` instead of `os.environ.get(...)`.

The API lifespan workaround is **removed**:
```python
# REMOVED from lifespan.py:
# if settings.encryption_key and not os.environ.get("NARRARE_ENCRYPTION_KEY"):
#     os.environ["NARRARE_ENCRYPTION_KEY"] = settings.encryption_key
```

API Settings removes the `encryption_key` field. The API app accesses the key
via `get_core_settings().encryption_key` when it needs it directly, or (more
commonly) via `core.crypto.encrypt()/decrypt()` which read CoreSettings
internally.

### 6. Transport retry compatibility (ADR-060)

`get_transport_max_retries()` currently reads `os.environ.get(
NARRARE_LLM_TRANSPORT_MAX_RETRIES)` directly. Under CoreSettings, it reads
`get_core_settings().llm_transport_max_retries`. The governed-default
classification (ADR-060) is unchanged — CoreSettings is the **typed mirror** of
the governed value, not a replacement for the per-value effect test
(`tests/unit/core/llm/test_transport_retry.py`). The effect test continues to
prove that changing the value changes runtime behaviour (RULE-18b).

### 7. Memory provider detection

`memory/availability.py::detect_provider_from_env()` currently reads
`OPENAI_API_KEY`/`ANTHROPIC_API_KEY` + base URLs from `os.environ`. Under
CoreSettings, it reads from `get_core_settings()`. The
`ProviderEnvConfig` dataclass and the priority order (openai → anthropic) are
unchanged.

`_PROVIDER_DEFAULT_MODELS` in `mem0_client.py` (ADR-064 governed defaults)
remain as hardcoded constants — they are **not** env-var-backed config and
stay out of CoreSettings.

### 8. Testability improvements

| Before | After |
|--------|-------|
| `patch.dict(os.environ, {"OPENAI_API_KEY": "test"})` | `CoreSettings(openai_api_key="test")` + accessor override |
| No startup validation; typos silently return defaults | pydantic-settings validates at construction; type errors caught |
| Duplicate reading (encryption key in two places) | Single canonical source (CoreSettings) |
| Lifespan env-var bridge workaround | Removed — Core reads CoreSettings directly |

Test injection pattern:
```python
# Construct a CoreSettings with test values
test_settings = CoreSettings(
    openai_api_key="test-key",
    encryption_key="test-encryption-key",
    e2e_test=True,
)
# Override the cached accessor for the test
get_core_settings.cache_clear()
# Either set env vars and let CoreSettings read them, or use a fixture
# that monkeypatches get_core_settings to return test_settings.
```

For factory-level tests, the factories still accept `api_key=`/`base_url=`
kwargs (ADR-001), so per-call injection is unchanged. CoreSettings only
affects the **fallback** path.

---

## Rationale

Option B is chosen because it addresses both root causes:

- **RC1 (missing infrastructure):** CoreSettings is the missing centralised
  config abstraction for Core. It mirrors the proven API `Settings` pattern and
  the ADR-060 `get_transport_max_retries()` accessor pattern.
- **RC2 (no injection seam):** `get_core_settings()` is the typed injection
  seam. The lifespan env-var bridge workaround is eliminated because Core now
  has its own settings object.

Option A (composition) was rejected because pydantic-settings nested-model env
prefix handling introduces unnecessary complexity and coupling for no
functional benefit — both models read the same `.env` and env vars regardless.
Option C violates RULE-07. Option D preserves known workarounds.

The factory Protocol (ADR-001) is deliberately left unchanged. CoreSettings
replaces the **source** of the fallback (`os.environ` → `get_core_settings()`),
not the **contract** (factories still accept `api_key`/`base_url` kwargs). This
is the same surgical change ADR-060 made for transport retry.

---

## Consequences

**Positive:**
- Single source of truth for Core env vars — discoverable in one typed model.
- Startup validation for Core config (pydantic-settings validates types and
  constraints at construction).
- Encryption-key duplicate eliminated; lifespan workaround removed.
- Testability improved: typed settings injection replaces `os.environ` patching.
- Core is more reusable by MCP/A2A/CLI clients (RULE-12) — it no longer relies
  on the API app's lifespan to bridge env vars.
- Consistent with ADR-060's established accessor pattern.

**Negative / Trade-offs:**
- The API app has two settings accessors (`get_settings()` + `get_core_settings()`).
  Mitigated by clear naming and documentation.
- CoreSettings duplicates the `BASE_DIR`/`ENV_FILE` path logic (4 lines) from
  API `settings_model.py` for package independence. Acceptable for RULE-07.
- A migration is needed: 14 `os.environ.get()` call sites in Core + the API
  lifespan workaround + API Settings field removal. This is mechanical but
  touches multiple files.
- `memory_llm_model` / `memory_embedding_model` stay in API Settings (app-level
  operational defaults). If a future need arises to centralise them, a
  follow-up ADR can move them. This ADR deliberately scopes to env-var-backed
  Core config that is currently read via `os.environ.get()`.

**Constraints introduced:**
- **RULE-07:** Core config lives in `packages/core/narrare_core/settings.py`.
  The API app may import `get_core_settings`; Core never imports from `apps/`.
- **ADR-001:** The factory Protocol signature is unchanged. CoreSettings is the
  fallback source only; per-user credentials from DB take precedence.
- **ADR-060:** CoreSettings is the typed mirror of the governed transport-retry
  default. The per-value effect test remains the real RULE-18b enforcement.
- **RULE-18b:** No new user/project-configurable surface is introduced.
  CoreSettings fields are operator-level env vars, not user-facing settings.

---

## RULE-XX Compliance

| Rule | Status | Note |
|------|--------|------|
| RULE-03 | ✅ | CoreSettings is a pydantic-settings data model, not a service class. RULE-03 (Protocol before service implementation) applies to service classes. The `get_core_settings()` accessor follows the established `get_transport_max_retries()` / `get_settings()` pattern — no Protocol required for a cached accessor. If the implementation chooses DI for the accessor, a `CoreSettingsProvider` Protocol may be added, but it is not mandated. |
| RULE-04 | ✅ | `settings.py` is a config file (200-line hard limit). Starts as a single file; splits into a `settings/` package if it approaches the limit. |
| RULE-05 | ✅ | CoreSettings is in `packages/core/narrare_core/settings.py` — Core owns its config. No cross-module `_internal` imports. |
| RULE-06 | ✅ | `settings.py` has the "Config" role (settings/constants only). No business logic, no I/O. |
| RULE-07 | ✅ | Dependency direction: `apps/api` → `core` (API may import `get_core_settings`). Core never imports from `apps/`. CoreSettings computes its own `.env` path. |
| RULE-09 | ✅ | All CoreSettings fields are fully typed (`str | None`, `int`, `bool`). `get_core_settings()` return type is `CoreSettings`. |
| RULE-10 | ✅ | Unit tests for CoreSettings construction, validation, and accessor caching in `tests/unit/core/test_settings.py`. Factory fallback tests updated to use CoreSettings injection. |
| RULE-11 | ✅ | No silent failures. Missing required config raises at construction (pydantic-settings validation), not silently returns a default. |
| RULE-18b | ✅ | CoreSettings is the typed mirror of governed values (transport retry). No new user/project surface. Per-value effect tests (ADR-060) remain the real enforcement. No setting is exposed as user-controllable unless it has a runtime consumer + regression evidence. |
| RULE-20 | ✅ | Full implementation: all 14 call sites migrated, not partial. No "Phase 1 only". |
| RULE-22 | ✅ | Cross-feature coherence: the encryption-key migration touches Core (`crypto.py`), API (`lifespan.py`, `settings_model.py`), and any consumer of `core.crypto`. The integration contract (CoreSettings is canonical; API delegates) is defined in this ADR. |

---

## Implementation Notes

**This ADR is the specification. Implementation follows after approval.**

### Files to create
- `packages/core/narrare_core/settings.py` — `CoreSettings(BaseSettings)` +
  `get_core_settings()` cached accessor.

### Files to modify (Core — replace `os.environ.get` with `get_core_settings()`)
- `packages/core/narrare_core/crypto.py` — `_get_key()` reads
  `get_core_settings().encryption_key`.
- `packages/core/narrare_core/llm/_providers/openai.py` — fallback key from
  `get_core_settings().openai_api_key`.
- `packages/core/narrare_core/llm/_providers/anthropic.py` — fallback key from
  `get_core_settings().anthropic_api_key`.
- `packages/core/narrare_core/llm/_providers/others.py` — Google/Groq/OpenRouter
  fallback keys from `get_core_settings()`.
- `packages/core/narrare_core/llm/_providers/ollama.py` — fallback base URL
  from `get_core_settings().ollama_base_url`.
- `packages/core/narrare_core/llm/_providers/zai.py` — fallback key from
  `get_core_settings().zai_api_key`.
- `packages/core/narrare_core/llm/_providers/registry.py` — E2E test flag from
  `get_core_settings().e2e_test`.
- `packages/core/narrare_core/llm/_transport_retry.py` —
  `get_transport_max_retries()` reads `get_core_settings().llm_transport_max_retries`.
- `packages/core/narrare_core/llm/embedding_providers.py` — default model from
  `get_core_settings().default_embedding_model`.
- `packages/core/narrare_core/memory/availability.py` —
  `detect_provider_from_env()` reads from `get_core_settings()`.

### Files to modify (API — remove duplicates, remove workaround)
- `apps/api/narrare/_app/settings_model.py` — remove `encryption_key` and
  `default_embedding_model` fields (now in CoreSettings).
- `apps/api/narrare/_app/lifespan.py` — remove the
  `os.environ["NARRARE_ENCRYPTION_KEY"] = settings.encryption_key` bridge.
- `apps/api/narrare/_app/lifespan.py` — E2E test flag read from
  `get_core_settings().e2e_test` (or keep `os.environ` read if the lifespan
  runs before any Core import — implementation decision).
- `apps/api/narrare/_app/rate_limiter_dep.py` — E2E test flag from
  `get_core_settings().e2e_test`.
- `apps/api/narrare/embeddings/service.py` — `DEFAULT_EMBEDDING_MODEL` from
  `get_core_settings().default_embedding_model`.

### Out of scope (API-level os.environ reads, not Core config)
- `apps/api/narrare/_app/telemetry.py` — OTEL env vars. These are API-level
  observability config, not Core config. A follow-up can extend API Settings.
- `apps/api/narrare/_app/rate_limits.py` — rate-limit env vars. API-level.
- `apps/api/narrare/_app/lifespan.py:91` — `DATABASE_URL` for Alembic. This
  runs before the app is fully wired; keeping the `os.environ` read is
  acceptable (Alembic needs the URL before Settings is constructed).

### Test injection
- `tests/unit/core/test_settings.py` — CoreSettings construction, validation,
  defaults, accessor caching.
- Existing factory tests updated: replace `patch.dict(os.environ, ...)` with
  `get_core_settings.cache_clear()` + env-var setting, or a fixture that
  overrides the accessor.
- `tests/unit/core/llm/test_transport_retry.py` — updated to use CoreSettings
  injection; the fail-if-changed effect test continues to prove RULE-18b.

### ADR-060 compatibility
`get_transport_max_retries()` can either (a) delegate to
`get_core_settings().llm_transport_max_retries`, or (b) keep its own
`os.environ.get` read. Option (a) is preferred for consistency (single source
of truth). The governed-default classification, the default value (2), and
the effect test are unchanged.

**ADR Implementation Completeness Gate (Gate 12):** Before marking this ADR as
"✅ Implemented", verify all items in the Gate 12 checklist at
`.opencode/context/narrare-dev/processes/quality-gates.md`. All 14 Core
`os.environ.get()` call sites must be migrated, the API lifespan workaround
removed, the API Settings duplicate fields removed, and unit tests for
CoreSettings passing.

### ✅ Implementation Complete

This ADR has been fully implemented (commit `281e09e8`):

- `packages/core/narrare_core/settings.py` created with `CoreSettings(BaseSettings)`
  + `get_core_settings()` cached accessor.
- All 14 Core `os.environ.get()` call sites migrated to `get_core_settings()`.
- API Settings duplicates removed (`encryption_key`, `default_embedding_model`).
- Lifespan env-var bridge workaround removed.
- **Enforcement:** regression test `test_does_not_bridge_encryption_key_to_environ`
  + architecture checker (RULE-07) prevent reintroduction.
- **Verification:** 9630 tests passing, pyright 0 errors, architecture check clean.

---

## Review Trigger

- [ ] When a new LLM provider is added (new API key env var → add field to
      CoreSettings, not a new `os.environ.get` in the factory).
- [ ] When pydantic-settings introduces breaking changes to `BaseSettings`
      nested-model or env-file handling.
- [ ] When a genuine requirement emerges for user/project-configurable Core
      settings (would require a new ADR evaluating RULE-18b effect integrity).
- [ ] When `settings.py` approaches the 200-line config-file limit (split into
      a `settings/` package per RULE-04).
