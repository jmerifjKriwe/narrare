# Provider presets and model profiles — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split one provider profile into a provider (endpoint, API shape, key, vendor) and model profiles under it, so ten providers are one click away, each task picks a model, and the same model priced through two providers stays two facts.

**Architecture:** Two kernel tables replace one. Resolution walks task → assignment → model profile → provider → adapter, and the catalog lookup uses the provider's vendor. Presets are kernel data for the provider form; the catalog supplies the model list; the Anthropic adapter speaks `/v1/messages` natively. Stream failures carry a code instead of an empty payload.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy async, Alembic, Postgres, Vite/React, TanStack Router, openapi-typescript, pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-04-provider-presets-and-model-profiles-design.md`

## Global Constraints

- Gates: `just check` (lint + types), `just test-file <path>`, `just test`, `just test-frontend`, `just test-e2e settings`, `just verify`. A gate counts only when its output was read.
- Schema: `just db-revision "<message>"` drafts the revision; hand-write data steps; `just db-init` applies, `just db-reset` recreates. The migration gate (`app/kernel/db/tests/test_migrations.py`) proves a fresh replay equals the models.
- `just generate` after any schema/route change; commit the generated OpenAPI, capability views and TS client.
- Text: user-visible strings only through `i18n/{en,de,fr}.json`; a missing key fails `just check`.
- Commits: conventional, `feat`/`fix` carry a `User-visible:` line, trailer `Assisted-by: OpenCode (<model>)`, never `--no-verify`.
- Servers never send prose to the UI — codes and parameters only (spec, #582).
- The schema cut is two revisions (A then B) so every task's gates are green; columns the code no longer reads are dropped in the second.
- The only provider a test may fake is a `kind=fake` provider row at the boundary; E2E drives the real browser, API and database.

## Review Focus

1. Deleting a provider that models point at — must be a 409 naming them, never a cascade that silently drops a task's assignment.
2. An OpenRouter model id containing a slash (`z-ai/glm-5.3-flash`) — the catalog lookup must ask `openrouter/z-ai/glm-5.3-flash`, not `openrouter/glm-5.3-flash`.
3. A provider whose `models_url` sits on another host — discovery must ask it anonymously.
4. A stream that dies mid-answer — coded error frame, no done frame, and the audit row carries `error_code`.
5. A preset whose vendor is absent from the snapshot — empty datalist, free text still saves, cost stays NULL.

---

### Task 1: Schema step A — the provider table

**Files:**
- Modify: `app/kernel/llm/models.py`
- Rename: `app/kernel/llm/profiles.py` → `app/kernel/llm/repositories.py`
- Create: `app/kernel/db/migrations/versions/<rev>_llm_providers.py` (via `just db-revision`)
- Modify: `app/kernel/llm/resolution.py`, `app/capabilities/chat/tests/test_chat.py`, `app/capabilities/writing/tests/test_continuation.py`, `app/capabilities/settings/profiles_service.py`, `app/kernel/tests/test_llm_*.py`, `app/api/test_callers_tool.py` (import path only)
- Test: `app/kernel/db/tests/test_migrations.py`, `app/kernel/tests/test_llm_providers.py`

**Interfaces:**
- Produces: `LLMProvider` (`llm_providers`), `ProviderProfile.provider_id: UUID` (nullable in this revision), `PROVIDER_KINDS = ("fake", "openai-chat")`, `ProviderRepository` in `app.kernel.llm.repositories`.

- [x] **Step 1: Write the failing repository test**

```python
# app/kernel/tests/test_llm_providers.py
async def test_a_provider_is_created_under_its_owner() -> None:
    provider = await ProviderRepository(session, user_id).create(
        name="OpenCode Go", kind="openai-chat",
        base_url="https://opencode.ai/inference/go/openai/v1",
        models_url=None, vendor="opencode-go", api_key="", api_key_hint="1234",
    )
    assert provider.name == "OpenCode Go"
    assert provider.vendor == "opencode-go"
```

- [x] **Step 2: Run it to see it fail**

Run: `just test-file app/kernel/tests/test_llm_providers.py`
Expected: FAIL — `LLMProvider`/`ProviderRepository` do not exist.

- [x] **Step 3: Add the table and the repository**

`models.py`: `class LLMProvider(UserOwned)` with `__tablename__ = "llm_providers"` and the columns `name String(120)`, `kind String(40)`, `base_url String(500)`, `models_url String(500)`, `vendor String(40)`, `api_key Text default ""`, `api_key_hint String(8)`, `created_at`, `updated_at`; `ProviderProfile` gains `provider_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("llm_providers.id", ondelete="CASCADE"))`; `PROVIDER_KINDS = ("fake", "openai-chat")`.
`repositories.py`: `class ProviderRepository(ScopedRepository[LLMProvider])` with `get(provider_id)`, `ordered()`, `create(**fields)`, `update(provider, **fields)`, `delete(provider)` — the shapes `ProfileRepository` already has.

- [x] **Step 4: Draft the revision and hand-write the backfill**

Run: `just db-revision "llm providers, one row per profile"`
Then in the generated file, after `op.add_column("provider_profiles", …)`:

```python
op.execute("""
    INSERT INTO llm_providers (id, user_id, name, kind, base_url, models_url,
        vendor, api_key, api_key_hint, created_at, updated_at)
    SELECT p.id, p.user_id, p.name, p.kind, p.base_url, NULL, NULL,
        p.api_key, p.api_key_hint, now(), now()
    FROM provider_profiles p
""")
op.execute("UPDATE provider_profiles SET provider_id = id")
```

The profile's own id becomes the provider's id — a 1:1 mapping with nothing to guess. `downgrade()` raises like every revision in this history (ADR-103: restore is from the pre-upgrade dump, never a downgrade script).

- [x] **Step 5: Write the backfill test**

```python
# app/kernel/db/tests/test_migrations.py — new test
async def test_the_provider_step_gives_every_profile_a_provider(...) -> None:
    # upgrade to the revision before the provider step, insert one profile row,
    # upgrade to head, then:
    assert await scalar("SELECT count(*) FROM llm_providers") == 1
    assert await scalar("SELECT provider_id FROM provider_profiles") == profile_id
```

- [x] **Step 6: Run the kernel and settings suites**

Run: `just test-file app/kernel/tests/test_llm_providers.py`, `just test-file app/kernel/db/tests/test_migrations.py`, `just check`
Expected: PASS; `just check` clean (nothing reads the new column yet).

- [x] **Step 7: Commit**

```bash
git add app/kernel docs/superpowers
git commit -m "feat(kernel): give provider profiles a provider row" \
  --trailer "Assisted-by: OpenCode (<model>)"
```

---

### Task 2: Providers API

**Files:**
- Create: `app/capabilities/settings/providers_service.py`, `app/capabilities/settings/tests/test_providers.py`
- Modify: `app/capabilities/settings/schemas.py`, `app/capabilities/settings/router.py`
- Test: `app/capabilities/settings/tests/test_providers.py`

**Interfaces:**
- Consumes: `ProviderRepository` (Task 1).
- Produces: `ProviderService` with `list()`, `create(payload) -> tuple[LLMProvider, str | None]`, `update(provider_id, payload)`, `delete(provider_id)`, `discover(provider_id) -> list[str]`; routes `GET/POST /api/settings/providers`, `PATCH/DELETE /api/settings/providers/{provider_id}`, `GET /api/settings/providers/{provider_id}/models`; schemas `ProviderCreate`, `ProviderUpdate`, `ProviderRead`, `ProviderCreated`.

- [ ] **Step 1: Write the failing gate tests**

```python
async def test_a_remote_provider_without_a_key_is_refused(client) -> None:
    response = await client.post("/api/settings/providers", json={
        "name": "Vendor", "kind": "openai-chat", "base_url": "https://api.vendor.example/v1",
    })
    assert response.status_code == 422
    assert "api_key" in response.text

async def test_a_provider_with_models_cannot_be_deleted(client, seeded_model) -> None:
    response = await client.delete(f"/api/settings/providers/{seeded_model.provider_id}")
    assert response.status_code == 409
    assert "GLM" in response.json()["detail"]        # names the model, not a count
```

- [ ] **Step 2: Run it to see it fail**

Run: `just test-file app/capabilities/settings/tests/test_providers.py`
Expected: FAIL — 404, the route does not exist.

- [ ] **Step 3: Implement the service**

Move the gate out of `ProfileService`: `kind` in `PROVIDER_KINDS`, `base_url` set and `https` for a remote kind, `api_key` required when `needs_api_key(base_url)`. Key storage stays `secrets.save_key(provider.id, key)`; the one plaintext response is the create's. `delete` refuses with `ProviderHasModelsError` naming the models (`select count` via `ProfileRepository.count_for_provider`). Discovery keeps today's SDK call in this task.

- [ ] **Step 4: Implement the schemas and routes**

`ProviderRead` carries `id, name, kind, base_url, models_url, vendor, api_key_mask`; `ProviderCreated` adds `api_key`. Router docstring gains the new failure list (409 provider-has-models).

- [ ] **Step 5: Run the tests and regenerate the client**

Run: `just test-file app/capabilities/settings/tests/test_providers.py`, `just generate`, `just check`
Expected: PASS; `web/lib/api/schema.ts` gains the provider operations.

- [ ] **Step 6: Commit**

```bash
git add app/capabilities/settings app/generated web/lib/api
git commit -m "feat(settings): a providers resource with its own gate" \
  --trailer "Assisted-by: OpenCode (<model>)"
```

---

### Task 3: The cut — models under a provider

**Files:**
- Modify: `app/kernel/llm/resolution.py`, `app/kernel/llm/catalog.py`, `app/kernel/llm/repositories.py`, `app/capabilities/settings/profiles_service.py`, `app/capabilities/settings/schemas.py`, `app/capabilities/settings/router.py`
- Create: `app/capabilities/settings/web/ProvidersSection.tsx`, `ModelsSection.tsx`, `TasksSection.tsx`
- Rewrite: `app/capabilities/settings/web/ProvidersPanel.tsx` (composition), delete `ProvidersPanel.test.tsx` in favour of `ProvidersSection.test.tsx` + `ModelsSection.test.tsx`
- Modify: `i18n/{en,de,fr}.json`, `app/capabilities/settings/e2e/test_profiles_e2e.py`, `app/capabilities/settings/tests/{test_profiles,test_tasks}.py`, `app/kernel/tests/test_llm_resolution.py`, `app/capabilities/settings/web/SettingsHub.test.tsx`

**Interfaces:**
- Consumes: `ProviderRepository`, `ProviderService` (Tasks 1–2).
- Produces: `ModelCreate`/`ModelUpdate`/`ModelRead` (renamed from `Profile*`) carrying `provider_id`; `ModelService` (renamed from `ProfileService`) with `list/test/tasks/assign` — no singular model read, the list is every consumer's source (model-level discovery is gone with Task 3: discovery lives on the provider, Task 2's route); `from_profile(profile: ProviderProfile, provider: LLMProvider) -> ResolvedProvider`; `effective_info(model_id, *, vendor, profile_context_window, profile_max_output_tokens)`.

