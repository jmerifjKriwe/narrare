# WP4 — Prompt Overrides Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Users override the four bundled task prompts (Jinja, novel-scoped or global), validated at save time, proven via `LlmCall.prompt_text`, with the allocator's never-overflow guarantee intact.

**Architecture:** A kernel registry (`app/kernel/prompts/`) owns the Jinja environment, the `PromptTemplate` rows and effective-chain resolution; each capability's `prompts.py` keeps its packers (what enters) and registers its bundled template (how it reads) at import; a new `prompts` capability is the thin HTTP + UI surface. `writing.continuation` docks via pre-packed section variables and a two-pass frame measurement; a template that cannot be honored is refused by name, never cut or swapped.

**Tech Stack:** Python 3.14 · FastAPI · SQLAlchemy async · Jinja2 (`SandboxedEnvironment`) · React + TanStack Router · vitest · Playwright E2E on the kernel testing stack.

**Spec:** `docs/superpowers/specs/2026-10-29-wp4-prompt-overrides-design.md` (until the build session moves it there: `~/.opencode/plan/2026-10-29-wp4-prompt-overrides-design.md`). Fahrplan §7: `docs/superpowers/plans/2026-10-25-v2-foundation.md`. Both travel with this plan; executors read both.

## Global Constraints

- Jinja `SandboxedEnvironment` + `StrictUndefined`, `autoescape=False` — nothing else.
- The overridable key set is closed: `writing.continuation`, `chat.ask`, `knowledge.extract-entities`, `knowledge.check-consistency`. Keys contain dots and are ordinary path segments.
- No capability imports another; the `prompts` capability reaches bundled content only through `app.kernel.prompts`.
- Machine markers stay kernel-owned: `PURPOSE_PREFIX` / `SOURCE_PREFIX` from `app.kernel.llm`, fed as variables (`purpose_line`, `sources`); the fake provider (`app/kernel/llm/fake.py`) parses them and is the default tier.
- `user_id` on every user-owned row; side effects only inside the request's transaction.
- English in code, comments and docs; en/de/fr for every user-visible string (root `i18n/{en,de,fr}.json`, `t()` from `@shell/lib/i18n`).
- Schema by models + registration in `app/kernel/db/init.py` (no Alembic); uniqueness via partial index where NULLs live (the `uq_provider_profiles_one_default_per_user` pattern at `app/kernel/llm/models.py:60`).
- Dependency change only where named: `uv add jinja2` (Task 1). No new frontend dependency.
- Commit discipline: conventional commits; `feat`/`fix` carry a real `User-visible:` line (given in each task); `just check` green before every commit; `just verify` + the capability E2E close the plan. `--no-verify` forbidden.
- Findings that survive a task review become GitHub issues (label `follow-up`) before the branch merges — not rows in a file.

## Review Focus

1. **Bundled byte-drift during the rewrite** — the bundled templates must render byte-identically to today's functions. Pinned by golden tests in Tasks 4, 5, 6 and the smoke goldens in Task 9; the existing prompt/budget tests must pass unchanged throughout.
2. **Save-valid but runtime-broken overrides** (an `StrictUndefined` gap in an untaken sample branch; an include broken by a later save) — must surface as a named `PromptRenderError` mapped to the existing error paths, never a silent bundled swap. Pinned in Tasks 3 and 4.
3. **Wrong-scope writes and deletes** — `PUT` with `novel_id` must write the novel row, `DELETE` must remove only the named scope's row, and `novel_id` on `chat.ask` is 422. Pinned in Task 7.
4. **Cross-user leakage** — another user's override must be invisible (scoped repository). Pinned in Task 3.
5. **Marker loss breaking the fake floor tier** — an override dropping `PURPOSE:`/`SOURCE:` is 422 at save (contract), and an accepted override still parses in the fake. Pinned in Tasks 5, 6, 7.

---

### Task 1: Kernel prompt registry and the sandboxed render

**Files:**
- Create: `app/kernel/prompts/__init__.py`, `app/kernel/prompts/registry.py`, `app/kernel/prompts/render.py`
- Test: `app/kernel/tests/test_prompts_registry.py`
- Modify: `pyproject.toml`, `uv.lock` (`uv add jinja2`)

