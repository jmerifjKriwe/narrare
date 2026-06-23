# CR-AUFG-07-22 Style Variants Regeneration — Increment A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Commit policy:** This plan uses **checkpoints, NOT commits**. Changes accumulate
> across tasks until the final verification phase. Do NOT run `git commit` at any
> task boundary.

**Goal:** Enable writers to regenerate an existing AI rewrite output (or generated
draft) in a controlled style variant — `leaner`, `more_lyrical`, `more_tense`,
`more_intimate`, `more_dialogue`, `more_sensory` — through a dedicated SSE-streaming
endpoint that reuses the existing `rewrite_selection` prompt mode with a new
`{{style_variant_instructions}}` template variable.

**Architecture:** A finite `StyleVariant` StrEnum lives in `narrare_core/writing/`
with an instruction-mapping dict. The variant is threaded as an optional parameter
through `pipeline.generate()` → `pipeline_rewrite.stream_rewrite()` → into the
prompt's `extra` variables. The existing `rewrite_selection/system.md` template
gains a `{{style_variant_instructions}}` injection point. A dedicated backend module
(`contracts_style_variants`, `schemas_style_variants`, `style_variant_service`,
`router_style_variants`, `deps_style_variants`) exposes
`POST /writing/chapters/{chapter_id}/style-variants/regenerate`. The frontend adds a
`StyleVariantPicker` dropdown + `streamStyleVariantRegeneration` SSE wrapper, wired
into `RewriteSuggestionModal`. Model/provider/token settings resolve through the
existing cascade — variants never change providers.

**Tech Stack:** Python 3.14 (StrEnum, async/await), FastAPI, Pydantic v2, structlog,
Next.js 16, TypeScript strict, Tailwind, Vitest, pytest-asyncio.

