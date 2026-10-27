# WP2a — Providers, Catalog, Keychain, Settings Route Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Per-user provider profiles with per-task assignment, a vendored models.dev catalog that prices every call, encrypted API keys, and the `/settings` route — WP2a, first half of the WP2 split.

**Architecture:** Kernel owns the models (`ProviderProfile`, `TaskAssignment` beside `LlmCall`), the secrets tiers, the catalog and the resolution cascade; the settings capability serves HTTP and the new `/settings` page. `resolve_provider` returns a `ResolvedProvider` (provider + facts) that the audit and WP2b's allocator consume. The `openai-chat` adapter moves onto the `openai` SDK; the hand-rolled httpx parser is deleted.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy async, Postgres, `openai` (new), `keyring` + `cryptography` (new), React + TanStack Router, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-26-wp2a-providers-catalog-settings-design.md` (moved there from `~/.opencode/plan/` by the build session before T1 starts — the plan argues from the spec; executors read both).

**Baseline:** `main` at `b2c499c3` (WP1 merged as #295). Branch: `wp2a-providers`.

## Global Constraints

- en/de/fr for every user-visible string in the same commit (`i18n/{en,de,fr}.json`, missing key = build error, German du-form). English in code, comments, tests, docs.
- Conventional commits; `feat`/`fix` carry a real `User-visible:` line. Nothing committed before the review is green; `--no-verify` and force push are forbidden.
- No capability imports another capability; shared domain in `app/kernel/`. Every user-owned row via `UserOwned` + `ScopedRepository` (`app/kernel/db/base.py`).
- No side effect in the request path beyond the request's transaction (`LlmCall` is the §3.4 log-row exception).
- `just check` before every commit; `just verify` before the WP closes; `just db-reset` after model changes (no migrations); `just generate` after `capability.yaml`/route changes.
- E2E on real UI + real API + real Postgres; the fake only at the LLM/embeddings boundary; `assert_accessible` on every page visited.
- No new rule, registry, check script, hook, required field or mandatory document (`NEEDS-APPROVAL` otherwise). Accepted packages only: `openai`, `keyring`, `cryptography`.
- The API key never appears in logs, in `LlmCall`, in tracebacks, or in any response after create.

## Review Focus

1. **Per-user isolation:** two users, distinct defaults — user B's continuation must never resolve user A's profile. Test in Task 3.
2. **Deleted assigned profile:** deleting a non-default profile cascades its assignments; affected tasks fall down the cascade, no 500. Tests in Tasks 3 and 4.
3. **Environment-tier regression:** the four existing capabilities' unit + E2E suites stay green, unmodified, in Task 3 — the env tier is behaviour-identical.
4. **Key leakage:** after create, no response, log line or `LlmCall` row contains the full key; masked reads show the last four only. Tests in Tasks 1 and 4.
5. **Price truth table:** unknown model on a remote endpoint costs NULL (never 0); any model on a local endpoint 0.0; fake 0.0. Tests in Task 2.
6. **Lost keychain:** a key missing from the keyring fails the call with a named error naming the profile; the masked list still shows the hint. Test in Task 1.

---

### Task 1: Models, keychain tiers, repositories

**Files:**
- Create: `app/kernel/secrets.py`
- Create: `app/kernel/llm/profiles.py`
- Modify: `app/kernel/llm/models.py` (add `ProviderProfile`, `TaskAssignment`; `LlmCall.profile_id`)
- Test: `app/kernel/tests/test_secrets.py`, `app/kernel/tests/test_llm_profiles.py`

**Interfaces:**
- Consumes: `UserOwned`, `ScopedRepository` from `app.kernel.db.base`.
- Produces (Task 3/4 rely on these exact names):
  - `ProviderProfile` columns: `id, user_id, name, kind, base_url, model, api_key, api_key_hint, is_default, context_window, max_output_tokens, temperature, request_timeout, created_at, updated_at`. `kind` free-text column; the closed vocabulary `PROFILE_KINDS = ("fake", "openai-chat")` lives in this module.
  - `TaskAssignment` columns: `id, user_id, task_key, profile_id (FK ProviderProfile, CASCADE), created_at, updated_at`, `UniqueConstraint(user_id, task_key)`.
  - `LlmCall.profile_id: Mapped[UUID | None]` — plain `Uuid`, no FK (a log row outlives its profile).
  - `secrets.save_key(profile_id: UUID, plaintext: str) -> str` — returns what the `api_key` column holds: `""` in the keyring tier, Fernet ciphertext in the Fernet tier. Raises `secrets.NoKeyStoreError` when no keychain and `NARRE_SECRET_KEY` is unset.
  - `secrets.load_key(profile_id: UUID, column: str) -> str` — plaintext from keyring (column empty) or by decrypting; raises `secrets.KeyUnavailableError` (message names the profile id) when the keychain lost it or decryption fails.
  - `secrets.erase_key(profile_id: UUID) -> None`.
  - Tier choice: OS keyring first; `NARRE_SECRET_KEY` Fernet when unavailable; `NARRE_KEYRING=off` forces Fernet (the knob tests use).
  - `ProfileRepository(ScopedRepository[ProviderProfile])`: `get(id) -> ProviderProfile | None`, `ordered() -> Sequence[ProviderProfile]` (default first, then name), `create(**fields)`, `update(profile, **fields)`, `delete(profile)`.
  - `AssignmentRepository(ScopedRepository[TaskAssignment])`: `for_task(task_key) -> TaskAssignment | None`, `for_prefix(prefix: str) -> TaskAssignment | None` (`task_key == prefix` excluded), `set(task_key, profile_id)`, `clear(task_key)`, `list_all()`.

- [ ] **Step 1: Write the failing tests**

`test_secrets.py`: Fernet tier round-trip under a temporary `NARRE_SECRET_KEY`; `NARRE_KEYRING=off` + no secret key → `NoKeyStoreError`; keyring tier via an in-memory `keyring` backend (`keyring.set_keyring`) → column empty, `load_key` reads back; `KeyUnavailableError` when the keyring entry is removed but the hint exists. `test_llm_profiles.py`: `ProviderProfile`/`TaskAssignment` persist through `ScopedRepository` narrowed to their user; `LlmCall.profile_id` round-trips; both tables exist after `db-reset`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `just test-file app/kernel/tests/test_secrets.py` and `just test-file app/kernel/tests/test_llm_profiles.py`
Expected: FAIL (modules/columns do not exist).

- [ ] **Step 3: Implement `app/kernel/secrets.py`, extend `app/kernel/llm/models.py`, add `app/kernel/llm/profiles.py`**

`keyring.get_keyring()` viability decides the tier (a fail/vault backend that raises counts as unavailable). Fernet key = `NARRE_SECRET_KEY` bytes. The hint (`api_key_hint`) is written by the caller (Task 4's service) — `secrets` does not touch the DB. Repositories hold no invariant logic (the settings service owns those, Task 4).

- [ ] **Step 4: `uv add keyring cryptography`; run `just db-reset`; run tests to verify they pass**

Run: `just test-file app/kernel/tests/test_secrets.py && just test-file app/kernel/tests/test_llm_profiles.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/kernel/secrets.py app/kernel/llm/models.py app/kernel/llm/profiles.py \
  app/kernel/tests/test_secrets.py app/kernel/tests/test_llm_profiles.py pyproject.toml uv.lock
git commit -m "feat(kernel): provider profiles and assignment rows with tiered key storage

User-visible: a user's API keys are stored encrypted or in the OS keychain, never in plaintext"
```

### Task 2: Catalog, lookup cascade, cost

**Files:**
- Create: `app/kernel/llm/catalog.py`, `app/kernel/llm/data/__init__.py`, `app/kernel/llm/data/models.json`, `app/kernel/llm/data/refresh.py`
- Modify: `app/kernel/llm/audit.py` (`record_call` computes and stores `cost_usd`)
- Modify: `THIRD-PARTY-NOTICES.md` (models.dev attribution, snapshot date)
- Test: `app/kernel/tests/test_llm_catalog.py`

**Interfaces:**
- Consumes: `LlmCall`, `record_call` signature (gains `profile_id: UUID | None = None`, `base_url: str | None = None`).
- Produces (Tasks 3/4 rely on):
  - `@dataclass(frozen=True) class ModelInfo`: `context_window: int | None`, `max_output_tokens: int | None`, `input_price_per_mtok: float | None`, `output_price_per_mtok: float | None`, `supports_json_schema: bool`, `supports_tools: bool`, `supports_vision: bool`.
  - `def load_catalog() -> dict[str, ModelInfo]` — from `data/models.json` (`snapshot_date` field included).
  - `def effective_info(model_id: str, *, profile_context_window: int | None, profile_max_output_tokens: int | None) -> ModelInfo | None` — exact id → provider prefix (`id.split("/")[0]` matched against any full id's vendor segment) → normalized (lowercase, `-`/`.`/`:`/`_` folded); profile columns override the catalog's.
  - `def compute_cost(info: ModelInfo | None, *, input_tokens: int | None, output_tokens: int | None, base_url: str | None) -> float | None` — truth table: local `base_url` (host in `app.kernel.vendor.LOCAL_HOSTS`) → `0.0`; `info is None` → `None`; prices or tokens missing → `None`; else `(in/1e6)*input_price + (out/1e6)*output_price` rounded to 6 decimals.

- [ ] **Step 1: Write the failing tests**

Truth table over a synthetic catalog (monkeypatched `load_catalog`): priced + remote + tokens → exact sum; unknown model + remote → `None`; priced + local → `0.0`; tokens `None` → `None`. Lookup cascade: exact beats prefix beats normalized; profile override wins. `record_call` writes `cost_usd`/`profile_id` (existing `test_llm_audit.py` extended: one priced-remote row costs, one local row is `0.0`). Smoke: the vendored `models.json` parses, carries `snapshot_date`, and has at least one priced entry.

- [ ] **Step 2: Run tests to verify they fail**

Run: `just test-file app/kernel/tests/test_llm_catalog.py`
Expected: FAIL.

- [ ] **Step 3: Implement the catalog and wire cost into `record_call`**

`refresh.py`: fetches `https://models.dev/api.json`, maps to the compact schema, writes `models.json` with today's `snapshot_date`. Run it **once** now to vendor the snapshot (manual, no recipe, no runtime network). `record_call` computes cost from the passed `info` + `base_url`; callers without a model id pass `info=None` and the column stays `NULL`.

- [ ] **Step 4: Run tests; verify the audit tests pass**

Run: `just test-file app/kernel/tests/test_llm_catalog.py && just test-file app/kernel/tests/test_llm_audit.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/kernel/llm/catalog.py app/kernel/llm/data THIRD-PARTY-NOTICES.md \
  app/kernel/llm/audit.py app/kernel/tests/test_llm_catalog.py app/kernel/tests/test_llm_audit.py
git commit -m "feat(kernel): a vendored model catalog prices every audited call

User-visible: each provider call's cost is computed from the vendored models.dev snapshot instead of staying unknown"
```

### Task 3: Resolution cascade and the per-call audit

**Files:**
- Create: `app/kernel/llm/resolution.py`
- Modify: `app/kernel/llm/__init__.py` (delete `get_provider`, `provider_facts`, `PROVIDERS`), `app/kernel/llm/audit.py` (`audited_stream` takes `ResolvedProvider`), `app/kernel/llm/fake.py` (construction unchanged), `app/capabilities/writing/router.py`, `app/capabilities/chat/router.py`, `app/capabilities/knowledge/jobs.py`
- Test: `app/kernel/tests/test_llm_resolution.py`; modify the three capabilities' existing tests where they monkeypatch `get_provider`

**Interfaces:**
- Consumes: Task 1 repositories, `secrets.load_key`; Task 2 `effective_info`, `compute_cost`.
- Produces (Tasks 4/5 and WP2b rely on):
  - `KNOWN_TASK_KEYS: tuple[str, ...] = ("writing.continuation", "chat.ask", "knowledge.extract-entities", "knowledge.check-consistency", "settings.test")`.
  - `@dataclass(frozen=True) class ResolvedProvider`: `provider: TextProvider`, `profile_id: UUID | None`, `kind: str`, `model: str`, `context_window: int | None`, `max_output_tokens: int | None`, `temperature: float | None`, `request_timeout: float | None`, `base_url: str | None`, `api_key: str | None`. The numeric fields are the **profile's stored columns** (or the catalog's, merged by the resolver via `effective_info`; `None` when neither knows) — WP2b consumes exactly these.
  - `async def resolve_provider(session: AsyncSession, user_id: UUID, task_key: str) -> ResolvedProvider` — cascade: exact `TaskAssignment` → prefix assignment (`task_key.split(".")[0]`) → default profile → environment (`NARRE_LLM_PROVIDER`, values `fake` | `openai-compatible`; the latter is the alias of the `openai-chat` adapter reading `NARRE_LLM_BASE_URL`/`NARRE_LLM_MODEL`/`NARRE_LLM_API_KEY`) → `FakeProvider()`. Unknown task keys resolve (forward-compatible). `secrets.KeyUnavailableError` propagates to the caller (stream error frame / `Job.error`).
  - `audited_stream(resolved: ResolvedProvider, request: CompletionRequest, *, user_id: UUID, task_key: str, novel_id: UUID | None = None)` — records `kind`, `model`, `profile_id`, and the computed cost: `compute_cost(effective_info(resolved.model, profile_context_window=resolved.context_window, profile_max_output_tokens=resolved.max_output_tokens), input_tokens=…, output_tokens=…, base_url=resolved.base_url)`.

- [ ] **Step 1: Write the failing tests**

`test_llm_resolution.py`: exact beats prefix beats default; prefix matches `writing` for `writing.continuation` but not vice versa; deleted assignment falls to default; no profiles → env tier (`openai-compatible` alias yields kind `openai-chat`, env model); no env → fake; **two users with different defaults resolve to their own**; a fake profile carries its `model` through. Monkeypatched-provider capability tests move from `get_provider` to `resolve_provider`.

- [ ] **Step 2: Run to verify failure**

Run: `just test-file app/kernel/tests/test_llm_resolution.py`
Expected: FAIL.

- [ ] **Step 3: Implement `resolution.py`; rewire the three consumers and the audit**

Each consumer calls `resolved = await resolve_provider(session, user_id, "<task_key>")` inside its handler/job and passes `resolved` to `audited_stream` (jobs pass facts to `record_call`). The FastAPI `ProviderDep` dependency is deleted; handlers already hold session and user. Fake construction stays argument-free; `openai-chat` construction lands in Task 4 — until then the env tier constructs the existing `OpenAICompatibleProvider` and the kind name is the only change.

- [ ] **Step 4: Run kernel tests, then the three capabilities' unit suites unchanged**

Run: `just test-file app/kernel/tests/test_llm_resolution.py && just test-file app/capabilities/writing/tests/test_continuation.py && just test-file app/capabilities/knowledge/tests/test_consistency.py`
Expected: PASS — and the suites' assertions other than the monkeypatch sites are unmodified (Review Focus 3).

- [ ] **Step 5: Commit**

```bash
git add -A app/kernel/llm app/kernel/tests/test_llm_resolution.py app/capabilities/writing app/capabilities/chat app/capabilities/knowledge
git commit -m "feat(kernel): providers resolve per user and task, and the audit names the profile

User-visible: which provider profile served a request is recorded per call instead of one process-wide choice"
```

### Task 4: `openai-chat` on the SDK, settings HTTP, chat vendor

**Files:**
- Create: `app/kernel/llm/openai_chat.py`, `app/capabilities/settings/profiles_service.py`
- Delete: `app/kernel/llm/openai_compat.py`
- Modify: `app/kernel/llm/resolution.py` (env tier + profiles construct `OpenAIChatProvider`), `app/capabilities/settings/schemas.py`, `app/capabilities/settings/router.py`, `app/kernel/testing/vendor.py` (chat endpoints)
- Test: `app/kernel/tests/test_llm_openai_chat.py`, `app/capabilities/settings/tests/test_profiles.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces (Task 5 relies on):
  - `class OpenAIChatProvider` — `__init__(self, *, base_url: str, model: str, api_key: str, request_timeout: float | None = None, temperature_default: float | None = None)`. `stream()` maps `CompletionRequest` onto `openai.AsyncOpenAI` (`max_retries=0`, `stream=True`, `stream_options={"include_usage": True}`, `response_format` from `response_schema`); `request.temperature` wins over `temperature_default`; wire semantics (delta order, one `Usage`, `DONE`, raise-once errors) identical to the deleted adapter.
  - `PROFILE_KINDS` gates profile validation.
  - `class ProfileService` (settings capability): `list()`, `create(payload) -> ProfileRead` (first profile auto-default; returns full key once), `update(id, payload)` (empty `api_key` keeps stored), `delete(id)` (refuses the default with 409 naming the way out; cascades assignments), `set_default(id)`, `test(id) -> TestResult` (one cheap completion, audited as `settings.test`), `discover(id) -> list[str]` (`GET {base_url}/models`). Half-configured create/update → 422 with named fields (`openai-chat` needs `model`, and `api_key` when `app.kernel.vendor.needs_api_key(base_url)`).
  - Endpoints on the settings router (prefix `/api/settings`): `GET /profiles`, `POST /profiles` (201), `PATCH /profiles/{id}`, `DELETE /profiles/{id}`, `POST /profiles/{id}/test`, `GET /profiles/{id}/models`, `GET /assignments`, `PUT /assignments/{task_key}` (body `profile_id | null`; unknown task keys allowed). Every read masks the key (`sk-…` + `api_key_hint`).
  - `ChatVendor` in `app/kernel/testing/vendor.py`: openai-shaped `POST /chat/completions` (SSE, usage included) and `GET /models` listing `vendor-mini` and `vendor-max`, on the same `ThreadingHTTPServer` pattern as `EmbeddingsVendor`.

- [ ] **Step 1: Write the failing tests**

`test_llm_openai_chat.py` against the `ChatVendor` over real HTTP: streamed deltas in order, one `Usage`, `DONE`; 401 raises once (count the vendor's received requests — `max_retries=0`); `response_schema` reaches the wire as `response_format`; `temperature_default` applies only when the request sets none. `test_profiles.py`: create/list masked/update-keeps-key/set-default flips in one transaction/delete guard 409/delete cascades assignments/422 half-configured/full key appears exactly once (create response) and never again; `test`/`discover` hit the vendor; the `settings.test` row lands in `llm_calls`.

- [ ] **Step 2: Run to verify failure**

Run: `just test-file app/capabilities/settings/tests/test_profiles.py`
Expected: FAIL.

- [ ] **Step 3: `uv add openai`; implement the adapter, service, endpoints, vendor**

Follow the existing `openai_compat.py` semantics exactly — this is a transport swap, not a behaviour change; the deleted file is the reference until it is gone.

- [ ] **Step 4: Run tests**

Run: `just test-file app/kernel/tests/test_llm_openai_chat.py && just test-file app/capabilities/settings/tests/test_profiles.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/kernel/llm/openai_chat.py app/capabilities/settings app/kernel/testing/vendor.py \
  app/kernel/tests/test_llm_openai_chat.py app/capabilities/settings/tests/test_profiles.py pyproject.toml uv.lock
git rm app/kernel/llm/openai_compat.py
git commit -m "feat(settings): provider profiles with per-task assignment over the openai SDK

User-visible: users manage their own provider profiles and assign them per task; a connection test and model discovery run against the configured endpoint"
```

### Task 5: `/settings` route, gear, E2E, docs overwrite

**Files:**
- Create: `app/capabilities/settings/web/routes.tsx`, `app/capabilities/settings/web/SettingsPage.tsx`, `app/capabilities/settings/web/ProvidersPanel.tsx`, `web/components/LanguageSwitcher.tsx` (extracted from `TopBar.tsx`), `app/capabilities/settings/e2e/test_profiles_e2e.py`
- Modify: `app/capabilities/settings/capability.yaml` (`path: /settings`), `web/components/TopBar.tsx` (imports the extracted switcher; gains a gear `Link` labelled `t("shell.settings")`), `i18n/en.json`, `i18n/de.json`, `i18n/fr.json`, `app/kernel/testing/stack.py` (env: `NARRE_SECRET_KEY` test value + `NARRE_KEYRING=off`), Fahrplan §5/§8.1 as-built note, frontend spec settings paragraph
- Generated (via `just generate`, committed): `web/lib/generated/{routes,capabilities}.ts`, `app/generated/capabilities.py`, `docs/user/INDEX.md`

**Interfaces:**
- Consumes: Task 4's endpoints; the knowledge capability's `web/routes.tsx` + `KnowledgePage.tsx` as the structural pattern; `assert_accessible` from `app.kernel.testing.a11y`.
- Produces: the shipped `/settings` page (Sprache: the extracted `LanguageSwitcher`; Provider: list, form incl. key field and tuning fields, default control, per-task assignments over `KNOWN_TASK_KEYS`, test connection, model discovery) — all strings in en/de/fr.

- [ ] **Step 1: Write the failing E2E**

`test_profiles_e2e.py` on the real stack (fake LLM at the boundary; `ChatVendor` for test/discovery): create two fake profiles through the UI; set one default; assign `writing.continuation` to the other; run a continuation in the workbench; assert on the `llm_calls` row (SQL, the `test_continuation_e2e.py` pattern) that `profile_id` and `model` are the alt profile's; test connection and discovery against the vendor (visible result); masked round-trip (create shows the key once, list shows the mask, update with empty key keeps it); deleting the default is refused with the named way out. `assert_accessible` on `/settings` and the workbench. Language switch renders the new surfaces in all three locales.

- [ ] **Step 2: Run to verify failure**

Run: `just test-file app/capabilities/settings/e2e/test_profiles_e2e.py`
Expected: FAIL (no route).

- [ ] **Step 3: Implement page, panel, extraction, gear; `capability.yaml` → `just generate`**

`capability.yaml`: only `path: /` becomes `path: /settings`; `nav: false` stays (the gear is the door). The route follows the knowledge pattern (`createRoute` under `@shell/routes/__root`, lazy page, exported `routes` tuple).

- [ ] **Step 4: Run E2E to verify it passes; run `just check`**

Run: `just test-file app/capabilities/settings/e2e/test_profiles_e2e.py && just check`
Expected: PASS / green.

- [ ] **Step 5: Docs overwrite, then `just verify`**

Fahrplan: §5 gains an as-built paragraph (WP2 split, `/settings` pulled forward from WP5, D1–D8 outcomes); §8.1 notes the route landed in WP2a. Frontend spec: settings paragraph overwritten (route exists, palette still WP5).

Run: `just verify`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(settings): the settings route with provider management, reachable from the top bar

User-visible: a gear in the top bar opens /settings, where language and provider profiles are managed in the user's language"
```

## Carry-forward (WP1 final review)

WP1 closed as #295 (`b2c499c3`). All final-review findings landed as fix commits before the merge (`2f923287` re-embed + chips keyboard, `2a2d564d` merge row locks + novel-scoped entity list). **No open constraints carry into WP2a.**

## Deviations from the design doc

None at plan time. The build session records any here, with the root cause, as they occur.
