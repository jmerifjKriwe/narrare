# E2E Spec: AI Writing (`test_ai_writing.py`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the first follow-on spec batch of the Phase-B E2E program — the AI-writing area specs (WRITE-002/003/004/005/006/007/009) on top of the merged suite foundation, with the audit's **M06** fix (empty-draft accept + dishonest 422/stream-death error handling) landing first as just-in-time gates, plus the two 2026-10-13 PO-ruled fix slices: the **B09-residual co-author bubble-menu entry** (the slash trigger provably cannot carry a selection) and the **N08 WS-origin test-mode parity** fix (spec §8).

**Architecture:** Three-layer delivery: (1) the fix slices — a Backend empty-draft accept guard (plus the `modified_text` body-contract repair it exposes), two Frontend honesty slices (localized 422 mapping; stream-death lifecycle + accept gating), a Frontend co-author bubble-menu entry mirroring the AI-rewrite pattern (PO ruling 1), and a Backend WS-origin `ENVIRONMENT=test` bypass mirroring the REST CSRF seam with a pinned production invariance (PO ruling 2); (2) deterministic catalog growth for the writing surfaces the specs assert against (`generation_stream/truncated`, `rewrite_stream`, `story_suggest`, `coauthor_stream`); (3) the specs themselves, split across three files to respect RULE-04's 400-line test-file hard limit: `test_ai_writing.py` (generate + ghost text), `test_ai_writing_selection.py` (extend/rewrite/co-author/unblock), `test_ai_writing_ws.py` (WS session full flow + the spec §8 N08 green/invariance pins). Shared editor/WS prep moves into `helpers/editor_ai.py` and `helpers/ws_probe.py`. **No strict-xfail pins remain** — both former red pins were converted to in-plan fixes + green pins per the PO rulings (see Decisions log).

**Tech Stack:** Python 3.14 · pytest + pytest-playwright (sync API, marker `e2e`) · FastAPI/SQLAlchemy (accept guard) · React 19 + Vitest (FE honesty slices) · `websockets` 16 sync client (N08 pin — already in the env via `uvicorn[standard]`).

**Inputs:**
- Spec: `docs/superpowers/specs/2026-10-11-e2e-full-suite-design.md` — §5 row `test_ai_writing.py`, §3 mock layers, §6 interleaving ("fixes zuerst"), §7 runtime budget, §8 N08 (test-mode parity fix ruled in-plan 2026-10-13), §10 catalog ratchet.
- Audit: `docs/superpowers/reports/2026-10-11-e2e-ui-audit.md` — M06, N08, N09, B01/B02/B08/B09 (fixed + merged), "Verified WORKING" list.
- Foundation (all on `main`): `tests/e2e/helpers/` (probes, llm_mocks `mock_llm(page, capability, *, fixture)`, audit_user, novel_factory), `tests/e2e/mocks/` catalog, `tests/e2e/foundation.py` fixtures (`stable_user` / `module_stable_user` / `stable_novel`), `scripts/run_e2e.sh` (`E2E_PYTEST_ARGS`), `tests/e2e/test_environment_smoke.py` (house style), `tests/e2e/test_ws_ticket_session.py` (WS observation pattern).
- Prior plans (same discipline): `docs/superpowers/plans/2026-10-12-e2e-blocker-fixes.md`, `docs/superpowers/plans/2026-10-12-e2e-suite-foundation.md`.

## Decisions log

- **D-2026-10-13-1 (PO ruling 1) — Co-author fix slice IN the plan, replacing the strict-xfail pin.** Code analysis (verified in-tree, Task 4) proves the slash trigger cannot carry a selection: the menu's activation grammar `^(\s*)/([^\s/]*)$` (`slash-commands/parser.ts:38`) requires the paragraph before the caret to be exactly `/query`, and `selectIndex` deletes `slashPos..selection.to` before the handler reads the selection (`useSlashCommandState.ts:120-124`). Ruling: a Frontend fix lands BEFORE the co-author spec — a bubble-menu entry mirroring the AI-rewrite pattern that opens CoAuthorOverlay WITH the current selection (Task 4). The spec (Task 9) then covers the REAL happy path (selection → bubble-menu → panel → apply) instead of an xfail. The slash entry stays AS-IS: the panel does NOT support selection-less opening (verified in Task 4 — `handleStartCoAuthor`'s empty-text guard is a no-op and `CoAuthorOverlay` mounts only for a non-null selection), so the slash command remains a listed, availability-gated no-op without a selection, pinned by Task 9's wiring test.
- **D-2026-10-13-2 (PO ruling 2) — N08 fix IN the plan, replacing the red pin.** The WS origin check in `apps/api/narrare/writing/router_sessions.py` (~line 87) must honor test mode the SAME way the REST CSRF middleware does. The exact seam (found in-tree, Task 5): `_app/main.py:62-69` does not install `OriginValidationMiddleware` when `settings.is_test` (`settings_model.py:236-237`, `environment == "test"`) — mirrored in a pure `origin_is_allowed(origin, settings)` helper. Bypass ONLY under `ENVIRONMENT=test`; the production security posture is unchanged, and that invariance is test-pinned (Task 5: policy pins under production AND development settings + the pre-existing route-level rejection test + a live-stack both-postures spot-check). The WS spec (Task 11) then pins the REAL behavior green: a ticketed connect from a non-allowlisted origin SUCCEEDS under `ENVIRONMENT=test` (the runner's mode). The production-settings rejection cannot be driven by the E2E runner — it boots exactly one API, under test mode — so that regression is pinned at unit level in Task 5 and referenced by Task 11.

## Global Constraints

- **Project language is English** — code, comments, tests, commit messages, docs (exception: `packages/i18n` message files).
- **`docs/_shared/CONSTRAINTS.md` is the constitution** — load it before starting. Most relevant here: RULE-04 (test files ≤ 400 lines hard — hence the three-file spec split; helpers ≤ 400), RULE-06 (one responsibility per file), RULE-10 (tests mandatory), RULE-11 (no silent failures), RULE-16 (i18n keys with en/de/fr parity — the keys used here already exist), RULE-17 (FE types mirror BE schemas in the same commit), RULE-20 (SSE backend ⇒ SSE frontend, no half-implementations), RULE-23 (no naked `# type: ignore`).
- **Regression-first:** every fix task writes the failing test FIRST, runs it, and records the red-phase output (command + observed failure) in the task report. A fix without red evidence is not done.
- **Task cap:** ≤ 3 product-implementation files and ≤ 250 new product LOC per task. Spec/helper/test files are the deliverable of Tasks 6–11 and are **exempt** from the caps per the PO ruling on suite slices (they are listed explicitly). Tasks 1–5 are product fixes and count normally; Task 4 additionally carries its three one-line i18n parity companions (`en/de/fr studio.json`) — a RULE-16 same-commit obligation, not extra implementation surface.
- **Layer tags** (first line of each task) route via the coordinator: `Backend` → NarrareBackendSpecialist, `Frontend` → NarrareFrontendSpecialist, `Platform` → NarrarePlatformSpecialist, `Docs` → NarrareDocsSpecialist. "Fixes zuerst": product fixes (Tasks 1–5) land BEFORE the specs that depend on them; execution order is 1 → 12, Docs last.
- **No product changes inside spec tasks.** If a spec task finds a NEW product defect (one beyond the two 2026-10-13-ruled in-plan fixes: co-author reachability → Task 4, N08 → Task 5), it writes the red pin (`xfail(strict=True)` documentation form per spec §5), stops, and routes the fix to the coordinator — never patches product code in a Platform task.
- **Conventional commits** (`fix(writing): …`, `fix(web): …`, `test(e2e): …`, `docs(testing): …`). **`git commit --no-verify` is FORBIDDEN.** Implementing sessions commit; pushes/tags go through NarrarePlatformSpecialist.
- **No real LLM calls, ever** (spec §3): factory layer (`NARRARE_E2E_TEST=1` → TestModel) for tolerance-loose surfaces (extend, ghost text, WS turns); browser-layer catalog for the deterministic surfaces this spec asserts exactly (generation, rewrite, unblock).
- **Test commands:**
  - Python integration: `uv run --all-packages pytest tests/integration/writing/test_writing_api.py -v -p no:randomly` (requires `just dev-services`, i.e. postgres_test on :5433).
  - Web unit: `pnpm --filter narrare-web exec vitest run <path>`; Web typecheck: `pnpm --filter narrare-web run type-check`.
  - Catalog/unit: `uv run --all-packages pytest tests/unit/test_e2e_mock_catalog.py -v -p no:randomly`.
  - Full E2E (CI-faithful): `just e2e`; subset: `E2E_PYTEST_ARGS="tests/e2e/test_ai_writing.py" just e2e`.
- **Live-stack verification (manual spot-check, fix tasks):** the proven :3001 pattern from the audit's environment section (`docs/superpowers/reports/2026-10-11-e2e-ui-audit.md` § "Audit environment (for reproduction)"): API on :8000 with `ENVIRONMENT=test NARRARE_E2E_TEST=1 SECRET_KEY=test-secret-key-not-for-production AUTH_JWT_SECRET=test-secret-key-not-for-production NARRARE_CSRF_TRUSTED_ORIGINS='["http://localhost:3001"]'` against the `narrare_test` DB on :5433; web via `pnpm dev --port 3001` with `AUTH_JWT_SECRET` exported (E01). Task 12 documents this recipe in `docs/development/testing-standards.md` so the citation is durable.
- **Runtime budget (spec §7):** full local suite target stays **≤ 25 min**. This batch's budget: **≤ 6 min added** on `E2E_FRONTEND_MODE=dev` (guidance: `test_ai_writing.py` ≤ 3 min, `test_ai_writing_selection.py` ≤ 2 min — the co-author happy path replaces the former fast-failing xfail within this budget, `test_ai_writing_ws.py` ≤ 90 s; each test ≤ 90 s — the runner's `--timeout=300` stays the hard stop). Task 12 records the measured actuals in `docs/development/e2e-coverage.md`.
- **Markers:** every test in this batch carries `@pytest.mark.e2e` (the runner selects `-m e2e`; an unmarked test is silently never run). **No strict-xfail pins remain in this batch** — the two former deferred-fix pins (co-author trigger, N08) were converted into in-plan fix slices (Tasks 4 and 5) whose spec tasks (9 and 11) pin the FIXED behavior green, per the 2026-10-13 PO rulings. **No new custom markers** (spec §7 default: single suite; the `test-e2e-core`/`test-e2e-full` split is a PO decision for when CI runtime is measured).
- **Catalog contract (spec §10):** new entries = fixture constant + `RouteSpec` + module `validate()` case + unit-test extension, in the same commit (documented in `docs/development/testing-standards.md` § E2E). SSE capabilities need happy+error variants.
- Line numbers quoted from source may be stale — each task re-verifies by semantic location before editing.

## Gate → Task map (fixes first — PO ruling "fixes zuerst")

| Task | Layer | Gate | Deliverable |
|------|-------|------|-------------|
| 1 | Backend | M06 (data integrity) | Accept-body contract repair + empty-draft accept guard (`422 EMPTY_DRAFT`) |
| 2 | Frontend | M06 (honest 422) | `422 MISSING_INPUT` → localized `generationPanel.validationMissingInput`; panel renders `t(error.i18nKey)` |
| 3 | Frontend | M06 (stream death) | Complete-without-`is_final` → error phase; Accept disabled on empty draft; accept sends the accepted text |
| 4 | Frontend | B09 residual (PO ruling 1) | Co-author bubble-menu entry (AI-rewrite pattern) that opens CoAuthorOverlay WITH the current selection; slash entry kept + selection-less support verified/documented |
| 5 | Backend | N08 (PO ruling 2) | WS origin check honors `ENVIRONMENT=test` via the exact REST CSRF seam (`settings.is_test`); production posture unchanged and pinned |
| 6 | Platform | — | Catalog: `generation_stream/truncated`, `rewrite_stream` (happy+error), `story_suggest` (happy+error), `coauthor_stream` (happy+error) |
| 7 | Platform | B-gates prep | `helpers/editor_ai.py` + `test_ai_writing.py` — WRITE-002 generate: happy accept, reject, empty-422, stream-error, truncated |
| 8 | Platform | B08/B01 pins | `test_ai_writing_selection.py` — WRITE-003 extend, WRITE-004 rewrite (apply) |
| 9 | Platform | B02 pin + B09 (fixed) | `test_ai_writing_selection.py` — WRITE-009 unblock, WRITE-006 co-author REAL happy path (selection → bubble-menu → panel → apply) + slash wiring pin |
| 10 | Platform | — | `test_ai_writing.py` — WRITE-007 ghost text accept + dismiss |
| 11 | Platform | spec §8 (fixed) | `helpers/ws_probe.py` + `test_ai_writing_ws.py` — WRITE-005 full WS flow + N08 green test-mode pin (production invariance unit-pinned in Task 5) |
| 12 | Docs | spec §9 | `e2e-coverage.md` status + budget actuals; testing-standards live-stack :3001 recipe |

---

### Task 1: Empty-draft accept guard + accept-body contract (M06, Backend half)

**Layer:** Backend · **Gate:** M06 (audit: "Accept enabled on an empty draft (empty-draft accept possible)")

**Files:**
- Modify: `apps/api/narrare/writing/schemas.py` (add `AcceptRequest`, ~line 96 next to `AcceptResponse`)
- Modify: `apps/api/narrare/writing/router.py:108-117` (`accept_draft` takes the body model)
- Modify: `apps/api/narrare/writing/service.py:228-242` (`accept_draft` guard)
- Test: `tests/integration/writing/test_writing_api.py` (new guard class + amend `test_accept_draft_returns_200`, line ~158)

**Interfaces:**
- Produces: `AcceptRequest(BaseModel)` with `modified_text: str | None = None` — the request body of `POST /writing/generation/{request_id}/accept`. `POST` without a body stays valid (the model is optional at the route).
- Produces: guard semantics — `accept_draft` raises `ValidationError(code="EMPTY_DRAFT")` (→ HTTP 422 `{"detail", "code"}`) iff `request_model.word_count == 0` AND `(modified_text or "").strip()` is empty. Task 3's FE relies on exactly this: it sends the accepted draft text as `modified_text`, which passes the guard.

**Root cause (2× why):**
- Why is an empty draft acceptable? `WritingService.accept_draft` validates ownership and nothing else — it records an "accept" feedback event for a request row with `word_count == 0` and returns 200 (audit M06: stream-death left the UI in review phase with Accept enabled; clicking it silently recorded a bogus accept).
- Why was there no guard? The FE was assumed to be the only gate; the M06 stream-death path proved the FE gate cannot be trusted (SSE can end without ever producing text), and the API is the integrity boundary for feedback/statistics (word_count feeds `get_stats`).