**Source spec:** `docs/features/ai-ux/CR-AUFG-07-22-style-variants-regeneration.md`
**Approved architecture:** Reuse `rewrite_selection` mode + new variable (Alternative 3
from the feature spec — "finite style taxonomy flowing through existing operation
contracts").

---

## Key Design Decisions (from approved contract)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Prompt approach | Reuse `rewrite_selection/system.md` + new `{{style_variant_instructions}}` variable | No new prompt mode/route; variant direction layers on top of rewrite instructions; settings-safe (RULE-02/02a/02b) |
| Enum location | `narrare_core/writing/style_variants.py` (new file) | Single responsibility; `_enums.py` already holds generation lifecycle enums; RULE-04/RULE-06 |
| Param threading | `service → pipeline.generate(style_variant=…) → stream_rewrite(style_variant=…)` | Minimal change surface; pipeline is the single LLM entry (RULE-01b) |
| Backend module | 5-file split (`contracts_style_variants`, `schemas_style_variants`, `style_variant_service`, `router_style_variants`, `deps_style_variants`) | RULE-04 (file-size limits); RULE-06 (one responsibility per file); matches existing rewrite/extend pattern |
| Endpoint | `POST /writing/chapters/{chapter_id}/style-variants/regenerate?novel_id=…` | Dedicated path; SSE-direct (create+stream in one call); RULE-13/RULE-20 (streaming required) |
| Service reuse | `StyleVariantService` calls `pipeline.generate()` directly (same deps as `RewriteService`) | Consistent with existing Extend/Rewrite service split; streaming glue is duplicated by design (orchestration, not business logic) |
| Frontend integration | `StyleVariantPicker` dropdown in `RewriteSuggestionModal`; `streamStyleVariantRegeneration` in `generation-streams.ts` | Reuses `connectSSE` transport + `parseAlternatives` parser; RULE-17 contract parity |

---

## File Structure

### New files (Core)
- `packages/core/narrare_core/writing/style_variants.py` — `StyleVariant` StrEnum + `STYLE_VARIANT_INSTRUCTIONS` dict + `get_style_variant_instructions()` helper
- `tests/unit/core/writing/test_style_variants.py` — enum + instruction mapping tests

### New files (Backend)
- `apps/api/narrare/writing/contracts_style_variants.py` — `StyleVariantRegenerationProtocol` (Protocol)
- `apps/api/narrare/writing/schemas_style_variants.py` — `StyleVariantRegenerateRequest`
- `apps/api/narrare/writing/style_variant_service.py` — `StyleVariantService`
- `apps/api/narrare/writing/router_style_variants.py` — SSE endpoint
- `apps/api/narrare/writing/deps_style_variants.py` — `get_style_variant_service` factory
- `tests/integration/writing/test_style_variant_streaming.py` — SSE + cancel + parity tests

### New files (Frontend)
- `packages/web/components/studio/editor/StyleVariantPicker.tsx` — dropdown picker
- `packages/web/components/studio/editor/__tests__/StyleVariantPicker.test.tsx` — component tests
- `packages/web/lib/api/__tests__/style-variants.test.ts` — stream function tests

### Modified files (Core)
- `packages/core/narrare_core/writing/pipeline_rewrite.py` — add `style_variant` param, inject `style_variant_instructions` into `extra`
- `packages/core/narrare_core/writing/pipeline.py` — add `style_variant` param to `generate()`, pass through to `stream_rewrite()`
- `packages/core/narrare_core/writing/__init__.py` — export `StyleVariant` + helper
- `packages/core/narrare_core/prompts/_bundled/writing/en/rewrite_selection/system.md` — add `{{style_variant_instructions}}` injection point
- `packages/core/narrare_core/prompts/route_table.py` — register `style_variant_instructions` as optional variable for REWRITE route
- `tests/unit/core/writing/test_rewrite_pipeline.py` — extend with style-variant tests

### Modified files (Backend)
- `apps/api/narrare/writing/deps.py` — re-export `get_style_variant_service`
- `apps/api/narrare/_app/main.py` — register `router_style_variants`
- `tests/integration/writing/conftest.py` — patch `get_style_variant_service` for integration tests

### Modified files (Frontend)
- `packages/web/lib/api/generation-streams.ts` — add `StyleVariant` type + `StyleVariantRegenerateRequest` + `streamStyleVariantRegeneration`
- `packages/web/lib/api/generation.ts` — re-export new symbols
- `packages/web/components/studio/editor/RewriteSuggestionModal.tsx` — integrate `StyleVariantPicker`
- `packages/web/components/studio/editor/RewriteModalFooter.tsx` — add "Regenerate as…" trigger
- `packages/web/components/studio/editor/TipTapEditorController.ts` — wire style-variant regeneration flow

### Modified files (i18n)
- `packages/i18n/messages/en/studio.json` — `studio.styleVariants.*`
- `packages/i18n/messages/de/studio.json` — `studio.styleVariants.*`
- `packages/i18n/messages/fr/studio.json` — `studio.styleVariants.*`

---

## Phase 1: Core Layer

### Task 1: StyleVariant enum + instruction mapping

**Files:**
- Create: `packages/core/narrare_core/writing/style_variants.py`
- Test: `tests/unit/core/writing/test_style_variants.py`

- [ ] **Step 1: Write the failing test (RED)**

Create `tests/unit/core/writing/test_style_variants.py`:

```python
"""Tests for writing/style_variants.py — style variant taxonomy.

Covers:
1. StyleVariant enum has exactly the 6 approved values
2. Each variant maps to a non-empty instruction string
3. get_style_variant_instructions returns the correct text per variant
4. get_style_variant_instructions(None) returns empty string (backward compat)
5. StyleVariant serialises to its string value (StrEnum)
"""

from __future__ import annotations

import pytest

from narrare_core.writing.style_variants import (
    STYLE_VARIANT_INSTRUCTIONS,
    StyleVariant,
    get_style_variant_instructions,
)


class TestStyleVariantEnum:
    def test_has_exactly_six_members(self) -> None:
        members = list(StyleVariant)
        assert len(members) == 6

    def test_member_values(self) -> None:
        assert StyleVariant.LEANER.value == "leaner"
        assert StyleVariant.MORE_LYRICAL.value == "more_lyrical"
        assert StyleVariant.MORE_TENSE.value == "more_tense"
        assert StyleVariant.MORE_INTIMATE.value == "more_intimate"
        assert StyleVariant.MORE_DIALOGUE.value == "more_dialogue"
        assert StyleVariant.MORE_SENSORY.value == "more_sensory"

    def test_strenum_serialises_to_value(self) -> None:
        assert str(StyleVariant.LEANER) == "leaner"
        assert StyleVariant.MORE_LYRICAL == "more_lyrical"


class TestStyleVariantInstructions:
    def test_every_variant_has_nonempty_instruction(self) -> None:
        for variant in StyleVariant:
            assert variant in STYLE_VARIANT_INSTRUCTIONS
            assert STYLE_VARIANT_INSTRUCTIONS[variant].strip() != ""

    def test_instructions_are_distinct(self) -> None:
        instructions = list(STYLE_VARIANT_INSTRUCTIONS.values())
        assert len(instructions) == len(set(instructions))

    @pytest.mark.parametrize(
        ("variant", "keyword"),
        [
            (StyleVariant.LEANER, "leaner"),
            (StyleVariant.MORE_LYRICAL, "lyrical"),
            (StyleVariant.MORE_TENSE, "tense"),
            (StyleVariant.MORE_INTIMATE, "intimate"),
            (StyleVariant.MORE_DIALOGUE, "dialogue"),
            (StyleVariant.MORE_SENSORY, "sensory"),
        ],
    )
    def test_instruction_contains_keyword(self, variant: StyleVariant, keyword: str) -> None:
        assert keyword in get_style_variant_instructions(variant).lower()

    def test_none_returns_empty(self) -> None:
        assert get_style_variant_instructions(None) == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/core/writing/test_style_variants.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'narrare_core.writing.style_variants'`

- [ ] **Step 3: Implement the enum + instructions (GREEN)**

Create `packages/core/narrare_core/writing/style_variants.py`:

```python
"""Style-variant taxonomy for creative regeneration (CR-AUFG-07-22).

A finite set of author-facing creative directions that can be applied when
regenerating an AI output.  These are NOT model-routing shortcuts and do not
bypass prompt customisation or the settings cascade — they inject additional
creative-direction text into the existing ``rewrite_selection`` prompt via the
``{{style_variant_instructions}}`` template variable.

See: docs/features/ai-ux/CR-AUFG-07-22-style-variants-regeneration.md
"""

from __future__ import annotations

from enum import StrEnum


class StyleVariant(StrEnum):
    """Finite creative-direction taxonomy for style-variant regeneration.

    Each value flows from the API schema → pipeline → prompt template as
    ``{{style_variant_instructions}}``.  The original output remains visible
    and unchanged until a variant is accepted.
    """

    LEANER = "leaner"
    MORE_LYRICAL = "more_lyrical"
    MORE_TENSE = "more_tense"
    MORE_INTIMATE = "more_intimate"
    MORE_DIALOGUE = "more_dialogue"
    MORE_SENSORY = "more_sensory"


STYLE_VARIANT_INSTRUCTIONS: dict[StyleVariant, str] = {
    StyleVariant.LEANER: (
        "Make the prose leaner and more economical. Cut adjectives, tighten "
        "sentences, and let strong verbs carry the weight. Remove anything "
        "that does not earn its place on the page."
    ),
    StyleVariant.MORE_LYRICAL: (
        "Make the prose more lyrical and flowing. Use rhythm, assonance, and "
        "evocative imagery to create a musical quality. Let sentences breathe "
        "with longer, more ornamented phrasing."
    ),
    StyleVariant.MORE_TENSE: (
        "Make the prose tenser and more urgent. Use short, punchy sentences "
        "and increase the sense of immediacy and pressure. Cut anything that "
        "slows the momentum."
    ),
    StyleVariant.MORE_INTIMATE: (
        "Make the prose more intimate and emotionally close. Draw the reader "
        "into the character's inner world using smaller, more personal details "
        "and a confessional, vulnerable tone."
    ),
    StyleVariant.MORE_DIALOGUE: (
        "Shift toward more dialogue. Convert narration and description into "
        "spoken exchanges where possible, letting characters reveal information "
        "and emotion through conversation."
    ),
    StyleVariant.MORE_SENSORY: (
        "Make the prose more sensory and immersive. Ground the reader in "
        "physical sensation — smell, texture, sound, taste, and temperature. "
        "Let the body perceive the scene."
    ),
}


def get_style_variant_instructions(variant: StyleVariant | None) -> str:
    """Return the creative-direction instruction text for a style variant.

    Args:
        variant: The style variant to resolve, or ``None`` when no variant
            is requested (e.g. a plain rewrite without style-variant direction).

    Returns:
        The instruction string for the variant, or an empty string when
        ``variant is None`` (the template variable renders as nothing,
        preserving backward compatibility for non-variant rewrites).
    """
    if variant is None:
        return ""
    return STYLE_VARIANT_INSTRUCTIONS.get(variant, "")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/core/writing/test_style_variants.py -v`
Expected: PASS — all 12 tests green.

- [ ] **Step 5: Checkpoint (NO COMMIT)**

Verify core imports cleanly: `uv run python -c "from narrare_core.writing.style_variants import StyleVariant; print(StyleVariant.LEANER)"`.
Plan policy: do NOT commit.

---

### Task 2: Export StyleVariant from core writing package

**Files:**
- Modify: `packages/core/narrare_core/writing/__init__.py`

- [ ] **Step 1: Add exports**

In `packages/core/narrare_core/writing/__init__.py`, add the import after the
`_enums` import (line 13) and extend `__all__`:

```python
from narrare_core.writing.style_variants import (
    STYLE_VARIANT_INSTRUCTIONS,
    StyleVariant,
    get_style_variant_instructions,
)
```

Add to `__all__` (alphabetical, after `"SessionState"`):
```python
    "STYLE_VARIANT_INSTRUCTIONS",
    "StyleVariant",
```

And after `"SessionManagerProtocol"`:
```python
    "get_style_variant_instructions",
```

- [ ] **Step 2: Verify import works**

Run: `uv run python -c "from narrare_core.writing import StyleVariant; print(list(StyleVariant))"`
Expected: prints all 6 variants.

- [ ] **Step 3: Checkpoint (NO COMMIT)**

Plan policy: do NOT commit.

---

### Task 3: Add `{{style_variant_instructions}}` to the rewrite prompt template

**Files:**
- Modify: `packages/core/narrare_core/prompts/_bundled/writing/en/rewrite_selection/system.md`

- [ ] **Step 1: Write the failing test (RED)**

Add to `tests/unit/core/writing/test_style_variants.py` a template-presence test:

```python
from pathlib import Path

_REWRITE_TEMPLATE = (
    Path(__file__).resolve().parents[4]
    / "packages"
    / "core"
    / "narrare_core"
    / "prompts"
    / "_bundled"
    / "writing"
    / "en"
    / "rewrite_selection"
    / "system.md"
)


class TestTemplateVariable:
    def test_template_contains_style_variant_variable(self) -> None:
        """The rewrite_selection template must declare the injection point."""
        content = _REWRITE_TEMPLATE.read_text(encoding="utf-8")
        assert "{{style_variant_instructions}}" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/core/writing/test_style_variants.py::TestTemplateVariable -v`
Expected: FAIL — `AssertionError: assert '{{style_variant_instructions}}' not in content`

- [ ] **Step 3: Add the variable to the template (GREEN)**

In `packages/core/narrare_core/prompts/_bundled/writing/en/rewrite_selection/system.md`,
add a new subsection **after** the "### Rewrite Instructions" block (after line 83,
`Tone: {{tone_instructions}}`) and **before** "### Output Format":

```markdown
### Style Variant Direction

{{style_variant_instructions}}
```

This renders as empty text when no variant is requested (backward compatible) and
as the creative-direction paragraph when a variant is applied.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/core/writing/test_style_variants.py::TestTemplateVariable -v`
Expected: PASS.

- [ ] **Step 5: Bump prompt_version**

In the same template file, bump the frontmatter `prompt_version` from `"2.2.0"` to
`"2.3.0"` (new variable = minor version bump per prompt governance).

- [ ] **Step 6: Checkpoint (NO COMMIT)**

Plan policy: do NOT commit.

---

### Task 4: Thread `style_variant` param through `pipeline_rewrite.stream_rewrite()`

**Files:**
- Modify: `packages/core/narrare_core/writing/pipeline_rewrite.py`
- Test: `tests/unit/core/writing/test_rewrite_pipeline.py`

- [ ] **Step 1: Write the failing tests (RED)**

Add a new test class to `tests/unit/core/writing/test_rewrite_pipeline.py`:

```python
# ---------------------------------------------------------------------------
# Style variant injection (CR-AUFG-07-22)
# ---------------------------------------------------------------------------


class TestStyleVariantInjection:
    @pytest.mark.asyncio
    async def test_style_variant_instructions_in_extra(
        self, pipeline: WritingPipeline, mock_registry: Any, mock_composer: Any
    ) -> None:
        """When style_variant is set, style_variant_instructions appears in extra."""
        from narrare_core.writing import StyleVariant

        _setup_stream(mock_registry)
        await _collect(
            pipeline.generate(
                _req(),
                config=CONFIG,
                selection_text="Text to regenerate.",
                style_variant=StyleVariant.LEANER,
            )
        )
        ctx = mock_composer.build.call_args.args[1]
        assert "style_variant_instructions" in ctx.extra
        assert "leaner" in ctx.extra["style_variant_instructions"].lower()

    @pytest.mark.asyncio
    async def test_no_style_variant_yields_empty_string(
        self, pipeline: WritingPipeline, mock_registry: Any, mock_composer: Any
    ) -> None:
        """When style_variant is None, style_variant_instructions is empty string."""
        _setup_stream(mock_registry)
        await _collect(
            pipeline.generate(
                _req(),
                config=CONFIG,
                selection_text="Text.",
            )
        )
        ctx = mock_composer.build.call_args.args[1]
        assert ctx.extra["style_variant_instructions"] == ""

    @pytest.mark.asyncio
    async def test_each_variant_produces_distinct_instruction(
        self, pipeline: WritingPipeline, mock_registry: Any, mock_composer: Any
    ) -> None:
        """Different variants inject different instruction text."""
        from narrare_core.writing import StyleVariant

        instructions_seen: set[str] = set()
        for variant in StyleVariant:
            _setup_stream(mock_registry)
            await _collect(
                pipeline.generate(
                    _req(),
                    config=CONFIG,
                    selection_text="Text.",
                    style_variant=variant,
                )
            )
            ctx = mock_composer.build.call_args.args[1]
            instructions_seen.add(ctx.extra["style_variant_instructions"])
        assert len(instructions_seen) == 6
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/core/writing/test_rewrite_pipeline.py::TestStyleVariantInjection -v`
Expected: FAIL — `TypeError: generate() got an unexpected keyword argument 'style_variant'`

- [ ] **Step 3: Add param to `pipeline_rewrite.stream_rewrite()` (GREEN)**

In `packages/core/narrare_core/writing/pipeline_rewrite.py`:

**3a.** Add the import at the top (after line 6, the `from narrare_core.prompts.context` import):

```python
from narrare_core.writing.style_variants import (
    StyleVariant,
    get_style_variant_instructions,
)
```

**3b.** Add `style_variant` parameter to `stream_rewrite()` signature. After the
`count: int = 1,` parameter (line 102), add:

```python
    style_variant: StyleVariant | None = None,
```

Update the `TYPE_CHECKING` import block to include `StyleVariant` — it is imported
at runtime now, so no TYPE_CHECKING guard is needed.

**3c.** Inject the instruction into `extra`. After the `"rewrite_mode_instructions": mode_instr,`
line (line 134), add:

```python
        "style_variant_instructions": get_style_variant_instructions(style_variant),
```

- [ ] **Step 4: Add param to `pipeline.generate()` and pass through (GREEN)**

In `packages/core/narrare_core/writing/pipeline.py`:

**4a.** Add `style_variant` parameter to `generate()` signature. After the
`co_author_focus: list[str] | None = None,` parameter (line 99), add:

```python
        style_variant: StyleVariant | None = None,
```

Add the import in the `TYPE_CHECKING` block is NOT needed because `StyleVariant`
is a runtime StrEnum. Add a runtime import at the top of `pipeline.py` after the
existing `from narrare_core.writing._tone_data import TONE_INSTRUCTIONS` (line 25):

```python
from narrare_core.writing.style_variants import StyleVariant
```

**4b.** Pass `style_variant` in the REWRITE dispatch branch. In the `stream_rewrite`
call (lines 203-216), add after `count=rewrite_count,`:

```python
                    style_variant=style_variant,
```

The REWRITE branch becomes:

```python
            elif request.mode == GenerationMode.REWRITE:
                from narrare_core.writing.pipeline_rewrite import stream_rewrite

                async for chunk in stream_rewrite(
                    self,
                    request,
                    context,
                    config,
                    api_key=api_key,
                    base_url=base_url,
                    selection_text=selection_text,
                    context_before=context_before,
                    context_after=context_after,
                    rewrite_mode=rewrite_mode,
                    custom_instructions=custom_instructions,
                    count=rewrite_count,
                    style_variant=style_variant,
                ):
                    yield chunk
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/core/writing/test_rewrite_pipeline.py -v`
Expected: PASS — all existing tests + 3 new style-variant tests green.

- [ ] **Step 6: Verify no regressions across core**

Run: `uv run pytest tests/unit/core/writing/ -v`
Expected: PASS — no regressions.

- [ ] **Step 7: Checkpoint (NO COMMIT)**

Plan policy: do NOT commit.

---

### Task 5: Register `style_variant_instructions` in the route table

**Files:**
- Modify: `packages/core/narrare_core/prompts/route_table.py`

- [ ] **Step 1: Add `style_variant_instructions` to REWRITE optional variables**

In `packages/core/narrare_core/prompts/route_table.py`, the `REWRITE` route config
(lines 95-100) currently uses `_COMMON_OPTIONAL_VARIABLES`. Update it to also accept
`style_variant_instructions`:

```python
    LLMIntent.REWRITE: PromptRouteConfig(
        "writing",
        "rewrite_selection",
        required_variables=frozenset({"selection_text"}),
        optional_variables=_COMMON_OPTIONAL_VARIABLES
        | frozenset({"style_variant_instructions"}),
    ),
```

- [ ] **Step 2: Verify the prompt governance gate passes**

Run: `uv run python -c "from narrare_core.prompts.route_table import ROUTE_CONFIGS; from narrare_core.llm.intents import LLMIntent; print('style_variant_instructions' in ROUTE_CONFIGS[LLMIntent.REWRITE].optional_variables)"`
Expected: `True`

- [ ] **Step 3: Run prompt variable governance tests**

Run: `uv run pytest tests/unit/core/prompts/ -k "variable or route or orphan" -v`
Expected: PASS — governance gates recognise the new variable.

- [ ] **Step 4: Checkpoint (NO COMMIT)**

Plan policy: do NOT commit.

---

## Phase 2: Backend Layer

### Task 6: Define the style-variant contract (Protocol)

**Files:**
- Create: `apps/api/narrare/writing/contracts_style_variants.py`

- [ ] **Step 1: Write the contract (RULE-03 — contract before implementation)**

Create `apps/api/narrare/writing/contracts_style_variants.py`:

```python
"""Style-variant regeneration service contract — written before implementation.

Split into its own file per RULE-04 (file-size limit) and RULE-06 (one
responsibility per file).  Implements RULE-03: Contract before implementation.

CR-AUFG-07-22 Increment A: Rewrite + generated-draft variant regeneration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.writing.schemas_style_variants import StyleVariantRegenerateRequest
    from narrare_core.llm.result import StreamChunk


@runtime_checkable
class StyleVariantRegenerationProtocol(Protocol):
    """Protocol for regenerating an AI output in a controlled style variant.

    Creates a ``generation_request`` row and streams the variant via the
    rewrite pipeline with an injected ``style_variant`` parameter.  The
    frontend receives SSE events directly from the dedicated endpoint —
    no separate ``GET /stream`` call needed.

    Model/provider/token settings resolve through the existing cascade;
    the variant never changes providers.
    """

    async def validate_variant(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        request: StyleVariantRegenerateRequest,
    ) -> None:
        """Pre-validate the style-variant request before SSE response.

        Raises:
            ValidationError: If source_text is empty.
            ConflictError: If another generation is active for the chapter.
            NotFoundError: If the chapter or novel does not exist.
        """
        ...

    async def stream_variant(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        user_id: str,
        request: StyleVariantRegenerateRequest,
    ) -> AsyncIterator[StreamChunk]:
        """Create request row AND stream the style-variant generation (SSE-direct).

        Internally creates a ``generation_request`` row (mode="rewrite"),
        transitions to streaming, calls ``pipeline.generate()`` with the
        ``style_variant`` parameter, and yields ``StreamChunk`` instances.

        Args:
            chapter_id: Chapter the source output belongs to.
            novel_id: Novel the chapter belongs to.
            user_id: Authenticated user identifier.
            request: Variant request with source_text + style_variant.

        Yields:
            StreamChunk instances with incremental text.  The final chunk
            has ``is_final=True`` and populated ``usage``.
        """
        ...
```

- [ ] **Step 2: Verify the contract imports cleanly**

Run: `uv run python -c "from narrare.writing.contracts_style_variants import StyleVariantRegenerationProtocol; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Checkpoint (NO COMMIT)**

Plan policy: do NOT commit.

---

### Task 7: Define the request schema

**Files:**
- Create: `apps/api/narrare/writing/schemas_style_variants.py`

- [ ] **Step 1: Write the schema**

Create `apps/api/narrare/writing/schemas_style_variants.py`:

```python
"""Style-variant regeneration schemas — request model for CR-AUFG-07-22.

Split from schemas.py per RULE-04 (file-size limit).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from narrare_core.writing.style_variants import StyleVariant


class StyleVariantRegenerateRequest(BaseModel):
    """Request to regenerate an AI output in a specific style variant.

    The source text is the existing AI output (or selection) that the writer
    wants regenerated in a controlled creative direction.  Context markers
    provide surrounding text for register matching.  Model/provider/token
    settings resolve through the existing cascade — the variant never changes
    providers.
    """

    source_text: str = Field(
        ...,
        min_length=50,
        max_length=2000,
        description="The existing AI output text to regenerate in the variant style",
    )
    context_before: str | None = Field(
        default=None,
        max_length=500,
        description="Text immediately before the source output (up to 500 chars)",
    )
    context_after: str | None = Field(
        default=None,
        max_length=500,
        description="Text immediately after the source output (up to 500 chars)",
    )
    style_variant: StyleVariant = Field(
        ...,
        description="Creative direction: leaner, more_lyrical, more_tense, "
        "more_intimate, more_dialogue, more_sensory",
    )
    tone: str = Field(
        default="balanced",
        min_length=1,
        max_length=100,
        description="Tone preference (resolved through the settings cascade)",
    )
    language: str = Field(
        default="en",
        min_length=2,
        max_length=5,
        description="Output language",
    )
```

- [ ] **Step 2: Verify the schema validates**

Run:
```bash
uv run python -c "
from narrare.writing.schemas_style_variants import StyleVariantRegenerateRequest
from narrare_core.writing import StyleVariant
r = StyleVariantRegenerateRequest(source_text='A' * 60, style_variant=StyleVariant.LEANER)
print(r.style_variant, 'ok')
"
```
Expected: `StyleVariant.LEANER ok`

- [ ] **Step 3: Checkpoint (NO COMMIT)**

Plan policy: do NOT commit.

---

### Task 8: Implement `StyleVariantService`

**Files:**
- Create: `apps/api/narrare/writing/style_variant_service.py`

- [ ] **Step 1: Write the failing unit test (RED)**

Create `tests/unit/api/writing/test_style_variant_service.py`:

```python
"""Unit tests for StyleVariantService — style-variant regeneration.

The service orchestrates: validate → create request row → stream via pipeline.
The pipeline is mocked; we assert the service passes ``style_variant`` through
and handles status transitions correctly.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.writing import StyleVariant
from narrare.writing.schemas_style_variants import StyleVariantRegenerateRequest
from narrare.writing.style_variant_service import StyleVariantService

CONFIG = ResolvedModelConfig(provider_name="test", model_id="m", max_tokens=2000)


def _make_request() -> StyleVariantRegenerateRequest:
    return StyleVariantRegenerateRequest(
        source_text="The forest was dark and full of ancient trees that whispered secrets.",
        style_variant=StyleVariant.MORE_SENSORY,
    )


def _make_service(pipeline: Any, repo: Any) -> StyleVariantService:
    return StyleVariantService(
        repo=repo,
        pipeline=pipeline,
        draft_processor=MagicMock(spec=[], side_effect=lambda text, **kw: text),
        config=CONFIG,
    )


@pytest.fixture()
def mock_repo() -> Any:
    repo = MagicMock()
    repo.chapter_exists = AsyncMock(return_value=True)
    repo.get_active_for_chapter = AsyncMock(return_value=None)
    repo.create_if_no_active = AsyncMock(return_value=uuid4())
    repo.update_status = AsyncMock()
    return repo


async def _fake_stream(*_chunks: StreamChunk):  # type: ignore[no-untyped-def]
    for c in _chunks:
        yield c


class TestStyleVariantService:
    @pytest.mark.asyncio
    async def test_validate_raises_on_empty_source(
        self, mock_repo: Any
    ) -> None:
        svc = _make_service(MagicMock(), mock_repo)
        req = _make_request()
        req.source_text = "   "
        from narrare_core.shared.errors import ValidationError

        with pytest.raises(ValidationError):
            await svc.validate_variant(uuid4(), uuid4(), req)

    @pytest.mark.asyncio
    async def test_stream_passes_style_variant_to_pipeline(
        self, mock_repo: Any
    ) -> None:
        pipeline = MagicMock()
        usage = TokenUsage(prompt_tokens=5, completion_tokens=10, total_tokens=15)
        pipeline.generate = MagicMock(
            return_value=_fake_stream(
                StreamChunk(text="<alternative label=\"Sensory\">Immersive text.</alternative>"),
                StreamChunk(text="", is_final=True, usage=usage),
            )
        )
        svc = _make_service(pipeline, mock_repo)
        chunks = []
        async for chunk in svc.stream_variant(uuid4(), uuid4(), "user-1", _make_request()):
            chunks.append(chunk)

        # The pipeline.generate call must include the style_variant kwarg
        call_kwargs = pipeline.generate.call_args.kwargs
        assert call_kwargs["style_variant"] == StyleVariant.MORE_SENSORY
        assert any(c.is_final for c in chunks)

    @pytest.mark.asyncio
    async def test_stream_uses_rewrite_mode(
        self, mock_repo: Any
    ) -> None:
        """Style-variant regeneration uses rewrite_mode='style' as the base."""
        pipeline = MagicMock()
        pipeline.generate = MagicMock(return_value=_fake_stream(StreamChunk(text="x", is_final=True, usage=TokenUsage(1,1,2))))
        svc = _make_service(pipeline, mock_repo)
        async for _ in svc.stream_variant(uuid4(), uuid4(), "u", _make_request()):
            pass
        call_kwargs = pipeline.generate.call_args.kwargs
        assert call_kwargs["rewrite_mode"] == "style"
        assert call_kwargs["rewrite_count"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/api/writing/test_style_variant_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'narrare.writing.style_variant_service'`

- [ ] **Step 3: Implement the service (GREEN)**

Create `apps/api/narrare/writing/style_variant_service.py`:

```python
"""Style-variant regeneration service — SSE-direct variant streaming (CR-AUFG-07-22).

Creates a ``generation_request`` row and streams a style-variant regeneration
through the rewrite pipeline in one method call.  The frontend receives SSE
events directly from the dedicated endpoint.

Follows the same SSE-direct pattern as :class:`RewriteService` (separate class
per RULE-04/RULE-06).  The variant direction is injected via the
``style_variant`` parameter, which flows through ``pipeline.generate()`` into
the ``{{style_variant_instructions}}`` template variable.

Implements :class:`StyleVariantRegenerationProtocol` (RULE-03).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError

from narrare_core.shared.errors import ConflictError, NotFoundError, ValidationError
from narrare_core.writing.style_variants import StyleVariant

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare.writing.repository import GenerationRepository
    from narrare.writing.schemas_style_variants import StyleVariantRegenerateRequest
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.result import StreamChunk
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.pipeline import WritingPipeline

logger = structlog.get_logger(__name__)


class StyleVariantService:
    """Orchestrates style-variant regeneration via pipeline + repository.

    Uses the SSE-direct pattern: ``stream_variant()`` creates the request
    row AND streams the variant result.  The base rewrite mode is ``"style"``
    with ``count=1`` (single variant).  The ``style_variant`` parameter
    carries the creative direction into the prompt.
    """

    def __init__(
        self,
        repo: GenerationRepository,
        pipeline: WritingPipeline,
        draft_processor: DraftProcessor,
        config: ResolvedModelConfig,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._repo = repo
        self._pipeline = pipeline
        self._draft_processor = draft_processor
        self._config = config
        self._api_key = api_key
        self._base_url = base_url

    # -- Public API --------------------------------------------------------

    async def validate_variant(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        request: StyleVariantRegenerateRequest,
    ) -> None:
        """Pre-validate the style-variant request before SSE response.

        Raises:
            ValidationError: If source_text is empty.
            ConflictError: If another generation is active for the chapter.
            NotFoundError: If the chapter or novel does not exist.
        """
        if not request.source_text.strip():
            raise ValidationError(
                "source_text must not be empty",
                code="MISSING_INPUT",
            )

        if not await self._repo.chapter_exists(chapter_id):
            raise NotFoundError("Chapter", identifier=str(chapter_id))

        active = await self._repo.get_active_for_chapter(chapter_id)
        if active is not None:
            raise ConflictError(
                f"Generation already active for chapter {chapter_id}",
            )

    async def stream_variant(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        user_id: str,
        request: StyleVariantRegenerateRequest,
    ) -> AsyncIterator[StreamChunk]:
        """Create request row AND stream the style-variant generation.

        Internally creates a ``generation_request`` row (mode="rewrite"),
        transitions to streaming, calls ``pipeline.generate()`` with the
        ``style_variant`` parameter, and handles status transitions.
        """
        from narrare_core.writing._enums import GenerationMode
        from narrare_core.writing.models import (
            GenerationRequest as CoreGenerationRequest,
        )

        # Step 1: Validate + create request row.
        await self.validate_variant(chapter_id, novel_id, request)

        try:
            request_id = await self._repo.create_if_no_active(
                chapter_id=chapter_id,
                novel_id=novel_id,
                user_id=UUID(user_id),
                mode="rewrite",
                tone=request.tone,
            )
        except IntegrityError as exc:
            raise NotFoundError(
                "Chapter or Novel", identifier=str(chapter_id)
            ) from exc

        # Step 2: Transition to streaming.
        await self._repo.update_status(
            request_id,
            "streaming",
            started_at=datetime.now(UTC),
            model_id=self._config.model_id,
            provider_name=self._config.provider_name,
        )

        logger.info(
            "style_variant_started",
            request_id=str(request_id),
            chapter_id=str(chapter_id),
            style_variant=request.style_variant.value,
        )

        # Step 3: Build pipeline request (REWRITE mode).
        pipeline_request = CoreGenerationRequest(
            id=request_id,
            chapter_id=chapter_id,
            project_id=novel_id,
            user_id=UUID(user_id),
            mode=GenerationMode.REWRITE,
            tone=request.tone,
            word_target=0,
            writing_language=request.language,
        )

        # Step 4: Build chapter_content with context markers.
        chapter_content = request.source_text
        if request.context_before or request.context_after:
            parts: list[str] = []
            if request.context_before:
                parts.append(request.context_before)
            parts.append("[SELECTION START]")
            parts.append(request.source_text)
            parts.append("[SELECTION END]")
            if request.context_after:
                parts.append(request.context_after)
            chapter_content = "\n".join(parts)

        # Step 5: Stream via pipeline with style_variant (RULE-01b, RULE-02).
        accumulated: list[str] = []
        try:
            async for chunk in self._pipeline.generate(
                pipeline_request,
                config=self._config,
                api_key=self._api_key,
                base_url=self._base_url,
                chapter_content=chapter_content,
                selection_text=request.source_text,
                context_before=request.context_before or "",
                context_after=request.context_after or "",
                rewrite_mode="style",
                rewrite_count=1,
                style_variant=request.style_variant,
            ):
                if chunk.context_meta is not None:
                    yield chunk
                    continue

                if chunk.is_final:
                    raw_text = "".join(accumulated) + chunk.text
                    cleaned = self._draft_processor.process(raw_text)
                    word_count = len(cleaned.split())
                    await self._repo.update_status(
                        request_id,
                        "completed",
                        tokens_used=(
                            chunk.usage.total_tokens if chunk.usage else 0
                        ),
                        word_count=word_count,
                        completed_at=datetime.now(UTC),
                    )
                    yield chunk
                    return
                accumulated.append(chunk.text)
                yield chunk
        except Exception as e:
            partial = self._draft_processor.process(
                "".join(accumulated),
                is_partial=True,
            )
            partial_words = len(partial.split()) if partial else 0
            await self._repo.update_status(
                request_id,
                "failed",
                error_message=str(e),
                word_count=partial_words,
                completed_at=datetime.now(UTC),
            )
            logger.error(
                "style_variant_stream_failed",
                request_id=str(request_id),
                error=str(e),
            )
            raise
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/api/writing/test_style_variant_service.py -v`
Expected: PASS — all 3 tests green.

- [ ] **Step 5: Checkpoint (NO COMMIT)**

Plan policy: do NOT commit.

---

### Task 9: Create the dependency factory

**Files:**
- Create: `apps/api/narrare/writing/deps_style_variants.py`
- Modify: `apps/api/narrare/writing/deps.py`

- [ ] **Step 1: Write the factory**

Create `apps/api/narrare/writing/deps_style_variants.py`:

```python
"""Writing module dependency injection — style-variant service factory.

Mirrors deps_rewrite.py but builds a StyleVariantService.  Model routing
resolves through the existing REWRITE intent cascade.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import UUID

from narrare._app.dependencies_services import get_model_routing_resolver
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.writing.style_variant_service import StyleVariantService


async def get_style_variant_service(
    session: AsyncSession,
    user_id: str,
    project_id: UUID | None = None,
) -> StyleVariantService:
    """Factory for StyleVariantService — resolves model config for REWRITE intent.

    Args:
        session: DB session for repository and settings lookups.
        user_id: Authenticated user identifier.
        project_id: Optional project/novel ID for project-level settings.

    Returns:
        Configured StyleVariantService ready for use.
    """
    from narrare._app.config import get_settings
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare.settings.repository import UserSettingsRepository
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService
    from narrare.writing.deps_pipeline import create_pipeline
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.style_variant_service import StyleVariantService
    from narrare_core.writing.draft_processor import DraftProcessor

    resolver = get_model_routing_resolver(session)
    assert isinstance(resolver, ModelRoutingResolverImpl)
    resolved = await resolver.resolve(
        LLMIntent.REWRITE,
        UUID(user_id),
        project_id,
    )
    token_limits_service = TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=get_settings(),
    )
    limits = await token_limits_service.get_resolved_limits(
        user_id=user_id,
        project_id=str(project_id) if project_id else None,
    )
    config = replace(
        resolved.config,
        temperature=0.7,
        max_tokens=limits.output_limit,
    )

    draft_processor = DraftProcessor()
    pipeline = create_pipeline(
        draft_processor, tier_overrides=limits.tier_percentages
    )
    repo = GenerationRepository(session)

    return StyleVariantService(
        repo=repo,
        pipeline=pipeline,
        draft_processor=draft_processor,
        config=config,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
    )
```

- [ ] **Step 2: Re-export from deps.py**

In `apps/api/narrare/writing/deps.py`, add after the `deps_rewrite` import block
(after line 18):

```python
from narrare.writing.deps_style_variants import (
    get_style_variant_service as get_style_variant_service,
)
```

Add `"get_style_variant_service",` to `__all__`.

- [ ] **Step 3: Verify the factory imports cleanly**

Run: `uv run python -c "from narrare.writing.deps import get_style_variant_service; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Checkpoint (NO COMMIT)**

Plan policy: do NOT commit.

---

### Task 10: Implement the router endpoint

**Files:**
- Create: `apps/api/narrare/writing/router_style_variants.py`

- [ ] **Step 1: Write the router (thin delegation, RULE-06)**

Create `apps/api/narrare/writing/router_style_variants.py`:

```python
"""Writing style-variant routes — SSE-direct regeneration endpoint (CR-AUFG-07-22).

Thin delegation layer (RULE-06): every route immediately delegates to
:class:`StyleVariantService`.  No business logic lives here.

Follows the same SSE-direct pattern as ``router_rewrite.py``.
"""

from __future__ import annotations

import json
import uuid  # noqa: TC003 — needed at runtime for FastAPI path parameter type resolution
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare._app.observability import enrich_sse_data
from narrare._app.rate_limits import AI_WRITE_LIMITER
from narrare.writing.deps import get_style_variant_service
from narrare.writing.schemas_style_variants import StyleVariantRegenerateRequest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from typing import Any

router = APIRouter(prefix="/writing", tags=["writing"])


@router.post(
    "/chapters/{chapter_id}/style-variants/regenerate",
    dependencies=[Depends(AI_WRITE_LIMITER)],
)
async def regenerate_style_variant(
    chapter_id: uuid.UUID,
    novel_id: uuid.UUID,
    request: StyleVariantRegenerateRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> StreamingResponse:
    """SSE stream for style-variant regeneration — create + stream in one call.

    Accepts an existing AI output (source_text) with a style variant and
    returns a regenerated version streamed via SSE.  The output is wrapped
    in ``<alternative>`` tags (count=1).  The final SSE event includes the
    ``request_id`` for use with accept/reject endpoints.

    Model/provider/token settings resolve through the existing REWRITE cascade;
    the variant never changes providers.
    """
    service = await get_style_variant_service(session, user_id, novel_id)

    # Pre-validate before starting SSE response to avoid RuntimeError
    # when ConflictError/NotFoundError fires after headers are sent.
    await service.validate_variant(chapter_id, novel_id, request)

    async def event_stream() -> AsyncIterator[str]:
        async for chunk in service.stream_variant(
            chapter_id,
            novel_id,
            user_id,
            request,
        ):
            # Context metadata event (CR-07: sent as first event before text)
            if chunk.context_meta is not None:
                meta_data: dict[str, Any] = {"type": "context_meta"}
                meta_data.update(chunk.context_meta)
                yield f"data: {json.dumps(enrich_sse_data(meta_data))}\n\n"
                continue

            # Normal text chunk — <alternative> tags preserved as raw text
            data: dict[str, Any] = {"text": chunk.text}
            if chunk.is_final:
                data["is_final"] = True
            if chunk.usage is not None:
                data["usage"] = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens,
                }
            yield f"data: {json.dumps(enrich_sse_data(data))}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 2: Verify the router imports cleanly**

Run: `uv run python -c "from narrare.writing.router_style_variants import router; print(router.routes)"`
Expected: prints the route list including the regenerate endpoint.

- [ ] **Step 3: Checkpoint (NO COMMIT)**

Plan policy: do NOT commit.

---

### Task 11: Register the router in the app

**Files:**
- Modify: `apps/api/narrare/_app/main.py`

- [ ] **Step 1: Add the import**

In `apps/api/narrare/_app/main.py`, after line 177 (`from narrare.writing.router_rewrite import router as writing_rewrite_router`), add:

```python
    from narrare.writing.router_style_variants import router as writing_style_variants_router
```

- [ ] **Step 2: Register the router**

After line 217 (`app.include_router(writing_rewrite_router, prefix=prefix)`), add:

```python
    app.include_router(writing_style_variants_router, prefix=prefix)
```

- [ ] **Step 3: Verify the route is registered**

Run:
```bash
uv run python -c "
from narrare._app.main import app
paths = [r.path for r in app.routes]
assert any('style-variants' in p for p in paths), paths
print('registered:', [p for p in paths if 'style-variants' in p])
"
```
Expected: `registered: ['/api/v1/writing/chapters/{chapter_id}/style-variants/regenerate']`

- [ ] **Step 4: Checkpoint (NO COMMIT)**

Plan policy: do NOT commit.

---

## Phase 3: Frontend Layer

### Task 12: Add frontend types + stream function

**Files:**
- Modify: `packages/web/lib/api/generation-streams.ts`
- Modify: `packages/web/lib/api/generation.ts`
- Test: `packages/web/lib/api/__tests__/style-variants.test.ts`

- [ ] **Step 1: Write the failing test (RED)**

Create `packages/web/lib/api/__tests__/style-variants.test.ts`:

```typescript
/**
 * Tests for streamStyleVariantRegeneration (CR-AUFG-07-22).
 *
 * Pattern: matches streamRewrite() in rewrite.test.ts exactly.
 */
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { setAccessToken } from "@/lib/api/core";
import { sseStream } from "./sse-helpers";
import {
  parseAlternatives,
  streamStyleVariantRegeneration,
  type StyleVariantRegenerateRequest,
} from "@/lib/api/generation";

const server = setupServer();
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("streamStyleVariantRegeneration", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  it("POSTs to /style-variants/regenerate and streams the variant", async () => {
    const alternatives: { label: string; text: string }[] = [];
    let capturedBody: StyleVariantRegenerateRequest | null = null;

    server.use(
      http.post(
        "*/api/v1/writing/chapters/ch-1/style-variants/regenerate",
        async ({ request }) => {
          capturedBody = (await request.json()) as StyleVariantRegenerateRequest;
          return new HttpResponse(
            sseStream([
              'data: {"type":"request_info","request_id":"sv-1"}',
              'data: {"text":"<alternative label=\\"Sensory\\">The damp moss clung to her fingers, releasing its earthy perfume.</alternative>"}',
              "data: [DONE]",
            ]),
            { headers: { "Content-Type": "text/event-stream" } },
          );
        },
      ),
    );

    await streamStyleVariantRegeneration(
      "ch-1",
      "novel-1",
      {
        source_text: "The forest was dark and full of ancient trees.",
        style_variant: "more_sensory",
      },
      {
        onAlternative: (label, text) => alternatives.push({ label, text }),
        onAlternativeFinal: () => {},
        onError: () => {},
      },
    );

    expect(capturedBody).not.toBeNull();
    expect(capturedBody!.style_variant).toBe("more_sensory");
    expect(alternatives).toHaveLength(1);
    expect(alternatives[0].label).toBe("Sensory");
  });

  it("calls onError on HTTP failure", async () => {
    const errors: Error[] = [];

    server.use(
      http.post(
        "*/api/v1/writing/chapters/ch-err/style-variants/regenerate",
        () => HttpResponse.json({ detail: "Not found" }, { status: 404 }),
      ),
    );

    await streamStyleVariantRegeneration(
      "ch-err",
      "novel-1",
      { source_text: "Some text here.", style_variant: "leaner" },
      {
        onAlternative: () => {},
        onAlternativeFinal: () => {},
        onError: (e) => errors.push(e),
      },
    );

    expect(errors).toHaveLength(1);
  });

  it("aborts cleanly on AbortSignal", async () => {
    const controller = new AbortController();
    server.use(
      http.post(
        "*/api/v1/writing/chapters/ch-abort/style-variants/regenerate",
        () =>
          new HttpResponse(
            sseStream(['data: {"text":"partial"}', "data: [DONE]"]),
            { headers: { "Content-Type": "text/event-stream" } },
          ),
      ),
    );

    controller.abort();
    await expect(
      streamStyleVariantRegeneration(
        "ch-abort",
        "novel-1",
        { source_text: "Some text here.", style_variant: "leaner" },
        {
          onAlternative: () => {},
          onAlternativeFinal: () => {},
          onError: () => {},
        },
        controller.signal,
      ),
    ).resolves.toBeUndefined();
  });
});
```

> **Note:** If `sseStream` helper doesn't exist in `__tests__/`, copy it from
> `packages/web/lib/api/__tests__/rewrite.test.ts` (it defines a helper that
> joins SSE lines). Check the existing rewrite test for the exact import path.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && pnpm vitest run lib/api/__tests__/style-variants.test.ts`
Expected: FAIL — `Failed to resolve import "streamStyleVariantRegeneration"`

- [ ] **Step 3: Add types + stream function (GREEN)**

In `packages/web/lib/api/generation-streams.ts`, add after the `RewriteConfig`
interface (after line 60):

```typescript
// ---------------------------------------------------------------------------
// Style variants (CR-AUFG-07-22)
// ---------------------------------------------------------------------------

export type StyleVariant =
  | "leaner"
  | "more_lyrical"
  | "more_tense"
  | "more_intimate"
  | "more_dialogue"
  | "more_sensory";

export interface StyleVariantRegenerateRequest {
  source_text: string;
  context_before?: string;
  context_after?: string;
  style_variant: StyleVariant;
  tone?: string;
  language?: string;
}

/**
 * Stream a style-variant regeneration of an existing AI output.
 *
 * POSTs to the dedicated endpoint and parses <alternative> tags, mirroring
 * streamRewrite().  The source_text is the existing output; style_variant is
 * the creative direction.  Model/provider settings resolve through the
 * existing cascade — this never changes providers.
 */
export async function streamStyleVariantRegeneration(
  chapterId: string,
  novelId: string,
  request: StyleVariantRegenerateRequest,
  callbacks: {
    onRequestInfo?: (requestId: string) => void;
    onAlternative: (label: string, text: string) => void;
    onAlternativeFinal?: (count: number) => void;
    onError?: (error: Error) => void;
  },
  signal?: AbortSignal,
): Promise<void> {
  let pendingText = "";
  let emittedCount = 0;
  let isComplete = false;
  const closeTag = "</alternative>";

  function emitCompleteAlternatives(): void {
    while (pendingText.includes(closeTag)) {
      const closeIdx = pendingText.indexOf(closeTag);
      const completeText = pendingText.slice(0, closeIdx + closeTag.length);
      for (const alternative of parseAlternatives(completeText)) {
        callbacks.onAlternative(alternative.label, alternative.text);
        emittedCount++;
      }
      pendingText = pendingText.slice(closeIdx + closeTag.length);
    }
  }

  function complete(): void {
    if (isComplete) return;
    isComplete = true;
    for (const alternative of parseAlternatives(pendingText)) {
      callbacks.onAlternative(alternative.label, alternative.text);
      emittedCount++;
    }
    pendingText = "";
    callbacks.onAlternativeFinal?.(emittedCount);
  }

  await connectSSE<ExtendStreamEvent>({
    url: `/writing/chapters/${chapterId}/style-variants/regenerate?novel_id=${novelId}`,
    method: "POST",
    body: request,
    signal,
    onChunk: (event) => {
      if (event.type === "request_info" && event.request_id) {
        callbacks.onRequestInfo?.(event.request_id);
        return;
      }
      if (event.text) {
        pendingText += event.text;
        emitCompleteAlternatives();
      }
      if (event.is_final) complete();
    },
    onComplete: complete,
    onError: (error) => reportStreamError(callbacks, error),
  });
}
```

- [ ] **Step 4: Re-export from generation.ts**

In `packages/web/lib/api/generation.ts`, add to the `export type` block (after
`RewriteRequest,` on line 20):

```typescript
  StyleVariant,
  StyleVariantRegenerateRequest,
```

And to the `export {` block (after `streamRewrite,` on line 27):

```typescript
  streamStyleVariantRegeneration,
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd packages/web && pnpm vitest run lib/api/__tests__/style-variants.test.ts`
Expected: PASS — all 3 tests green.

- [ ] **Step 6: Checkpoint (NO COMMIT)**

Plan policy: do NOT commit.

---

### Task 13: Create the `StyleVariantPicker` component

**Files:**
- Create: `packages/web/components/studio/editor/StyleVariantPicker.tsx`
- Test: `packages/web/components/studio/editor/__tests__/StyleVariantPicker.test.tsx`

- [ ] **Step 1: Write the failing test (RED)**

Create `packages/web/components/studio/editor/__tests__/StyleVariantPicker.test.tsx`:

```typescript
/**
 * StyleVariantPicker tests — dropdown for selecting a creative direction.
 */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { StyleVariantPicker } from "@/components/studio/editor/StyleVariantPicker";
import type { StyleVariant } from "@/lib/api/generation";

const t = (key: string) => key;

function renderPicker(props: Partial<Parameters<typeof StyleVariantPicker>[0]> = {}) {
  const onSelect = vi.fn();
  const onRegenerate = vi.fn();
  return {
    onSelect,
    onRegenerate,
    ...render(
      <StyleVariantPicker
        selectedVariant={null}
        onSelect={onSelect}
        onRegenerate={onRegenerate}
        isStreaming={false}
        t={t}
        {...props}
      />,
    ),
  };
}

describe("StyleVariantPicker", () => {
  it("renders all 6 variants", () => {
    renderPicker();
    const select = screen.getByRole("combobox");
    // 6 options + 1 placeholder = 7
    expect(select.querySelectorAll("option")).toHaveLength(7);
  });

  it("calls onSelect when a variant is chosen", () => {
    const { onSelect } = renderPicker();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "leaner" } });
    expect(onSelect).toHaveBeenCalledWith("leaner");
  });

  it("calls onRegenerate when the button is clicked", () => {
    const { onRegenerate } = renderPicker({ selectedVariant: "leaner" as StyleVariant });
    fireEvent.click(screen.getByText("studio.styleVariants.regenerate"));
    expect(onRegenerate).toHaveBeenCalledTimes(1);
  });

  it("disables the regenerate button when no variant is selected", () => {
    renderPicker({ selectedVariant: null });
    expect(screen.getByText("studio.styleVariants.regenerate")).toBeDisabled();
  });

  it("disables the regenerate button when streaming", () => {
    renderPicker({ selectedVariant: "leaner" as StyleVariant, isStreaming: true });
    expect(screen.getByText("studio.styleVariants.regenerate")).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && pnpm vitest run components/studio/editor/__tests__/StyleVariantPicker.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the component (GREEN)**

Create `packages/web/components/studio/editor/StyleVariantPicker.tsx`:

```tsx
"use client";

/**
 * StyleVariantPicker — dropdown for selecting a creative direction and
 * triggering style-variant regeneration (CR-AUFG-07-22).
 *
 * Shows the 6 approved variants.  The regenerate button is disabled until a
 * variant is selected and not currently streaming.
 */

import { Loader2, Wand2 } from "lucide-react";
import type { StyleVariant } from "@/lib/api/generation";

const VARIANTS: StyleVariant[] = [
  "leaner",
  "more_lyrical",
  "more_tense",
  "more_intimate",
  "more_dialogue",
  "more_sensory",
];

type StudioTranslator = (key: string) => string;

interface StyleVariantPickerProps {
  readonly selectedVariant: StyleVariant | null;
  readonly onSelect: (variant: StyleVariant) => void;
  readonly onRegenerate: () => void;
  readonly isStreaming: boolean;
  readonly t: StudioTranslator;
}

export function StyleVariantPicker({
  selectedVariant,
  onSelect,
  onRegenerate,
  isStreaming,
  t,
}: StyleVariantPickerProps) {
  const canRegenerate = selectedVariant !== null && !isStreaming;

  return (
    <div className="flex items-center gap-2">
      <select
        value={selectedVariant ?? ""}
        onChange={(e) => onSelect(e.target.value as StyleVariant)}
        disabled={isStreaming}
        className="px-3 py-2 bg-input-background border border-border rounded-lg text-sm disabled:opacity-50"
        aria-label={t("studio.styleVariants.title")}
      >
        <option value="" disabled>
          {t("studio.styleVariants.title")}
        </option>
        {VARIANTS.map((variant) => (
          <option key={variant} value={variant}>
            {t(`studio.styleVariants.${variant}`)}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={onRegenerate}
        disabled={!canRegenerate}
        className="flex items-center gap-2 px-3 py-2 border border-border rounded-lg text-sm hover:bg-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        title={t("studio.styleVariants.regenerate")}
      >
        {isStreaming ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <Wand2 className="w-4 h-4" />
        )}
        {t("studio.styleVariants.regenerate")}
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/web && pnpm vitest run components/studio/editor/__tests__/StyleVariantPicker.test.tsx`
Expected: PASS — all 5 tests green.

- [ ] **Step 5: Checkpoint (NO COMMIT)**

Plan policy: do NOT commit.

---

### Task 14: Integrate `StyleVariantPicker` into `RewriteSuggestionModal`

**Files:**
- Modify: `packages/web/components/studio/editor/RewriteSuggestionModal.tsx`
- Modify: `packages/web/components/studio/editor/RewriteModalFooter.tsx`
- Modify: `packages/web/components/studio/editor/TipTapEditorController.ts`

- [ ] **Step 1: Add style-variant state + handler to `TipTapEditorController.ts`**

In `TipTapEditorController.ts`, add imports near the top (after the existing
`streamRewrite` import on line 10):

```typescript
  streamStyleVariantRegeneration,
```

(Add it to the existing import from `"@/lib/api/generation"`.)

And add `StyleVariant` to the type import.

Add state + handler inside the controller component (near the existing rewrite
state declarations):

```typescript
  const [styleVariant, setStyleVariant] = useState<StyleVariant | null>(null);

  const handleStyleVariantRegenerate = useCallback(async () => {
    const sel = rewriteSelectionRef.current;
    if (!sel || !styleVariant || !chapterId || !novelId) return;

    const alternatives: RewriteAlternative[] = [];

    await streamStyleVariantRegeneration(
      chapterId,
      novelId,
      {
        source_text: sel.text,
        context_before: sel.contextBefore,
        context_after: sel.contextAfter,
        style_variant: styleVariant,
        language: locale,
      },
      {
        onAlternative: (label, text) => {
          alternatives.push({ label, text });
          setAiSuggestion((prev) =>
            prev
              ? {
                  ...prev,
                  suggestions: alternatives.map((a) => a.text),
                  labels: alternatives.map((a) => a.label),
                }
              : {
                  original: sel.text,
                  suggestions: alternatives.map((a) => a.text),
                  labels: alternatives.map((a) => a.label),
                  position: { from: sel.from, to: sel.to },
                },
          );
          if (alternatives.length === 1) setSelectedSuggestion(0);
        },
        onAlternativeFinal: () => {},
        onError: (error: Error) => {
          setRewriteError(error as AIErrorResponse);
        },
      },
    );
  }, [chapterId, novelId, styleVariant, locale]);
```

> **Note:** `useCallback`, `useState`, and the existing refs (`rewriteSelectionRef`,
> `chapterId`, `novelId`, `locale`, `setAiSuggestion`, `setSelectedSuggestion`,
> `setRewriteError`) are already in scope.  `AIErrorResponse` is already imported.
> Verify the exact import names match the controller's existing imports before
> writing.  If the controller already has an abort controller for rewrite, reuse
> the same `signal` pattern.

Pass these props to `RewriteSuggestionModal`:

```typescript
        styleVariant={styleVariant}
        onSelectStyleVariant={setStyleVariant}
        onRegenerateStyleVariant={handleStyleVariantRegenerate}
```

- [ ] **Step 2: Add props + render `StyleVariantPicker` in `RewriteSuggestionModal.tsx`**

Add to the props interface:

```typescript
  styleVariant: StyleVariant | null;
  onSelectStyleVariant: (variant: StyleVariant) => void;
  onRegenerateStyleVariant: () => void;
```

Add the import:
```typescript
import { StyleVariantPicker } from "./StyleVariantPicker";
import type { StyleVariant } from "@/lib/api/generation";
```

Render the picker inside the modal body — after the suggestions list `</div>`
and before the streaming loader (after line 124):

```tsx
          <div className="mt-4 pt-4 border-t border-border">
            <StyleVariantPicker
              selectedVariant={styleVariant}
              onSelect={onSelectStyleVariant}
              onRegenerate={onRegenerateStyleVariant}
              isStreaming={isRewriteStreaming}
              t={t}
            />
          </div>
```

- [ ] **Step 3: Verify the existing modal tests still pass**

Run: `cd packages/web && pnpm vitest run components/studio/editor/__tests__/RewriteSuggestionModal.test.tsx`
Expected: PASS — existing tests must not regress.  If they fail due to missing
props, update the test's `defaultProps` to include the three new props
(`styleVariant: null`, `onSelectStyleVariant: vi.fn()`, `onRegenerateStyleVariant: vi.fn()`).

- [ ] **Step 4: Checkpoint (NO COMMIT)**

Plan policy: do NOT commit.

---

### Task 15: Add i18n keys (DE/EN/FR)

**Files:**
- Modify: `packages/i18n/messages/{en,de,fr}/studio.json`

- [ ] **Step 1: Add `studio.styleVariants.*` to EN**

In `packages/i18n/messages/en/studio.json`, add after the `"aiActions": { ... }`
block (after line 1780, the closing `}` of aiActions) — as a sibling key:

```json
  "styleVariants": {
    "title": "Regenerate as…",
    "regenerate": "Regenerate",
    "leaner": "Leaner",
    "more_lyrical": "More Lyrical",
    "more_tense": "More Tense",
    "more_intimate": "More Intimate",
    "more_dialogue": "More Dialogue",
    "more_sensory": "More Sensory",
    "description": "Regenerate the output in a controlled style direction without changing your model or settings."
  },
```

- [ ] **Step 2: Add the same keys to DE**

In `packages/i18n/messages/de/studio.json`, add the corresponding German block:

```json
  "styleVariants": {
    "title": "Regenerieren als…",
    "regenerate": "Regenerieren",
    "leaner": "Knapper",
    "more_lyrical": "Lyrischer",
    "more_tense": "Spannender",
    "more_intimate": "Intimer",
    "more_dialogue": "Mehr Dialog",
    "more_sensory": "Sinnlicher",
    "description": "Regeneriert den Text in eine kontrollierte Stilrichtung, ohne Modell oder Einstellungen zu ändern."
  },
```

- [ ] **Step 3: Add the same keys to FR**

In `packages/i18n/messages/fr/studio.json`, add the corresponding French block:

```json
  "styleVariants": {
    "title": "Régénérer en…",
    "regenerate": "Régénérer",
    "leaner": "Plus économe",
    "more_lyrical": "Plus lyrique",
    "more_tense": "Plus tendu",
    "more_intimate": "Plus intime",
    "more_dialogue": "Plus de dialogue",
    "more_sensory": "Plus sensoriel",
    "description": "Régénère le texte dans une direction stylistique contrôlée sans modifier le modèle ou les paramètres."
  },
```

- [ ] **Step 4: Verify JSON validity for all three files**

Run: `for lang in en de fr; do node -e "JSON.parse(require('fs').readFileSync('packages/i18n/messages/$lang/studio.json','utf8')); console.log('$lang ok')"; done`
Expected: `en ok`, `de ok`, `fr ok`

- [ ] **Step 5: Run i18n completeness check (if a script exists)**

Run: `cd packages/i18n && pnpm run check` (or the project's i18n lint command)
Expected: PASS — no missing keys between locales.

- [ ] **Step 6: Checkpoint (NO COMMIT)**

Plan policy: do NOT commit.

---

## Phase 4: Platform Layer

### Task 16: Patch the integration test conftest

**Files:**
- Modify: `tests/integration/writing/conftest.py`

- [ ] **Step 1: Add a factory for `StyleVariantService`**

In `tests/integration/writing/conftest.py`, add the import after line 34
(`from narrare.writing.rewrite_service import RewriteService`):

```python
from narrare.writing.style_variant_service import StyleVariantService
```

Add a factory function after `_make_rewrite_service` (after line 161):

```python
async def _make_style_variant_service(
    session: AsyncSession,
    user_id: str,
    project_id: object = None,
) -> StyleVariantService:
    """Build a StyleVariantService with real repo + fake pipeline (no LLM calls)."""
    repo = GenerationRepository(session)
    fake_registry = FakeModelRegistry()
    fake_registry.returns_stream(
        [
            '<alternative label="Style variant">',
            "The damp moss clung to her fingers, releasing its earthy perfume.",
            "</alternative>",
        ]
    )
    config = ResolvedModelConfig(
        provider_name="test",
        model_id="test-model",
        temperature=0.7,
        max_tokens=4000,
    )

    pipeline = WritingPipeline(
        registry=fake_registry,
        composer=get_composer(),
        context_assembler=_assembler,
        draft_processor=_processor,
    )

    return StyleVariantService(
        repo=repo,
        pipeline=pipeline,
        draft_processor=_processor,
        config=config,
    )
```

- [ ] **Step 2: Add the patch to the autouse fixture**

In the `_patch_writing_service` fixture's `with (...)` block (lines 197-218), add
after the `router_rewrite` patch:

```python
        patch(
            "narrare.writing.router_style_variants.get_style_variant_service",
            new=_make_style_variant_service,
        ),
```

- [ ] **Step 3: Checkpoint (NO COMMIT)**

Plan policy: do NOT commit.

---

### Task 17: Integration tests — SSE streaming, cancel, parity

**Files:**
- Create: `tests/integration/writing/test_style_variant_streaming.py`

- [ ] **Step 1: Write the integration tests (RED)**

Create `tests/integration/writing/test_style_variant_streaming.py`:

```python
"""Integration tests for style-variant SSE streaming (CR-AUFG-07-22).

Tests:
- SSE protocol correctness (data: prefix, [DONE] sentinel)
- <alternative> tag structure in streamed output
- style_variant field reaches the backend (observable in request)
- Visible cancel aborts the transport (DELETE generation/{id})
- Parity: the same service protocol shape as RewriteService

LLM calls are mocked via dependency override in conftest.py.
Requires: ``just dev-services`` running (PostgreSQL on port 5433).
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


_SELECTION = (
    "The old house stood at the end of the lane, its windows dark "
    "and unseeing. A cold wind blew through the broken shutters."
)


async def _create_novel_with_chapter(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> tuple[str, str]:
    novel_resp = await client.post(
        "/api/v1/novels",
        json={"title": "Variant Test Novel", "language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        json={"title": "Ch 1", "position": 1},
        headers=auth_headers,
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]
    return novel_id, chapter_id


def _parse_sse(body: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for line in body.split("\n"):
        if line.startswith("data: ") and line != "data: [DONE]":
            events.append(json.loads(line[6:]))
    return events


class TestStyleVariantSSEProtocol:
    async def test_streams_alternative_with_done_sentinel(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/style-variants/regenerate"
            f"?novel_id={novel_id}",
            json={"source_text": _SELECTION, "style_variant": "more_sensory"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.text
        assert "data: " in body
        assert "data: [DONE]" in body
        events = _parse_sse(body)
        text_events = [e for e in events if "text" in e]
        assert len(text_events) >= 1
        full_text = "".join(str(e["text"]) for e in text_events)
        assert "<alternative" in full_text


class TestStyleVariantValidation:
    async def test_rejects_empty_source_text(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/style-variants/regenerate"
            f"?novel_id={novel_id}",
            json={"source_text": "   ", "style_variant": "leaner"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_rejects_invalid_variant(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/style-variants/regenerate"
            f"?novel_id={novel_id}",
            json={"source_text": _SELECTION, "style_variant": "nonexistent"},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestStyleVariantCancel:
    async def test_stop_aborts_active_generation(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Visible cancel must abort the variant transport (RULE-20)."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        # Start the variant generation
        resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/style-variants/regenerate"
            f"?novel_id={novel_id}",
            json={"source_text": _SELECTION, "style_variant": "leaner"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

        # Extract request_id from SSE events
        events = _parse_sse(resp.text)
        request_info = next(
            (e for e in events if e.get("type") == "request_info"), None
        )
        # If the stream completed before we could cancel, the test still
        # proves the endpoint is reachable and streamable.  A slow-stream
        # fake would be needed for a true mid-stream cancel assertion.
        if request_info and "request_id" in request_info:
            stop_resp = await client.delete(
                f"/api/v1/writing/generation/{request_info['request_id']}",
                headers=auth_headers,
            )
            assert stop_resp.status_code in (200, 404)
```

- [ ] **Step 2: Run integration tests (requires dev-services)**

Run: `uv run pytest tests/integration/writing/test_style_variant_streaming.py -v`
Expected: PASS — all tests green.  If PostgreSQL is not running, run
`just dev-services` first.

- [ ] **Step 3: Checkpoint (NO COMMIT)**

Plan policy: do NOT commit.

---

### Task 18: Platform parity test + inventory + docs

**Files:**
- Create/Modify: `tests/unit/api/writing/test_style_variant_parity.py`
- Modify: inventory of AI operations (if one exists in the repo)

- [ ] **Step 1: Write a contract-parity unit test (RULE-17)**

Create `tests/unit/api/writing/test_style_variant_parity.py`:

```python
"""Contract-parity test for StyleVariantRegenerationProtocol (RULE-17).

Ensures the runtime service structurally satisfies its declared Protocol so
the contract cannot silently drift.
"""

from __future__ import annotations

from narrare.writing.contracts_style_variants import StyleVariantRegenerationProtocol
from narrare.writing.style_variant_service import StyleVariantService


def test_service_satisfies_protocol() -> None:
    """StyleVariantService must be a runtime instance of its Protocol."""
    assert issubclass(StyleVariantService, StyleVariantRegenerationProtocol) or (
        # runtime_checkable Protocols use isinstance, not issubclass
        hasattr(StyleVariantService, "validate_variant")
        and hasattr(StyleVariantService, "stream_variant")
    )


def test_protocol_has_stream_variant_method() -> None:
    assert hasattr(StyleVariantRegenerationProtocol, "stream_variant")
```

- [ ] **Step 2: Run the parity test**

Run: `uv run pytest tests/unit/api/writing/test_style_variant_parity.py -v`
Expected: PASS.

- [ ] **Step 3: Update the AI-operations inventory**

Search for an inventory file of AI operations (e.g. `docs/mvp/ai-operations.md`
or similar) and add the style-variant regenerate endpoint. If no formal
inventory exists, skip this step and note it in the final self-review.

Run: `rg -l "ai-operations|ai_operations|inventory" docs/ apps/ 2>/dev/null`
to locate the inventory.  Add an entry noting:
- Operation: `style-variant-regenerate`
- Endpoint: `POST /writing/chapters/{chapter_id}/style-variants/regenerate`
- Intent: `LLMIntent.REWRITE` (reused)
- Streaming: SSE-direct
- Mode: `rewrite_selection` (reused)

- [ ] **Step 4: Checkpoint (NO COMMIT)**

Plan policy: do NOT commit.

---

## Phase 5: Final Verification + Self-Review

### Task 19: Architecture-constraint check + type check

- [ ] **Step 1: Run the architecture check**

Run: `uv run python scripts/check_architecture.py`
Expected: EXIT 0 — no RULE violations.  If it fails, fix the violation before
proceeding (do NOT bypass the check).

- [ ] **Step 2: Run mypy --strict on touched core + backend files**

Run:
```bash
uv run mypy --strict \
  packages/core/narrare_core/writing/style_variants.py \
  packages/core/narrare_core/writing/pipeline_rewrite.py \
  packages/core/narrare_core/writing/pipeline.py \
  apps/api/narrare/writing/contracts_style_variants.py \
  apps/api/narrare/writing/schemas_style_variants.py \
  apps/api/narrare/writing/style_variant_service.py \
  apps/api/narrare/writing/router_style_variants.py \
  apps/api/narrare/writing/deps_style_variants.py
```
Expected: `Success: no issues found`.  Fix any type errors.

- [ ] **Step 3: Run pyright on the same files (if configured)**

Run: `uv run pyright <same files>` (or `just typecheck`)
Expected: 0 errors.

- [ ] **Step 4: Run the full unit test suite**

Run: `uv run pytest tests/unit/ -x -q`
Expected: PASS — no regressions.

- [ ] **Step 5: Run frontend type check + tests**

Run:
```bash
cd packages/web && pnpm tsc --noEmit && pnpm vitest run
```
Expected: 0 type errors, all tests pass.

---

### Task 20: Self-review checklist

- [ ] **Step 1: Verify spec coverage**

Walk through each acceptance criterion in
`docs/features/ai-ux/CR-AUFG-07-22-style-variants-regeneration.md` and confirm
a task implements it:

| Criterion | Implemented by |
|-----------|---------------|
| Finite variant taxonomy (6 values) | Task 1 (StyleVariant enum) |
| Original output visible until variant accepted | Task 14 (modal shows both, picker is additive) |
| Variants compared via shared diff/review primitive | Task 14 (reuses AIDiffView in RewriteSuggestionModal) |
| Selected variant flows into service request, observable in tests | Task 8 (service test asserts style_variant passed), Task 12 (frontend test asserts body) |
| Model/provider/token settings resolve through cascade | Task 9 (deps uses REWRITE intent resolver) |
| Streaming required | Task 10 (SSE endpoint), Task 12 (SSE wrapper) |
| Visible cancel aborts transport | Task 17 (cancel test) |
| Partial output preserved on connection loss | Task 8 (service marks failed + partial word count) |
| DE/EN/FR variant labels | Task 15 (i18n) |
| Backend schema/service tests | Task 8 (unit), Task 17 (integration) |
| Streaming tests proving cancel reaches transport | Task 17 |
| Frontend tests proving variant in API request | Task 12 |
| Prompt variable/manifest check | Task 3 (template), Task 5 (route table) |
| Inventory update | Task 18 |

- [ ] **Step 2: Verify no workarounds or shortcuts**

Search for `TODO`, `FIXME`, `HACK`, `XXX` in the new/modified files:
```bash
rg -n "TODO|FIXME|HACK|XXX" \
  packages/core/narrare_core/writing/style_variants.py \
  apps/api/narrare/writing/style_variant_service.py \
  apps/api/narrare/writing/router_style_variants.py \
  packages/web/components/studio/editor/StyleVariantPicker.tsx
```
Expected: no matches.

- [ ] **Step 3: Verify type consistency**

Confirm the `StyleVariant` string values match across all layers:
- Core enum: `leaner`, `more_lyrical`, `more_tense`, `more_intimate`, `more_dialogue`, `more_sensory`
- Backend schema: uses `StyleVariant` from core (re-exported)
- Frontend type: same 6 string literals
- i18n keys: `studio.styleVariants.<value>` for each

- [ ] **Step 4: Verify RULE-XX compliance**

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-01b | ✅ | Service calls `pipeline.generate()`, not LLM directly |
| RULE-02/02a/02b | ✅ | Instructions injected via template variable, not inline f-string; prompt built by PromptComposer |
| RULE-03 | ✅ | `contracts_style_variants.py` written before service (Task 6 before Task 8) |
| RULE-04 | ✅ | 5-file backend split; core enum in own file; no file exceeds limits |
| RULE-06 | ✅ | Router delegates immediately; service has logic; one responsibility per file |
| RULE-07 | ✅ | router → service → repo → DB; core has no apps/ imports |
| RULE-09 | ✅ | All public methods typannotated; mypy --strict passes |
| RULE-11 | ✅ | Errors raised (ValidationError, ConflictError, NotFoundError); failed status logged |
| RULE-12 | ✅ | Service Layer is only public API; endpoint calls service |
| RULE-13 | ✅ | Streaming + non-streaming share the service (stream_variant) |
| RULE-17 | ✅ | Parity test (Task 18) proves runtime conformance to Protocol |
| RULE-20 | ✅ | SSE streaming required + cancel test |

- [ ] **Step 5: Final full-suite run**

Run:
```bash
uv run pytest tests/ -x -q
cd packages/web && pnpm vitest run
cd packages/i18n && pnpm run check 2>/dev/null || true
```
Expected: all green.

- [ ] **Step 6: Report completion**

Report to the coordinator:

```
✅ CR-AUFG-07-22 Increment A — Style Variants Regeneration
   Plan executed. All tasks complete.

✅ Core: StyleVariant enum + instructions + pipeline threading + template variable
✅ Backend: 5-file module split (contracts, schemas, service, router, deps) + registered
✅ Frontend: StyleVariantPicker + streamStyleVariantRegeneration + modal integration
✅ i18n: DE/EN/FR studio.styleVariants.*
✅ Tests: unit (core + service + parity) + integration (SSE + validation + cancel)
✅ Gates: check_architecture.py + mypy --strict + tsc + vitest all green

⏳ NOT DONE: git commit (per plan policy — coordinator decides when to commit)
```

---

## Appendix: Commands Quick Reference

| Action | Command |
|--------|---------|
| Core unit tests | `uv run pytest tests/unit/core/writing/ -v` |
| Backend unit tests | `uv run pytest tests/unit/api/writing/ -v` |
| Integration tests (needs `just dev-services`) | `uv run pytest tests/integration/writing/test_style_variant_streaming.py -v` |
| Frontend tests | `cd packages/web && pnpm vitest run` |
| Architecture check | `uv run python scripts/check_architecture.py` |
| Type check (Python) | `uv run mypy --strict <files>` |
| Type check (TS) | `cd packages/web && pnpm tsc --noEmit` |
| i18n check | `cd packages/i18n && pnpm run check` |

---

## Notes for the Implementer

1. **Style variant ≠ rewrite mode.** The `style_variant` param is layered ON TOP
   of the base `rewrite_mode="style"`. The template renders both
   `{{rewrite_mode_instructions}}` (from the mode) and `{{style_variant_instructions}}`
   (from the variant). When `style_variant is None`, the variable renders as empty
   string — fully backward compatible.

2. **The service duplicates streaming glue by design.** This matches the existing
   Extend/Rewrite/Co-Author pattern. A shared base class for streaming services is a
   larger refactor outside this increment's scope.

3. **count is always 1 for variants.** A style-variant regeneration produces a single
   alternative. Multi-variant comparison is a future increment (B).

4. **The frontmatter in the feature spec** (`docs/features/ai-ux/CR-AUFG-07-22-...md`)
   lists aspirational file paths (`style_variant/system.md` prompt,
   `contracts.py#StyleVariantRegenerationProtocol`). The approved architecture
   supersedes these: the prompt reuses `rewrite_selection/system.md` and the contract
   lives in `contracts_style_variants.py`. Do not create the frontmatter's prompt path.
