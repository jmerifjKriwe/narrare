# WP0-C — Bounded prompts and structured output · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extraction stops sending whole chapters and the check stops sending whole
novels; answers are demanded as JSON, repaired, retried once, and a job that fails names
why — with live per-chapter progress on the check.

**Architecture:** The lane owns progress (`report` callback, own transaction); a
capability-local `ask_structured` owns ask→parse→repair→retry for both knowledge
handlers; one 20 000-character bound truncates extraction and skips check chapters.

**Tech Stack:** Python 3.14, SQLAlchemy async, pytest (+pytest-asyncio), `json_repair`
(new runtime dependency, approved), Playwright against the real stack.

**Spec:** `docs/superpowers/specs/2026-10-26-wp0c-bounded-prompts-design.md`; foundation
plan §3.2, §3.3 (`docs/superpowers/plans/2026-10-25-v2-foundation.md`).

## Global Constraints

- The helper is capability-local in `app/capabilities/knowledge/`; kernel untouched
  except `kernel/jobs` (progress) — never the other way round.
- The dev fake (`app/kernel/llm/fake.py`) stays honest: no malformed-JSON behaviour. The
  only fakes are provider stubs at the `TextProvider` boundary in tests and a scripted
  openai-compatible stand-in in the E2E.
- en/de/fr for every user-visible string; `just generate` after i18n/*.json.
- Audits ride the handler's terminal commit (D3 unchanged: a failed job writes no audit
  row). Every provider call is audited, including retries.
- `just check` before every commit, output read. Nothing is committed before the review
  is green. Touch only the files a task names.
- English in code, comments, tests and docs.

## Review Focus

- **A chapter of exactly 20 000 characters** — neither truncated nor skipped; the
  boundary is inclusive (Task 3 test).
- **A novel whose every chapter is over the bound** — no provider call, no findings, all
  chapters named as skipped, job done, not failed (Task 4 test).
- **Characters, not bytes** — a body of 20 000 characters containing multi-byte code
  points is not truncated (Task 3 test).
- **The retry's prompt carries the validation error** from the first parse failure
  (Task 2 test, asserted on the stub's second request).
- **Progress survives a failed run** — a handler that reports 50 and then raises leaves
  progress=50 and error set on the row (Task 1 test).

---

## Task 1: The lane owns progress

**Files:**
- Modify: `app/kernel/jobs/worker.py` (JobHandler type, report callback)
- Modify: `app/capabilities/knowledge/jobs.py` (both handler signatures; extraction
  reports instead of writing the column)
- Test: `app/kernel/tests/test_jobs.py`

**Interfaces:**
- Produces: `ProgressReport = Callable[[int], Awaitable[None]]` (worker.py);
  `JobHandler = Callable[[AsyncSession, Job, ProgressReport], Awaitable[dict[str, object]]]`;
  handlers `extract_entities(session, job, report)` / `check_consistency(session, job, report)`.
  The worker persists each `report(value)` on the claimed row in its **own** short
  transaction — the handler's terminal commit is untouched.

- [ ] **Step 1: Write the failing kernel test**

In `app/kernel/tests/test_jobs.py`, following the file's existing fixtures:

```python
async def test_report_persists_progress_and_survives_a_later_raise(...):
    # A handler that reports twice, then raises: the row keeps the last
    # reported progress and gains the error — the lane's honesty about
    # failure, not the handler's.
    async def handler(session, job, report):
        await report(25)
        await report(50)
        raise RuntimeError("boom")

    # enqueue, run the lane once (the file's existing pattern), then:
    assert job_row.progress == 50
    assert job_row.status == FAILED
    assert "boom" in job_row.error
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `just test-file app/kernel/tests/test_jobs.py`
Expected: FAIL — `handler() takes 3 positional arguments` / type mismatch, no report.

- [ ] **Step 3: Implement in `worker.py`**

`ProgressReport` type as above; the lane builds one `report` per run (fresh session per
call, `update(Job).where(Job.id == job.id).values(progress=value)`, commit); the handler
call passes it third. Update the module docstring's discipline paragraph: handlers own
their transaction, the lane owns progress.

- [ ] **Step 4: Update both knowledge handlers' signatures**

`extract_entities` / `check_consistency` take `report`; extraction replaces its
`update(Job)...progress=100` (and its comment) with `await report(100)` right before
returning — the row's status flips only after the handler returns, so 100 never
precedes a done row the database lacks. `check_consistency` keeps its `progress=100`
write for now (Task 4 replaces the whole body); only the signature changes here.

- [ ] **Step 5: Run the suites**

Run: `just test-file app/kernel/tests/test_jobs.py` → PASS.
Run: `just test` → PASS (216; api/job-handler tests included).
Run: `just check` → PASS.

- [ ] **Step 6: Commit**

```bash
git add app/kernel/jobs/worker.py app/capabilities/knowledge/jobs.py app/kernel/tests/test_jobs.py
git commit -m "refactor(jobs): the lane owns a job's progress, handlers report it"
```

(No `User-visible:` line — the reported numbers do not change in this task; Task 4
makes them live.)

---

## Task 2: `ask_structured` — ask, parse, repair, retry once

**Files:**
- Modify: `pyproject.toml` + `uv.lock` (`json_repair` runtime dependency)
- Create: `app/capabilities/knowledge/structured.py`
- Modify: `app/capabilities/knowledge/jobs.py` (`MalformedAnswerError` moves to
  structured.py; jobs re-exports it so existing imports keep working)
- Test: `app/capabilities/knowledge/tests/test_structured.py` (new)

**Interfaces:**
- Consumes: `TextProvider`, `CompletionRequest`, `Message`, `Delta`, `Usage` from
  `app.kernel.llm` (WP0-A contract).
- Produces:
  `async def ask_structured(provider: TextProvider, prompt: str, *, schema_name: str, schema: dict[str, object], parse: Callable[[str], list[T]], audit: Callable[[AuditedCall], Awaitable[None]]) -> list[T]`
  with `@dataclass(frozen=True) class AuditedCall: prompt: str; answer: str; latency_ms: int; usage: Usage | None`
  and `class MalformedAnswerError(ValueError)`. Raises `MalformedAnswerError` whose
  `str()` is the parse reason after the failed retry; audits every call through `audit`.

- [ ] **Step 1: Add the dependency**

`pyproject.toml` `[project] dependencies`: `"json_repair>=0.4.0"` (or the version
`uv add json_repair` resolves); `uv lock` updates `uv.lock`; `uv sync` stays green.

- [ ] **Step 2: Write the failing tests (stub provider)**

A `StubProvider` implementing `TextProvider` whose scripted `answers: list[str]` are
consumed per `stream()` call (raising when empty), yielding the answer as one `Delta`
plus a `Usage(1, 1)`; a recording `audit` appending to a list. Four tests:

```python
async def test_valid_answer_parses_with_one_call_and_one_audit(): ...
async def test_malformed_answer_is_repaired_without_a_retry():
    # answers[0] is the entities JSON with a trailing comma — parse fails,
    # json_repair fixes it, one provider call, one audit row.
async def test_retry_once_with_the_validation_error_appended():
    # answers[0] unrepairable prose, answers[1] valid. Two calls; the second
    # request's messages carry the first parse error (assert on the captured
    # CompletionRequest.messages[-1].content); two audit rows.
async def test_second_failure_raises_with_the_parse_reason():
    # both answers unrepairable: MalformedAnswerError, str() names what the
    # parser said; two calls, two audits.
```

- [ ] **Step 3: Run and confirm they fail**

Run: `just test-file app/capabilities/knowledge/tests/test_structured.py`
Expected: FAIL — module/function not defined.

- [ ] **Step 4: Implement `structured.py`**

Collect the stream (Delta/Usage loop, `monotonic()` latency) → `parse(answer)`; on
failure `json_repair.repair_json(answer, return_objects=False)`-style repair → parse; on
failure build the retry `CompletionRequest(messages=(Message("user", prompt), Message("user", f"The previous answer was invalid: {reason}. Answer again as JSON.")), response_schema=schema)` → one more call; on failure raise
`MalformedAnswerError(f"...{reason}")`. First request is
`CompletionRequest.user(prompt)` with `response_schema=schema` set. Audit each call
(prompt as sent, answer, latency, usage) — status is the handler's business.

- [ ] **Step 5: Run the suites**

Run: `just test-file app/capabilities/knowledge/tests/test_structured.py` → PASS.
Run: `just test` → PASS (MalformedAnswerError re-export keeps old tests green).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock app/capabilities/knowledge/structured.py \
        app/capabilities/knowledge/jobs.py \
        app/capabilities/knowledge/tests/test_structured.py
git commit -m "feat(knowledge): structured answers are repaired and retried once"
```

---

## Task 3: Extraction is bounded

**Files:**
- Modify: `app/capabilities/knowledge/prompts.py` (`BODY_LIMIT`)
- Modify: `app/capabilities/knowledge/jobs.py` (extract_entities: truncate, ask via
  `ask_structured`, result carries `truncated`)
- Modify: `app/capabilities/knowledge/web/ExtractionPanel.tsx` (names a truncated read)
- Modify: `i18n/{en,de,fr}.json` + `just generate`
- Test: `app/capabilities/knowledge/tests/test_extraction.py`

**Interfaces:**
- Consumes: `ask_structured`, `AuditedCall` from Task 2; `report` from Task 1.
- Produces: `BODY_LIMIT = 20_000` in prompts.py; extraction result
  `{"suggestions": int, "truncated": bool}`.

- [ ] **Step 1: Write the failing tests**

Using the file's existing db/session fixtures and a `StubProvider` monkeypatched as
`get_provider`:

```python
async def test_a_long_body_is_cut_at_the_limit_and_reported_truncated():
    # chapter body of 20_001 chars: the audited prompt contains the first
    # 20_000 and not the last; result["truncated"] is True
async def test_a_body_at_the_limit_is_sent_whole():
    # exactly 20_000 chars: prompt ends with the body's last char,
    # result["truncated"] is False
async def test_the_limit_counts_characters_not_bytes():
    # 20_000 chars of "é" (40_000 bytes): not truncated
```

- [ ] **Step 2: Run and confirm they fail**

Run: `just test-file app/capabilities/knowledge/tests/test_extraction.py`
Expected: FAIL — no truncation, no `truncated` key.

- [ ] **Step 3: Implement**

`BODY_LIMIT = 20_000` in prompts.py (characters; `body[:BODY_LIMIT]`); extraction
builds its prompt from the cut body, calls `ask_structured` with the existing
`parse_entities` and the entities-JSON schema (write the schema dict once, next to the
parse function it belongs to), audits through a closure calling `record_call` with
`task_key="knowledge.extract-entities"`; result gains `"truncated": len(body) > BODY_LIMIT`.

- [ ] **Step 4: The dock names it**

`ExtractionPanel.tsx`: when the settled job's `result.truncated` is true, the row shows
`t("jobs.truncated")`. Keys (exact copy):

- `jobs.truncated`: en "Only the first 20,000 characters were read." /
  de "Nur die ersten 20.000 Zeichen wurden gelesen." /
  fr "Seuls les 20 000 premiers caractères ont été lus."

`just generate`; the panel test (if the file has one) extended or the E2E in Task 5
carries the proof.

- [ ] **Step 5: Run the suites**

Run: `just test-file app/capabilities/knowledge/tests/test_extraction.py` → PASS.
Run: `just test` and `just test-frontend` → PASS. `just check` → PASS.

- [ ] **Step 6: Commit**

```bash
git add app/capabilities/knowledge/prompts.py app/capabilities/knowledge/jobs.py \
        app/capabilities/knowledge/web/ExtractionPanel.tsx \
        i18n/en.json i18n/de.json i18n/fr.json web/lib/generated/catalogs.ts \
        app/capabilities/knowledge/tests/test_extraction.py
git commit -m "feat(knowledge): extraction reads at most the first 20 000 characters"
```

`User-visible:` line: extraction names it when a chapter was only partly read.

---

## Task 4: The check is map-reduce over chapters

**Files:**
- Modify: `app/capabilities/knowledge/prompts.py` (per-chapter consistency prompt)
- Modify: `app/capabilities/knowledge/jobs.py` (check_consistency rewritten)
- Modify: `app/capabilities/knowledge/web/ChecksPanel.tsx` (names skipped chapters)
- Modify: `i18n/{en,de,fr}.json` + `just generate`
- Test: `app/capabilities/knowledge/tests/test_consistency.py`

**Interfaces:**
- Consumes: Tasks 1–3 (`report`, `ask_structured`, `BODY_LIMIT`).
- Produces: check result `{"findings": int, "skipped_chapters": list[str]}`;
  `consistency_prompt(entities, chapter_title, body)` (singular chapter).

- [ ] **Step 1: Write the failing tests**

```python
async def test_each_chapter_is_its_own_call_and_findings_merge():
    # two chapters, stub answers with one finding each: two provider calls,
    # two audit rows, both findings filed
async def test_duplicate_summaries_across_chapters_deduplicate():
    # same summary from both passes: filed once, result["findings"] == 1
async def test_an_oversized_chapter_is_skipped_by_name():
    # chapter "Riesig" at 20_001 chars: never sent (one call for the other
    # chapter only), result["skipped_chapters"] == ["Riesig"]
async def test_a_novel_of_only_oversized_chapters_is_done_with_no_call():
    # no provider call, no findings, all names skipped, handler returns
async def test_progress_is_reported_per_chapter():
    # three chapters: report receives 33, 66 (values in order; 100 is the
    # handler's last report)
```

- [ ] **Step 2: Run and confirm they fail**

Run: `just test-file app/capabilities/knowledge/tests/test_consistency.py`

- [ ] **Step 3: Implement**

`check_consistency` loads chapters and canon entities once; per chapter within the
bound: `ask_structured(...)` with `consistency_prompt(entities=…, chapter_title=…, body=…)`
and the findings schema; audit closure with `task_key="knowledge.check-consistency"`
(one row per call); collect findings; `await report(round(done / total * 100))` after
each pass (total = chapters within the bound; a total of 0 skips reporting entirely);
dedupe by `summary` keeping first occurrence in chapter order; result as above.

- [ ] **Step 4: The dock names the skipped chapters**

`ChecksPanel.tsx`: the settled row lists `result.skipped_chapters` through
`t("jobs.skippedChapters", {titles})`:

- `jobs.skippedChapters`: en "Skipped, too long: {titles}" /
  de "Übersprungen, zu lang: {titles}" /
  fr "Ignorés, trop longs : {titles}"

- [ ] **Step 5: Run the suites**

Run: `just test-file app/capabilities/knowledge/tests/test_consistency.py` → PASS.
Run: `just test`, `just test-frontend`, `just check` → PASS.

- [ ] **Step 6: Commit**

```bash
git add app/capabilities/knowledge/prompts.py app/capabilities/knowledge/jobs.py \
        app/capabilities/knowledge/web/ChecksPanel.tsx \
        i18n/en.json i18n/de.json i18n/fr.json web/lib/generated/catalogs.ts \
        app/capabilities/knowledge/tests/test_consistency.py
git commit -m "feat(knowledge): the check runs per chapter and names what it skipped"
```

`User-visible:` the whole-novel check survives long novels, shows live progress, and
names chapters too long to check.

---

## Task 5: The real stack proves it, and the record

**Files:**
- Test: `app/capabilities/knowledge/e2e/test_bounded_e2e.py` (new)
- Modify: `app/kernel/testing/vendor_server.py` (an LLM stand-in route, if the existing
  server is the right home — otherwise a sibling module used the same way)
- Docs: `docs/superpowers/reports/2026-10-26-wp0c-report.md` (new)

**Interfaces:**
- Consumes: everything above; the E2E stack's `env` for `NARRE_LLM_PROVIDER` /
  base-URL pointing at the stand-in (read `OpenAICompatibleProvider.from_environment`
  for the exact variable names before writing the fixture).

- [ ] **Step 1: Write the E2E**

Three flows on the real stack (browser, API, Postgres), the fake provider except where
the stand-in is named:

1. A two-chapter novel with a planted contradiction per chapter: the check settles done,
   both findings reviewable, the row's progress was observable below 100 during the run
   (poll while running — assert at least one poll saw 0 < progress < 100, with a
   chapter count and timing that make the window real; if the fake answers too fast,
   assert instead that the result merged both chapters' findings and say so in the
   report).
2. A chapter typed past 20 000 characters via `page.keyboard.insert_text`: the check
   names it skipped; an extraction of the same chapter names the truncated read.
3. The malformed path against the scripted stand-in: first answer unrepairable prose,
   second valid — the job settles done with the findings and `llm_calls` carries two
   rows for the task (assert via the DB or an API surface, whichever the stack exposes).

- [ ] **Step 2: Run it and confirm the flows fail without their features**

Where a flow can run red (stash the production file it exercises), record the red; where
it cannot (new file, nothing to stash), say so in the report instead of inventing a
stash.

- [ ] **Step 3: Full gate**

Run: `just verify` → green, output read.

- [ ] **Step 4: The report**

`docs/superpowers/reports/2026-10-26-wp0c-report.md`: red outputs, the three deviations
from the design doc, the review focus lines and where each is pinned, gate counts.

---

## Verify

1. Every commit: `just check` ran, output read.
2. `grep -c "jobs.truncated\|jobs.skippedChapters" i18n/{en,de,fr}.json` → 2 each.
3. `grep -n "json_repair" pyproject.toml uv.lock` → present in both.
4. D3 intact: no test asserts an audit row for a failed job; the fail-path test asserts
   the raise, and the handler-level tests confirm rows only on success.
5. `just verify` green at close, output read.

## Report

Terse, pipe-delimited, English, nothing else:

```
status: DONE|BLOCKED
files: <commits with files, one token each>
ledger: <n>/5 tasks, one token each
verify: <per-commit just check, final just verify counts>
deviations: none | <what and why>
concerns: none | <what>
```
