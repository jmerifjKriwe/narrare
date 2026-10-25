# WP0-A — LLM contract and the `LlmCall` audit (Phase 0, §3.5 + §3.4)

> **For agentic workers:** backend only — no `web/` change, no i18n key, the SSE wire
> the browser sees stays byte-identical. Spec: foundation plan §3.4, §3.5, §12 (Phase 0
> rows), `docs/superpowers/plans/2026-10-25-v2-foundation.md`. Authority: the plan;
> where plan and tree disagree, the tree wins and the deviation is reported.

**Goal:** `TextProvider.stream(prompt)` becomes `stream(CompletionRequest)` yielding
`Delta | Usage | Done`, and every provider call lands in a new kernel table
`llm_calls` — the evidence table WP2/WP4 assert on.

**Approved decisions (coordinator, 2026-10-25 — binding, pre-adjudicated):**

- **D1** Task 1 touches six production files in one atomic commit (a protocol swap has
  no green intermediate). This exceeds the usual three-file limit by necessity.
- **D2** No `profile_id` column until WP2: no profile table exists; a dead column would
  be a lying schema. WP2 adds it with the then-usual `db-reset`.
- **D3** A failed job writes no audit row — the handler's transaction rolls back
  wholesale (D14); the job's `error` column already names the failure. Failed streams
  DO audit (`status="error"`). The asymmetry is documented, not accidental.
- **D4** The adapter stays hand-rolled httpx; the `openai` SDK swap belongs to WP2 with
  the profiles. Only the `response_format` mapping lands now, so WP0-B does not reopen
  the adapter.
- **D5** `cost_usd` stays NULL until WP2's catalog — never 0. NULL-vs-0 is pinned by a
  test now.
- **D6** The fake's `Usage` rule is `len(prompt) // 4` / `len(answer) // 4`,
  deterministic and pinned; WP2 replaces it with the profile's `chars_per_token`.

## Hard constraints

- Touch only the files named in the tasks. No `just generate` (no route/view changes).
  No `--no-verify`, no force push. English everywhere.
- The browser-visible SSE frames (`data: {"delta": …}`, `event: done`, `event: error`)
  are unchanged — pinned by the existing capability tests, which must pass unmodified
  except where a task names the edit.
- The fake stays the only fake. No new packages.
- No new rule, registry, gate or hook.
- `just check` before every commit. A red suite stops the task; report BLOCKED.

## Expected tree state before starting

`git status --porcelain` shows exactly this brief as untracked plus the local-only
`.opencode/dispatches/` directory, nothing else:

```
?? docs/superpowers/plans/2026-10-25-wp0a-llm-contract-audit.md
?? .opencode/dispatches/
```

Base: the commit this branch was cut from (`f9c155895f9e9671a488bcdd6392c4c27b7a3ac5`).
Anything else dirty: stop.

---

## Task 1 — The contract swap (atomic)

**Files:** `app/kernel/llm/contract.py`, `app/kernel/llm/fake.py`,
`app/kernel/llm/openai_compat.py`, `app/capabilities/writing/router.py`
(`_continuation_events` only), `app/capabilities/chat/router.py` (`_events` only),
`app/capabilities/knowledge/jobs.py` (the two provider loops only) · Tests:
`app/kernel/tests/test_fake_provider.py`, `app/kernel/tests/test_openai_compat.py`.

**Interfaces (produced, exact):**

```python
@dataclass(frozen=True)
class Message:
    role: str          # "system" | "user"
    content: str

@dataclass(frozen=True)
class CompletionRequest:
    messages: tuple[Message, ...]
    temperature: float | None = None
    max_tokens: int | None = None
    response_schema: dict[str, object] | None = None

    @classmethod
    def user(cls, prompt: str) -> CompletionRequest: ...

@dataclass(frozen=True)
class Delta:
    text: str

@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int

@dataclass(frozen=True)
class Done: ...

DONE = Done()
CompletionEvent: TypeAlias = Delta | Usage | Done

class TextProvider(Protocol):
    def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]: ...
```

- **Fake:** purpose/sources read from the joined user-message contents (answers
  unchanged); after the last delta it yields `Usage(input_tokens=len(prompt) // 4,
  output_tokens=len(answer) // 4)` (D6), then `DONE`. For the prose shapes the answer
  is the joined chunks; for JSON shapes it is the single piece.
- **openai_compat:** `messages` mapped as-is; `temperature`/`max_tokens` in the body
  only when not `None`; `response_schema` → `"response_format": {"type":
  "json_schema", "json_schema": {"name": "answer", "schema": …}}` (no consumer sets it
  yet — WP0-B does); always `"stream_options": {"include_usage": true}`; a frame
  carrying `"usage"` yields `Usage(prompt_tokens, completion_tokens)`; exactly one
  `DONE` as the last event, with or without a `[DONE]` line (local servers omit it).