**Interfaces:**
- Produces: `PromptRenderError(RuntimeError)` with `reason: str` — one of `"syntax"`, `"undefined-variable"`, `"include-depth"`, `"include-cycle"`, `"include-missing"` (a `KeyError` from the `include` callback), `"forbidden"` (a sandbox `SecurityError`), `"runtime"` (any other template-time exception), `"budget"` — and `detail: str`; `PromptSpec` (dataclass: `key: str`, `template: str`, `sample_variables: Callable[[], dict[str, object]]`, `contract: Callable[[str], bool] | None`, `novel_scopable: bool`); `PromptRegistry` with `register(key, *, template, sample_variables, contract=None, novel_scopable=True)`, `spec(key) -> PromptSpec`, `keys() -> tuple[str, ...]` (entry order); `get_registry() -> PromptRegistry` (idempotent; discovers `app/capabilities/*/prompts.py` by convention and imports each — folders without one are skipped); `render_source(source: str, variables: Mapping[str, object], *, include: Callable[[str], str]) -> str`.

- [ ] **Step 1: Write the failing tests** — register a toy spec; `render_source` with all variables returns the rendered text; each failure mode raises `PromptRenderError` with its exact reason: unknown `{{ var }}` → `undefined-variable`; bad `{% %}` → `syntax`; an `include` callback that recurses `a → b → a` → `include-cycle`; a chain deeper than 5 → `include-depth`. A test that `get_registry()` is idempotent and today (no capability `prompts.py` registers yet) yields an empty registry without raising.
- [ ] **Step 2: Run red** — `just test-file app/kernel/tests/test_prompts_registry.py`; expect import errors.
- [ ] **Step 3: Implement** — `uv add jinja2` first. Environment per render: `SandboxedEnvironment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)`; a loader whose `get_source` calls the `include` callback; depth and cycle tracked on a render-time stack (raise before rendering deeper) that template text cannot reach — the bracket wraps the compiled template's render, never source text or environment globals. `render_source` catches Jinja's exceptions and re-raises as `PromptRenderError` with the mapped reason and `str(e)` as detail. Docstrings in the house voice (module docstring says: the registry is the one prompt authority beside the allocator).
- [ ] **Step 4: Run green** — `just test-file app/kernel/tests/test_prompts_registry.py`; then `just check`.
- [ ] **Step 5: Commit** — `feat(kernel): a sandboxed prompt registry with named render refusals`

  ```
  User-visible: prompts become overridable templates — groundwork, no surface yet.
  ```

### Task 2: `PromptTemplate` rows and the scoped repository

**Files:**
- Create: `app/kernel/prompts/models.py`
- Modify: `app/kernel/db/init.py` (register the models module beside the llm import)
- Test: `app/kernel/tests/test_prompts_repository.py`

**Interfaces:**
- Consumes: `UserOwned`, `ScopedRepository` (`app/kernel/db/base.py`).
- Produces: `PromptTemplate(UserOwned)` — `__tablename__ = "prompt_templates"`; `id: UUID` (pk, `default=uuid4`), `novel_id: UUID | None` (FK `novels.id`, `ondelete="CASCADE"`, indexed), `prompt_key: str` (`String(80)`), `content: str` (`Text`), `created_at`/`updated_at` mirroring `ProviderProfile`'s UTC lambdas; `__table_args__` = `UniqueConstraint("user_id", "novel_id", "prompt_key", name="uq_prompt_templates_novel_scope")` + `Index("uq_prompt_templates_one_global_per_key", "user_id", "prompt_key", unique=True, postgresql_where=text("novel_id IS NULL"))`. `PromptTemplateRepository(ScopedRepository[PromptTemplate])` with `async effective(prompt_key: str, novel_id: UUID | None) -> PromptTemplate | None` (novel row first, then global), `async save(prompt_key: str, content: str, novel_id: UUID | None) -> PromptTemplate` (upsert on the scope's row), `async delete(prompt_key: str, novel_id: UUID | None) -> bool`.