**Secondary defect verified while re-checking (fix included):** `router.py:113` declares `modified_text: str | None = None` as a **query parameter** (FastAPI default for un-annotated scalars), while the FE (`packages/web/lib/api/generation.ts:122`, `useEditorAutosave.ts:62`, `useAnnotationActions.ts:75`) sends `{ "modified_text": … }` in the **JSON body** — the value is silently discarded today (RULE-11 + RULE-17 violation; the FE's own unit test `generation.test.ts:89` pins the body shape). Switching the route to the body model makes the existing FE payloads land; no in-repo caller uses the query form (verified by grep).

**Alternatives considered:**
1. Body model `AcceptRequest` + word_count guard (chosen) — fixes the contract drift AND the integrity hole in one slice; backward-compatible for the only client (FE already sends the body).
2. Guard only, keep the query param — the guard would 422 the FE's body-carrying accepts (body ignored → `modified_text=None` → empty guard fires even when the user accepted text), i.e. the fix would break the happy path. Rejected.
3. FE-only gating (no backend guard) — the audit's repro is exactly the FE gate failing; defense-in-depth belongs at the API (data integrity + stats).

- [ ] **Step 1: Write the failing integration tests**

Append to `tests/integration/writing/test_writing_api.py`:

```python
class TestAcceptDraftEmptyGuard:
    """Audit M06 — accepting a draft that never received text must 422.

    A browser-side stream death leaves the request row at word_count == 0;
    the API must not record an "accept" for it (empty-draft accept was
    possible, polluting feedback + generation stats).
    """

    async def _start_request(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> str:
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)
        start_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={"mode": "full_draft", "prompt": "A dramatic scene", "language": "en"},
            headers=auth_headers,
        )
        assert start_resp.status_code == 200, start_resp.text[:300]
        return start_resp.json()["request_id"]

    async def test_accept_without_generated_text_returns_422_empty_draft(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        request_id = await self._start_request(client, auth_headers)

        resp = await client.post(
            f"/api/v1/writing/generation/{request_id}/accept",
            headers=auth_headers,
        )

        assert resp.status_code == 422, resp.text[:300]
        body = resp.json()
        assert body["code"] == "EMPTY_DRAFT"

    async def test_accept_with_edited_text_passes_guard_on_empty_row(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """modified_text in the JSON BODY must reach the service (contract repair)."""
        request_id = await self._start_request(client, auth_headers)

        resp = await client.post(
            f"/api/v1/writing/generation/{request_id}/accept",
            json={"modified_text": "Hand-edited opening line."},
            headers=auth_headers,
        )

        assert resp.status_code == 200, resp.text[:300]
        assert resp.json()["request_id"] == request_id
```

Amend the existing `test_accept_draft_returns_200` (line ~158): add the `db_session` fixture parameter and, between the `DELETE` (stop) and the accept `POST`, insert:

```python
        # Post-M06 guard: a request row that never streamed text
        # (word_count == 0) must not be acceptable — make the row non-empty
        # exactly like a completed stream would before asserting the 200 path.
        from sqlalchemy import update

        from narrare.writing.models import GenerationRequest

        await db_session.execute(
            update(GenerationRequest)
            .where(GenerationRequest.id == uuid.UUID(request_id))
            .values(word_count=120, status="completed")
        )
        await db_session.flush()
```

(`uuid` is already imported at module top; the integration `client` runs on the same rolled-back session, so the flush is visible to the app.)

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --all-packages pytest tests/integration/writing/test_writing_api.py -v -p no:randomly`
Expected: FAIL — `test_accept_without_generated_text…`: `assert 200 == 422` (the audit repro); `test_accept_with_edited_text…`: `assert 200 == 200` passes the status but is the guard's red companion — it fails only after the guard exists if the body is not read; treat the FIRST test's red as the gate evidence and record both outputs. The amended `test_accept_draft_returns_200` still passes pre-fix (guard absent). Record output.

- [ ] **Step 3: Implement schema, route, guard**

In `apps/api/narrare/writing/schemas.py`, directly above `class AcceptResponse`:

```python
class AcceptRequest(BaseModel):
    """Accept-draft request body.

    RULE-17 repair (audit M06 slice): the FE has always sent
    ``{"modified_text": …}`` as a JSON body
    (packages/web/lib/api/generation.ts), but the route read it as a query
    parameter — silently discarding the value. This model makes the body the
    contract.
    """

    modified_text: str | None = None
```

In `apps/api/narrare/writing/router.py`, change the accept route (lines 108-117) to:

```python
@router.post("/generation/{request_id}/accept", response_model=AcceptResponse)
async def accept_draft(
    request_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
    accept_request: AcceptRequest | None = None,
) -> AcceptResponse:
    """Accept a generated draft (optionally with user edits in the body)."""
    service = await get_writing_service(session, user_id)
    modified_text = accept_request.modified_text if accept_request is not None else None
    return await service.accept_draft(request_id, user_id, modified_text)
```

and add `AcceptRequest` to the `from narrare.writing.schemas import (…)` block (line ~23).

In `apps/api/narrare/writing/service.py`, extend `accept_draft` (line ~228) — add the guard directly after `get_validated_request` and extend the docstring's `Raises:` section:

```python
        request_model = await get_validated_request(self._repo, request_id, user_id)
        if request_model.word_count == 0 and not (modified_text or "").strip():
            raise ValidationError(
                "Cannot accept a draft with no generated text",
                code="EMPTY_DRAFT",
            )
```

Add `ValidationError` to the module's imports if absent (`from narrare_core.shared.errors import ValidationError`).

- [ ] **Step 4: Run the tests to verify green**

Run: `uv run --all-packages pytest tests/integration/writing/test_writing_api.py tests/unit/api/writing/test_writing_service_scenes.py -v -p no:randomly`
Expected: ALL PASS (the service-level `accept_draft(modified_text=…)` test is untouched — service signature unchanged).

- [ ] **Step 5: Live-stack spot-check**

Start the stack per the :3001 recipe (Global Constraints). In the running API: `curl -s -X POST 'http://localhost:8000/api/v1/writing/generation/<fresh-request-id>/accept' -H "Authorization: Bearer <token>" -H 'Content-Type: application/json'` → expect `422 {"detail": "Cannot accept a draft with no generated text", "code": "EMPTY_DRAFT"}`. Record the exchange.

- [ ] **Step 6: Commit**

```bash
git add apps/api/narrare/writing/schemas.py apps/api/narrare/writing/router.py apps/api/narrare/writing/service.py tests/integration/writing/test_writing_api.py
git commit -m "fix(writing): read accept modified_text from body and reject empty-draft accepts (M06)"
```

---

### Task 2: Honest 422 MISSING_INPUT mapping in the generation panel (M06, Frontend half 1)

**Layer:** Frontend · **Gate:** M06 (audit: "Empty-form 422 MISSING_INPUT mis-mapped to 'connection lost' (unused i18n key `generationPanel.validationMissingInput` exists)")

**Files:**
- Modify: `packages/web/lib/api/ai-error-mapping.ts` (map entry + `mapHTTPStatus` 422 branch)
- Modify: `packages/web/components/studio/editor/GenerationPanel.tsx:140-147` (localized error rendering)
- Test: `packages/web/lib/api/__tests__/ai-error-mapping.test.ts` (extend) and `packages/web/components/studio/editor/__tests__/GenerationPanel.test.tsx` (extend)

**Interfaces:**
- Produces: `mapSSEError(new ApiError(msg, 422, "MISSING_INPUT"))` → `AIErrorResponse { kind: "http", status: 422, i18nKey: "generationPanel.validationMissingInput", retryable: false }`. The key resolves under the `studio` namespace (both `aiActions.*` and `generationPanel.*` live in `studio.json`), so the panel's `t = useTranslations("studio")` renders it directly.
- Produces: panel error branch renders `t(error.i18nKey)` whenever the structured error carries an i18n key (falling back to `errorMsg`/`unknownError` only when it does not). Task 7's E2E pins rely on the rendered English strings.

**Root cause (2× why):**
- Why does an empty generate form render "Verbindung verloren. Prüfe deine Internetverbindung."? The start POST answers `422 {"detail": …, "code": "MISSING_INPUT"}`; `mapHTTPStatus` has no 422 branch, so it falls into the "5xx or other HTTP errors" bucket → `aiActions.errorConnection` whose `userMessage` is the hardcoded German fallback (the M05 class) — and the panel prints `errorMsg` (that fallback) verbatim.
- Why is the mapping missing? The mapper predates the backend's `code` field on validation errors; only 401/413/429/408 were wired, and the panel never consumed `error.i18nKey`. The honest key (`studio.generationPanel.validationMissingInput`, en/de/fr parity already shipped) has been sitting unused since the panel was built.

**Alternatives considered:**
1. Mapper branch + localized panel rendering (chosen) — every 422 MISSING_INPUT (now and future) maps honestly; no new i18n keys needed; the rendering fix also un-Deutschmarks the generic error branch for this panel without touching the M05 wave's panels (ChatPanel/ConsistencyCheckPanel stay theirs).
2. FE-only pre-validation that blocks the empty submit client-side — good UX but leaves the wire-level mis-mapping intact (the spec explicitly pins the empty-422 path through the REAL backend response); rejected as the sole fix. (A client-side guard may be added later as UX polish — out of scope.)
3. Mapping inside `useGenerationStream` via `useAIOperation`'s `errorMapper` option — a per-operation override duplicates the shared mapper's knowledge of the backend code; the shared mapper is the SSOT.

- [ ] **Step 1: Write the failing unit tests**

Append to `packages/web/lib/api/__tests__/ai-error-mapping.test.ts`:

```ts
describe("MISSING_INPUT validation mapping (audit M06)", () => {
  it("maps 422 + MISSING_INPUT to the generationPanel validation key", () => {
    const error = new ApiError(
      "At least one of prompt, outline, or auto_continue must be provided",
      422,
      "MISSING_INPUT",
    );

    const result = mapSSEError(error);

    expect(result).not.toBeNull();
    expect(result!.kind).toBe("http");
    expect(result!.status).toBe(422);
    expect(result!.i18nKey).toBe("generationPanel.validationMissingInput");
    expect(result!.retryable).toBe(false);
  });

  it("keeps the generic connection mapping for 422 without a known code", () => {
    const error = new ApiError("Unprocessable entity", 422, null);

    const result = mapSSEError(error);

    expect(result!.i18nKey).toBe("aiActions.errorConnection");
  });
});
```

(Import `ApiError` from `"../core"` and `mapSSEError` from `"../ai-error-mapping"` if not already imported in that file.)

Append to `packages/web/components/studio/editor/__tests__/GenerationPanel.test.tsx`:

```tsx
it("renders the localized validation message for 422 MISSING_INPUT (M06)", async () => {
  // next-intl is mocked globally to echo keys (setupTests.ts), so the
  // localized rendering assertion is on the KEY being passed to t().
  mockStartGeneration.mockRejectedValue(
    new ApiError("At least one of prompt, outline, or auto_continue", 422, "MISSING_INPUT"),
  );
  renderWithProviders(
    <GenerationPanel
      novelId="novel-1"
      chapterId="chapter-1"
      chapterContent=""
      onDraftAccepted={vi.fn()}
      onClose={vi.fn()}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "Generate" }));

  await waitFor(() =>
    expect(screen.getByRole("alert").textContent).toBe("generationPanel.validationMissingInput"),
  );
  // M06 pin: the German connection-lost fallback must NOT be the rendered text.
  expect(screen.getByRole("alert").textContent).not.toContain("Verbindung");
});
```

Import `ApiError` from `"@/lib/api/core"` in that test file. (If the existing harness's Generate click needs the prompt step first, mirror the existing "calls startGeneration" test's exact navigation to the config phase — the assertion target is the `role="alert"` div of the error phase.)

- [ ] **Step 2: Run them to verify they fail**

Run: `pnpm --filter narrare-web exec vitest run lib/api/__tests__/ai-error-mapping.test.ts components/studio/editor/__tests__/GenerationPanel.test.tsx`
Expected: FAIL — mapper test: `i18nKey` is `"aiActions.errorConnection"`; panel test: alert contains the German fallback, not the key. Record output.

- [ ] **Step 3: Implement**

In `packages/web/lib/api/ai-error-mapping.ts`:

1. Add to `AI_ERROR_MESSAGE_MAP` (note in the comment above the map that keys may come from any `studio.*` sub-namespace):

```ts
  "generationPanel.validationMissingInput": {
    de: "Mindestens eines der Felder Gliederung, Prompt oder automatisches Fortfahren muss ausgefüllt sein.",
    retryable: false,
  },
```

2. In `mapHTTPStatus`, directly above the `if (status === 429)` branch:

```ts
  if (status === 422 && code === "MISSING_INPUT") {
    // Audit M06: an empty generate form is a validation error, not a
    // connection failure — map it to the panel's honest key (en/de/fr
    // parity already shipped with the panel).
    return {
      kind: "http",
      status: 422,
      i18nKey: "generationPanel.validationMissingInput",
      userMessage: AI_ERROR_MESSAGE_MAP["generationPanel.validationMissingInput"].de,
      retryable: false,
      cause,
    };
  }
```

3. Extend the `mapSSEError` doc-comment mapping-rules list with: `kind="http" + 422 + code="MISSING_INPUT" → empty-input validation (not retryable)`.

In `packages/web/components/studio/editor/GenerationPanel.tsx`, replace the error-phase alert's content (line ~146):

```tsx
                {controller.error?.i18nKey
                  ? t(controller.error.i18nKey)
                  : controller.errorMsg || t("generationPanel.unknownError")}