- **Consumers:** build `CompletionRequest.user(prompt)`; forward `Delta.text` exactly
  as before; `Usage` is captured for Tasks 4/5; `DONE` ends the loop.

**Tests (red first):** fake — purpose answers unchanged under the new call shape;
`Usage` numbers as pinned by D6; `DONE` last in every shape. openai_compat — the body
carries `messages` and `stream_options`; optional fields are absent when unset;
`response_format` mapping; the usage frame parses to `Usage`; deltas in order;
refusal still raises. The existing capability tests pass unmodified.

**Commit 1:**

```
refactor(kernel): the provider contract carries messages, limits and usage

TextProvider.stream(prompt) could not express a system message, max_tokens,
temperature, JSON mode or usage (plan §3.5). It becomes stream(CompletionRequest)
yielding Delta | Usage | Done; the fake derives deterministic Usage from the
markers, the openai-compatible adapter maps stream_options.include_usage and
response_format. The SSE wire the browser sees is unchanged; the capability
tests pass unmodified.

User-visible: none — the wire is unchanged.
```

## Task 2 — The `llm_calls` table

**Files:** create `app/kernel/llm/models.py` (mirrors `app/kernel/jobs/models.py`),
modify `app/kernel/db/init.py` (the registration import, same pattern as
`jobs_models`) · Test: `app/kernel/tests/test_llm_audit.py` (new file).

Columns, exactly: `id UUID pk (uuid4)`, `user_id` (UserOwned), `novel_id: UUID | None`
(plain column, no FK — a log row outlives its novel), `task_key: str(100)`,
`prompt_key: str(100) | None` (NULL until WP4), `provider_kind: str(40)`,
`model: str(200)`, `input_tokens: int | None`, `output_tokens: int | None`,
`cost_usd: float | None` (NULL until WP2 — never 0, D5), `latency_ms: int`,
`status: str(16)` (`ok`|`error`), `error: Text | None`, `prompt_text: Text`,
`response_text: Text`, `truncated: bool`, `created_at` (timezone-aware, the Job
pattern). No `profile_id` (D2).

**Test:** after `reset_schema`/`init_schema` the table `llm_calls` exists with exactly
these columns (assert on `Base.metadata`); the jobs and contracts tables are still
registered.

**Commit 2:**

```
feat(kernel): the llm_calls audit table

One row per provider call: prompt and answer (capped), tokens, latency, status
(plan §3.4). cost_usd stays NULL until WP2's catalog exists — NULL, never 0.
No profile_id until a profile table exists (WP2, with the then-usual db-reset).
A log row: novel_id carries no foreign key, so the audit outlives its novel.

User-visible: none — groundwork for WP2/WP4 proof.
```

## Task 3 — The writer

**Files:** create `app/kernel/llm/audit.py` · Test: `app/kernel/tests/test_llm_audit.py`.

**Interface (exact):**

```python
async def record_call(
    session: AsyncSession,
    *,
    user_id: UUID,
    task_key: str,
    provider_kind: str,
    model: str,
    latency_ms: int,
    status: str,
    prompt_text: str,
    response_text: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    novel_id: UUID | None = None,
    prompt_key: str | None = None,
    error: str | None = None,
) -> None
```

Adds to the caller's session, never commits; caps `prompt_text` and `response_text`
at 65 536 characters and sets `truncated` true exactly when it clipped; `cost_usd`
stays NULL (D5).

**Tests:** the cap at the 65 536/65 537 boundary for both columns, alone and
together; `truncated` false below; `cost_usd` is NULL, and the row is visible after
the caller commits (no hidden commit inside).

**Commit 3:**

```
feat(kernel): record_call writes the audit row

The one writer of llm_calls: caps prompt and answer at 64 KB with a truncated
flag, never commits (the job handler's commit or the finalizer's own session
owns that), leaves cost_usd NULL until WP2.

User-visible: none.
```

## Task 4 — Knowledge handlers audit their calls

**Files:** `app/capabilities/knowledge/jobs.py`, `app/kernel/llm/__init__.py` ·
Tests: `app/capabilities/knowledge/tests/test_extraction.py`,
`app/capabilities/knowledge/tests/test_consistency.py`.

**Interface (added):** `provider_facts() -> tuple[str, str]` in
`app/kernel/llm/__init__.py` — `(kind, model)` from the same environment
`get_provider()` reads: `("fake", "fake")` for the fake,
`("openai-compatible", NARRE_LLM_MODEL)` for the real entry. Not parsed from
`describe()`.