- [ ] **Step 1: Write the failing tests** (mirror `test_llm_profiles.py`'s DB fixtures): two global rows for one key collide (`IntegrityError`); global + novel rows coexist; `effective` prefers the novel row, falls back to the global row, then `None`; `save` upserts in place (one row per scope, `updated_at` moves); `delete` removes only the named scope and returns `False` for an absent one.
- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** the model and repository; add the registration import to `app/kernel/db/init.py` exactly the way `llm_models` registers (`from app.kernel.prompts import models as prompts_models` … `del prompts_models`).
- [ ] **Step 4: Run green** — repository tests + `just check` (pyright sees the new module).
- [ ] **Step 5: Commit** — `feat(kernel): per-user prompt template rows, one override per scope`

  ```
  User-visible: overrides persist per user and scope; the surface comes later.
  ```

### Task 3: Effective-chain resolution — `render`

**Files:**
- Modify: `app/kernel/prompts/__init__.py` (add `render`), `app/kernel/prompts/render.py`
- Test: `app/kernel/tests/test_prompts_render.py`

**Interfaces:**
- Consumes: Task 1's `render_source`, Task 2's `PromptTemplateRepository`.
- Produces: `async render(session: AsyncSession, user_id: UUID, key: str, variables: Mapping[str, object], *, novel_id: UUID | None = None) -> str` — source = `effective()` row's `content` if present, else `registry.spec(key).template`; the `include` callback resolves another key through the same chain (same session/user/novel scope). Unknown key → `KeyError` (caller's 404); render failures re-raise `PromptRenderError`.

- [ ] **Step 1: Write the failing tests** — bundled renders when no row exists; a global row overrides bundled; a novel row overrides global; another user's rows are invisible (scoped); `{% include 'chat.ask' %}` inside a stored override resolves the *effective* `chat.ask` (override, not bundled); an include of an unknown key raises `PromptRenderError` (`include-depth`/`syntax` reasons flow through unchanged).
- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement.** One session read per render (the row lookup), includes resolve recursively through the same helper.
- [ ] **Step 4: Run green** + `just check`.
- [ ] **Step 5: Commit** — `feat(kernel): prompt resolution walks novel, then global, then bundled`

  ```
  User-visible: an override takes effect where its scope matches; includes follow.
  ```

### Task 4: `writing.continuation` docks — packers stay, template arranges

**Files:**
- Modify: `app/capabilities/writing/prompts.py`, `app/capabilities/writing/service.py` (`continuation_prompt`, ~:129-181), `app/capabilities/writing/router.py` (~:382)
- Test: `app/capabilities/writing/tests/test_prompts_writing.py` (new); existing `test_continuation.py` must pass unchanged

**Interfaces:**
- Consumes: `render` (Task 3), `ContextBudgets` (`app/kernel/context.py`).
- Produces: in `prompts.py` — `CONTINUATION_TEMPLATE: str` (Jinja over `novel_title`, `chapter_title`, `tail`, `entities_section`, `predecessors_section`, `style_section`; absent sections render nothing); `sample_variables() -> dict`; `chat_contract`-style none (no contract); `async render_continuation(session, user_id, novel_id, *, budgets: ContextBudgets, novel_title: str, chapter_title: str, body: str, entities: Sequence[Entity], predecessors: Sequence[Chapter], genre: str | None, blurb: str | None) -> str`; module-level `registry.register("writing.continuation", template=CONTINUATION_TEMPLATE, sample_variables=sample_variables, novel_scopable=True)`. `_entities_block`, `_predecessors_block`, `_style_block`, the headings and `_SECTION_OVERHEAD` stay byte-identical.