- [ ] **Step 1: Write the failing resolution test**

```python
# app/kernel/tests/test_llm_resolution.py
async def test_a_model_resolves_through_its_provider() -> None:
    provider = await providers.create(name="P", kind="openai-chat",
        base_url="http://127.0.0.1:9/v1", vendor="opencode-go", api_key="")
    await profiles.create(name="M", provider_id=provider.id, model="glm-5.3-flash")
    resolved = await resolve_provider(session, user_id, "chat.ask")
    assert resolved.kind == "openai-chat"
    assert resolved.base_url == "http://127.0.0.1:9/v1"
    assert resolved.info.context_window == 1_000_000

async def test_the_same_model_is_priced_per_provider() -> None:
    # two providers, vendors "opencode" and "openrouter", both serving glm-5.3-flash
    assert opencode_model.info.context_window == 1_000_000
    assert openrouter_model.info.context_window == 1_048_576
```

- [ ] **Step 2: Run it to see it fail**

Run: `just test-file app/kernel/tests/test_llm_resolution.py`
Expected: FAIL — `from_profile()` takes one argument; the model carries no provider.

- [ ] **Step 3: Move resolution to the two levels**

`resolve_provider` loads the profile, then `ProviderRepository.get(profile.provider_id)`; `from_profile(profile, provider)` branches on `provider.kind`, reads the key from the provider, and passes `provider.vendor` into `_merged`. `effective_info` tries `f"{vendor}/{model_id}"` first when a vendor is given, then the existing tiers. `catalog.py` also gains `vendor_models(vendor) -> tuple[str, ...]` (bare ids, sorted; `()` for an unknown vendor) and `snapshot_date() -> str | None` reading the payload's `snapshot_date` when present.

