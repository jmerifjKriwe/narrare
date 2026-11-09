# Implementation Plan: LLM Usage View

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve the requesting account's `llm_calls` aggregates and render them
as a settings page with a period filter.

**Architecture:** One kernel read endpoint (`app/kernel/llm/`) over the existing
`llm_calls` table, a composite index, and a TanStack Query page in the settings
capability. No new table; no cost estimation.

**Tech Stack:** Python 3.14, FastAPI/SQLAlchemy async, Alembic, PostgreSQL,
Vite/React/TanStack Router/TanStack Query, existing `just generate`.

**Spec:** `docs/superpowers/specs/2026-11-09-llm-usage-view-design.md`

**Dispatch:** implementer `zai-coding-plan/glm-5.3-flash`; reviewer
`opencode-go/deepseek-v4.1-flash`. The reviewer does not edit, stage, commit or
push.

**Task report:** `docs/superpowers/reports/2026-11-09-llm-usage-view-report.md`.
One section per task: what changed, the exact gate command run, its exit status,
and any deviation from this plan. Written while the work happens, never after.

## Global Constraints

- No new standing rule, checker, hook, or required field (CONSTRAINTS §8).
- Capability folders never import another capability; imports point
  `api → capabilities → kernel`.
- Generated files are regenerated with `just generate`, never hand-edited.
- English in code and tests; user-visible text in en/de/fr, in the settings
  capability catalog (rule 5).
- Every query is scoped to the requesting user through `ScopedRepository`
  (rule 4); a second user's rows never appear.
- A user-visible page is done only with a green E2E (rule 2).
- Every task leaves the tree green: a commit that adds a route includes the
  regenerated OpenAPI document and client.

---

## Task 1: The summary function (test first)

**Files:**
- Create: `app/kernel/tests/test_llm_usage.py`
- Create: `app/kernel/llm/usage.py`

**Interfaces:**
- Produces:
  `summarise(session: AsyncSession, *, user_id: UUID, days: int) -> UsageSummary`
  where `UsageSummary` carries `period_days`, `totals`, `by_task`; every row
  carries `task_key`, `calls`, `errors`, `input_tokens: int | None`,
  `output_tokens: int | None`.

- [ ] **Step 1: Write the failing tests**

`app/kernel/tests/test_llm_usage.py`. Follow `test_llm_audit.py` for the module
fixture (`OWNER = LOCAL_USER_ID`, `seed_user(OWNER)`, `empty_tables`, `Session`).
Seed rows directly — do not drive a provider:

```python
@pytest.fixture
async def a_user(empty_tables: None) -> None:
    await seed_user(OWNER)


async def _seed(
    task_key: str,
    status: str,
    *,
    user_id: UUID = OWNER,
    days_ago: int = 0,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> None:
    async with Session() as session:
        session.add(
            LlmCall(
                user_id=user_id,
                task_key=task_key,
                provider_kind="fake",
                model="fake",
                latency_ms=1,
                status=status,
                prompt_text="p",
                response_text="r",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                created_at=datetime.now(UTC) - timedelta(days=days_ago),
            )
        )
        await session.commit()
```

Pin these behaviours, one test each:

1. `days=7` excludes a row seeded 30 days ago and includes one seeded 1 day ago.
2. Two users' rows: only `OWNER`'s rows are counted, in `by_task` and `totals`
   (seed the second user with `seed_user(OTHER)`).
3. `errors` counts only `status == ERROR` (`"error"`), using the constant.
4. Tokens sum per group; a group whose rows are all NULL yields `None`, never
   `0`; a mixed group sums the non-NULL values.
5. `by_task` is ordered `calls DESC, task_key ASC`.
6. `days=0` includes every row regardless of age.
7. Empty table: `by_task == []`, `totals.calls == 0`, tokens `None`.
8. `totals.calls == sum(row.calls for row in by_task)` for a mixed fixture.

- [ ] **Step 2: Run and watch them fail**

Run: `just test-file app/kernel/tests/test_llm_usage.py`
Expected: collection error — `app.kernel.llm.usage` does not exist.

- [ ] **Step 3: Implement `app/kernel/llm/usage.py`**

- `class LlmCallRepository(ScopedRepository[LlmCall]): model = LlmCall`.
- One `select` over `LlmCall.task_key`, `func.count()`,
  `func.count().filter(LlmCall.status == ERROR)`, `func.sum(LlmCall.input_tokens)`,
  `func.sum(LlmCall.output_tokens)`, grouped by `task_key`, ordered
  `count.desc(), LlmCall.task_key.asc()`, narrowed by `repository.owned()`.