```

(`controller.error` is already exposed by the controller — `error: stream.state.error`.)

- [ ] **Step 4: Run the tests to verify green**

Run: `pnpm --filter narrare-web exec vitest run lib/api/__tests__/ai-error-mapping.test.ts components/studio/editor/__tests__/GenerationPanel.test.tsx && pnpm --filter narrare-web run type-check`
Expected: ALL PASS.

- [ ] **Step 5: Live-stack spot-check (:3001 recipe)**

In the running web app: open a novel editor → Generate → submit the empty form → the panel must show "At least one of outline, prompt, or auto-continue must be provided." — not "Verbindung verloren…". Record a screenshot path in the task report.

- [ ] **Step 6: Commit**

```bash
git add packages/web/lib/api/ai-error-mapping.ts packages/web/components/studio/editor/GenerationPanel.tsx packages/web/lib/api/__tests__/ai-error-mapping.test.ts packages/web/components/studio/editor/__tests__/GenerationPanel.test.tsx
git commit -m "fix(web): map empty-generation 422 to the localized validation message (M06)"
```

---

### Task 3: Stream-death honesty + accept gating (M06, Frontend half 2)

**Layer:** Frontend · **Gate:** M06 (audit: "the SSE dies silently → UI stuck 'Waiting for AI response…' with Accept enabled on an empty draft")

**Files:**
- Modify: `packages/web/components/studio/editor/useGenerationStream.ts` (final-chunk guard)
- Modify: `packages/web/components/studio/editor/useGenerationMutations.ts` (accept sends the draft text)
- Modify: `packages/web/components/studio/editor/GenerationDraft.tsx:109-119` (Accept disabled on empty draft)
- Test: `packages/web/components/studio/editor/generationPanelController.test.tsx` (extend) and `packages/web/components/studio/editor/__tests__/GenerationDraft.test.tsx` (extend)

**Interfaces:**
- Produces: `useGenerationStream` throws `SSEStreamError(kind="stream")` when the SSE completes without any `is_final` chunk — the operation lands in the error phase instead of `isComplete` (which previously derived the review phase with an empty draft).
- Produces: `acceptMutation` calls `writingApi.acceptDraft(requestId, draftText || undefined)` — the accepted text travels as `modified_text` (Task 1's body contract), so a browser-mocked stream's accept passes the backend `EMPTY_DRAFT` guard, and production feedback records the text the user actually accepted.
- Produces: the review-phase Accept button is `disabled` when `draftText.trim()` is empty.

**Root cause (2× why):**
- Why is Accept enabled on an empty draft after a stream death? `connectSSE` never rejects — a stream that ends without `[DONE]`/`is_final` (TestModel retry exhaustion killed the generator mid-flight; the reader just sees `done`) resolves normally → `execute` returns → `useAIOperation` status `complete` → `useGenerationMutations` derives `phase = "review"` for `isComplete` — with `draftText === ""`. The panel then renders the review buttons unconditionally (`GenerationDraft.tsx:109-119` gates only on mutation-pending state).
- Why did nobody notice? Every catalog/happy path ends with `is_final`; only the validator-strict agent dying under TestModel produces the silent-end shape (audit E04), and no unit test drove `streamGeneration` to a no-final-chunk resolution.

**Alternatives considered:**
1. Final-chunk guard at the operation level (chosen) — the stream's own completion contract is enforced where the stream is consumed; every consumer of the hook gets it; the error phase renders Retry (recoverable UX).
2. Phase-derivation fix only (`phase = isComplete && draftText ? "review" : "error"`) — treats the symptom in the derived state and would still show "complete" (no error message) for a genuinely failed stream; the user learns nothing. Rejected as primary, kept as belt-and-braces via the disabled Accept.
3. Backend emits an explicit error SSE event on stream failure — already half-true (the row is marked `failed`), but the browser cannot see post-mortem events after the generator dies; the client must treat missing `is_final` as failure regardless. Rejected as the sole fix.

- [ ] **Step 1: Write the failing unit tests**

Append to `packages/web/components/studio/editor/generationPanelController.test.tsx` (inside the existing describe, reusing its harness and mocks):

```tsx
  it("treats a stream that completes without is_final as an error (M06)", async () => {
    mockStartGeneration.mockResolvedValue({ request_id: "gen-m06", status: "pending" });
    mockStreamGeneration.mockImplementation(
      async (_rid: string, onChunk: (c: { text: string; is_final?: boolean }) => void) => {
        onChunk({ text: "" }); // silent death: no is_final, stream just ends
      },
    );

    const { result } = renderHook(
      () =>
        useGenerationPanelController({
          novelId: "novel-1",
          chapterId: "chapter-1",
          onDraftAccepted: vi.fn(),
          t: (key: string) => key,
        }),
      { wrapper: makeWrapper() },
    );

    act(() => result.current.handleGenerate());

    await waitFor(() => expect(result.current.phase).toBe("error"));
    expect(result.current.error?.i18nKey).toBe("aiActions.errorDefault");
  });

  it("accepts with the streamed draft text as modified_text (M06 + Task 1 contract)", async () => {
    mockStartGeneration.mockResolvedValue({ request_id: "gen-m06b", status: "pending" });
    mockStreamGeneration.mockImplementation(
      async (_rid: string, onChunk: (c: { text: string; is_final?: boolean }) => void) => {
        onChunk({ text: "The harbour bell rang twice." });
        onChunk({ text: " Done.", is_final: true });
      },
    );
    mockAcceptDraft.mockResolvedValue({ request_id: "gen-m06b", chapter_id: "c1", word_count: 5 });

    const onDraftAccepted = vi.fn();
    const { result } = renderHook(
      () =>
        useGenerationPanelController({
          novelId: "novel-1",
          chapterId: "chapter-1",
          onDraftAccepted,
          t: (key: string) => key,
        }),
      { wrapper: makeWrapper() },
    );

    act(() => result.current.handleGenerate());
    await waitFor(() => expect(result.current.phase).toBe("review"));
    act(() => result.current.acceptDraft());

    await waitFor(() => expect(mockAcceptDraft).toHaveBeenCalledWith("gen-m06b", "The harbour bell rang twice. Done."));
    await waitFor(() => expect(onDraftAccepted).toHaveBeenCalledWith("The harbour bell rang twice. Done."));
  });