- [ ] **Step 4: Switch the settings service and its schemas**

`ModelCreate` requires `provider_id` and `model`; the gate checks the provider exists and belongs to the user. `ModelService.test()` builds `from_profile(profile, provider)`. Keys, masks and the default flip move to the provider. The routes keep their `/api/settings/profiles` path in this task.

- [ ] **Step 5: Split the panel and add the provider select**

`ProvidersSection` lists providers (name, kind, base URL, mask) with create/edit/delete; `ModelsSection` lists models with a provider select, model text field, tunables, default and test; `TasksSection` keeps the assignment selects, labels now `"{provider} · {model}"`. `ProvidersPanel` composes the three, and `SettingsHub.test.tsx` follows the page's new reads. i18n keys for the three headings and the provider fields in en, de, fr.

- [ ] **Step 6: Run the suites the cut touches**

Run: `just test-file app/kernel/tests/test_llm_resolution.py`, `just test`, `just test-frontend`, `just test-e2e settings`, `just check`
Expected: PASS on all five.

- [ ] **Step 7: Commit**

```bash
git add app i18n web/lib
git commit -m "feat(settings): models hang off a provider" \
  --trailer "Assisted-by: OpenCode (<model>)"
```

---

### Task 4: Schema step B — drop what moved, rename the models route

