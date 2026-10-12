# E2E Audit Blocker Fixes (B01–B09) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the nine dead UI features flagged as BLOCKER in the 2026-10-11 E2E audit (B01–B09) by fixing their verified root causes in the correct layer, each behind a red-then-green regression test.

**Architecture:** Four Backend fixes (app-lifespan DI singleton, prompt-route mode deferral, KB-context variable supply, missing router registration) followed by eight Frontend fix slices (contract compliance, error surfacing, type alignment, and UI wiring for extend/co-author). Every task is independently testable and committable; the fix wave is the gate for the E2E suite plan (spec §6, fix-wave 1).

**Tech Stack:** Python 3.14 · FastAPI · SQLAlchemy async · pydantic-ai (TestModel in tests) · Next.js 16 · React 19 · TipTap v3 · TypeScript · Vitest · pytest.

**Inputs:**
- Spec: `docs/superpowers/specs/2026-10-11-e2e-full-suite-design.md`
- Audit: `docs/superpowers/reports/2026-10-11-e2e-ui-audit.md` (§ BLOCKER)
- Evidence: `docs/superpowers/reports/evidence/2026-10-11-e2e-ui-audit/`

## Global Constraints

- **Project language is English** — code, comments, tests, commit messages (exception: `packages/i18n` message files).
- **`docs/_shared/CONSTRAINTS.md` is the constitution** — load it before starting. Directly relevant here: RULE-02/02b (prompt assembly/resolution only in `core/prompts/`; services only pass runtime input), RULE-04 (modularize, don't squeeze), RULE-06 (routers delegate immediately), RULE-10 (tests mandatory), RULE-11 (no silent failures), RULE-15 (no `middleware.ts` in `packages/web`), RULE-16 (i18n namespace + en/de/fr parity for every used key), RULE-17 (FE types mirror BE schemas exactly — same commit), RULE-19 (`SessionDep` in dependency factories), RULE-20 (no half-implementations; SSE backend ⇒ SSE frontend), RULE-23 (no naked `# type: ignore`).
- **Regression-first:** write the failing test BEFORE the fix, run it, and record the red-phase output (command + observed failure) in the task report. A fix without red evidence is not done.
- **Task cap:** ≤ 3 implementation files and ≤ 250 new LOC per task (test files and one-line i18n JSON parity edits don't count toward the file cap; they are listed explicitly). Sub-slices exist where a blocker needs more.
- **Conventional commits** (`fix(kb): …`, `fix(web): …`, `fix(analysis): …`, `fix(api): …`). **`git commit --no-verify` is FORBIDDEN.** Commits are made by the implementing session; pushes/tags go through NarrarePlatformSpecialist.
- **Layer tags** (first line of each task) route the task via the coordinator: `Backend` → NarrareBackendSpecialist, `Frontend` → NarrareFrontendSpecialist, `Core` → NarrareCoreSpecialist. Layer order in this plan: Backend (Tasks 1–4) → Frontend (Tasks 5–12).
- **Test commands:** Python unit: `uv run --all-packages pytest <path> -v -p no:randomly`; Python integration: same command (integration conftest provisions the DB). Web unit: `pnpm --filter narrare-web exec vitest run <path>`; Web typecheck: `pnpm --filter narrare-web run type-check`; Web testid check (tasks adding `data-testid`): `pnpm --filter narrare-web run check:testid`.
- **Next.js 16 note (RULE-15):** never create `middleware.ts`; route-level concerns live in `proxy.ts`. No task here touches Next routing APIs.
- Line numbers quoted from the audit may be stale — every task below re-verified the defect by semantic location in the current tree (2026-10-12).

## Blocker → Task map

| Task | Layer | Blockers | Surface |
|------|-------|----------|---------|
| 1 | Backend | B05 | KB session cache shared across requests |
| 2 | Backend | B06 | KB improve prompt mode → `kb/en/improve` |
| 3 | Backend | B07 | POV analysis KB prompt variables |
| 4 | Backend | B03 | Consistency router registration |
| 5 | Frontend | B02 | Unblock story-suggest `novel_id` body field |
| 6 | Frontend | B01 (part 1) | Rewrite context clamp to 500 chars |
| 7 | Frontend | B01 (part 2) | Rewrite error banner (no silent modal close) |
| 8 | Frontend | B04 (part 1) | KB entry detail renders without `field_groups` |
| 9 | Frontend | B04 (part 2) | `KBTemplate` type aligned with real contract |
| 10 | Frontend | B08 (part 1) | Continue-stream hardening + `ContinueButton` refactor |
| 11 | Frontend | B08 (part 2) | Extend wired into toolbar + command palette |
| 12 | Frontend | B08 (slash) + B09 | Extend + co-author wired into slash menu; CoAuthorPanel mounted in editor |

---

### Task 1: KB session cache shared across requests (B05)

**Layer:** Backend · **Blocker:** B05

**Files:**
- Modify: `apps/api/narrare/_app/lifespan.py` (after `bind_writing_session_singletons`, ~line 58, and its call site ~line 257)
- Modify: `apps/api/narrare/kb/dependencies_session.py:84-86`
- Modify: `tests/integration/conftest.py` (in the session-scoped `app` fixture, after `create_app(test_mode=True)` ~line 247)
- Test: `tests/integration/kb/test_kb_session_cache_shared.py` (new)

**Interfaces:**
- Produces: `bind_kb_session_singletons(app: FastAPI) -> None` in `narrare._app.lifespan` — binds `app.state.kb_session_cache` (one `narrare_core.cache.InMemorySessionCache` per app process). Consumed by `get_kb_session_service` and by the integration test app fixture.

**Root cause (2× why):**
- Why does `GET /kb/sessions/{id}` 404 right after `POST /kb/sessions` 201? The factory builds a fresh `InMemorySessionCache()` per request (`dependencies_session.py:85`), so the session stored by the POST lives in a cache the GET never sees (evidence `08-report` bug #3, 11× 404; also documented in `test_kb_session_lazy_resolution.py:16-18`).
- Why was a per-request cache built? The factory predates ADR-080's app-state singleton pattern (ADR-052 binds the writing-session singletons on `app.state`); the KB session factory was never migrated, and service-level tests always mock the service, so the wiring was never exercised end-to-end.

**Alternatives considered:**
1. Bind on `app.state` in lifespan + accessor (chosen) — mirrors the established ADR-052/`deps_ws.py` pattern; loud `RuntimeError` when unbound.
2. Module-level singleton in `dependencies_session.py` — leaks across app lifecycles in tests; violates the ADR-052 precedent.
3. Lazy init-on-first-request on `app.state` — masks binding mistakes (against the `deps_ws._state_value` fail-loud precedent).

- [ ] **Step 1: Write the failing integration test**

Create `tests/integration/kb/test_kb_session_cache_shared.py`:

```python
"""Audit B05 regression — KB sessions survive across requests.

``get_kb_session_service`` built a fresh ``InMemorySessionCache`` per
request, so ``POST /kb/sessions`` returned 201 and the immediate
``GET /kb/sessions/{id}`` answered 404 (session invisible to the next
request's cache). The fix binds ONE cache on ``app.state`` at startup;
both requests now share it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestKBSessionCacheSharedAcrossRequests:
    async def test_create_then_get_roundtrip_with_real_factory(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST 201 → GET 200 through the REAL factory (no service override)."""
        novel_resp = await client.post(
            "/api/v1/novels",
            json={"title": "KB Session Cache Novel", "writing_language": "en"},
            headers=auth_headers,
        )
        assert novel_resp.status_code == 201
        novel_id = novel_resp.json()["id"]

        create_resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/sessions",
            json={"entity_type": "character"},
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        session_id = create_resp.json()["id"]

        get_resp = await client.get(
            f"/api/v1/novels/{novel_id}/kb/sessions/{session_id}",
            headers=auth_headers,
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == session_id
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --all-packages pytest tests/integration/kb/test_kb_session_cache_shared.py -v -p no:randomly`
Expected: FAIL — `assert 404 == 200` on the GET (the audit repro). Record the output in the task report.

- [ ] **Step 3: Implement the lifespan binder**

In `apps/api/narrare/_app/lifespan.py`, add directly below `bind_writing_session_singletons` (after its final `raise`, ~line 58):

```python
def bind_kb_session_singletons(app: FastAPI) -> None:
    """Bind the KB creation-session cache singleton on ``app.state`` (audit B05).

    ADR-080 in-process cache: one ``InMemorySessionCache`` per app process,
    shared by every ``get_kb_session_service`` factory call so a session
    created in one request is readable in the next. The store's 30-minute
    TTL is applied on write by ``KBCreationSessionStore``. Multi-worker
    deployments re-plug a shared backend via ``SessionCacheProtocol``
    (same re-introduction path as the writing-session singletons above).
    """
    from narrare_core.cache import InMemorySessionCache

    app.state.kb_session_cache = InMemorySessionCache()
    logger.info("kb_session_singletons_bound")
```

In `lifespan()` startup, directly below the existing `bind_writing_session_singletons(app)` call (~line 257), add:

```python
    bind_kb_session_singletons(app)
```

In `tests/integration/conftest.py`, in the session-scoped `app` fixture, directly below `app = create_app(test_mode=True)`:

```python
    # ASGITransport never runs the lifespan; bind the KB session cache the
    # same way startup would so real-factory tests see production wiring
    # (audit B05 regression suite).
    from narrare._app.lifespan import bind_kb_session_singletons

    bind_kb_session_singletons(app)
```

- [ ] **Step 4: Consume the shared cache in the factory**

In `apps/api/narrare/kb/dependencies_session.py`:

1. Add `Request` to the FastAPI import (line 15): `from fastapi import Depends, Request`
2. Add `request: Request` as a factory parameter (after `event_publisher`).
3. Replace the per-request cache construction (lines 84-86) and drop the now-unused `from narrare_core.cache import InMemorySessionCache` import inside the factory body:

```python
    # Session storage: app-lifespan-shared cache (ADR-080, audit B05) —
    # NOT a per-request cache, otherwise a session created by this request
    # is invisible to the next (POST 201 → GET 404).
    cache = getattr(request.app.state, "kb_session_cache", None)
    if cache is None:
        raise RuntimeError(
            "app.state.kb_session_cache is not bound; lifespan did not initialize"
        )
    session_store = KBCreationSessionStore(cache=cache)
```

Update the factory docstring's storage paragraph: "For session storage, uses the app-lifespan-scoped InMemorySessionCache shared across requests (ADR-080, audit B05) with a 30min TTL applied by the store."

- [ ] **Step 5: Run the tests to verify green**

Run: `uv run --all-packages pytest tests/integration/kb/test_kb_session_cache_shared.py tests/integration/kb/test_kb_session_lazy_resolution.py tests/integration/kb/test_kb_sessions_api.py -v -p no:randomly`
Expected: ALL PASS (the existing suites must stay green — they override the service, so the new `Request` param is transparent).

- [ ] **Step 6: Commit**

```bash
git add apps/api/narrare/_app/lifespan.py apps/api/narrare/kb/dependencies_session.py tests/integration/conftest.py tests/integration/kb/test_kb_session_cache_shared.py
git commit -m "fix(kb): share KB session cache across requests via app lifespan (B05)"
```

---

### Task 2: KB improve prompt resolves to `kb/en/improve` (B06)

**Layer:** Backend · **Blocker:** B06

**Files:**
- Modify: `apps/api/narrare/kb/improve_analyzer.py:175-196` (`_build_prompt_context`) and its call site ~line 283
- Test: `tests/unit/api/kb/test_kb_improve_prompt_route.py` (new)

**Interfaces:**
- Produces: `KBImproveAnalyzer._build_prompt_context(entity_type: str, entry_content: dict[str, object], *, template_structure: str = "", existing_relationships: str = "", world_context: str = "") -> PromptContext` — a pure context builder whose `mode` is `""` (defers to the route-table default `("kb", "improve")`).

**Root cause (2× why):**
- Why 400 `PROMPT_NOT_FOUND: kb/en/kb_improve`? `_build_prompt_context` sets `mode=LLMIntent.KB_IMPROVE.value` (`"kb_improve"`); `resolve_prompt_route` treats any non-empty context mode as the template mode (KB_IMPROVE declares no `allowed_context_modes`), so the composer looks up `kb/en/kb_improve` — the bundled template lives at `kb/en/improve` (evidence `08-report` bug #2, lines 106-112).
- Why was the intent value used as mode? The author conflated intent identity with prompt mode. The compose seam was only ever tested with `FakeComposer` (`test_kb_improve_analyzer.py`), which hides both the route resolution and the template's variable requirements.

**Secondary defect verified while re-checking (fix included):** the template `kb/en/improve/system.md` references `{{world_context}}`, `{{template_structure}}`, `{{existing_relationships}}` — none supplied by the context and none declared optional for KB_IMPROVE — so a mode-only fix would next fail with `PromptVariableError`. The analyzer already builds all three as agent deps; they must flow into the context (architectural-discipline §7: documented template slots must be genuinely fed).

**Alternatives considered:**
1. `mode=""` + feed the three deps-derived slots into `extra` (chosen) — real data reaches the template; mirrors the coreference SSOT supply.
2. `mode=""` + declare the three slots `optional_variables` on `KB_IMPROVE` in the route table — works, but renders the template's context sections permanently empty while the analyzer holds the real values in deps: incoherent.
3. Rename the bundled template directory to `kb/en/kb_improve` — moves the artifact to match a bug; contradicts the route table (`("kb", "improve")`).

- [ ] **Step 1: Write the failing unit test**

Create `tests/unit/api/kb/test_kb_improve_prompt_route.py`:

```python
"""Audit B06 regression — KB improve prompt resolves to kb/en/improve.

``KBImproveAnalyzer._build_prompt_context`` set ``mode="kb_improve"`` (the
intent VALUE). ``resolve_prompt_route`` treats a non-empty context mode as
the template mode, so the composer looked up ``kb/en/kb_improve`` — which
does not exist — and the endpoint answered 400 PROMPT_NOT_FOUND. The fix
defers to the route-table default (``kb/en/improve``) via ``mode=""`` and
feeds the template's remaining declared slots from the analyzer's deps.
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.prompts.routes import resolve_prompt_route


def _make_analyzer() -> Any:
    """Minimal analyzer — only the pure context builder is exercised."""
    from narrare._app.dependencies_services import StaticModelResolution
    from narrare.kb.improve_analyzer import KBImproveAnalyzer
    from narrare_core.llm.model_config import ResolvedModelConfig
    from narrare_core.llm.model_routing import ResolvedModel

    config = ResolvedModelConfig(provider_name="test", model_id="test-model")
    return KBImproveAnalyzer(
        registry=cast("Any", AsyncMock()),
        model_resolution=StaticModelResolution(ResolvedModel(config=config)),
        kb_context_provider=cast("Any", AsyncMock()),
        prompt_composer=cast("Any", AsyncMock()),
        kb_repo=cast("Any", AsyncMock()),
        rel_repo=cast("Any", AsyncMock()),
    )


class TestKBImprovePromptRoute:
    def test_context_mode_defers_to_route_table_default(self) -> None:
        ctx = _make_analyzer()._build_prompt_context("character", {"name": "Alice"})
        route = resolve_prompt_route(LLMIntent.KB_IMPROVE, ctx.mode)
        assert (route.category, route.mode) == ("kb", "improve")

    @pytest.mark.asyncio
    async def test_real_cascade_composes_bundled_improve_template(self) -> None:
        """End-to-end compose over the real registry + bundled templates.

        Red today: registry lookup fails for ``kb/en/kb_improve``; green
        after the fix (template found, all declared variables supplied).
        """
        analyzer = _make_analyzer()
        ctx = analyzer._build_prompt_context(
            "character",
            {"name": "Alice"},
            template_structure="name, summary",
            existing_relationships="- Alice → ally → Bob",
            world_context="- Alice (character): a brave hero",
        )
        composer = PromptComposer(PromptRegistry())
        composed = await composer.build(LLMIntent.KB_IMPROVE, ctx)
        assert "Knowledge Base improvement analyst" in composed.system
        assert "Alice" in composed.system
        assert "- Alice → ally → Bob" in composed.system
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --all-packages pytest tests/unit/api/kb/test_kb_improve_prompt_route.py -v -p no:randomly`
Expected: FAIL — test 1: `(route.category, route.mode) == ("kb", "kb_improve")` ≠ `("kb", "improve")`; test 2: prompt-not-found error from the real registry. Record output.

- [ ] **Step 3: Fix `_build_prompt_context` and its call site**

In `apps/api/narrare/kb/improve_analyzer.py`, replace `_build_prompt_context` (lines 175-196) with:

```python
    def _build_prompt_context(
        self,
        entity_type: str,
        entry_content: dict[str, object],
        *,
        template_structure: str = "",
        existing_relationships: str = "",
        world_context: str = "",
    ) -> PromptContext:
        """Build PromptContext for the improve prompt (RULE-02).

        Mode defers to the route-table default (``kb/en/improve``) — a
        non-empty mode is treated as the template mode and previously
        pointed at the nonexistent ``kb/en/kb_improve`` (audit B06). The
        template-declared slots (template_structure / existing_relationships
        / world_context) are fed from the analyzer's deps so the compose
        preflight passes with real data (architectural-discipline §7).
        """
        from narrare_core.prompts.context import PromptContext

        return PromptContext(
            language="en",
            writing_language="en",
            genre="",
            project_title="",
            mode="",
            extra={
                "entity_type": entity_type,
                "entry_content": str(entry_content),
                "template_structure": template_structure,
                "existing_relationships": existing_relationships,
                "world_context": world_context,
            },
        )
```

In `analyze()` (~line 282-286), replace the two lines building `deps`/`prompt_context` so the deps-derived slots flow through:

```python
        deps = await self._build_deps(novel_id=novel_id, entry_id=entry_id)
        prompt_context = self._build_prompt_context(
            entity_type=deps.entity_type,
            entry_content=deps.entry_content or {},
            template_structure=deps.template_structure,
            existing_relationships=str(deps.existing_relationships),
            world_context=deps.world_context or "",
        )
```

- [ ] **Step 4: Run the tests to verify green**

Run: `uv run --all-packages pytest tests/unit/api/kb/test_kb_improve_prompt_route.py tests/unit/api/kb/test_kb_improve_analyzer.py tests/unit/api/kb/test_kb_improve_service.py -v -p no:randomly`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/kb/improve_analyzer.py tests/unit/api/kb/test_kb_improve_prompt_route.py
git commit -m "fix(kb): defer improve prompt mode to route table default (B06)"
```

---

### Task 3: POV analysis prompt gets KB context variables (B07)

**Layer:** Backend · **Blocker:** B07

**Files:**
- Modify: `apps/api/narrare/analysis/services/pov_service.py` (ctor + `analyze` compose section)
- Modify: `apps/api/narrare/analysis/_invocation_compose.py` (optional `extra` parameter)
- Modify: `apps/api/narrare/analysis/dependencies.py:126-175` (`get_pov_service` wiring)
- Test: `tests/unit/api/analysis/test_pov_service_kb.py` (new)

**Interfaces:**
- Consumes: `KBContextProviderProtocol.fetch_context(novel_id, entity_types=..., options=...) -> KBContextBundle` and `KBContextBundle.to_prompt_variables() -> dict[str, str]` (keys `kb_characters` / `kb_locations` / `kb_factions` / `kb_relationships`) — the same SSOT supply `CoreferenceService` uses (`coreference_service.py:190-200`).
- Produces: `compose_analysis_invocation_prompt(..., extra: dict[str, str] | None = None)` — backward-compatible optional spread into `PromptContext.extra` (both the pipeline path and the direct fallback). `POVService.__init__` gains `kb_context_provider: KBContextProviderProtocol | None = None`.

**Root cause (2× why):**
- Why 500 `PromptVariableError: Missing required prompt variable 'kb_characters'`? The pov template (`analysis/en/pov/system.md`, `{{kb_characters}}` at line 53 + the other three kb slots) is composed through `compose_analysis_invocation_prompt`, which builds a bare `PromptContext(language, mode, project_title="")` — the kb slots are neither supplied nor declared optional for the `ANALYSE` intent, so `prepare_variables_for_template` raises; the pipeline path swallows it, the fallback raises again → `AnalysisError` → 500 (evidence `05-pov-final.txt`).
- Why are the variables missing? Unlike its working sibling coreference (same `ANALYSE` intent, `mode="coreference"`), POV never wired the canonical `KBContextProvider` (ADR-067) — the prompt-supply bug family the audit flags for analysis routes. (Readability shares the same gap and silently degrades — audit N12, explicitly out of scope here.)

**Alternatives considered:**
1. Wire `KBContextProvider` into POVService and spread `to_prompt_variables()` into the compose context (chosen) — exact precedent `coreference_prompt.py` / `dependencies_coreference.py`; real KB data reaches the template; degrades to empty strings per RULE-11 when the KB is empty.
2. Declare the four kb slots `optional_variables` on `ANALYSE` in the route table — renders them permanently empty for ALL analysis modes (pov/readability/review/coreference), degrading coreference which today genuinely feeds them. Too broad.
3. Template edit removing the kb slots from pov — loses real analysis quality context and diverges the pov template from its siblings.

- [ ] **Step 1: Write the failing unit test**

Create `tests/unit/api/analysis/test_pov_service_kb.py`:

```python
"""Audit B07 regression — POV prompt compose receives KB context variables.

``analysis/en/pov/system.md`` references {{kb_characters}} / {{kb_locations}}
/ {{kb_factions}} / {{kb_relationships}}, but POVService composed with a
bare PromptContext — the variable engine raised PromptVariableError and the
endpoint answered 500. The fix follows the coreference SSOT supply: the
canonical KBContextProvider feeds all four slots (ADR-067), degrading to
empty strings when the KB is empty (RULE-11).
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare._app.dependencies_services import StaticModelResolution
from narrare.analysis.services.pov_service import POVService
from narrare.kb._context_provider import KBContextProvider
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.registry import PromptRegistry
from tests.fakes import FakeChapterRepository, FakeModelRegistry, FakeNovelRepository
from tests.unit.api._test_helpers import make_chapter, make_novel, seed_repos
from tests.unit.api.analysis._fakes import FakePOVAgent

_CONFIG = ResolvedModelConfig(provider_name="test", model_id="test-model")


def _pov_output() -> Any:
    from narrare_core.agents.pov_types import POVDetectionOutput

    return POVDetectionOutput(
        scenes=[{"scene_index": 0, "pov_character": "Alice", "confidence": 0.9}],
        issues=[],
        pov_distribution={"Alice": 1.0},
        switch_count=0,
        analysis_type="third_limited",
    )


def _kb_entry(entity_type: str, name: str, body: str) -> MagicMock:
    entry = MagicMock()
    entry.entity_type = entity_type
    entry.name = name
    entry.body = body
    return entry


def _provider_with(entries: list[MagicMock]) -> KBContextProvider:
    """Real KBContextProvider over a faked KB repo (coreference-test pattern)."""
    repo = AsyncMock()
    repo.list_entries.return_value = (entries, len(entries))
    return KBContextProvider(kb_repo=repo, relationship_repo=None)  # type: ignore[arg-type]


def _prepared() -> PreparedModelCall:
    return PreparedModelCall(model=MagicMock(spec=object), model_settings=None, usage_limits=None)


class TestPOVKBContextSupply:
    @pytest.mark.asyncio
    async def test_analyze_composes_pov_prompt_with_kb_variables(self) -> None:
        """Real registry + real composer: analyze completes and the composed
        system prompt carries the KB character names (B07 red: AnalysisError)."""
        novel = make_novel(writing_language="en")
        ch = make_chapter(novel_id=novel.id, content="Alice saw the light and smiled.")
        nr, cr = FakeNovelRepository(), FakeChapterRepository()
        seed_repos(novel, ch, novel_repo=nr, chapter_repo=cr)

        provider = _provider_with(
            [_kb_entry("character", "Alice", "A brave hero who fears rivers.")]
        )
        captured: dict[str, str | None] = {}
        agent = FakePOVAgent(output=_pov_output())

        svc = POVService(
            chapter_repo=cr,
            novel_repo=nr,
            model_registry=FakeModelRegistry(),
            model_resolution=StaticModelResolution(ResolvedModel(config=_CONFIG)),
            composer=PromptComposer(PromptRegistry()),
            kb_context_provider=provider,
        )

        async def _prepare_agent(
            system_prompt: str | None = None,
            resolved_model: ResolvedModel | None = None,
        ) -> tuple[FakePOVAgent, PreparedModelCall]:
            captured["system"] = system_prompt
            return agent, _prepared()

        svc._prepare_agent = _prepare_agent  # type: ignore[method-assign]

        result = await svc.analyze(
            novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id
        )

        assert result.analysis_type == "third_limited"
        system = captured["system"] or ""
        assert "Alice" in system, "kb_characters must flow into the pov system prompt"

    @pytest.mark.asyncio
    async def test_analyze_without_provider_degrades_to_empty_slots(self) -> None:
        """No provider wired → compose still succeeds (empty kb slots, RULE-11)."""
        novel = make_novel(writing_language="en")
        ch = make_chapter(novel_id=novel.id, content="Alice saw the light.")
        nr, cr = FakeNovelRepository(), FakeChapterRepository()
        seed_repos(novel, ch, novel_repo=nr, chapter_repo=cr)

        agent = FakePOVAgent(output=_pov_output())

        async def _prepare_agent_without_capture(
            system_prompt: str | None = None,
            resolved_model: ResolvedModel | None = None,
        ) -> tuple[FakePOVAgent, PreparedModelCall]:
            return agent, _prepared()

        svc = POVService(
            chapter_repo=cr,
            novel_repo=nr,
            model_registry=FakeModelRegistry(),
            model_resolution=StaticModelResolution(ResolvedModel(config=_CONFIG)),
            composer=PromptComposer(PromptRegistry()),
            kb_context_provider=None,
        )
        svc._prepare_agent = _prepare_agent_without_capture  # type: ignore[method-assign]

        result = await svc.analyze(
            novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id
        )
        assert result.analysis_type == "third_limited"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --all-packages pytest tests/unit/api/analysis/test_pov_service_kb.py -v -p no:randomly`
Expected: FAIL — `AnalysisError: Failed to compose analysis_pov prompt` (or underlying `PromptVariableError: kb_characters`) from the real composer. Record output.

- [ ] **Step 3: Add the `extra` parameter to the shared compose helper**

In `apps/api/narrare/analysis/_invocation_compose.py`, extend the signature (keep keyword-only):

```python
async def compose_analysis_invocation_prompt(
    *,
    composer: PromptComposer,
    invocation_pipeline: InvocationPipeline | None,
    feature_id: str,
    intent: LLMIntent,
    novel_id: UUID,
    user_id: UUID,
    language: str,
    mode: str,
    extra: dict[str, str] | None = None,
) -> ComposedPrompt:
```

Document the new parameter in the docstring:

```
        extra: Optional prompt variables spread into ``PromptContext.extra``
            (e.g. the four ``kb_*`` slots from the canonical KBContextProvider,
            ADR-067 — audit B07). ``None`` keeps the previous bare context.
```

Replace BOTH `PromptContext(...)` constructions (pipeline path line ~89 and fallback line ~123) with:

```python
    ctx = PromptContext(
        language=language,
        mode=mode,
        project_title="",
        extra=dict(extra or {}),
    )
```

- [ ] **Step 4: Wire the provider into POVService**

In `apps/api/narrare/analysis/services/pov_service.py`:

1. Add under `TYPE_CHECKING` imports: `from narrare.kb.context_contracts import KBContextProviderProtocol`
2. Add ctor parameter and field:

```python
        kb_context_provider: KBContextProviderProtocol | None = None,
```

```python
        self._kb_context_provider = kb_context_provider
```

Document it in the class docstring Args block (mirroring `CoreferenceService`).

3. In `analyze()`, directly ABOVE the `composed = await compose_analysis_invocation_prompt(...)` call (~line 157), insert the SSOT supply (verbatim coreference pattern):

```python
        # KB-context variables for the pov template's {{kb_*}} slots (audit
        # B07): canonical provider (ADR-067) — the same SSOT supply the
        # coreference service uses. ``None`` provider or empty KB degrades
        # to empty slots (RULE-11); the provider never raises.
        from narrare_core.context._render_options import RenderOptions

        if self._kb_context_provider is None:
            from narrare.kb.context_contracts import KBContextBundle

            kb_bundle = KBContextBundle.empty(RenderOptions(annotate_provenance=True))
        else:
            kb_bundle = await self._kb_context_provider.fetch_context(
                novel_id,
                entity_types=["character", "location", "faction"],
                options=RenderOptions(annotate_provenance=True),
            )
        kb_vars = kb_bundle.to_prompt_variables()
```

4. Add `extra=kb_vars,` to the `compose_analysis_invocation_prompt(...)` call.

In `apps/api/narrare/analysis/dependencies.py` `get_pov_service` (~line 168-175): add the provider wiring and pass it (mirroring `dependencies_coreference.py:100-105`):

```python
    from narrare.kb._context_provider import KBContextProvider
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
```

```python
    # Canonical KB-context provider (ADR-067): single fetch+render source for
    # the pov template's kb_* slots. Degrades gracefully (RULE-11).
    kb_context_provider = KBContextProvider(
        kb_repo=KBRepository(session),
        relationship_repo=RelationshipRepository(session),
    )
```

```python
    return POVService(
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
        model_registry=registry,
        model_resolution=model_resolution,
        composer=get_composer(),
        kb_context_provider=kb_context_provider,
        invocation_pipeline=get_invocation_pipeline(),
    )
```

(`dependencies.py` stays ≤ 200 lines — RULE-04 hard limit; verify with `wc -l`.)

- [ ] **Step 5: Run the tests to verify green**

Run: `uv run --all-packages pytest tests/unit/api/analysis/test_pov_service_kb.py tests/unit/api/analysis/test_pov_service.py -v -p no:randomly`
Expected: ALL PASS (existing POV tests unaffected — the new ctor param defaults to `None`).

- [ ] **Step 6: Commit**

```bash
git add apps/api/narrare/analysis/services/pov_service.py apps/api/narrare/analysis/_invocation_compose.py apps/api/narrare/analysis/dependencies.py tests/unit/api/analysis/test_pov_service_kb.py
git commit -m "fix(analysis): supply KB context variables to POV prompt compose (B07)"
```

---

### Task 4: Register the consistency router (B03)

**Layer:** Backend · **Blocker:** B03

**Files:**
- Modify: `apps/api/narrare/_app/main.py` (import block ~line 263 + `include_router` block ~line 333)
- Test: `tests/integration/consistency/__init__.py` (new, empty) and `tests/integration/consistency/test_consistency_router_registration.py` (new)

**Interfaces:**
- Produces: the documented CONS-001 HTTP surface (`docs/features/consistency/CONS-001-checker.md` line 131, ADR-044 Slice 4): `POST /api/v1/consistency/check`, `POST /api/v1/consistency/check/stream`, `POST /api/v1/consistency/chapters/{chapter_id}/check` — the exact routes the frontend `streamConsistencyCheck` client already speaks (no FE change).

**Root cause (2× why):**
- Why 404? The editor ConsistencyPanel calls `POST /api/v1/consistency/check/stream?novel_id=…` (evidence `06b-api-calls.json:180,188`), but no such route exists at runtime: `narrare/consistency/router.py` is fully implemented yet never imported/included in `create_app` (`main.py` registers `kb_consistency_router` and `series_consistency_router`, not this one).
- Why does the module exist without registration? ADR-044 Slice 4 shipped the router + orchestrator + unit tests (`tests/unit/api/consistency/*`) but the final `include_router` line was missed; no integration test ever exercised the HTTP path, so nothing failed.

**Ruling (encoded, not open):** fix the BACKEND registration — the FE URL is correct per the feature doc and ADR-044; the BE genuinely never shipped the route. The separate KB-004 surface (`POST /novels/{id}/kb/consistency-check`) is a different feature and is NOT touched here.

**Alternatives considered:**
1. Register the existing router (chosen) — one line + tests; restores the documented contract for an already-built FE.
2. Rewire the FE to `/novels/{id}/kb/consistency-check` — wrong feature (KB-entity consistency vs chapter-prose consistency), different response schema; would require rebuilding the staged-SSE panel.
3. Delete the dormant module — discards a working ADR-044 implementation and its FE consumer.

- [ ] **Step 1: Write the failing integration test**

Create `tests/integration/consistency/__init__.py` (empty) and `tests/integration/consistency/test_consistency_router_registration.py`:

```python
"""Audit B03 regression — CONS-001 router is registered on the app.

``narrare/consistency/router.py`` ships POST /consistency/check and
POST /consistency/check/stream (ADR-044 Slice 4, CONS-001 feature doc)
but was never included in ``create_app`` — the editor ConsistencyPanel
got 404 on every check (auto-run + Retry loop).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from narrare.consistency.deps import get_consistency_service
from narrare.consistency.schemas import ConsistencyResponse
from narrare.consistency.stage_schemas import ConsistencyStageEvent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from fastapi import FastAPI
    from httpx import AsyncClient


class _FakeCheckerService:
    """Duck-typed ConsistencyCheckerService for route-level wiring tests."""

    async def ensure_resolved(self) -> None:
        return None

    async def check(self, *, novel_id: UUID, user_id: UUID, request: object) -> ConsistencyResponse:
        return ConsistencyResponse(
            novel_id=novel_id,
            chapter_ids=[],
            check_types=[],
            issues=[],
            overall_assessment="Consistent",
            analyzed_at="2026-10-12T00:00:00Z",
        )

    async def stream_check(
        self, *, novel_id: UUID, user_id: UUID, request: object
    ) -> AsyncIterator[ConsistencyStageEvent | ConsistencyResponse]:
        yield ConsistencyStageEvent(
            stage="extracting_facts", status="start", message="Extracting facts"
        )
        yield ConsistencyResponse(
            novel_id=novel_id,
            chapter_ids=[],
            check_types=[],
            issues=[],
            overall_assessment="Consistent",
            analyzed_at="2026-10-12T00:00:00Z",
        )


def test_consistency_routes_registered() -> None:
    from narrare._app.main import create_app

    app = create_app(test_mode=True)
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/api/v1/consistency/check" in paths
    assert "/api/v1/consistency/check/stream" in paths


class TestConsistencyEndpointsReachable:
    async def test_stream_check_returns_sse(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        app.dependency_overrides[get_consistency_service] = lambda: _FakeCheckerService()
        try:
            resp = await client.post(
                f"/api/v1/consistency/check/stream?novel_id={uuid4()}",
                json={},
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_consistency_service, None)

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert '"type": "stage"' in resp.text
        assert '"type": "result"' in resp.text
        assert "[DONE]" in resp.text

    async def test_check_returns_json(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        app.dependency_overrides[get_consistency_service] = lambda: _FakeCheckerService()
        try:
            resp = await client.post(
                f"/api/v1/consistency/check?novel_id={uuid4()}",
                json={},
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_consistency_service, None)

        assert resp.status_code == 200
        assert resp.json()["overall_assessment"] == "Consistent"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --all-packages pytest tests/integration/consistency/test_consistency_router_registration.py -v -p no:randomly`
Expected: FAIL — registration pin: paths missing; request tests: 404. Record output.

- [ ] **Step 3: Register the router**

In `apps/api/narrare/_app/main.py`:

1. Import block — directly below `from narrare.chapters.router_versions import router as chapter_versions_router` (line 263), add:

```python
    from narrare.consistency.router import router as consistency_router
```

2. Include block — directly below `app.include_router(chapter_versions_router, prefix=prefix)` (~line 333), add:

```python
    app.include_router(consistency_router, prefix=prefix)
```

- [ ] **Step 4: Run the tests to verify green**

Run: `uv run --all-packages pytest tests/integration/consistency/ -v -p no:randomly`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/_app/main.py tests/integration/consistency/
git commit -m "fix(api): register consistency router in app factory (B03)"
```

---

### Task 5: Unblock sends `novel_id` in the request body (B02)

**Layer:** Frontend · **Blocker:** B02

**Files:**
- Modify: `packages/web/lib/api/story-suggest-stream.ts:51-62` (`StorySuggestRequestBody`)
- Modify: `packages/web/components/studio/editor/useUnblockStream.ts:65-70` (request body)
- Test: `packages/web/lib/hooks/__tests__/useUnblockStream.test.tsx` (new)

**Interfaces:**
- Produces: `StorySuggestRequestBody { novel_id: string; chapter_id?: string; author_instructions?: string }` — RULE-17 parity with `StorySuggestRequest` (`apps/api/narrare/writing/schemas_story_suggest.py:36`), where `novel_id` is a REQUIRED body field even though the route also takes it as a path parameter.

**Root cause (2× why):**
- Why 422 `Field required`? `useUnblockStream` posts `{chapter_id, author_instructions}` only; the BE body schema requires `novel_id` (evidence `06b-report`).
- Why was it omitted? The FE interface doc-comment claims "novel_id … supplied via the URL path parameter, not the body" — an incorrect reading of the contract written into the type; no contract test compares the FE body against the BE schema (RULE-17 gap).

**Ruling:** the BE schema is the SSOT — the FE adds the field. Changing the BE to drop the redundant body field would alter a shipped contract and gain nothing.

**Alternatives considered:**
1. FE adds `novel_id` to the body (chosen) — one field, contract-true, no BE release coupling.
2. BE makes `novel_id` body-optional (path is authoritative) — contract change on a healthy endpoint for a FE bug; rejected.

- [ ] **Step 1: Write the failing hook test**

Create `packages/web/lib/hooks/__tests__/useUnblockStream.test.tsx`:

```tsx
/**
 * useUnblockStream tests — request-body contract for Writer's Unblock.
 *
 * Audit B02 regression: the hook omitted `novel_id` from the POST body even
 * though `StorySuggestRequest` requires it (422 "Field required" rendered as
 * "Connection lost").
 *
 * @module useUnblockStream.test
 */

import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const streamStorySuggestions = vi.hoisted(() => vi.fn(async () => new Promise<void>(() => {})));

vi.mock("@/lib/api/story-suggest-stream", () => ({
  streamStorySuggestions: (...args: unknown[]) => streamStorySuggestions(...args),
}));

import { useUnblockStream } from "@/lib/hooks/useUnblockStream";

describe("useUnblockStream", () => {
  beforeEach(() => {
    streamStorySuggestions.mockClear();
  });

  it("sends novel_id in the request body (B02)", async () => {
    const { result } = renderHook(() => useUnblockStream("novel-1", "chapter-9"));

    result.current.request("Stuck at the door scene");

    await waitFor(() => expect(streamStorySuggestions).toHaveBeenCalled());
    const body = streamStorySuggestions.mock.calls[0][1] as Record<string, unknown>;
    expect(body.novel_id).toBe("novel-1");
    expect(body.chapter_id).toBe("chapter-9");
    expect(body.author_instructions).toBe("Stuck at the door scene");
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pnpm --filter narrare-web exec vitest run lib/hooks/__tests__/useUnblockStream.test.tsx`
Expected: FAIL — `body.novel_id` is `undefined`. Record output.

- [ ] **Step 3: Implement**

In `packages/web/lib/api/story-suggest-stream.ts`, replace the `StorySuggestRequestBody` interface (and its doc comment, lines 51-62) with:

```ts
/**
 * Request body for the story-suggest endpoint.
 *
 * RULE-17 contract parity: mirrors `StorySuggestRequest` — `novel_id` is a
 * REQUIRED body field even though the route also carries it as the URL path
 * parameter (audit B02: omitting it yields 422 "Field required").
 * `author_instructions` is capped at 2000 characters server-side.
 */
export interface StorySuggestRequestBody {
  novel_id: string;
  chapter_id?: string;
  author_instructions?: string;
}
```

In `packages/web/components/studio/editor/useUnblockStream.ts`, extend the body passed to `streamStorySuggestions` (lines 65-70):

```ts
        streamStorySuggestions(
          novelId,
          {
            novel_id: novelId,
            chapter_id: chapterId,
            author_instructions: instructionsRef.current.trim() || undefined,
          },
```

- [ ] **Step 4: Run the tests to verify green**

Run: `pnpm --filter narrare-web exec vitest run lib/hooks/__tests__/useUnblockStream.test.tsx lib/api/__tests__/story-suggest-stream.test.tsx && pnpm --filter narrare-web run type-check`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/lib/api/story-suggest-stream.ts packages/web/components/studio/editor/useUnblockStream.ts packages/web/lib/hooks/__tests__/useUnblockStream.test.tsx
git commit -m "fix(web): send novel_id in story-suggest request body (B02)"
```

---

### Task 6: Rewrite context clamped to the 500-char backend cap (B01, part 1)

**Layer:** Frontend · **Blocker:** B01

**Files:**
- Create: `packages/web/components/studio/editor/selectionContext.ts`
- Modify: `packages/web/components/studio/editor/useRewriteFlow.ts:57-81` (drop the local 800-radius helper)
- Test: `packages/web/components/studio/editor/__tests__/selectionContext.test.ts` (new)

**Interfaces:**
- Produces:

```ts
export const AI_CONTEXT_RADIUS_CHARS = 500;
export interface SelectionContext { contextBefore: string; contextAfter: string }
export function getSelectionContext(editor: Editor, from: number, to: number): SelectionContext
```

Consumed by this task (`useRewriteFlow`), Task 7's sibling surface, and Task 12 (co-author selection capture).

**Root cause (2× why):**
- Why guaranteed 422? `RewriteRequest` caps `context_before`/`context_after` at 500 chars (`schemas_rewrite.py:38-47`); the FE extracted a radius of 800 (`useRewriteFlow.ts:60`, evidence `09-REPORT.txt:119`), so any selection not near the document edges sends >500-char fields.
- Why 800? The radius was chosen locally without consulting the BE cap; nothing shares a constant between the FE extraction and the BE schema (RULE-17 gap at the value level, not the name level).

**Ruling (per task briefing):** the FE complies with the documented cap — BE contract unchanged. The radius IS the cap (500), making compliant payloads true by construction.

**Alternatives considered:**
1. Radius 500 via shared helper (chosen) — correct by construction, reusable by co-author (Task 12) which has the same cap.
2. Truncate after extraction (`payload.contextBefore.slice(0, 500)`) — keeps two magic numbers drifting apart.
3. Raise the BE cap to 800 — contract change to accommodate a FE bug; also silently invites larger drift next time.

- [ ] **Step 1: Write the failing unit test**

Create `packages/web/components/studio/editor/__tests__/selectionContext.test.ts`:

```ts
/**
 * selectionContext tests — context extraction honors the backend cap.
 *
 * Audit B01 regression: the rewrite flow extracted an 800-char radius while
 * the backend caps context_before/context_after at 500 chars (guaranteed 422).
 *
 * @module selectionContext.test
 */

import { Editor } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import { describe, expect, it } from "vitest";
import { AI_CONTEXT_RADIUS_CHARS, getSelectionContext } from "../selectionContext";

function createTestEditor(content: string): Editor {
  const element = document.createElement("div");
  document.body.appendChild(element);
  return new Editor({ element, extensions: [StarterKit], content });
}

describe("getSelectionContext", () => {
  it("clamps context to the 500-char backend cap on both sides", () => {
    const editor = createTestEditor(`<p>${"a".repeat(2000)}</p>`);
    editor.commands.setTextSelection({ from: 1000, to: 1100 });

    const { contextBefore, contextAfter } = getSelectionContext(editor, 1000, 1100);

    expect(contextBefore.length).toBe(AI_CONTEXT_RADIUS_CHARS);
    expect(contextAfter.length).toBe(AI_CONTEXT_RADIUS_CHARS);
    expect(contextBefore).toBe("a".repeat(AI_CONTEXT_RADIUS_CHARS));
    editor.destroy();
  });

  it("returns shorter context near the document edges without crashing", () => {
    const editor = createTestEditor("<p>Hello selection world</p>");
    const { contextBefore } = getSelectionContext(editor, 1, 6);

    expect(contextBefore.length).toBeLessThanOrEqual(AI_CONTEXT_RADIUS_CHARS);
    editor.destroy();
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pnpm --filter narrare-web exec vitest run components/studio/editor/__tests__/selectionContext.test.ts`
Expected: FAIL — module `../selectionContext` does not exist. Record output.

- [ ] **Step 3: Create the helper and rewire the flow**

Create `packages/web/components/studio/editor/selectionContext.ts`:

```ts
/**
 * Selection-context extraction shared by the AI selection tools.
 *
 * The backend caps `context_before` / `context_after` at 500 chars for both
 * rewrite (`apps/api/narrare/writing/schemas_rewrite.py`) and co-author
 * (`apps/api/narrare/writing/schemas_coauthor.py`). Extracting with a radius
 * of exactly that cap guarantees compliant payloads by construction (audit
 * B01: a local radius of 800 produced a guaranteed 422 on nearly every
 * selection).
 */

import type { Editor } from "@tiptap/react";

/** Maximum characters of before/after context the backend accepts. */
export const AI_CONTEXT_RADIUS_CHARS = 500;

/** Context around a selection, capped to the backend limit. */
export interface SelectionContext {
  contextBefore: string;
  contextAfter: string;
}

/** Extract up to {@link AI_CONTEXT_RADIUS_CHARS} of context around a range. */
export function getSelectionContext(
  editor: Editor,
  from: number,
  to: number,
): SelectionContext {
  return {
    contextBefore: editor.state.doc.textBetween(
      Math.max(0, from - AI_CONTEXT_RADIUS_CHARS),
      from,
      " ",
    ),
    contextAfter: editor.state.doc.textBetween(
      to,
      Math.min(editor.state.doc.content.size, to + AI_CONTEXT_RADIUS_CHARS),
      " ",
    ),
  };
}
```

In `packages/web/components/studio/editor/useRewriteFlow.ts`:

1. Add `import { getSelectionContext } from "./selectionContext";`
2. Delete the whole local `getSelectionContext` callback (lines 57-71, the one with `const contextRadius = 800;`).
3. In `handleAIRewrite`, change the staged selection to use the helper:

```ts
    setRewriteSelection({
      text: selectedText,
      from,
      to,
      ...getSelectionContext(editor, from, to),
    });
```

4. Update the `useCallback` dependency array of `handleAIRewrite` from `[editor, getSelectionContext]` to `[editor]` (the helper is a pure module import).

- [ ] **Step 4: Run the tests to verify green**

Run: `pnpm --filter narrare-web exec vitest run components/studio/editor/__tests__/selectionContext.test.ts components/studio/editor/__tests__/ && pnpm --filter narrare-web run type-check`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/studio/editor/selectionContext.ts packages/web/components/studio/editor/useRewriteFlow.ts packages/web/components/studio/editor/__tests__/selectionContext.test.ts
git commit -m "fix(web): clamp rewrite context radius to backend 500-char cap (B01)"
```

---

### Task 7: Rewrite errors render when no alternatives arrived (B01, part 2)

**Layer:** Frontend · **Blocker:** B01

**Files:**
- Create: `packages/web/components/studio/editor/RewriteErrorBanner.tsx`
- Modify: `packages/web/components/studio/editor/TipTapEditorController.ts:88-114` (expose `setRewriteError`)
- Modify: `packages/web/components/studio/TipTapEditor.tsx:100-167` (render the banner)
- i18n parity data: `packages/i18n/messages/{en,de,fr}/studio.json` (one key `aiActions.dismiss`)
- Test: `packages/web/components/studio/editor/__tests__/RewriteErrorBanner.test.tsx` (new)

**Interfaces:**
- Consumes: `controller.rewriteError` (`AIErrorResponse | null`), `controller.setRewriteError` (new on the controller surface), `controller.handleAIRewrite`.
- Produces: `RewriteErrorBanner({ error, onRetry, onDismiss, t })` — renders `role="alert"`, `data-testid="rewrite-error-banner"`.

**Root cause (2× why):**
- Why does the modal "close silently" on failure? `RewriteSuggestionModal` (which owns the error UI) only mounts when `controller.aiSuggestion` is truthy (`TipTapEditor.tsx:147`), and on error `useRewriteOperation.onError` resets `aiSuggestion` to `null` + phase to `idle` when no alternatives exist — so on a pre-stream failure (the 422 fires before any data) NO error surface is mounted; `rewriteError` is set but rendered nowhere.
- Why is the error surface coupled to suggestion presence? The modal was designed for in-modal failures (style-variant regeneration) where alternatives already exist; the pre-stream failure path was never designed — the two failure classes need two surfaces.

**Alternatives considered:**
1. Standalone banner when `rewriteError && !aiSuggestion` (chosen) — no state-machine changes; covers every pre-stream failure; modal keeps handling in-modal failures.
2. Keep the modal mounted with a placeholder empty suggestion set — couples the error fix to the empty-suggestion list/footer behavior (empty-accept hazards, audit M06 family); touches more code with more risk.
3. Toast via a global notifier — audit 08c showed the toast notifier can be null on error paths; adds a dependency for no gain.

- [ ] **Step 1: Write the failing component test**

Create `packages/web/components/studio/editor/__tests__/RewriteErrorBanner.test.tsx`:

```tsx
/**
 * RewriteErrorBanner tests — the standalone rewrite error surface.
 *
 * Audit B01 regression: pre-stream failures (e.g. 422) reset the flow to
 * idle with no suggestion, so the modal's error UI never mounted and the
 * modal "closed silently". The banner renders the structured error whenever
 * it is set and no suggestion modal is showing.
 *
 * @module RewriteErrorBanner.test
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
import { RewriteErrorBanner } from "../RewriteErrorBanner";

const t = ((key: string) => key) as never;

function makeError(overrides: Partial<AIErrorResponse> = {}): AIErrorResponse {
  return {
    kind: "http",
    status: 422,
    i18nKey: "aiActions.errorDefault",
    userMessage: "mapped message",
    retryable: false,
    cause: new Error("boom"),
    ...overrides,
  };
}

describe("RewriteErrorBanner", () => {
  it("renders the resolved error message with role=alert", () => {
    render(
      <RewriteErrorBanner error={makeError()} onRetry={vi.fn()} onDismiss={vi.fn()} t={t} />,
    );
    const banner = screen.getByTestId("rewrite-error-banner");
    expect(banner).toHaveAttribute("role", "alert");
    expect(banner).toHaveTextContent("aiActions.errorDefault");
  });

  it("falls back to userMessage when the i18n key is unknown", () => {
    render(
      <RewriteErrorBanner
        error={makeError({ i18nKey: "no.such.key" })}
        onRetry={vi.fn()}
        onDismiss={vi.fn()}
        t={t}
      />,
    );
    expect(screen.getByTestId("rewrite-error-banner")).toHaveTextContent("mapped message");
  });

  it("shows retry only for retryable errors and wires dismiss", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    const onDismiss = vi.fn();

    const { rerender } = render(
      <RewriteErrorBanner error={makeError({ retryable: false })} onRetry={onRetry} onDismiss={onDismiss} t={t} />,
    );
    expect(screen.queryByText("aiActions.retry")).toBeNull();

    rerender(
      <RewriteErrorBanner error={makeError({ retryable: true })} onRetry={onRetry} onDismiss={onDismiss} t={t} />,
    );
    await user.click(screen.getByText("aiActions.retry"));
    expect(onRetry).toHaveBeenCalledOnce();

    await user.click(screen.getByText("aiActions.dismiss"));
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});
```

(The `t` fake returns the key — that is why textContent assertions use the key strings.)

- [ ] **Step 2: Run it to verify it fails**

Run: `pnpm --filter narrare-web exec vitest run components/studio/editor/__tests__/RewriteErrorBanner.test.tsx`
Expected: FAIL — module `../RewriteErrorBanner` does not exist. Record output.

- [ ] **Step 3: Add the i18n key (en/de/fr parity — RULE-16)**

In each of `packages/i18n/messages/{en,de,fr}/studio.json`, inside the existing `"aiActions"` object (next to `"retry"`), add one key:

- en: `"dismiss": "Dismiss"`
- de: `"dismiss": "Schließen"`
- fr: `"dismiss": "Fermer"`

- [ ] **Step 4: Implement the banner, controller surface, and mount**

Create `packages/web/components/studio/editor/RewriteErrorBanner.tsx`:

```tsx
"use client";

/**
 * Standalone rewrite error surface (audit B01).
 *
 * The RewriteSuggestionModal renders errors only while mounted, and it
 * mounts only when an alternative has arrived (`aiSuggestion`). On a
 * pre-stream failure (e.g. a 422 before any data) the flow resets to idle
 * and the modal never opens — the error was rendered nowhere ("modal
 * closes silently"). This banner renders the structured error whenever one
 * is set and no suggestion modal is showing.
 */

import { AlertTriangle } from "lucide-react";
import type { useTranslations } from "next-intl";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";

type StudioTranslator = ReturnType<typeof useTranslations>;

interface RewriteErrorBannerProps {
  readonly error: AIErrorResponse;
  readonly onRetry: () => void;
  readonly onDismiss: () => void;
  readonly t: StudioTranslator;
}

export function RewriteErrorBanner({ error, onRetry, onDismiss, t }: RewriteErrorBannerProps) {
  return (
    <div
      role="alert"
      data-testid="rewrite-error-banner"
      className="absolute bottom-4 left-1/2 -translate-x-1/2 z-40 max-w-xl w-full mx-4 px-4 py-3 flex items-start gap-2 bg-card border border-destructive/30 rounded-lg shadow-lg text-sm"
    >
      <AlertTriangle className="w-4 h-4 text-destructive flex-shrink-0 mt-0.5" />
      <p className="flex-1 text-foreground">{resolveMessage(error, t)}</p>
      {error.retryable && (
        <button
          type="button"
          onClick={onRetry}
          className="underline hover:no-underline text-primary"
        >
          {t("aiActions.retry")}
        </button>
      )}
      <button
        type="button"
        onClick={onDismiss}
        className="underline hover:no-underline text-muted-foreground"
      >
        {t("aiActions.dismiss")}
      </button>
    </div>
  );
}

/** Resolve a structured AIErrorResponse to a user-facing message. */
function resolveMessage(error: AIErrorResponse, t: StudioTranslator): string {
  try {
    return t(error.i18nKey as Parameters<typeof t>[0]);
  } catch {
    return error.userMessage || t("aiActions.errorDefault");
  }
}
```

In `packages/web/components/studio/editor/TipTapEditorController.ts`, add to the returned object (next to `rewriteError: rewrite.rewriteError,`):

```ts
    setRewriteError: rewrite.setRewriteError,
```

In `packages/web/components/studio/TipTapEditor.tsx`:

1. Import: `import { RewriteErrorBanner } from "./editor/RewriteErrorBanner";`
2. Inside the root `<div className="relative flex-1">`, directly AFTER the `{controller.aiSuggestion && (…RewriteSuggestionModal…)}` block (~line 165), add:

```tsx
      {controller.rewriteError && !controller.aiSuggestion && (
        <RewriteErrorBanner
          error={controller.rewriteError}
          onRetry={() => {
            controller.setRewriteError(null);
            controller.handleAIRewrite();
          }}
          onDismiss={() => controller.setRewriteError(null)}
          t={t}
        />
      )}
```

(`handleAIRewrite` re-reads the live selection and is a safe no-op when the selection no longer qualifies — its own guards apply.)

- [ ] **Step 5: Run the tests to verify green**

Run: `pnpm --filter narrare-web exec vitest run components/studio/editor/__tests__/RewriteErrorBanner.test.tsx components/studio/editor/__tests__/RewriteSuggestionModal.test.tsx && pnpm --filter narrare-web run type-check && pnpm --filter narrare-web run check:testid`
Expected: ALL PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/web/components/studio/editor/RewriteErrorBanner.tsx packages/web/components/studio/editor/TipTapEditorController.ts packages/web/components/studio/TipTapEditor.tsx packages/i18n/messages/en/studio.json packages/i18n/messages/de/studio.json packages/i18n/messages/fr/studio.json packages/web/components/studio/editor/__tests__/RewriteErrorBanner.test.tsx
git commit -m "fix(web): render rewrite errors when no alternatives arrived (B01)"
```

---

### Task 8: KB entry detail renders without `field_groups` (B04, part 1)

**Layer:** Frontend · **Blocker:** B04

**Files:**
- Modify: `packages/web/components/studio/kb/KBEntryDetail.tsx` (remove structured-template paths)
- Delete: `packages/web/components/studio/kb/KBEntryTemplateFields.tsx` (collapses into `KBFlatEditor`)
- Modify: `packages/web/components/studio/kb/KBFlatEditor.tsx` (drop `template` prop + fields branch)
- Test: `packages/web/components/studio/kb/__tests__/KBEntryDetail.graceful.test.tsx` (new)

**Interfaces:**
- Consumes: the REAL template payload `TemplateDetailResponse` (`{entity_type, scope, content, base_content, schema_version, based_on_version, is_overridden}` — `apps/api/narrare/templates/schemas.py:24-35`). It has NO `field_groups`, NO `fields`, NO `sections`, NO `meta`.
- Produces: `KBEntryDetail` renders every entity detail view as metadata display + flat body editor (via `KBFlatEditor`) regardless of template shape; `KBFlatEditor({fieldValues, entryMetadata, body, onFieldChange, onBodyChange})` (no template prop).

**Root cause (2× why):**
- Why does every entity detail view hit the error boundary? `KBEntryDetail.tsx:35` reads `template.field_groups.length` (and `KBEntryTemplateFields.tsx:41` the same) on the object returned by `GET /novels/{id}/kb/templates/{type}` — which never carries `field_groups` → `undefined.length` → TypeError (evidence `08-report` bug #1, 2× pageerror).
- Why did the code expect those keys? The FE `KBTemplate` interface (`lib/api/kb.ts:148-153`) describes a structured template schema that the backend never served on this route — a RULE-17 contract drift; unit tests mock the template with the fantasy shape, so both sides stayed green while the integration crashed.

**Alternatives considered:**
1. Render flat always (chosen) — the real contract carries a YAML prompt template, not a field schema; the flat editor (metadata + body textarea) is the correct rendering for it and already exists.
2. Null-safe reads (`template?.field_groups?.length ?? 0`) keeping the structured branches — compiles today, but Task 9 removes the keys from the type; dead branches must go anyway (RULE-20: no half-implementations).
3. Parse `template.content` frontmatter into field groups in the FE — re-implements template semantics client-side; wrong layer, large scope.

- [ ] **Step 1: Write the failing component test**

Create `packages/web/components/studio/kb/__tests__/KBEntryDetail.graceful.test.tsx`:

```tsx
/**
 * KBEntryDetail graceful-render tests — audit B04 regression.
 *
 * `GET /novels/{id}/kb/templates/{type}` returns `TemplateDetailResponse`
 * (no `field_groups`); the detail view read `template.field_groups.length`
 * and crashed into the error boundary on EVERY entity. After the fix the
 * view renders metadata + flat body editor for the real contract shape.
 *
 * @module KBEntryDetail.graceful.test
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { KBEntry, KBRelationship } from "@/lib/api/kb";
import { KBEntryDetail } from "../KBEntryDetail";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock("@/lib/hooks/useKB", () => ({
  useKBTemplate: () => ({
    // Real TemplateDetailResponse shape — NO field_groups/fields/sections/meta.
    data: {
      entity_type: "character",
      scope: "user",
      content: "---\nprompt_type: kb\n---\n\nbody",
      base_content: null,
      schema_version: "2.0.0",
      based_on_version: null,
      is_overridden: false,
    },
    isLoading: false,
  }),
  useUpdateKBEntry: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
  useDeleteKBEntry: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
}));

vi.mock("../KBEntryHeader", () => ({ KBEntryHeader: () => <div data-testid="kb-entry-header" /> }));
vi.mock("../KBMetadataBar", () => ({ KBMetadataBar: () => <div data-testid="kb-metadata-bar" /> }));
vi.mock("../KBRelationshipSection", () => ({
  KBRelationshipSection: () => <div data-testid="kb-relationships" />,
}));
vi.mock("../KBEntryAISections", () => ({
  KBEntryAISections: () => <div data-testid="kb-ai-sections" />,
}));
vi.mock("@/components/kb/ScopeToggle", () => ({ ScopeToggle: () => null }));
vi.mock("@/components/ui/confirm-dialog", () => ({ ConfirmDialog: () => null }));

const entry = {
  id: "entry-1",
  entity_type: "character",
  name: "Alice",
  status: "draft",
  tags: ["hero"],
  metadata: { origin: "Chapter 1" },
  body: "A brave hero who fears rivers.",
} as unknown as KBEntry;

describe("KBEntryDetail with the real template contract", () => {
  it("renders without crashing and shows the flat body editor", () => {
    render(
      <KBEntryDetail
        novelId="novel-1"
        entry={entry}
        relationships={[] as unknown as KBRelationship[]}
        onDeleted={vi.fn()}
      />,
    );

    expect(screen.getByTestId("kb-entry-header")).toBeInTheDocument();
    expect(screen.getByLabelText("kb.body")).toBeInTheDocument();
    expect(screen.getByDisplayValue("A brave hero who fears rivers.")).toBeInTheDocument();
    expect(screen.getByText("Origin:")).toBeInTheDocument(); // metadata fallback display
  });
});
```

Note for the implementer: `getByLabelText("kb.body")` requires the flat editor's `<label htmlFor="entry-body">` to keep using `t("kb.body")` — with the mocked `t` that is the literal key. If the metadata assertion is brittle against the metadata render, assert via `getByText("Chapter 1")` instead (the VALUE must appear).

- [ ] **Step 2: Run it to verify it fails**

Run: `pnpm --filter narrare-web exec vitest run components/studio/kb/__tests__/KBEntryDetail.graceful.test.tsx`
Expected: FAIL — render throws `TypeError: Cannot read properties of undefined (reading 'length')`. Record output.

- [ ] **Step 3: Implement the always-flat detail view**

In `packages/web/components/studio/kb/KBEntryDetail.tsx`:

1. Replace the `KBEntryTemplateFields` import with `import { KBFlatEditor } from "./KBFlatEditor";` and delete `import { KBEntrySections } from "./KBEntrySections";` and `import { buildBodyFromSections, parseSectionsFromBody } from "./kbBodyUtils";`
2. Delete `const hasTemplate = …` (line 35).
3. Delete the `sectionContents` state; in the `useEffect`, replace the whole body with:

```ts
  useEffect(() => {
    setName(entry.name);
    setStatus(entry.status);
    setTags(entry.tags);
    setFieldValues(entry.metadata as Record<string, unknown>);
    setExtraBody(entry.body);
  }, [entry]);
```

4. Delete the `sortedSections` memo.
5. In `handleSave`, replace the body construction with `const body = extraBody;`
6. Replace the `<KBEntryTemplateFields … />` render with:

```tsx
        <KBFlatEditor
          fieldValues={fieldValues}
          entryMetadata={entry.metadata}
          body={extraBody}
          onFieldChange={handleFieldChange}
          onBodyChange={setExtraBody}
        />
```

7. Delete the whole `<KBEntrySections … />` render block.
8. Change the template hook destructuring from `const { data: template, isLoading: templateLoading } = useKBTemplate(novelId, entry.entity_type);` to `const { isLoading: templateLoading } = useKBTemplate(novelId, entry.entity_type);` (the query stays mounted — it drives the loading state — but nothing reads the payload anymore).

In `packages/web/components/studio/kb/KBFlatEditor.tsx`: remove the `template` prop from the interface and the destructuring, delete the `hasFlatFields` branch (lines 40-69) and the `KBMoreFields`/`KBTypeField` imports — the component renders the metadata fallback display + the body textarea only (both already present below the deleted branch).

Delete `packages/web/components/studio/kb/KBEntryTemplateFields.tsx` (its only consumer was `KBEntryDetail`; its structured branch is unreachable under the real contract). Also delete its test file if one exists.

- [ ] **Step 4: Run the tests to verify green**

Run: `pnpm --filter narrare-web exec vitest run components/studio/kb && pnpm --filter narrare-web run type-check`
Expected: ALL PASS (if `KBView.test.tsx` or other suites referenced the deleted component or the old template shape, update their mocks to the real shape — same RULE-17 rationale).

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/studio/kb/
git commit -m "fix(web): render KB entry detail gracefully without field groups (B04)"
```

---

### Task 9: `KBTemplate` type aligned with `TemplateDetailResponse` (B04, part 2)

**Layer:** Frontend · **Blocker:** B04 (RULE-17 contract pin)

**Files:**
- Modify: `packages/web/lib/api/kb.ts:120-156` (reshape `KBTemplate`, delete `KBTemplateMeta`)
- Test: `packages/web/lib/api/__tests__/kb-template-contract.test.ts` (new)

**Interfaces:**
- Produces: `KBTemplate` mirrors `TemplateDetailResponse` exactly: `{entity_type: string; scope: string; content: string; base_content: string | null; schema_version: string; based_on_version: string | null; is_overridden: boolean}`.
- Deliberately kept: `KBTemplateField` / `KBTemplateFieldGroup` / `KBTemplateSection` type exports — still referenced by the dormant section components (`KBEntrySections`, `KBTypeField`) kept for a future structured-template surface. Deleting them is out of scope (YAGNI boundary documented here).

**Root cause:** the type-level half of B04 — after Task 8 no consumer reads the fantasy keys, so the type can now tell the truth. This task exists so the NEXT developer's mock data cannot reintroduce the drift (the compile-time ratchet below fails if the keys return).

**Alternatives considered:**
1. Reshape the interface in place (chosen) — smallest diff; `useKBTemplate` keeps its signature (type name unchanged).
2. Rename to `KBTemplateDetail` and alias — churn in every import for zero behavior change.

- [ ] **Step 1: Write the failing test (type ratchet)**

Create `packages/web/lib/api/__tests__/kb-template-contract.test.ts`:

```ts
/**
 * KBTemplate contract tests — RULE-17 parity with TemplateDetailResponse.
 *
 * Audit B04: the interface previously claimed `meta` / `fields` /
 * `field_groups` / `sections`, none of which the backend route ever
 * returned. The @ts-expect-error lines are a compile-time ratchet: if any
 * of those keys reappear on the type, type-check FAILS with "unused
 * '@ts-expect-error' directive".
 *
 * @module kb-template-contract.test
 */

import { describe, expect, it } from "vitest";
import type { KBTemplate } from "@/lib/api/kb";

const realPayload = {
  entity_type: "character",
  scope: "user",
  content: "---\nprompt_type: kb\n---\n\nbody",
  base_content: null,
  schema_version: "2.0.0",
  based_on_version: null,
  is_overridden: false,
} as const satisfies KBTemplate;

describe("KBTemplate mirrors TemplateDetailResponse", () => {
  it("accepts a real payload", () => {
    expect(realPayload.entity_type).toBe("character");
    expect(realPayload.is_overridden).toBe(false);
  });

  it("no longer declares the fantasy keys (compile-time ratchet)", () => {
    const template = realPayload as KBTemplate;
    // @ts-expect-error — the backend contract has no field_groups (audit B04)
    expect(template.field_groups).toBeUndefined();
    // @ts-expect-error — the backend contract has no fields (audit B04)
    expect(template.fields).toBeUndefined();
    // @ts-expect-error — the backend contract has no sections (audit B04)
    expect(template.sections).toBeUndefined();
    // @ts-expect-error — the backend contract has no meta (audit B04)
    expect(template.meta).toBeUndefined();
  });
});
```

Note: `template.field_groups` on the CURRENT type is valid TypeScript, so `@ts-expect-error` makes this file FAIL type-check right now — that is the red phase. At runtime the assertions pass (the keys are absent from the payload object), so run BOTH vitest and type-check and record the type-check failure as red evidence.

- [ ] **Step 2: Run it to verify it fails**

Run: `pnpm --filter narrare-web exec vitest run lib/api/__tests__/kb-template-contract.test.ts && pnpm --filter narrare-web run type-check`
Expected: vitest may pass, `type-check` FAILS — "Unused '@ts-expect-error' directive" (the keys still exist on the type). Record output.

- [ ] **Step 3: Reshape the type**

In `packages/web/lib/api/kb.ts`, delete the `KBTemplateMeta` interface (lines 142-147) and replace `KBTemplate` (lines 148-154) with:

```ts
/**
 * Template detail for a KB entity type.
 *
 * RULE-17 contract parity: mirrors `TemplateDetailResponse` in
 * `apps/api/narrare/templates/schemas.py` exactly (audit B04: the previous
 * shape claimed `meta` / `fields` / `field_groups` / `sections`, none of
 * which this route has ever returned).
 */
export interface KBTemplate {
  entity_type: string;
  scope: string;
  content: string;
  base_content: string | null;
  schema_version: string;
  based_on_version: string | null;
  is_overridden: boolean;
}
```

Keep `KBTemplateField`, `KBTemplateFieldGroup`, `KBTemplateSection` exported (still consumed by `KBEntrySections` / `KBTypeField`; see Interfaces).

- [ ] **Step 4: Run the tests to verify green**

Run: `pnpm --filter narrare-web exec vitest run lib/api/__tests__/kb-template-contract.test.ts && pnpm --filter narrare-web run type-check`
Expected: ALL PASS (Task 8 already removed every consumer of the deleted keys — if type-check still fails, fix the remaining consumer, do NOT re-add keys).

- [ ] **Step 5: Commit**

```bash
git add packages/web/lib/api/kb.ts packages/web/lib/api/__tests__/kb-template-contract.test.ts
git commit -m "fix(web): align KBTemplate type with TemplateDetailResponse (B04)"
```

---

### Task 10: Continue-stream hardening + `ContinueButton` becomes presentational (B08, part 1)

**Layer:** Frontend · **Blocker:** B08

**Files:**
- Modify: `packages/web/components/studio/editor/useContinueStream.ts` (nullable editor + BE payload caps)
- Modify: `packages/web/components/studio/editor/ContinueButton.tsx` (ops-props refactor)
- Test: `packages/web/components/studio/editor/__tests__/useContinueStream.test.tsx` (new) and update `packages/web/components/studio/editor/__tests__/ContinueButton.test.tsx`

**Interfaces:**
- Produces:
  - `useContinueStream({ editor: Editor | null; chapterId: string; novelId: string; tone?: string }) -> { handleExtend(length: ExtendLength): void; handleStop(): void; isLoading: boolean; isStreaming: boolean }` — null-safe (single instance owned by `EditorView` in Task 11; `useAIOperation` reads `executeRef.current`, so closures always see the latest editor).
  - `ContinueButton({ isStreaming: boolean; onExtend(length: ExtendLength): void; onStop(): void })` — presentational (length dropdown state stays internal).

**Root cause (2× why):**
- Why is extend dead in the UI? The full machinery exists (`streamExtend` client → healthy `POST /writing/chapters/{id}/extend` SSE, `useContinueStream` hook, `ContinueButton` component) but `ContinueButton` is mounted nowhere and every palette/slash entry point is a stub — a wiring gap, not a broken part.
- Why a wiring gap? The editor chrome was rebuilt into `EditorView`/`EditorToolbar`/`EditorWorkspace` (view-layer split) and the extend surface was never re-mounted; the slash contract intentionally renders unwired ops "unavailable" (`registry.ts` availability), which masked the omission as designed behavior.

**Defect-class prevention (folded in):** `useContinueStream.handleExtend` sends the whole current paragraph split at the caret; `ExtendRequest` caps `text_before` at 10 000 and `text_after` at 2 000 chars (`schemas.py:175-186`). A long paragraph would 422 — the same FE-exceeds-BE-cap class as B01. Clamp at extraction.

**Alternatives considered:**
1. Lift the single stream owner to `EditorView`, make the button presentational (chosen) — one stream for toolbar + palette + slash; no double-extend hazard.
2. Keep `ContinueButton` owning its hook and give the palette a second instance — two independent extends can interleave inserts into one editor.
3. Store-driven orchestration — editorStore additions for a local feature; overkill.

- [ ] **Step 1: Write the failing hook test**

Create `packages/web/components/studio/editor/__tests__/useContinueStream.test.tsx`:

```tsx
/**
 * useContinueStream tests — payload caps + null-editor safety (B08).
 *
 * ExtendRequest caps text_before at 10 000 and text_after at 2 000 chars;
 * the hook previously forwarded the raw paragraph split, which 422s on long
 * paragraphs (same FE-exceeds-BE-cap class as audit B01).
 *
 * @module useContinueStream.test
 */

import { Editor } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const streamExtend = vi.hoisted(() => vi.fn(async () => {}));

vi.mock("@/lib/api/generation", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/generation")>();
  return { ...original, streamExtend: (...args: unknown[]) => streamExtend(...args) };
});

import { useContinueStream } from "../useContinueStream";

function createTestEditor(content: string): Editor {
  const element = document.createElement("div");
  document.body.appendChild(element);
  return new Editor({ element, extensions: [StarterKit], content });
}

describe("useContinueStream", () => {
  beforeEach(() => {
    streamExtend.mockClear();
  });

  it("clamps text_before to the 10 000-char backend cap", () => {
    const editor = createTestEditor(`<p>${"w".repeat(12_000)}</p>`);
    editor.commands.focus("end");

    const { result } = renderHook(() =>
      useContinueStream({ editor, chapterId: "chapter-1", novelId: "novel-1" }),
    );

    result.current.handleExtend("short");

    expect(streamExtend).toHaveBeenCalledOnce();
    const body = streamExtend.mock.calls[0][2] as { text_before: string };
    expect(body.text_before.length).toBe(10_000);
    expect(body.length).toBe("short");
    editor.destroy();
  });

  it("clamps text_after to the 2 000-char backend cap", () => {
    // Caret at the START of a long paragraph: everything after is text_after.
    const editor = createTestEditor(`<p>${"w".repeat(3_000)}</p>`);
    editor.commands.setTextSelection(1);

    const { result } = renderHook(() =>
      useContinueStream({ editor, chapterId: "chapter-1", novelId: "novel-1" }),
    );

    result.current.handleExtend("medium");

    const body = streamExtend.mock.calls[0][2] as { text_after: string | null };
    expect((body.text_after ?? "").length).toBe(2_000);
    editor.destroy();
  });

  it("is a no-op while the editor is null (Task 11 owner pattern)", () => {
    const { result } = renderHook(() =>
      useContinueStream({ editor: null, chapterId: "chapter-1", novelId: "novel-1" }),
    );

    result.current.handleExtend("medium");

    expect(streamExtend).not.toHaveBeenCalled();
  });
});
```

Also update `ContinueButton.test.tsx` to the new props API (replace hook-level assertions with ops-props assertions): render `<ContinueButton isStreaming={false} onExtend={spy} onStop={spy2} />` → click main button calls `onExtend("medium")`; open dropdown, pick "short" → next main-button click calls `onExtend("short")`; `isStreaming` renders the stop control and clicking it calls `onStop`. Keep the file's existing i18n mocking approach.

- [ ] **Step 2: Run them to verify they fail**

Run: `pnpm --filter narrare-web exec vitest run components/studio/editor/__tests__/useContinueStream.test.tsx components/studio/editor/__tests__/ContinueButton.test.tsx`
Expected: FAIL — hook test: TS error (`editor: null` not assignable) and `text_before.length` 12 000 ≠ 10 000; button test: unknown props. Record output.

- [ ] **Step 3: Implement**

In `packages/web/components/studio/editor/useContinueStream.ts`:

1. Parameter type: `readonly editor: Editor | null;`
2. In `execute`, capture and guard a local reference at the top of the promise body:

```ts
        const ed = editor;
        const req = requestRef.current;
        if (!ed || !req || ed.isDestroyed) {
          resolve();
          return;
        }
```

…then replace every `editor.` reference INSIDE the promise body with `ed.` (`ed.isDestroyed` in `onChunk`, `ed` in `finalizePendingMark`).
3. In `handleExtend`, clamp at extraction:

```ts
  const handleExtend = useCallback(
    (selectedLength: ExtendLength) => {
      if (isLoading || isStreaming) return;
      if (!editor || editor.isDestroyed) return;

      const $head = editor.state.selection.$head;
      // ExtendRequest caps: text_before ≤ 10 000, text_after ≤ 2 000 chars
      // (apps/api/narrare/writing/schemas.py) — clamp at extraction so the
      // payload is compliant by construction (same class as audit B01).
      const textBefore = $head.parent.textContent
        .slice(0, $head.parentOffset)
        .slice(0, 10_000);
      const textAfter = $head.parent.textContent
        .slice($head.parentOffset)
        .slice(0, 2_000);

      requestRef.current = { textBefore, textAfter: textAfter || null, selectedLength };
      accumulatedRef.current = "";
      start();
    },
    [editor, isLoading, isStreaming, start],
  );
```

In `packages/web/components/studio/editor/ContinueButton.tsx`, replace the component with the presentational version:

```tsx
"use client";

import { ChevronDown, Loader2, PenLine } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import type { ExtendLength } from "@/lib/api/generation";

interface ContinueButtonProps {
  /** Whether a continue/extend stream is active (owned by EditorView). */
  readonly isStreaming: boolean;
  /** Start an extension of the given target length. */
  readonly onExtend: (length: ExtendLength) => void;
  /** Stop the active extension stream. */
  readonly onStop: () => void;
}

export function ContinueButton({ isStreaming, onExtend, onStop }: ContinueButtonProps) {
  const t = useTranslations("studio");
  const [length, setLength] = useState<ExtendLength>("medium");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!dropdownOpen) return;
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [dropdownOpen]);

  return (
    <div className="relative" ref={dropdownRef}>
      <div className="flex items-center">
        <button
          type="button"
          onClick={() => (isStreaming ? onStop() : onExtend(length))}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border border-border bg-card hover:bg-accent transition-colors"
          aria-label={t("annotation.continueWriting")}
        >
          {isStreaming ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>{t("aiActions.stop")}</span>
            </>
          ) : (
            <>
              <PenLine className="w-3.5 h-3.5" />
              <span>{t("annotation.continueWriting")}</span>
            </>
          )}
        </button>
        {!isStreaming && (
          <button
            type="button"
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center px-1 py-1.5 text-xs rounded-r-md border border-l-0 border-border bg-card hover:bg-accent transition-colors"
            aria-label={t("annotation.selectLength")}
          >
            <ChevronDown className="w-3 h-3" />
          </button>
        )}
      </div>

      {dropdownOpen && !isStreaming && (
        <div className="absolute top-full left-0 mt-1 w-36 bg-card border border-border rounded-lg shadow-lg overflow-hidden z-50">
          {(["short", "medium", "long"] as const).map((len) => (
            <button
              key={len}
              type="button"
              onClick={() => {
                setLength(len);
                setDropdownOpen(false);
              }}
              className={`w-full text-left px-3 py-2 text-xs transition-colors ${
                length === len ? "bg-accent font-medium" : "hover:bg-accent"
              }`}
            >
              {t(`annotation.length.${len}`)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

(The editor-disabled guard moved into the hook — `handleExtend` no-ops on a destroyed editor.)

- [ ] **Step 4: Run the tests to verify green**

Run: `pnpm --filter narrare-web exec vitest run components/studio/editor/__tests__/useContinueStream.test.tsx components/studio/editor/__tests__/ContinueButton.test.tsx && pnpm --filter narrare-web run type-check`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/studio/editor/useContinueStream.ts packages/web/components/studio/editor/ContinueButton.tsx packages/web/components/studio/editor/__tests__/useContinueStream.test.tsx packages/web/components/studio/editor/__tests__/ContinueButton.test.tsx
git commit -m "fix(web): harden continue stream and make ContinueButton presentational (B08)"
```

---

### Task 11: Extend wired into toolbar + command palette (B08, part 2)

**Layer:** Frontend · **Blocker:** B08 (toolbar + palette entries)

**Files:**
- Modify: `packages/web/components/studio/editor-view/EditorToolbar.tsx` (render `ContinueButton`)
- Modify: `packages/web/components/studio/EditorView.tsx` (own `useContinueStream`, feed toolbar + palette)
- Modify: `packages/web/components/studio/editor-view/useEditorCommandPalette.ts` (real `startExtend`)
- Test: `packages/web/components/studio/editor-view/__tests__/useEditorCommandPalette.test.tsx` (new) and extend `packages/web/components/studio/editor-view/EditorToolbar.test.tsx`

**Interfaces:**
- Consumes: `useContinueStream` + `ContinueButton` from Task 10 (`handleExtend(length)`, `handleStop()`, `isStreaming`).
- Produces: `useEditorCommandPalette({ …, handleStartExtend: (length: "short" | "medium" | "long") => void })` → `commandContext.startExtend` calls the handler (replaces the `startExtend: () => {}` stub at `useEditorCommandPalette.ts:49`); `EditorToolbar` props gain `onExtend`, `onExtendStop`, `isExtendStreaming`.

**Root cause:** see Task 10 — this task mounts the machinery. The palette stubs (`startExtend: () => {}` line 49; also `startRewrite` line 50 stays a stub — out of scope, see Concerns) came from the palette never receiving handlers.

**Decision encoded:** the single stream owner is `EditorView` (it has `editor` from the store, `activeChapterId`, `novelId`); toolbar button + palette items call the same `handleExtend`. The slash `/continue` item becomes available in Task 12 (it needs `EditorWorkspace` to forward handlers).

- [ ] **Step 1: Write the failing palette test**

Create `packages/web/components/studio/editor-view/__tests__/useEditorCommandPalette.test.tsx`:

```tsx
/**
 * useEditorCommandPalette tests — extend wiring (audit B08).
 *
 * `commandContext.startExtend` was a `() => {}` stub; the palette's
 * "Continue Writing" commands were no-ops. The hook now receives the real
 * handler from EditorView.
 *
 * @module useEditorCommandPalette.test
 */

import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useEditorCommandPalette } from "../useEditorCommandPalette";

function makeParams() {
  return {
    handleSave: vi.fn(async () => {}),
    handleStartGeneration: vi.fn(),
    handleStopGeneration: vi.fn(async () => {}),
    handleAcceptDraft: vi.fn(),
    handleRejectDraft: vi.fn(async () => {}),
    handleStartExtend: vi.fn(),
  };
}

describe("useEditorCommandPalette", () => {
  it("wires startExtend to the host handler (B08)", () => {
    const params = makeParams();
    const { result } = renderHook(() => useEditorCommandPalette(params));

    result.current.commandContext.startExtend("short");

    expect(params.handleStartExtend).toHaveBeenCalledTimes(1);
    expect(params.handleStartExtend).toHaveBeenCalledWith("short");
  });

  it("keeps the commandContext stable across re-renders with stable inputs", () => {
    const params = makeParams();
    const { result, rerender } = renderHook(() => useEditorCommandPalette(params));
    const first = result.current.commandContext;
    rerender();
    expect(result.current.commandContext).toBe(first);
  });
});
```

Extend `packages/web/components/studio/editor-view/EditorToolbar.test.tsx` with a continue case (reuse the file's existing render helper/mocks):

```tsx
  it("renders the Continue button and forwards the default length (B08)", async () => {
    const onExtend = vi.fn();
    const user = userEvent.setup();
    render(<EditorToolbar {...baseToolbarProps} onExtend={onExtend} onExtendStop={vi.fn()} isExtendStreaming={false} />);

    await user.click(screen.getByRole("button", { name: "annotation.continueWriting" }));

    expect(onExtend).toHaveBeenCalledTimes(1);
    expect(onExtend).toHaveBeenCalledWith("medium");
  });
```

(`baseToolbarProps` = the test file's existing minimal props object plus the three new required props.)

- [ ] **Step 2: Run them to verify they fail**

Run: `pnpm --filter narrare-web exec vitest run components/studio/editor-view/__tests__/useEditorCommandPalette.test.tsx components/studio/editor-view/EditorToolbar.test.tsx`
Expected: FAIL — hook test: TS error (`handleStartExtend` not in params) + spy never called; toolbar test: unknown props / button missing. Record output.

- [ ] **Step 3: Implement**

`useEditorCommandPalette.ts`: add `handleStartExtend: (length: "short" | "medium" | "long") => void;` to `UseEditorCommandPaletteParams`, replace the stub `startExtend: (_length: "short" | "medium" | "long") => {},` with `startExtend: handleStartExtend,` and add `handleStartExtend` to the `commandContext` dependency array.

`EditorToolbar.tsx`:

1. Props: add

```ts
  /** Continue-writing (extend) operations — single owner is EditorView (B08). */
  onExtend: (length: "short" | "medium" | "long") => void;
  onExtendStop: () => void;
  isExtendStreaming: boolean;
```

2. Import `import { ContinueButton } from "../editor/ContinueButton";` and render it directly after the Generate button's separator:

```tsx
      <ToolbarSeparator />
      <ContinueButton
        isStreaming={isExtendStreaming}
        onExtend={onExtend}
        onStop={onExtendStop}
      />
```

`EditorView.tsx`:

1. Import `import { useContinueStream } from "./editor/useContinueStream";`
2. Below `generationActions`, add the single owner:

```ts
  // Continue-writing (extend) — single stream owner shared by toolbar,
  // command palette, and slash commands (audit B08). Null-safe while the
  // TipTap instance is being created.
  const continueStream = useContinueStream({
    editor,
    chapterId: activeChapterId,
    novelId,
  });
```

3. Pass to the palette: `handleStartExtend: continueStream.handleExtend,`
4. Pass to the toolbar: `onExtend={continueStream.handleExtend} onExtendStop={continueStream.handleStop} isExtendStreaming={continueStream.isStreaming}`

- [ ] **Step 4: Run the tests to verify green**

Run: `pnpm --filter narrare-web exec vitest run components/studio/editor-view && pnpm --filter narrare-web run type-check`
Expected: ALL PASS (extend `EditorView.test.tsx` mocks if it asserts the toolbar prop set).

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/studio/editor-view/EditorToolbar.tsx packages/web/components/studio/EditorView.tsx packages/web/components/studio/editor-view/useEditorCommandPalette.ts packages/web/components/studio/editor-view/__tests__/useEditorCommandPalette.test.tsx packages/web/components/studio/editor-view/EditorToolbar.test.tsx
git commit -m "fix(web): wire extend into toolbar and command palette (B08)"
```

---

### Task 12: Co-author panel in the editor + slash wiring for extend & co-author (B08 slash + B09)

**Layer:** Frontend · **Blocker:** B09 (+ B08's `/continue` slash entry)

**Files:**
- Modify: `packages/web/components/studio/EditorView.tsx` (co-author selection state + `CoAuthorPanel` mount + slash handlers)
- Modify: `packages/web/components/studio/editor-view/EditorWorkspace.tsx` (forward `slashCommandHandlers`)
- Modify: `packages/web/components/studio/editor-view/types.ts` (`EditorSurfaceProps`)
- Test: `packages/web/components/studio/editor-view/__tests__/EditorWorkspace.slash.test.tsx` (new)

**Interfaces:**
- Consumes: `CoAuthorPanel` (`components/studio/editor/CoAuthorPanel.tsx`, complete but unmounted): props `{novelId, chapterId, selectionText, contextBefore?, contextAfter?, onAccept(revisedText), onClose}`. BE contract: `selection_text` 50–10 000 chars, contexts ≤ 500 (Task 6's `getSelectionContext` supplies the capped contexts).
- Consumes: `TipTapEditor`'s `slashCommandHandlers?: Partial<SlashCommandHandlers>` prop — `onContinue`/`onCoAuthor` flip the `/continue` + `/coauthor` items from "unavailable" to "available" (`TipTapEditor.tsx:65-73` `wiredOps`) with no TipTapEditor change.
- Produces: `EditorSurfaceProps.slashCommandHandlers?: Partial<SlashCommandHandlers>` (forwarded to `TipTapEditor`).

**Root cause (2× why):**
- Why is co-author unreachable in the editor? `CoAuthorPanel` — a fully built modal (focus selection → SSE streaming → change review → apply/feedback, all against the healthy `POST /writing/chapters/{id}/co-author` endpoint) — is mounted NOWHERE (the audit's "only in NotesChatDrawer" was stale: NotesChatDrawer mounts `ChatPanel` only; `CoAuthorPanel` appears solely in a comment), and `EditorWorkspace` passes no `slashCommandHandlers`, so `/coauthor` renders "Not available here" (evidence `09e-*`).
- Why was it never mounted? The workspace/view split left host-handler wiring as an explicit contract (`SlashCommandHandlers`) that no host satisfied for co-author; the panel's only consumer was planned for the notes drawer surface and dropped there.

**Decision encoded (placement):** mount `CoAuthorPanel` as a fixed overlay from `EditorView` (same lifecycle position as the rewrite modal and `UnblockPanel`), triggered by the `/coauthor` slash command. Alternatives: (a) bubble-menu entry — duplicates the slash surface and clutters the selection menu; (b) right-panel slot — the panel is a modal flow with its own Escape/keyboard handling, not a persistent panel. Ruling on selection length: open with ANY non-empty selection; selections shorter than the BE's 50-char minimum surface through the panel's existing error phase with Retry (the panel is the error surface — no silent no-op).

- [ ] **Step 1: Write the failing wiring test**

Create `packages/web/components/studio/editor-view/__tests__/EditorWorkspace.slash.test.tsx`:

```tsx
/**
 * EditorWorkspace slash-wiring tests — audits B08 (/continue) + B09 (/coauthor).
 *
 * EditorWorkspace passed no `slashCommandHandlers`, so TipTapEditor rendered
 * the continue + coauthor slash items "unavailable" and the CoAuthorPanel
 * had no trigger. The workspace now forwards the host handlers.
 *
 * @module EditorWorkspace.slash.test
 */

import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { EditorSurfaceProps } from "../types";
import { EditorWorkspace } from "../EditorWorkspace";

const TipTapEditor = vi.hoisted(() => vi.fn(() => null));

vi.mock("../../TipTapEditor", () => ({
  TipTapEditor: (...args: unknown[]) => TipTapEditor(...args),
}));

import { TipTapEditor as TipTapEditorMock } from "../../TipTapEditor";

const baseProps: EditorSurfaceProps = {
  editor: null,
  novelId: "novel-1",
  activeChapterId: "chapter-1",
  content: "<p>Some prose</p>",
  setContent: vi.fn(),
  handleAutosave: vi.fn(async () => {}),
};

describe("EditorWorkspace slash wiring", () => {
  it("forwards slashCommandHandlers to TipTapEditor (B08/B09)", () => {
    const onContinue = vi.fn();
    const onCoAuthor = vi.fn();
    render(
      <EditorWorkspace
        {...baseProps}
        slashCommandHandlers={{ onContinue, onCoAuthor }}
      />,
    );

    expect(TipTapEditorMock).toHaveBeenCalled();
    const passed = vi.mocked(TipTapEditorMock).mock.calls[0][0];
    expect(passed.slashCommandHandlers?.onContinue).toBe(onContinue);
    expect(passed.slashCommandHandlers?.onCoAuthor).toBe(onCoAuthor);
  });

  it("omits the prop when the host provides none (backwards compatible)", () => {
    render(<EditorWorkspace {...baseProps} />);
    const passed = vi.mocked(TipTapEditorMock).mock.calls[0][0];
    expect(passed.slashCommandHandlers).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pnpm --filter narrare-web exec vitest run components/studio/editor-view/__tests__/EditorWorkspace.slash.test.tsx`
Expected: FAIL — TS error (`slashCommandHandlers` not in `EditorSurfaceProps`) and `passed.slashCommandHandlers` undefined. Record output.

- [ ] **Step 3: Implement**

`types.ts` — extend `EditorSurfaceProps` (and import the type):

```ts
import type { SlashCommandHandlers } from "../editor/slash-commands";
```

```ts
  /** Host handlers for slash commands the workspace surface wires (B08/B09). */
  slashCommandHandlers?: Partial<SlashCommandHandlers>;
```

`EditorWorkspace.tsx` — accept and forward:

```tsx
export function EditorWorkspace({
  novelId,
  activeChapterId,
  content,
  setContent,
  handleAutosave,
  slashCommandHandlers,
}: EditorSurfaceProps) {
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-4xl mx-auto">
        <TipTapEditor
          content={content}
          onChange={setContent}
          onAutosave={handleAutosave}
          autosaveInterval={30_000}
          chapterId={activeChapterId}
          novelId={novelId}
          slashCommandHandlers={slashCommandHandlers}
        />
      </div>
    </div>
  );
}
```

`EditorView.tsx`:

1. Imports:

```tsx
import { CoAuthorPanel } from "./editor/CoAuthorPanel";
import { getSelectionContext } from "./editor/selectionContext";
import type { SlashCommandHandlers } from "./editor/slash-commands";
```

2. Co-author state + handlers (below `continueStream` from Task 11):

```tsx
  // Co-author (B09): capture the selection (capped 500-char contexts, same
  // helper as rewrite — Task 6) and mount the panel as a modal overlay.
  interface CoAuthorSelectionState {
    text: string;
    from: number;
    to: number;
    contextBefore: string;
    contextAfter: string;
  }
```

(Place the interface at module scope next to `EditorViewProps`, not inside the component.)

```tsx
  const [coAuthorSelection, setCoAuthorSelection] = useState<CoAuthorSelectionState | null>(
    null,
  );

  const handleStartCoAuthor = useCallback(() => {
    if (!editor) return;
    const { from, to } = editor.state.selection;
    const text = editor.state.doc.textBetween(from, to, " ");
    if (!text.trim()) return;
    setCoAuthorSelection({ text, from, to, ...getSelectionContext(editor, from, to) });
  }, [editor]);

  const handleCoAuthorAccept = useCallback(
    (revisedText: string) => {
      if (!editor || !coAuthorSelection) return;
      editor
        .chain()
        .focus()
        .insertContentAt(
          { from: coAuthorSelection.from, to: coAuthorSelection.to },
          revisedText,
        )
        .run();
      void persistence.handleAutosave(editor.getHTML());
      setCoAuthorSelection(null);
    },
    [editor, coAuthorSelection, persistence.handleAutosave],
  );

  const slashCommandHandlers = useMemo<Partial<SlashCommandHandlers>>(
    () => ({
      onContinue: () => continueStream.handleExtend("medium"),
      onCoAuthor: handleStartCoAuthor,
    }),
    [continueStream.handleExtend, handleStartCoAuthor],
  );
```

3. Pass to the workspace: `slashCommandHandlers={slashCommandHandlers}` (add to the existing `<EditorWorkspace … />` props).
4. Mount the panel after `<EditorOverlays … />`:

```tsx
          {coAuthorSelection && (
            <CoAuthorPanel
              novelId={novelId}
              chapterId={activeChapterId}
              selectionText={coAuthorSelection.text}
              contextBefore={coAuthorSelection.contextBefore}
              contextAfter={coAuthorSelection.contextAfter}
              onAccept={handleCoAuthorAccept}
              onClose={() => setCoAuthorSelection(null)}
            />
          )}
```

- [ ] **Step 4: Run the tests to verify green**

Run: `pnpm --filter narrare-web exec vitest run components/studio/editor-view components/studio/__tests__/EditorView.test.tsx components/studio/editor/__tests__/CoAuthorPanel.keyboard.test.tsx && pnpm --filter narrare-web run type-check`
Expected: ALL PASS (update `EditorView.test.tsx` mocks if it snapshots the workspace props).

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/studio/EditorView.tsx packages/web/components/studio/editor-view/EditorWorkspace.tsx packages/web/components/studio/editor-view/types.ts packages/web/components/studio/editor-view/__tests__/EditorWorkspace.slash.test.tsx
git commit -m "fix(web): wire co-author panel into editor and slash commands (B09)"
```

---

## Self-Review (performed 2026-10-12, before publication)

**1. Spec/audit coverage — B01–B09:** B01 → Tasks 6+7 (clamp + error surface; BE contract untouched per ruling). B02 → Task 5. B03 → Task 4 (registration ruling; FE URL is contract-correct). B04 → Tasks 8+9 (graceful render + RULE-17 type). B05 → Task 1. B06 → Task 2 (mode + variable supply). B07 → Task 3. B08 → Tasks 10+11+12 (owner refactor, toolbar+palette, slash `/continue`). B09 → Task 12 (panel mount + `/coauthor`). All nine blockers covered; no task implements anything outside B01–B09 (M/N items untouched).

**2. Placeholder scan:** no "TBD/TODO/similar to Task N" — every code step carries the actual code; the two places where the implementer adapts an existing file's mock setup (`KBEntryDetail.graceful.test.tsx` display-value fallback, `ContinueButton.test.tsx` rewrite) include the full new-test semantics inline.

**3. Type consistency (cross-task):** `getSelectionContext(editor, from, to)` + `AI_CONTEXT_RADIUS_CHARS` defined in Task 6, consumed verbatim in Task 12. `useContinueStream` returns `{handleExtend, handleStop, isLoading, isStreaming}` (Task 10) — Task 11 uses exactly those. `ContinueButton` props (Task 10) match Task 11's render. `handleStartExtend: (length: "short"|"medium"|"long") => void` (Task 11 hook test) matches `CommandContext.startExtend` (`commands.ts:46`). `StorySuggestRequestBody.novel_id: string` (Task 5) matches the BE `Field(...)` requirement. `KBTemplate` (Task 9) matches `TemplateDetailResponse` field-for-field; Task 8's test payload uses that exact shape. `EditorSurfaceProps.slashCommandHandlers?: Partial<SlashCommandHandlers>` (Task 12) matches `TipTapEditorProps.slashCommandHandlers` — verified same optional-partial type.

**4. Boundary/dependency-direction check:** no router logic (RULE-06 violations); the lifespan binder is wiring-only; `improve_analyzer` change stays app-layer (prompt assembly remains in `core/prompts` — RULE-02/02b intact); POV KB supply goes through the existing `KBContextProviderProtocol` (ADR-067), no new cross-module imports; FE tasks touch `packages/web` only. Task ordering is dependency-safe (6 → 12; 10 → 11 → 12; 8 → 9); every task ends green and committable.

**5. Verification path:** each task's Step "run red" names the exact command and the expected failure signature; green steps re-run the same suites plus neighbors. Full-wave verification after Task 12 (coordinator): `uv run --all-packages pytest tests/unit tests/integration -m "not schema_mutating" -n auto` and `pnpm --filter narrare-web exec vitest run` plus `pnpm --filter narrare-web run type-check` and `just check-architecture`.
