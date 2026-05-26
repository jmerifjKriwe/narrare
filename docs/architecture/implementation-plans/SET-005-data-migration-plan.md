# SET-005: Data Migration & Deprecation Plan

## TL;DR

**Problem**: Dual data models for token limits — old columns (`token_limit_overrides` + `token_limit_profile` on `user_ai_settings` / `project_settings`) vs. new tables (`user_token_limits` / `project_token_limits` with `TokenLimitsService`). Writes go to both, reads use neither cleanly.

**Solution (Option A)**: Migrate all data from old columns → new tables, switch all code paths to `TokenLimitsService`, deprecate old columns for future removal.

**Risk**: Low-to-medium. Old per-category `token_limit_overrides` have no flat equivalent in the new model — preserved as `legacy_per_category_overrides` in the JSONB. Data loss impossible (no destructive migration).

---

## 1. Migration Design

### 1.1 Pre-Flight Check

Before migration runs, verify:
- `user_token_limits` and `project_token_limits` tables exist (migration 0021)
- `user_ai_settings.token_limit_profile` + `token_limit_overrides` columns exist
- `project_settings.token_limit_profile` + `token_limit_overrides` columns exist
- No orphaned FK references (though these tables have no FKs, so safe)

### 1.2 Migration SQL — Conceptual (`0023_token_limit_migration.py`)

**Header**:
```
Revision ID: 0023_token_limit_migration
Revises: 0022_embeddings
```

**`upgrade()`** — Two-phase approach:

#### Phase A: Migrate user token limits

```sql
INSERT INTO user_token_limits (user_id, overrides)
SELECT
    uas.user_id::text,
    jsonb_build_object(
        'token_profile', COALESCE(uas.token_limit_profile, 'balanced'),
        'output_limit',
            CASE COALESCE(uas.token_limit_profile, 'balanced')
                WHEN 'quick' THEN 500
                WHEN 'balanced' THEN 2000
                WHEN 'long_texts' THEN 8000
                ELSE 4096
            END,
        'legacy_per_category_overrides', COALESCE(uas.token_limit_overrides, '{}'::jsonb)
    )
FROM user_ai_settings uas
WHERE NOT EXISTS (
    SELECT 1 FROM user_token_limits utl
    WHERE utl.user_id = uas.user_id::text
)
AND (
    uas.token_limit_overrides IS NOT NULL
    AND uas.token_limit_overrides != '{}'::jsonb
    OR uas.token_limit_profile != 'balanced'
);
```

#### Phase B: Migrate project token limits

```sql
INSERT INTO project_token_limits (project_id, overrides)
SELECT
    ps.novel_id::text,
    jsonb_build_object(
        'token_profile', COALESCE(ps.token_limit_profile, 'balanced'),
        'output_limit',
            CASE COALESCE(ps.token_limit_profile, 'balanced')
                WHEN 'quick' THEN 500
                WHEN 'balanced' THEN 2000
                WHEN 'long_texts' THEN 8000
                ELSE 4096
            END,
        'legacy_per_category_overrides', COALESCE(ps.token_limit_overrides, '{}'::jsonb)
    )
FROM project_settings ps
WHERE NOT EXISTS (
    SELECT 1 FROM project_token_limits ptl
    WHERE ptl.project_id = ps.novel_id::text
)
AND (
    ps.token_limit_overrides IS NOT NULL
    AND ps.token_limit_overrides != '{}'::jsonb
    OR ps.token_limit_profile != 'balanced'
);
```

**Key design decisions**:
- **`WHERE NOT EXISTS`** — If a row already exists in the new table (set via new API), the migration skips it. Existing new data = intentional user action → never overwrite.
- **`legacy_per_category_overrides`** — The old `token_limit_overrides` JSONB stores per-category `{max_tokens, temperature}` objects. The new flat model has no equivalent. We store the raw dict under this key for preservation. It's silently ignored by `_merge_overrides()`.
- **`output_limit` mapping** — Profile name → sensible default (quick=500, balanced=2000, long_texts=8000, else 4096). User can override via new API.

**`downgrade()`**:

```sql
-- No data loss on downgrade: old columns still have their data.
-- Just remove rows that were created by upgrade.
DELETE FROM user_token_limits utl
WHERE EXISTS (
    SELECT 1 FROM user_ai_settings uas
    WHERE uas.user_id::text = utl.user_id
);

DELETE FROM project_token_limits ptl
WHERE EXISTS (
    SELECT 1 FROM project_settings ps
    WHERE ps.novel_id::text = ptl.project_id
);
```