- [ ] **Step 1: Write the tests — the golden first.** (a) Golden: write a test asserting today's `continuation_prompt` output for a fixed rich input (entities present, predecessors present, genre+blurb) equals a pinned literal, run it **green against the current function** — that is the regression pin the rewrite must hold. Then the red tests: (b) a novel-scoped override reorders sections; `render_continuation` returns the override's arrangement. (c) Budget invariant: for a huge frame template (long instruction), the result length is `<= immediate_text + referenced_entities + recent_chapters + style_hints`, and a template whose glue grows in `{% else %}` when the tail shrinks raises `PromptRenderError` with reason `"budget"` — not a truncated prompt. (d) Two-pass honesty: an override with a 500-char instruction and a full chapter still carries a tail; the tail shrinks by the frame's measured length.
- [ ] **Step 2: Run** — (a) green, (b)–(d) red.
- [ ] **Step 3: Implement.** The flow: pack the three sections with the existing packers (each within its slice); candidate tail `body[-budgets.immediate_text:]`; pass 1 renders via `render` with the full candidate; frame = `len(pass1) − len(candidate_tail) − len(each section string as passed)` — the titles are part of the frame, exactly as today's header math charges them; tail room `= budgets.immediate_text − frame`; pass 2 with `body[-room:]` (empty when `room <= 0`); if the frame grew (else-branches) one more pass; if the frame still grows after the bounded passes, raise `PromptRenderError("budget", …)` — sections are never cut. A stable frame that exceeds a degenerate window ships with an empty tail, exactly as today's scaffold floor does; only the growth pathology refuses. Service: `continuation_prompt` gathers as today and calls `render_continuation` with the chapter's `novel_id`. Router: `except PromptRenderError` beside the `BudgetImpossibleError` branch — log + the one error frame, no audit row.
- [ ] **Step 4: Run green** — new tests, existing `test_continuation.py` unchanged, `just check`.
- [ ] **Step 5: Commit** — `feat(writing): the continuation prompt renders through the registry, budgets held`

  ```
  User-visible: a novel-scoped prompt override steers continuations; impossible frames are refused by name.
  ```

### Task 5: `chat.ask` docks — sources stay marked

**Files:**
- Modify: `app/capabilities/chat/prompts.py`, `app/capabilities/chat/service.py` (`prepare`, :18-26), `app/capabilities/chat/router.py` (error path)
- Test: `app/capabilities/chat/tests/test_prompts_chat.py`

**Interfaces:**
- Consumes: `render`, `SOURCE_PREFIX` (`app.kernel.llm`).
- Produces: `CHAT_TEMPLATE: str` (Jinja over `question`, `sources`); `sources_block(passages: Sequence[Passage]) -> str` — `"\n".join(f"{SOURCE_PREFIX}{p.text}")`, byte-identical to today's join; `sample_variables()` with one passage; `def chat_contract(rendered: str) -> bool: return SOURCE_PREFIX in rendered`; register `"chat.ask"`, `novel_scopable=False`.

- [ ] **Step 1: Write the tests — golden first.** Golden byte-identity: pin today's `chat_prompt` output for a fixed question + two passages and run it **green against the current function** before the rewrite. Red: an override that keeps `{{ sources }}` renders its own frame and the fake still quotes the source line (drive the fake provider with the rendered prompt, assert its answer cites the passage); `chat_contract` rejects a render without a `SOURCE_PREFIX` line.
- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement.** `prepare` builds `sources_block` and calls `render(session, user_id, "chat.ask", {...})` (no novel scope). Router maps `PromptRenderError` to the error path a dead provider takes today.
- [ ] **Step 4: Run green** + `just check`.
- [ ] **Step 5: Commit** — `feat(chat): the chat prompt renders through the registry, sources stay marked`

  ```
  User-visible: chat answers can be re-voiced; the retrieval marker cannot be lost.
  ```

### Task 6: knowledge prompts dock — purposes stay marked

**Files:**
- Modify: `app/capabilities/knowledge/prompts.py`, `app/capabilities/knowledge/jobs.py` (:318 extraction, :478 consistency)
- Test: `app/capabilities/knowledge/tests/test_prompts_knowledge.py`

**Interfaces:**
- Consumes: `render`, `PURPOSE_PREFIX`, `SOURCE_PREFIX`, `BODY_LIMIT` (unchanged, cuts stay at the call sites).
- Produces: `EXTRACTION_TEMPLATE` (over `purpose_line`, `types`, `chapter_title`, `sources` — the body behind the `SOURCE_PREFIX`, cut by the caller), `CONSISTENCY_TEMPLATE` (over `purpose_line`, `grounding`, `chapters` — each chapter title + `SOURCE_PREFIX`-marked body, as today); `sample_variables_extraction()`, `sample_variables_consistency()`; `def purpose_contract_factory(purpose: str)` returning a **content-bound** contract — the rendered sample must contain the sample's `purpose_line` AND the sample's marked payload (the marked chapter/body text), not merely the prefixes; register both keys, both novel-scopable. The `Parsed*` NamedTuples stay untouched.