**Files:**
- Create: `app/kernel/db/migrations/versions/<rev>_drop_profile_provider_columns.py`
- Rename: `app/capabilities/settings/profiles_service.py` → `models_service.py`
- Modify: `app/kernel/llm/models.py`, `app/kernel/llm/repositories.py`, `app/capabilities/settings/{router,schemas}.py`, `app/capabilities/settings/web/*.tsx`, `app/capabilities/settings/tests/*`
- Test: `app/kernel/db/tests/test_migrations.py`, `app/capabilities/settings/tests/test_models.py` (renamed from `test_profiles.py`)

**Interfaces:**
- Produces: `provider_profiles.provider_id` NOT NULL; routes `/api/settings/models` and `/api/settings/models/{model_id}` (the `/profiles` paths disappear).

- [ ] **Step 1: Write the failing route test**

```python
async def test_models_live_at_their_own_path(client) -> None:
    assert (await client.get("/api/settings/models")).status_code == 200
    assert (await client.get("/api/settings/profiles")).status_code == 404
```

- [ ] **Step 2: Draft and hand-write the revision**

Run: `just db-revision "drop the provider columns the model no longer owns"`
The revision sets `provider_id` NOT NULL, then drops `kind`, `base_url`, `api_key`, `api_key_hint` from `provider_profiles`. `downgrade()` raises (ADR-103).

- [ ] **Step 3: Drop the columns from the model and rename the routes**

`ProviderProfile` loses the five fields; `_masked()` and the gate read only the provider; `profiles_service.py` becomes `models_service.py` (its class already renamed in Task 3). Router paths become `/models`; schemas keep their names.

- [ ] **Step 4: Move the web and the tests with it**

All `client.GET("/api/settings/profiles")` become `/models`; `just generate` rewrites the client; the E2E follows the UI, not the path.

- [ ] **Step 5: Run every gate the rename touches**

Run: `just test`, `just test-frontend`, `just test-e2e settings`, `just check`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app i18n web
git commit -m "refactor(settings): the model route is named for what it holds" \
  --trailer "Assisted-by: OpenCode (<model>)"
