# WP2b — Context Budget and Continuation Assembly Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One kernel allocator budgets continuation's context into four named slices (60/25/10/5) from the resolved profile's window, and continuation's prompt assembles the chapter tail, the referenced entities, predecessor tails and style hints inside those budgets — WP2b, second half of the WP2 split; closes WP2.

**Architecture:** `app/kernel/context.py` owns the pure allocator (`allocate`, `BudgetImpossibleError`, `CHARS_PER_TOKEN = 3.5`, the two limit defaults); the fake's `Usage` divisor follows the same constant. Writing's service gathers chapter/novel/entities/predecessors through the kernel's scoped repositories over the shared `kernel/contracts` models and renders the prompt with the budgets; the router resolves the provider first, maps `BudgetImpossibleError` to the one-frame error response, and always sends `max_tokens` (the effective reservation), `temperature` only when set. `NARRE_CONTEXT_CHARS` is deleted. Two fix-wave tasks close the open follow-up findings (backend kernel/settings, then settings UI).

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy async, Postgres, `hypothesis` (new, dev group — owner-accepted in the design's Constraints), React + TanStack Router, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-26-wp2b-context-budget-assembly-design.md` (approved by the product owner 2026-10-27, refined through `0f21d58e`..`0df8dbeb`; the plan argues from the spec — executors read both).

**Baseline:** `main` at `287d3e44` (WP2a merged as #296). Branch: `wp2b-context-budget`.

## Global Constraints

- en/de/fr for every user-visible string in the same commit (`i18n/{en,de,fr}.json`, missing key = build error, German du-form). English in code, comments, tests, docs. Prompt scaffolding is English.
- Conventional commits; `feat`/`fix` carry a real `User-visible:` line. Nothing committed before the review is green; `--no-verify` and force push are forbidden.
- No capability imports another capability; shared domain in `app/kernel/`. Every user-owned row via `UserOwned` + `ScopedRepository` (`app/kernel/db/base.py`).
- No side effect in the request path beyond the request's transaction (`LlmCall` is the §3.4 log-row exception).
- `just check` before every commit; `just verify` before the WP closes; `just db-reset` after model changes (no migrations); `just generate` after `capability.yaml`/route changes.
- E2E on real UI + real API + real Postgres; the fake only at the LLM/embeddings boundary; `assert_accessible` on every page visited.
- The fake stays answer-neutral: the continuation prompt carries no `PURPOSE:` and no `SOURCE:` line before or after this change.
- The budgets are an estimate in characters, never a token guarantee; prompt scaffolding (headings, title lines, the instruction) counts inside its slice — nothing rides free.
- No new rule, registry, check script, hook, required field or mandatory document (`NEEDS-APPROVAL` otherwise). Accepted new dev dependency: `hypothesis` only.
- Fix-wave discipline: a fix closes its `docs/superpowers/follow-ups.md` row in the same commit that lands it (`| closed <sha>`).

## Review Focus

1. **Zero-room pair via defaults:** a profile with `context_window = 1024` and `max_output_tokens` unset merges to 1024/1024 (the default fills the gap) — refused by name, error frame, no `llm_calls` row, no ghost. The settings gate cannot see this class. Tests in Tasks 2 and 4.
2. **Tiny window degrades deterministically:** room of 1–3 characters leaves the 25/10/5 % floors at zero — those sections are omitted, never padded; the remainder lands in immediate text. Property test in Task 1, unit pin in Task 2.
3. **Entity slice never overflows:** a body that no longer fits degrades to name + type; a name+type line that does not fit skips silently — the slice stays within budget however many entities match. Test in Task 2.
4. **Environment/fake tier unchanged in shape:** with no profile the defaults 8 192/1 024 apply, `max_tokens=1024` reaches the wire where nothing did, the prompt keeps its sections, and the existing ghost-text E2E stays green unmodified. Tests in Tasks 3 and 4.
5. **German case-insensitivity:** the reference scan folds with `str.casefold()` (ß/umlaut names match their cased occurrences); an alias written in different case in the tail is found. Test in Task 2; E2E proves it on the real stack in Task 4.

---

### Task 1: Kernel allocator `app/kernel/context.py`

**Files:**
- Create: `app/kernel/context.py`
- Test: `app/kernel/tests/test_context.py`
- Modify: `pyproject.toml`, `uv.lock` (`uv add --group dev hypothesis`)

**Interfaces:**
- Produces (Tasks 2, 3 and the fake rely on these exact names):
  - `CHARS_PER_TOKEN: float = 3.5` — the kernel constant (design D8/WP2a D8; not a profile field).
  - `DEFAULT_CONTEXT_WINDOW = 8192`, `DEFAULT_MAX_OUTPUT_TOKENS = 1024`.
  - `@dataclass(frozen=True) class ContextBudgets` with `immediate_text: int`, `referenced_entities: int`, `recent_chapters: int`, `style_hints: int` — character budgets.
  - `class BudgetImpossibleError(ValueError)` — message names the effective pair and the model.
  - `def allocate(*, context_window: int | None = None, max_output_tokens: int | None = None, model: str | None = None) -> ContextBudgets` — pure. Each unset limit falls back to its default **independently** (D7); after defaults, `max_output_tokens >= context_window` raises `BudgetImpossibleError` naming both numbers and the model (D8, never clamped); otherwise `room = floor((context_window − max_output_tokens) × CHARS_PER_TOKEN)`, every slice takes `floor(room × fraction)` for 60/25/10/5, the remainder goes to `immediate_text`, a zero floor stays zero.

- [ ] **Step 1: Write the failing property tests**

`test_context.py` with `hypothesis` (`@given(context_window=st.integers(1, 200_000), max_output=st.integers(1, ...))`): on ordered pairs the four budgets sum exactly to `floor((cw − mot) × 3.5)`; no slice is negative; each non-immediate slice equals its `floor(room × fraction)`; `immediate_text` is at least its floor; equality and greater-than pairs raise `BudgetImpossibleError` and the message contains both numbers and the model string; one unset limit falls back alone (8 192 / 1 024, the other honored); room 1–3 leaves the three small slices at zero with everything in `immediate_text`. Example-based edge pins beside the properties: `(None, None)` → the defaults' budgets; `(2048, None)` → room 3 584 → 2 151/896/358/179 (the E2E's pinned numbers).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv add --group dev hypothesis && just test-file app/kernel/tests/test_context.py`
Expected: FAIL (module does not exist).

- [ ] **Step 3: Implement `app/kernel/context.py`**

Integers throughout (`math.floor`); the fractions live as one module constant (`immediate_text` 0.60, `referenced_entities` 0.25, `recent_chapters` 0.10, `style_hints` 0.05) overridable only in code (D1). The docstring states the estimate-not-guarantee rule verbatim from the design's Goals.

- [ ] **Step 4: Run tests to verify they pass**

Run: `just test-file app/kernel/tests/test_context.py && just check`
Expected: PASS / green.

- [ ] **Step 5: Commit**

```bash
git add app/kernel/context.py app/kernel/tests/test_context.py pyproject.toml uv.lock
git commit -m "feat(kernel): one context allocator with named slice budgets

User-visible: a continuation's context is sized from the resolved provider's
window instead of a fixed 4 000-character tail"
```

### Task 2: Continuation assembly in writing

**Files:**
- Modify: `app/capabilities/writing/prompts.py` (rebuild `continuity_prompt` → budgeted `continuation_prompt`; delete nothing yet — `MAX_CONTEXT_CHARS` dies in Task 3)
- Modify: `app/capabilities/writing/service.py` (`continuation_prompt` gathers entities and predecessors)
- Modify: `app/capabilities/writing/repository.py` (add `EntityRepository`)
- Test: `app/capabilities/writing/tests/test_continuation.py` (rewritten builder tests + service tests over fixture novels)

**Interfaces:**
- Consumes: `allocate`, `ContextBudgets`, `BudgetImpossibleError` from Task 1; `Entity`, `Chapter`, `Novel` from `app.kernel.contracts.models`; `ScopedRepository`.
- Produces (Task 3's router and Task 4's E2E rely on):
  - `class EntityRepository(ScopedRepository[Entity])` with `list_for_novel(novel_id: UUID) -> Sequence[Entity]` (scoped to the user, any order — the scan orders).
  - In `prompts.py`: `def continuation_prompt(*, budgets: ContextBudgets, novel_title: str, chapter_title: str, body: str, entities: Sequence[Entity] = (), predecessors: Sequence[Chapter] = (), genre: str | None = None, blurb: str | None = None) -> str`. Headings, pinned for the tests and the E2E: `Referenced entities:`, `Previous chapters:`, `Style notes:`; the existing instruction sentence and the `Novel:`/`Chapter:`/`Text so far:` lines stay verbatim from today's prompt. No line starts with `PURPOSE:` or `SOURCE:`.
  - In `service.py`: `async def continuation_prompt(self, chapter_id: UUID, *, context_window: int | None, max_output_tokens: int | None, model: str) -> str` — calls `allocate` first (so `BudgetImpossibleError` fires before any gathering), raises `NotFoundError` as today, returns the rendered prompt. The tail is `body[-budgets.immediate_text:]` (the whole body when shorter). The entity scan: for each of the novel's entities, the first index in the tail (case-insensitive via `str.casefold()` on both sides) where the entity's `name` or any of its `aliases` occurs; entities ordered by that index, unmatched entities excluded.

- [ ] **Step 1: Write the failing tests**

Builder tests (pure, no DB): each section renders under its heading and truncates hard at its budget (scaffolding included); a zero-floor slice's section is absent, not empty; an entity whose rendered body exceeds the remaining slice degrades to the `name (type)` line; an entity whose floor does not fit is skipped silently; predecessors render nearest-first with hard-cut tails; genre+blurb render under `Style notes:` truncated to the style budget; the prompt contains no `PURPOSE:`/`SOURCE:` line. Service tests over a fixture novel (real session, the existing `test_continuation.py` fixture pattern): an entity found by alias in different case (casefold) is included, order is first-occurrence; predecessors arrive nearest-first; `continuation_prompt(..., context_window=4096, max_output_tokens=5000, model="vendor/small")` raises `BudgetImpossibleError` naming `4096`, `5000` and the model (the catalog/profile merge class); a tiny window (facts yielding room 3) omits the three small sections.

- [ ] **Step 2: Run tests to verify they fail**

Run: `just test-file app/capabilities/writing/tests/test_continuation.py`
Expected: FAIL (`continuation_prompt` signature/sections do not exist).

- [ ] **Step 3: Implement the builder, the repository, the gathering**

Degradation mechanics (the design's "left to the builder", decided here): an entity entry is `### {name} ({type})\n{content}`; when it exceeds the remaining entities slice it degrades to the `{name} ({type})` line; when that line no longer fits the entity is skipped — the slice never overflows and the skip is silent. A predecessor entry is `### {title}\n` plus its own tail hard-cut to the remaining recent-chapters budget. The style section is `Genre: {genre}` / `Blurb: {blurb}` lines truncated to the style budget, omitted when both are `None` or the floor is zero. The `Novel:`/`Chapter:` header, `Text so far:` tail and the instruction all count against the immediate-text budget.

- [ ] **Step 4: Run tests to verify they pass**

Run: `just test-file app/capabilities/writing/tests/test_continuation.py && just check`
Expected: PASS / green (the old `continuity_prompt` tests are replaced by these in the same commit).

- [ ] **Step 5: Commit**

```bash
git add app/capabilities/writing/prompts.py app/capabilities/writing/service.py \
  app/capabilities/writing/repository.py app/capabilities/writing/tests/test_continuation.py
git commit -m "feat(writing): continuation assembles budgeted entity, chapter and style slices

User-visible: a continuation's context carries the entities the chapter tail
names, the previous chapters and the novel's genre and blurb, within the
provider's window"
```

### Task 3: Wiring — facts to the wire, `NARRE_CONTEXT_CHARS` deleted

**Files:**
- Modify: `app/capabilities/writing/router.py` (resolution first, `BudgetImpossibleError` → error frame, `CompletionRequest` carries the facts)
- Modify: `app/capabilities/writing/prompts.py` (delete `MAX_CONTEXT_CHARS` and the `environ` import; docstring rewrite)
- Modify: `app/kernel/llm/fake.py` (Usage divisor follows `CHARS_PER_TOKEN`)
- Modify: `app/kernel/tests/test_fake_provider.py` (the pinning test moves with the divisor)
- Modify: `app/capabilities/writing/tests/test_review_round.py` and the router's tests where they assert the old call order/prompt path

**Interfaces:**
- Consumes: Task 1 (`DEFAULT_MAX_OUTPUT_TOKENS`, `CHARS_PER_TOKEN`); Task 2 (`service.continuation_prompt` facts signature); `ResolvedProvider.context_window/max_output_tokens/temperature` (landed WP2a).
- Produces: the shipped continuation request path. `continue_chapter` order: (1) `resolve_provider(...)` — `KeyUnavailableError` → the one-frame error response, as today; (2) `service.continuation_prompt(chapter_id, context_window=resolved.context_window, max_output_tokens=resolved.max_output_tokens, model=resolved.model)` — `NotFoundError` → 404, `BudgetImpossibleError` → logged and mapped to the same one-frame error response (the `KeyUnavailableError` precedent; no call ran, so no audit row); (3) the `novel_id` scalar, session close, stream — all as today. The request is `CompletionRequest(messages=(Message(role="user", content=prompt),), temperature=resolved.temperature, max_tokens=resolved.max_output_tokens if resolved.max_output_tokens is not None else DEFAULT_MAX_OUTPUT_TOKENS)` — `max_tokens` always on the wire (design: the reservation is a wire cap), `temperature` only when the profile sets it. In `fake.py`, both `Usage` sites become `int(len(text) / CHARS_PER_TOKEN)` (kernel-internal import; the `// 4` divisor is gone).

- [ ] **Step 1: Write the failing tests**

Router tests: a monkeypatched `allocate`-impossible pair yields the SSE error frame and writes no `llm_calls` row; the built `CompletionRequest` pins `max_tokens=1024` when the resolved facts carry `None` and the profile's value when set, `temperature` present only when set (assert on what the provider receives — the existing monkeypatched-provider pattern in `test_continuation.py`/`test_review_round.py`). `test_fake_provider.py`: `Usage == int(len/3.5)` on both shapes. A sweep test asserting `rg -n NARRE_CONTEXT_CHARS app web` is clean is not a test — it is the done criterion, run in Task 4.

- [ ] **Step 2: Run tests to verify they fail**

Run: `just test-file app/capabilities/writing/tests/test_continuation.py && just test-file app/kernel/tests/test_fake_provider.py`
Expected: FAIL (new wiring absent).

- [ ] **Step 3: Implement the router order, the request facts, the fake divisor; delete `NARRE_CONTEXT_CHARS`**

- [ ] **Step 4: Run tests; run the full backend suite (environment-tier regression)**

Run: `just test && just check`
Expected: PASS / green — every capability's suite unmodified-green except the files this task names.

- [ ] **Step 5: Commit**

```bash
git add app/capabilities/writing/router.py app/capabilities/writing/prompts.py \
  app/kernel/llm/fake.py app/kernel/tests/test_fake_provider.py \
  app/capabilities/writing/tests
git commit -m "feat(writing): the budget reaches the wire — max_tokens always, NARRE_CONTEXT_CHARS gone

User-visible: continuations respect the provider's output reservation on
every call, and the context tail is no longer capped by a fixed 4 000 characters"
```

### Task 4: E2E on the real stack + Fahrplan overwrite

**Files:**
- Create: `app/capabilities/writing/e2e/test_context_budget_e2e.py`
- Modify: `docs/superpowers/plans/2026-10-25-v2-foundation.md` (§5.4 as-built, §5.9 closing note)
- Test: the new E2E file

**Interfaces:**
- Consumes: Tasks 1–3; the settings UI (profile form with `Kontextfenster (Tokens)` / `Maximale Ausgabe (Tokens)` fields, task assignment — WP2a); the knowledge UI (extraction → accept → entity editor with alias field — WP1); `_continuation_audit`'s SQL pattern extended to select `prompt_text` and `profile_id`.

- [ ] **Step 1: Write the failing E2E**

Three tests, one unique novel title each, real stack:
1. **Slices land in the prompt.** Create a novel with genre and blurb through the create form; chapter 1 with text naming `Mira`; knowledge surface: run extraction, accept the `Mira` suggestion, give the entity the alias `die Wanderin` through the entity editor; chapter 2 whose typed tail contains `DIE WANDERIN` (different case) plus more prose; run `Weiterschreiben` (default tier, no profile); assert on `llm_calls.prompt_text`: the entity's name and the body the entity editor shows, a chapter-1 tail excerpt, and the genre string are present; ghost still streams; `assert_accessible`.
2. **A small window measurably shrinks the prompt.** Create a fake profile through the settings form with `Kontextfenster (Tokens)` = 2048 (max output empty); assign `writing.continuation` to it (the WP2a E2E's selectors); run a continuation on the same novel; on `prompt_text` assert each section between its headings stays within its budget — immediate ≤ 2 151, entities ≤ 896, previous ≤ 358, style ≤ 179 — and the whole prompt is shorter than test 1's. Ghost still streams; `assert_accessible`.
3. **A zero-room pair is refused.** A fake profile with `Kontextfenster (Tokens)` = 1024 (max output empty → default 1024): assign continuation to it, run `Weiterschreiben` on a fresh novel — no ghost appears, the editor text is untouched, and `llm_calls` holds **no row** for that novel.

- [ ] **Step 2: Run to verify failure**

Run: `just test-file app/capabilities/writing/e2e/test_context_budget_e2e.py`
Expected: FAIL.

- [ ] **Step 3: Make it pass (no product change expected — failures here are Task 1–3 defects, fixed at their source)**

- [ ] **Step 4: Docs overwrite, the sweep, the full gate**

Fahrplan §5.4 rewritten as-built: the allocator is `app/kernel/context.py` with `chars_per_token` a kernel constant (3.5), `NARRE_CONTEXT_CHARS` deleted, check/extraction keep WP0-C's caps (D4), the zero-room refusal and the wire cap recorded. §5.9 gains the closing sentence: WP2b landed, WP2 closed. Run `rg -n NARRE_CONTEXT_CHARS app web` → no matches (design and history documents may name it). Run: `just verify`.
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add app/capabilities/writing/e2e/test_context_budget_e2e.py docs/superpowers/plans/2026-10-25-v2-foundation.md
git commit -m "test(writing): E2E pins the budgeted continuation prompt on the audited row

User-visible: none — the release-note surface is docs/superpowers/plans/2026-10-25-v2-foundation.md §5.4"
```

### Task 5: Backend fix wave (F-03–F-08, F-10, F-11, F-18, F-19)

**Files:** (one commit per lettered fix; each closes its follow-ups row in the same commit — locate every site by the semantic names here, the row's line numbers have drifted)
- Modify: `app/kernel/llm/catalog.py` (+ its tests) — a, c
- Modify: `app/kernel/llm/profiles.py` (+ tests) — b
- Modify: `app/kernel/llm/streaming.py`, `app/kernel/llm/resolution.py`, `app/kernel/llm/audit.py`, `app/capabilities/knowledge/jobs.py`, `app/capabilities/writing/router.py`, `app/capabilities/chat/router.py` — c
- Modify: `app/kernel/llm/openai_chat.py` — d
- Modify: `app/capabilities/settings/profiles_service.py` — e, f
- Modify: `app/kernel/llm/models.py` (+ tests; `just db-reset`) — f
- Modify: `app/kernel/testing/vendor.py` (+ a kernel test) — g
- Modify: `app/capabilities/knowledge/prompts.py` (+ its prompt tests) — h
- Modify: `docs/superpowers/follow-ups.md` — every lettered commit

**Interfaces:**
- Produces (Task 6 and WP4 rely on):
  - (c) `ResolvedProvider.info: ModelInfo | None = None` — the one merge of catalog and profile facts, computed in `resolution` (today's `_merged`); `audit.audited_stream` and both `jobs.py` call sites price from `resolved.info` instead of recomputing `effective_info`; `async def error_events() -> AsyncGenerator[str]` in `app/kernel/llm/streaming.py` (the `event: error` frame today duplicated in the writing and chat routers — both import it, local copies deleted).
  - (a) `class CatalogError(RuntimeError)` raised by `load_catalog` on a malformed snapshot, naming the file; `load_catalog() -> MappingProxyType` view over a module-cached dict with the normalized and prefix indexes built once at load.
  - (f) `ProviderProfile` gains a partial unique index: one `is_default` row per `user_id` (`Index(..., unique=True, postgresql_where=...)`); `profiles_service` sets a new default by flipping the old one to `False` (flush) before raising the new one, and maps the concurrent-create `IntegrityError` narrowly to a named 409.
  - (g) `ChatVendor` gains an optional per-request delay mode for the timeout test.

- [ ] **Step 1: (a) F-03 + F-05 + F-07 — catalog hardening, red first**

Tests: a damaged `models.json` (tmp path swapped in) raises `CatalogError` naming the file at load, not `KeyError` at first lookup; `next(load_catalog().values())["…"] = …` style mutation raises `TypeError` (read-only view); two unknown-id normalized lookups succeed with `sorted` monkeypatched to raise — no per-lookup sorting. Implement: load-once module cache, prebuilt normalized + prefix indexes, `MappingProxyType` return, shape validation. `just check` → commit (closes F-03, F-05, F-07).

- [ ] **Step 2: (b) F-04 — `for_prefix` wildcard escape**

Test: an assignment `axe.continue` stored; `for_prefix("a%b")` returns `None` (today the unescaped LIKE matches). Implement: `.startswith(f"{prefix}.", autoescape=True)`. `just check` → commit (closes F-04).

- [ ] **Step 3: (c) F-06 — one error frame, one merge**

Tests: `resolved.info` equals today's `effective_info` merge for a profile-with-override and a catalog-only model; the audit row's cost is unchanged for both (existing audit/jobs tests keep their numbers, now reading `resolved.info`); writing and chat stream their existing error frames through the shared helper. Implement the interfaces above. `just check` → commit (closes F-06).

- [ ] **Step 4: (d) F-08 + (e) F-10 — comment and docstring truths**

`openai_chat.py`'s usage comment states what the code does (both events yield; precedence is not taken); `profiles_service`'s create docstring documents the keyring-before-commit ordering and the orphaned-secret consequence. No behavior change. `just check` → commit (closes F-08, F-10).

- [ ] **Step 5: (f) F-11 — one default per user, enforced by the database**

Tests: two concurrent creates (two sessions, `asyncio.gather`) end with exactly one default and the loser gets the named 409; `set_default`'s flip keeps a single default through the swap. Implement the index + ordering + narrow `IntegrityError` mapping (nothing broad). `just db-reset`; `just test-file app/capabilities/settings/tests/test_profiles.py && just check` → commit (closes F-11).

- [ ] **Step 6: (g) F-18 — a stored `request_timeout` reaches the socket**

Test: `OpenAIChatProvider(request_timeout=0.2, base_url=<delayed ChatVendor>, ...)` against a 1 s-delayed completions route raises within a loose 1 s bound (wall-clock measured). Implement the vendor delay mode. `just check` → commit (closes F-18).

- [ ] **Step 7: (h) F-19 — extraction prompt says the full vocabulary**

The opening no longer narrows to "the characters, the places and the things" (the eight-type list already follows in the same sentence, interpolated from `ENTITY_TYPES`); the relation examples come from the Fahrplan §4.2 vocabulary (`related_to`, `member_of`, `located_in`) — `lives_in` is not in it. Adjust the prompt tests; the fake and knowledge E2E are unaffected (they read markers, not prose). `just test-file app/capabilities/knowledge && just check` → commit (closes F-19).

### Task 6: Settings UI fix wave (F-12–F-17, F-45)

**Files:**
- Modify: `app/capabilities/settings/router.py`, `app/capabilities/settings/profiles_service.py` (the tasks endpoint), `app/capabilities/settings/web/ProvidersPanel.tsx`, `app/capabilities/settings/web/SettingsPage.tsx`, `app/capabilities/settings/capability.yaml`, `i18n/{en,de,fr}.json`
- Modify (via `just generate`, committed): `web/lib/generated/{routes,capabilities}.ts`, `app/generated/capabilities.py`, `docs/user/INDEX.md`
- Test: `app/capabilities/settings/tests/test_tasks.py`; `app/capabilities/settings/web/ProvidersPanel.test.tsx`; extend `app/capabilities/settings/e2e/test_profiles_e2e.py`
- Modify: `docs/superpowers/follow-ups.md` (rows closed per fix)

**Interfaces:**
- Consumes: `KNOWN_TASK_KEYS` and `resolve_provider` (kernel, read-only); F-06's merged facts.
- Produces: `GET /api/settings/tasks` → `list[TaskEffectiveRead]`, one row per known task key: `task_key`, `profile_id: UUID | None`, `profile_name: str | None`, `kind: str` — the effective serving tier via `resolve_provider` per key (reads only; prefix inheritance visible). The panel's task list renders from this response (no mirrored key list in the frontend); a task shows its effective provider (`via {profile_name}`, or the kind when no profile serves), replacing the bare "Automatic".

- [ ] **Step 1: Write the failing tests**

`test_tasks.py`: every known key resolves; an exact assignment names that profile; a task without one inherits the segment prefix assignment or the default, and the environment tier reports its kind with `profile_id = null`. `ProvidersPanel.test.tsx`: a rejected fetch on test/assign/default renders the failure (the panel's existing error pattern), not silence. E2E: after assigning `writing.continuation` to the alt profile, the task list shows that profile as effective; `/settings` still `assert_accessible`.

- [ ] **Step 2: Run to verify failure**

Run: `just test-file app/capabilities/settings/tests/test_tasks.py && pnpm --dir web test && just test-file app/capabilities/settings/e2e/test_profiles_e2e.py`
Expected: FAIL.

- [ ] **Step 3: Implement, then the small fixes in the same task**

The endpoint and panel rework (closes F-13, F-45). Then, each its own commit: F-12 failure surfacing (covered by the tests above); F-14 `capability.yaml` title key → `settings.heading` with the key added in en/de/fr, `just generate` re-renders `docs/user/INDEX.md`; F-15 the settings back control gets its own key `settings.back` ("Back"/"Zurück"/"Retour"), `nav.back` untouched; F-16 the duplicated E2E comment line deleted; F-17 the mount effect's cancelled guard in `SettingsPage.tsx`.

- [ ] **Step 4: Run tests, the settings E2E, `just check`**

Run: `just test-file app/capabilities/settings && pnpm --dir web test && just test-file app/capabilities/settings/e2e/test_profiles_e2e.py && just check`
Expected: PASS / green.

- [ ] **Step 5: Commits** — one per fix letter as named in Step 3, each closing its follow-ups row.

### Task 7: Close-out

- [ ] **Step 1: Full gate** — `just verify` green; output read.
- [ ] **Step 2: Ledger reconciliation** — every row this branch closes (F-03–F-08, F-10–F-19, F-45) carries `closed <sha>`; the still-open rows (F-20+ WP5 batch, parked rows) are untouched and still reconcile with the tree; any finding the final review adds is appended per the house rule — nothing dropped for being minor.
- [ ] **Step 3: Final whole-branch review** — a fresh reviewer on `opencode-go/deepseek-v4.1-flash` (not the implementer's model), verdict with fixes; then the fix wave; then the finishing menu to the product owner (merge as a merge commit, branch kept as reference — the WP2a pattern).

## Carry-forward (binding)

- The WP1 findings with later triggers (F-20–F-28: WP5 UI-coherence/a11y batch; F-26 fires at WP3; parked F-35–F-44) are **constraints, not work**: this branch does not touch their surfaces beyond what Tasks 5–6 name, and does not worsen them.
- WP2a's deferred minors are folded here as Tasks 5–6 — the "WP2b-adjacent batch" triage (owner, 2026-10-27, this session's plan decision).
- D5 honored: every symbol named above (`ResolvedProvider` facts, `allocate`, the settings form fields) is read from the merged tree at `287d3e44`, not from a design doc.

## Deviations from the design doc

None at plan time. The build session records any here, with the root cause, as they occur.