- [ ] **Step 1: Write the tests — goldens first.** Pin both of today's outputs (fixed inputs: two entities, two chapters) and run them **green against the current functions** before the rewrite. Red: an override re-voicing the instruction still answers through the fake (extraction derives entities from the marked chapter); a purpose-less render fails the contract.
- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement.** Jobs build variables as today (`body[:BODY_LIMIT]` behind the marker) and call `render`; `PromptRenderError` propagates the way `MalformedAnswerError` does — a failed, named job row.
- [ ] **Step 4: Run green** + `just check`.
- [ ] **Step 5: Commit** — `feat(knowledge): extraction and consistency render through the registry`

  ```
  User-visible: knowledge prompts can be re-voiced per novel or globally; answer shapes stay declared.
  ```

### Task 7: the `prompts` capability — API with save-time validation

**Files:**
- Create: `app/capabilities/prompts/__init__.py`, `router.py`, `service.py`, `schemas.py`, `capability.yaml`, `tests/__init__.py`, `tests/test_prompts_api.py`
- Modify: generated output after `just generate` (`app/generated/capabilities.py`, `docs/user/INDEX.md`)

**Interfaces:**
- Consumes: `get_registry`, `render_source`, `PromptRenderError`, `PromptTemplateRepository`; house deps `SessionDep`, `UserDep` (see `app/capabilities/settings/router.py:44-63`).
- Produces: `APIRouter(prefix="/api/prompts", tags=["prompts"])` — `GET ""` (query `novel_id: UUID | None`) → `list[Pydantic PromptSummary]` (`key`, `novel_scopable`, `override_global`, `override_novel`, `bundled_summary` — first 120 chars of the bundled render with sample variables); `GET "/{key}"` → `PromptDetail` (`bundled_content`, `variables: list[{name, example}]` from the sample factory, `override: {scope, content} | None`, `effective_content`); `PUT "/{key}"` body `PromptSave {content: str, novel_id: UUID | None = None}`; `DELETE "/{key}"` (query `novel_id`) → house no-content style; `GET "/{key}/diff"` → `PromptDiff {bundled_content, override_content | None}`. `capability.yaml`: `id: prompts`, `title: prompts.heading`, `path: /prompts`, `needs: []`, `nav: true`.

