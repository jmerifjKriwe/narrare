# STATS-002 — Cost CSV Export — Design Addendum

- **Date:** 2026-10-07
- **Status:** PO-ratified (analytics program decision sheet, item B; sequencing C→D→B→A→E)
- **Amends:** `2026-10-05-stats002-cost-tracking-design.md` §9 — implements the "CSV export"
  deferred slice; PDF is formally REJECTED (design-sheet ruling: CSV covers data egress,
  the panel is the presentation view, and a cost PDF would widen the RULE-08-guarded
  renderer surface for near-zero value)
- **ADR:** none needed (surface addition inside the existing analytics module; no new seam,
  no new dependency — stdlib `csv` only)

---

## 1. Decisions

| # | Decision | Ruling |
|---|----------|--------|
| B-1 | Endpoint | `GET /api/v1/analytics/costs/export?month=YYYY-MM` (auth required; month optional, default current server-local month — same semantics as the costs endpoint; same `^\d{4}-(0[1-9]|1[0-2])$` pattern + service-side year-window guard ⇒ 422). Month-only in v1 — no from/to range (no stated need, validation surface for nothing). |
| B-2 | Response | `StreamingResponse` with an async generator (house style — SSE/streaming precedents; constant memory). `text/csv; charset=utf-8`, `Content-Disposition: attachment; filename="narrare-costs-<YYYY-MM>.csv"`. BOM prefix (`\ufeff`) so Excel opens UTF-8 correctly. |
| B-3 | Columns (header row, exact order) | `created_at,intent,provider,model_id,tokens_in,tokens_out,cache_read_tokens,cache_creation_tokens,duration_ms,cost_usd,novel_id` — `cost_usd` empty string when NULL (unpriced); `novel_id` empty when NULL; `created_at` ISO-8601 UTC. Includes embedding rows (same table). |
| B-4 | Streaming source | repository stream method over the month window (user-scoped, `[start, end)` UTC bucketing identical to `aggregate_range`), `yield_per`-style chunked row iteration — NO full-month list in memory. |
| B-5 | CSV formatting | service layer (stdlib `csv` module, `aiocsv` NOT introduced); generator yields formatted lines through an asyncio queue or direct async iteration — simplest honest shape wins; router delegates immediately (RULE-06). |
| B-6 | FE | "Export CSV" button in `AnalyticsCostsPanel`'s header next to the month selector, exporting the currently selected month; authenticated fetch → blob → object-URL download (no new dependency, no page reload). Disabled state while a request is in flight. |
| B-7 | i18n | `analytics.costs.exportCsv` label (en/de/fr) — the only new string. |

## 2. Testing Strategy

- **Repository:** stream returns rows in `created_at` order for the month window, user-scoped, half-open bounds (mirror the aggregation tests' fixtures — real PG where available).
- **Service/router:** header row + row formatting (unpriced ⇒ empty cell, novel NULL ⇒ empty, ISO timestamps); 422 for invalid/unconstructible months (reuse the year-edge guard); 401 unauthenticated; content-type + disposition headers; streaming actually chunks (first chunk arrives before generator exhaustion in tests).
- **FE:** button renders with label, triggers a download (msw handler; assert blob URL creation mocked), disabled-while-loading; i18n parity.

## 3. Out of Scope

PDF (rejected) · from/to ranges · per-novel filtered export · CSV column customization · export of budgets (stage A) data.