- The cutoff is `datetime.now(UTC) - timedelta(days=days)` when `days > 0`, else
  no time predicate.
- Totals are summed from the fetched rows in Python; a token total is `None`
  when every group's is `None`.
- The pydantic models (`UsageTotals`, `UsageTask`, `UsageSummary`) live in the
  same module; the router re-exports `UsageSummary` as its response model.

- [ ] **Step 4: Run the tests**

Run: `just test-file app/kernel/tests/test_llm_usage.py`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add app/kernel/llm/usage.py app/kernel/tests/test_llm_usage.py
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "feat(kernel): aggregate LLM calls per task and period

User-visible: the account's LLM call counts, errors and tokens are readable
per task over a chosen period."
```

---

## Task 2: The endpoint

**Files:**
- Create: `app/kernel/llm/router.py`
- Modify: `app/api/main.py`
- Modify: `app/kernel/tests/test_llm_usage.py`

- [ ] **Step 1: Write the failing API tests**

Append to `test_llm_usage.py`, using the `client` fixture from
`app/conftest.py` (the app is built once; the database is the module's):

1. `GET /api/llm-calls/summary` defaults to `days=30` (`period_days == 30`).
2. `?days=7`, `?days=90`, `?days=0` each answer 200 with that
   `period_days` (0 for all time).
3. `?days=14` and `?days=-1` answer 422.
4. The body matches the spec's shape: `totals` and `by_task` with the four
   numeric fields plus `task_key`.
5. A second user's row is absent from a response fetched as the local user.

- [ ] **Step 2: Run and watch them fail**

Run: `just test-file app/kernel/tests/test_llm_usage.py`
Expected: 404 on `/api/llm-calls/summary` (route missing).

- [ ] **Step 3: Implement**

`app/kernel/llm/router.py`, modelled on `app/kernel/jobs/router.py`:

```python
router = APIRouter(prefix="/api/llm-calls", tags=["llm"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UUID, Depends(current_user_id)]

@router.get("/summary", response_model=UsageSummary)
async def summary(
    session: SessionDep,
    user_id: UserDep,
    days: Annotated[Literal[0, 7, 30, 90], Query()] = 30,
) -> UsageSummary:
    return await summarise(session, user_id=user_id, days=days)
```

`Literal` is the validation; do not add a hand-written check. The handler does
no work beyond the call (kernel-routers-delegate rule). Mount it in
`create_app()` beside `jobs_router`, with a comment naming what it is.

- [ ] **Step 4: Run the tests**

Run: `just test-file app/kernel/tests/test_llm_usage.py`
Expected: all pass.

- [ ] **Step 5: Regenerate the client**

Run: `just generate`
Expected: `web/lib/api/openapi.json` gains `/api/llm-calls/summary`, and
`web/lib/api/schema.d.ts` gains the path and its schemas.

Run: `just test-file app/api/test_openapi_doc.py`
Expected: pass. A commit that adds a route without regenerating these files is
red in `just test`.

- [ ] **Step 6: Commit**

```bash
git add app/kernel/llm/router.py app/api/main.py app/kernel/tests/test_llm_usage.py \
  web/lib/api web/lib/generated
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "feat(kernel): serve the LLM usage summary

User-visible: the account's LLM call counts, errors and tokens are readable
per task over a chosen period."
```

---

## Task 3: The index and its revision

**Files:**
- Modify: `app/kernel/llm/models.py`
- Create: `app/kernel/db/migrations/versions/<rev>_llm_calls_user_created.py`
  (written by Alembic, reviewed by hand)

- [ ] **Step 1: Add the index to the model**

In `LlmCall`, add:

```python
__table_args__ = (
    Index("ix_llm_calls_user_created", "user_id", "created_at"),
)
```

`user_id` already has its own single-column index from `UserOwned`; this one
serves the summary's user + time filter and does not replace it.

- [ ] **Step 2: Draft the revision**

Run: `just db-revision "index llm_calls by user and time"`
Expected: a new file under `app/kernel/db/migrations/versions/` containing
`op.create_index` and its exact reverse in `downgrade`. Read it: no unrelated
diff (an empty-diff revision means the model and the history disagreed — fix
that first, do not hand-write the index).

- [ ] **Step 3: Run the migration gate**

Run: `just test-file app/kernel/db/tests/test_migrations.py`
Expected: all pass — one head, empty replay equals the models, downgrade
reaches the previous head.

- [ ] **Step 4: Commit**

```bash
git add app/kernel/llm/models.py app/kernel/db/migrations/versions
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "perf(db): index llm_calls by user and time

The usage summary always filters on both; the audit table never shrinks."
```

---

## Task 4: Text

**Files:**
- Modify: `app/capabilities/settings/web/i18n/en.json`
- Modify: `app/capabilities/settings/web/i18n/de.json`
- Modify: `app/capabilities/settings/web/i18n/fr.json`

- [ ] **Step 1: Insert the keys from the spec's table (§4.5), sorted**

The generator rejects an unsorted catalog (`scripts/generate_capabilities.py`
raises "keys are not sorted"), so insert each key where it belongs
alphabetically; do not append.

- [ ] **Step 2: Confirm the formal overlay needs no entry**

Read the German strings. `i18n/overlays/formality/de.json` is sparse on purpose:
a key absent there falls through to the base. Add an entry only where the formal
register genuinely changes a sentence; `settings.usage.empty`,
`settings.usage.error` and the cluster description are register-neutral as
written.

- [ ] **Step 3: Regenerate and check**

Run: `just check-generated`
Expected: pass, or a diff limited to the regenerated catalogs — commit that
diff (it is the merged `catalogs.ts`).

- [ ] **Step 4: Commit**

```bash
git add app/capabilities/settings/web/i18n i18n/overlays/formality web/lib/generated
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "feat(settings): name the usage view in three languages"
```

---

## Task 5: The page, E2E first

**Files:**
- Modify: `app/capabilities/settings/e2e/test_settings_e2e.py`
- Create: `app/capabilities/settings/web/UsagePage.tsx`
- Create: `app/capabilities/settings/web/UsagePage.test.tsx`
- Modify: `app/capabilities/settings/web/routes.tsx`
- Modify: `app/capabilities/settings/web/SettingsLayout.tsx`
- Modify: `web/lib/query.ts`

**Interfaces:**
- Consumes: `client` and the generated types from `@shell/lib/api/client`;
  `useTranslation` from `@shell/lib/i18n`.
- Produces: `useUsageQuery(days: UsageDays)` in `web/lib/query.ts` returning
  `UseQueryResult<UsageSummary>`.

- [ ] **Step 1: Write the failing E2E**

Add to `app/capabilities/settings/e2e/test_settings_e2e.py`. Seed through the
database, following `app/capabilities/prompts/e2e/test_prompts_e2e.py`:

```python
async def _seed_calls() -> None:
    async with SessionLocal() as session:   # engine from testsupport.url_for(DATABASE)
        session.add_all([...])              # LlmCall rows, user_id=LOCAL_USER_ID
        await session.commit()
```

Four rows: two `ok` for `writing.continuation` (1 day ago, 20 days ago), one
`error` for `chat.ask` (1 day ago), one `ok` for `knowledge.extract-entities`
(100 days ago). `provider_kind`/`model` are `"fake"`; token columns carry values
on the recent rows and `NULL` on the oldest.

`test_usage_lists_the_accounts_calls_by_task` — one test, both states. The
module shares one database and `pytest-randomly` orders its tests, so two tests
cannot rely on each other's absence; this one walks the phases in order:

1. `page.goto(f"{WEB_URL}/settings/usage")` on the untouched database.
   Title: `expect(page).to_have_title("Nutzung — Narrare")`.
   The empty state ("In diesem Zeitraum wurden keine Aufrufe aufgezeichnet.") is
   visible.
2. `_seed_calls()`, then `page.reload()`.
3. The nav row "Nutzung" carries `aria-current="page"`.
4. The table lists all three task keys; `chat.ask` shows 1 call and 1 error; the
   `NULL` token row renders an em dash, not `0`.
5. The totals row equals the sum of the visible rows.
6. Select "Letzte 7 Tage": the 20-day and 100-day rows disappear, the 1-day rows
   remain; selecting "Gesamt" brings all three back.
7. `assert_accessible(page)`.

Run: `just test-e2e settings`
Expected: red — the page 404s or the title assertion fails, because neither the
route nor the page exists yet.

- [ ] **Step 2: Write the failing component tests**

`UsagePage.test.tsx`, following `ProvidersPanel.test.tsx`'s seam (mock the
client's `GET`, wrap in a fresh `QueryClientProvider`). Pin:

1. The empty answer renders `settings.usage.empty` and a totals row of zeros.
2. A populated answer renders one row per task key and a totals row whose calls
   equal the sum.
3. A rejected request renders `settings.usage.error`.
4. Changing the select from 30 to 7 issues a second request with `days=7` and
   renders the new answer (assert on the query, not only on the DOM).
5. The page sets the document title to `settings.usage` (via `usePageTitle`;
   the hook tolerates a missing provider, so no wrapper is required).

Run: `pnpm --dir web exec vitest run UsagePage`
Expected: cannot resolve `./UsagePage`.

- [ ] **Step 3: Implement the query hook**

`web/lib/query.ts`:

```ts
export type UsageDays = 0 | 7 | 30 | 90;

export function useUsageQuery(days: UsageDays) {
  return useQuery({
    queryKey: ["llm-usage", days],
    queryFn: async () => {
      const { data } = await client.GET("/api/llm-calls/summary", {
        params: { query: { days } },
      });
      return data ?? null;
    },
  });
}
```

The shared client already sets `retry: false`; a down service is a named
failure, not a retry loop. Do not add a second `QueryClient`.

- [ ] **Step 4: Implement the page**

- `const [days, setDays] = useState<UsageDays>(30)`; the select offers 7/30/90/0
  with the labels from the spec.
- `<table>` with `<thead>` (task, calls, errors, input tokens, output tokens),
  `<tbody>` rows ordered as the API returned them, `<tfoot>` totals.
- `null` tokens render as an em dash (`—`), never as `0`.
- `usePageTitle(t("settings.usage"))`.
- Error and empty states use their own keys; loading renders the empty table
  frame, not a spinner (the local service answers in milliseconds).

- [ ] **Step 5: Wire the route and the cluster**

`routes.tsx`: a lazy `UsagePage` and a child route `usage` under
`settingsLayoutRoute`, appended to `routes`.
`SettingsLayout.tsx`: a fourth `CLUSTERS` entry
(`id: "usage"`, `path: "/settings/usage"`,
`titleKey: "settings.clusterUsage"`,
`descriptionKey: "settings.clusterUsage.description"`).

Do not export `settingsRoutes` from the settings capability: that export is the
registry for *other* capabilities' pages; the settings' own pages are
`CLUSTERS`.

- [ ] **Step 6: Make both suites green**

Run: `pnpm --dir web exec vitest run UsagePage`
Expected: pass.

Run: `just test-e2e settings`
Expected: pass, including axe. If the period filter does not change the numbers,
the query parameter is not reaching the backend — fix that, not the assertion.

- [ ] **Step 7: Run the full frontend gates**

Run: `just test-frontend` and `just typecheck`
Expected: pass. The `settingsPages` generated table is untouched.

- [ ] **Step 8: Commit**

```bash
git add app/capabilities/settings/e2e app/capabilities/settings/web web/lib/query.ts
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "feat(settings): show LLM usage by task and period

User-visible: Settings → Usage lists the account's LLM calls per task, with
errors and tokens, for the last 7, 30 or 90 days or all time."
```

---

## Task 6: Verify and report

- [ ] `just check`
- [ ] `just check-generated` (needs network for `pnpm dlx`; CI runs it anyway)
- [ ] `just test`
- [ ] `just test-frontend`
- [ ] `just test-e2e settings`
- [ ] `just build`
- [ ] Write the report's final section: every gate above with its exit status,
  the seeded numbers the E2E asserted, and any deviation from this plan.

## Review Focus

- The endpoint returns `null`, not `0`, for a token total whose rows are all
  NULL.
- The second user's rows are absent from both `by_task` and `totals` (the test
  seeds them; the query must be structurally scoped).
- `days` is a `Literal`; `?days=14` is 422, not silently clamped.
- The migration's `downgrade` drops exactly the index it added, and the head
  replay equals the models.
- The page uses `CLUSTERS`, not `settingsRoutes`, and the hub shows the row.
- The E2E's period filter proves the query parameter reaches the backend (the
  numbers change), not merely that a select rendered.
- No test asserts a task key that only exists in the fixture and not in the
  product's real task list without saying so in its docstring.
- The E2E's empty-state phase runs before it seeds; a test that seeds first
  proves nothing about the empty state.