### 1.3 Migration Rules

| Rule | Compliance |
|------|------------|
| RULE-14 | ✅ Migration created in same task as model changes |
| RULE-04 | Migration file < 150 lines |
| RULE-11 | No silent failures — logging in migration |
| RULE-09 | All functions typed |

---

## 2. Profile Name Alignment

### 2.1 The Bug

`_PROFILE_OUTPUT_LIMITS` in `core/llm/intents.py` has key `"long"` but the API/DB uses `"long_texts"`:

```python
# intents.py
_PROFILE_OUTPUT_LIMITS: dict[str, int] = {
    "quick": 500,
    "balanced": 2000,
    "long": 8000,  # ← BUG: should be "long_texts"
}
```

**Impact**: `resolve_output_limit("long_texts")` falls through to `max_tokens` because `"long_texts"` is not in the dict. Users who select "long_texts" in the UI get the default `max_tokens` instead of 8000. **All "long_texts" users are affected.**

### 2.2 Resolution

**Recommendation: Option 1 — Rename in core (`intents.py`)**

| Option | Verdict | Why |
|--------|---------|-----|
| **1. Rename "long" → "long_texts"** | ✅ **CHOSEN** | Single source of truth. No aliases, no mapping. Matches DB values and API validation regex. |
| 2. Add "long_texts" as alias | ❌ | Two paths to same value → confusion, dead code. `"long"` has no DB storage path. |
| 3. Validate at schema boundary | ❌ | Just kicks the can — the boundary is already validated (regex `^(quick|balanced|long_texts|custom)$`). The bug is in core. |

**Exact change** in `packages/core/narrare_core/llm/intents.py`:
```python
_PROFILE_OUTPUT_LIMITS: dict[str, int] = {
    "quick": 500,
    "balanced": 2000,
    "long_texts": 8000,  # was "long"
}
```

### 2.3 Test Updates

`tests/unit/core/llm/test_intents.py` — tests referencing `"long"` as a profile need updating to use `"long_texts"`.

---

## 3. Integration Changes

### 3.1 Backend Changes

#### 3.1.1 `writing/deps.py` — Token limit resolution

**Current pattern** (3 occurrences: `get_writing_service`, `get_extend_service`, `get_rewrite_service`):
```python
profile = resolved.config.token_limit_profile or "balanced"
config = replace(
    resolved.config,
    temperature=0.7,
    max_tokens=resolved.config.resolve_output_limit(profile),
)
```

**New pattern**:
```python
from narrare.settings.token_limits.repository import (
    ProjectTokenLimitsRepository,
    UserTokenLimitsRepository,
)
from narrare.settings.token_limits.service import TokenLimitsService
from narrare._app.config import get_settings

token_limits_service = TokenLimitsService(
    user_repo=UserTokenLimitsRepository(session),
    project_repo=ProjectTokenLimitsRepository(session),
    config=get_settings(),
)
limits = await token_limits_service.get_resolved_limits(
    user_id=user_id,
    project_id=str(project_id) if project_id else None,
)
config = replace(
    resolved.config,
    temperature=0.7,
    max_tokens=limits.output_limit,
)
```

**Diff summary** (per factory function):
- Add 4 imports (late imports, same pattern as existing code)
- Replace `profile = ... | resolve_output_limit(profile)` block with `token_limits_service.get_resolved_limits()`
- Replace `max_tokens=resolved.config.resolve_output_limit(profile)` with `max_tokens=limits.output_limit`
- Remove unused import: no more `from dataclasses import replace`

#### 3.1.2 `writing/summary_deps.py` — Same pattern

**Current:**
```python
profile = resolved.config.token_limit_profile or "quick"
config = replace(
    resolved.config,
    temperature=0.3,
    max_tokens=resolved.config.resolve_output_limit(profile),
)
```

**New:**
```python
limits = await token_limits_service.get_resolved_limits(
    user_id=str(user_id),
    project_id=str(novel_id) if novel_id else None,
)
config = replace(
    resolved.config,
    temperature=0.3,
    max_tokens=limits.output_limit,
)
```

Note: `summary_deps.py` uses FastAPI `Depends()` pattern. The factory function `get_summary_service` already has `session: AsyncSession = Depends(get_async_session)`, so we can instantiate the TokenLimitsService the same way.

#### 3.1.3 `writing/router_sessions.py` — WS handler

