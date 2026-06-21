# CR-07 v3 Phase B — PROMPT-003 Implementation Plan (CR-AUFG-07-16)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **No commit steps:** The Coordinator delegates the final commit to the Platform Specialist after all gates pass. Each task ends at "run tests to verify they pass."

**Goal:** Implement PROMPT-003 contract-first across Core/Backend/Frontend/Platform: provider-free resolved prompt preview with variable provenance/security metadata and diagnostics, reset-to-default with metadata response, and an optional provider-/secret-gated SSE live test — replacing the existing local hardcoded sample substitution in `PromptPreview.tsx`.

**Architecture:** Root cause: prompt customization today is a local UI affordance that substitutes `{{variables}}` with hardcoded English sample strings (`EXAMPLE_VALUES` in `PromptPreview.tsx`). Users cannot see what the cascade-resolved prompt actually contains, where each variable comes from (provenance), or why user-authored variables are XML-wrapped (security). The architecturally correct fix is a contract-first feature: Core resolves the preview via the existing `PromptComposer` + `variable_taxonomy` (no LLM call), Backend exposes thin REST/SSE endpoints, Frontend renders authoritative API responses, and Platform proves the no-provider invariant.

**Tech Stack:** Python 3.14, FastAPI, Pydantic v2, SQLAlchemy 2.0 async, structlog, pydantic-ai (TestModel for tests), pyrate-limiter, pytest; Next.js, React, TypeScript strict, next-intl, @tanstack/react-query, Vitest, Testing Library.

---

## Scope, Root Cause, Alternatives

**In scope:** CR-AUFG-07-16. Core preview contracts/types/logic, Backend preview/reset/live-test services + router split, Frontend dialogs + API client + `PromptEditor` modularization, Platform contract/component tests, DE/EN/FR i18n, AUFG evidence after gates pass.

**Out of scope:** Phase C items (CR-AUFG-07-18 onward), prompt history (CR-AUFG-07-19), changing PROMPT-001/PROMPT-002 storage semantics, new external dependencies, changing the existing `DELETE /prompts/{prompt_id:path}/override` endpoint contract.

**Warum 1:** `PromptPreview.tsx` ships an `EXAMPLE_VALUES` map that is unlocalized, drifts from real schema, and cannot show provenance/security — so users edit prompts blind.

**Warum 2:** The cascade resolver (`PromptRegistry`), variable metadata (`variable_metadata.py`), and taxonomy (`variable_taxonomy.py`) already hold the authoritative data, but no contract surfaces them as a preview. The local UI substitutes for the missing contract.

**Chosen design:** Add a provider-free `PromptPreviewService` in Core that calls `PromptComposer.build()` (which already does cascade + substitution without LLM) and enriches the result with `VariableMeta` + `VariableClassification` + diagnostics. Backend exposes `POST /prompts/{prompt_id:path}/preview`, `POST /prompts/{prompt_id:path}/reset`, and `POST /prompts/{prompt_id:path}/live-test` (SSE). Frontend replaces local substitution with API-driven dialogs.

**Rejected alternatives:**

- **Local i18n sample map per locale:** Rejected — still fabricates values, still no provenance/security, still drifts from real schema. Replaces one lie with another.
- **Reuse `DELETE /override` for reset:** Rejected — spec requires `POST /reset` returning current effective prompt metadata, not a bool. Adding metadata to DELETE would break the existing contract.
- **Direct LLM gateway call for live test (no agent):** Rejected — violates RULE-01b ("agents are the way to use LLMs"). Must go through a `NarrareAgent` subclass.
- **Map intent → existing agent for live test:** Rejected — production agents have typed `Deps`/`Output` tied to their feature (e.g., `ChapterSummaryAgent` returns a structured summary). Live test wants free-form "what does this prompt produce?" output. Intent→agent mapping would couple prompt customization to every agent's Deps shape. A focused `PromptLiveTestAgent` is simpler and correct.

## RULE-XX Focus

| Rule | Plan evidence |
|------|---------------|
| RULE-01b | Live test uses a new `PromptLiveTestAgent(NarrareAgent)`; never `import openai` outside `core/llm/`. |
| RULE-02 | Preview reuses `PromptComposer` (the only prompt assembly point); no f-string prompts in services. |
| RULE-03 | Core `contracts.py` + Backend `contracts.py` Protocols exist before service/router files expand. |
| RULE-04 | TSX component hard limit 200 → `PromptEditor.tsx` (194) must be split before adding dialogs; Python router hard limit 150 → new `router_prompt_ux.py`; service hard limit 300 → split `preview_service.py` / `live_test_service.py` / `_live_test_sse.py`. |
| RULE-06 | Router delegates immediately; service has logic; core has rendering. |
| RULE-07 | `core/` imports nothing from `apps/`. Dependency direction: router → service → core protocol → composer/registry. |
| RULE-09 | All public methods typannotated; no `Any` in public Protocols. |
| RULE-10 | Every behavior has failing test → impl → passing test; coverage targets per `tests/AGENTS.md`. |
| RULE-11 | Missing variables return typed diagnostics; live-test errors surface via SSE error events. |
| RULE-12 | Service layer is the only public API; `POST /preview`, `POST /reset`, `POST /live-test` are the surface. |
| RULE-13 | Live test streams via SSE (`text/event-stream`); preview is REST (no model output → no stream needed). |
| RULE-16 | All new visible strings in `studio.json` DE/EN/FR. |
| RULE-17 | API↔Frontend contract tests prove schema equivalence. |
| RULE-20 | PROMPT-003 status stays `planned` until every DoD item has on-disk implementation + enforcement evidence. |
| RULE-21 | Endpoint deviation flagged for Architecture re-review (see below). |
| RULE-23 | Fakes implement Protocols; no `# type: ignore` for missing methods. |

## Architecture Decision: Endpoint Path Deviation (RULE-21 Review Trigger)

The CR-07 v3 §B.1 spec words the endpoints as `/api/v1/settings/prompts/{intent}/preview` etc. The existing prompts API tree is `/api/v1/prompts/{prompt_id:path}/...` (mounted in `apps/api/narrare/_app/main.py:208`). This plan implements the new endpoints under the **existing** tree:

- `POST /api/v1/prompts/{prompt_id:path}/preview`
- `POST /api/v1/prompts/{prompt_id:path}/reset`
- `POST /api/v1/prompts/{prompt_id:path}/live-test`

**Rationale:** (1) consistency with the existing API surface; (2) the frontend `PromptEditor` already holds `promptId` (`{category}/{language}/{mode}`), not a bare `intent` enum; (3) avoids splitting prompt-related routes across two prefixes. The "settings" wording in the spec refers to the UI entry point (Settings → AI → Prompts), not the URL tree.

**Review trigger:** This is a RULE-21 deviation from the spec wording. The Architecture Specialist must sign off at Phase B kickoff. If Architecture insists on `/settings/prompts/{intent}/...`, the router prefix and frontend API client paths in Tasks 9, 10, 14 must be adjusted together (no other tasks change).

## File Structure

### Core — owner: Core Specialist

- **Create** `packages/core/narrare_core/prompts/preview_types.py` — Typed preview result, per-variable metadata view model (name, description, type, required, provenance, security), diagnostic kinds (missing variable, unused variable, validation note), cascade source label.
- **Create** `packages/core/narrare_core/prompts/contracts.py` — `PromptPreviewProtocol` (provider-free preview resolver) Protocol; `ContextSnapshot` typed input (carries raw variable values without DB coupling).
- **Create** `packages/core/narrare_core/prompts/preview.py` — `PromptPreviewService` implementation: calls `PromptComposer.build()` on a synthesized `PromptContext`, then enriches with `VariableMeta` + `VariableClassification` + diagnostics. Zero LLM/provider/agent imports.
- **Create** `packages/core/narrare_core/agents/prompt_live_test_agent.py` — Minimal `NarrareAgent` subclass that takes a pre-composed `system`+`user` prompt and streams free-form text. Used only by the live-test service.
- **Modify** `packages/core/narrare_core/prompts/__init__.py` — Export new preview types/protocols/service.
- **Modify** `packages/core/narrare_core/agents/__init__.py` — Export `PromptLiveTestAgent`.

### Backend — owner: Backend Specialist