Both handlers time the provider loop (`latency_ms`, int milliseconds) and, after a
successful parse, `record_call` on the handler's session — it rides the handler's
commit. `task_key` = `"knowledge.extract-entities"` / `"knowledge.check-consistency"`;
`novel_id` = the chapter's novel / the novel; `prompt_text` = the prompt;
`response_text` = the joined answer. A failed job writes no audit row (D3).

**Tests:** after each job succeeds, exactly one row: task_key, novel_id, tokens > 0,
`status="ok"`, `cost_usd` is NULL. After a malformed-answer failure, zero rows and
the job row failed (the existing failure tests gain the zero-rows assertion).

**Commit 4:**

```
feat(knowledge): extraction and consistency audit their LlmCall

Both handlers record their provider call on their own commit: task key, novel,
tokens, latency, prompt and answer (plan §3.4). A failed job writes no row —
the transaction rolls back wholesale and the job's error column already names
the failure (D14; documented asymmetry, plan §3.4). provider_facts() exposes
kind and model without parsing describe().

User-visible: none.
```

## Task 5 — Stream finalizers audit their calls

**Files:** `app/capabilities/writing/router.py`, `app/capabilities/chat/router.py` ·
Tests: `app/capabilities/writing/tests/test_continuation.py`,
`app/capabilities/chat/tests/test_chat.py`; e2e assertions in
`app/capabilities/writing/e2e/test_continuation_e2e.py` and
`app/capabilities/knowledge/e2e/test_extraction_e2e.py`.

Writing reads the chapter's `novel_id` before the response starts (one scalar on the
request's session) and threads it into `_continuation_events`; chat's `novel_id` is
NULL (no novel context until plan §9.2). After the stream — success **or** error
frame — the finalizer opens its own short session (`Session`,
`app/kernel/db/session.py:21`), `record_call`s with `status="ok"`/`"error"` (plus
`str(exception)` as `error`), commits, closes. Plan §3.4's explicit exception: a log
row, not user data. `task_key` = `"writing.continuation"` / `"chat.ask"`;
`latency_ms` measures the provider loop.

**Tests:** component — success row (tokens > 0, `response_text` nonempty, correct
task_key); error path with a raising provider stub (FastAPI dependency override):
the error frame is on the wire AND one `status="error"` row exists. E2E — the
continuation flow and the extraction flow each assert their `llm_calls` row in the
real database (Stack fixture).

**Commit 5:**

```
feat(writing,chat): continuation and chat audit their LlmCall

The stream finalizers write their audit row after the stream ends — success or
error frame — on a short session of their own (plan §3.4's exception: a log
row, not user data). Writing threads the chapter's novel_id in before the
response starts; chat has no novel context until §9.2 and audits NULL.

User-visible: none.
```

## Task 6 — Plan doc sync + full gate

**Files:** `docs/superpowers/plans/2026-10-25-v2-foundation.md` (§1) and this brief
(both staged in this commit).

OLD (line 52):

```
beyond `character|place|thing`; `LlmCall` audit; a context budget; hybrid search;
```

NEW:

```
beyond `character|place|thing`; a context budget; hybrid search;
```

If the OLD block does not match byte-for-byte: stop, report BLOCKED with the line.

Then the full gate, outputs read: `just verify`, then `just test-e2e`. Anything red:
stop, report BLOCKED.

**Commit 6:**

```
docs(plan): LlmCall audit is built

The foundation plan's §1 "Not built yet" list drops the LlmCall audit; this
brief (the WP0-A slice) moves into the repo with it, as WP0's did.

User-visible: none.
```

---

## Verify

1. Every commit: `just check` ran and its output was read.
2. The wire is unchanged: the existing writing/chat capability tests that pin the SSE
   frames pass unmodified (`git diff` shows no edit to them beyond what Tasks name).
3. The audit is real: for each of the four task keys a test asserts a row — tokens,
   status, NULL cost — and for one failure path a zero-rows assertion.
4. `git diff --stat` across the whole branch names only the files this brief names.
5. `just verify` and `just test-e2e` green at close, outputs read.

## Report

Terse, pipe-delimited, English, nothing else:

```
status: DONE|BLOCKED
files: <commits with files, one token each>
ledger: <n>/6 tasks, one token each
verify: <per-commit just check, final just verify + test-e2e counts>
deviations: none | <what and why>
concerns: none | <what>
```

## Dispatch

Launch with `background: true`. Write the returned session id and the base commit to
`.opencode/dispatches/wp0a-llm.progress` in the same turn, with the current task
number and the next verify command. If the provider kills the dispatch: read
`git log --oneline <base>..HEAD` and `git status --porcelain` before deciding
anything; commits or edits present means resume the same session, not reset.