- [ ] **Step 1: Write the failing tests** (API level, mirror the settings API tests' fixtures): PUT a valid override → 200, row exists, `GET /{key}` shows it; PUT with `novel_id` writes the novel row (`override_novel` true, global untouched); PUT an unknown-variable template → 422, detail names `undefined-variable` and the variable; PUT a syntax error → 422 `syntax`; PUT a marker-dropping `chat.ask` override → 422 naming the contract; PUT `novel_id` on `chat.ask` → 422 naming the key; PUT an include cycle → 422 `include-cycle`; unknown key → 404; DELETE global leaves a novel row in place; GET list shows all four keys with correct `novel_scopable`.
- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement.** Service `validate(key, content, novel_id)`: 404 unknown key; 422 `novel-scope` when `novel_id` on a `novel_scopable=False` key; render the sample through `render_source` with includes resolving bundled-or-this-content at sample scope; run the contract; re-raise `PromptRenderError` as 422 `{reason, detail}`. Then `save`. Add `capability.yaml`, run `just generate`, commit its output in the same commit.
- [ ] **Step 4: Run green** + `just check` (the mounted-vs-registered guard in `app/api/main.py:151` must pass — router and `capability.yaml` land together).
- [ ] **Step 5: Commit** — `feat(prompts): the override API refuses what would break, saves the rest`

  ```
  User-visible: prompts can be listed, inspected, overridden and reset per scope; broken templates are named at save.
  ```

### Task 8: the prompts page

**Files:**
- Create: `app/capabilities/prompts/web/PromptsPage.tsx`, `app/capabilities/prompts/web/routes.tsx`, `app/capabilities/prompts/web/PromptsPage.test.tsx`
- Modify: `i18n/en.json`, `i18n/de.json`, `i18n/fr.json`; generated `web/lib/generated/routes.ts` after `pnpm --dir web generate`

**Interfaces:**
- Consumes: the Task 7 API; `useTranslation` from `@shell/lib/i18n`; the novels list route on the writing router (`app/capabilities/writing/router.py:119`) for the filter; the lazy-route pattern of `app/capabilities/settings/web/routes.tsx`.
- Produces: route `/prompts`; page components per the existing web patterns.

- [ ] **Step 1: Write the failing component tests** (mirror `ProvidersPanel.test.tsx`): renders the four keys with scope chips Global / novel; `chat.ask` shows no novel chip (API says `novel_scopable: false`); an empty novel scope shows the inherits-label and a create action that opens the editor prefilled with `effective_content`; saving a novel scope never touches the global row (assert the PUT body carries `novel_id`); a 422 renders the named reason; reset calls DELETE for the chip's scope; the diff view shows bundled and override side by side; every user-visible string comes from `t()`.
- [ ] **Step 2: Run red** (`pnpm --dir web test` scoped to the new file).
- [ ] **Step 3: Implement** the page, route and i18n keys (`prompts.heading`, chrome keys) in all three languages; run `pnpm --dir web generate`; commit the generated routes with the page.
- [ ] **Step 4: Run green** — component tests + `just check` (tsc).
- [ ] **Step 5: Commit** — `feat(prompts): the prompts page — both scopes, honest labels, named refusals`

  ```
  User-visible: one page lists every prompt, edits either scope, and shows exactly what a refusal names.
  ```

### Task 9: smoke goldens — every bundled prompt renders

**Files:**
- Create: `app/kernel/tests/test_prompts_smoke.py`

**Interfaces:**
- Consumes: `get_registry`, `render_source`, each capability's `sample_variables` via the registry.

- [ ] **Step 1: Write the tripwire test** — parametrized over `get_registry().keys()`: each bundled template renders through `render_source` with its sample variables (includes resolve bundled) and equals the committed golden literal for that key; each key's contract (when set) passes on its own bundled render. The goldens come from Tasks 4–6 (each pinned its own against the pre-rewrite function); this test re-asserts them through the registry, so a future edit to any bundled template or sample factory fails here.
- [ ] **Step 2: Run green** — this test is born green by construction (T4–6 hold the goldens); its value is the next change that rot. Verify it fails when a golden is deliberately perturbed (flip one character, see red, revert) — proof the tripwire trips.
- [ ] **Step 3: Commit** — `test(kernel): every bundled prompt renders its golden sample`

  ```
  User-visible: prompt rot becomes a failing test, not a surprise in production.
  ```

### Task 10: end-to-end — §7.5 and the archive boundary

**Files:**
- Create: `app/capabilities/prompts/e2e/__init__.py`, `app/capabilities/prompts/e2e/conftest.py`, `app/capabilities/prompts/e2e/test_prompts_e2e.py`

**Interfaces:**
- Consumes: the kernel testing stack (`app/kernel/testing/stack.py`) as the writing/settings E2Es use it; the interchange export/import API (`app/capabilities/writing/router.py:155,205`).

- [ ] **Step 1: Write the failing E2E** — (1) open `/prompts`, `assert_accessible`; (2) override `writing.continuation` for the novel through the page, run a continuation in the editor, read the latest `LlmCall` row from the database and assert `prompt_text` contains the override's marker sentence; (3) save a broken template (unknown variable) → the named 422 appears, nothing is stored; (4) save a `chat.ask` override without the source marker → contract 422; (5) reset the novel scope → the next continuation's `prompt_text` is the bundled text again; (6) with an override stored, export the novel → the archive's file set is exactly `metadata.json`, `chapters/`, `kb/` (no prompt file), and import round-trips as before.
- [ ] **Step 2: Run red.**
- [ ] **Step 3: Make it pass** — only test code; product fixes, if the flow exposes a gap, go back into the owning task as a new step with its own test.
- [ ] **Step 4: Full gate** — `just verify` (whole project) and this E2E, outputs read.
- [ ] **Step 5: Commit** — `test(prompts): the override lifecycle end to end, archive untouched`

  ```
  User-visible: the whole override lifecycle is proven on the real stack.
  ```

---

## Close-out

- `just verify` green and the prompts E2E green, outputs read, before the final review dispatch.
- Final whole-branch review on the review model; its findings triaged; surviving findings become GitHub issues (label `follow-up`, hung under the wave's index issue) before merge.
- The build session moves this plan to `docs/superpowers/plans/2026-10-29-wp4-prompt-overrides-plan.md` and the design to `docs/superpowers/specs/2026-10-29-wp4-prompt-overrides-design.md`, and commits both — move, never copy.
