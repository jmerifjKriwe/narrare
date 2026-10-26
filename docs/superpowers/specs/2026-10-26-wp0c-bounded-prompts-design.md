# WP0-C — Bounded prompts and structured output (Phase 0, §3.2 + §3.3)

Design, 2026-10-26. Authority for the *what*: foundation plan §3.2, §3.3. This document
records the decisions the foundation plan leaves open; where it departs from that plan,
the departure is named at the end.

## Intent and why

With the fake provider, extraction sends a chapter's whole body and the consistency check
sends every chapter in one prompt — a real model overflows the context window on any
novel of size. Answers come back as JSON-in-prose parsed by hand: one malformed answer
fails the job with no repair attempt and no retry.

Success is: extraction bounded, the check map-reduced over chapters with live progress,
answers demanded as JSON schemas and repaired or retried once before a job fails for a
reason the user can read.

## Goals

- Extraction sends at most 20 000 characters of body; the job result carries
  `truncated`, and the dock names it.
- The consistency check runs one pass per chapter (the canon entities in every pass),
  merges findings and deduplicates by `summary`; a chapter over the bound is reported
  skipped — never silently dropped; the dock names the skipped chapters.
- Structured output: `response_format` json_schema (the WP0-A contract already carries
  it), parse → `json_repair` → one retry with the validation error appended → the job
  fails with the parse reason in `Job.error`.
- Every provider call audited: map-reduce means one `llm_calls` row per chapter, plus one
  per retry.

## Non-goals

- No provider profiles, catalog or budget (WP2). No `web/` change beyond the two dock
  rows. No change to chat or writing. No kernel/llm code beyond consuming the contract.

## Constraints

- The helper is capability-local (`app/capabilities/knowledge/`): the spec's rule is a
  kernel module for two or more consumers; one capability consuming it keeps it here
  until WP2 proves a second.
- The only permitted fake is the LLM provider at its boundary; the dev fake stays
  honest — it never emits malformed JSON.
- en/de/fr for every new user-visible string; a missing key is a build error.
- Nothing is committed before a green review (AGENTS.md).

## Approaches considered

1. **Making the malformed-JSON path testable.** (a) A stub `TextProvider` in unit tests
   plus a scripted openai-compatible stand-in in the E2E — the fake stays honest;
   (b) a marker in the fake that emits malformed JSON — the fake then holds behaviour no
   real provider promised; (c) unit tests only — the Phase 0 verification ("a malformed
   JSON answer retries once and then fails visibly") would not be proven on the real
   stack. **Chosen: (a)** (coordinator, 2026-10-26).
2. **Live progress per chapter.** (a) The lane owns it: handlers get a `report`
   callback, the worker persists it in its own session — the handler's terminal commit
   and D3 (a failed job writes no audit row) stay untouched; (b) the handler commits
   progress per chapter — breaks D3 (partial audits on failure) and duplicates rows on
   the at-least-once re-run; (c) no live progress (0 → 100 terminal) — quietly drops
   what §3.2 promises. **Chosen: (a)**.
3. **Where the structured-output helper lives.** Capability-local now, kernel when a
   second consumer exists. **Chosen: capability-local.**

## Design

### Progress belongs to the lane (`app/kernel/jobs/worker.py`)

`JobHandler` grows a third parameter: `report: ProgressReport`,
`ProgressReport = Callable[[int], Awaitable[None]]`. The worker builds one per handler
run; each call writes the claimed row's `progress` in the worker's own short transaction.
Handlers stop writing the column themselves. A handler that reports 100 and then raises
leaves progress at 100 with `error` set — the row tells the truth twice, which is the
lane's existing honesty about failure.

### The structured ask (`app/capabilities/knowledge/structured.py`)

One function used by both handlers. It takes the provider, the request's prompt and
schema, a parse callable, and an audit callback; it sends `response_schema` (the adapter
maps it to `response_format` since WP0-A); on a parse failure it tries `json_repair`
before anything else; if the repaired text still fails, it retries **once** with the
validation error appended to the messages; a second failure raises
`MalformedAnswerError` whose text is the parse reason — the worker writes it to
`Job.error`. Every call, including the retry, is audited through the callback with the
handler's session: audits still ride the handler's terminal commit, so D3 holds — a
failed job leaves no audit row.

### Bounded prompts (`app/capabilities/knowledge/`)

One constant, `BODY_LIMIT = 20_000` **characters** (not bytes), one behaviour per
handler:

- **Extraction truncates.** The prompt carries the first 20 000 characters; the result
  carries `truncated: true` when the body was longer; the dock names it.
- **Consistency skips.** A chapter over the limit is not sent; the result carries
  `skipped_chapters` as the list of its titles; the dock names them. A partially checked
  novel would be a lie a writer acts on; suggestions from a chapter's head are not.

The asymmetry is the plan's, not an accident.

### Map-reduce (`check_consistency`)

Load the novel's chapters and canon entities once. For each chapter within the bound: one
structured pass (canon entities and that chapter's body), one audit row, `report` of the
running percentage. Merge all findings, deduplicate by `summary` (first occurrence
wins). A novel whose every chapter is over the bound makes no provider call, files no
findings, and lists every chapter as skipped — the job is done, not failed. A novel with
no chapters likewise makes no call (today it sends an empty prompt; see deviations).

## Verification

- Unit (stub `TextProvider`, real parse functions): repair path; retry path (second
  prompt carries the validation error); fail path (`MalformedAnswerError`, reason in the
  text); merge and dedupe across chapters; truncation at and around the boundary; the
  skip list; exactly-at-limit chapters neither truncated nor skipped.
- Kernel: `report` persists progress per call, and progress survives a handler that
  raises afterwards.
- E2E, real stack: a two-chapter check merges findings; a chapter typed past the limit
  is named as skipped in the dock; a truncated extraction is named; the malformed-JSON
  path runs against a scripted openai-compatible stand-in and either recovers on the
  retry (two audit rows) or fails with the parse reason in `Job.error`.
- `just check` before every commit; `just verify` before the WP closes.

## Deviations from foundation plan §3.2/§3.3 (to be reported in the commits)

1. **Progress is written by the lane, not the handler.** §3.2 promises "progress per
   chapter" without naming the writer; the handler-committed variant would break D3.
2. **`json_repair` is a new runtime dependency** — approved by the product owner
   (2026-10-25) against the recommendation to stay dependency-free.
3. **A chapterless novel makes no provider call** where today it is sent an empty prompt.
   Map-reduce makes the question moot; documented so the old docstring's promise is not
   silently inverted.