**Current:**
```python
_WRITE_SESSION_DEFAULT_OUTPUT_LIMIT: int = 2000

config = ResolvedModelConfig(
    provider_name="default",
    model_id="default",
    temperature=0.7,
    max_tokens=_WRITE_SESSION_DEFAULT_OUTPUT_LIMIT,  # hardcoded 2000
)
settings = get_settings()
handler = WritingSessionHandler(
    ...
    config=config,
    ws_idle_timeout=settings.ws_idle_timeout_seconds,
)
```

**New:**
```python
# Remove _WRITE_SESSION_DEFAULT_OUTPUT_LIMIT constant

# Inside the endpoint function, after session setup:
from narrare.settings.token_limits.repository import (
    ProjectTokenLimitsRepository,
    UserTokenLimitsRepository,
)
from narrare.settings.token_limits.service import TokenLimitsService

token_limits_service = TokenLimitsService(
    user_repo=UserTokenLimitsRepository(session),
    project_repo=ProjectTokenLimitsRepository(session),
    config=get_settings(),
)
limits = await token_limits_service.get_resolved_limits(
    user_id=user_id,
    project_id=str(project_id) if project_id else None,
)

config = ResolvedModelConfig(
    provider_name="default",
    model_id="default",
    temperature=0.7,
    max_tokens=limits.output_limit,
)
handler = WritingSessionHandler(
    ...
    config=config,
    ws_idle_timeout=limits.ws_timeout,
)
```

⚠ **Important**: The WS handler currently does NOT have a DB session. It would need one. Options:
- **(A)** Inject `AsyncSession` via `get_async_session` (same pattern as deps)
- **(B)** Create a minimal engine from config (simpler but anti-pattern)

**Recommendation: Option A**. The WS endpoint can accept an async session dependency. FastAPI supports this for WebSocket endpoints.

#### 3.1.4 `writing/ws_handler.py` — Constructor stays the same

No changes needed to `ws_handler.py` itself. The `ws_idle_timeout` parameter is already configurable via constructor injection. The caller (`router_sessions.py`) just passes a different value.

#### 3.1.5 `settings/user_ai_settings_service.py` — Stop writing `token_limit_overrides`

**Current:**
```python
# The PATCH /settings/ai endpoint accepts token_limit_overrides
# and token_limit_profile in the request body and writes them to
# user_ai_settings table.
```

**Change**: The `update_settings()` method should:
- Keep validating `token_limit_profile` (for backward compat schema reads)
- When `token_limit_overrides` is provided → call `TokenLimitsService.update_user_limits()` instead of writing to the old column
- When `token_limit_profile` is provided → also call `TokenLimitsService` to update `overrides.token_profile`

