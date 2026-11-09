# Spec: LLM Usage View

**Date:** 2026-11-09
**Status:** Proposed
**Author:** Coordinator

---

## 1. Problem

Every LLM call is recorded in `llm_calls` (WP0-A): task key, model, status,
input/output tokens, latency, novel id, timestamp. The table exists, the writer
exists (`app/kernel/llm/audit.py`), and `cost_usd` stays NULL until a catalog
prices it. What does not exist is a way for the user to see the account's own
usage: how many calls ran, for which task, how many failed, how many tokens were
spent.

The data is already scoped per user (`LlmCall` is `UserOwned`), so the view is a
read, not a new record.

## 2. Goals

- A read-only endpoint `GET /api/llm-calls/summary` returning aggregate usage
  for the requesting user: call count, error count, input/output tokens, grouped
  by task key.
- A date-range filter with exactly four choices: last 7 days, last 30 days, last
  90 days, all time.
- A settings page at `/settings/usage` that renders the aggregates as a table
  with a totals row, reachable from the settings hub and the settings nav.
- No new table, no retention mechanism, no cost estimation.

## 3. Non-Goals

- No per-call detail view, no prompt/response text, no export.
- No cost in any currency: `cost_usd` is NULL by design until a model catalog
  prices it; the response does not invent a number.
- No charts, no sparklines, no comparison across periods.
- No pagination. The grouping key is `task_key`, whose distinct values are the
  capability's fixed task list (fewer than twenty today), not user data.
- No change to `llm_calls` beyond one index.

## 4. Design

### 4.1 Endpoint contract

```
GET /api/llm-calls/summary?days=30
```

`days` is one of `0`, `7`, `30`, `90`, default `30`; `0` means all time. Any
other value is a `422` (a `Literal` query parameter, not a hand-written check).

```json
{
  "period_days": 30,
  "totals": {
    "calls": 42,
    "errors": 3,
    "input_tokens": 120000,
    "output_tokens": 80000
  },
  "by_task": [
    {
      "task_key": "writing.continuation",
      "calls": 20,
      "errors": 1,
      "input_tokens": 60000,
      "output_tokens": 40000
    },
    {
      "task_key": "chat.ask",
      "calls": 15,
      "errors": 2,
      "input_tokens": 45000,
      "output_tokens": 30000
    }
  ]
}
```

Semantics, stated once so the implementation cannot invent them:

- **Scope.** Only rows whose `user_id` is the requesting user. Another user's
  rows never appear in `by_task` or in `totals`.
- **Period.** `created_at >= now() - days`, computed as an aware UTC cutoff in
  Python (`datetime.now(UTC) - timedelta(days=days)`); no SQL interval bind.
  `days=0` adds no lower bound.
- **Errors.** `count(*) FILTER (WHERE status = 'error')`, using the existing
  `ERROR` constant.
- **Tokens.** `sum(input_tokens)` / `sum(output_tokens)`. Both columns are
  nullable; a group whose rows all carry NULL yields `null`, never `0`. An
  integer sum is returned otherwise.
- **Ordering.** `calls DESC, task_key ASC` — the busiest task first, ties in a
  stable order, so a refresh cannot reorder the table.
- **Empty period.** `by_task: []`, `totals` all `0` (tokens `null`).
- **Totals.** Summed from the grouped rows in Python; one query, no second
  round trip, and the invariant `sum(by_task.calls) == totals.calls` holds by
  construction.

### 4.2 Query and scoping

`app/kernel/llm/usage.py` holds one function computing the summary from a
session and a user id, using a `ScopedRepository[LlmCall]` subclass so rule 4 is
structural rather than remembered:

```python
class LlmCallRepository(ScopedRepository[LlmCall]):
    model = LlmCall
```

`app/kernel/llm/router.py` is the HTTP surface, mounted in `create_app()` beside
the jobs router, following `app/kernel/jobs/router.py` (prefix `/api/jobs`) as
the precedent for kernel machinery that every capability would otherwise
duplicate. The router depends on `get_session` and `current_user_id` and does no
logic beyond calling `usage.summarise`.

### 4.3 Index

`llm_calls` carries only `ix_llm_calls_user_id` today. The summary filters on
`user_id` **and** `created_at`, and the table grows monotonically (an audit,
never deleted). Add:

```python
Index("ix_llm_calls_user_created", "user_id", "created_at")
```

as a migration revision (`just db-revision "index llm_calls by user and time"`).
Alembic is the repo's migration tool (ADR-103); the gate in
`app/kernel/db/tests/test_migrations.py` compares an empty database replayed to
head against the models, so a model index without its revision is a red test,
not a style question.

### 4.4 Frontend

- Route `/settings/usage` in `app/capabilities/settings/web/routes.tsx`.
- A fourth entry in `CLUSTERS` (`app/capabilities/settings/web/SettingsLayout.tsx`):
  the settings area's own pages live there, and the hub (`SettingsPage.tsx`
  renders `[...CLUSTERS, ...settingsPages]`) and the nav get the row for free.
  `settingsRoutes` is the registry for *other* capabilities, not for settings
  itself.