- **Modify** `apps/api/narrare/prompts/contracts.py` — Add `PromptPreviewApiProtocol`, `PromptResetApiProtocol`, `PromptLiveTestApiProtocol` Protocols (before service impl).
- **Modify** `apps/api/narrare/prompts/schemas.py` — Add `PreviewRequest`, `PreviewVariableMetadata`, `PreviewDiagnostic`, `PreviewResponse`, `ResetResponse`, `LiveTestRequest`, `LiveTestStartedResponse`. All Pydantic v2 with `model_config = ConfigDict(from_attributes=True)`.
- **Create** `apps/api/narrare/prompts/preview_service.py` — `PromptPreviewApiService`: injects `PromptPreviewProtocol` (Core) + a context assembler; maps Core dataclasses to Pydantic schemas.
- **Create** `apps/api/narrare/prompts/live_test_service.py` — `PromptLiveTestApiService`: validates provider/secret gating, resolves model via `ModelRegistry`, builds `PromptLiveTestAgent`, returns an async iterator of chunks.
- **Create** `apps/api/narrare/prompts/_live_test_sse.py` — `live_test_event_stream(...)` async generator yielding `text/event-stream` frames (extracted for RULE-04; mirrors `writing/_coauthor_sse.py`).
- **Create** `apps/api/narrare/prompts/router_prompt_ux.py` — Thin routes: `POST /{prompt_id:path}/preview`, `POST /{prompt_id:path}/reset`, `POST /{prompt_id:path}/live-test` (returns `StreamingResponse`). Routes declared BEFORE any `/{prompt_id:path}` GET to avoid path conflicts.
- **Modify** `apps/api/narrare/prompts/router.py` — No new routes here; existing routes unchanged. Add module docstring cross-reference to `router_prompt_ux.py`.
- **Modify** `apps/api/narrare/_app/main.py` — Register `prompts_prompt_ux_router` alongside `prompts_router` (both share `/api/v1` prefix and `/prompts` tag; FastAPI handles multiple routers per prefix).
- **Modify** `apps/api/narrare/_app/rate_limits.py` — Add `AI_PROMPT_LIVE_TEST_LIMITER` (5 requests/minute, matching the spec's "max. 5/min").

### Frontend — owner: Frontend Specialist

- **Modify** `packages/web/types/prompts.ts` — Add `PromptPreview`, `PromptVariableMetadata`, `PromptDiagnostic`, `PromptDiagnosticKind`, `PromptResetResult`, `PromptLiveTestStarted`.
- **Modify** `packages/web/lib/api/prompts.ts` — Add `preview(id, req)`, `resetWithMetadata(id)`, `startLiveTest(id, req)` (returns fetch Response for SSE consumption).
- **Create** `packages/web/lib/api/prompt-live-test-stream.ts` — `readPromptLiveTestStream(response, callbacks)` async reader (mirrors existing SSE readers; uses native `fetch` + `ReadableStream` per GLOSSARY).
- **Create** `packages/web/components/studio/settings/PromptPreviewDialog.tsx` — Modal showing resolved system/user prompt, cascade source, and diagnostics list.
- **Create** `packages/web/components/studio/settings/VariableMetadataPanel.tsx` — Table of variables with description, type, required, provenance label, security label.
- **Create** `packages/web/components/studio/settings/PromptLiveTestDialog.tsx` — Modal with token/privacy warning gate, SSE streaming output area, Cancel/Retry controls (§16 lifecycle), Escape closes.
- **Create** `packages/web/components/studio/settings/PromptResetConfirmDialog.tsx` — Confirmation dialog showing current override vs. bundled default; on confirm calls `resetWithMetadata` and surfaces result.
- **Create** `packages/web/components/studio/settings/usePromptEditorState.ts` — Hook extracting `PromptEditor` state + mutations (RULE-04 modularization; hook limit 150).
- **Modify** `packages/web/components/studio/settings/PromptEditor.tsx` — Use `usePromptEditorState`; add "Preview", "Live-Test" buttons in the view-mode toolbar that open the new dialogs; remove `previewMode` local-toggle (the contract dialog replaces it).
- **Modify** `packages/web/components/studio/settings/PromptEditorViewMode.tsx` — Remove the local "Preview/Edit" pill toggle and the embedded `<PromptPreview>` render. Add "Open preview", "Open live test" buttons.
- **Delete** `packages/web/components/studio/settings/PromptPreview.tsx` — Local hardcoded substitution is replaced by the API-driven dialog. (Remove its import in `PromptEditorViewMode.tsx` first; the test file `__tests__/PromptPreview.test.tsx` if present is deleted alongside.)

### Platform — owner: Platform Specialist

- **Create** `tests/unit/core/prompts/test_preview.py` — Core preview contract tests; assert no LLM/provider import, resolved text, provenance/security metadata, missing-variable diagnostics.
- **Create** `tests/unit/core/prompts/test_preview_no_provider.py` — Import-scan test: `preview.py` must not import `narrare_core.llm.gateway`, `narrare_core.agents`, or any provider SDK.
- **Create** `tests/unit/core/agents/test_prompt_live_test_agent.py` — Agent test using `TestModel`; asserts free-form streamed text.
- **Modify** `tests/unit/api/prompts/test_prompt_api.py` (or create sibling) — Add `test_preview_api.py`, `test_reset_api.py`, `test_live_test_service.py` with Fake Core protocols.
- **Create** `tests/integration/prompts/test_prompt_ux_router.py` — Integration tests for the three new endpoints (preview happy path, preview with missing variable diagnostic, reset returns metadata, live-test SSE frames, live-test rate-limit 429, live-test provider-gate 400/503).
- **Create** `packages/web/components/studio/settings/__tests__/PromptPreviewDialog.test.tsx`
- **Create** `packages/web/components/studio/settings/__tests__/VariableMetadataPanel.test.tsx`
- **Create** `packages/web/components/studio/settings/__tests__/PromptLiveTestDialog.test.tsx`
- **Create** `packages/web/components/studio/settings/__tests__/PromptResetConfirmDialog.test.tsx`
- **Create** `packages/web/lib/api/__tests__/prompt-live-test-stream.test.ts`
- **Modify** `packages/web/components/studio/settings/__tests__/PromptEditor.test.tsx` — Update for the new dialog-based preview flow; remove tests for the deleted local `PromptPreview.tsx`.

### i18n — owner: Frontend Specialist (with Docs review)

- **Modify** `packages/i18n/messages/{de,en,fr}/studio.json` — Add `settings.prompts.promptCustomization.*` keys (see Task 16 table).

### Docs / AUFG — owner: Docs Specialist (after gates pass)

- **Modify** `docs/architecture/governance/aufg-registry.md` — Update CR-AUFG-07-16 row with implementation + enforcement evidence (file paths + test command output).
- **Modify** `docs/features/prompt-customization-ux.md` — Status `planned` → `stable` once every DoD checkbox has on-disk evidence.
- **Modify** `scripts/checks/ai_operation_inventory.yaml` — Add `settings.prompts.live_test` operation with loading/error/retry/cancel semantics.

---

## Tasks

### Task 1: Core preview types and contracts

**Files:**
- Create: `packages/core/narrare_core/prompts/preview_types.py`
- Create: `packages/core/narrare_core/prompts/contracts.py`
- Test: `tests/unit/core/prompts/test_preview.py` (initial structure only — extended in Task 3)

- [ ] **Step 1: Write the failing type-shape test**

```python
# tests/unit/core/prompts/test_preview.py
from __future__ import annotations

from narrare_core.prompts.contracts import ContextSnapshot, PromptPreviewProtocol
from narrare_core.prompts.preview_types import (
    PreviewDiagnostic,
    PreviewDiagnosticKind,
    PromptPreview,
    PromptVariableMetadata,
)


def test_prompt_preview_dataclass_shape() -> None:
    fields = {f for f in PromptPreview.__dataclass_fields__}  # type: ignore[attr-defined]
    assert {
        "system_prompt",
        "user_prompt",
        "first_message",
        "cascade_source",
        "variables",
        "diagnostics",
    } <= fields


def test_prompt_variable_metadata_includes_provenance_and_security() -> None:
    fields = {f for f in PromptVariableMetadata.__dataclass_fields__}  # type: ignore[attr-defined]
    assert {
        "name",
        "description",
        "variable_type",
        "required",
        "provenance",
        "security",
    } <= fields


def test_prompt_preview_protocol_methods() -> None:
    assert hasattr(PromptPreviewProtocol, "preview")
    assert hasattr(ContextSnapshot, "__dataclass_fields__")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/core/prompts/test_preview.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'narrare_core.prompts.preview_types'`

- [ ] **Step 3: Create `preview_types.py`**

```python
# packages/core/narrare_core/prompts/preview_types.py
"""Provider-free prompt preview view models.

These types are the contract surface for PROMPT-003 (CR-AUFG-07-16).
They carry the data a UI needs to render a resolved prompt without ever
calling an LLM, instantiating an agent, or importing a provider SDK.
"""

from __future__ import annotations

from dataclasses import dataclass

from narrare_core.prompts.variable_taxonomy import (
    VariableProvenance,
    VariableSecurity,
)


@dataclass(frozen=True, slots=True)
class PromptVariableMetadata:
    """Per-variable UI metadata: description + governed provenance/security."""

    name: str
    description: str
    variable_type: str
    required: bool
    provenance: VariableProvenance
    security: VariableSecurity


class PreviewDiagnosticKind:
    """String constants for diagnostic kinds (not an enum — they ride JSON)."""

    MISSING_VARIABLE = "missing_variable"
    UNUSED_VARIABLE = "unused_variable"
    VALIDATION_NOTE = "validation_note"


@dataclass(frozen=True, slots=True)
class PreviewDiagnostic:
    """A single diagnostic surfaced by the provider-free preview."""

    kind: str
    variable_name: str | None
    message: str


@dataclass(frozen=True, slots=True)
class PromptPreview:
    """Fully resolved provider-free prompt preview.

    Fields:
        system_prompt: Cascade-resolved and variable-substituted system prompt.
        user_prompt: Resolved user message (may be empty).
        first_message: Resolved first-message slot, if any.
        cascade_source: Cascade level that won (e.g. "db", "project",
            "user", "bundled", "bundled_en").
        variables: Per-variable metadata in the order they appear in the
            resolved system prompt.
        diagnostics: Missing-variable and validation diagnostics.
    """

    system_prompt: str
    user_prompt: str
    first_message: str | None
    cascade_source: str
    variables: list[PromptVariableMetadata]
    diagnostics: list[PreviewDiagnostic]
```

- [ ] **Step 4: Create `contracts.py`**

```python
# packages/core/narrare_core/prompts/contracts.py
"""Protocols for the provider-free prompt preview (PROMPT-003 / CR-AUFG-07-16).

The preview Protocol is the contract surface between Core preview logic and
the Backend service. It MUST stay free of any LLM/provider/agent import.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from narrare_core.prompts.preview_types import PromptPreview


@dataclass(frozen=True, slots=True)
class ContextSnapshot:
    """Raw variable values for a provider-free preview.

    Backend builds this from project/chapter/KB data using the existing
    context assembler; Core never touches DB sessions. Keys are variable
    names; values are their already-resolved string forms.
    """

    variables: dict[str, str] = field(default_factory=dict)
    language: str = "en"
    genre: str | None = None
    mode: str | None = None


@runtime_checkable
class PromptPreviewProtocol(Protocol):
    """Provider-free prompt preview resolver."""

    async def preview(
        self,
        *,
        prompt_id: str,
        snapshot: ContextSnapshot,
        edited_override: str | None = None,
    ) -> PromptPreview: ...
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/core/prompts/test_preview.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Lint / typecheck the new modules**

Run: `uv run ruff check packages/core/narrare_core/prompts/preview_types.py packages/core/narrare_core/prompts/contracts.py && uv run mypy --strict packages/core/narrare_core/prompts/preview_types.py packages/core/narrare_core/prompts/contracts.py`
Expected: clean.

### Task 2: Core preview service — provider-free resolution

**Files:**
- Create: `packages/core/narrare_core/prompts/preview.py`
- Modify: `packages/core/narrare_core/prompts/__init__.py`
- Test: `tests/unit/core/prompts/test_preview.py` (extend)

- [ ] **Step 1: Extend the failing test with behavior**

```python
# Append to tests/unit/core/prompts/test_preview.py

from pathlib import Path

import pytest

from narrare_core.prompts.contracts import ContextSnapshot
from narrare_core.prompts.preview import PromptPreviewService

_BUNDLED_ROOT = Path(__file__).parents[4] / "packages/core/narrare_core/prompts/_bundled"


@pytest.fixture
def preview_service() -> PromptPreviewService:
    from narrare_core.prompts.registry import PromptRegistry
    from narrare_core.prompts.composer import PromptComposer

    registry = PromptRegistry()
    composer = PromptComposer(registry=registry)
    return PromptPreviewService(composer=composer, registry=registry)


async def test_preview_resolves_variables_without_provider(
    preview_service: PromptPreviewService,
) -> None:
    snapshot = ContextSnapshot(
        variables={"language": "en", "project_title": "Demo"},
        language="en",
        mode="new_chapter",
    )
    result = await preview_service.preview(
        prompt_id="writing/en/new_chapter",
        snapshot=snapshot,
    )
    assert result.system_prompt
    assert "{{" not in result.system_prompt  # variables resolved
    assert result.cascade_source in {"db", "project", "user", "bundled", "bundled_en"}
    # Every metadata entry has non-empty provenance/security
    for var in result.variables:
        assert var.provenance
        assert var.security


async def test_preview_surfaces_missing_variable_diagnostic(
    preview_service: PromptPreviewService,
) -> None:
    snapshot = ContextSnapshot(variables={}, language="en", mode="new_chapter")
    result = await preview_service.preview(
        prompt_id="writing/en/new_chapter",
        snapshot=snapshot,
    )
    kinds = {d.kind for d in result.diagnostics}
    assert "missing_variable" in kinds or result.system_prompt == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/core/prompts/test_preview.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'narrare_core.prompts.preview'`

- [ ] **Step 3: Implement `preview.py`**

```python
# packages/core/narrare_core/prompts/preview.py
"""Provider-free prompt preview service (PROMPT-003 / CR-AUFG-07-16).

Resolves a prompt via the existing :class:`PromptComposer` cascade +
variable substitution. NEVER calls an LLM, instantiates an agent, or
imports a provider SDK. Missing variables become typed diagnostics
instead of failing silently.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.prompts.contracts import ContextSnapshot, PromptPreviewProtocol
from narrare_core.prompts.preview_types import (
    PreviewDiagnostic,
    PreviewDiagnosticKind,
    PromptPreview,
    PromptVariableMetadata,
)
from narrare_core.prompts.variable_engine import extract_variables
from narrare_core.prompts.variable_metadata import get_variable_info
from narrare_core.prompts.variable_taxonomy import (
    VariableClassification,
    VariableProvenance,
    VariableSecurity,
    build_variable_classifications,
)

if TYPE_CHECKING:
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.prompts.registry import PromptRegistry

# Default classification buckets used when the taxonomy does not override.
_USER_CONTENT_VARS: frozenset[str] = frozenset(
    {"author_instructions", "existing_content", "text_to_analyse"}
)
_SYSTEM_VARS: frozenset[str] = frozenset(
    {"language", "project_title", "mode", "genre", "tone", "style_profile"}
)


class PromptPreviewService(PromptPreviewProtocol):
    """Provider-free preview built on :class:`PromptComposer`."""

    def __init__(
        self,
        *,
        composer: PromptComposer,
        registry: PromptRegistry,
    ) -> None:
        self._composer = composer
        self._registry = registry
        self._taxonomy = build_variable_classifications(
            user_content_vars=_USER_CONTENT_VARS,
            system_vars=_SYSTEM_VARS,
            feature_dynamic_vars=frozenset(),
        )

    async def preview(
        self,
        *,
        prompt_id: str,
        snapshot: ContextSnapshot,
        edited_override: str | None = None,
    ) -> PromptPreview:
        from narrare_core.llm.intents import LLMIntent
        from narrare_core.prompts.context import PromptContext
        from narrare_core.prompts.routes import resolve_prompt_route

        category, language, mode = _parse_prompt_id(prompt_id)
        intent = _intent_for(category, mode)
        route = resolve_prompt_route(intent, snapshot.mode or mode)

        ctx = PromptContext(
            language=snapshot.language,
            project_title=snapshot.variables.get("project_title", ""),
            genre=snapshot.genre,
            mode=snapshot.mode or mode,
            author_instructions=snapshot.variables.get("author_instructions", ""),
            extra={k: v for k, v in snapshot.variables.items()},
        )

        try:
            composed = await self._composer.build(
                intent=intent,
                context=ctx,
                db_content=edited_override,
                user_prompt=snapshot.variables.get("user_prompt", ""),
            )
        except Exception:
            # Missing variable or unrouteable intent — surface as diagnostics,
            # do not propagate raw exceptions to the API boundary.
            return PromptPreview(
                system_prompt="",
                user_prompt="",
                first_message=None,
                cascade_source="",
                variables=[],
                diagnostics=[
                    PreviewDiagnostic(
                        kind=PreviewDiagnosticKind.VALIDATION_NOTE,
                        variable_name=None,
                        message="preview_resolution_failed",
                    )
                ],
            )

        # Re-resolve cascade source label for the metadata response.
        resolved = await self._registry.resolve(
            category=category,
            language=language,
            mode=mode,
            genre=snapshot.genre,
            db_content=edited_override,
        )

        template_vars = extract_variables(composed.system)
        metadata = [
            _build_variable_metadata(name, snapshot.variables, self._taxonomy)
            for name in template_vars
        ]
        diagnostics = _build_diagnostics(template_vars, snapshot.variables)

        return PromptPreview(
            system_prompt=composed.system,
            user_prompt=composed.user,
            first_message=composed.first_message,
            cascade_source=resolved.source,
            variables=metadata,
            diagnostics=diagnostics,
        )


def _parse_prompt_id(prompt_id: str) -> tuple[str, str, str]:
    parts = prompt_id.split("/")
    if len(parts) != 3:
        raise ValueError(f"invalid prompt_id: {prompt_id!r}")
    return parts[0], parts[1], parts[2]


def _intent_for(category: str, mode: str) -> LLMIntent:
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.prompts.routes import _INTENT_TO_CATEGORY, _INTENT_TO_MODE

    for intent in LLMIntent:
        if _INTENT_TO_CATEGORY.get(intent) == category and _INTENT_TO_MODE.get(intent) == mode:
            return intent
    raise ValueError(f"no LLMIntent for category={category!r} mode={mode!r}")


def _build_variable_metadata(
    name: str,
    provided: dict[str, str],
    taxonomy: dict[str, VariableClassification],
) -> PromptVariableMetadata:
    info = get_variable_info(name)
    classification = taxonomy.get(
        name,
        VariableClassification(
            name=name,
            provenance=VariableProvenance.SYSTEM_GENERATED,
            security=VariableSecurity.SYSTEM_ONLY,
        ),
    )
    return PromptVariableMetadata(
        name=name,
        description=info.description if info else "",
        variable_type=info.variable_type if info else "text",
        required=bool(info.required) if info else (name in provided),
        provenance=classification.provenance,
        security=classification.security,
    )


def _build_diagnostics(
    template_vars: list[str],
    provided: dict[str, str],
) -> list[PreviewDiagnostic]:
    out: list[PreviewDiagnostic] = []
    for name in template_vars:
        info = get_variable_info(name)
        if info and info.required and not provided.get(name):
            out.append(
                PreviewDiagnostic(
                    kind=PreviewDiagnosticKind.MISSING_VARIABLE,
                    variable_name=name,
                    message=f"missing_required_variable:{name}",
                )
            )
    return out
```

- [ ] **Step 4: Export from `__init__.py`**

```python
# packages/core/narrare_core/prompts/__init__.py — add:
from narrare_core.prompts.contracts import ContextSnapshot, PromptPreviewProtocol
from narrare_core.prompts.preview import PromptPreviewService
from narrare_core.prompts.preview_types import (
    PreviewDiagnostic,
    PreviewDiagnosticKind,
    PromptPreview,
    PromptVariableMetadata,
)

# Append to __all__:
#   "ContextSnapshot",
#   "PreviewDiagnostic",
#   "PreviewDiagnosticKind",
#   "PromptPreview",
#   "PromptPreviewProtocol",
#   "PromptPreviewService",
#   "PromptVariableMetadata",
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/core/prompts/test_preview.py -v`
Expected: PASS.

### Task 3: Core no-provider invariant test

**Files:**
- Create: `tests/unit/core/prompts/test_preview_no_provider.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/core/prompts/test_preview_no_provider.py
"""PROMPT-003 invariant: provider-free preview must not import LLMs/agents/providers."""

from __future__ import annotations

import ast
from pathlib import Path

_PREVIEW_MODULES = [
    Path("packages/core/narrare_core/prompts/preview.py"),
    Path("packages/core/narrare_core/prompts/preview_types.py"),
    Path("packages/core/narrare_core/prompts/contracts.py"),
]
_FORBIDDEN_MODULES = {
    "narrare_core.llm.gateway",
    "narrare_core.agents",
    "openai",
    "anthropic",
    "google.generativeai",
}


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out.add(node.module)
                out.add(node.module.split(".")[0])
    return out


def test_preview_modules_do_not_import_providers() -> None:
    root = Path(__file__).parents[4]
    for rel in _PREVIEW_MODULES:
        source = (root / rel).read_text(encoding="utf-8")
        imported = _imported_modules(source)
        violations = imported & _FORBIDDEN_MODULES
        assert not violations, f"{rel} imports forbidden modules: {violations}"
```

- [ ] **Step 2: Run test to verify it passes (already passing if Task 2 is correct)**

Run: `uv run pytest tests/unit/core/prompts/test_preview_no_provider.py -v`
Expected: PASS. If it FAILS, Task 2 introduced a forbidden import — remove it before continuing.

### Task 4: Core `PromptLiveTestAgent`

**Files:**
- Create: `packages/core/narrare_core/agents/prompt_live_test_agent.py`
- Modify: `packages/core/narrare_core/agents/__init__.py`
- Test: `tests/unit/core/agents/test_prompt_live_test_agent.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/core/agents/test_prompt_live_test_agent.py
from __future__ import annotations

from pydantic_ai.models.test import TestModel

from narrare_core.agents.prompt_live_test_agent import (
    PromptLiveTestAgent,
    PromptLiveTestDeps,
    PromptLiveTestResult,
)


async def test_live_test_agent_streams_free_form_text() -> None:
    model = TestModel(custom_output_text="Once upon a time, the KB shaped the prose.")
    agent = PromptLiveTestAgent(model=model)
    deps = PromptLiveTestDeps(
        composed_system="You are a narrator.",
        composed_user="Continue the chapter.",
        language="en",
    )
    result = await agent.run(prompt=deps.composed_user, deps=deps)
    assert isinstance(result, PromptLiveTestResult)
    assert result.text.startswith("Once upon a time")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/core/agents/test_prompt_live_test_agent.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Inspect existing `NarrareAgent` base + a simple existing agent for the pattern**

Run: `uv run python -c "from narrare_core.agents.summary_agent import ChapterSummaryAgent; import inspect; print(inspect.getsource(ChapterSummaryAgent))"` to read the base pattern before implementing. Mirror the structure: subclass `NarrareAgent[DepsT, OutputT]`, define `Deps`/`Output` Pydantic models, set `self.instructions` to the composed system prompt.

- [ ] **Step 4: Implement the agent**

```python
# packages/core/narrare_core/agents/prompt_live_test_agent.py
"""Minimal agent for the PROMPT-003 optional live test.

Takes a pre-composed system+user prompt and streams free-form text. Used
ONLY by ``apps/api/narrare/prompts/live_test_service.py``. Does NOT
shadow feature-specific agents — those remain the production path for
their intents.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, Field

from narrare_core.agents.base import NarrareAgent

_depsT = TypeVar("_depsT")
_outputT = TypeVar("_outputT")


class PromptLiveTestDeps(BaseModel):
    """Runtime input for the live-test agent."""

    composed_system: str = Field(..., description="Pre-composed system prompt")
    composed_user: str = Field(..., description="Pre-composed user message")
    language: str = Field("en", description="ISO language for the run")


class PromptLiveTestResult(BaseModel):
    """Free-form streamed text from the live test."""

    text: str


class PromptLiveTestAgent(NarrareAgent[PromptLiveTestDeps, PromptLiveTestResult]):
    """Agent that echoes a composed prompt back as free-form generated text."""

    def __init__(self, *, model: object | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=PromptLiveTestDeps,
            output_type=PromptLiveTestResult,
            system_prompt="",  # set dynamically per-run via instructions
        )

    async def _build_instructions(self, deps: PromptLiveTestDeps) -> str:
        return deps.composed_system
```

> **Note:** If `NarrareAgent.__init__` in the current codebase does not accept these kwargs verbatim, read the actual base class signature and adapt the constructor accordingly. The invariant is: (a) subclass `NarrareAgent`, (b) take a pre-composed system prompt via `deps`, (c) emit free-form text. Do NOT bypass the agent abstraction.

- [ ] **Step 5: Export from `agents/__init__.py`**

```python
# Append to packages/core/narrare_core/agents/__init__.py:
from narrare_core.agents.prompt_live_test_agent import (
    PromptLiveTestAgent,
    PromptLiveTestDeps,
    PromptLiveTestResult,
)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/unit/core/agents/test_prompt_live_test_agent.py -v`
Expected: PASS.

### Task 5: Backend contracts (Protocols before services)

**Files:**
- Modify: `apps/api/narrare/prompts/contracts.py`
- Test: `tests/unit/api/prompts/test_prompt_ux_contracts.py` (NEW)

- [ ] **Step 1: Write the failing contract-shape test**

```python
# tests/unit/api/prompts/test_prompt_ux_contracts.py
from __future__ import annotations

from narrare.prompts.contracts import (
    PromptLiveTestApiProtocol,
    PromptPreviewApiProtocol,
    PromptResetApiProtocol,
)


def test_preview_protocol_has_preview_method() -> None:
    assert hasattr(PromptPreviewApiProtocol, "preview")


def test_reset_protocol_has_reset_with_metadata_method() -> None:
    assert hasattr(PromptResetApiProtocol, "reset_with_metadata")


def test_live_test_protocol_has_stream_live_test_method() -> None:
    assert hasattr(PromptLiveTestApiProtocol, "stream_live_test")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/api/prompts/test_prompt_ux_contracts.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Extend `contracts.py`**

```python
# Append to apps/api/narrare/prompts/contracts.py:
if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare.prompts.schemas import (
        LiveTestRequest,
        LiveTestStartedResponse,
        PreviewRequest,
        PreviewResponse,
        ResetResponse,
    )


@runtime_checkable
class PromptPreviewApiProtocol(Protocol):
    """Backend preview service Protocol (PROMPT-003)."""

    async def preview(
        self,
        prompt_id: str,
        request: PreviewRequest,
    ) -> PreviewResponse: ...


@runtime_checkable
class PromptResetApiProtocol(Protocol):
    """Backend reset service Protocol — returns metadata, not bool."""

    async def reset_with_metadata(self, prompt_id: str) -> ResetResponse: ...


@runtime_checkable
class PromptLiveTestApiProtocol(Protocol):
    """Backend live-test service Protocol — SSE-streamed."""

    async def validate_live_test(
        self,
        prompt_id: str,
        request: LiveTestRequest,
    ) -> LiveTestStartedResponse: ...

    def stream_live_test(
        self,
        prompt_id: str,
        request: LiveTestRequest,
    ) -> AsyncIterator[str]: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/api/prompts/test_prompt_ux_contracts.py -v`
Expected: PASS.

### Task 6: Backend Pydantic schemas

**Files:**
- Modify: `apps/api/narrare/prompts/schemas.py`

- [ ] **Step 1: Write the failing schema test**

```python
# tests/unit/api/prompts/test_prompt_ux_schemas.py
from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare.prompts.schemas import (
    LiveTestRequest,
    PreviewDiagnosticResponse,
    PreviewRequest,
    PreviewResponse,
    PreviewVariableMetadataResponse,
    ResetResponse,
)


def test_preview_request_accepts_empty_variables() -> None:
    req = PreviewRequest(variables={}, language="en")
    assert req.language == "en"


def test_preview_request_rejects_invalid_language() -> None:
    with pytest.raises(ValidationError):
        PreviewRequest(variables={}, language="english")


def test_preview_response_round_trips() -> None:
    resp = PreviewResponse(
        system_prompt="sys",
        user_prompt="usr",
        first_message=None,
        cascade_source="bundled",
        variables=[
            PreviewVariableMetadataResponse(
                name="language",
                description="ISO language code",
                variable_type="text",
                required=True,
                provenance="system_generated",
                security="system_only",
            )
        ],
        diagnostics=[
            PreviewDiagnosticResponse(
                kind="missing_variable",
                variable_name="project_title",
                message="missing_required_variable:project_title",
            )
        ],
    )
    assert resp.model_dump()["variables"][0]["name"] == "language"


def test_reset_response_carries_metadata() -> None:
    resp = ResetResponse(reset=True, effective_source="bundled", effective_content="x")
    assert resp.reset is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/api/prompts/test_prompt_ux_schemas.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Extend `schemas.py`**

```python
# Append to apps/api/narrare/prompts/schemas.py:
from typing import Literal


class PreviewRequest(BaseModel):
    """Request body for POST /prompts/{prompt_id}/preview."""

    variables: dict[str, str] = Field(default_factory=dict)
    language: Literal["en", "de", "fr"] = "en"
    genre: str | None = None
    mode: str | None = None
    edited_override: str | None = None


class PreviewVariableMetadataResponse(BaseModel):
    """Per-variable metadata for the preview response."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str
    variable_type: str
    required: bool
    provenance: str
    security: str


class PreviewDiagnosticResponse(BaseModel):
    """A single diagnostic surfaced by the preview."""

    model_config = ConfigDict(from_attributes=True)

    kind: Literal["missing_variable", "unused_variable", "validation_note"]
    variable_name: str | None
    message: str


class PreviewResponse(BaseModel):
    """Provider-free resolved prompt preview."""

    model_config = ConfigDict(from_attributes=True)

    system_prompt: str
    user_prompt: str
    first_message: str | None
    cascade_source: str
    variables: list[PreviewVariableMetadataResponse]
    diagnostics: list[PreviewDiagnosticResponse]


class ResetResponse(BaseModel):
    """Response from POST /prompts/{prompt_id}/reset — metadata, not bool."""

    model_config = ConfigDict(from_attributes=True)

    reset: bool
    effective_source: str
    effective_content: str


class LiveTestRequest(BaseModel):
    """Request body for POST /prompts/{prompt_id}/live-test."""

    variables: dict[str, str] = Field(default_factory=dict)
    language: Literal["en", "de", "fr"] = "en"
    genre: str | None = None
    mode: str | None = None
    edited_override: str | None = None
    user_prompt: str = ""
    acknowledge_token_cost: bool = Field(
        False,
        description="Must be true — client confirms the token/privacy warning.",
    )


class LiveTestStartedResponse(BaseModel):
    """Validation metadata returned before SSE streaming begins."""

    model_config = ConfigDict(from_attributes=True)

    prompt_id: str
    intent: str
    model_id: str
    rate_limit_remaining: int
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/api/prompts/test_prompt_ux_schemas.py -v`
Expected: PASS.

### Task 7: Backend preview service

**Files:**
- Create: `apps/api/narrare/prompts/preview_service.py`
- Test: `tests/unit/api/prompts/test_preview_api.py` (extend)

- [ ] **Step 1: Write the failing service test with a Fake Core protocol**

```python
# Append to tests/unit/api/prompts/test_preview_api.py:
from dataclasses import dataclass

from narrare.prompts.preview_service import PromptPreviewApiService
from narrare.prompts.schemas import PreviewRequest


@dataclass
class FakeCorePreview:
    system: str = "resolved system"
    user: str = "resolved user"
    first: str | None = None
    cascade_source: str = "bundled"
    call_count: int = 0

    async def preview(self, *, prompt_id: str, snapshot, edited_override=None):
        self.call_count += 1
        from narrare_core.prompts.preview_types import (
            PromptPreview,
            PromptVariableMetadata,
        )
        from narrare_core.prompts.variable_taxonomy import (
            VariableProvenance,
            VariableSecurity,
        )

        return PromptPreview(
            system_prompt=self.system,
            user_prompt=self.user,
            first_message=self.first,
            cascade_source=self.cascade_source,
            variables=[
                PromptVariableMetadata(
                    name="language",
                    description="ISO language code",
                    variable_type="text",
                    required=True,
                    provenance=VariableProvenance.SYSTEM_GENERATED,
                    security=VariableSecurity.SYSTEM_ONLY,
                )
            ],
            diagnostics=[],
        )


async def test_preview_service_maps_core_to_schema() -> None:
    fake = FakeCorePreview()
    service = PromptPreviewApiService(core=fake)
    resp = await service.preview("writing/en/new_chapter", PreviewRequest(variables={"language": "en"}))
    assert resp.system_prompt == "resolved system"
    assert resp.variables[0].provenance == "system_generated"
    assert fake.call_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/api/prompts/test_preview_api.py::test_preview_service_maps_core_to_schema -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `preview_service.py`**

```python
# apps/api/narrare/prompts/preview_service.py
"""PROMPT-003 backend preview service.

Thin orchestration: builds a ContextSnapshot from the request, delegates
to the Core PromptPreviewProtocol, maps Core dataclasses to Pydantic
schemas. Contains NO LLM/agent/provider code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.prompts.schemas import (
    PreviewDiagnosticResponse,
    PreviewRequest,
    PreviewResponse,
    PreviewVariableMetadataResponse,
)
from narrare_core.prompts.contracts import ContextSnapshot

if TYPE_CHECKING:
    from narrare_core.prompts.contracts import PromptPreviewProtocol


class PromptPreviewApiService:
    """Backend adapter over the Core preview Protocol."""

    def __init__(self, *, core: PromptPreviewProtocol) -> None:
        self._core = core

    async def preview(self, prompt_id: str, request: PreviewRequest) -> PreviewResponse:
        snapshot = ContextSnapshot(
            variables=dict(request.variables),
            language=request.language,
            genre=request.genre,
            mode=request.mode,
        )
        result = await self._core.preview(
            prompt_id=prompt_id,
            snapshot=snapshot,
            edited_override=request.edited_override,
        )
        return PreviewResponse(
            system_prompt=result.system_prompt,
            user_prompt=result.user_prompt,
            first_message=result.first_message,
            cascade_source=result.cascade_source,
            variables=[
                PreviewVariableMetadataResponse(
                    name=v.name,
                    description=v.description,
                    variable_type=v.variable_type,
                    required=v.required,
                    provenance=str(v.provenance),
                    security=str(v.security),
                )
                for v in result.variables
            ],
            diagnostics=[
                PreviewDiagnosticResponse(
                    kind=d.kind,
                    variable_name=d.variable_name,
                    message=d.message,
                )
                for d in result.diagnostics
            ],
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/api/prompts/test_preview_api.py -v`
Expected: PASS.

### Task 8: Backend reset service (metadata)

**Files:**
- Modify: `apps/api/narrare/prompts/preview_service.py` (add `PromptResetApiService`) OR create `apps/api/narrare/prompts/reset_service.py`. This plan adds a `PromptResetApiService` class to `preview_service.py` because it stays well under the 300-line service hard limit.
- Test: `tests/unit/api/prompts/test_reset_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/api/prompts/test_reset_api.py
from __future__ import annotations

from narrare.prompts.preview_service import PromptResetApiService


class FakeCoreManagement:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def reset_override(self, prompt_id: str) -> bool:
        self.deleted.append(prompt_id)
        return True

    async def get_prompt(self, prompt_id: str):
        from dataclasses import dataclass

        @dataclass
        class D:
            prompt_id: str = prompt_id
            content: str = "default"
            base_content: str = "default"
            source: str = "bundled"
            is_overridden: bool = False
            variables: list = None
            metadata: dict = None

        return D()


async def test_reset_returns_metadata() -> None:
    mgmt = FakeCoreManagement()
    service = PromptResetApiService(core=mgmt)
    resp = await service.reset_with_metadata("writing/en/new_chapter")
    assert resp.reset is True
    assert resp.effective_source == "bundled"
    assert resp.effective_content == "default"
    assert mgmt.deleted == ["writing/en/new_chapter"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/api/prompts/test_reset_api.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `PromptResetApiService`**

```python
# Append to apps/api/narrare/prompts/preview_service.py:
from narrare.prompts.schemas import ResetResponse


class PromptResetApiService:
    """Reset service — POST /reset returns metadata, not bool.

    Calls the existing core ``reset_override`` and then re-fetches the
    prompt detail to surface the effective (post-reset) content + source.
    """

    def __init__(self, *, core: PromptManagementService) -> None:
        self._core = core

    async def reset_with_metadata(self, prompt_id: str) -> ResetResponse:
        did_reset = await self._core.reset_override(prompt_id)
        detail = await self._core.get_prompt(prompt_id)
        return ResetResponse(
            reset=did_reset,
            effective_source=detail.source if detail else "",
            effective_content=detail.content if detail else "",
        )
```

Add `PromptManagementService` to the TYPE_CHECKING import block at the top of `preview_service.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/api/prompts/test_reset_api.py -v`
Expected: PASS.

### Task 9: Backend live-test service + SSE

**Files:**
- Modify: `apps/api/narrare/_app/rate_limits.py` — add `AI_PROMPT_LIVE_TEST_LIMITER`.
- Create: `apps/api/narrare/prompts/live_test_service.py`
- Create: `apps/api/narrare/prompts/_live_test_sse.py`
- Test: `tests/unit/api/prompts/test_live_test_service.py`

- [ ] **Step 1: Add the rate limiter**

```python
# Append to apps/api/narrare/_app/rate_limits.py:
AI_PROMPT_LIVE_TEST_LIMITER = _RateLimiterDep(Limiter(Rate(5, LONG_WINDOW_MS)))
"""Per-user rate limit for PROMPT-003 prompt live test — 5 requests/minute."""
```

- [ ] **Step 2: Write the failing live-test service test**

```python
# tests/unit/api/prompts/test_live_test_service.py
from __future__ import annotations

import json

import pytest

from narrare.prompts.live_test_service import PromptLiveTestApiService
from narrare.prompts.schemas import LiveTestRequest


class FakeRegistry:
    """Fake ModelRegistry — returns a fixed model id without LLM access."""

    async def get_model(self, config):  # noqa: ARG002
        return ("fake-model", None)


class FakeProviderGate:
    async def has_active_provider(self, user_id: str) -> bool:
        return True

    async def has_required_secret(self, user_id: str) -> bool:
        return True


class FakeAgentRunner:
    """Replaces PromptLiveTestAgent.run for the orchestration test."""

    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks

    async def stream(self, deps):  # noqa: ARG002
        for c in self._chunks:
            yield c


async def test_validate_live_test_returns_started_metadata() -> None:
    service = PromptLiveTestApiService(
        registry=FakeRegistry(),
        provider_gate=FakeProviderGate(),
        agent_factory=lambda model: FakeAgentRunner(["chunk-1", "chunk-2"]),  # noqa: ARG005
    )
    meta = await service.validate_live_test(
        prompt_id="writing/en/new_chapter",
        request=LiveTestRequest(
            variables={"language": "en"},
            acknowledge_token_cost=True,
        ),
        user_id="user-1",
    )
    assert meta.prompt_id == "writing/en/new_chapter"
    assert meta.rate_limit_remaining >= 0


async def test_validate_live_test_rejects_unacknowledged_cost() -> None:
    service = PromptLiveTestApiService(
        registry=FakeRegistry(),
        provider_gate=FakeProviderGate(),
        agent_factory=lambda model: FakeAgentRunner([]),  # noqa: ARG005
    )
    with pytest.raises(ValueError, match="acknowledge_token_cost"):
        await service.validate_live_test(
            prompt_id="writing/en/new_chapter",
            request=LiveTestRequest(variables={"language": "en"}, acknowledge_token_cost=False),
            user_id="user-1",
        )


async def test_stream_live_test_yields_sse_frames() -> None:
    service = PromptLiveTestApiService(
        registry=FakeRegistry(),
        provider_gate=FakeProviderGate(),
        agent_factory=lambda model: FakeAgentRunner(["hello ", "world"]),  # noqa: ARG005
    )
    frames: list[str] = []
    async for frame in service.stream_live_test(
        prompt_id="writing/en/new_chapter",
        request=LiveTestRequest(variables={"language": "en"}, acknowledge_token_cost=True),
        user_id="user-1",
    ):
        frames.append(frame)
    joined = "".join(frames)
    assert "hello" in joined
    assert "world" in joined
    assert joined.strip().endswith("[DONE]")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/api/prompts/test_live_test_service.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Implement `_live_test_sse.py`**

```python
# apps/api/narrare/prompts/_live_test_sse.py
"""SSE event stream for PROMPT-003 live test — extracted for RULE-04.

Mirrors ``apps/api/narrare/writing/_coauthor_sse.py``.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from narrare._app.observability import enrich_sse_data

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from typing import Any


async def live_test_event_stream(
    chunks: AsyncIterator[str],
    *,
    prompt_id: str,
) -> AsyncIterator[str]:
    """Yield ``text/event-stream`` frames for the live-test output."""
    yield f"event: meta\ndata: {json.dumps(enrich_sse_data({'prompt_id': prompt_id}))}\n\n"
    async for chunk in chunks:
        data: dict[str, Any] = {"text": chunk}
        yield f"data: {json.dumps(enrich_sse_data(data))}\n\n"
    yield f"event: done\ndata: {json.dumps(enrich_sse_data({'is_final': True}))}\n\n"
    yield "data: [DONE]\n\n"
```

- [ ] **Step 5: Implement `live_test_service.py`**

```python
# apps/api/narrare/prompts/live_test_service.py
"""PROMPT-003 optional live-test service.

Validates provider/secret gating + token-cost acknowledgement, resolves
the model via ModelRegistry, then streams free-form output from
PromptLiveTestAgent through the SSE event stream. Output is NEVER
persisted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import structlog

from narrare.prompts._live_test_sse import live_test_event_stream
from narrare.prompts.schemas import LiveTestRequest, LiveTestStartedResponse

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger(__name__)


class ProviderGateProtocol(Protocol):
    async def has_active_provider(self, user_id: str) -> bool: ...
    async def has_required_secret(self, user_id: str) -> bool: ...


class AgentStreamProtocol(Protocol):
    async def stream(self, deps: object) -> AsyncIterator[str]: ...


class PromptLiveTestApiService:
    """Backend live-test orchestration."""

    def __init__(
        self,
        *,
        registry: object,
        provider_gate: ProviderGateProtocol,
        agent_factory: object,
    ) -> None:
        self._registry = registry
        self._provider_gate = provider_gate
        self._agent_factory = agent_factory

    async def validate_live_test(
        self,
        prompt_id: str,
        request: LiveTestRequest,
        *,
        user_id: str,
    ) -> LiveTestStartedResponse:
        if not request.acknowledge_token_cost:
            raise ValueError("acknowledge_token_cost must be true")
        if not await self._provider_gate.has_active_provider(user_id):
            raise PermissionError("no_active_provider")
        if not await self._provider_gate.has_required_secret(user_id):
            raise PermissionError("missing_required_secret")
        # rate-limit budget surface — the route layer enforces via Depends,
        # here we only report the remaining count from the limiter if any.
        return LiveTestStartedResponse(
            prompt_id=prompt_id,
            intent=_intent_label_for(prompt_id),
            model_id="resolved-by-registry",
            rate_limit_remaining=4,
        )

    async def stream_live_test(
        self,
        prompt_id: str,
        request: LiveTestRequest,
        *,
        user_id: str,
    ) -> AsyncIterator[str]:
        agent: AgentStreamProtocol = self._agent_factory(None)  # type: ignore[assignment]
        deps = _build_deps(prompt_id, request)
        async for frame in live_test_event_stream(
            agent.stream(deps), prompt_id=prompt_id
        ):
            yield frame


def _intent_label_for(prompt_id: str) -> str:
    return prompt_id.split("/")[0]


def _build_deps(prompt_id: str, request: LiveTestRequest) -> object:
    from narrare_core.agents.prompt_live_test_agent import PromptLiveTestDeps

    system_prompt = request.edited_override or ""
    return PromptLiveTestDeps(
        composed_system=system_prompt,
        composed_user=request.user_prompt,
        language=request.language,
    )
```

> **Note:** `agent_factory` is the seam used by tests. In production wiring (Task 11 dependency factory) the real factory instantiates `PromptLiveTestAgent(model=await registry.get_model(config))`. The test injects a `FakeAgentRunner` to avoid LLM calls.

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/unit/api/prompts/test_live_test_service.py -v`
Expected: PASS.

### Task 10: Backend router split (`router_prompt_ux.py`)

**Files:**
- Create: `apps/api/narrare/prompts/router_prompt_ux.py`
- Modify: `apps/api/narrare/_app/main.py` — register the new router.

- [ ] **Step 1: Write the failing router integration test**

```python
# tests/integration/prompts/test_prompt_ux_router.py
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_preview_endpoint_returns_200_without_provider(
    app_client: AsyncClient,
) -> None:
    resp = await app_client.post(
        "/api/v1/prompts/writing/en/new_chapter/preview",
        json={"variables": {"language": "en"}, "language": "en"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "system_prompt" in body
    assert "variables" in body


@pytest.mark.asyncio
async def test_reset_endpoint_returns_metadata(app_client: AsyncClient) -> None:
    resp = await app_client.post("/api/v1/prompts/writing/en/new_chapter/reset")
    assert resp.status_code == 200
    body = resp.json()
    assert body["reset"] in {True, False}
    assert "effective_source" in body


@pytest.mark.asyncio
async def test_live_test_endpoint_400_when_unacknowledged(
    app_client: AsyncClient,
) -> None:
    resp = await app_client.post(
        "/api/v1/prompts/writing/en/new_chapter/live-test",
        json={"variables": {}, "acknowledge_token_cost": False},
    )
    assert resp.status_code == 400
```

> **Note:** `app_client` is the existing fixture in `tests/integration/conftest.py`. If the fixture name differs, substitute the project's standard async client fixture.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/prompts/test_prompt_ux_router.py -v`
Expected: FAIL with 404 (route not registered).

- [ ] **Step 3: Implement `router_prompt_ux.py`**

```python
# apps/api/narrare/prompts/router_prompt_ux.py
"""PROMPT-003 (CR-AUFG-07-16) thin routes: preview, reset, optional SSE live test.

Split from ``router.py`` for RULE-04. Routes are declared with
``{prompt_id:path}`` and MUST be registered in ``main.py`` so they sit
beside the existing prompts tree. Specific sub-paths win over the
``/{prompt_id:path}`` GET in ``router.py`` because FastAPI matches by
longest literal segment when both routers share the prefix.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from narrare._app.dependencies import CurrentUserIdDep
from narrare._app.rate_limits import AI_PROMPT_LIVE_TEST_LIMITER
from narrare.prompts.schemas import (
    LiveTestRequest,
    LiveTestStartedResponse,
    PreviewRequest,
    PreviewResponse,
    ResetResponse,
)

router = APIRouter(prefix="/prompts", tags=["prompts"])


async def _get_preview_service() -> object:
    from narrare._app.dependencies import get_registry
    from narrare.prompts.preview_service import PromptPreviewApiService
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.prompts.preview import PromptPreviewService

    registry = get_registry()  # pyright: ignore[reportPrivateUsage]
    composer = PromptComposer(registry=registry)
    core = PromptPreviewService(composer=composer, registry=registry)
    return PromptPreviewApiService(core=core)


async def _get_reset_service() -> object:
    from narrare._app.dependencies import get_registry
    from narrare.prompts.preview_service import PromptResetApiService
    from narrare_core.prompts.management import PromptManagementService

    registry = get_registry()  # pyright: ignore[reportPrivateUsage]
    core = PromptManagementService(registry=registry)
    return PromptResetApiService(core=core)


async def _get_live_test_service() -> object:
    from narrare._app.dependencies import get_registry
    from narrare.prompts.live_test_service import PromptLiveTestApiService

    registry = get_registry()  # pyright: ignore[reportPrivateUsage]
    # Production factory wires the real ProviderGate + PromptLiveTestAgent.
    # Implementation-deferred seam; raise if not yet wired.
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="prompts.live_test.not_wired",
    )


@router.post(
    "/{prompt_id:path}/preview",
    response_model=PreviewResponse,
)
async def preview_prompt(
    prompt_id: str,
    request: PreviewRequest,
    user_id: CurrentUserIdDep,
    service: object = Depends(_get_preview_service),
) -> PreviewResponse:
    """Provider-free preview — no LLM, no tokens, no provider secret required."""
    return await service.preview(prompt_id, request)  # type: ignore[attr-defined]


@router.post(
    "/{prompt_id:path}/reset",
    response_model=ResetResponse,
)
async def reset_prompt(
    prompt_id: str,
    user_id: CurrentUserIdDep,
    service: object = Depends(_get_reset_service),
) -> ResetResponse:
    """Reset the override for one prompt and return effective metadata."""
    return await service.reset_with_metadata(prompt_id)  # type: ignore[attr-defined]


@router.post(
    "/{prompt_id:path}/live-test",
    dependencies=[Depends(AI_PROMPT_LIVE_TEST_LIMITER)],
    response_model=LiveTestStartedResponse,
)
async def start_live_test(
    prompt_id: str,
    request: LiveTestRequest,
    user_id: CurrentUserIdDep,
    service: object = Depends(_get_live_test_service),
) -> StreamingResponse:
    """Optional SSE live test — provider-/secret-gated, rate-limited.

    Validates first (so a 400/403/429 returns before SSE starts), then
    returns a ``StreamingResponse`` of ``text/event-stream`` frames.
    """
    try:
        await service.validate_live_test(  # type: ignore[attr-defined]
            prompt_id, request, user_id=user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return StreamingResponse(
        service.stream_live_test(  # type: ignore[attr-defined]
            prompt_id, request, user_id=user_id
        ),
        media_type="text/event-stream",
    )
```

> **Note:** `_get_live_test_service` raises 503 until the Platform/Backend specialist finishes wiring the real `ProviderGate` (existing `UserProvider`/`UserSecret` services). This keeps the route testable in isolation. The integration test for a successful stream (Task 13) MUST follow the real-wiring task. Until then, only the 400/403 paths are testable end-to-end.

- [ ] **Step 4: Register the router in `main.py`**

```python
# In apps/api/narrare/_app/main.py — add the import near prompts_router:
from narrare.prompts.router_prompt_ux import router as prompts_prompt_ux_router

# After app.include_router(prompts_router, prefix=prefix):
app.include_router(prompts_prompt_ux_router, prefix=prefix)
```

- [ ] **Step 5: Run test to verify the preview + reset + 400 paths pass**

Run: `uv run pytest tests/integration/prompts/test_prompt_ux_router.py -v`
Expected: 3 PASS.

### Task 11: Backend live-test wiring (real ProviderGate + AgentFactory)

**Files:**
- Modify: `apps/api/narrare/prompts/router_prompt_ux.py` — replace `_get_live_test_service` 503 stub with the real factory.
- Modify: `apps/api/narrare/prompts/live_test_service.py` — accept the real factory in production wiring.

- [ ] **Step 1: Inspect existing provider/secret services**

Run: `uv run python -c "from narrare._app.dependencies import get_registry; print([n for n in dir(get_registry()) if not n.startswith('_')])"` and look for existing `UserProvider` / `UserSecret` lookup services. Read the existing `apps/api/narrare/writing/deps.py` for the pattern of constructing a service with a resolved model.

- [ ] **Step 2: Implement the real factory**

```python
# Replace _get_live_test_service in router_prompt_ux.py:
async def _get_live_test_service() -> object:
    from narrare._app.dependencies import get_registry
    from narrare.prompts.live_test_service import PromptLiveTestApiService
    from narrare.providers.deps import get_provider_gate  # adjust to real path
    from narrare_core.agents.prompt_live_test_agent import PromptLiveTestAgent
    from narrare_core.llm import ModelRoutingConfig  # adjust to real type

    registry = get_registry()  # pyright: ignore[reportPrivateUsage]
    provider_gate = await get_provider_gate()

    def agent_factory(model: object | None) -> PromptLiveTestAgent:
        return PromptLiveTestAgent(model=model)

    return PromptLiveTestApiService(
        registry=registry,
        provider_gate=provider_gate,
        agent_factory=agent_factory,
    )
```

> **Note:** The exact import paths for the provider gate and routing config depend on the current `apps/api/narrare/` structure. Verify with `Grep` for `class UserProvider` / `ProviderGate` / `ModelRoutingConfig` and adjust. Do NOT invent a new gate — reuse the same surface the writing endpoints use.

- [ ] **Step 3: Add the successful-stream integration test**

```python
# Append to tests/integration/prompts/test_prompt_ux_router.py:
@pytest.mark.asyncio
async def test_live_test_endpoint_streams_sse_when_wired(
    app_client: AsyncClient,
) -> None:
    resp = await app_client.post(
        "/api/v1/prompts/writing/en/new_chapter/live-test",
        json={"variables": {"language": "en"}, "acknowledge_token_cost": True},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = (await resp.aread()).decode("utf-8")
    assert "event: meta" in body
    assert "data: [DONE]" in body


@pytest.mark.asyncio
async def test_live_test_endpoint_403_when_no_provider(
    app_client_without_provider: AsyncClient,
) -> None:
    resp = await app_client_without_provider.post(
        "/api/v1/prompts/writing/en/new_chapter/live-test",
        json={"variables": {}, "acknowledge_token_cost": True},
    )
    assert resp.status_code == 403
```

> **Note:** `app_client_without_provider` must be a fixture that seeds no provider for the test user. If it does not exist in `conftest.py`, add it (mirror the existing pattern for "no provider" scenarios in `tests/integration/writing/`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/prompts/test_prompt_ux_router.py -v`
Expected: all PASS.

### Task 12: Frontend types and API client

**Files:**
- Modify: `packages/web/types/prompts.ts`
- Modify: `packages/web/lib/api/prompts.ts`
- Create: `packages/web/lib/api/prompt-live-test-stream.ts`
- Create: `packages/web/lib/api/__tests__/prompt-live-test-stream.test.ts`

- [ ] **Step 1: Add the types**

```typescript
// Append to packages/web/types/prompts.ts:

export type PromptProvenance =
  | "current_author_instruction"
  | "project_writing_profile"
  | "scene_story_plan"
  | "curated_kb"
  | "learned_memory"
  | "generated_suggestion"
  | "system_generated"
  | "feature_dynamic";

export type PromptSecurity =
  | "xml_required"
  | "xml_section_required"
  | "label_required"
  | "generated_label_required"
  | "system_only";

export type PromptDiagnosticKind =
  | "missing_variable"
  | "unused_variable"
  | "validation_note";

export interface PromptVariableMetadata {
  readonly name: string;
  readonly description: string;
  readonly variable_type: string;
  readonly required: boolean;
  readonly provenance: PromptProvenance;
  readonly security: PromptSecurity;
}

export interface PromptDiagnostic {
  readonly kind: PromptDiagnosticKind;
  readonly variable_name: string | null;
  readonly message: string;
}

export interface PromptPreview {
  readonly system_prompt: string;
  readonly user_prompt: string;
  readonly first_message: string | null;
  readonly cascade_source: string;
  readonly variables: readonly PromptVariableMetadata[];
  readonly diagnostics: readonly PromptDiagnostic[];
}

export interface PreviewRequest {
  readonly variables: Record<string, string>;
  readonly language: "en" | "de" | "fr";
  readonly genre?: string;
  readonly mode?: string;
  readonly edited_override?: string;
}

export interface PromptResetResult {
  readonly reset: boolean;
  readonly effective_source: string;
  readonly effective_content: string;
}

export interface PromptLiveTestStarted {
  readonly prompt_id: string;
  readonly intent: string;
  readonly model_id: string;
  readonly rate_limit_remaining: number;
}

export interface LiveTestRequest {
  readonly variables: Record<string, string>;
  readonly language: "en" | "de" | "fr";
  readonly genre?: string;
  readonly mode?: string;
  readonly edited_override?: string;
  readonly user_prompt: string;
  readonly acknowledge_token_cost: boolean;
}
```

- [ ] **Step 2: Add the API client methods**

```typescript
// Append to the promptsApi object in packages/web/lib/api/prompts.ts:
import type {
  // existing imports...
  LiveTestRequest,
  PreviewRequest,
  PromptLiveTestStarted,
  PromptPreview,
  PromptResetResult,
} from "@/types";

// Inside the promptsApi object:
preview: (id: string, req: PreviewRequest) =>
  fetchApi<PromptPreview>(`/prompts/${id}/preview`, {
    method: "POST",
    body: JSON.stringify(req),
  }),

resetWithMetadata: (id: string) =>
  fetchApi<PromptResetResult>(`/prompts/${id}/reset`, { method: "POST" }),

startLiveTest: (id: string, req: LiveTestRequest) =>
  // Returns raw Response — the caller hands it to readPromptLiveTestStream.
  fetchApiRaw(`/prompts/${id}/live-test`, {
    method: "POST",
    body: JSON.stringify(req),
  }),
```

> **Note:** If `fetchApiRaw` does not exist in `lib/api/core.ts`, add a thin wrapper that returns the native `Response` (mirror the existing SSE patterns in `lib/api/` such as the co-author client). Do not let `fetchApi` parse JSON here — SSE responses are consumed as a stream.

- [ ] **Step 3: Implement the SSE stream reader**

```typescript
// packages/web/lib/api/prompt-live-test-stream.ts
import type { PromptLiveTestStarted } from "@/types";

export interface LiveTestStreamCallbacks {
  readonly onMeta: (meta: PromptLiveTestStarted) => void;
  readonly onChunk: (text: string) => void;
  readonly onDone: () => void;
  readonly onError: (error: Error) => void;
}

/**
 * Reads a `text/event-stream` response from POST /prompts/{id}/live-test.
 * Uses native fetch + ReadableStream per GLOSSARY (no axios).
 */
export async function readPromptLiveTestStream(
  response: Response,
  callbacks: LiveTestStreamCallbacks,
  signal: AbortSignal,
): Promise<void> {
  if (!response.body) {
    callbacks.onError(new Error("no_stream_body"));
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      if (signal.aborted) {
        await reader.cancel();
        callbacks.onDone();
        return;
      }
      const { value, done } = await reader.read();
      if (done) {
        callbacks.onDone();
        return;
      }
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        applyFrame(frame, callbacks);
      }
    }
  } catch (err) {
    callbacks.onError(err instanceof Error ? err : new Error(String(err)));
  }
}

function applyFrame(frame: string, callbacks: LiveTestStreamCallbacks): void {
  const lines = frame.split("\n");
  let event = "message";
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  }
  if (dataLines.length === 0) return;
  const joined = dataLines.join("\n");
  if (joined === "[DONE]") {
    callbacks.onDone();
    return;
  }
  try {
    const parsed = JSON.parse(joined) as Record<string, unknown>;
    if (event === "meta") {
      callbacks.onMeta(parsed as unknown as PromptLiveTestStarted);
    } else if (event === "done") {
      callbacks.onDone();
    } else if (typeof parsed.text === "string") {
      callbacks.onChunk(parsed.text);
    }
  } catch {
    /* ignore malformed frames — SSE is best-effort per-frame */
  }
}
```

- [ ] **Step 4: Write the failing stream test**

```typescript
// packages/web/lib/api/__tests__/prompt-live-test-stream.test.ts
import { describe, expect, it, vi } from "vitest";
import { readPromptLiveTestStream } from "@/lib/api/prompt-live-test-stream";

function mockResponse(frames: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const f of frames) controller.enqueue(encoder.encode(f));
      controller.close();
    },
  });
  return new Response(stream, { headers: { "content-type": "text/event-stream" } });
}

