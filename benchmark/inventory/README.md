# KB Benchmark — User-Capability Inventory

> Program reference: [ADR-083 — KB Infrastructure Benchmark Program](../../docs/architecture/decisions/ADR-083-kb-infrastructure-benchmark-program.md)
> Instrument design: "KB Infrastructure Benchmark — Instrument Design" spec
> (2026-08-20), §3 — path recorded under "Detailed instrument design" in the ADR above

## Purpose

This directory holds the **user-perspective test surface** of the Knowledge Base,
per instrument-design spec §3. The benchmark measures exactly these capabilities —
nothing that is absent here is measured, and nothing here is measured by any other
means. The inventory is therefore also the **implicit yardstick for later
candidates**: a candidate tool is measured against precisely these capabilities,
with adapted tests using its native operations (spec §7).

## Method

- **API paths** are sourced from the frontend's own API clients
   (`packages/web/lib/api/*.ts`) and cross-verified against the backend routers
   (`apps/api/narrare/*/router*.py` decorators). A path is only listed when the
   router decorator mechanically matches (see each file's survey; those
   verification logs are session-local and not committed — re-run the checks
   per this Method).
- **LLM-backed** means: the service behind the route invokes an agent/LLM —
  verified by checking the service's imports of `narrare_core.agents`.
- **Output artifact** is the response/stream the user actually receives
  (KB entry, report, SSE stream, …).

## Entry format

Used verbatim in `01-in.md`, `02-out.md`, `03-check.md`:

```markdown
### CAP-IN-NN: <capability name, user perspective, one sentence>

| Field | Value |
|---|---|
| Direction | in |
| API path(s) | `<METHOD> /api/v1/<path>` (router: `apps/api/narrare/<domain>/router*.py`; client: `packages/web/lib/api/<file>.ts`) |
| Output artifact | <what the operation produces: KB entry, report, SSE stream, …> |
| LLM-backed | yes / no / partial (<one-line reason, e.g. service uses ExtractionAgent>) |
| Benchmarkable | yes / partially / no (<one-line reason: is the output mechanically scorable against a reference?>) |
| Notes | <optional: preconditions, caveats, findings> |
```

## Findings rule

Capabilities that exist only as frontend orchestration (no direct API path) are
recorded as findings in the file's trailing `## Findings` section — verdict
`not benchmarkable as-is` or `backend must expose this` — never silently dropped
(spec §3). The same section records scope decisions that kept a verifiable path
out of a file (with a one-line reason), so Tasks 3–5 inherit an explicit ledger.

## Status

- **Files:**
  - `README.md` — this file (format + method).
  - `01-in.md` — direction `in` (text → KB): **9 entries, 26 mechanically verified
    API paths, 6 findings** (surveyed 2026-08-21; revised 2026-08-22, register
    R7/R8 riders).
  - `02-out.md` — direction `out` (KB → use): surveyed 2026-08-21 — 10 entries, 21 verified API paths.
  - `03-check.md` — direction `check` (KB ↔ text): surveyed 2026-08-21 — 7 entries, 8 verified API paths.
  - `04-findings.md` — synthesis: findings register + counts (20 raw findings →
    13 register entries), 2026-08-21.
- **Coverage counts** (entries / verified paths / findings; revised 2026-08-23):
  in = 9 / 26 / 6; out = 10 / 21 / 8; check = 7 / 8 / 8. Synthesis across
  directions: `04-findings.md` (13 register entries; 20 raw findings at
  synthesis time — the 2026-08-22 in-F5/F6 riders postdate it).
- Direction `in` survey scope: `apps/api/narrare/kb/`, `apps/api/narrare/series/`,
  `apps/api/narrare/planning/`, `apps/api/narrare/wiki/` routers mounted in
  `_app/main.py`, cross-read against `packages/web/lib/api/`.