- `UsagePage.tsx`: a TanStack Query hook over the generated client
  (`client.GET("/api/llm-calls/summary", { params: { query: { days } } })`),
  query key `["llm-usage", days]`, `retry: false` (the shared client's default).
  The range selector writes `days` into the key; a change refetches.
- Table columns: task, calls, errors, input tokens, output tokens; a totals row
  at the bottom, marked as such for assistive technology (`<tfoot>`).
- Three states, each with its own text: loading (the table stays empty, no
  spinner copy), error (the page names the failure), empty (no calls in this
  period).
- `usePageTitle(t("settings.usage"))`, exactly as `LanguagePage` does.

### 4.5 Text

All keys live in the settings capability catalog
(`app/capabilities/settings/web/i18n/{en,de,fr}.json`), sorted — rule 5.

| Key | en | de | fr |
|---|---|---|---|
| `settings.clusterUsage` | Usage | Nutzung | Utilisation |
| `settings.clusterUsage.description` | The LLM calls made by this account. | Die LLM-Aufrufe dieses Kontos. | Les appels LLM de ce compte. |
| `settings.usage` | Usage | Nutzung | Utilisation |
| `settings.usage.period` | Period | Zeitraum | Période |
| `settings.usage.last7` | Last 7 days | Letzte 7 Tage | 7 derniers jours |
| `settings.usage.last30` | Last 30 days | Letzte 30 Tage | 30 derniers jours |
| `settings.usage.last90` | Last 90 days | Letzte 90 Tage | 90 derniers jours |
| `settings.usage.allTime` | All time | Gesamt | Depuis le début |
| `settings.usage.task` | Task | Aufgabe | Tâche |
| `settings.usage.calls` | Calls | Aufrufe | Appels |
| `settings.usage.errors` | Errors | Fehler | Erreurs |
| `settings.usage.inputTokens` | Input tokens | Eingabe-Tokens | Tokens d'entrée |
| `settings.usage.outputTokens` | Output tokens | Ausgabe-Tokens | Tokens de sortie |
| `settings.usage.empty` | No calls in this period. | In diesem Zeitraum wurden keine Aufrufe aufgezeichnet. | Aucun appel sur cette période. |
| `settings.usage.error` | The usage summary could not be loaded. | Die Nutzungsübersicht konnte nicht geladen werden. | Le résumé d'utilisation n'a pas pu être chargé. |

The German formal overlay (`i18n/overlays/formality/de.json`) needs no entry:
every string above reads in the same register formally and informally ("dieses
Kontos", not "deines Kontos"). The implementer confirms this by reading the
strings, not by assuming it.

## 5. Constraints

- **Rule 2:** the page is user-visible, so the settings E2E grows a case. A unit
  test is not the gate.
- **Rule 4:** every query is scoped by the repository base; the test seeds a
  second user's row and asserts it never appears.
- **Rule 5:** keys in the capability catalog, sorted, all three locales, parity
  enforced by `just generate`.
- **§8:** no new standing rule, checker, hook or required field. Extending the
  watched paths of the existing `check-generated` gate is not a new gate.
- Generated files (`openapi.json`, `schema.d.ts`, `catalogs.ts`,
  `settingsPages.ts` if touched) are regenerated with `just generate` and
  committed.

## 6. Risks

- **Audit growth.** The index is the answer; the query never reads
  `prompt_text`/`response_text`, so TOASTed prose is not part of the scan.
- **Task keys are free text.** A capability can write a new `task_key` at any
  time; the table grows a row without a migration. Accepted — that is the
  intended shape.
- **Truncated calls.** `record_call` caps prompt/response text; token counts are
  what the provider reported and are unaffected. The view does not need to
  mention truncation.
- **Octets vs. tokens.** Input and output are different units of cost; the table
  keeps them apart rather than summing them.
- **Empty first run.** A fresh instance shows the empty state; the E2E asserts
  it in addition to the populated case.

## 7. Decisions Made

These were open in the earlier draft and are decided here:

1. **Route:** `/settings/usage`, a settings cluster. Not a top-level route: the
   page belongs to the account's configuration, and the hub already organises
   exactly these.
2. **Tokens:** included, as separate input/output sums. The API promised them in
   the goal; the columns exist; a call counter alone is not "usage".
3. **Index:** added, as a migration. The table never shrinks and the filter is
   always user + time.
4. **Cost:** absent, explicitly. `cost_usd` stays NULL until a catalog prices it.
5. **Pagination:** absent, because the grouping key is a fixed task list.

## 8. Expected Verification

- `just test-file app/kernel/tests/test_llm_usage.py` — aggregates, scoping,
  periods, empty, token NULLs, invalid `days`.
- `just test-file app/kernel/db/tests/test_migrations.py` — head replay equals
  models.
- `just test-frontend` — the page's states and the range refetch.
- `just test-e2e settings` — title, nav, `aria-current`, the table, the period
  filter, the empty state, axe.
- `just check`, `just check-generated`, `just build`.