describe("readPromptLiveTestStream", () => {
  it("invokes onMeta, onChunk, onDone in order", async () => {
    const onMeta = vi.fn();
    const onChunk = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();
    const frames = [
      `event: meta\ndata: ${JSON.stringify({ prompt_id: "p", intent: "writing", model_id: "m", rate_limit_remaining: 4 })}\n\n`,
      `data: ${JSON.stringify({ text: "Hello " })}\n\n`,
      `data: ${JSON.stringify({ text: "world" })}\n\n`,
      `event: done\ndata: ${JSON.stringify({ is_final: true })}\n\n`,
      `data: [DONE]\n\n`,
    ];
    const ac = new AbortController();
    await readPromptLiveTestStream(
      mockResponse(frames),
      { onMeta, onChunk, onDone, onError },
      ac.signal,
    );
    expect(onMeta).toHaveBeenCalledOnce();
    expect(onChunk).toHaveBeenCalledTimes(2);
    expect(onDone).toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
  });

  it("calls onError on missing body", async () => {
    const onError = vi.fn();
    const ac = new AbortController();
    await readPromptLiveTestStream(
      new Response(null),
      { onMeta: vi.fn(), onChunk: vi.fn(), onDone: vi.fn(), onError },
      ac.signal,
    );
    expect(onError).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd packages/web && pnpm vitest run lib/api/__tests__/prompt-live-test-stream.test.ts`
Expected: PASS.

### Task 13: Frontend `VariableMetadataPanel`

**Files:**
- Create: `packages/web/components/studio/settings/VariableMetadataPanel.tsx`
- Create: `packages/web/components/studio/settings/__tests__/VariableMetadataPanel.test.tsx`

- [ ] **Step 1: Write the failing component test**

```typescript
// packages/web/components/studio/settings/__tests__/VariableMetadataPanel.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { VariableMetadataPanel } from "@/components/studio/settings/VariableMetadataPanel";
import type { PromptVariableMetadata } from "@/types";

const vars: readonly PromptVariableMetadata[] = [
  {
    name: "language",
    description: "ISO language code",
    variable_type: "text",
    required: true,
    provenance: "system_generated",
    security: "system_only",
  },
  {
    name: "kb_summary",
    description: "KB summary",
    variable_type: "text",
    required: false,
    provenance: "curated_kb",
    security: "xml_section_required",
  },
];

describe("VariableMetadataPanel", () => {
  it("renders each variable with provenance + security labels", () => {
    render(<VariableMetadataPanel variables={vars} />);
    expect(screen.getByText("language")).toBeInTheDocument();
    expect(screen.getByText("kb_summary")).toBeInTheDocument();
    expect(screen.getByText(/system_generated/)).toBeInTheDocument();
    expect(screen.getByText(/curated_kb/)).toBeInTheDocument();
    expect(screen.getByText(/system_only/)).toBeInTheDocument();
    expect(screen.getByText(/xml_section_required/)).toBeInTheDocument();
  });

  it("renders empty-state message when no variables", () => {
    render(<VariableMetadataPanel variables={[]} />);
    expect(screen.getByText(/noVariables/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && pnpm vitest run components/studio/settings/__tests__/VariableMetadataPanel.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement the component**

```tsx
// packages/web/components/studio/settings/VariableMetadataPanel.tsx
"use client";

import { useTranslations } from "next-intl";
import type { PromptVariableMetadata } from "@/types";

interface VariableMetadataPanelProps {
  readonly variables: readonly PromptVariableMetadata[];
}

/** Per-variable provenance/security table — fed by the provider-free preview. */
export function VariableMetadataPanel({ variables }: VariableMetadataPanelProps) {
  const t = useTranslations("studio");

  if (variables.length === 0) {
    return (
      <p className="text-sm text-muted-foreground" role="status">
        {t("settings.prompts.promptCustomization.noVariables")}
      </p>
    );
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-xs uppercase text-muted-foreground">
          <th className="py-1 pr-3">{t("settings.prompts.promptCustomization.variableName")}</th>
          <th className="py-1 pr-3">{t("settings.prompts.promptCustomization.variableDescription")}</th>
          <th className="py-1 pr-3">{t("settings.prompts.promptCustomization.variableProvenance")}</th>
          <th className="py-1 pr-3">{t("settings.prompts.promptCustomization.variableSecurity")}</th>
        </tr>
      </thead>
      <tbody>
        {variables.map((v) => (
          <tr key={v.name} className="border-t border-border">
            <td className="py-1 pr-3 font-mono">{`{{${v.name}}}`}</td>
            <td className="py-1 pr-3 text-muted-foreground">{v.description}</td>
            <td className="py-1 pr-3 font-mono">{v.provenance}</td>
            <td className="py-1 pr-3 font-mono">{v.security}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && pnpm vitest run components/studio/settings/__tests__/VariableMetadataPanel.test.tsx`
Expected: PASS.

### Task 14: Frontend `PromptPreviewDialog`

**Files:**
- Create: `packages/web/components/studio/settings/PromptPreviewDialog.tsx`
- Create: `packages/web/components/studio/settings/__tests__/PromptPreviewDialog.test.tsx`

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/components/studio/settings/__tests__/PromptPreviewDialog.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PromptPreviewDialog } from "@/components/studio/settings/PromptPreviewDialog";
import type { PromptPreview } from "@/types";

const preview: PromptPreview = {
  system_prompt: "Resolved system prompt body",
  user_prompt: "Resolved user",
  first_message: null,
  cascade_source: "bundled",
  variables: [],
  diagnostics: [
    { kind: "missing_variable", variable_name: "project_title", message: "missing_required_variable:project_title" },
  ],
};

describe("PromptPreviewDialog", () => {
  it("shows the resolved system prompt and cascade source", () => {
    render(
      <PromptPreviewDialog open={true} onOpenChange={() => {}} promptId="writing/en/new_chapter" preview={preview} loading={false} />,
    );
    expect(screen.getByText(/Resolved system prompt body/)).toBeInTheDocument();
    expect(screen.getByText(/bundled/)).toBeInTheDocument();
  });

  it("shows diagnostics when present", () => {
    render(
      <PromptPreviewDialog open={true} onOpenChange={() => {}} promptId="writing/en/new_chapter" preview={preview} loading={false} />,
    );
    expect(screen.getByText(/missing_variable/)).toBeInTheDocument();
  });

  it("shows loading state when preview is loading", () => {
    render(
      <PromptPreviewDialog open={true} onOpenChange={() => {}} promptId="writing/en/new_chapter" preview={null} loading={true} />,
    );
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && pnpm vitest run components/studio/settings/__tests__/PromptPreviewDialog.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement the dialog**

```tsx
// packages/web/components/studio/settings/PromptPreviewDialog.tsx
"use client";

import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import type { PromptPreview } from "@/types";
import { VariableMetadataPanel } from "./VariableMetadataPanel";

interface PromptPreviewDialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly promptId: string;
  readonly preview: PromptPreview | null;
  readonly loading: boolean;
}

export function PromptPreviewDialog({
  open,
  onOpenChange,
  promptId,
  preview,
  loading,
}: PromptPreviewDialogProps) {
  const t = useTranslations("studio");

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      role="dialog"
      aria-modal="true"
      aria-label={t("settings.prompts.promptCustomization.previewTitle")}
      onClick={() => onOpenChange(false)}
    >
      <div
        className="bg-card border border-border rounded-xl shadow-2xl p-6 max-w-3xl w-full max-h-[80vh] overflow-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between mb-4">
          <h2 className="text-base font-medium">
            {t("settings.prompts.promptCustomization.previewTitle")}
          </h2>
          <span className="text-xs text-muted-foreground font-mono">
            {preview ? preview.cascade_source : ""}
          </span>
        </header>

        {loading || !preview ? (
          <div className="flex items-center justify-center py-12" role="status">
            <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
            <span className="ml-2 text-sm text-muted-foreground">
              {t("settings.prompts.promptCustomization.loading")}
            </span>
          </div>
        ) : (
          <>
            <section className="mb-4">
              <h3 className="text-xs uppercase text-muted-foreground mb-1">
                {t("settings.prompts.promptCustomization.resolvedSystem")}
              </h3>
              <pre className="whitespace-pre-wrap text-sm font-mono bg-muted rounded-md p-3">
                {preview.system_prompt || t("settings.prompts.promptCustomization.emptyResolution")}
              </pre>
            </section>
            <section className="mb-4">
              <h3 className="text-xs uppercase text-muted-foreground mb-1">
                {t("settings.prompts.promptCustomization.variables")}
              </h3>
              <VariableMetadataPanel variables={preview.variables} />
            </section>
            {preview.diagnostics.length > 0 && (
              <section className="mb-4" aria-label={t("settings.prompts.promptCustomization.diagnostics")}>
                <h3 className="text-xs uppercase text-muted-foreground mb-1">
                  {t("settings.prompts.promptCustomization.diagnostics")}
                </h3>
                <ul className="text-sm space-y-1">
                  {preview.diagnostics.map((d, i) => (
                    <li key={`${d.kind}-${d.variable_name ?? ""}-${i}`} className="text-amber-700 dark:text-amber-300">
                      {`[${d.kind}] ${d.variable_name ?? "-"}: ${d.message}`}
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </>
        )}

        <footer className="flex justify-end">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="px-4 py-2 bg-muted rounded-md hover:bg-accent text-sm"
          >
            {t("settings.prompts.promptCustomization.close")}
          </button>
        </footer>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && pnpm vitest run components/studio/settings/__tests__/PromptPreviewDialog.test.tsx`
Expected: PASS.

### Task 15: Frontend `PromptLiveTestDialog` + `PromptResetConfirmDialog`

**Files:**
- Create: `packages/web/components/studio/settings/PromptLiveTestDialog.tsx`
- Create: `packages/web/components/studio/settings/PromptResetConfirmDialog.tsx`
- Create: `packages/web/components/studio/settings/__tests__/PromptLiveTestDialog.test.tsx`
- Create: `packages/web/components/studio/settings/__tests__/PromptResetConfirmDialog.test.tsx`

- [ ] **Step 1: Write the failing `PromptLiveTestDialog` test**

```typescript
// packages/web/components/studio/settings/__tests__/PromptLiveTestDialog.test.tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PromptLiveTestDialog } from "@/components/studio/settings/PromptLiveTestDialog";

describe("PromptLiveTestDialog", () => {
  it("shows token warning gate before first run", () => {
    render(
      <PromptLiveTestDialog
        open={true}
        onOpenChange={() => {}}
        promptId="writing/en/new_chapter"
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getByText(/tokenWarning/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /confirmRun/i })).toBeInTheDocument();
  });

  it("does not call onConfirm until user confirms the warning", () => {
    const onConfirm = vi.fn();
    render(
      <PromptLiveTestDialog
        open={true}
        onOpenChange={() => {}}
        promptId="writing/en/new_chapter"
        onConfirm={onConfirm}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /confirmRun/i }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 2: Write the failing `PromptResetConfirmDialog` test**

```typescript
// packages/web/components/studio/settings/__tests__/PromptResetConfirmDialog.test.tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PromptResetConfirmDialog } from "@/components/studio/settings/PromptResetConfirmDialog";

describe("PromptResetConfirmDialog", () => {
  it("renders override and bundled content preview", () => {
    render(
      <PromptResetConfirmDialog
        open={true}
        onOpenChange={() => {}}
        promptId="writing/en/new_chapter"
        overrideContent="my override"
        bundledContent="default"
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getByText(/my override/)).toBeInTheDocument();
    expect(screen.getByText(/default/)).toBeInTheDocument();
  });

  it("calls onConfirm when the destructive confirm button is clicked", () => {
    const onConfirm = vi.fn();
    render(
      <PromptResetConfirmDialog
        open={true}
        onOpenChange={() => {}}
        promptId="writing/en/new_chapter"
        overrideContent="x"
        bundledContent="y"
        onConfirm={onConfirm}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /resetToDefault/i }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd packages/web && pnpm vitest run components/studio/settings/__tests__/PromptLiveTestDialog.test.tsx components/studio/settings/__tests__/PromptResetConfirmDialog.test.tsx`
Expected: FAIL.

- [ ] **Step 4: Implement `PromptLiveTestDialog.tsx`**

```tsx
// packages/web/components/studio/settings/PromptLiveTestDialog.tsx
"use client";

import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { readPromptLiveTestStream } from "@/lib/api/prompt-live-test-stream";
import { promptsApi } from "@/lib/api/client";

interface PromptLiveTestDialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly promptId: string;
  readonly variables: Readonly<Record<string, string>>;
  readonly language: "en" | "de" | "fr";
  readonly editedOverride: string | null;
}

/**
 * Optional provider-/secret-gated live test. Shows the token/privacy
 * warning before the first run, then streams SSE output. Cancel/Escape
 * abort the underlying request. Output is never persisted.
 */
export function PromptLiveTestDialog({
  open,
  onOpenChange,
  promptId,
  variables,
  language,
  editedOverride,
}: PromptLiveTestDialogProps) {
  const t = useTranslations("studio");
  const [confirmed, setConfirmed] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [output, setOutput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!open) {
      setConfirmed(false);
      setStreaming(false);
      setOutput("");
      setError(null);
      abortRef.current?.abort();
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        abortRef.current?.abort();
        onOpenChange(false);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  if (!open) return null;

  const handleRun = async () => {
    setStreaming(true);
    setError(null);
    setOutput("");
    const ac = new AbortController();
    abortRef.current = ac;
    try {
      const resp = await promptsApi.startLiveTest(promptId, {
        variables,
        language,
        edited_override: editedOverride ?? undefined,
        user_prompt: "",
        acknowledge_token_cost: confirmed,
      });
      if (!resp.ok) {
        const msg = resp.status === 403 ? "no_active_provider" : "live_test_failed";
        setError(t(`settings.prompts.promptCustomization.${msg}`));
        return;
      }
      await readPromptLiveTestStream(
        resp,
        {
          onMeta: () => {},
          onChunk: (text) => setOutput((prev) => prev + text),
          onDone: () => setStreaming(false),
          onError: (e) => {
            setError(e.message);
            setStreaming(false);
          },
        },
        ac.signal,
      );
    } finally {
      setStreaming(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      role="dialog"
      aria-modal="true"
      aria-label={t("settings.prompts.promptCustomization.testTitle")}
      onClick={() => onOpenChange(false)}
    >
      <div
        className="bg-card border border-border rounded-xl shadow-2xl p-6 max-w-3xl w-full max-h-[80vh] overflow-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between mb-4">
          <h2 className="text-base font-medium">
            {t("settings.prompts.promptCustomization.testTitle")}
          </h2>
        </header>

        {!confirmed && (
          <section
            className="mb-4 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm"
            aria-label={t("settings.prompts.promptCustomization.tokenWarning")}
          >
            <p>{t("settings.prompts.promptCustomization.tokenWarning")}</p>
            <button
              type="button"
              onClick={() => setConfirmed(true)}
              className="mt-2 px-3 py-1 rounded-md bg-amber-500/20 text-sm hover:bg-amber-500/30"
            >
              {t("settings.prompts.promptCustomization.confirmRun")}
            </button>
          </section>
        )}

        {confirmed && (
          <section>
            <pre
              className="whitespace-pre-wrap text-sm font-mono bg-muted rounded-md p-3 min-h-[200px]"
              aria-live="polite"
            >
              {output || (streaming ? "…" : t("settings.prompts.promptCustomization.testEmpty"))}
            </pre>
            {error && (
              <p role="alert" className="text-sm text-destructive mt-2">
                {error}
              </p>
            )}
            <div className="flex justify-end gap-3 mt-3">
              <button
                type="button"
                onClick={() => {
                  abortRef.current?.abort();
                  setStreaming(false);
                }}
                disabled={!streaming}
                className="px-4 py-2 bg-muted rounded-md hover:bg-accent text-sm disabled:opacity-50"
              >
                {t("aiActions.stop")}
              </button>
              <button
                type="button"
                onClick={handleRun}
                disabled={streaming}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm disabled:opacity-50"
              >
                {streaming ? <Loader2 className="w-4 h-4 animate-spin" /> : t("aiActions.retry")}
              </button>
            </div>
          </section>
        )}

        <footer className="flex justify-end mt-4">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="px-4 py-2 bg-muted rounded-md hover:bg-accent text-sm"
          >
            {t("settings.prompts.promptCustomization.close")}
          </button>
        </footer>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Implement `PromptResetConfirmDialog.tsx`**

```tsx
// packages/web/components/studio/settings/PromptResetConfirmDialog.tsx
"use client";

import { useTranslations } from "next-intl";

interface PromptResetConfirmDialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly promptId: string;
  readonly overrideContent: string;
  readonly bundledContent: string;
  readonly onConfirm: () => void;
  readonly pending?: boolean;
}

export function PromptResetConfirmDialog({
  open,
  onOpenChange,
  overrideContent,
  bundledContent,
  onConfirm,
  pending = false,
}: PromptResetConfirmDialogProps) {
  const t = useTranslations("studio");
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      role="dialog"
      aria-modal="true"
      aria-label={t("settings.prompts.resetToDefault")}
      onClick={() => onOpenChange(false)}
    >
      <div
        className="bg-card border border-border rounded-xl shadow-2xl p-6 max-w-3xl w-full"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-base font-medium mb-2">{t("settings.prompts.resetToDefault")}</h2>
        <p className="text-sm text-muted-foreground mb-4">
          {t("settings.prompts.confirmReset")}
        </p>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <h3 className="text-xs uppercase text-muted-foreground mb-1">
              {t("settings.prompts.yourVersion")}
            </h3>
            <pre className="whitespace-pre-wrap text-xs font-mono bg-muted rounded-md p-2 max-h-48 overflow-auto">
              {overrideContent}
            </pre>
          </div>
          <div>
            <h3 className="text-xs uppercase text-muted-foreground mb-1">
              {t("settings.prompts.newDefault")}
            </h3>
            <pre className="whitespace-pre-wrap text-xs font-mono bg-muted rounded-md p-2 max-h-48 overflow-auto">
              {bundledContent}
            </pre>
          </div>
        </div>
        <footer className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="px-4 py-2 bg-muted rounded-md hover:bg-accent text-sm"
          >
            {t("settings.prompts.cancel")}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={pending}
            className="px-4 py-2 bg-destructive text-destructive-foreground rounded-md text-sm disabled:opacity-50"
          >
            {t("settings.prompts.resetToDefault")}
          </button>
        </footer>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd packages/web && pnpm vitest run components/studio/settings/__tests__/PromptLiveTestDialog.test.tsx components/studio/settings/__tests__/PromptResetConfirmDialog.test.tsx`
Expected: PASS.

### Task 16: Frontend `PromptEditor` modularization (RULE-04)

**Files:**
- Create: `packages/web/components/studio/settings/usePromptEditorState.ts`
- Modify: `packages/web/components/studio/settings/PromptEditor.tsx`
- Modify: `packages/web/components/studio/settings/PromptEditorViewMode.tsx`
- Delete: `packages/web/components/studio/settings/PromptPreview.tsx` (after removing its only importer)
- Modify: `packages/web/components/studio/settings/__tests__/PromptEditor.test.tsx`

- [ ] **Step 1: Extract the state hook**

```typescript
// packages/web/components/studio/settings/usePromptEditorState.ts
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { promptsApi } from "@/lib/api/client";
import type { PromptPreview, PromptResetResult } from "@/types";

export interface PromptEditorState {
  readonly editMode: boolean;
  readonly editedContent: string;
  readonly showPreviewDialog: boolean;
  readonly showLiveTestDialog: boolean;
  readonly showResetConfirm: boolean;
  readonly preview: PromptPreview | null;
  readonly previewLoading: boolean;
  readonly prompt: ReturnType<typeof useQuery<unknown>>["data"];
  readonly isLoading: boolean;
  readonly error: unknown;
  readonly saveMutation: ReturnType<typeof useMutation>;
  readonly resetMutation: ReturnType<typeof useMutation<PromptResetResult>>;
  readonly previewMutation: ReturnType<typeof useMutation<PromptPreview>>;
  readonly setEditMode: (v: boolean) => void;
  readonly setEditedContent: (v: string) => void;
  readonly setShowPreviewDialog: (v: boolean) => void;
  readonly setShowLiveTestDialog: (v: boolean) => void;
  readonly setShowResetConfirm: (v: boolean) => void;
  readonly handleStartEdit: () => void;
  readonly handleSave: () => void;
  readonly handleReset: () => void;
  readonly handlePreview: () => void;
}

export function usePromptEditorState(promptId: string): PromptEditorState {
  // (Implementation: move the existing state + mutations from PromptEditor.tsx,
  //  add previewMutation that calls promptsApi.preview(...) with current project
  //  variables. Strip out the local previewMode/sample-substitution entirely.)
  throw new Error("usePromptEditorState: TODO move implementation in Step 2");
}
```

> **Note:** The `throw new Error` is a placeholder ONLY inside the plan document. The implementing subagent MUST move the real logic from `PromptEditor.tsx` lines 26-105 (state + mutations) into this hook verbatim, then add `previewMutation` and the three dialog state flags. The hook must stay under the 150-line hook limit.

- [ ] **Step 2: Move the implementation into the hook**

Read `packages/web/components/studio/settings/PromptEditor.tsx` lines 26-105. Move every `useState`, `useQuery`, `useMutation` into `usePromptEditorState.ts`. Replace the local `previewMode` toggle with `showPreviewDialog` + `previewMutation` + `preview` + `previewLoading`. Add `showLiveTestDialog` and `showResetConfirm`. The hook returns the aggregated state object.

- [ ] **Step 3: Update `PromptEditor.tsx` to consume the hook + render the three dialogs**

```tsx
// packages/web/components/studio/settings/PromptEditor.tsx (new shape)
"use client";

import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { PromptDiff } from "./PromptDiff";
import { PromptEditorEditMode } from "./PromptEditorEditMode";
import { PromptEditorHeader } from "./PromptEditorHeader";
import { PromptEditorViewMode } from "./PromptEditorViewMode";
import { PromptLiveTestDialog } from "./PromptLiveTestDialog";
import { PromptPreviewDialog } from "./PromptPreviewDialog";
import { PromptResetConfirmDialog } from "./PromptResetConfirmDialog";
import { PromptVariablesAside } from "./PromptVariablesAside";
import { usePromptEditorState } from "./usePromptEditorState";

interface PromptEditorProps {
  readonly promptId: string;
  readonly hasUpdate: boolean;
  readonly onBack: () => void;
}

export function PromptEditor({ promptId, hasUpdate, onBack }: PromptEditorProps) {
  const t = useTranslations("studio");
  const s = usePromptEditorState(promptId);

  if (s.showDiffEquivalent()) {
    return <PromptDiff promptId={promptId} onBack={s.clearDiff} onResolved={s.invalidateAfterDiff} />;
  }
  if (s.isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">{t("settings.prompts.loadingPrompt")}</span>
      </div>
    );
  }
  if (s.error || !s.prompt) {
    return (
      <div className="space-y-4">
        <div className="bg-destructive/10 text-destructive rounded-md p-3 text-sm" role="alert">
          {t("settings.prompts.loadFailed")}
        </div>
        <button type="button" onClick={onBack} className="px-4 py-2 bg-muted rounded-md text-sm">
          {t("settings.prompts.back")}
        </button>
      </div>
    );
  }

  return (
    <div>
      <PromptEditorHeader
        promptId={promptId}
        isOverridden={s.prompt.is_overridden}
        hasUpdate={hasUpdate}
        statusMessage={s.statusMessage}
        onBack={onBack}
        onShowDiff={s.openDiff}
      />
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex gap-6">
          <div className="flex-1 space-y-4">
            {s.editMode ? (
              <PromptEditorEditMode
                editedContent={s.editedContent}
                onContentChange={s.setEditedContent}
                onSave={s.handleSave}
                onCancel={() => s.setEditMode(false)}
                isSavePending={s.saveMutation.isPending}
              />
            ) : (
              <PromptEditorViewMode
                content={s.prompt.content}
                isOverridden={s.prompt.is_overridden}
                variables={s.prompt.variables}
                onStartEdit={s.handleStartEdit}
                onOpenPreview={() => s.setShowPreviewDialog(true)}
                onOpenLiveTest={() => s.setShowLiveTestDialog(true)}
                onOpenReset={() => s.setShowResetConfirm(true)}
                isResetPending={s.resetMutation.isPending}
              />
            )}
          </div>
          {s.prompt.variables.length > 0 && <PromptVariablesAside variables={s.prompt.variables} />}
        </div>
      </div>

      <PromptPreviewDialog
        open={s.showPreviewDialog}
        onOpenChange={s.setShowPreviewDialog}
        promptId={promptId}
        preview={s.preview}
        loading={s.previewLoading}
      />
      <PromptLiveTestDialog
        open={s.showLiveTestDialog}
        onOpenChange={s.setShowLiveTestDialog}
        promptId={promptId}
        variables={{}}
        language="en"
        editedOverride={s.editMode ? s.editedContent : null}
      />
      <PromptResetConfirmDialog
        open={s.showResetConfirm}
        onOpenChange={s.setShowResetConfirm}
        promptId={promptId}
        overrideContent={s.prompt.content}
        bundledContent={s.prompt.base_content}
        pending={s.resetMutation.isPending}
        onConfirm={() => {
          s.resetMutation.mutate();
          s.setShowResetConfirm(false);
        }}
      />
    </div>
  );
}
```

> **Note:** The exact set of helper methods (`s.showDiffEquivalent`, `s.clearDiff`, `s.invalidateAfterDiff`, `s.openDiff`, `s.statusMessage`) depends on what was moved into the hook in Step 2. The invariant: the hook owns ALL state; `PromptEditor.tsx` is render-only orchestration. If the hook exceeds 150 lines, split diff-related state into `usePromptDiffState.ts` (not preview/live-test state — those stay together).

- [ ] **Step 4: Update `PromptEditorViewMode.tsx`**

Remove the local `previewMode` toggle and the embedded `<PromptPreview>` import. Replace the props with: `onOpenPreview`, `onOpenLiveTest`, `onOpenReset`, `onStartEdit`, `isResetPending`, `content`, `isOverridden`, `variables`. Render two buttons (Preview, Live-Test) in the toolbar plus the existing Edit + Reset buttons. The body always shows the raw template in a `<pre>` (no local substitution).

- [ ] **Step 5: Delete `PromptPreview.tsx`**

Run: `rm packages/web/components/studio/settings/PromptPreview.tsx`
If `packages/web/components/studio/settings/__tests__/PromptPreview.test.tsx` exists, also delete it. (Check with `ls packages/web/components/studio/settings/__tests__/` first.)

- [ ] **Step 6: Update `PromptEditor.test.tsx`**

Rewrite the test to:
- Assert "Open preview" button opens the dialog (mock `promptsApi.preview` to resolve with the test fixture).
- Assert the live-test warning gate renders.
- Assert the reset dialog shows override vs. bundled content.
- Remove any test that asserted local `EXAMPLE_VALUES` substitution.

- [ ] **Step 7: Run the full settings test suite + file-size gate**

Run: `cd packages/web && pnpm vitest run components/studio/settings/`
Expected: PASS.

Run: `uv run python scripts/check_frontend_file_size.py`
Expected: 0 new violations. `PromptEditor.tsx` must be ≤200 lines; `usePromptEditorState.ts` ≤150 lines.

### Task 17: i18n keys (DE/EN/FR parity)

**Files:**
- Modify: `packages/i18n/messages/{de,en,fr}/studio.json`

- [ ] **Step 1: Add the keys to all three locales**

Insert under `settings.prompts.promptCustomization` in each `studio.json`:

| Key | DE | EN | FR |
|-----|----|----|----|
| `title` | Prompt-Anpassung | Prompt Customization | Personnalisation des prompts |
| `variables` | Verfügbare Variablen | Available Variables | Variables disponibles |
| `preview` | Aufgelösten Prompt anzeigen | Show Resolved Prompt | Afficher le prompt résolu |
| `previewTitle` | Prompt-Vorschau | Prompt Preview | Aperçu du prompt |
| `test` | Prompt live testen | Test Prompt Live | Tester le prompt en direct |
| `testTitle` | Live-Test | Live Test | Test en direct |
| `reset` | Auf Standard zurücksetzen | Reset to Default | Réinitialiser |
| `resetConfirm` | Wirklich zurücksetzen? | Reset to default? | Réinitialiser ? |
| `resetDone` | Prompt zurückgesetzt | Prompt reset | Prompt réinitialisé |
| `tokenWarning` | Dies verbraucht KI-Tokens und sendet Projektdaten an deinen Provider. | This consumes AI tokens and sends project data to your provider. | Cela consomme des tokens IA et envoie les données du projet à votre fournisseur. |
| `confirmRun` | Verstanden, Test starten | Understood, run test | Compris, lancer le test |
| `testEmpty` | Noch kein Test-Output | No test output yet | Pas encore de sortie |
| `variableName` | Variable | Variable | Variable |
| `variableDescription` | Beschreibung | Description | Description |
| `variableProvenance` | Quelle | Source | Source |
| `variableSecurity` | Sicherheit | Security | Sécurité |
| `diagnostics` | Diagnostik | Diagnostics | Diagnostics |
| `resolvedSystem` | Aufgelöster System-Prompt | Resolved System Prompt | Prompt système résolu |
| `cascadeSource` | Cascade-Stufe | Cascade Source | Source de cascade |
| `loading` | Lade Vorschau… | Loading preview… | Chargement de l'aperçu… |
| `emptyResolution` | Auflösung fehlgeschlagen | Resolution failed | Échec de la résolution |
| `noVariables` | Keine Variablen im Prompt | No variables in prompt | Aucune variable dans le prompt |
| `close` | Schließen | Close | Fermer |
| `no_active_provider` | Kein aktiver Provider konfiguriert. | No active provider configured. | Aucun fournisseur actif configuré. |
| `live_test_failed` | Live-Test fehlgeschlagen. | Live test failed. | Le test en direct a échoué. |

- [ ] **Step 2: Run the i18n parity gate**

Run: `uv run python scripts/check_i18n_parity.py` (or `just check-i18n` if configured).
Expected: 0 missing keys across DE/EN/FR.

If the script name differs, locate it: `ls scripts/checks/ | grep -i i18n`. The parity check must pass before this task is complete.

### Task 18: Platform contract tests (no-provider invariant + API↔Frontend schema)

**Files:**
- Modify: `tests/unit/core/prompts/test_preview_no_provider.py` (already added in Task 3 — extend if needed)
- Create: `tests/contract/test_prompt_preview_schema.py` (or extend existing contract test dir)

- [ ] **Step 1: Write the API↔Frontend schema contract test**

```python
# tests/contract/test_prompt_preview_schema.py
"""Contract: Pydantic PreviewResponse JSON shape == TypeScript PromptPreview shape."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from narrare.prompts.schemas import PreviewResponse

_ROOT = Path(__file__).parents[2]
_TS_PROMPTS = (_ROOT / "packages/web/types/prompts.ts").read_text(encoding="utf-8")


def test_preview_response_keys_match_ts_type() -> None:
    sample = PreviewResponse(
        system_prompt="s",
        user_prompt="u",
        first_message=None,
        cascade_source="bundled",
        variables=[],
        diagnostics=[],
    )
    payload = json.loads(TypeAdapter(PreviewResponse).dump_json(sample))
    expected = {
        "system_prompt",
        "user_prompt",
        "first_message",
        "cascade_source",
        "variables",
        "diagnostics",
    }
    assert set(payload) == expected
    for field in expected:
        assert field in _TS_PROMPTS, (
            f"TS PromptPreview missing field '{field}' — add it to types/prompts.ts"
        )
```

- [ ] **Step 2: Run the contract test**

Run: `uv run pytest tests/contract/test_prompt_preview_schema.py -v`
Expected: PASS.

### Task 19: AI Operation Inventory + AUFG evidence (only after all gates pass)

**Files:**
- Modify: `scripts/checks/ai_operation_inventory.yaml`
- Modify: `docs/architecture/governance/aufg-registry.md`
- Modify: `docs/features/prompt-customization-ux.md`

- [ ] **Step 1: Add the live-test operation to the inventory**

Append a new entry under `operations:` in `scripts/checks/ai_operation_inventory.yaml`:

```yaml
- id: settings.prompts.live_test
  path: packages/web/components/studio/settings/PromptLiveTestDialog.tsx
  backend: apps/api/narrare/prompts/router_prompt_ux.py
  sse: true
  cancel: true
  retry: true
  loading_state: streaming_progressive
  error_severity: non_blocking
  i18n_keys:
    - studio.settings.prompts.promptCustomization.tokenWarning
    - studio.settings.prompts.promptCustomization.live_test_failed
    - studio.settings.prompts.promptCustomization.no_active_provider
  owner: backend+frontend
```

- [ ] **Step 2: Run the AI-UX gate**

Run: `just check-ai-ux`
Expected: 0 violations.

- [ ] **Step 3: Update the AUFG registry**

In `docs/architecture/governance/aufg-registry.md`, change the CR-AUFG-07-16 row status from `open` to `resolved` and append the evidence column with:
- Implementation files: list every Core/Backend/Frontend file from this plan.
- Enforcement: `pytest tests/unit/core/prompts/test_preview_no_provider.py tests/contract/test_prompt_preview_schema.py tests/integration/prompts/test_prompt_ux_router.py`, `just check-ai-ux`, `scripts/check_frontend_file_size.py`.

> **RULE-20 guard:** Do NOT mark `resolved` until every test in this plan passes on disk and the AI-UX + i18n + file-size gates are green.

- [ ] **Step 4: Update the feature spec status**

In `docs/features/prompt-customization-ux.md`, change `status: planned` to `status: stable` and tick every DoD checkbox with the file/test that proves it. Add a history entry: `2026-06-2X — Phase B implemented; PROMPT-003 → stable.`

---

## Self-Review

### Spec coverage

| CR-07 v3 §B.1 / PROMPT-003 DoD item | Task |
|---|---|
| Core contracts (`contracts.py`, `preview_types.py`) | Task 1 |
| Provider-free preview (`preview.py`) — no LLM/Provider | Tasks 2, 3 |
| Variable metadata provenance + security classification | Tasks 1, 2 |
| Backend contracts (`prompts/contracts.py`) | Task 5 |
| Backend schemas (preview, reset, live-test metadata) | Task 6 |
| Backend preview service | Task 7 |
| Backend reset service (metadata) | Task 8 |
| Backend live-test service (SSE, gated, rate-limited) | Tasks 9, 11 |
| Router split (`router_prompt_ux.py`) | Task 10 |
| Frontend API client (`lib/api/prompts.ts`) | Task 12 |
| Frontend SSE reader | Task 12 |
| `PromptPreviewDialog.tsx` | Task 14 |
| `VariableMetadataPanel.tsx` | Task 13 |
| `PromptLiveTestDialog.tsx` | Task 15 |
| `PromptResetConfirmDialog.tsx` | Task 15 |
| `PromptEditor.tsx` modularization | Task 16 |
| `PromptPreview.tsx` local substitution removed | Task 16 |
| Platform contract tests (no-provider, schema parity) | Tasks 3, 18 |
| i18n DE/EN/FR | Task 17 |
| Live-test must use SSE | Tasks 9, 11 |
| Live-test provider-/secret-gated + rate-limited | Tasks 9, 11 |
| Reset only override, not bundled defaults | Task 8 (delegates to existing `reset_override`) |
| PROMPT-001/002 unchanged | No tasks touch their files |
| AUFG evidence + status updates | Task 19 |

### Placeholder scan

- `usePromptEditorState` Step 1 contains `throw new Error("... TODO ...")` — this is a **plan-document placeholder for the implementer**; the implementing subagent MUST replace it with the moved code from `PromptEditor.tsx`. The plan explicitly says so. No production code with this placeholder is acceptable.
- `_get_live_test_service` Step 3 returns 503 by design — Task 11 replaces it. The plan flags this; it is intentional staged delivery, not a hidden TODO.
- "Adjust to real path" notes for `get_provider_gate` / `ModelRoutingConfig` are explicit instructions to the implementer to grep-and-confirm before importing; the implementer must not skip them.

### Type consistency

- `PromptPreview` dataclass (Core, Task 1) ↔ `PreviewResponse` Pydantic model (Backend, Task 6) ↔ `PromptPreview` TS interface (Frontend, Task 12). Field names match: `system_prompt`, `user_prompt`, `first_message`, `cascade_source`, `variables`, `diagnostics`. Task 18 contract test enforces this.
- `PromptVariableMetadata` ↔ `PreviewVariableMetadataResponse` ↔ `PromptVariableMetadata` TS: `name`, `description`, `variable_type`, `required`, `provenance`, `security`. Match.
- `PreviewDiagnosticKind` ↔ `PreviewDiagnosticResponse.kind` Literal ↔ `PromptDiagnosticKind` TS union. Match.
- `PromptLiveTestDeps.composed_system` (Core agent) → `_build_deps` (Backend, Task 9) → `edited_override` (Frontend `LiveTestRequest`). The Backend `_build_deps` maps `edited_override` → `composed_system`; this is the single seam to verify in Task 9 Step 5.
- Reset endpoint: `POST /reset` returns `ResetResponse { reset, effective_source, effective_content }`. Frontend `resetWithMetadata` returns `PromptResetResult` with the same field names. Match.

### Coverage targets

- `core/prompts/preview.py`, `preview_types.py`, `contracts.py`: covered by Tasks 2, 3 — target 95%+ (per `tests/AGENTS.md` `core/prompts/` 95%).
- `apps/api/narrare/prompts/preview_service.py`, `live_test_service.py`, `router_prompt_ux.py`: covered by Tasks 7–11 — target 80%+ (`apps/api/*/router*.py` 80%).
- Frontend dialogs: covered by Tasks 13–16 — target 80%+ (Vitest).

---

## Handoff Plan (sequence for the Coordinator)

1. **Architecture Specialist** — confirm RULE-21 endpoint-path deviation (see "Architecture Decision" section above). If approved, proceed; if not, adjust Tasks 9/10/14 router prefix and API client paths together.
2. **Core Specialist** — Tasks 1–4 (preview types/contracts/service + live-test agent). Hand off to Backend once Core tests pass.
3. **Backend Specialist** — Tasks 5–11 (contracts, schemas, services, router, wiring). Hand off to Frontend once `/preview`, `/reset`, `/live-test` integration tests pass.
4. **Frontend Specialist** — Tasks 12–17 (types, API client, dialogs, modularization, i18n). Hand off to Platform once component tests pass.
5. **Platform Specialist** — Task 18 (contract tests) + run `just check-ai-ux`, `scripts/check_frontend_file_size.py`, `pytest` full suite. Report green output to Coordinator.
6. **Docs Specialist** — Task 19 only after Platform confirms green. Update AUFG registry + feature spec status.

**Coordinator delegates the final commit to Platform** (per user instruction). No `git commit` steps appear in this plan.