```

---

### Task 5: The native Anthropic adapter

**Files:**
- Create: `app/kernel/llm/anthropic_messages.py`, `app/kernel/tests/test_llm_anthropic.py`
- Modify: `app/kernel/llm/models.py` (`PROVIDER_KINDS`), `app/kernel/llm/contract.py` (the two typed failures), `app/kernel/llm/openai_chat.py` (raise them), `app/kernel/llm/resolution.py` (`ANTHROPIC_DEFAULT_BASE_URL`, the branch), `app/kernel/testing/vendor.py` (a Messages stand-in), `app/kernel/tests/test_llm_openai_chat.py`, `i18n/*.json` (the `anthropic` kind label), `app/capabilities/settings/web/ProvidersSection.tsx` (kind labels)

**Interfaces:**
- Produces: `AnthropicMessagesProvider(base_url, model, api_key, request_timeout, temperature_default)` with `stream(request) -> AsyncIterator[CompletionEvent]`; `PROVIDER_KINDS = ("fake", "openai-chat", "anthropic")`; `ModelNotFoundError(model)` and `ProviderAuthError` in `contract.py`, raised by both adapters.

- [ ] **Step 1: Add the stand-in and its failing test**

```python
# app/kernel/testing/vendor.py — messages_vendor(), same pattern as chat_vendor()
# app/kernel/tests/test_llm_anthropic.py
async def test_the_adapter_maps_the_messages_stream() -> None:
    with messages_vendor() as vendor:
        events = [e async for e in _provider(vendor.base_url).stream(
            CompletionRequest.user("Hi"))]
    assert events == [Delta("Hel"), Delta("lo"), Usage(4, 2), DONE]

async def test_a_missing_model_is_named() -> None:
    with messages_vendor() as vendor:
        vendor.refuse_requests(404, {"type": "error", "error": {"type": "not_found_error"}})
        with pytest.raises(ModelNotFoundError) as raised:
            [e async for e in _provider(vendor.base_url).stream(CompletionRequest.user("Hi"))]
    assert raised.value.model == "vendor-mini"
```

- [ ] **Step 2: Run it to see it fail**

Run: `just test-file app/kernel/tests/test_llm_anthropic.py`
Expected: FAIL — module and vendor do not exist.

- [ ] **Step 3: Implement the adapter**

`POST {base_url}/messages`, headers `x-api-key`, `anthropic-version: 2023-06-01`, body `{model, messages, max_tokens: request.max_tokens or 4096, stream: true}`, plus `system` hoisted and joined with `\n`; `temperature` only when configured. `response_schema` adds `anthropic-beta: structured-outputs-2025-11-13` and `output_format: {"type": "json_schema", "schema": …}`. Events: `message_start` → input tokens remembered, `content_block_delta`/`text_delta` → `Delta`, `message_delta` → output tokens, `message_stop` → one `DONE`; an `error` event or non-2xx raises without `DONE`. Use `httpx.AsyncClient` with `TIMEOUT`.

- [ ] **Step 4: Wire the kind**

`resolution.from_profile` builds it for `kind == "anthropic"` with `ANTHROPIC_DEFAULT_BASE_URL = "https://api.anthropic.com/v1"`; the settings gate applies the same rules as `openai-chat`; the kind label joins the i18n catalogs.

- [ ] **Step 5: Run the adapter and resolution suites**

Run: `just test-file app/kernel/tests/test_llm_anthropic.py`, `just test-file app/kernel/tests/test_llm_resolution.py`, `just check`
Expected: PASS — including a 401 raising `ProviderAuthError` and a 404 `ModelNotFoundError` under a test that pins the mapping for both.

- [ ] **Step 6: Commit**

```bash
git add app i18n
git commit -m "feat(kernel): a native Anthropic Messages adapter" \
  --user-visible "Claude works through its own API, structured answers included." \
  --trailer "Assisted-by: OpenCode (<model>)"
```

---

### Task 6: Presets and the model picker

**Files:**
- Create: `app/kernel/llm/presets.py`, `app/kernel/tests/test_llm_presets.py`
- Modify: `app/capabilities/settings/{router,schemas,providers_service}.py`, `app/capabilities/settings/web/ProvidersSection.tsx`, `app/capabilities/settings/web/ModelsSection.tsx`, `i18n/*.json`, `app/capabilities/settings/tests/test_providers.py`, `app/capabilities/settings/web/{ProvidersSection,ModelsSection}.test.tsx`

**Interfaces:**
- Produces: `ProviderPreset(id, label, kind, base_url, models_url, vendor, model, note_key=None)`, `PRESETS: tuple[ProviderPreset, ...]`, `preset(preset_id) -> ProviderPreset | None`; `GET /api/settings/presets -> list[PresetRead]` where `PresetRead` is the preset plus `models: list[str]` (from `vendor_models`) and `snapshot_date: str | None`.

- [ ] **Step 1: Write the failing preset-table test**

```python
def test_the_presets_name_only_known_vendors() -> None:
    known = {entry.split("/")[0] for entry in load_catalog()}
    assert {p.vendor for p in PRESETS} <= known
    assert [p.id for p in PRESETS] == ["openai", "anthropic", "xai", "google",
        "openrouter", "opencode", "opencode-go", "zai", "zai-coding-plan"]

def test_an_unknown_vendor_has_no_models() -> None:
    assert vendor_models("nope") == ()
```

- [ ] **Step 2: Run it to see it fail**

Run: `just test-file app/kernel/tests/test_llm_presets.py`
Expected: FAIL — `app.kernel.llm.presets` does not exist.

- [ ] **Step 3: Write the table**

```python
PRESETS = (
    ProviderPreset("openai", "OpenAI", "openai-chat",
        "https://api.openai.com/v1", None, "openai", "gpt-5.4"),
    ProviderPreset("anthropic", "Claude", "anthropic",
        "https://api.anthropic.com/v1", None, "anthropic", "claude-sonnet-5-5"),
    ProviderPreset("xai", "Grok", "openai-chat",
        "https://api.x.ai/v1", None, "xai", "grok-4.7"),
    ProviderPreset("google", "Gemini", "openai-chat",
        "https://generativelanguage.googleapis.com/v1beta/openai", None,
        "google", "gemini-3.8-flash"),
    ProviderPreset("openrouter", "OpenRouter", "openai-chat",
        "https://openrouter.ai/api/v1", None, "openrouter", "z-ai/glm-5.3-flash"),
    ProviderPreset("opencode", "OpenCode", "openai-chat",
        "https://opencode.ai/inference/openai/v1",
        "https://opencode.ai/inference/v1/models", "opencode", "glm-5.3-flash"),
    ProviderPreset("opencode-go", "OpenCode Go", "openai-chat",
        "https://opencode.ai/inference/go/openai/v1",
        "https://opencode.ai/inference/go/v1/models", "opencode-go", "glm-5.3-flash"),
    ProviderPreset("zai", "Z.ai", "openai-chat",
        "https://api.z.ai/api/paas/v4", None, "zai", "glm-5.3"),
    ProviderPreset("zai-coding-plan", "Z.ai Coding Plan", "openai-chat",
        "https://api.z.ai/api/coding/paas/v4", None, "zai-coding-plan",
        "glm-5.3", "settings.providers.note.zaiCodingPlan"),
)
```

- [ ] **Step 4: Add the read and the picker**

`GET /api/settings/presets` returns each preset with `models=vendor_models(vendor)` and `snapshot_date()`, cached per process because the catalog is static. The provider form gains a preset select that fills name, kind, base URL, models URL, vendor and model, and clears the key field; the model input becomes an `<input list="…">` fed from the provider's preset models, and the list names the catalog's date beneath it. i18n gains the select's label and the z.ai note in en, de, fr. A preset whose vendor is absent yields an empty list — saving still works with free text.

- [ ] **Step 5: Run the suites**

Run: `just test-file app/kernel/tests/test_llm_presets.py`, `just test-file app/capabilities/settings/tests/test_providers.py`, `just test-frontend`, `just check`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app i18n web
git commit -m "feat(settings): providers come from presets, models from the catalog" \
  --user-visible "Ten providers are one click away; the model list is there before a key is." \
  --trailer "Assisted-by: OpenCode (<model>)"
```

---

### Task 7: Discovery that asks the provider

**Files:**
- Modify: `app/capabilities/settings/providers_service.py`, `app/capabilities/settings/router.py`, `app/capabilities/settings/web/ProvidersSection.tsx`, `app/kernel/testing/vendor.py`, `app/capabilities/settings/tests/test_providers.py`, `app/capabilities/settings/web/ProvidersSection.test.tsx`

**Interfaces:**
- Produces: `ProviderService.discover(provider_id)` issuing `GET models_url or f"{base_url}/models"` with `Authorization: Bearer` for `openai-chat` and `x-api-key` + `anthropic-version: 2023-06-01` for `anthropic`; the key is sent only when the two URLs share a host.

- [ ] **Step 1: Write the failing discovery tests**

```python
async def test_discovery_asks_the_providers_own_list_url(client, vendor) -> None:
    # provider: base_url = vendor.base_url, models_url = vendor.models_url (another path)
    ids = (await client.get(f"/api/settings/providers/{pid}/models")).json()
    assert "vendor-mini" in ids
    assert vendor.list_requests == 1        # the /models path on base_url was never asked

async def test_discovery_keeps_the_key_on_the_endpoint_host(client, vendor) -> None:
    # models_url points at a second stand-in with another host
    await client.get(f"/api/settings/providers/{pid}/models")
    assert other.authorization is None
```

- [ ] **Step 2: Run them to see them fail**

Run: `just test-file app/capabilities/settings/tests/test_providers.py -k discovery`
Expected: FAIL — the SDK call still asks `{base_url}/models` and always sends Bearer.

- [ ] **Step 3: Replace the SDK call with httpx**

`httpx.AsyncClient` with `DISCOVERY_TIMEOUT`; URL as above; `data[].id` parsed and sorted; host comparison via `httpx.URL(...).host`; a transport failure still maps to the router's 502.

- [ ] **Step 4: Extend the stand-ins**

`chat_vendor()` gains a second list path and records the `Authorization` header; a new small `list_vendor()` answers a different host's list and records whether a key arrived.

- [ ] **Step 5: Wire the button and run**

The providers section offers *Modelle laden* per provider and shows the ids; the models form can copy one into its field. Run `just test-file app/capabilities/settings/tests/test_providers.py`, `just test-frontend`, `just check` — PASS.

- [ ] **Step 6: Commit**

```bash
git add app web
git commit -m "fix(settings): discovery asks the provider's own list url" \
  --user-visible "Loading a provider's models works at OpenCode and OpenCode Go too." \
  --trailer "Assisted-by: OpenCode (<model>)"
```

---

### Task 8: Failure codes instead of an empty frame

**Files:**
- Modify: `app/kernel/llm/contract.py` (`error_code()`), `app/kernel/llm/streaming.py`, `app/kernel/llm/audit.py`, `app/kernel/llm/models.py` (`LlmCall.error_code`), `app/capabilities/writing/router.py`, `app/capabilities/chat/router.py`, `app/capabilities/writing/web/ChapterEditor.tsx`, `app/capabilities/chat/web/ChatPanel.tsx`, `i18n/*.json`
- Create: `app/kernel/db/migrations/versions/<rev>_llm_call_error_code.py`
- Test: `app/kernel/tests/test_llm_streaming.py`, `app/capabilities/writing/web/ChapterEditor.test.tsx`, `app/capabilities/chat/web/ChatPanel.test.tsx`, `app/capabilities/writing/tests/test_continuation.py`

**Interfaces:**
- Consumes: `ModelNotFoundError`, `ProviderAuthError` (Task 5).
- Produces: `error_code(failure) -> str` (`"model-not-found" | "provider-auth" | "unknown"`) in `contract.py`; `error_frame(code: str, **params) -> str` and `error_events(code: str = "unknown", **params)` in `streaming.py`; `LlmCall.error_code`.

- [ ] **Step 1: Write the failing frame test**

```python
def test_a_missing_model_gets_its_own_frame() -> None:
    assert error_frame("model-not-found", model="glm-5.3") == (
        'event: error\ndata: {"code": "model-not-found", "model": "glm-5.3"}\n\n')
```

- [ ] **Step 2: Run it to see it fail**

Run: `just test-file app/kernel/tests/test_llm_streaming.py`
Expected: FAIL — `error_frame` does not exist.

- [ ] **Step 3: Add the codes, the frame and the audit column**

`just db-revision "llm call error code"` adds the nullable column. `audited_stream` derives `error_code(failure)` and writes it. Writing and chat yield `error_frame(...)` in their `except`; the two pre-call endings become `error_events("key-unavailable")` and `error_events("prompt-refused")`.

- [ ] **Step 4: Teach the surfaces the sentence**

`readFrames` keeps the payload; `ChapterEditor` and `ChatPanel` pick the message by code — `errors.modelNotFound` = "The provider no longer serves "{model}". Pick another under Settings → Models.", `errors.providerAuth`, `errors.keyUnavailable`, `errors.unknown` (today's text) — in en, de, fr, each with a link to `/settings/provider`.

- [ ] **Step 5: Run the suites**

Run: `just test-file app/kernel/tests/test_llm_streaming.py`, `just test-file app/capabilities/writing/tests/test_continuation.py`, `just test-frontend`, `just check`
Expected: PASS — a stream that dies yields exactly one error frame, no done frame, and the audit row carries the code.

- [ ] **Step 6: Commit**

```bash
git add app i18n web
git commit -m "fix(kernel): a stream failure names its cause" \
  --user-visible "A model the provider stopped serving now says so and points at the settings." \
  --trailer "Assisted-by: OpenCode (<model>)"
```

---

### Task 9: Model state on the settings page

**Files:**
- Modify: `app/capabilities/settings/schemas.py` (`ModelRead`, `TaskEffectiveRead.profile_id`), `models_service.py` (last audit row), `router.py`, `app/capabilities/settings/web/ModelsSection.tsx`, `TasksSection.tsx`, `i18n/*.json`
- Test: `app/capabilities/settings/tests/test_models.py`, `app/capabilities/settings/web/ModelsSection.test.tsx`

**Interfaces:**
- Produces: `ModelRead.last_error_code: str | None`, `last_error_at: datetime | None`; `TaskEffectiveRead.profile_id: UUID | None`; the model row's three marks.

- [ ] **Step 1: Write the failing read test**

```python
async def test_a_model_reports_its_last_failure(client, session) -> None:
    await _failed_call(session, profile_id=model.id, error_code="model-not-found")
    row = next(m for m in (await client.get("/api/settings/models")).json() if m["id"] == str(model.id))
    assert row["last_error_code"] == "model-not-found"
```

- [ ] **Step 2: Run it to see it fail**

Run: `just test-file app/capabilities/settings/tests/test_models.py -k last_failure`
Expected: FAIL — the key is absent.

- [ ] **Step 3: Read the newest audit row per model**

One `select(LlmCall).where(user_id, profile_id).order_by(created_at.desc()).limit(1)` per model in the list (the list is small); the read never writes.

- [ ] **Step 4: Show the three marks**

*Preis unbekannt* when the catalog has no `vendor/model`; *Nicht im aktuellen Angebot (Liste vom …)* when the model is absent from a live list fetched this session; *Letzter Aufruf fehlgeschlagen: <localised code> (<date>)* from the row. The model form merges the catalog list with the live list in its datalist, and warns before saving from local facts only — *not in the list you just loaded — save anyway?*, *no catalog entry — the price will be unknown* — never by calling the vendor. The tasks section joins on `profile_id` and shows the same mark. i18n in en, de, fr.

- [ ] **Step 5: Run the suites**

Run: `just test-file app/capabilities/settings/tests/test_models.py`, `just test-frontend`, `just check`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app i18n web
git commit -m "feat(settings): a model shows whether it still works" \
  --user-visible "Settings marks models the provider no longer serves and models with no known price." \
  --trailer "Assisted-by: OpenCode (<model>)"
```

---

### Task 10: E2E, ADR amendment and the record

**Files:**
- Modify: `app/capabilities/settings/e2e/test_profiles_e2e.py` (rename to `test_providers_e2e.py`), `docs/architecture/decisions/ADR-102-provider-profiles-and-key-storage.md`, `docs/superpowers/follow-ups.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Write the failing E2E case**

```python
def test_a_provider_carries_models_and_tasks_use_them(page):
    # create a provider from the OpenCode Go preset (fields filled, key typed),
    # add two models from its catalog list, assign two tasks to them
    expect(page.get_by_text("OpenCode Go · GLM 5.3 Flash")).to_be_visible()
```

- [ ] **Step 2: Run it to see it fail**

Run: `just test-e2e settings`
Expected: FAIL — the flow does not exist yet.

- [ ] **Step 3: Finish the E2E**

The case drives the real UI, the real API and the real database; it presses neither *Test* nor *Modelle laden*, so no vendor is called. Rename the module to `test_providers_e2e.py` and keep every existing case.

- [ ] **Step 4: Record the cut**

ADR-102 gains a dated *Amendment* section: a provider is now a row with endpoint, key and vendor; models hang off it; the reason and a pointer to the spec. The same amendment updates the ADR's layout sentence that still names `app/kernel/llm/profiles.py` (now `repositories.py`), and `docs/_shared/CONSTRAINTS.md`'s "A provider is a profile row" line moves with the same change. `docs/superpowers/follow-ups.md` gains this wave's row when the index issue opens (none yet).

- [ ] **Step 5: Run the whole gate**

Run: `just verify all`, `just test-e2e settings`
Expected: PASS, output read in full.

- [ ] **Step 6: Commit**

```bash
git add app docs
git commit -m "test(settings): the providers-and-models flow, end to end" \
  --trailer "Assisted-by: OpenCode (<model>)"
```