```

(Adjust the `mockStreamGeneration` call arity if the harness's mocked signature differs — assert on the calls, not the mock shape.)

Append to `packages/web/components/studio/editor/__tests__/GenerationDraft.test.tsx`:

```tsx
  it("disables Accept when the draft is empty (M06)", () => {
    render(
      <GenerationDraft
        phase="review"
        draftText=""
        wordCount={0}
        targetNum={3000}
        tokenUsage={null}
        isAcceptPending={false}
        isRejectPending={false}
        onStop={vi.fn()}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        onRegenerate={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Accept" })).toBeDisabled();
  });

  it("keeps Accept enabled for a non-empty draft", () => {
    render(
      <GenerationDraft
        phase="review"
        draftText="The harbour bell rang twice before dawn."
        wordCount={7}
        targetNum={3000}
        tokenUsage={null}
        isAcceptPending={false}
        isRejectPending={false}
        onStop={vi.fn()}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        onRegenerate={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Accept" })).toBeEnabled();
  });
```

(Match the existing file's render helpers/imports; the component takes no i18n provider because of the global next-intl mock.)

- [ ] **Step 2: Run them to verify they fail**

Run: `pnpm --filter narrare-web exec vitest run components/studio/editor/generationPanelController.test.tsx components/studio/editor/__tests__/GenerationDraft.test.tsx`
Expected: FAIL — test 1: `phase` is `"review"` with an empty draft (the audit repro, unit level); test 2: `mockAcceptDraft` called with `("gen-m06b", undefined)`; GenerationDraft tests: Accept enabled on empty. Record output.

- [ ] **Step 3: Implement**

In `packages/web/components/studio/editor/useGenerationStream.ts`:

1. Import `SSEStreamError`: `import { SSEStreamError } from "@/lib/api/streaming";`
2. In `execute`, wrap the stream call with the final-chunk contract:

```ts
      let sawFinalChunk = false;
      await streamGeneration(
        rid,
        (chunk) => {
          onChunkNotify();
          if (chunk.is_final) sawFinalChunk = true;
          setDraftText((prev) => prev + chunk.text);
          setWordCount((prev) => prev + chunk.text.split(/\s+/).filter(Boolean).length);
        },
        undefined,
        (err) => {
          throw err;
        },
        signal,
        setTokenUsage,
        setContextMeta,
      );
      // Audit M06: a generation stream that ends without an is_final chunk
      // died silently (TestModel retry exhaustion / provider drop). Treat it
      // as a stream error — NOT a completed draft — so the panel never
      // reaches the review phase with an empty draft.
      if (!sawFinalChunk) {
        throw new SSEStreamError("Generation stream ended without a final chunk", "stream");
      }
      return null;
```

In `packages/web/components/studio/editor/useGenerationMutations.ts`, change the accept mutation (line ~37):

```ts
  const acceptMutation = useMutation({
    // Audit M06 + accept-body contract: send the accepted text as
    // modified_text. For browser-mocked streams the backend row has no
    // text (the stream never ran server-side), so the EMPTY_DRAFT guard
    // needs it; in production feedback records what the user accepted.
    mutationFn: () => writingApi.acceptDraft(requestId!, draftText || undefined),
    onSuccess: () => {
      rating.captureOriginal();
      onDraftAccepted(draftText);
      rating.setShowRating("accept");
    },
  });
```

In `packages/web/components/studio/editor/GenerationDraft.tsx` (Accept button, line ~111):

```tsx
            <button
              type="button"
              onClick={onAccept}
              disabled={isAcceptPending || draftText.trim().length === 0}
              title="Ctrl/⌘+Enter"
```

- [ ] **Step 4: Run the tests to verify green**

Run: `pnpm --filter narrare-web exec vitest run components/studio/editor/generationPanelController.test.tsx components/studio/editor/__tests__/GenerationDraft.test.tsx components/studio/editor/__tests__/GenerationPanel.test.tsx && pnpm --filter narrare-web run type-check`
Expected: ALL PASS (Task 2's panel test stays green).

- [ ] **Step 5: Live-stack spot-check (:3001 recipe)**

With the stack running, in the browser devtools on a novel editor: `window.fetch = new Proxy(window.fetch, {apply: async () => new Response('data: {"type":"context_meta"}\n\ndata: [DONE]\n\n', {status: 200, headers: {'Content-Type': 'text/event-stream'}})})` is NOT needed — simpler: verify the disabled-Accept UI by opening Generate with the dev network throttled to offline after starting a generation: the panel must land in the error phase with Retry, and at no point show an enabled Accept over "Waiting for AI response…". Record the observation.

- [ ] **Step 6: Commit**

```bash
git add packages/web/components/studio/editor/useGenerationStream.ts packages/web/components/studio/editor/useGenerationMutations.ts packages/web/components/studio/editor/GenerationDraft.tsx packages/web/components/studio/editor/generationPanelController.test.tsx packages/web/components/studio/editor/__tests__/GenerationDraft.test.tsx
git commit -m "fix(web): fail generation streams that never finalize and gate empty-draft accepts (M06)"
```

---

### Task 4: Co-author bubble-menu entry carrying the selection (B09 residual, Frontend)

**Layer:** Frontend · **Gate:** B09 residual — PO ruling 1 (2026-10-13): the slash trigger provably cannot carry a selection, so the co-author flow is unreachable with a passage through real input. Fix lands IN this plan, BEFORE the WRITE-006 spec (Task 9).

**Files:**
- Modify: `packages/web/components/studio/editor/TipTapBubbleMenu.tsx` (optional `onCoAuthor` prop + button mirroring the AI-rewrite button)
- Modify: `packages/web/components/studio/TipTapEditor.tsx:104-111` (forward `slashCommandHandlers?.onCoAuthor` into the bubble menu)
- Modify (RULE-16 parity companions, one key each): `packages/i18n/messages/en/studio.json`, `de/studio.json`, `fr/studio.json` (`bubble.coAuthor`)
- Test: `packages/web/components/studio/__tests__/TipTapEditor.test.tsx` (extend the existing `TipTapBubbleMenu` mock + two forwarding tests)

**Interfaces:**
- Produces: `TipTapBubbleMenuProps.onCoAuthor?: () => void` — when defined, a "Co-Author" button renders after the AI-rewrite button (same shape: `px-3 py-2 hover:bg-accent … text-primary`, `Users` icon from `lucide-react`, label `t("bubble.coAuthor")`); when undefined, no button (TipTapEditor used outside EditorView).
- Produces: `TipTapEditor` passes `onCoAuthor={slashCommandHandlers?.onCoAuthor}` — the host's existing `handleStartCoAuthor` (`useEditorAiEntryPoints.ts:77-83`) already captures `from/to/text/context` from `editor.state.selection`; the bubble menu is visible exactly when `from !== to` (`TipTapBubbleMenu.tsx:33-37`), so the entry point and the selection requirement coincide by construction.

**Root cause (2× why):**
- Why is Co-Author unreachable with a selected passage? The only in-editor trigger is the slash command (`writing.co_author`), and the menu's activation grammar `ACTIVATING_PATTERN = /^(\s*)\/([^\s/]*)$/` (`slash-commands/parser.ts:38`) requires the textblock before the caret to be exactly `/query`; `selectIndex` deletes `slashPos..selection.to` before dispatching (`useSlashCommandState.ts:120-124`, verified in-tree) — so dispatching through real input destroys the selected passage, and `handleStartCoAuthor`'s empty-text guard (`useEditorAiEntryPoints.ts:81`) no-ops.
- Why did the B09 fix not catch this? The fix slice wired the handler, the overlay mount, and the slash item — all provable by unit tests that call the handler directly with a selection preset. The input-level destruction only manifests in real typing (an E2E-class concern), which is exactly what the audit's B09 evidence and this plan's former strict-xfail pin demonstrated. The rewrite feature solved the same problem with a bubble-menu entry; co-author never got one.

**Selection-less panel support — VERIFIED (ruling 1 requirement), document in the task report:** the panel does NOT support selection-less opening. `handleStartCoAuthor` returns early on empty selection text, and `CoAuthorOverlay` mounts only while `flow.selection` is non-null (`editor-view/CoAuthorOverlay.tsx:19`; `CoAuthorPanel` requires a non-empty `selectionText`). Consequence, encoded in Task 9: the slash entry stays AS-IS — a listed, availability-gated command whose dispatch is a guarded no-op without a selection (pinned green by Task 9's wiring test); the bubble entry is THE selection-carrying path. No slash-side change in this plan.

**Alternatives considered:**
1. Bubble-menu entry mirroring AI-rewrite (chosen — PO ruling 1): the menu exists exactly when a selection exists; its buttons demonstrably preserve the selection through click (the AI-rewrite E2E path, Task 8, proves click → handler reads the live selection); ~30 LOC, no shared-state-machine changes.
2. Fix the slash pipeline to preserve the selection (delete only the slash text, not through `selection.to`): touches the state machine every slash command shares, and the activation grammar still requires the caret's paragraph to BE `/query` — a passage selected elsewhere contradicts that state; higher risk for no UX gain over the bubble entry. Rejected for this slice.
3. Toolbar button: more chrome, loses the locality of the selection surface; the PO ruling names the bubble-menu pattern. Rejected.

- [ ] **Step 1: Write the failing unit tests**

In `packages/web/components/studio/__tests__/TipTapEditor.test.tsx`, the existing mock renders the bubble menu as plain buttons — extend it to expose the new prop:

```tsx
vi.mock("@/components/studio/editor/TipTapBubbleMenu", () => ({
  TipTapBubbleMenu: vi.fn(({ onAIRewrite, onCoAuthor }) => (
    <div>
      <button type="button" onClick={onAIRewrite}>AI rewrite</button>
      {onCoAuthor && <button type="button" onClick={onCoAuthor}>Co-Author</button>}
    </div>
  )),
}));
```

(Keep the existing assertions green — the mock only ADDS a conditional button.) Append inside the existing describe:

```tsx
  it("forwards the host co-author handler to the bubble menu (B09 residual)", () => {
    const onCoAuthor = vi.fn();
    renderTipTapEditor({ slashCommandHandlers: { onCoAuthor } });

    fireEvent.click(screen.getByRole("button", { name: "Co-Author" }));

    expect(onCoAuthor).toHaveBeenCalledTimes(1);
  });

  it("renders no co-author bubble entry when the host supplies no handler", () => {
    renderTipTapEditor({}); // no slashCommandHandlers

    expect(screen.queryByRole("button", { name: "Co-Author" })).toBeNull();
  });
```

(Match the file's existing render helper/signature — the assertion targets are the two button states; if the harness requires content/chapterId props, mirror the neighboring tests.)

- [ ] **Step 2: Run them to verify they fail**

Run: `pnpm --filter narrare-web exec vitest run components/studio/__tests__/TipTapEditor.test.tsx`
Expected: FAIL — test 1: no "Co-Author" button (prop not forwarded); test 2: passes vacuously pre-fix? No — without the prop both find nothing, so test 1 is the red gate (`getByRole` throws "unable to find role=button name=Co-Author"). Record output.

- [ ] **Step 3: Implement**

In `packages/web/components/studio/editor/TipTapBubbleMenu.tsx`:

1. Extend the lucide import: `import { Loader2, Sparkles, Users } from "lucide-react";`
2. Add to `TipTapBubbleMenuProps` (after `onAIRewrite`): `readonly onCoAuthor?: () => void;` and destructure it.
3. After the AI-rewrite `</button>`, inside the flex row:

```tsx
        {onCoAuthor && (
          <button
            type="button"
            onClick={onCoAuthor}
            title={t("bubble.coAuthor")}
            className="px-3 py-2 hover:bg-accent transition-colors flex items-center gap-1.5 text-sm text-primary"
          >
            <Users className="w-3.5 h-3.5" />
            <span>{t("bubble.coAuthor")}</span>
          </button>
        )}
```

In `packages/web/components/studio/TipTapEditor.tsx`, extend the `<TipTapBubbleMenu>` mount (line ~104):

```tsx
        onAIRewrite={controller.handleAIRewrite}
        onCoAuthor={slashCommandHandlers?.onCoAuthor}
```

In each of `packages/i18n/messages/{en,de,fr}/studio.json`, inside the existing `"bubble"` object (en line ~148):

```json
    "coAuthor": "Co-Author"
```

(`de`: `"Co-Autor"`, `fr`: `"Co-auteur"` — matching the existing `slashCommands.coauthor`/`settings-ai` label conventions per locale.)

- [ ] **Step 4: Run the tests to verify green**

Run: `pnpm --filter narrare-web exec vitest run components/studio/__tests__/TipTapEditor.test.tsx && pnpm --filter narrare-web run type-check`
Expected: ALL PASS (including the pre-existing bubble-menu tests — the mock change is additive). If the repo's i18n parity check exists as a script (RULE-16), run it too and record the command.

- [ ] **Step 5: Live-stack spot-check (:3001 recipe)**

With the stack running: open a novel editor with text, select a passage → the bubble menu shows "Co-Author" next to "AI rewrite" → click it → the Co-Author overlay opens CARRYING the passage (visible in the panel's selection summary). Then verify the slash entry unchanged: `/co` in an empty paragraph lists Co-Author; dispatching it there does NOT open the overlay (guarded no-op). Record a screenshot path + the selection-less observation in the task report.

- [ ] **Step 6: Commit**

```bash
git add packages/web/components/studio/editor/TipTapBubbleMenu.tsx packages/web/components/studio/TipTapEditor.tsx packages/i18n/messages/en/studio.json packages/i18n/messages/de/studio.json packages/i18n/messages/fr/studio.json packages/web/components/studio/__tests__/TipTapEditor.test.tsx
git commit -m "fix(web): co-author bubble-menu entry carrying the selection (B09 residual)"
```

---

### Task 5: WS origin check honors ENVIRONMENT=test (N08, Backend)

**Layer:** Backend · **Gate:** N08 — PO ruling 2 (2026-10-13): the WS origin check in `router_sessions.py` (~line 87) must honor test mode the SAME way the REST CSRF middleware does. Fix lands IN this plan, BEFORE the WRITE-005/N08 spec (Task 11). Bypass ONLY under `ENVIRONMENT=test`; the production security posture is unchanged and that invariance is test-pinned.

**Files:**
- Create: `apps/api/narrare/writing/ws_origin.py` (pure policy helper)
- Modify: `apps/api/narrare/writing/router_sessions.py:83-91` (origin block delegates to the helper)
- Test: `tests/unit/api/writing/test_router_sessions_validation.py` (extend: route-level test-mode red test) and `tests/unit/api/writing/test_ws_origin.py` (create: production-invariance policy pins)

**The exact REST seam (verified in-tree):** `apps/api/narrare/_app/main.py:62-69` does NOT install `OriginValidationMiddleware` when `settings.is_test` (`settings_model.py:236-237`, `environment == "test"`) — plus a constructor `_test_mode` flag for integration app instances. The WS handshake is a route-level guard with no middleware stack to skip, so the mirror is the same settings-derived gate read at dispatch time: `settings.is_test` bypasses the origin rejection. No `create_app` plumbing, no new flag — the runner's actual lever is `ENVIRONMENT=test` (`scripts/run_e2e.sh:79`).

**Interfaces:**
- Produces: `origin_is_allowed(origin: str, settings: Settings) -> bool` in `narrare.writing.ws_origin` — `True` iff (a) `settings.is_test` (REST parity), or (b) `origin == ""` (non-browser clients — pre-fix behavior preserved), or (c) `origin in settings.csrf_trusted_origins`.
- Produces: route behavior — under `ENVIRONMENT=test`, a ticketed WS connect with a NON-allowlisted Origin proceeds past the origin gate (to rate limit → session resolution → greeting); under development/production the check rejects exactly as today (1008 + error frame).

**Root cause (2× why):**
- Why does the WS origin check reject under `ENVIRONMENT=test` while REST CSRF does not? The check reads `get_settings().csrf_trusted_origins` unconditionally (`router_sessions.py:87-91`) — it never got the environment seam the REST path has (`main.py:64` skips middleware installation under `is_test`).
- Why does that matter? The E2E runner operates the API under `ENVIRONMENT=test` precisely so programmatic/test clients are not CSRF-gated; a raw WebSocket client (spec §8's probe) sends an Origin outside the test allowlist and is rejected 1008 — the surface behaves differently from every REST endpoint around it (N08), and the WRITE-005 WS specs cannot drive the real handshake from a non-browser origin. In test mode there is no production threat model; in production the posture must stay byte-identical.

**Alternatives considered:**
1. Pure `origin_is_allowed(origin, settings)` helper with the `is_test` gate, route delegates (chosen) — mirrors `main.py`'s environment seam exactly; extraction also respects RULE-04 (`router_sessions.py` sits at 149/150 lines — an inline `if not settings.is_test:` wrapper would breach the cap); the pure function gives the production-invariance pin a direct home without monkeypatching.
2. Thread a `test_mode` flag through `create_app` → `websocket.app.state` (mirror of the middleware constructor flag): more plumbing for a route-level guard, and it diverges from the `ENVIRONMENT=test` semantics the runner actually sets. Rejected.
3. Add the probe origin to `NARRARE_CSRF_TRUSTED_ORIGINS` in the runner: masks the parity defect and mutates security config suite-wide; spec §8 prescribes honoring test mode, not an allowlist workaround. Rejected.

- [ ] **Step 1: Write the failing route-level test**

Append to `tests/unit/api/writing/test_router_sessions_validation.py` (in the Origin validation section; `AppSettings` is already imported, line 18):

```python
async def test_untrusted_origin_allowed_under_environment_test(
    mock_websocket: AsyncMock,
    chapter_id: UUID,
    project_id: UUID,
) -> None:
    """N08: under ENVIRONMENT=test the origin gate relaxes like REST CSRF.

    Mirrors ``test_empty_origin_is_allowed``: the rate limiter is forced to
    reject so reaching close(4003) PROVES the foreign origin passed the
    origin gate (pre-fix: close(1008) — the red).
    """
    from narrare._app import config as app_config
    from narrare._app.rate_limits import AI_WS_LIMITER

    mock_websocket.headers["origin"] = "http://localhost:9999"
    test_settings = AppSettings(
        environment="test",
        csrf_trusted_origins=["http://localhost:3000"],
    )
    with (
        patch.object(app_config, "get_settings", return_value=test_settings),
        patch.object(AI_WS_LIMITER, "try_acquire", return_value=False),
    ):
        await interactive_session(
            mock_websocket,
            chapter_id,
            token=mint_ws_ticket(USER_ID),
            project_id=project_id,
        )

    mock_websocket.close.assert_awaited_once_with(code=4003, reason="Rate limited")
```

(Calibration: `AppSettings(...)` is a `BaseSettings` — explicit kwargs override ambient env. If any field without a default makes bare construction fail under the unit-test env, pass it explicitly; do NOT drop the explicit `environment=`/`csrf_trusted_origins=` pair — they are the point of the test.)

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --all-packages pytest tests/unit/api/writing/test_router_sessions_validation.py -v -p no:randomly`
Expected: the NEW test FAILS with `close` awaited `code=1008, reason="Origin not allowed"` (the pre-fix rejection); the existing `test_untrusted_origin_returns_error` (default/dev settings) still PASSES — that test is part of the invariance pin. Record output.

- [ ] **Step 3: Implement helper + route delegation**

Create `apps/api/narrare/writing/ws_origin.py`:

```python
"""WS origin validation policy (CSRF defense-in-depth, AUFG-05-13 / ADR-084).

Pure decision helper extracted from ``router_sessions`` (RULE-04: the
router sits at the 150-line cap) so the origin policy is pinnable without
a live socket. Mirrors the REST seam: ``_app/main.py`` does not install
``OriginValidationMiddleware`` when ``settings.is_test`` — the WS gate
honors the same ``ENVIRONMENT=test`` rule (N08). Production deployments
keep the exact pre-fix posture: the bypass is ``is_test``-only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare._app.settings_model import Settings


def origin_is_allowed(origin: str, settings: Settings) -> bool:
    """Return ``True`` when a WS connect carrying *origin* may proceed.

    Rules:
    * ``ENVIRONMENT=test`` → allowed (REST CSRF parity, N08).
    * Empty origin → allowed (non-browser clients; pre-fix behavior).
    * Otherwise → allowed iff listed in ``csrf_trusted_origins``.
    """
    if settings.is_test:
        return True
    if not origin:
        return True
    return origin in settings.csrf_trusted_origins
```

In `apps/api/narrare/writing/router_sessions.py`, replace the origin block (lines ~83-91) with:

```python
    # 3. Origin validation (CSRF defense-in-depth, AUFG-05-13; 1008 per
    #    ADR-084). ENVIRONMENT=test mirrors the REST seam (main.py skips
    #    the middleware under is_test); production posture unchanged (N08).
    from narrare._app.config import get_settings
    from narrare.writing.ws_origin import origin_is_allowed

    if not origin_is_allowed(websocket.headers.get("origin", ""), get_settings()):
        await _close_with_error(websocket, code=1008, reason="Origin not allowed")
        return
```

(RULE-04 discipline: `router_sessions.py` is at 149/150 lines — this replacement nets ≤ +1 line via the extraction. Verify `wc -l` ≤ 150 before commit; trim the comment, not the guard, if over.)

- [ ] **Step 4: Write the policy pins + run everything green**

Create `tests/unit/api/writing/test_ws_origin.py`:

```python
"""Pure policy pins for the WS origin gate (N08 fix, production invariance).

The route-level behavior is pinned in test_router_sessions_validation.py;
these pins fix the POLICY so a future refactor cannot silently relax
production while fixing test mode (or vice versa).
"""

from __future__ import annotations

from narrare._app.config import Settings
from narrare.writing.ws_origin import origin_is_allowed

_TRUSTED = ["http://localhost:3000"]


def _settings(environment: str) -> Settings:
    return Settings(environment=environment, csrf_trusted_origins=_TRUSTED)


def test_foreign_origin_rejected_in_production() -> None:
    assert origin_is_allowed("http://localhost:9999", _settings("production")) is False


def test_trusted_origin_allowed_in_production() -> None:
    assert origin_is_allowed("http://localhost:3000", _settings("production")) is True


def test_empty_origin_allowed_in_production() -> None:
    assert origin_is_allowed("", _settings("production")) is True


def test_foreign_origin_rejected_in_development() -> None:
    """Dev keeps the strict posture too — only is_test relaxes (N08)."""
    assert origin_is_allowed("http://localhost:9999", _settings("development")) is False


def test_foreign_origin_allowed_in_test_environment() -> None:
    assert origin_is_allowed("http://localhost:9999", _settings("test")) is True
```

Run: `uv run --all-packages pytest tests/unit/api/writing/test_ws_origin.py tests/unit/api/writing/test_router_sessions_validation.py tests/unit/api/writing/test_router_sessions_auth.py -v -p no:randomly`
Expected: ALL PASS (new route test now reaches 4003; the pre-existing 1008 rejection test stays green on default/dev settings).

- [ ] **Step 5: Live-stack spot-check (both postures)**

(a) Test posture — with the :3001 recipe (`ENVIRONMENT=test`): run a raw connect from Python (`websockets.sync.client.connect`, header `Origin: http://localhost:9999`, ticket from `POST /api/v1/auth/ws-ticket`) → expect the `greeting` frame. (b) Invariance — restart the API WITHOUT `ENVIRONMENT=test` (development) and repeat → expect the error frame + close 1008. Record both exchanges (this is the production-posture evidence the ruling demands).

- [ ] **Step 6: Commit**

```bash
git add apps/api/narrare/writing/ws_origin.py apps/api/narrare/writing/router_sessions.py tests/unit/api/writing/test_router_sessions_validation.py tests/unit/api/writing/test_ws_origin.py
git commit -m "fix(writing): honor ENVIRONMENT=test in the WS origin check, production posture pinned (N08)"
```

---

### Task 6: Catalog growth — truncated generation, rewrite, story-suggest, co-author

**Layer:** Platform

**Files:**
- Modify: `tests/e2e/mocks/catalog_writing.py` (new fixtures + SPECS entries + validate cases)
- Test: `tests/unit/test_e2e_mock_catalog.py` (extend)

**Interfaces:**
- Produces capabilities (consumed by Tasks 7–9 via `mock_llm`):
  - `generation_stream` variant `"truncated"` — SSE with the `context_meta` event and terminal `[DONE]` but **no text chunk and no `is_final`** (the audit M06 silent-death wire shape; drives Task 3's guard E2E).
  - `rewrite_stream` variants `"happy"` / `"error"` — `POST /api/v1/writing/chapters/*/rewrite*` SSE: `request_info` event, `<alternative label="…">…</alternative>` text chunks, final chunk `is_final` + `usage`, `[DONE]` (wire shape from `packages/web/lib/api/generation-streams.ts` `streamRewrite` + `apps/api/narrare/writing/router_rewrite.py`). Error variant: HTTP 500 JSON body.
  - `story_suggest` variants `"happy"` / `"error"` — `POST /api/v1/writing/story-suggest/*` SSE: one `{"event": "suggestions", "suggestions": […]}` event + `{"event": "done", "is_final": true}` + `[DONE]` (wire shape from `router_story_suggest.py` docstring + `story-suggest-stream.ts`). Error variant: HTTP 500 JSON body.
  - `coauthor_stream` variants `"happy"` / `"error"` — `POST /api/v1/writing/chapters/*/co-author` SSE: `context_meta` event, `{"text": …}` chunks, final event `is_final` + `usage` + `changes: [ChangeDetail…]` + `total_changes` + `has_changes` + `reasoning` + `request_id`, `[DONE]` (wire shape from `apps/api/narrare/writing/router_coauthor.py` docstring + `_coauthor_sse.py` final-event key set + `packages/web/lib/api/coauthor.ts` `streamCoAuthor`). The pattern ends at `/co-author` — full-match semantics leave `/co-author/apply` and `/co-author/feedback` untouched (real backend). Needed by Task 9's co-author REAL happy path: the review/apply phase consumes the structured `changes` payload, so TestModel junk cannot drive it deterministically (same argument as rewrite). Error variant: HTTP 500 JSON body.

- [ ] **Step 1: Write the failing unit tests**

Append to `tests/unit/test_e2e_mock_catalog.py`:

```python
class TestWritingCatalogGrowth:
    def test_generation_stream_truncated_has_no_final_chunk(self) -> None:
        spec = entries_for("generation_stream", "truncated")[0]
        events = assert_sse_body_wellformed(spec.body)
        assert events and events[0]["type"] == "context_meta"
        assert not any(e.get("is_final") for e in events), "truncated = silent death: no is_final"
        assert not any("text" in e for e in events), "truncated emits no draft text"

    def test_rewrite_stream_happy_carries_two_complete_alternatives(self) -> None:
        spec = entries_for("rewrite_stream", "happy")[0]
        assert spec.method == "POST"
        events = assert_sse_body_wellformed(spec.body)
        assert events[0]["type"] == "request_info"
        texts = "".join(str(e.get("text") or "") for e in events)
        assert texts.count('<alternative label="') == texts.count("</alternative>") == 2
        assert any(e.get("is_final") for e in events)

    def test_rewrite_stream_has_error_variant(self) -> None:
        assert entries_for("rewrite_stream", "error")[0].status == 500

    def test_story_suggest_suggestions_validate_against_real_model(self) -> None:
        from narrare_core.agents.story_suggest_types import StorySuggestOutput

        spec = entries_for("story_suggest", "happy")[0]
        events = assert_sse_body_wellformed(spec.body)
        suggestions_event = next(e for e in events if e.get("event") == "suggestions")
        StorySuggestOutput.model_validate({"suggestions": suggestions_event["suggestions"]})
        done = events[-1]
        assert done.get("event") == "done" and done.get("is_final") is True

    def test_story_suggest_has_error_variant(self) -> None:
        assert entries_for("story_suggest", "error")[0].status == 500

    def test_coauthor_stream_final_event_carries_valid_changes(self) -> None:
        from narrare.writing.schemas_coauthor import ChangeDetail

        spec = entries_for("coauthor_stream", "happy")[0]
        assert spec.method == "POST"
        events = assert_sse_body_wellformed(spec.body)
        assert events[0]["type"] == "context_meta"
        final = events[-1]
        assert final.get("is_final") is True
        assert final.get("has_changes") is True
        assert final.get("total_changes") == len(final["changes"])
        for change in final["changes"]:
            ChangeDetail.model_validate(change)  # ChangeDetail.id is a UUID — fixture must use one

    def test_coauthor_stream_has_error_variant(self) -> None:
        assert entries_for("coauthor_stream", "error")[0].status == 500
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --all-packages pytest tests/unit/test_e2e_mock_catalog.py -v -p no:randomly`
Expected: FAIL — `Unknown capability/variant` for each new name. Record output.

- [ ] **Step 3: Implement the catalog entries**

In `tests/e2e/mocks/catalog_writing.py`, add below the existing constants:

```python
GENERATION_TRUNCATED_SSE = _sse(
    json.dumps({"type": "context_meta", "source": "e2e-mock", "word_count": 1420}),
)
# No text chunks, no is_final — the audit-M06 silent stream death.

REWRITE_HAPPY_SSE = _sse(
    json.dumps({"type": "request_info", "request_id": "e2e-mock-rewrite-1"}),
    json.dumps(
        {
            "text": '<alternative label="Tighter">The harbour bell rang twice; '
            "Elara counted each strike the way her mother had taught her.</alternative>"
        }
    ),
    json.dumps(
        {
            "text": '<alternative label="More sensory">Two strikes, iron on iron, '
            "and the taste of salt: the tide gate would seal within the hour.</alternative>"
        }
    ),
    json.dumps(
        {
            "text": "",
            "is_final": True,
            "usage": {"prompt_tokens": 150, "completion_tokens": 40, "total_tokens": 190},
        }
    ),
)

REWRITE_ERROR_BODY = json.dumps({"detail": "e2e-mock: rewrite provider stream died"})

_STORY_SUGGESTIONS = [
    {
        "type": "plot_development",
        "title": "The writ names a rival house",
        "description": "The forged writ Elara bought carries the seal of the house that ruined her family.",
        "connection": "Explains why she hesitates at the gate she fought to reach.",
    },
    {
        "type": "character_moment",
        "title": "Elara counts strikes",
        "description": "Her mother's counting habit becomes the beat that calms her before the bargain.",
        "connection": "Pays off the opening line about the harbour bell.",
    },
    {
        "type": "world_detail",
        "title": "The tide gate law",
        "description": "City law seals the gate for the first hour after the bell; no writ can override it.",
        "connection": "Raises the stakes of the deadline established in chapter one.",
    },
]

STORY_SUGGEST_HAPPY_SSE = _sse(
    json.dumps({"event": "suggestions", "suggestions": _STORY_SUGGESTIONS}),
    json.dumps({"event": "done", "is_final": True}),
)

STORY_SUGGEST_ERROR_BODY = json.dumps({"detail": "e2e-mock: story-suggest provider died"})

_COAUTHOR_CHANGE = {
    # ChangeDetail.id is uuid.UUID (schemas_coauthor.py) — a real UUID string.
    "id": "00000000-0000-0000-0000-00000000c0a1",
    "change_type": "word_choice",
    "original_text": "counted the strikes",
    "revised_text": "counted each strike",
    "index": 0,
}

COAUTHOR_HAPPY_SSE = _sse(
    json.dumps({"type": "context_meta", "source": "e2e-mock", "word_count": 1420}),
    json.dumps({"text": "The harbour bell rang twice before dawn. "}),
    json.dumps({"text": "Elara counted each strike, tasting salt on the wind."}),
    json.dumps(
        {
            "text": "",
            "is_final": True,
            "usage": {"prompt_tokens": 180, "completion_tokens": 52, "total_tokens": 232},
            "changes": [_COAUTHOR_CHANGE],
            "total_changes": 1,
            "has_changes": True,
            "reasoning": "Tightens the image and adds a sensory anchor.",
            "request_id": "e2e-mock-coauthor-1",
        }
    ),
)

COAUTHOR_ERROR_BODY = json.dumps({"detail": "e2e-mock: co-author provider stream died"})
```

Extend `SPECS` with:

```python
    RouteSpec(
        capability="generation_stream",
        variant="truncated",
        pattern="**/api/v1/writing/generation/*/stream",
        method="GET",
        content_type="text/event-stream",
        body=GENERATION_TRUNCATED_SSE,
    ),
    RouteSpec(
        capability="rewrite_stream",
        variant="happy",
        pattern="**/api/v1/writing/chapters/*/rewrite*",
        method="POST",
        content_type="text/event-stream",
        body=REWRITE_HAPPY_SSE,
    ),
    RouteSpec(
        capability="rewrite_stream",
        variant="error",
        pattern="**/api/v1/writing/chapters/*/rewrite*",
        method="POST",
        status=500,
        body=REWRITE_ERROR_BODY,
    ),
    RouteSpec(
        capability="story_suggest",
        variant="happy",
        pattern="**/api/v1/writing/story-suggest/*",
        method="POST",
        content_type="text/event-stream",
        body=STORY_SUGGEST_HAPPY_SSE,
    ),
    RouteSpec(
        capability="story_suggest",
        variant="error",
        pattern="**/api/v1/writing/story-suggest/*",
        method="POST",
        status=500,
        body=STORY_SUGGEST_ERROR_BODY,
    ),
    RouteSpec(
        capability="coauthor_stream",
        variant="happy",
        pattern="**/api/v1/writing/chapters/*/co-author",
        method="POST",
        content_type="text/event-stream",
        body=COAUTHOR_HAPPY_SSE,
    ),
    RouteSpec(
        capability="coauthor_stream",
        variant="error",
        pattern="**/api/v1/writing/chapters/*/co-author",
        method="POST",
        status=500,
        body=COAUTHOR_ERROR_BODY,
    ),
```

Extend `validate()`:

```python
    truncated = next(s for s in SPECS if s.capability == "generation_stream" and s.variant == "truncated")
    truncated_events = assert_sse_body_wellformed(truncated.body)
    assert truncated_events[0]["type"] == "context_meta", "truncated SSE must open with context_meta"
    assert not any(e.get("is_final") for e in truncated_events), "truncated must lack is_final"

    rewrite = next(s for s in SPECS if s.capability == "rewrite_stream" and s.variant == "happy")
    rewrite_events = assert_sse_body_wellformed(rewrite.body)
    rewrite_text = "".join(str(e.get("text") or "") for e in rewrite_events)
    assert rewrite_text.count("<alternative label=") == rewrite_text.count("</alternative>") >= 1

    from narrare_core.agents.story_suggest_types import StorySuggestOutput

    suggest = next(s for s in SPECS if s.capability == "story_suggest" and s.variant == "happy")
    suggest_events = assert_sse_body_wellformed(suggest.body)
    suggestions_event = next(e for e in suggest_events if e.get("event") == "suggestions")
    StorySuggestOutput.model_validate({"suggestions": suggestions_event["suggestions"]})

    from narrare.writing.schemas_coauthor import ChangeDetail

    coauthor = next(s for s in SPECS if s.capability == "coauthor_stream" and s.variant == "happy")
    coauthor_events = assert_sse_body_wellformed(coauthor.body)
    assert coauthor_events[0]["type"] == "context_meta", "co-author SSE must open with context_meta"
    coauthor_final = coauthor_events[-1]
    assert coauthor_final.get("is_final") is True and coauthor_final.get("has_changes") is True
    for change in coauthor_final["changes"]:
        ChangeDetail.model_validate(change)
```

(If `validate_catalog`'s SSE happy+error loop in `tests/e2e/mocks/catalog.py` enumerates capabilities explicitly, add `"rewrite_stream"`, `"story_suggest"`, and `"coauthor_stream"` to that tuple so the ratchet arms for them.)

- [ ] **Step 4: Run the tests to verify green**

Run: `uv run --all-packages pytest tests/unit/test_e2e_mock_catalog.py -v -p no:randomly`
Expected: ALL PASS (session-start conftest ratchet picks the entries up automatically — `foundation.py::_validate_mock_catalog`).

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/mocks/catalog_writing.py tests/unit/test_e2e_mock_catalog.py
git commit -m "test(e2e): catalog entries for truncated generation, rewrite, story-suggest, co-author"
```

---

### Task 7: Spec part 1 — generate (WRITE-002) + editor helper

**Layer:** Platform · **Pins:** M06 (all three fixed behaviors), B-gate substrate for the panel

**Files:**
- Create: `tests/e2e/helpers/editor_ai.py`
- Create: `tests/e2e/test_ai_writing.py`
- Test: the spec IS the test (verified via the runner in Step 4)

**Interfaces:**
- Produces (`tests/e2e/helpers/editor_ai.py`, consumed by Tasks 8–11):
  - `prepare_ai_chapter(page, api_request, novel_id, *, title="AI Flow Chapter", content="") -> dict` — creates a chapter via `novel_factory.create_chapter_via_api`, reloads the editor, selects the chapter in the sidebar (`[data-testid="chapter-item"]` filtered by title), waits for `.ProseMirror`, returns `{"chapter_id": str, "title": str}`.
  - `editor_text(page) -> str` — inner text of the first `.ProseMirror`.
  - `focus_editor_end(page) -> None` — clicks the editor, moves the caret to the document end (`Control+End`).
  - `open_generation_panel(page) -> None` — clicks the toolbar Generate button (`get_by_role("button", name="Generate", exact=True)`).
- Produces (`tests/e2e/test_ai_writing.py`): module fixture `ai_novel` (module-scoped: `module_stable_user` + one `complete_wizard` blank-starter novel) — per-test chapters keep tests independent on the shared page (navigate explicitly at each test start, per the `module_stable_user` contract).

**Test inventory (WRITE-002 scope: "generate modes happy + empty-422 + stream-death paths"):**

| Test | Path | Mock |
|---|---|---|
| `test_full_draft_happy_accept_inserts_into_editor` | generate → draft → Accept → editor contains fixture text; accept POST 200 | `generation_stream` happy |
| `test_full_draft_reject_leaves_editor_unchanged` | generate → draft → Reject → editor unchanged; rating prompt appears | `generation_stream` happy |
| `test_empty_form_shows_localized_validation_not_connection_lost` (M06) | empty prompt/outline → Generate → localized message; 422 observed on the wire | none (REAL backend 422) |
| `test_stream_http_error_shows_error_phase_without_accept` (M06) | Generate → HTTP 500 stream → error phase + Retry; no Accept button | `generation_stream` error |
| `test_truncated_stream_never_reaches_review_with_empty_draft` (M06) | Generate → silent end → error phase; no "Waiting for AI response…" review state with enabled Accept | `generation_stream` truncated |

- [ ] **Step 1: Create the helper**

Create `tests/e2e/helpers/editor_ai.py`:

```python
"""Editor prep for AI-writing E2E specs (spec §4 helpers package).

Owns the recurring "put the editor into a known state" concerns so the
AI-writing specs assert instead of navigating: chapter seeding via API,
sidebar selection, editor text/caret access, and the generation-panel
entry point. No auth or wizard concerns (RULE-04 — compose with the
conftest stable_* fixtures and novel_factory).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from tests.e2e.helpers.novel_factory import create_chapter_via_api

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests
    from playwright.sync_api import Page

_EDITOR_SELECTOR = ".ProseMirror"
_SIDEBAR_CHAPTER = '[data-testid="chapter-item"]'
_UI_WAIT_MS: int = 15_000


def prepare_ai_chapter(
    page: Page,
    api_request: Callable[..., requests.Response],
    novel_id: str,
    *,
    title: str = "AI Flow Chapter",
    content: str = "",
) -> dict[str, str]:
    """Create a chapter via API and open it in the editor.

    Returns ``{"chapter_id": …, "title": …}``. Reloads the novel page so the
    sidebar picks up the new chapter, then selects it by title (the editor
    auto-selects the FIRST chapter — ours is newest/last).
    """
    created = create_chapter_via_api(api_request, novel_id, title=title, content=content)
    page.reload()
    page.wait_for_load_state("domcontentloaded")
    chapter_button = page.locator(_SIDEBAR_CHAPTER, has_text=re.compile(re.escape(title)))
    chapter_button.last.wait_for(state="visible", timeout=_UI_WAIT_MS)
    chapter_button.last.click()
    page.locator(_EDITOR_SELECTOR).first.wait_for(state="visible", timeout=_UI_WAIT_MS)
    return {"chapter_id": created["id"], "title": title}


def editor_text(page: Page) -> str:
    """The editor's visible text (assertion basis for AI insertions)."""
    return page.locator(_EDITOR_SELECTOR).first.inner_text()


def focus_editor_end(page: Page) -> None:
    """Focus the editor and place the caret at the document end."""
    editor = page.locator(_EDITOR_SELECTOR).first
    editor.click()
    page.keyboard.press("Control+End")


def open_generation_panel(page: Page) -> None:
    """Open the right-hand generation panel from the toolbar."""
    page.get_by_role("button", name="Generate", exact=True).click()
    page.get_by_text("AI Generation").first.wait_for(state="visible", timeout=_UI_WAIT_MS)
```

- [ ] **Step 2: Write the spec**

Create `tests/e2e/test_ai_writing.py`:

```python
"""AI-writing E2E specs — chapter generation (WRITE-002).

Drives the REAL generation panel against the real stack: the START POST and
accept/reject hit the real backend; the validator-strict generation STREAM
is deterministic via the browser-layer catalog (audit E04). Pins the three
fixed M06 behaviors (localized empty-input 422, stream-death error phase,
no empty-draft review) plus the happy accept/reject flows.

Runtime budget: ≤ 3 min (spec §7 — full suite ≤ 25 min). Markers: e2e.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.e2e.config import BASE_URL
from tests.e2e.foundation import NovelContext
from tests.e2e.helpers import capture_network, mock_llm
from tests.e2e.helpers.editor_ai import editor_text, open_generation_panel, prepare_ai_chapter
from tests.e2e.helpers.novel_factory import complete_wizard

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests as http_requests
    from playwright.sync_api import Page


@pytest.fixture(scope="module")
def ai_novel(module_stable_user, api_request) -> NovelContext:
    """One wizard novel per module; tests create their own chapters."""
    novel = complete_wizard(module_stable_user.page, BASE_URL)
    return NovelContext(
        page=module_stable_user.page,
        novel_id=novel["novel_id"],
        email=module_stable_user.email,
        password=module_stable_user.password,
        access_token=module_stable_user.access_token,
    )


@pytest.mark.e2e
class TestGenerateFullDraft:
    def test_full_draft_happy_accept_inserts_into_editor(
        self, ai_novel: NovelContext, api_request: Callable[..., http_requests.Response]
    ) -> None:
        page = ai_novel.page
        network = capture_network(page)
        mock_llm(page, "generation_stream")  # happy variant

        prepare_ai_chapter(page, api_request, ai_novel.novel_id, title="Generate Happy")
        open_generation_panel(page)

        page.get_by_placeholder("What should the AI write about?").fill(
            "Elara waits at the sealed tide gate."
        )
        page.get_by_role("button", name="Generate", exact=True).click()

        draft = page.locator(".ProseMirror, [contenteditable='true']").first
        page.get_by_text("harbour bell").first.wait_for(state="visible", timeout=30_000)
        page.get_by_role("button", name="Accept", exact=True).click()

        # The accepted draft lands in the editor (onDraftAccepted).
        page.wait_for_function(
            "() => document.querySelector('.ProseMirror')?.innerText.includes('harbour bell')",
            timeout=30_000,
        )
        assert "harbour bell" in editor_text(page)
        network.assert_no_provider_calls()
        assert draft.is_visible()

    def test_full_draft_reject_leaves_editor_unchanged(
        self, ai_novel: NovelContext, api_request: Callable[..., http_requests.Response]
    ) -> None:
        page = ai_novel.page
        mock_llm(page, "generation_stream")

        chapter = prepare_ai_chapter(
            page, api_request, ai_novel.novel_id, title="Generate Reject", content="Original opening line."
        )
        before = editor_text(page)
        open_generation_panel(page)

        page.get_by_placeholder("What should the AI write about?").fill("A rejected draft.")
        page.get_by_role("button", name="Generate", exact=True).click()
        page.get_by_text("harbour bell").first.wait_for(state="visible", timeout=30_000)

        page.get_by_role("button", name="Reject", exact=True).click()
        # Reject shows the rating prompt; the editor keeps the original text.
        page.get_by_text("Rate this suggestion").first.wait_for(state="visible", timeout=15_000)
        assert editor_text(page).strip().startswith("Original opening line.")
        assert "harbour bell" not in editor_text(page)
        assert chapter["title"]


@pytest.mark.e2e
class TestGenerateErrorPaths:
    def test_empty_form_shows_localized_validation_not_connection_lost(
        self, ai_novel: NovelContext, api_request: Callable[..., http_requests.Response]
    ) -> None:
        """M06 pin: empty-form 422 MISSING_INPUT renders the honest localized
        message (was: hardcoded German 'connection lost')."""
        page = ai_novel.page
        network = capture_network(page)

        prepare_ai_chapter(page, api_request, ai_novel.novel_id, title="Generate Empty 422")
        open_generation_panel(page)

        page.get_by_role("button", name="Generate", exact=True).click()  # empty form

        alert = page.get_by_role("alert")
        alert.wait_for(state="visible", timeout=15_000)
        assert (
            "At least one of outline, prompt, or auto-continue must be provided."
            in alert.inner_text()
        ), "M06: the empty-form 422 must map to generationPanel.validationMissingInput"
        assert "Verbindung" not in alert.inner_text(), "M06: German connection-lost fallback must be gone"
        network.assert_no_api_failures(allow_statuses=(422,))  # the real backend 422 is expected

    def test_stream_http_error_shows_error_phase_without_accept(
        self, ai_novel: NovelContext, api_request: Callable[..., http_requests.Response]
    ) -> None:
        """M06 pin: an HTTP-500 generation stream lands in the error phase
        with Retry — never a review phase with Accept."""
        page = ai_novel.page
        mock_llm(page, "generation_stream", fixture="error")

        prepare_ai_chapter(page, api_request, ai_novel.novel_id, title="Generate Stream 500")
        open_generation_panel(page)

        page.get_by_placeholder("What should the AI write about?").fill("A doomed generation.")
        page.get_by_role("button", name="Generate", exact=True).click()

        page.get_by_role("button", name="Retry", exact=True).wait_for(state="visible", timeout=30_000)
        assert page.get_by_role("button", name="Accept", exact=True).count() == 0, (
            "M06: the error phase must not offer Accept"
        )

    def test_truncated_stream_never_reaches_review_with_empty_draft(
        self, ai_novel: NovelContext, api_request: Callable[..., http_requests.Response]
    ) -> None:
        """M06 pin (the audit repro): a stream that ends silently — no text,
        no is_final — must produce the error phase, not 'Waiting for AI
        response…' with an enabled Accept."""
        page = ai_novel.page
        mock_llm(page, "generation_stream", fixture="truncated")

        prepare_ai_chapter(page, api_request, ai_novel.novel_id, title="Generate Truncated")
        open_generation_panel(page)

        page.get_by_placeholder("What should the AI write about?").fill("A silent death.")
        page.get_by_role("button", name="Generate", exact=True).click()

        page.get_by_role("button", name="Retry", exact=True).wait_for(state="visible", timeout=30_000)
        assert page.get_by_role("button", name="Accept", exact=True).count() == 0
```

Note: the happy-path test's `draft` locator is the editor element itself — keep it (it pins that the editor stayed mounted through the accept flow) but drop it if reviewers find it redundant; the material assertions are the `wait_for_function` + `editor_text` checks.

- [ ] **Step 3: Syntax-check and collect**

Run: `uv run --all-packages pytest tests/e2e/test_ai_writing.py --collect-only -q -m e2e`
Expected: 5 tests collected, no import errors.

- [ ] **Step 4: Run the spec (CI-faithful)**

Run: `E2E_PYTEST_ARGS="tests/e2e/test_ai_writing.py" just e2e`
Expected: 5 PASS within the ≤ 3 min module budget. If a selector misses (label drift), fix the selector against the live UI using the :3001 recipe — do NOT relax the assertion.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/helpers/editor_ai.py tests/e2e/test_ai_writing.py
git commit -m "test(e2e): WRITE-002 generation spec — happy/empty-422/stream-death (M06 pins)"
```

---

### Task 8: Spec part 2a — extend (WRITE-003, B08) + rewrite (WRITE-004, B01)

**Layer:** Platform · **Pins:** B08 (toolbar extend wiring), B01 (rewrite ≤500 context, modal + preview reachable, Replace applies)

**Files:**
- Create: `tests/e2e/test_ai_writing_selection.py`
- Test: the spec IS the test

**Interfaces:**
- Consumes: `helpers/editor_ai.prepare_ai_chapter/editor_text/focus_editor_end` (Task 7), catalog `rewrite_stream` happy (Task 6), TestModel factory layer for extend (spec §3: extend is tolerance-loose — audit proved the endpoint streams 200 SSE under TestModel).
- Produces: the file's module fixture `sel_novel` (same shape as Task 7's `ai_novel`).

**Mock decision (extend):** extend streams plain text appended at the caret — no validator-strict output (audit E04 does not list it; B08 evidence proved the SSE healthy under the audit's TestModel stack). The test asserts growth + persistence, not exact text — the factory layer stays exercised (spec §3 layer 1).

- [ ] **Step 1: Write the spec**

Create `tests/e2e/test_ai_writing_selection.py`:

```python
"""AI-writing E2E specs — selection tools: extend, rewrite, co-author, unblock.

WRITE-003 extend (B08 pin: toolbar wiring), WRITE-004 rewrite (B01 pin:
500-char context compliance, modal/preview reachable, Replace applies).
Extend runs on the TestModel factory layer (tolerance-loose, spec §3);
rewrite is deterministic via the browser-layer catalog (FE parses
``<alternative>`` tags — TestModel output would be junk for Apply paths).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.e2e.config import BASE_URL
from tests.e2e.foundation import NovelContext
from tests.e2e.helpers import capture_network, mock_llm
from tests.e2e.helpers.editor_ai import editor_text, focus_editor_end, prepare_ai_chapter
from tests.e2e.helpers.novel_factory import complete_wizard

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests as http_requests
    from playwright.sync_api import Page

_EXTEND_SEED = (
    "The harbour bell rang twice before dawn, and Elara counted the strikes "
    "the way her mother had taught her. Two strikes meant the tide gate would "
    "seal within the hour."
)


@pytest.fixture(scope="module")
def sel_novel(module_stable_user, api_request) -> NovelContext:
    novel = complete_wizard(module_stable_user.page, BASE_URL)
    return NovelContext(
        page=module_stable_user.page,
        novel_id=novel["novel_id"],
        email=module_stable_user.email,
        password=module_stable_user.password,
        access_token=module_stable_user.access_token,
    )


@pytest.mark.e2e
class TestExtend:
    def test_continue_writing_appends_text_at_caret(
        self, sel_novel: NovelContext, api_request: Callable[..., http_requests.Response]
    ) -> None:
        """B08 pin: the toolbar Continue button is wired and streams into the
        editor (pre-fix: never rendered / stub no-op)."""
        page = sel_novel.page
        network = capture_network(page)

        prepare_ai_chapter(
            page, api_request, sel_novel.novel_id, title="Extend Chapter", content=_EXTEND_SEED
        )
        focus_editor_end(page)
        before = len(editor_text(page))
        assert before > 0

        page.get_by_role("button", name="Continue writing").click()

        page.wait_for_function(
            """(before) => document.querySelector('.ProseMirror')?.innerText.length > before + 10""",
            arg=before,
            timeout=60_000,
        )
        grown = editor_text(page)
        assert grown.startswith(_EXTEND_SEED.split(".")[0])  # append, not replace
        network.assert_no_provider_calls()


@pytest.mark.e2e
class TestRewrite:
    def test_rewrite_modal_preview_and_replace_applies_alternative(
        self, sel_novel: NovelContext, api_request: Callable[..., http_requests.Response]
    ) -> None:
        """B01 pin: select text → AI rewrite → modal stays open with a
        preview → Replace swaps the selection (pre-fix: guaranteed 422 +
        silent modal close)."""
        page = sel_novel.page
        mock_llm(page, "rewrite_stream")  # happy variant

        prepare_ai_chapter(
            page, api_request, sel_novel.novel_id, title="Rewrite Chapter", content=_EXTEND_SEED
        )

        editor = page.locator(".ProseMirror").first
        editor.click()
        page.keyboard.press("Control+a")  # ~150-char selection < 2000 cap

        page.get_by_role("button", name="AI rewrite").click()
        page.get_by_text("Rewrite Selection").first.wait_for(state="visible", timeout=15_000)

        page.get_by_role("button", name="Generate", exact=True).click()

        page.get_by_text("Tighter").first.wait_for(state="visible", timeout=30_000)

        page.get_by_role("button", name="Replace", exact=True).click()

        page.wait_for_function(
            """() => document.querySelector('.ProseMirror')?.innerText.includes('Tighter') === false
                && document.querySelector('.ProseMirror')?.innerText.includes('iron on iron')""",
            timeout=30_000,
        )
        # The alternative replaced the original selection.
        assert "iron on iron" in editor_text(page)
        assert "counted the strikes" not in editor_text(page)
```

(The final `wait_for_function` guards the label-vs-body distinction: the "Tighter" label may appear in the editor? No — Replace inserts the alternative TEXT ("iron on iron"), not the label; the guard asserts the body marker while allowing label remnants to vanish with the modal.)

- [ ] **Step 2: Collect + run**

Run: `uv run --all-packages pytest tests/e2e/test_ai_writing_selection.py --collect-only -q -m e2e`
Expected: 2 tests collected.
Run: `E2E_PYTEST_ARGS="tests/e2e/test_ai_writing_selection.py" just e2e`
Expected: 2 PASS. If the bubble menu needs a wider selection than Ctrl+A yields in a heading-less paragraph, keep Ctrl+A (whole ~150-char chapter) — it is within `MIN/MAX_SELECTION_LENGTH`.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_ai_writing_selection.py
git commit -m "test(e2e): WRITE-003 extend + WRITE-004 rewrite specs (B08/B01 pins)"
```

---

### Task 9: Spec part 2b — unblock (WRITE-009, B02) + co-author (WRITE-006, B09 real path)

**Layer:** Platform · **Pins:** B02 (novel_id body fix → suggestions render + insert), B09 residual FIXED by Task 4 (PO ruling 1) — this task pins the REAL happy path (selection → bubble-menu → panel → apply) plus the slash wiring pin. No xfail.

**Files:**
- Modify: `tests/e2e/test_ai_writing_selection.py` (append two classes)
- Test: the spec IS the test

**Interfaces:**
- Consumes: catalog `story_suggest` happy + `coauthor_stream` happy (Task 6), `helpers/editor_ai` (Task 7), and Task 4's bubble-menu entry (`bubble.coAuthor` = "Co-Author", rendered exactly when a selection exists).
- Produces: the WRITE-006 real-path pin — the full user journey through real input: select a passage → bubble-menu Co-Author → overlay opens carrying the passage → Start → streamed revision with structured changes → apply replaces the selection in the editor — plus the B09 slash wiring pin (listed command whose selection-less dispatch is a guarded no-op).

**Ruling encoded (co-author real path, PO ruling 1 — Decisions log D-2026-10-13-1):** the slash trigger provably cannot carry a selection (activation grammar `^(\s*)/([^\s/]*)$` + `selectIndex` deleting `slashPos..selection.to`), so the reachability fix landed as Task 4's bubble-menu entry BEFORE this spec ("fixes zuerst"). This task therefore pins the FIXED flow green. The slash entry stays as-is: the panel does not support selection-less opening (Task 4 verified: `handleStartCoAuthor`'s empty-text guard no-ops, `CoAuthorOverlay` mounts only for a non-null selection) — the wiring test below pins that availability gate.

**Apply-path note (deliberate):** the happy path applies with ALL changes accepted (the panel default — `useCoAuthorStream` seeds acceptance all-true). All-accepted apply is client-side (`onAccept(streamedText)` in `useCoAuthorApply`) — no `/co-author/apply` call. A partial apply would POST the REAL `/co-author/apply` with the catalog mock's `request_id`, which the (correctly unmocked) backend rejects as unknown — the catalog pattern ends at `/co-author` on purpose (Task 6). The E2E pins the all-accepted journey; partial-apply remains integration-test surface.

- [ ] **Step 1: Append the spec classes**

Append to `tests/e2e/test_ai_writing_selection.py`:

```python
@pytest.mark.e2e
class TestUnblock:
    def test_unblock_suggestions_render_and_insert(
        self, sel_novel: NovelContext, api_request: Callable[..., http_requests.Response]
    ) -> None:
        """B02 pin: the panel fetches suggestions (novel_id in the body —
        pre-fix 422 'Field required') and Accept inserts into the editor."""
        page = sel_novel.page
        mock_llm(page, "story_suggest")  # happy variant

        prepare_ai_chapter(page, api_request, sel_novel.novel_id, title="Unblock Chapter")
        focus_editor_end(page)

        page.get_by_role("button", name="Writer's Unblock").click()
        page.get_by_text("Get Suggestions").wait_for(state="visible", timeout=15_000)

        page.get_by_placeholder("I'm stuck because…").fill("The gate scene has no way forward.")
        page.get_by_role("button", name="Get Suggestions").click()

        first_card = page.get_by_text("The writ names a rival house").first
        first_card.wait_for(state="visible", timeout=30_000)

        # Insert the first suggestion at the caret (aiActions.accept on the card).
        page.get_by_role("button", name="Accept", exact=True).first.click()

        page.wait_for_function(
            "() => document.querySelector('.ProseMirror')?.innerText.includes('rival house')",
            timeout=30_000,
        )
        assert "rival house" in editor_text(page)


@pytest.mark.e2e
class TestCoAuthor:
    def test_slash_menu_lists_coauthor_as_wired_command(self, sel_novel, api_request) -> None:
        """B09 wiring pin: the slash menu offers Co-Author as a real command
        (pre-fix: stub 'Not available here'), and the no-selection guard is
        an actionable no-op (availability gating)."""
        page = sel_novel.page

        prepare_ai_chapter(page, api_request, sel_novel.novel_id, title="CoAuthor Slash")
        editor = page.locator(".ProseMirror").first
        editor.click()
        page.keyboard.press("Control+End")
        page.keyboard.press("Enter")  # fresh empty paragraph
        page.keyboard.type("/")

        page.get_by_text("Co-Author", exact=True).first.wait_for(state="visible", timeout=15_000)

        # Without a selection the command must not dispatch (guarded no-op):
        page.get_by_text("Co-Author", exact=True).first.click()
        page.wait_for_timeout(500)
        assert page.get_by_text("Co-Author", exact=True).count() == 0 or not page.locator(
            ".fixed.inset-0"
        ).count(), "no-selection dispatch must not open the overlay"

    def test_selected_passage_bubble_entry_full_coauthor_flow(
        self, sel_novel: NovelContext, api_request: Callable[..., http_requests.Response]
    ) -> None:
        """WRITE-006 real happy path (PO ruling 1; fix = Task 4's bubble
        entry): select a passage → bubble Co-Author → overlay carries the
        passage → Start → streamed revision with structured changes →
        apply replaces the selection in the editor. No xfail — fixed path."""
        page = sel_novel.page
        network = capture_network(page)
        mock_llm(page, "coauthor_stream")  # happy variant (Task 6)

        prepare_ai_chapter(
            page, api_request, sel_novel.novel_id, title="CoAuthor Happy", content=_EXTEND_SEED
        )
        editor = page.locator(".ProseMirror").first
        editor.click()
        page.keyboard.press("Control+a")

        # Task 4's selection-carrying trigger (the slash trigger provably
        # cannot carry one — Decisions log D-2026-10-13-1).
        page.get_by_role("button", name="Co-Author", exact=True).first.click()

        # The overlay opens in the focus phase carrying the passage.
        overlay = page.locator(".fixed.inset-0").first
        overlay.wait_for(state="visible", timeout=15_000)
        assert "30 words selected" in overlay.inner_text(), (
            "the overlay must open carrying the selected passage "
            "(calibrate the count on :3001 if the doc model shifts a word boundary)"
        )

        page.get_by_role("button", name="Start", exact=True).click()

        # Review phase: the final event's structured changes render as a diff
        # ("counted the strikes" → "counted each strike", Task 6 fixture).
        page.get_by_text("1 improvements found").first.wait_for(state="visible", timeout=30_000)
        assert "counted each strike" in overlay.inner_text()

        # Apply with all changes accepted (the panel default). Deliberately
        # the all-accepted path: it applies client-side (onAccept), while a
        # partial apply would POST the REAL /co-author/apply with the mock's
        # request_id and correctly fail (see the task's apply-path note).
        # Two "Accept All" buttons exist (header chip + primary apply) —
        # .last is the primary apply button.
        page.get_by_role("button", name="Accept All").last.click()

        page.get_by_text("Changes applied successfully").first.wait_for(
            state="visible", timeout=15_000
        )
        page.get_by_test_id("coauthor-done-close").click()
        overlay.wait_for(state="detached", timeout=10_000)

        # The streamed revision replaced the selected passage in the editor.
        assert "tasting salt on the wind" in editor_text(page)
        assert "the way her mother" not in editor_text(page), (
            "the original passage must be replaced, not appended"
        )
        network.assert_no_provider_calls()
```

(The `Get Suggestions` textarea placeholder: verify against the live UI on :3001 — the i18n table shows `unblock.stuckLabel`/`getSuggestions`; if the placeholder differs, target `textarea` inside the unblock panel. Adjust before commit; do not weaken the insert assertion.)

- [ ] **Step 2: Collect + run**

Run: `uv run --all-packages pytest tests/e2e/test_ai_writing_selection.py --collect-only -q -m e2e`
Expected: 4 tests collected.
Run: `E2E_PYTEST_ARGS="tests/e2e/test_ai_writing_selection.py" just e2e`
Expected: 4 PASS within the ≤ 2 min module budget (the co-author real happy path replaced the former fast-failing xfail pin — PO ruling 1). If the bubble entry never appears, Task 4 regressed — fix there, not here.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_ai_writing_selection.py
git commit -m "test(e2e): WRITE-009 unblock + WRITE-006 co-author real-path specs (B02 pin, B09 fixed-path + slash wiring pins)"
```

---

### Task 10: Spec part 1b — ghost text (WRITE-007)

**Layer:** Platform

**Files:**
- Modify: `tests/e2e/test_ai_writing.py` (append one class)

**Interfaces:**
- Consumes: TestModel factory layer (spec §3: ghost text is a tolerance-loose surface; audit verified suggest + Tab-accept + Ctrl+Z working), `helpers/editor_ai` (Task 7), GhostText DOM contract `.ghost-text-suggestion` (`extensions/GhostText.ts:273`, aria-hidden decoration).

- [ ] **Step 1: Append the spec class**

Append to `tests/e2e/test_ai_writing.py`:

```python
@pytest.mark.e2e
class TestGhostText:
    def test_ghost_text_tab_accept_inserts_suggestion(
        self, ai_novel: NovelContext, api_request: Callable[..., http_requests.Response]
    ) -> None:
        """WRITE-007: an inline suggestion appears after typing; Tab accepts
        it into the document."""
        page = ai_novel.page
        network = capture_network(page)

        prepare_ai_chapter(page, api_request, ai_novel.novel_id, title="Ghost Accept")
        editor = page.locator(".ProseMirror").first
        editor.click()
        page.keyboard.type("Elara waited at the gate ")

        ghost = page.locator(".ghost-text-suggestion").first
        ghost.wait_for(state="visible", timeout=30_000)

        before = editor_text(page)
        page.keyboard.press("Tab")

        page.wait_for_function(
            """(before) => document.querySelector('.ProseMirror')?.innerText.length > before""",
            arg=len(before),
            timeout=10_000,
        )
        network.assert_no_provider_calls()

    def test_ghost_text_escape_dismisses_suggestion(
        self, ai_novel: NovelContext, api_request: Callable[..., http_requests.Response]
    ) -> None:
        """WRITE-007: Escape clears the suggestion without inserting."""
        page = ai_novel.page

        prepare_ai_chapter(page, api_request, ai_novel.novel_id, title="Ghost Dismiss")
        editor = page.locator(".ProseMirror").first
        editor.click()
        page.keyboard.type("Elara waited at the gate ")

        ghost = page.locator(".ghost-text-suggestion").first
        ghost.wait_for(state="visible", timeout=30_000)
        before = editor_text(page)

        page.keyboard.press("Escape")

        page.locator(".ghost-text-suggestion").wait_for(state="detached", timeout=10_000)
        assert editor_text(page) == before  # dismissed, nothing inserted
```


- [ ] **Step 2: Collect + run**

Run: `E2E_PYTEST_ARGS="tests/e2e/test_ai_writing.py" just e2e`
Expected: 7 PASS (5 from Task 7 + 2 ghost-text) within the ≤ 3 min module budget. Ghost-text appearance under headless Chromium is audit-verified; if the decoration never appears, FAIL loudly (regression-first — no retry loop, no skip).

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_ai_writing.py
git commit -m "test(e2e): WRITE-007 ghost text accept/dismiss specs"
```

---

### Task 11: WS session full flow (WRITE-005) + N08 test-mode pin (spec §8, fixed by Task 5)

**Layer:** Platform · **Pins:** WRITE-005 full flow (audit-proven wire sequence), N08 FIXED by Task 5 (PO ruling 2) — pinned GREEN here for test mode; production invariance unit-pinned in Task 5

**Files:**
- Create: `tests/e2e/helpers/ws_probe.py` (extracted from `tests/e2e/test_ws_ticket_session.py`)
- Create: `tests/e2e/test_ai_writing_ws.py`
- Modify: `tests/e2e/test_ws_ticket_session.py` (import the extracted tracker — no behavior change)

**Interfaces:**
- Produces (`helpers/ws_probe.py`): `WritingSocketTracker(page)` with `.sockets` (list of `SocketRecord(url, frames, sent)`), `.urls`, `.frame_types(i)`, `.sent_types(i)` — the exact surface `test_ws_ticket_session.py` uses privately today (verbatim move; `_SocketRecord`, `_append_text_frame`, `_json_frame_types` become module members without the leading underscore where they are part of the helper's API).
- Produces (`test_ai_writing_ws.py`): the full WRITE-005 flow pin and the N08 pin (sync `websockets` client, available via `uvicorn[standard]`; v16 `additional_headers`).

**N08 pin semantics (fixed path, PO ruling 2 — Decisions log D-2026-10-13-2):** the fix landed in Task 5 — the origin gate delegates to `origin_is_allowed`, which honors `settings.is_test` exactly like the REST seam (`_app/main.py` skips the middleware under `is_test`). This spec pins the FIXED observable behavior GREEN: under the runner (`ENVIRONMENT=test`), a ticketed WS connect with a NON-allowlisted Origin reaches the `greeting` frame — no xfail. The production posture (foreign origin → 1008) cannot be driven by this runner — it boots exactly one API, under test mode — so that regression is pinned where it lives: Task 5's pure policy pins (`tests/unit/api/writing/test_ws_origin.py`, production AND development settings) plus the pre-existing route-level rejection test, and Task 5's live-stack both-postures spot-check. A failure of the green pin here means Task 5 regressed — route the fix there, never to this spec.

- [ ] **Step 1: Extract the WS observation helper**

Create `tests/e2e/helpers/ws_probe.py` by moving `_SocketRecord` → `SocketRecord`, `_append_text_frame` → `append_text_frame`, `_json_frame_types` → `json_frame_types`, and `_WritingSocketTracker` → `WritingSocketTracker` out of `tests/e2e/test_ws_ticket_session.py` (keep the HMR-filter + framereceived/framesent wiring identical, docstring credited to the ADR-084 acceptance gate).

In `tests/e2e/test_ws_ticket_session.py`, replace the moved block with:

```python
from tests.e2e.helpers.ws_probe import WritingSocketTracker as _WritingSocketTracker
```

(keep the alias so the test body is untouched).

- [ ] **Step 2: Write the spec**

Create `tests/e2e/test_ai_writing_ws.py`:

```python
"""AI-writing E2E specs — WS interactive session (WRITE-005) + N08 pin.

Full-flow pin (audit-verified wire sequence, driven through the REAL UI):
ticket → WS connect → greeting → user_direction → text_chunk* → text_done
(with usage) → Add to Draft → save_to_chapter ("Draft saved to chapter!")
→ end_session → clean close. TestModel powers the turn (spec §3 layer 1).

N08 pin (spec §8, FIXED by Task 5 — PO ruling 2): the WS origin gate now
honors ENVIRONMENT=test exactly like REST CSRF. Pinned GREEN here: a
ticketed connect from a non-allowlisted origin reaches the greeting under
the runner's test mode. The production-settings rejection is unit-pinned
in Task 5 (tests/unit/api/writing/test_ws_origin.py + the route-level
rejection test) — the E2E runner boots one API, under test mode only.

Runtime budget: ≤ 90 s. Markers: e2e.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from tests.e2e.config import API_URL, BASE_URL
from tests.e2e.foundation import NovelContext
from tests.e2e.helpers.editor_ai import prepare_ai_chapter
from tests.e2e.helpers.novel_factory import complete_wizard
from tests.e2e.helpers.ws_probe import WritingSocketTracker

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests as http_requests
    from playwright.sync_api import Page


def _wait_until(page: Page, predicate, *, timeout_s: float, description: str) -> None:
    import time

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        page.wait_for_timeout(250)
    raise AssertionError(f"Timed out after {timeout_s}s waiting for: {description}")


@pytest.fixture(scope="module")
def ws_novel(module_stable_user, api_request) -> NovelContext:
    novel = complete_wizard(module_stable_user.page, BASE_URL)
    return NovelContext(
        page=module_stable_user.page,
        novel_id=novel["novel_id"],
        email=module_stable_user.email,
        password=module_stable_user.password,
        access_token=module_stable_user.access_token,
    )


@pytest.mark.e2e
class TestWsSessionFullFlow:
    def test_direction_turn_usage_save_and_clean_end(
        self, ws_novel: NovelContext, api_request: Callable[..., http_requests.Response]
    ) -> None:
        page = ws_novel.page
        tracker = WritingSocketTracker(page)

        prepare_ai_chapter(page, api_request, ws_novel.novel_id, title="WS Flow Chapter")

        # Open the session through the generation panel (WRITE-005 UI path).
        page.get_by_role("button", name="Generate", exact=True).click()
        page.get_by_role("button", name="Interactive", exact=True).click()
        page.get_by_role("button", name="Start Session", exact=True).click()

        _wait_until(page, lambda: len(tracker.sockets) >= 1, timeout_s=20,
                    description="writing-session WebSocket to open")
        _wait_until(page, lambda: "greeting" in tracker.frame_types(0), timeout_s=20,
                    description="greeting frame")
        page.locator('span[title="Connected"]').first.wait_for(state="visible", timeout=15_000)

        # One turn: user_direction → text_chunk* → text_done with usage.
        page.get_by_placeholder("Type your direction...").fill(
            "Elara bargains with the gatekeeper."
        )
        page.get_by_role("button", name="Send", exact=True).click()
        _wait_until(page, lambda: "user_direction" in tracker.sent_types(0), timeout_s=10,
                    description="user_direction client frame")
        _wait_until(page, lambda: "text_chunk" in tracker.frame_types(0), timeout_s=60,
                    description="first text_chunk frame (TestModel turn)")
        _wait_until(page, lambda: "text_done" in tracker.frame_types(0), timeout_s=60,
                    description="text_done frame with usage")
        done = next(json.loads(f) for f in tracker.sockets[0].frames if '"text_done"' in f)
        assert done.get("usage"), f"text_done must carry usage (N09-adjacent contract): {done}"

        # Draft-gated save (audit N09 reality): Save to Chapter is disabled
        # until a message is added to the draft.
        save_button = page.get_by_role("button", name="Save to Chapter")
        assert save_button.is_disabled(), "N09: save is draft-gated — pin current behavior"

        page.get_by_role("button", name="Add to Draft", exact=True).first.click()
        _wait_until(page, lambda: not save_button.is_disabled(), timeout_s=10,
                    description="Save to Chapter enabled after Add to Draft")
        save_button.click()
        page.get_by_text("Draft saved to chapter!").first.wait_for(state="visible", timeout=20_000)

        # Clean end: end_session client frame → server closes the socket.
        page.get_by_role("button", name="End Session", exact=True).click()
        _wait_until(page, lambda: "end_session" in tracker.sent_types(0), timeout_s=10,
                    description="end_session client frame")
        _wait_until(page, lambda: tracker.sockets[0].raw.is_closed(), timeout_s=10,
                    description="writing-session WebSocket closed")


@pytest.mark.e2e
class TestWsOriginTestMode:
    def test_ws_origin_check_honors_test_mode(
        self, ws_novel: NovelContext, api_request: Callable[..., http_requests.Response]
    ) -> None:
        """N08 GREEN pin (fix = Task 5): under ENVIRONMENT=test the origin
        gate relaxes exactly like REST CSRF — a ticketed WS connect with
        Origin http://localhost:9999 (not in the allowlist) reaches the
        greeting. Production invariance (foreign origin still rejected
        outside test mode) is unit-pinned by Task 5's policy pins and the
        pre-existing route-level rejection test."""
        from websockets.sync.client import connect

        chapter = prepare_ai_chapter(
            ws_novel.page, api_request, ws_novel.novel_id, title="WS Origin Chapter"
        )

        ticket_resp = api_request(
            "POST",
            "/api/v1/auth/ws-ticket",
            headers={"Authorization": f"Bearer {ws_novel.access_token}"},
        )
        assert ticket_resp.status_code == 200, ticket_resp.text[:200]
        ticket = ticket_resp.json()["ticket"]

        ws_url = (
            f"ws://localhost:8000/api/v1/writing/sessions/{chapter['chapter_id']}"
            f"?token={ticket}&project_id={ws_novel.novel_id}"
        )
        with connect(ws_url, additional_headers={"Origin": "http://localhost:9999"}) as ws:
            first = json.loads(ws.recv(timeout=10))
        assert first.get("type") == "greeting", (
            f"N08: expected greeting, got the origin rejection frame: {first}"
        )
```

**Implementation notes for the implementer (resolve before commit, they are mechanical):**
- `SocketRecord` gains a `raw` field (the Playwright `WebSocket` handle) during the Step 1 extraction — the existing spec only reads `url`/`frames`/`sent`, so adding the field is safe, and the full-flow test above already uses `tracker.sockets[0].raw.is_closed()`.
- Verify the ticket response field name (`ticket` vs `token`) against `narrare.auth.schemas` `WsTicketResponse` at write time and adjust.
- The N08 test never drives the browser for the WS itself (raw client) — `prepare_ai_chapter` runs first only to create the chapter + keep everything within the real user's novel.

- [ ] **Step 3: Verify the extraction kept the ADR-084 gate green**

Run: `E2E_PYTEST_ARGS="tests/e2e/test_ws_ticket_session.py" just e2e`
Expected: PASS unchanged (pure move + alias).

- [ ] **Step 4: Run the new spec**

Run: `E2E_PYTEST_ARGS="tests/e2e/test_ai_writing_ws.py" just e2e`
Expected: 2 PASS within ≤ 90 s (the full flow + the N08 test-mode green pin — the fix landed in Task 5; a failure of the N08 pin means Task 5 regressed, not this spec).

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/helpers/ws_probe.py tests/e2e/test_ws_ticket_session.py tests/e2e/test_ai_writing_ws.py
git commit -m "test(e2e): WRITE-005 WS full-flow spec + N08 test-mode origin pin (spec §8)"
```

---

### Task 12: Docs — coverage matrix, budget actuals, live-stack recipe

**Layer:** Docs · **Gate:** spec §9

**Files:**
- Modify: `docs/development/e2e-coverage.md`
- Modify: `docs/development/testing-standards.md` (E2E section)

**Interfaces:** none (documentation).

- [ ] **Step 1: Update the coverage matrix**

In `docs/development/e2e-coverage.md`, replace the `test_ai_writing.py` row:

```markdown
| test_ai_writing.py (+ `_selection`, `_ws` split per RULE-04 400-line cap) | WRITE-002/003/004/005/006/007/009 | B01 B02 B08 B09 M06 | ✅ done (2026-10-13) — M06 fixed in-slice (accept guard + honest errors); co-author reachability (B09 residual) + N08 fixed in-slice per the 2026-10-13 PO rulings (Tasks 4–5) and pinned green |
```

Append a runtime-budget block at the bottom of the file:

```markdown
## Runtime budget (spec §7 — full local suite ≤ 25 min)

| Module | Target | Measured |
|---|---|---|
| test_ai_writing.py (WRITE-002/007) | ≤ 3 min | <fill from the runner summary> |
| test_ai_writing_selection.py (WRITE-003/004/006/009) | ≤ 2 min | <fill> |
| test_ai_writing_ws.py (WRITE-005 + N08 pin) | ≤ 90 s | <fill> |
```

(Fill the Measured column from the `just e2e` summaries of the spec tasks' run steps (Tasks 8, 10, 11) — real numbers, no estimates.)

- [ ] **Step 2: Document the live-stack verification recipe**

In `docs/development/testing-standards.md`, append to the `## End-to-End (E2E)` → `### Runner` block:

```markdown
### Live-stack manual verification (:3001 recipe)

For fix tasks that need human eyes on the real UI (M06-class slices), run the
stack exactly as the 2026-10-11 audit did (reproduction section in
`docs/superpowers/reports/2026-10-11-e2e-ui-audit.md`):

- API :8000 — `DATABASE_URL=…:5433/narrare_test`, `ENVIRONMENT=test`,
  `SECRET_KEY=test-secret-key-not-for-production`, `NARRARE_E2E_TEST=1`,
  `AUTH_JWT_SECRET=test-secret-key-not-for-production`,
  `NARRARE_CSRF_TRUSTED_ORIGINS='["http://localhost:3001"]'`
- Web :3001 — `pnpm dev --port 3001` with `AUTH_JWT_SECRET` exported (E01)
- Then verify the fixed behavior by hand before committing the fix task.
```

- [ ] **Step 3: Verify docs gates**

Run: `uv run --all-packages pytest tests/unit/test_e2e_mock_catalog.py tests/unit/test_e2e_probes.py -v -p no:randomly` (still green) and confirm `docs/development/e2e-coverage.md` renders (table lint by eye). No `check_architecture` delta expected (no product files added by Tasks 6–11; Tasks 1–5 ran it in their own gates via pre-commit).

- [ ] **Step 4: Commit**

```bash
git add docs/development/e2e-coverage.md docs/development/testing-standards.md
git commit -m "docs(testing): ai-writing spec coverage, budget actuals, live-stack recipe"
```

---

## Self-Review

**1. Spec coverage (spec §5 row `test_ai_writing.py`):**
- "generate modes happy" → Task 7 (`TestGenerateFullDraft`, full_draft mode; mode-switching beyond default is exercised by the WS task's Interactive start — the four-mode matrix is WRITE-002's own feature doc scope, E2E pins the paths the audit flagged).
- "empty-422" → Task 7 `test_empty_form_shows_localized_validation…` (M06).
- "stream-death paths" → Task 7 error + truncated (M06), catalog variants Task 6.
- "extend" → Task 8 (B08 pin). "co-author" → Task 9 REAL happy path: selection → bubble-menu (Task 4 fix) → panel → apply, plus the B09 slash wiring pin. "rewrite" → Task 8 (B01 pin). "unblock" → Task 9 (B02 pin). "happy + apply/reject" → accept/reject (Task 7), Replace (Task 8), suggestion insert + co-author apply (Task 9), Add-to-Draft/Save (Task 11).
- "ghost text accept/dismiss" → Task 10.
- "WS session full flow" → Task 11 (greeting → user_direction → text_chunk → text_done+usage → save → end_session close).
- Gates: B01/B02/B08 pinned as green regression pins (fixes merged); M06 fixed by Tasks 1–3, B09 residual by Task 4, N08 by Task 5 — ALL BEFORE the specs that depend on them ("fixes zuerst", spec §6); N08 pinned green in Task 11 (test mode) with production invariance unit-pinned in Task 5 (PO ruling 2). **No strict-xfail pins remain** (PO rulings 2026-10-13 — Decisions log).
- Spec §9 doc gate → Task 12. Spec §7 budget stated in Global Constraints + recorded in Task 12.

**2. Placeholder scan:** no "TBD"/"TODO"/"implement later"/"add handling" patterns; every code step shows complete code (spec code, unit tests, implementation diffs). The "verify at write time" notes (unblock textarea placeholder, ws-ticket field name, co-author word-count calibration) name the exact source of truth to verify against — they are calibration steps with named references, not deferred content.

**3. Type consistency:** `mock_llm(page, capability, *, fixture=…)` used as shipped; `prepare_ai_chapter` returns `{"chapter_id", "title"}` in every consumer; `WritingSocketTracker.socket_record.raw` added in Task 11 Step 1 and consumed in Step 2; `AcceptRequest.modified_text` matches the FE body field; `EMPTY_DRAFT` code asserted identically in Task 1 test and Task 1 service guard; catalog capability/variant names (`generation_stream/truncated`, `rewrite_stream/happy|error`, `story_suggest/happy|error`, `coauthor_stream/happy|error`) identical between Task 6 SPECS, Task 6 unit tests, and Tasks 7–9 `mock_llm` calls; Task 4's `bubble.coAuthor` key is the exact label Task 9's bubble-entry selector targets (`get_by_role("button", name="Co-Author")`).

**4. Task discipline:** Tasks 1–5 are product fixes within the caps (Task 4: 2 FE files + 3 one-line i18n companions; Task 5: 1 new module + 1 route-block replacement ≤ +1 net line at the RULE-04 cap); Tasks 6–11 deliver spec/helper/test files (exempt per the suite-slice ruling, listed explicitly); every task carries a Layer tag; every code step has a complete code block; the live-stack :3001 verification recipe is unchanged and cited by Tasks 1–5's spot-checks, documented durably by Task 12.

**Known risks (documented, not hidden):**
- Selector drift (labels pinned to `en/studio.json` values quoted in the tasks) — the :3001 recipe is the calibration tool; selectors may be adjusted, assertions may not be weakened.
- Task 9's apply step deliberately uses the all-accepted client-side path (`onAccept(streamedText)`): a partial apply would POST the REAL `/co-author/apply` with the catalog mock's `request_id` and correctly fail — the catalog pattern ends at `/co-author` on purpose (Task 6); documented in the test body.
- Task 11's N08 green pin depends on Task 5 landing first (execution order 1 → 12); a failure there routes back to Task 5, never a spec-side workaround.
- `module_stable_user` page sharing requires explicit navigation per test — every test starts with `prepare_ai_chapter` (which reloads), satisfying the contract.