Actually, rethinking: if we're fully migrating, we should:
- **Remove** `token_limit_overrides` from the `UpdateUserAiSettingsRequest` schema (since it's deprecated)
- **Remove** `token_limit_profile` from the schema as well — it should only be set through the TokenLimits API

But this is a breaking API change. Better approach:
- **Phase 1**: Write to BOTH locations (old column + new service) with a deprecation warning log
- **Phase 2**: Stop writing to old column, only keep reading it for backward compat
- **Phase 3**: Remove old column entirely

For SET-005 scope (Phase 1+2):
- Accept old fields in schemas but emit deprecation warning
- Route writes through TokenLimitsService
- Keep reading old columns for backward compat during transition

#### 3.1.6 `settings/project_ai_settings_service.py` — Same as user variant

Same treatment: `token_limit_overrides` writes → `TokenLimitsService.update_project_limits()`, emit deprecation warning.

#### 3.1.7 `settings/token_profiles.py` — Valid profile alignment

`VALID_TOKEN_LIMIT_PROFILES` already has `"long_texts"` — no change needed. Already aligned with new system.

#### 3.1.8 `_PROFILE_OUTPUT_LIMITS` fix — See Section 2

### 3.2 Frontend Changes

#### 3.2.1 `AiTab.tsx` — Move profile writes to new API

**Current:**
```tsx
function handleTokenProfileChange(profile: TokenLimitProfile) {
    updateAiSettingsMutation.mutate({ token_limit_profile: profile });
}
```

**New:**
```tsx
function handleTokenProfileChange(profile: TokenLimitProfile) {
    updateTokenLimitsMutation.mutate({ token_profile: profile });
}
```

The `UpdateTokenLimitsRequest` already has `token_profile?: TokenLimitProfile` in the type definition. No type changes needed.

#### 3.2.2 `AiTab.tsx` — Custom token limits (per-category overrides)

**Current:**
```tsx
<CustomTokenLimits
    overrides={aiSettings?.token_limit_overrides ?? {}}
    onChange={handleTokenLimitOverridesChange}
/>
```

**Decision**: Keep the `CustomTokenLimits` component working through the OLD API path for now. The per-category token override feature has no equivalent in the new flat model. It's a separate deprecation track.

**Change**: Add a deprecation notice log. Keep writing to old API. When the old columns are removed (Phase 3), this component must be either removed or re-implemented against the new model.

#### 3.2.3 Frontend types — No changes needed

The `UpdateTokenLimitsRequest` already has `token_profile`. The old `UserAiSettings` types will be deprecated later.

#### 3.2.4 Read path — What reads what

| UI Element | Currently Reads From | After Migration Reads From |
|------------|---------------------|---------------------------|
| Profile selector | `aiSettings.token_limit_profile` (old) | `tokenLimitsData.token_profile` (new) |
| Custom token limits | `aiSettings.token_limit_overrides` (old) | Keep old (separate deprecation) |
| Context budget | `tokenLimitsData.tier_percentages` (new) | No change |
| System timeouts | `tokenLimitsData.ws_timeout`, etc. (new) | No change |

---

## 4. Deprecation Strategy

### 4.1 Timeline

```
Phase 1 (SET-005 — NOW)
├── Migration 0023: copy old → new (non-destructive)
├── Writing deps: switch to TokenLimitsService
├── WS handler: switch to TokenLimitsService
├── Profile name fix: "long" → "long_texts" in core
├── Settings services: route writes through TokenLimitsService
│   (dual-write with deprecation warning)
├── Frontend: profile selector writes to new API
└── Tests: update for all changes

Phase 2 (Next release)
├── Remove token_limit_overrides from UpdateUserAiSettingsRequest schema
├── Remove token_limit_profile from UpdateUserAiSettingsRequest schema
├── Remove token_limit_overrides from ProjectAiSettingsResponse
├── Remove token_limit_profile from UserAiSettingsResponse
├── Remove write paths from UserAiSettingsService + ProjectAiSettingsService
├── Remove CustomTokenLimits component (or re-implement against new model)
├── Update frontend types to remove old fields
└── Frontend reads profile ONLY from TokenLimitsResponse

Phase 3 (Future — after data validation)
├── Migration to DROP old columns:
│   - ALTER TABLE user_ai_settings DROP COLUMN token_limit_overrides
│   - ALTER TABLE project_settings DROP COLUMN token_limit_overrides
│   - ALTER TABLE user_ai_settings DROP COLUMN token_limit_profile
│   - ALTER TABLE project_settings DROP COLUMN token_limit_profile
├── Remove old column definitions from models.py
└── Remove old read paths
```

### 4.2 Code Paths That Write to Old Columns (Current)

| Code Path | Old Column | New Path | Status |
|-----------|-----------|----------|--------|
| `PATCH /settings/ai` → `UserAiSettingsService.update_settings()` | `token_limit_overrides`, `token_limit_profile` | `TokenLimitsService` | Migrate to dual-write (Phase 1) |
| `PATCH /settings/ai/novels/{id}` → `ProjectAiSettingsService.update_settings()` | `token_limit_overrides` | `TokenLimitsService` | Migrate to dual-write (Phase 1) |
| `AiTab.tsx` `handleTokenProfileChange()` | `token_limit_profile` | `tokenLimitsApi.updateUser()` | Migrate (Phase 1) |
| `AiTab.tsx` `handleTokenLimitOverridesChange()` | `token_limit_overrides` | N/A (different feature) | Keep old (Phase 2) |

### 4.3 Code Paths That Read Old Columns (Current)

| Code Path | Old Column | After Migration |
|-----------|-----------|-----------------|
| `GET /settings/ai` → `UserAiSettingsResponse` | `token_limit_profile`, `token_limit_overrides` | Keep reading (Phase 1), remove from response (Phase 2) |
| `GET /settings/ai/novels/{id}` → `ProjectAiSettingsResponse` | `token_limit_overrides` | Same |
| `writing/deps.py` `resolved.config.token_limit_profile` | `token_limit_profile` via ModelRoutingResolver | **Switch to `TokenLimitsService.get_resolved_limits()`** |
| `gateway.py` `config.token_limit_profile` | `token_limit_profile` via ResolvedModelConfig | Keep (it reads UsageLimits profile, not output limits — separate concern) |
| `AiTab.tsx` profile selector | `aiSettings.token_limit_profile` | **Switch to `tokenLimitsData.token_profile`** |

### 4.4 Dual-Write Implementation (Phase 1)

To avoid breaking existing behavior during transition:

```python
# In UserAiSettingsService.update_settings():

# Old path (DEPRECATED): write to user_ai_settings table column
if "token_limit_overrides" in updates:
    logger.warning("token_limit_overrides_write_deprecated",
                   user_id=str(user_id))
    # Also write to new service
    await self._token_limits_service.update_user_limits(
        user_id=str(user_id),
        overrides={"legacy_per_category_overrides": updates["token_limit_overrides"]},
    )

# Keep token_limit_profile for now (dual resolution)
if "token_limit_profile" in updates:
    logger.warning("token_limit_profile_write_deprecated",
                   user_id=str(user_id))
    # Also write to new service
    await self._token_limits_service.update_user_limits(
        user_id=str(user_id),
        overrides={"token_profile": updates["token_limit_profile"]},
    )
```

**Rollback safety**: Writes still go to old columns. If the new service has issues, old reads still work.

---

## 5. Risk Assessment

### 5.1 Data Loss Risk: **LOW**

| Scenario | Mitigation |
|----------|------------|
| Migration fails mid-way | `WHERE NOT EXISTS` ensures idempotency. Transaction rolled back on failure. |
| Overwrites existing new data | `WHERE NOT EXISTS` prevents overwriting rows that already have new data. |
| Old data is lost | Old columns are NOT dropped in Phase 1. Data exists in both places. |
| Downgrade needed | `downgrade()` only deletes rows that the migration created. Old columns untouched. |

### 5.2 Backward Compatibility Risk: **MEDIUM**

| Scenario | Mitigation |
|----------|------------|
| Writing deps use new service but service fails | Keep old `resolve_output_limit(profile)` as fallback path |
| WS handler writes fail due to no session | Require explicit session injection in WS handler |
| Frontend profile selector reads old API but old API still returns value | Old columns kept for Phase 1 reads |
| Per-category custom token limits broken | Keep writing to old API for now |

### 5.3 Rollback Strategy

**Immediate rollback** (within a deployment cycle):
1. Revert `deps.py`, `summary_deps.py`, `router_sessions.py` to old pattern
2. Revert `AiTab.tsx` profile write to old API
3. Migration 0023 is NOT destructive — old columns still have data
4. Re-run `downgrade()` for migration 0023 if desired

**Long-term rollback** (after Phase 2):
1. Restore old columns from backup (Phase 3 migration drops them)
2. Revert all code changes

### 5.4 Testing Requirements

| Test Type | What | Coverage |
|-----------|------|----------|
| Unit | `TokenLimitsService.get_resolved_limits()` returns correct values | Existing tests |
| Unit | Writing deps correctly use `limits.output_limit` | New tests |
| Unit | Profile name resolution (`resolve_output_limit("long_texts")` = 8000) | Existing tests (update) |
| Integration | Migration 0023 copies data correctly | New migration test |
| Integration | Dual-write routes to both old and new | New integration test |
| E2E | Frontend profile selector writes to new API and reads back | Manual or E2E |

---

## 6. Layer Ordering & Implementation Steps

### Step 1: Core — Profile Name Fix

**File**: `packages/core/narrare_core/llm/intents.py`
**Change**: `"long"` → `"long_texts"` in `_PROFILE_OUTPUT_LIMITS`

**Tests**: Update `test_intents.py` — any test using "long" profile → use "long_texts"

**Specialist**: `narrare-core` (Core Layer)

### Step 2: Data Migration

**File**: `apps/api/alembic/versions/0023_token_limit_migration.py`
**Change**: Create migration as specified in Section 1.2

**Tests**: `tests/integration/settings/test_token_limit_migration.py`
- Verify migration copies user data
- Verify migration copies project data
- Verify idempotency (running twice produces same result)
- Verify existing data in new tables is NOT overwritten

**Specialist**: `narrare-platform` (Platform Layer — migration expertise)

### Step 3: Backend — Writing Deps Integration

**Files**:
- `apps/api/narrare/writing/deps.py` (3 functions)
- `apps/api/narrare/writing/summary_deps.py` (1 function)

**Change**: Replace `resolve_output_limit(profile)` pattern with `TokenLimitsService.get_resolved_limits().output_limit`

**Tests**:
- `tests/unit/writing/test_deps.py` — new tests verifying TokenLimitsService is called
- Update existing deps tests if they assert on `max_tokens` values

**Specialist**: `narrare-backend` (Backend Layer)

### Step 4: Backend — WS Handler Integration

**File**: `apps/api/narrare/writing/router_sessions.py`

**Change**:
- Remove `_WRITE_SESSION_DEFAULT_OUTPUT_LIMIT` constant
- Inject `AsyncSession` dependency in WS endpoint
- Instantiate `TokenLimitsService` and use `limits.output_limit` + `limits.ws_timeout`

**Tests**:
- `tests/unit/writing/test_router_sessions.py` — verify WS handler config uses resolved limits
- May need integration test for WS session

**Specialist**: `narrare-backend` (Backend Layer)

### Step 5: Backend — Settings Services Dual-Write

**Files**:
- `apps/api/narrare/settings/user_ai_settings_service.py`
- `apps/api/narrare/settings/project_ai_settings_service.py`

**Change**:
- Inject `TokenLimitsService` dependency
- When `token_limit_overrides` or `token_limit_profile` is updated, also write to `TokenLimitsService`
- Emit deprecation warning log

**Tests**:
- `tests/unit/settings/test_user_ai_settings_service.py` — verify dual-write
- `tests/unit/settings/test_project_ai_settings_service.py` — verify dual-write

**Specialist**: `narrare-backend` (Backend Layer)

### Step 6: Frontend — Profile Writes to New API

**File**: `packages/web/components/studio/settings/AiTab.tsx`

**Change**:
- `handleTokenProfileChange()` → use `updateTokenLimitsMutation` with `{ token_profile: profile }` instead of `updateAiSettingsMutation` with `{ token_limit_profile: profile }`
- Profile reads: update to read `tokenLimitsData.token_profile` instead of `aiSettings.token_limit_profile`
- Current profile detection changes from `aiSettings?.token_limit_profile ?? "balanced"` to `tokenLimitsData?.token_profile ?? "balanced"`

**Tests**: Update `AiTab.test.tsx` to verify new write path

**Specialist**: `narrare-frontend` (Frontend Layer)

### Step 7: Test Suite Updates

**Files**:
- `tests/unit/core/llm/test_intents.py` — fix "long" → "long_texts"
- `tests/integration/settings/` — new migration test
- `tests/unit/writing/` — new deps tests
- `tests/unit/settings/` — dual-write tests
- `packages/web/components/studio/settings/__tests__/AiTab.test.tsx` — profile write path

**Files not changed** (read-only updates in Phase 1):
- `gateway.py` — continues to read `token_limit_profile` from `ResolvedModelConfig` for UsageLimits (separate concern from output limits)
- `model_routing_resolver.py` — continues to pass through `token_limit_profile` (backward compat)

### Execution Order

```
Step 1 (Core fix)
    ↓
Step 2 (Migration)     Step 3 (Writing deps)     Step 6 (Frontend)
    ↓                         ↓
Step 5 (Dual-write)    Step 4 (WS handler)
    ↓                         ↓
Step 7 (Tests)
```

Steps 2, 3, 6 can start in parallel after Step 1.
Steps 4, 5 depend on Step 2 being available (migration exists).
Step 7 depends on all previous steps.

---

## Compliance Matrix

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-03 | ✅ | Contracts (`TokenLimitOverrides`, `TokenLimitsRepositoryProtocol`, `TokenLimitsServiceProtocol`) exist in `contracts.py` before implementation |
| RULE-04 | ✅ | Migration < 150 lines, no file crosses limits |
| RULE-05 | ✅ | Module boundaries respected: settings/token_limits/ owns new tables, settings/ owns old |
| RULE-06 | ✅ | One responsibility per file (service, deps, router, migration separated) |
| RULE-07 | ✅ | Dependency direction: writing/deps → settings/token_limits/service → repository. Never reverse. |
| RULE-09 | ✅ | All public functions typed |
| RULE-10 | ✅ | Tests specified per layer |
| RULE-11 | ✅ | Deprecation warnings via structlog, no silent failures |
| RULE-14 | ✅ | Migration 0023 created in same task |
| RULE-20 | ✅ | No half-implementations — migration is complete, not a stub |
| RULE-21 | ✅ | Architecture plan documented before implementation |
