# Adaptive Context Core Foundation — Implementation Plan (Phase 1+2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Core data models, Protocol, enricher, and Backend provider for the Adaptive Context vertical — foundation for ASSIST-004 Dialogue Coach + LEARN-002 Adaptivity Dashboard. Covers ADR-069 Retrofit-Plan steps 1–10 only; Phases 3–6 (Backend domains, Frontend, Evals, Docs) are planned separately.

**Architecture:** New frozen dataclasses (`AdaptiveWeights`, `AdaptiveContext`, `AdaptiveSettings`) live in Core `ai_invocation/adaptive_context.py`. A new Core `AdaptiveContextProvider` Protocol (in `ai_invocation/contracts.py`) is consumed by a new Core `AdaptiveContextEnricher` (in `ai_invocation/enrichers/adaptive.py`) which becomes the **single canonical writer** of all four adaptive prompt variables (`user_preferences`, `style_constraints`, `avoidance_patterns`, `character_voice_profiles`). `AdaptiveContextEnricher` **replaces** `PreferenceContextEnricherImpl` (the ADR-038 enricher that wrote only `user_preferences`). A Backend `AdaptiveContextProviderImpl` (`apps/api/narrare/adaptive/adaptive_context_provider.py`) composes the existing `PreferenceProvider` + `ProfileProvider` Protocols; Phase 2 ships it as a scaffold (settings defaults + no evidence writes; persistence + evidence land in Phase 3).

**Tech Stack:** Python 3.14, pydantic-ai, structlog, FastAPI (Backend only), SQLAlchemy 2.0 async (Backend only — not yet exercised in Phase 2), ruff (line-length=100), pyright `--strict`.

## Global Constraints

Verbatim from ADR-069 § Decision Drivers, § Consequences, § Retrofit-Plan §3 (Breaking-change assessment); CONSTRAINTS.md RULE-03 / RULE-04 / RULE-06 / RULE-10 / RULE-11:

- **Python 3.14**, pyright `--strict` mode, ruff line-length=100. No `# type: ignore` introduced (RULE-23).
- **RULE-03 (Contract first):** `AdaptiveContextProvider` Protocol exists in `contracts.py` BEFORE any impl. Phase 2 impl is gated on the Protocol landing in Phase 1.
- **RULE-04 (Modularise, don't compress):** `adaptive_context.py` (Core data) <= 200 LOC; `enrichers/adaptive.py` <= 150 LOC; Backend `adaptive_context_provider.py` <= 250 LOC.
- **RULE-06 (One responsibility per file):** separate dataclass file, enricher file, provider impl file. The enricher name (`AdaptiveContextEnricher`) documents its responsibility.
- **RULE-07 (Dependency direction):** Core Protocol consumed by Core enricher; Backend impl handles I/O. No `apps/`->`core` cycles; no `core/`->`apps/` imports. The Core enricher imports ONLY from `narrare_core.*`.
- **RULE-10 (Tests are not optional):** every task has TDD (test first, fail, impl, pass, check, commit). Coverage target: `core/ai_invocation/` >= 95%.
- **RULE-11 (No silent failures):** provider failures log warnings and return graceful defaults — the enricher must not crash on missing data (ADR-038 D7). A user with no preferences / no voices / adaptivity disabled yields a no-op enricher, never an exception.
- **ADR-055/057 hard constraint:** `voice_metrics` MUST NOT appear in any `AdaptiveContext` field. `AdaptiveContext.voice_profiles_text` carries ONLY the descriptive `formatted_voice_profiles` text (the `speech_summary` block). Never the numeric metrics.
- **ADR-067 pattern:** `AdaptiveContextProvider` mirrors the proven `KBContextProvider` pattern — Core Protocol + Backend composer impl that folds existing providers into one bundle.
- **ADR-069 §3 (Breaking change):** `AdaptiveContextEnricher` is a strict functional superset of `PreferenceContextEnricherImpl` for the `user_preferences` key. Tests that mock the old class must mock the new one — mechanical migration in Task 9, deletion in Task 10.
- **Phase 2 scaffold boundaries:** Backend `AdaptiveContextProviderImpl.get_settings()` returns defaults (`AdaptiveSettings()` — `enabled=True`, `weights=AdaptiveWeights()`). It does NOT yet read `ProjectSettings.adaptive_settings` (Phase 3) and does NOT write `invocation_evidence.adaptive_*` columns (Phase 3).
- **pyright `--strict` must pass** for all new code.
- **`just check` must pass** (9 step groups: Architecture, Lint & Format, Typecheck, Security, Model Registry, Prompts, Frontend Lint, i18n Validation, Frontend Types) at the end of every task.
- **No `--no-verify`** in any git command. Pre-commit architecture hook must pass.
- **Existing wiring location:** the production enricher wiring lives in `apps/api/narrare/_app/dependencies_pipeline.py` (NOT `dependencies_prompts.py` — that file owns the PreferenceService singleton only). Task 8 modifies `dependencies_pipeline.py`.

---

## File Structure Map

### NEW files

| Path | Responsibility | RULE-04 cap |
|------|----------------|-------------|
| `packages/core/narrare_core/ai_invocation/adaptive_context.py` | Frozen dataclasses: `AdaptiveWeights`, `AdaptiveContext`, `AdaptiveSettings`. Pure value objects, no I/O. | <= 200 LOC |
| `packages/core/narrare_core/ai_invocation/enrichers/adaptive.py` | `AdaptiveContextEnricher` — Core enricher that calls `AdaptiveContextProvider` and writes all four adaptive `dynamic_inputs` keys. | <= 150 LOC |
| `apps/api/narrare/adaptive/__init__.py` | Backend adaptive-domain package init (empty namespace marker). | -- |
| `apps/api/narrare/adaptive/adaptive_context_provider.py` | `AdaptiveContextProviderImpl` — Backend impl composing `PreferenceProvider` + `ProfileProvider`. Phase 2 scaffold. | <= 250 LOC |
| `packages/core/narrare_core/llm/intents/_docs_ai_assist.py` | Verbose Scope/Input/Output/NOT docs for `DIALOGUE_COACH`. | -- |
| `tests/unit/core/ai_invocation/test_adaptive_context.py` | Dataclass unit tests: clamping, defaults, `has_any_signal`, frozen, slots. | -- |
| `tests/unit/core/ai_invocation/test_adaptive_enricher.py` | Enricher tests: success, no provider, missing IDs, provider failure, disabled, no signal, all 4 variables written, immutability. | -- |
| `tests/unit/core/ai_invocation/test_adaptive_provider_protocol.py` | Protocol conformance test with a Fake. | -- |
| `tests/unit/core/llm/intents/test_dialogue_coach_intent.py` | DIALOGUE_COACH enum + docs entry tests. | -- |
| `tests/unit/core/prompts/test_variable_registry_dialogue_coach.py` | New template variables registration tests. | -- |
| `tests/unit/api/adaptive/__init__.py` + `test_adaptive_context_provider.py` | Backend provider tests with fakes. | -- |
| `tests/unit/api/_app/test_dependencies_pipeline_adaptive.py` | Production pipeline wiring regression tests. | -- |

### MODIFIED files

| Path | Change |
|------|--------|
| `packages/core/narrare_core/ai_invocation/contracts.py` | ADD `AdaptiveContextProvider` Protocol (after `ProfileProvider`). |
| `packages/core/narrare_core/ai_invocation/enrichers/__init__.py` | EXPORT `AdaptiveContextEnricher` (Task 6); REMOVE `PreferenceContextEnricherImpl` export (Task 10). |
| `packages/core/narrare_core/ai_invocation/enrichers/preferences.py` | DELETE the entire file (Task 10). The `PreferenceContextEnricher` Protocol stays in `contracts.py`. |
| `packages/core/narrare_core/llm/intents/_enums.py` | ADD `DIALOGUE_COACH = "dialogue_coach"` member (new "AI assist operations" section). |
| `packages/core/narrare_core/llm/intents/_docs.py` | ADD `_docs_ai_assist.py` import + spread into `INTENT_DOCS`. |
| `packages/core/narrare_core/prompts/variable_registry.py` | ADD `"characters"` to `SYSTEM_VARS`; ADD `"text_to_analyze"` to `USER_CONTENT_VARS`. |
| `apps/api/narrare/_app/dependencies_pipeline.py` | REPLACE `PreferenceContextEnricherImpl(...)` wiring with `AdaptiveContextEnricher(adaptive_provider=AdaptiveContextProviderImpl(...))`. |
| `tests/unit/core/ai_invocation/test_writing_preference_enricher.py` | Migrate mocks from `PreferenceContextEnricherImpl` to `AdaptiveContextEnricher` via `FakeAdaptiveContextProvider` (Task 9). |
| `tests/unit/core/ai_invocation/enrichers/test_preferences.py` | DELETE (Task 9) — its coverage is subsumed by `test_adaptive_enricher.py`. |
| `scripts/probes/preference_enrichment_probe.py` | Migrate the probe to use `AdaptiveContextEnricher` (Task 9). |

### NOT modified (Phase 3+ scope, explicitly out of plan)

- `route_table.py` — `DIALOGUE_COACH` route entry is Phase 4 step 17.
- `prompt-surface-manifest.yaml` / `adoption-registry.yaml` — Phase 4 step 16.
- `_bundled/ai_assist/en/dialogue_coach/system.md` — Phase 4 step 15.
- `ProjectSettings.adaptive_settings` JSONB + Alembic — Phase 3 step 11.
- `invocation_evidence.adaptive_*` columns + Alembic — Phase 3 step 12.

---

## Task Ordering

**Phase 1 (Tasks 1–5):** Pure Core additions. No behaviour change at runtime — the new code exists but nothing wires it yet. Each task ships independently; `just check` stays green throughout.

**Phase 2 (Tasks 6–10):** The enricher swap. Task 6 implements the new enricher; Task 7 implements the Backend provider; Task 8 rewires production DI; Task 9 migrates existing tests + probes; Task 10 deletes the old class. After Task 10, the codebase has ONE adaptive enricher.

Tasks 6 and 7 can be developed in parallel (Task 7 depends on Task 4 Protocol; Task 6 depends on Tasks 1+2+3 dataclasses + Task 4 Protocol). Task 8 depends on both. The plan serialises them for clarity.

---

### Task 1: `AdaptiveWeights` dataclass

**Files:**
- Create: `packages/core/narrare_core/ai_invocation/adaptive_context.py`
- Test: `tests/unit/core/ai_invocation/test_adaptive_context.py`

**Interfaces:**
- Consumes: nothing (pure value object).
- Produces: `AdaptiveWeights` — frozen, slotted dataclass with four float fields (`preference: float = 0.7`, `voice_fidelity: float = 0.9`, `style_constraints: float = 1.0`, `avoidance: float = 1.0`) and a `validated() -> AdaptiveWeights` method that clamps each to `[0.0, 1.0]`. Tasks 2, 3, 6, 7 import this class.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/core/ai_invocation/test_adaptive_context.py`:

```python
"""Tests for AdaptiveWeights, AdaptiveContext, AdaptiveSettings dataclasses.

Covers: defaults, clamping, frozen, slots, has_any_signal.
See: ADR-069, CONSTRAINTS.md RULE-03/RULE-04.
"""

from __future__ import annotations

import dataclasses

import pytest

from narrare_core.ai_invocation.adaptive_context import AdaptiveWeights


class TestAdaptiveWeights:
    """AdaptiveWeights — frozen value object with clamping."""

    def test_default_weights_match_spec(self) -> None:
        """Spec §5.1: preference=0.7, voice_fidelity=0.9,
        style_constraints=1.0, avoidance=1.0."""
        weights = AdaptiveWeights()
        assert weights.preference == 0.7
        assert weights.voice_fidelity == 0.9
        assert weights.style_constraints == 1.0
        assert weights.avoidance == 1.0

    def test_custom_weights_preserved(self) -> None:
        weights = AdaptiveWeights(preference=0.3, voice_fidelity=0.5)
        assert weights.preference == 0.3
        assert weights.voice_fidelity == 0.5

    def test_is_frozen(self) -> None:
        """RULE-03: immutable value object."""
        weights = AdaptiveWeights()
        with pytest.raises(dataclasses.FrozenInstanceError):
            weights.preference = 0.5  # type: ignore[misc]

    def test_is_slotted(self) -> None:
        """No __dict__ — slots prevent arbitrary attribute addition."""
        weights = AdaptiveWeights()
        assert not hasattr(weights, "__dict__")

    def test_validated_clamps_below_zero(self) -> None:
        weights = AdaptiveWeights(preference=-0.5, voice_fidelity=-1.0)
        clamped = weights.validated()
        assert clamped.preference == 0.0
        assert clamped.voice_fidelity == 0.0

    def test_validated_clamps_above_one(self) -> None:
        weights = AdaptiveWeights(style_constraints=2.0, avoidance=1.5)
        clamped = weights.validated()
        assert clamped.style_constraints == 1.0
        assert clamped.avoidance == 1.0

    def test_validated_preserves_in_range(self) -> None:
        weights = AdaptiveWeights(preference=0.42, voice_fidelity=0.81)
        clamped = weights.validated()
        assert clamped.preference == 0.42
        assert clamped.voice_fidelity == 0.81

    def test_validated_returns_new_instance(self) -> None:
        """validated() does not mutate; returns a new frozen instance."""
        weights = AdaptiveWeights(preference=2.0)
        clamped = weights.validated()
        assert weights.preference == 2.0  # original unchanged
        assert clamped.preference == 1.0
        assert clamped is not weights
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/core/ai_invocation/test_adaptive_context.py::TestAdaptiveWeights -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'narrare_core.ai_invocation.adaptive_context'`.

- [ ] **Step 3: Write minimal implementation**

Create `packages/core/narrare_core/ai_invocation/adaptive_context.py`:

```python
"""Adaptive Context — consolidated view of all adaptivity signals.

Defines the Core data models for adaptivity:
- ``AdaptiveWeights``: user-tunable weighting of signal sources.
- ``AdaptiveContext``: consolidated snapshot of all adaptive data for one
  specific AI invocation.
- ``AdaptiveSettings``: persisted user settings (enabled flag + weights).

Pure value objects — no I/O, no dependencies on apps/.

See:
    ADR-069 (Adaptive Context + Dialogue Coach Vertical),
    CONSTRAINTS.md RULE-03 (Contracts first), RULE-04 (Modularise).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AdaptiveWeights:
    """User-tunable weighting of adaptivity signals.

    All values are floats in ``[0.0, 1.0]``. The exact semantics are
    determined by the ``AdaptiveContextEnricher``; typically a higher
    weight controls how strongly the corresponding signal is injected
    into the prompt (e.g., as an explicit instruction vs. context block).

    Attributes:
        preference: Weight for user preferences (PreferenceProfile).
            Default ``0.7`` — preferences are primary.
        voice_fidelity: Weight for character-voice fidelity
            (CharacterVoiceProfile). Default ``0.9`` — voice fidelity is
            critical for dialogue-coach use cases.
        style_constraints: Weight for hard style constraints.
            Default ``1.0`` — constraints are binding.
        avoidance: Weight for avoidance patterns (things the user
            rejects). Default ``1.0`` — avoidance is binding.
    """

    preference: float = 0.7
    voice_fidelity: float = 0.9
    style_constraints: float = 1.0
    avoidance: float = 1.0

    def validated(self) -> AdaptiveWeights:
        """Return a copy with each weight clamped to ``[0.0, 1.0]``.

        Does not mutate ``self`` (the dataclass is frozen). Use this at
        any boundary where untrusted input (REST API, JSONB load) may
        have produced out-of-range values.
        """
        return AdaptiveWeights(
            preference=max(0.0, min(1.0, self.preference)),
            voice_fidelity=max(0.0, min(1.0, self.voice_fidelity)),
            style_constraints=max(0.0, min(1.0, self.style_constraints)),
            avoidance=max(0.0, min(1.0, self.avoidance)),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/core/ai_invocation/test_adaptive_context.py::TestAdaptiveWeights -v`
Expected: PASS — all 8 tests green.

- [ ] **Step 5: Run full check suite**

Run: `just check`
Expected: All 9 step groups pass (Architecture, Lint & Format, Typecheck, Security, Model Registry, Prompts, Frontend Lint, i18n Validation, Frontend Types).

- [ ] **Step 6: Commit**

```bash
git add packages/core/narrare_core/ai_invocation/adaptive_context.py \
        tests/unit/core/ai_invocation/test_adaptive_context.py
git commit -m "feat(core): add AdaptiveWeights dataclass for adaptive context

Pure frozen, slotted value object with four weight fields
(preference, voice_fidelity, style_constraints, avoidance) and a
validated() method clamping each to [0.0, 1.0].

First piece of ADR-069 Phase 1 (Retrofit-Plan step 1).
No runtime behaviour change yet — no caller wires the dataclass."
```

---

### Task 2: `AdaptiveContext` dataclass

**Files:**
- Modify: `packages/core/narrare_core/ai_invocation/adaptive_context.py` (append class)
- Test: `tests/unit/core/ai_invocation/test_adaptive_context.py` (append test class)

**Interfaces:**
- Consumes: `AdaptiveWeights` from Task 1, `UUID` from stdlib.
- Produces: `AdaptiveContext` — frozen, slotted dataclass with `user_id: UUID`, `project_id: UUID`, four `str` text fields (default `""`), `weights: AdaptiveWeights` (default factory), `source_summary: str` (default `""`), and a `has_any_signal: bool` property. Tasks 3, 4, 6, 7 import this class.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/core/ai_invocation/test_adaptive_context.py`:

```python
from uuid import uuid4

from narrare_core.ai_invocation.adaptive_context import AdaptiveContext


class TestAdaptiveContext:
    """AdaptiveContext — consolidated snapshot."""

    def test_default_text_fields_empty(self) -> None:
        ctx = AdaptiveContext(user_id=uuid4(), project_id=uuid4())
        assert ctx.preference_text == ""
        assert ctx.voice_profiles_text == ""
        assert ctx.style_constraints_text == ""
        assert ctx.avoidance_patterns_text == ""
        assert ctx.source_summary == ""

    def test_default_weights_are_factory_fresh(self) -> None:
        """Each new instance gets its own AdaptiveWeights (no shared default)."""
        ctx_a = AdaptiveContext(user_id=uuid4(), project_id=uuid4())
        ctx_b = AdaptiveContext(user_id=uuid4(), project_id=uuid4())
        assert ctx_a.weights == ctx_b.weights
        assert ctx_a.weights is not ctx_b.weights

    def test_has_any_signal_false_when_all_empty(self) -> None:
        ctx = AdaptiveContext(user_id=uuid4(), project_id=uuid4())
        assert ctx.has_any_signal is False

    def test_has_any_signal_true_if_preference_text(self) -> None:
        ctx = AdaptiveContext(
            user_id=uuid4(),
            project_id=uuid4(),
            preference_text="prefers dark prose",
        )
        assert ctx.has_any_signal is True

    def test_has_any_signal_true_if_voice_profiles_text(self) -> None:
        ctx = AdaptiveContext(
            user_id=uuid4(),
            project_id=uuid4(),
            voice_profiles_text="**Alice**: terse",
        )
        assert ctx.has_any_signal is True

    def test_has_any_signal_true_if_style_constraints_text(self) -> None:
        ctx = AdaptiveContext(
            user_id=uuid4(),
            project_id=uuid4(),
            style_constraints_text="- Short sentences",
        )
        assert ctx.has_any_signal is True

    def test_has_any_signal_true_if_avoidance_patterns_text(self) -> None:
        ctx = AdaptiveContext(
            user_id=uuid4(),
            project_id=uuid4(),
            avoidance_patterns_text="- No passive voice",
        )
        assert ctx.has_any_signal is True

    def test_is_frozen(self) -> None:
        ctx = AdaptiveContext(user_id=uuid4(), project_id=uuid4())
        with pytest.raises(dataclasses.FrozenInstanceError):
            ctx.preference_text = "mutated"  # type: ignore[misc]

    def test_is_slotted(self) -> None:
        ctx = AdaptiveContext(user_id=uuid4(), project_id=uuid4())
        assert not hasattr(ctx, "__dict__")

    def test_does_not_carry_voice_metrics_field(self) -> None:
        """ADR-055/057 hard constraint: voice_metrics never reach
        AdaptiveContext. Only descriptive text (voice_profiles_text)
        is permitted. Asserting the field list excludes metrics."""
        field_names = {f.name for f in dataclasses.fields(AdaptiveContext)}
        assert "voice_metrics" not in field_names
        assert "metrics" not in field_names
        assert "voice_profiles_text" in field_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/core/ai_invocation/test_adaptive_context.py::TestAdaptiveContext -v`
Expected: FAIL with `ImportError: cannot import name 'AdaptiveContext'`.

- [ ] **Step 3: Write minimal implementation**

Append to `packages/core/narrare_core/ai_invocation/adaptive_context.py` (update top imports to `from dataclasses import dataclass, field` and `from uuid import UUID`, then append the class):

```python
@dataclass(frozen=True, slots=True)
class AdaptiveContext:
    """Consolidated snapshot of all adaptive signals for one invocation.

    Assembled by the ``AdaptiveContextProvider`` (Backend impl) and
    consumed by the ``AdaptiveContextEnricher`` (Core), which injects
    the four text fields into ``dynamic_inputs`` for prompt composition.

    ADR-055/057 boundary: ``voice_profiles_text`` carries ONLY the
    descriptive ``formatted_voice_profiles`` text (the
    ``speech_summary`` block). The numeric ``voice_metrics`` are
    checking-path only and never reach this dataclass.

    Attributes:
        user_id: The user ID the context applies to.
        project_id: The project ID the context applies to.
        preference_text: Formatted text from PreferenceProfile
            (may be empty if no preferences).
        voice_profiles_text: Formatted text of all CharacterVoiceProfiles
            (may be empty if no profiles).
        style_constraints_text: Derived style constraints as a
            bullet list (may be empty).
        avoidance_patterns_text: Derived avoidance patterns as a
            bullet list (may be empty).
        weights: The weights active at invocation time.
        source_summary: Short human-readable summary of sources
            (e.g., "3 character voices, 12 preference events") for
            transparency UI and logging.
    """

    user_id: UUID
    project_id: UUID
    preference_text: str = ""
    voice_profiles_text: str = ""
    style_constraints_text: str = ""
    avoidance_patterns_text: str = ""
    weights: AdaptiveWeights = field(default_factory=AdaptiveWeights)
    source_summary: str = ""

    @property
    def has_any_signal(self) -> bool:
        """True if at least one adaptive signal is present."""
        return bool(
            self.preference_text
            or self.voice_profiles_text
            or self.style_constraints_text
            or self.avoidance_patterns_text
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/core/ai_invocation/test_adaptive_context.py::TestAdaptiveContext -v`
Expected: PASS — all 10 tests green.

- [ ] **Step 5: Run full check suite**

Run: `just check`
Expected: All 9 step groups pass.

- [ ] **Step 6: Commit**

```bash
git add packages/core/narrare_core/ai_invocation/adaptive_context.py \
        tests/unit/core/ai_invocation/test_adaptive_context.py
git commit -m "feat(core): add AdaptiveContext dataclass for adaptive snapshot

Frozen, slotted value object aggregating user_id/project_id plus four
text fields (preference_text, voice_profiles_text, style_constraints_text,
avoidance_patterns_text) and weights. has_any_signal property gates
injection in the enricher (Task 6).

Hard constraint enforced: voice_metrics field MUST NOT exist on this
dataclass (ADR-055/057 boundary preserved by structural assertion).

Second piece of ADR-069 Phase 1 (Retrofit-Plan step 1).
No runtime behaviour change yet."
```

---

### Task 3: `AdaptiveSettings` dataclass

**Files:**
- Modify: `packages/core/narrare_core/ai_invocation/adaptive_context.py` (append class)
- Test: `tests/unit/core/ai_invocation/test_adaptive_context.py` (append test class)

**Interfaces:**
- Consumes: `AdaptiveWeights` from Task 1.
- Produces: `AdaptiveSettings` — frozen, slotted dataclass with `enabled: bool = True`, `weights: AdaptiveWeights = field(default_factory=AdaptiveWeights)`. Tasks 4, 6, 7 import this class.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/core/ai_invocation/test_adaptive_context.py`:

```python
from narrare_core.ai_invocation.adaptive_context import AdaptiveSettings


class TestAdaptiveSettings:
    """AdaptiveSettings — persisted user settings."""

    def test_defaults_enabled_with_factory_weights(self) -> None:
        settings = AdaptiveSettings()
        assert settings.enabled is True
        assert isinstance(settings.weights, AdaptiveWeights)
        assert settings.weights.preference == 0.7

    def test_custom_enabled_false(self) -> None:
        settings = AdaptiveSettings(enabled=False)
        assert settings.enabled is False

    def test_custom_weights(self) -> None:
        weights = AdaptiveWeights(voice_fidelity=0.42)
        settings = AdaptiveSettings(enabled=True, weights=weights)
        assert settings.weights.voice_fidelity == 0.42

    def test_default_weights_are_factory_fresh(self) -> None:
        """Each new AdaptiveSettings gets its own AdaptiveWeights."""
        a = AdaptiveSettings()
        b = AdaptiveSettings()
        assert a.weights is not b.weights

    def test_is_frozen(self) -> None:
        settings = AdaptiveSettings()
        with pytest.raises(dataclasses.FrozenInstanceError):
            settings.enabled = False  # type: ignore[misc]

    def test_is_slotted(self) -> None:
        settings = AdaptiveSettings()
        assert not hasattr(settings, "__dict__")

    def test_nested_weights_remain_independent(self) -> None:
        """Two AdaptiveSettings with the same values do not share weights."""
        a = AdaptiveSettings()
        b = AdaptiveSettings()
        a.weights.preference  # touch to ensure no lazy-init surprise
        assert a.weights == b.weights
        assert a.weights is not b.weights
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/core/ai_invocation/test_adaptive_context.py::TestAdaptiveSettings -v`
Expected: FAIL with `ImportError: cannot import name 'AdaptiveSettings'`.

- [ ] **Step 3: Write minimal implementation**

Append to `packages/core/narrare_core/ai_invocation/adaptive_context.py`:

```python
@dataclass(frozen=True, slots=True)
class AdaptiveSettings:
    """Persisted user settings for adaptivity.

    Stored per-project as JSONB on ``ProjectSettings.adaptive_settings``
    (Phase 3 / ADR-069 Decision 2). Phase 2 ships a scaffold impl that
    returns defaults only.

    Attributes:
        enabled: Master switch. When ``False``, the
            ``AdaptiveContextEnricher`` short-circuits and writes no
            adaptive variables (graceful no-op).
        weights: Active weight configuration.
    """

    enabled: bool = True
    weights: AdaptiveWeights = field(default_factory=AdaptiveWeights)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/core/ai_invocation/test_adaptive_context.py::TestAdaptiveSettings -v`
Expected: PASS — all 7 tests green.

- [ ] **Step 5: Run full check suite**

Run: `just check`
Expected: All 9 step groups pass.

- [ ] **Step 6: Commit**

```bash
git add packages/core/narrare_core/ai_invocation/adaptive_context.py \
        tests/unit/core/ai_invocation/test_adaptive_context.py
git commit -m "feat(core): add AdaptiveSettings dataclass for adaptive settings

Frozen, slotted value object: enabled (bool, default True) + weights
(AdaptiveWeights, factory default). Phase 3 persists to
ProjectSettings.adaptive_settings JSONB.

Third piece of ADR-069 Phase 1 (Retrofit-Plan step 1).
adaptive_context.py is now 3 classes, ~140 LOC (under RULE-04 cap)."
```

---

### Task 4: `AdaptiveContextProvider` Protocol + conformance test

**Files:**
- Modify: `packages/core/narrare_core/ai_invocation/contracts.py` (append Protocol)
- Test: `tests/unit/core/ai_invocation/test_adaptive_provider_protocol.py` (new file)

**Interfaces:**
- Consumes: `AdaptiveContext` + `AdaptiveSettings` from Tasks 2+3, `UUID` from stdlib.
- Produces: `AdaptiveContextProvider` Protocol with two async methods:
  - `async def get_context(self, user_id: UUID, project_id: UUID) -> AdaptiveContext`
  - `async def get_settings(self, user_id: UUID, project_id: UUID) -> AdaptiveSettings`
  Tasks 6 and 7 import this Protocol.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/core/ai_invocation/test_adaptive_provider_protocol.py`:

```python
"""Protocol conformance tests for AdaptiveContextProvider.

Covers: a complete Fake satisfies the Protocol; an incomplete class
does not; the Fake methods return the documented types.

See: ADR-069, ADR-067 (KBContextProvider pattern mirror),
CONSTRAINTS.md RULE-03.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare_core.ai_invocation.adaptive_context import (
    AdaptiveContext,
    AdaptiveSettings,
)
from narrare_core.ai_invocation.contracts import AdaptiveContextProvider


class FakeAdaptiveContextProvider:
    """Complete AdaptiveContextProvider implementation for tests."""

    def __init__(
        self,
        context: AdaptiveContext | None = None,
        settings: AdaptiveSettings | None = None,
    ) -> None:
        self._context = context
        self._settings = settings
        self.context_calls: list[tuple[object, object]] = []
        self.settings_calls: list[tuple[object, object]] = []

    async def get_context(self, user_id: object, project_id: object) -> AdaptiveContext:
        self.context_calls.append((user_id, project_id))
        if self._context is not None:
            return self._context
        return AdaptiveContext(user_id=user_id, project_id=project_id)  # type: ignore[arg-type]

    async def get_settings(self, user_id: object, project_id: object) -> AdaptiveSettings:
        self.settings_calls.append((user_id, project_id))
        return self._settings or AdaptiveSettings()


def _make_context() -> AdaptiveContext:
    return AdaptiveContext(
        user_id=uuid4(),
        project_id=uuid4(),
        preference_text="prefers dark prose",
        voice_profiles_text="**Alice**: terse",
    )


class TestAdaptiveContextProviderProtocol:
    """AdaptiveContextProvider protocol conformance."""

    def test_fake_satisfies_protocol(self) -> None:
        """FakeAdaptiveContextProvider has both required async methods."""
        fake = FakeAdaptiveContextProvider()
        assert hasattr(fake, "get_context")
        assert hasattr(fake, "get_settings")
        assert callable(fake.get_context)
        assert callable(fake.get_settings)

    @pytest.mark.asyncio
    async def test_get_context_returns_adaptive_context(self) -> None:
        fake = FakeAdaptiveContextProvider(context=_make_context())
        result = await fake.get_context(user_id=uuid4(), project_id=uuid4())
        assert isinstance(result, AdaptiveContext)
        assert result.preference_text == "prefers dark prose"
        assert len(fake.context_calls) == 1

    @pytest.mark.asyncio
    async def test_get_settings_returns_adaptive_settings(self) -> None:
        fake = FakeAdaptiveContextProvider(settings=AdaptiveSettings(enabled=False))
        result = await fake.get_settings(user_id=uuid4(), project_id=uuid4())
        assert isinstance(result, AdaptiveSettings)
        assert result.enabled is False
        assert len(fake.settings_calls) == 1

    def test_incomplete_does_not_satisfy(self) -> None:
        """Class missing get_settings does not satisfy the Protocol."""

        class OnlyGetContext:
            async def get_context(self, user_id: object, project_id: object) -> AdaptiveContext:
                del user_id, project_id
                return AdaptiveContext(user_id=uuid4(), project_id=uuid4())

        fake = OnlyGetContext()
        assert not hasattr(fake, "get_settings") or not callable(
            getattr(fake, "get_settings", None)
        )

    @pytest.mark.asyncio
    async def test_protocol_runtime_checkable_with_fake(self) -> None:
        """Duck-type shape verification (Protocol is implicit)."""
        fake = FakeAdaptiveContextProvider()
        assert callable(getattr(fake, "get_context", None))
        assert callable(getattr(fake, "get_settings", None))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/core/ai_invocation/test_adaptive_provider_protocol.py -v`
Expected: FAIL with `ImportError: cannot import name 'AdaptiveContextProvider' from 'narrare_core.ai_invocation.contracts'`.

- [ ] **Step 3: Write minimal implementation**

Modify `packages/core/narrare_core/ai_invocation/contracts.py`. Update the `TYPE_CHECKING` block at the top:

```python
if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.ai_invocation.adaptive_context import (
        AdaptiveContext,
        AdaptiveSettings,
    )
    from narrare_core.ai_invocation.budgets import OutputBudgetDecision
    from narrare_core.ai_invocation.models import (
        FeatureInvocationEvidence,
        PromptInvocationContext,
        ValidationResult,
    )
    from narrare_core.profiles.models import ProjectWritingProfile
    from narrare_core.prompts.composer import ComposedPrompt
```

Append the Protocol at the end of the file (after `ProfileProvider`):

```python


class AdaptiveContextProvider(Protocol):
    """Assembles an ``AdaptiveContext`` for an AI invocation.

    Consolidates data from:
    - ``PreferenceProfile`` (LEARN-001 / ADR-033 / mem0) via
      :class:`~narrare_core.memory.protocols.PreferenceProvider`.
    - ``ProjectWritingProfile`` (ADR-040; contains
      ``CharacterVoiceProfile`` instances) via ``ProfileProvider``.
    - ``AdaptiveSettings`` (ADR-069) via the persistence layer.

    The provider is **consumer-agnostic** — it does not know which AI
    operation consumes the data. Consumer-specific logic (e.g.,
    voice-fidelity scoring for Dialogue Coach) belongs in the
    respective service or agent.

    Backend implementations may perform I/O (mem0, DB) and MUST degrade
    gracefully (ADR-038 D7): when preferences or voice profiles are
    missing, return an ``AdaptiveContext`` with empty text fields but
    correct ``user_id`` / ``project_id``. Raise only for programmer
    errors (e.g., corrupted settings JSON); never for missing data.

    Mirrors the :class:`KBContextProvider` pattern from ADR-067 —
    a thin Core Protocol with a Backend composer impl that folds
    multiple existing sources into one canonical bundle.

    See:
        ADR-069 Decision 3 (Provider vs Service separation),
        ADR-067 (KBContextProvider precedent),
        CONSTRAINTS.md RULE-07 (Core contracts only depend on Core).
    """

    async def get_context(
        self,
        user_id: UUID,
        project_id: UUID,
    ) -> AdaptiveContext:
        """Return the consolidated AdaptiveContext for user+project.

        Args:
            user_id: The user identifier.
            project_id: The project identifier.

        Returns:
            An AdaptiveContext. Even when no preferences or voice
            profiles exist, a valid object with empty text fields is
            returned (graceful degradation).
        """
        ...

    async def get_settings(
        self,
        user_id: UUID,
        project_id: UUID,
    ) -> AdaptiveSettings:
        """Load the persisted AdaptiveSettings for user+project.

        Args:
            user_id: The user identifier.
            project_id: The project identifier.

        Returns:
            The stored settings, or default settings
            (``AdaptiveSettings()``) if none are persisted yet.
        """
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/core/ai_invocation/test_adaptive_provider_protocol.py -v`
Expected: PASS — all 5 tests green.

- [ ] **Step 5: Run full check suite**

Run: `just check`
Expected: All 9 step groups pass.

- [ ] **Step 6: Commit**

```bash
git add packages/core/narrare_core/ai_invocation/contracts.py \
        tests/unit/core/ai_invocation/test_adaptive_provider_protocol.py
git commit -m "feat(core): add AdaptiveContextProvider Protocol

New Core Protocol with two async methods: get_context() and
get_settings(). Mirrors ADR-067 KBContextProvider pattern —
Core contract consumed by the Core enricher (Task 6), Backend impl
composes PreferenceProvider + ProfileProvider (Task 7).

ADR-069 Decision 3 / Retrofit-Plan step 2.
No runtime behaviour change yet — no caller wires the Protocol."
```

---

### Task 5: `LLMIntent.DIALOGUE_COACH` enum + docs entry + variable registration

**Files:**
- Modify: `packages/core/narrare_core/llm/intents/_enums.py` (add enum member)
- Create: `packages/core/narrare_core/llm/intents/_docs_ai_assist.py`
- Modify: `packages/core/narrare_core/llm/intents/_docs.py` (import + spread)
- Modify: `packages/core/narrare_core/prompts/variable_registry.py` (register `characters` + `text_to_analyze`)
- Test: `tests/unit/core/llm/intents/test_dialogue_coach_intent.py` (new file)
- Test: `tests/unit/core/prompts/test_variable_registry_dialogue_coach.py` (new file)

**Interfaces:**
- Consumes: `LLMIntent` StrEnum, existing `_docs_*.py` aggregator pattern, existing `variable_registry` pattern.
- Produces:
  - `LLMIntent.DIALOGUE_COACH` — new enum member (additive, not yet routed).
  - `AI_ASSIST_INTENT_DOCS: dict[LLMIntent, str]` — picked up by `INTENT_DOCS`.
  - Two registered variables: `characters` (in `SYSTEM_VARS`), `text_to_analyze` (in `USER_CONTENT_VARS`).

**Note:** The route_table entry for `DIALOGUE_COACH` is Phase 4 step 17 — explicitly out of scope for this task. The enum member exists; nothing routes it yet. The architecture checker does NOT require every enum member to be in `INTENT_TO_CATEGORY` or `NON_ROUTEABLE_INTENTS` (verified: `_check_prompt_identity.py` only validates members that ARE declared in the manifest).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/core/llm/intents/test_dialogue_coach_intent.py`:

```python
"""Tests for the new DIALOGUE_COACH intent and its docs entry.

Phase 1 of ADR-069 adds the enum member + docs entry only.
Route-table registration is Phase 4.

See: ADR-069 Decision 5, CONSTRAINTS.md RULE-03.
"""

from __future__ import annotations

from narrare_core.llm.intents import INTENT_DOCS, LLMIntent


class TestDialogueCoachEnum:
    """LLMIntent.DIALOGUE_COACH — enum member exists."""

    def test_enum_value(self) -> None:
        assert LLMIntent.DIALOGUE_COACH == "dialogue_coach"

    def test_is_distinct_from_existing_intents(self) -> None:
        """Semantically distinct from ANALYSE, VOICE, WRITE, REWRITE."""
        assert LLMIntent.DIALOGUE_COACH is not LLMIntent.ANALYSE
        assert LLMIntent.DIALOGUE_COACH is not LLMIntent.VOICE
        assert LLMIntent.DIALOGUE_COACH is not LLMIntent.WRITE
        assert LLMIntent.DIALOGUE_COACH is not LLMIntent.REWRITE

    def test_str_representation(self) -> None:
        assert str(LLMIntent.DIALOGUE_COACH) == "dialogue_coach"


class TestDialogueCoachDocsEntry:
    """INTENT_DOCS has a verbose Scope/Input/Output/NOT entry."""

    def test_docs_entry_exists(self) -> None:
        assert LLMIntent.DIALOGUE_COACH in INTENT_DOCS

    def test_docs_entry_has_required_sections(self) -> None:
        docs = INTENT_DOCS[LLMIntent.DIALOGUE_COACH]
        assert "Scope:" in docs
        assert "Input:" in docs
        assert "Output:" in docs
        assert "NOT:" in docs

    def test_docs_entry_mentions_modes(self) -> None:
        """The docs entry references both analyze and improve modes."""
        docs = INTENT_DOCS[LLMIntent.DIALOGUE_COACH]
        assert "analyze" in docs.lower()
        assert "improve" in docs.lower()

    def test_docs_entry_mentions_adaptive_context(self) -> None:
        """The docs entry references adaptive context as a consumer."""
        docs = INTENT_DOCS[LLMIntent.DIALOGUE_COACH]
        assert "adaptive" in docs.lower() or "preference" in docs.lower()
```

Create `tests/unit/core/prompts/test_variable_registry_dialogue_coach.py`:

```python
"""Tests for the new DIALOGUE_COACH template variables.

ADR-069 Decision 10 requires {{characters}} and {{text_to_analyze}}
to be registered before the dialogue_coach template (Phase 4) can
reference them. This task registers both — Phase 4 wires them into
the template.

See: ADR-069 Decision 10, CONSTRAINTS.md RULE-22 §4.
"""

from __future__ import annotations

from narrare_core.prompts.variable_registry import (
    SYSTEM_VARS,
    USER_CONTENT_VARS,
    get_variable_classification,
    is_registered_variable,
)


class TestCharactersVariable:
    """{{characters}} — system-generated list of speaker names."""

    def test_registered_in_system_vars(self) -> None:
        assert "characters" in SYSTEM_VARS

    def test_is_registered_variable(self) -> None:
        assert is_registered_variable("characters")

    def test_classification_exists(self) -> None:
        c = get_variable_classification("characters")
        assert c is not None


class TestTextToAnalyzeVariable:
    """{{text_to_analyze}} — user-authored selection from the editor."""

    def test_registered_in_user_content_vars(self) -> None:
        """Per ADR-069 Decision 10: text_to_analyze is user content
        (must be XML-tag-wrapped in the Phase 4 template per RULE-22 §6)."""
        assert "text_to_analyze" in USER_CONTENT_VARS

    def test_is_registered_variable(self) -> None:
        assert is_registered_variable("text_to_analyze")

    def test_classification_exists(self) -> None:
        c = get_variable_classification("text_to_analyze")
        assert c is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/core/llm/intents/test_dialogue_coach_intent.py tests/unit/core/prompts/test_variable_registry_dialogue_coach.py -v`
Expected: FAIL — `AttributeError: DIALOGUE_COACH not found on LLMIntent`; `AssertionError: 'characters' not in SYSTEM_VARS`.

- [ ] **Step 3: Write minimal implementation**

**3a. Add the enum member.** Modify `packages/core/narrare_core/llm/intents/_enums.py`. Insert a new "AI assist operations" section between the "Chat" section (`RESEARCH`) and the "Embeddings" section (`EMBED`):

```python
    RESEARCH = "research"
    """Web research synthesis."""

    # ------------------------------------------------------------------
    # AI assist operations — writer-facing assistance (ASSIST-* features)
    # ------------------------------------------------------------------

    DIALOGUE_COACH = "dialogue_coach"
    """Analyse or improve selected dialogue (ASSIST-004)."""

    # ------------------------------------------------------------------
    # Embeddings (handled separately via embeddings.py)
    # ------------------------------------------------------------------

    EMBED = "embed"
    """Text embedding (not routed via gateway)."""
```

**3b. Create the docs module.** Create `packages/core/narrare_core/llm/intents/_docs_ai_assist.py`:

```python
"""Verbatim intent documentation — AI-assist operations category.

Full original docstring text (Scope/Input/Output/NOT) for ASSIST-*
intents. Aggregated into :data:`narrare_core.llm.intents.INTENT_DOCS`.

Split into its own category module per RULE-04 (mirrors
``_docs_analysis.py``, ``_docs_writing.py``, etc.).
"""

from __future__ import annotations

from narrare_core.llm.intents._enums import LLMIntent

AI_ASSIST_INTENT_DOCS: dict[LLMIntent, str] = {
    LLMIntent.DIALOGUE_COACH: """\
Dialogue coaching — analyse and improve selected dialogue.

Scope: Dual-mode dialogue assistance. ``analyze`` mode identifies
issues (voice mismatch, subtext absence, exposition overload, tag
overuse, redundancy, unnatural cadence, inconsistency) with severity
and speaker attribution. ``improve`` mode additionally proposes one
or more ``DialogueAlternative`` rewrites per flagged issue. Consumes
``AdaptiveContext`` (PreferenceProfile + CharacterVoiceProfile +
derived style_constraints / avoidance_patterns + weights) as the
first pilot user of the adaptive-context vertical. Uses only the
descriptive ``speech_summary`` (never ``voice_metrics`` — ADR-055/057
boundary preserved).
Input: {{text_to_analyze}} (user-selected dialogue passage),
{{characters}} (system-attributed speaker list),
{{user_preferences}}, {{style_constraints}},
{{avoidance_patterns}}, {{character_voice_profiles}},
{{mode}} ("analyze" | "improve").
Output: Structured DialogueCoachOutput — issues with severity and
speaker; alternatives when mode="improve".
NOT: General analysis (use ANALYSE). NOT: Voice profiling (use
VOICE with character_voice mode). NOT: Voice checking/drift scoring
(use VOICE with voice_check mode). NOT: Full-chapter rewrite (use
REWRITE). NOT: Inline suggestions (use SUGGEST).
""",
}
```

**3c. Update the aggregator.** Modify `packages/core/narrare_core/llm/intents/_docs.py`:

Add the import after the existing category imports:

```python
from narrare_core.llm.intents._docs_ai_assist import AI_ASSIST_INTENT_DOCS
from narrare_core.llm.intents._docs_analysis import ANALYSIS_INTENT_DOCS
from narrare_core.llm.intents._docs_chat import CHAT_INTENT_DOCS
from narrare_core.llm.intents._docs_embed import EMBED_INTENT_DOCS
from narrare_core.llm.intents._docs_extraction import EXTRACTION_INTENT_DOCS
from narrare_core.llm.intents._docs_generation import GENERATION_INTENT_DOCS
from narrare_core.llm.intents._docs_kb import KB_INTENT_DOCS
from narrare_core.llm.intents._docs_planning import PLANNING_INTENT_DOCS
from narrare_core.llm.intents._docs_writing import WRITING_INTENT_DOCS
```

Update the `INTENT_DOCS` dict literal to spread the new mapping (between `CHAT_INTENT_DOCS` and `EMBED_INTENT_DOCS`):

```python
INTENT_DOCS: dict[LLMIntent, str] = {
    **WRITING_INTENT_DOCS,
    **ANALYSIS_INTENT_DOCS,
    **KB_INTENT_DOCS,
    **PLANNING_INTENT_DOCS,
    **GENERATION_INTENT_DOCS,
    **EXTRACTION_INTENT_DOCS,
    **CHAT_INTENT_DOCS,
    **AI_ASSIST_INTENT_DOCS,
    **EMBED_INTENT_DOCS,
}
```

**3d. Register the variables.** Modify `packages/core/narrare_core/prompts/variable_registry.py`:

Add `"text_to_analyze"` to `USER_CONTENT_VARS`:

```python
USER_CONTENT_VARS: frozenset[str] = frozenset(
    {
        "existing_content",
        "chapter_text",
        "chapter_texts",
        "entry_content",
        "selection_text",
        "context_before",
        "context_after",
        "text_before",
        "text_after",
        "existing_answers",
        "author_instructions",
        "candidate_pairs",
        "conversation_history",
        "entity_name",
        "entity_current_content",
        "entity_body",
        # ADR-069: user-authored dialogue selection for DIALOGUE_COACH.
        # Must be XML-tag-wrapped in the Phase 4 template per RULE-22 §6.
        "text_to_analyze",
    }
)
```

Add `"characters"` to `SYSTEM_VARS` (insert immediately after `character_voice_profiles`):

```python
        "character_voice_profiles",
        # ADR-069: system-attributed speaker list for DIALOGUE_COACH.
        # Produced by DialogueParser-backed attribution (ADR-055 D3).
        "characters",
        "character_name",
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/core/llm/intents/test_dialogue_coach_intent.py tests/unit/core/prompts/test_variable_registry_dialogue_coach.py -v`
Expected: PASS — all 11 tests green.

- [ ] **Step 5: Run full check suite**

Run: `just check`
Expected: All 9 step groups pass.

- [ ] **Step 6: Commit**

```bash
git add packages/core/narrare_core/llm/intents/_enums.py \
        packages/core/narrare_core/llm/intents/_docs_ai_assist.py \
        packages/core/narrare_core/llm/intents/_docs.py \
        packages/core/narrare_core/prompts/variable_registry.py \
        tests/unit/core/llm/intents/test_dialogue_coach_intent.py \
        tests/unit/core/prompts/test_variable_registry_dialogue_coach.py
git commit -m "feat(core): add DIALOGUE_COACH intent + characters/text_to_analyze variables

- LLMIntent.DIALOGUE_COACH enum member (additive; not yet routed —
  route_table entry is Phase 4 step 17)
- _docs_ai_assist.py: verbose Scope/Input/Output/NOT entry
- variable_registry: characters in SYSTEM_VARS, text_to_analyze in
  USER_CONTENT_VARS (text_to_analyze requires XML-tag wrapping per
  RULE-22 §6 when the Phase 4 template references it)

ADR-069 Decision 5 + Decision 10 / Retrofit-Plan steps 3+4.
No runtime behaviour change yet — no caller routes DIALOGUE_COACH
and no template references the new variables."
```

---

### Task 6: `AdaptiveContextEnricher` (Core)

**Files:**
- Create: `packages/core/narrare_core/ai_invocation/enrichers/adaptive.py`
- Modify: `packages/core/narrare_core/ai_invocation/enrichers/__init__.py` (export the new class)
- Test: `tests/unit/core/ai_invocation/test_adaptive_enricher.py` (new file)

**Interfaces:**
- Consumes:
  - `AdaptiveContext`, `AdaptiveSettings` from Tasks 2+3
  - `AdaptiveContextProvider` Protocol from Task 4
  - `PromptInvocationContext` from `ai_invocation.models` (existing)
- Produces: `AdaptiveContextEnricher` — Core enricher with constructor `__init__(self, adaptive_provider: AdaptiveContextProvider | None)` and async `enrich(self, context: PromptInvocationContext) -> PromptInvocationContext`. Writes four `dynamic_inputs` keys: `user_preferences`, `style_constraints`, `avoidance_patterns`, `character_voice_profiles`. Tasks 8 and 9 import this class.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/core/ai_invocation/test_adaptive_enricher.py`:

```python
"""Tests for AdaptiveContextEnricher — the single canonical writer of
all four adaptive prompt variables.

Covers: success path, no provider, missing IDs, provider failure,
disabled settings, no signal, all 4 variables written, immutability.

See: ADR-069 Decision 1, ADR-038 D7 (graceful degradation),
CONSTRAINTS.md RULE-03/RULE-06/RULE-11.
"""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

import pytest

from narrare_core.ai_invocation.adaptive_context import (
    AdaptiveContext,
    AdaptiveSettings,
    AdaptiveWeights,
)
from narrare_core.ai_invocation.enrichers.adaptive import (
    AVOIDANCE_PATTERNS_KEY,
    CHARACTER_VOICE_PROFILES_KEY,
    PREFERENCE_KEY,
    STYLE_CONSTRAINTS_KEY,
    AdaptiveContextEnricher,
)
from narrare_core.ai_invocation.models import PromptInvocationContext
from narrare_core.llm.intents import LLMIntent


class FakeAdaptiveProvider:
    """Async fake AdaptiveContextProvider with programmable results.

    Mirrors the FakePreferenceProvider pattern — real async methods
    avoid the AsyncMock(spec=...) pitfall. Records calls for assertions.
    """

    def __init__(
        self,
        *,
        context: AdaptiveContext | None = None,
        settings: AdaptiveSettings | None = None,
        context_raises: Exception | None = None,
        settings_raises: Exception | None = None,
    ) -> None:
        self._context = context
        self._settings = settings
        self._context_raises = context_raises
        self._settings_raises = settings_raises
        self.context_calls: list[tuple[object, object]] = []
        self.settings_calls: list[tuple[object, object]] = []

    async def get_context(self, user_id: object, project_id: object) -> AdaptiveContext:
        self.context_calls.append((user_id, project_id))
        if self._context_raises is not None:
            raise self._context_raises
        return self._context or AdaptiveContext(
            user_id=cast("UUID", user_id),
            project_id=cast("UUID", project_id),
        )

    async def get_settings(self, user_id: object, project_id: object) -> AdaptiveSettings:
        self.settings_calls.append((user_id, project_id))
        if self._settings_raises is not None:
            raise self._settings_raises
        return self._settings or AdaptiveSettings()


def _make_context(**overrides: object) -> PromptInvocationContext:
    defaults: dict[str, object] = {
        "feature_id": "test/feature",
        "intent": LLMIntent.WRITE,
        "user_id": uuid4(),
        "project_id": uuid4(),
    }
    defaults.update(overrides)
    return PromptInvocationContext(**defaults)  # type: ignore[arg-type]


def _full_adaptive_context(user_id: object, project_id: object) -> AdaptiveContext:
    return AdaptiveContext(
        user_id=cast("UUID", user_id),
        project_id=cast("UUID", project_id),
        preference_text="prefers dark prose",
        voice_profiles_text="**Alice**: terse",
        style_constraints_text="- Short sentences",
        avoidance_patterns_text="- No passive voice",
        weights=AdaptiveWeights(),
        source_summary="3 voices, 12 preference events",
    )


class TestAdaptiveEnricherSuccess:
    """Happy path: provider returns full context; all 4 variables written."""

    @pytest.mark.asyncio
    async def test_all_four_variables_written(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        provider = FakeAdaptiveProvider(
            context=_full_adaptive_context(user_id, project_id),
        )
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)

        ctx = _make_context(user_id=user_id, project_id=project_id)
        result = await enricher.enrich(ctx)

        assert result.dynamic_inputs[PREFERENCE_KEY] == "prefers dark prose"
        assert result.dynamic_inputs[STYLE_CONSTRAINTS_KEY] == "- Short sentences"
        assert result.dynamic_inputs[AVOIDANCE_PATTERNS_KEY] == "- No passive voice"
        assert result.dynamic_inputs[CHARACTER_VOICE_PROFILES_KEY] == "**Alice**: terse"

    @pytest.mark.asyncio
    async def test_provider_called_once_with_context_ids(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        provider = FakeAdaptiveProvider(
            context=_full_adaptive_context(user_id, project_id),
        )
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)

        await enricher.enrich(_make_context(user_id=user_id, project_id=project_id))

        assert len(provider.context_calls) == 1
        assert provider.context_calls[0] == (user_id, project_id)
        assert len(provider.settings_calls) == 1


class TestAdaptiveEnricherNoProvider:
    """No provider wired — graceful no-op (ADR-038 D7)."""

    @pytest.mark.asyncio
    async def test_none_provider_returns_context_unchanged(self) -> None:
        enricher = AdaptiveContextEnricher(adaptive_provider=None)
        ctx = _make_context()
        result = await enricher.enrich(ctx)
        assert result is ctx  # unchanged
        assert result.dynamic_inputs == {}


class TestAdaptiveEnricherMissingIds:
    """user_id or project_id missing — graceful no-op with warning."""

    @pytest.mark.asyncio
    async def test_missing_user_id_returns_unchanged(self) -> None:
        provider = FakeAdaptiveProvider()
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)
        ctx = _make_context(user_id=None, project_id=uuid4())
        result = await enricher.enrich(ctx)
        assert result is ctx
        assert provider.context_calls == []

    @pytest.mark.asyncio
    async def test_missing_project_id_returns_unchanged(self) -> None:
        provider = FakeAdaptiveProvider()
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)
        ctx = _make_context(user_id=uuid4(), project_id=None)
        result = await enricher.enrich(ctx)
        assert result is ctx
        assert provider.context_calls == []


class TestAdaptiveEnricherProviderFailure:
    """Provider raises — graceful no-op with warning (RULE-11)."""

    @pytest.mark.asyncio
    async def test_context_provider_raises_returns_unchanged(self) -> None:
        provider = FakeAdaptiveProvider(
            context_raises=RuntimeError("mem0 down"),
        )
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)
        ctx = _make_context()
        result = await enricher.enrich(ctx)
        assert result is ctx
        assert result.dynamic_inputs == {}

    @pytest.mark.asyncio
    async def test_settings_provider_raises_returns_unchanged(self) -> None:
        """If settings fail to load, the enricher skips entirely —
        safer than running with default-enabled when user disabled."""
        provider = FakeAdaptiveProvider(
            context=_full_adaptive_context(uuid4(), uuid4()),
            settings_raises=RuntimeError("settings repo down"),
        )
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)
        ctx = _make_context()
        result = await enricher.enrich(ctx)
        assert result is ctx
        assert result.dynamic_inputs == {}


class TestAdaptiveEnricherDisabled:
    """AdaptiveSettings.enabled=False — graceful no-op."""

    @pytest.mark.asyncio
    async def test_disabled_settings_skips_injection(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        provider = FakeAdaptiveProvider(
            context=_full_adaptive_context(user_id, project_id),
            settings=AdaptiveSettings(enabled=False),
        )
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)
        ctx = _make_context(user_id=user_id, project_id=project_id)
        result = await enricher.enrich(ctx)
        assert result is ctx
        assert result.dynamic_inputs == {}


class TestAdaptiveEnricherNoSignal:
    """AdaptiveContext.has_any_signal=False — write empty strings.

    Even though no signal is present, the enricher writes the four keys
    with empty values so the variable engine resolves them (RULE-11
    graceful degradation — empty strings, not KeyError).
    """

    @pytest.mark.asyncio
    async def test_empty_context_writes_empty_strings(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        provider = FakeAdaptiveProvider(
            context=AdaptiveContext(user_id=user_id, project_id=project_id),
        )
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)
        ctx = _make_context(user_id=user_id, project_id=project_id)
        result = await enricher.enrich(ctx)

        assert result.dynamic_inputs[PREFERENCE_KEY] == ""
        assert result.dynamic_inputs[STYLE_CONSTRAINTS_KEY] == ""
        assert result.dynamic_inputs[AVOIDANCE_PATTERNS_KEY] == ""
        assert result.dynamic_inputs[CHARACTER_VOICE_PROFILES_KEY] == ""


class TestAdaptiveEnricherPartialSignal:
    """Only some signals present — only those keys get non-empty values."""

    @pytest.mark.asyncio
    async def test_only_preference_present(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        provider = FakeAdaptiveProvider(
            context=AdaptiveContext(
                user_id=user_id,
                project_id=project_id,
                preference_text="prefers dark prose",
            ),
        )
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)
        ctx = _make_context(user_id=user_id, project_id=project_id)
        result = await enricher.enrich(ctx)

        assert result.dynamic_inputs[PREFERENCE_KEY] == "prefers dark prose"
        assert result.dynamic_inputs[STYLE_CONSTRAINTS_KEY] == ""
        assert result.dynamic_inputs[AVOIDANCE_PATTERNS_KEY] == ""
        assert result.dynamic_inputs[CHARACTER_VOICE_PROFILES_KEY] == ""


class TestAdaptiveEnricherImmutability:
    """The original context is NOT mutated (RULE-03 immutable value flow)."""

    @pytest.mark.asyncio
    async def test_returns_new_instance(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        provider = FakeAdaptiveProvider(
            context=_full_adaptive_context(user_id, project_id),
        )
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)
        ctx = _make_context(user_id=user_id, project_id=project_id)
        original_dynamic_inputs = dict(ctx.dynamic_inputs)
        result = await enricher.enrich(ctx)

        assert result is not ctx
        # Original unchanged:
        assert ctx.dynamic_inputs == original_dynamic_inputs

    @pytest.mark.asyncio
    async def test_preserves_existing_dynamic_inputs(self) -> None:
        """Existing dynamic_inputs (e.g., from other enrichers) survive."""
        user_id = uuid4()
        project_id = uuid4()
        provider = FakeAdaptiveProvider(
            context=_full_adaptive_context(user_id, project_id),
        )
        enricher = AdaptiveContextEnricher(adaptive_provider=provider)
        ctx = _make_context(user_id=user_id, project_id=project_id)
        ctx = ctx.model_copy(update={"dynamic_inputs": {"existing_key": "kept"}})
        result = await enricher.enrich(ctx)

        assert result.dynamic_inputs["existing_key"] == "kept"
        assert PREFERENCE_KEY in result.dynamic_inputs


class TestAdaptiveEnricherProtocolConformance:
    """The enricher satisfies the ContextEnricher Protocol."""

    @pytest.mark.asyncio
    async def test_enrich_method_signature(self) -> None:
        enricher = AdaptiveContextEnricher(adaptive_provider=None)
        ctx = _make_context()
        result = await enricher.enrich(ctx)
        assert isinstance(result, PromptInvocationContext)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/core/ai_invocation/test_adaptive_enricher.py -v`
Expected: FAIL with `ImportError: cannot import name 'AdaptiveContextEnricher'`.

- [ ] **Step 3: Write minimal implementation**

Create `packages/core/narrare_core/ai_invocation/enrichers/adaptive.py`:

```python
"""Adaptive context enricher — single canonical writer of all four
adaptive prompt variables.

Replaces ``PreferenceContextEnricherImpl`` (ADR-038) per ADR-069
Decision 1. Where the old enricher wrote only ``user_preferences``,
this enricher consults the new ``AdaptiveContextProvider`` Protocol
and writes:

- ``dynamic_inputs["user_preferences"]``         <- AdaptiveContext.preference_text
- ``dynamic_inputs["style_constraints"]``        <- AdaptiveContext.style_constraints_text
- ``dynamic_inputs["avoidance_patterns"]``       <- AdaptiveContext.avoidance_patterns_text
- ``dynamic_inputs["character_voice_profiles"]`` <- AdaptiveContext.voice_profiles_text

Graceful degradation (ADR-038 D7):
- No provider -> return context unchanged.
- Missing user_id / project_id -> return context unchanged (warning).
- Provider raises -> return context unchanged (warning).
- AdaptiveSettings.enabled=False -> return context unchanged.
- AdaptiveContext.has_any_signal=False -> write all four keys with "".

See:
    ADR-069 Decision 1 (enricher swap), Decision 4 (applicability),
    ADR-038 D7 (graceful degradation),
    ADR-055/057 (voice_metrics never reach generation — only
    descriptive voice_profiles_text is written here),
    CONSTRAINTS.md RULE-03 / RULE-06 / RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from narrare_core.ai_invocation.contracts import AdaptiveContextProvider
    from narrare_core.ai_invocation.models import PromptInvocationContext

logger = structlog.get_logger(__name__)

#: Well-known key for preference text in dynamic_inputs.
PREFERENCE_KEY: str = "user_preferences"
#: Well-known key for derived style constraints.
STYLE_CONSTRAINTS_KEY: str = "style_constraints"
#: Well-known key for derived avoidance patterns.
AVOIDANCE_PATTERNS_KEY: str = "avoidance_patterns"
#: Well-known key for character voice profiles (descriptive text only).
CHARACTER_VOICE_PROFILES_KEY: str = "character_voice_profiles"


class AdaptiveContextEnricher:
    """Writes all four adaptive prompt variables via immutable model_copy.

    Single canonical writer per ADR-069 Decision 1. Replaces the
    single-variable ``PreferenceContextEnricherImpl``.

    Args:
        adaptive_provider: An ``AdaptiveContextProvider`` implementation,
            or ``None`` for a no-op enricher (graceful degradation when
            adaptivity is not configured — e.g., mem0 unavailable).

    Implements:
        ``ContextEnricher`` Protocol from ``ai_invocation.contracts``.
    """

    def __init__(self, adaptive_provider: AdaptiveContextProvider | None) -> None:
        self._provider = adaptive_provider

    async def enrich(self, context: PromptInvocationContext) -> PromptInvocationContext:
        """Enrich the context with adaptive data.

        Args:
            context: The current invocation context.

        Returns:
            A new ``PromptInvocationContext`` with all four adaptive
            ``dynamic_inputs`` keys set, or the original context
            unchanged when enrichment is not possible.
        """
        if self._provider is None:
            logger.debug(
                "adaptive_enricher_noop",
                reason="no_provider",
                feature_id=context.feature_id,
            )
            return context

        if context.user_id is None or context.project_id is None:
            logger.warning(
                "adaptive_enricher_missing_ids",
                feature_id=context.feature_id,
                has_user_id=context.user_id is not None,
                has_project_id=context.project_id is not None,
            )
            return context

        try:
            settings = await self._provider.get_settings(
                user_id=context.user_id,
                project_id=context.project_id,
            )
        except Exception:
            logger.warning(
                "adaptive_enricher_settings_failed",
                feature_id=context.feature_id,
                user_id=str(context.user_id),
                project_id=str(context.project_id),
                exc_info=True,
            )
            return context

        if not settings.enabled:
            logger.debug(
                "adaptive_enricher_disabled",
                feature_id=context.feature_id,
                user_id=str(context.user_id),
                project_id=str(context.project_id),
            )
            return context

        try:
            adaptive = await self._provider.get_context(
                user_id=context.user_id,
                project_id=context.project_id,
            )
        except Exception:
            logger.warning(
                "adaptive_enricher_context_failed",
                feature_id=context.feature_id,
                user_id=str(context.user_id),
                project_id=str(context.project_id),
                exc_info=True,
            )
            return context

        logger.debug(
            "adaptive_enricher_success",
            feature_id=context.feature_id,
            user_id=str(context.user_id),
            has_signal=adaptive.has_any_signal,
            preference_length=len(adaptive.preference_text),
            voice_profiles_length=len(adaptive.voice_profiles_text),
            style_constraints_length=len(adaptive.style_constraints_text),
            avoidance_length=len(adaptive.avoidance_patterns_text),
        )

        return context.model_copy(
            update={
                "dynamic_inputs": {
                    **context.dynamic_inputs,
                    PREFERENCE_KEY: adaptive.preference_text,
                    STYLE_CONSTRAINTS_KEY: adaptive.style_constraints_text,
                    AVOIDANCE_PATTERNS_KEY: adaptive.avoidance_patterns_text,
                    CHARACTER_VOICE_PROFILES_KEY: adaptive.voice_profiles_text,
                },
            },
        )
```

Update `packages/core/narrare_core/ai_invocation/enrichers/__init__.py` to export the new enricher (keep `PreferenceContextEnricherImpl` for now — Task 10 removes it):

```python
"""Enrichers for the AI invocation pipeline.

Enrichers add runtime context to a PromptInvocationContext before
prompt composition runs. Each enricher is a focused, single-responsibility
implementation of the ContextEnricher Protocol.

See:
    ADR-038, ADR-039, ADR-040, ADR-069, INFRA-013, CONSTRAINTS.md RULE-06.
"""

from narrare_core.ai_invocation.enrichers.adaptive import (
    AdaptiveContextEnricher,
)
from narrare_core.ai_invocation.enrichers.consistency import (
    KBConsistencyEnricher,
)
from narrare_core.ai_invocation.enrichers.kb_suggested import (
    KBSuggestedContextEnricher,
)
from narrare_core.ai_invocation.enrichers.preferences import (
    PreferenceContextEnricherImpl,
)

__all__ = [
    "AdaptiveContextEnricher",
    "KBConsistencyEnricher",
    "KBSuggestedContextEnricher",
    "PreferenceContextEnricherImpl",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/core/ai_invocation/test_adaptive_enricher.py -v`
Expected: PASS — all 14 tests green.

- [ ] **Step 5: Run full check suite**

Run: `just check`
Expected: All 9 step groups pass. The Architecture step's RULE-04 check should confirm `adaptive.py` is under 150 LOC. If it overflows, split the four well-known key constants into a sibling `_keys.py` module before committing — do NOT compress code or delete docstrings (RULE-04 explicitly forbids compression).

- [ ] **Step 6: Commit**

```bash
git add packages/core/narrare_core/ai_invocation/enrichers/adaptive.py \
        packages/core/narrare_core/ai_invocation/enrichers/__init__.py \
        tests/unit/core/ai_invocation/test_adaptive_enricher.py
git commit -m "feat(core): add AdaptiveContextEnricher — single canonical writer

New Core enricher writes all four adaptive prompt variables
(user_preferences, style_constraints, avoidance_patterns,
character_voice_profiles) via immutable model_copy. Consumes the
AdaptiveContextProvider Protocol (Task 4).

Graceful degradation (ADR-038 D7):
- No provider / missing IDs / provider failure / disabled / no signal
  -> return context unchanged OR write empty strings.
- voice_metrics never enter dynamic_inputs (ADR-055/057 boundary).

ADR-069 Decision 1 / Retrofit-Plan step 5.
Production wiring lands in Task 8; the old class is removed in Task 10."
```

---

### Task 7: Backend `AdaptiveContextProviderImpl` (Phase 2 scaffold)

**Files:**
- Create: `apps/api/narrare/adaptive/__init__.py`
- Create: `apps/api/narrare/adaptive/adaptive_context_provider.py`
- Test: `tests/unit/api/adaptive/__init__.py`
- Test: `tests/unit/api/adaptive/test_adaptive_context_provider.py`

**Interfaces:**
- Consumes:
  - `AdaptiveContext`, `AdaptiveSettings`, `AdaptiveWeights` from Tasks 1-3
  - `AdaptiveContextProvider` Protocol from Task 4
  - `PreferenceProvider` Protocol from `narrare_core.memory.protocols` (existing)
  - `ProfileProvider` Protocol from `narrare_core.ai_invocation.contracts` (existing)
- Produces: `AdaptiveContextProviderImpl` — Backend impl with constructor
  `__init__(self, preference_provider: PreferenceProvider | None, profile_provider: ProfileProvider | None)`
  and the two Protocol methods. Phase 2 scaffold: `get_settings()` returns `AdaptiveSettings()` defaults; `get_context()` derives `style_constraints_text` + `avoidance_patterns_text` from `PreferenceProfile` data (heuristic, tunable in Phase 3 via Eval). Task 8 wires this class into production DI.

**Phase 2 scope:**
- Reads `PreferenceProvider.get_preferences()` for `preference_text` + derived constraints/avoidance.
- Reads `ProfileProvider.get_profile()` for `voice_profiles_text` (descriptive `formatted_voice_profiles` only — never `voice_metrics`).
- Returns default `AdaptiveSettings()` (no persistence).
- Does NOT persist `AdaptiveSettings` to `ProjectSettings.adaptive_settings` JSONB (Phase 3).
- Does NOT write `invocation_evidence.adaptive_*` columns (Phase 3).

- [ ] **Step 1: Write the failing test**

Create `tests/unit/api/adaptive/__init__.py` (empty file).

Create `tests/unit/api/adaptive/test_adaptive_context_provider.py`:

```python
"""Tests for the Backend AdaptiveContextProviderImpl (Phase 2 scaffold).

Phase 2 scope: composes PreferenceProvider + ProfileProvider;
returns default AdaptiveSettings (no persistence); derives simple
style_constraints_text + avoidance_patterns_text from PreferenceProfile.

Phase 3 will add: ProjectSettings.adaptive_settings JSONB persistence,
invocation_evidence.adaptive_* snapshot writes, richer derivation
tuned by Eval.

See: ADR-069 Decision 3, ADR-067 (KBContextProvider pattern),
CONSTRAINTS.md RULE-07/RULE-08/RULE-11.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest

from narrare.adaptive.adaptive_context_provider import (
    AdaptiveContextProviderImpl,
)
from narrare_core.ai_invocation.adaptive_context import (
    AdaptiveContext,
    AdaptiveSettings,
)
from narrare_core.memory.models import PreferenceProfile
from narrare_core.profiles.models import (
    CharacterVoiceProfile,
    ProjectWritingProfile,
)


class FakePreferenceProvider:
    """Async fake PreferenceProvider (mirrors production fake pattern)."""

    def __init__(
        self,
        profile: PreferenceProfile | None = None,
        *,
        raises: Exception | None = None,
    ) -> None:
        self._profile = profile
        self._raises = raises
        self.calls: list[tuple[object, object]] = []

    async def get_preferences(
        self,
        user_id: object,
        project_id: object,
    ) -> PreferenceProfile:
        self.calls.append((user_id, project_id))
        if self._raises is not None:
            raise self._raises
        if self._profile is None:
            return PreferenceProfile(
                user_id=cast("UUID", user_id),
                project_id=cast("UUID", project_id),
                event_count=0,
                confidence=0.0,
                style={},
                content={},
                constraints=[],
                last_updated=datetime.now(UTC),
            )
        return self._profile

    async def reset(self, user_id: object, project_id: object) -> None:
        del user_id, project_id


class FakeProfileProvider:
    """Async fake ProfileProvider (Core Protocol from contracts.py)."""

    def __init__(
        self,
        profile: ProjectWritingProfile | None = None,
        *,
        raises: Exception | None = None,
    ) -> None:
        self._profile = profile
        self._raises = raises
        self.calls: list[object] = []

    async def get_profile(self, project_id: object) -> ProjectWritingProfile | None:
        self.calls.append(project_id)
        if self._raises is not None:
            raise self._raises
        return self._profile


def _make_preference_profile(
    user_id: object,
    project_id: object,
    *,
    style: dict[str, str] | None = None,
    constraints: list[str] | None = None,
) -> PreferenceProfile:
    return PreferenceProfile(
        user_id=cast("UUID", user_id),
        project_id=cast("UUID", project_id),
        event_count=5,
        confidence=0.8,
        style=style if style is not None else {"tone": "prefers dark prose"},
        content={},
        constraints=constraints if constraints is not None else ["avoid passive voice"],
        last_updated=datetime.now(UTC),
    )


def _make_writing_profile() -> ProjectWritingProfile:
    return ProjectWritingProfile(
        writing_language="en",
        genre="Fantasy",
        character_voice_profiles=(
            CharacterVoiceProfile(
                character_id="ch-1",
                name="Alice",
                speech_summary="terse, ironic",
            ),
        ),
    )


class TestProtocolConformance:
    """AdaptiveContextProviderImpl satisfies the Core Protocol."""

    def test_satisfies_protocol(self) -> None:
        impl = AdaptiveContextProviderImpl(
            preference_provider=None,
            profile_provider=None,
        )
        assert hasattr(impl, "get_context")
        assert hasattr(impl, "get_settings")
        assert callable(impl.get_context)
        assert callable(impl.get_settings)


class TestGetSettingsPhase2Scaffold:
    """Phase 2: get_settings returns defaults (no persistence)."""

    @pytest.mark.asyncio
    async def test_returns_default_adaptive_settings(self) -> None:
        impl = AdaptiveContextProviderImpl(
            preference_provider=None,
            profile_provider=None,
        )
        settings = await impl.get_settings(user_id=uuid4(), project_id=uuid4())
        assert isinstance(settings, AdaptiveSettings)
        assert settings.enabled is True
        assert settings.weights.preference == 0.7


class TestGetContextHappyPath:
    """Both providers return data — full AdaptiveContext assembled."""

    @pytest.mark.asyncio
    async def test_assembles_preference_and_voice(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        impl = AdaptiveContextProviderImpl(
            preference_provider=FakePreferenceProvider(
                _make_preference_profile(user_id, project_id),
            ),
            profile_provider=FakeProfileProvider(_make_writing_profile()),
        )

        ctx = await impl.get_context(user_id=user_id, project_id=project_id)

        assert isinstance(ctx, AdaptiveContext)
        assert ctx.user_id == user_id
        assert ctx.project_id == project_id
        # preference_text comes from PreferenceProfile.to_prompt_text():
        assert "dark prose" in ctx.preference_text.lower() or ctx.preference_text != ""
        # voice_profiles_text comes from formatted_voice_profiles (descriptive only):
        assert "Alice" in ctx.voice_profiles_text
        # ADR-055/057 boundary — no voice_metrics in the result:
        assert not hasattr(ctx, "voice_metrics")
        # Derived fields are non-empty when PreferenceProfile has style/constraints:
        assert ctx.style_constraints_text != ""
        assert ctx.avoidance_patterns_text != ""

    @pytest.mark.asyncio
    async def test_source_summary_mentions_signal_sources(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        impl = AdaptiveContextProviderImpl(
            preference_provider=FakePreferenceProvider(
                _make_preference_profile(user_id, project_id),
            ),
            profile_provider=FakeProfileProvider(_make_writing_profile()),
        )

        ctx = await impl.get_context(user_id=user_id, project_id=project_id)
        # source_summary is a heuristic human-readable string; it should
        # reference at least one signal source.
        assert ctx.source_summary != ""


class TestGetContextGracefulDegradation:
    """RULE-11: missing data does NOT crash — returns empty fields."""

    @pytest.mark.asyncio
    async def test_no_preference_provider(self) -> None:
        impl = AdaptiveContextProviderImpl(
            preference_provider=None,
            profile_provider=FakeProfileProvider(_make_writing_profile()),
        )
        ctx = await impl.get_context(user_id=uuid4(), project_id=uuid4())
        assert ctx.preference_text == ""
        assert ctx.style_constraints_text == ""
        assert ctx.avoidance_patterns_text == ""
        # Voice profiles still present:
        assert "Alice" in ctx.voice_profiles_text

    @pytest.mark.asyncio
    async def test_no_profile_provider(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        impl = AdaptiveContextProviderImpl(
            preference_provider=FakePreferenceProvider(
                _make_preference_profile(user_id, project_id),
            ),
            profile_provider=None,
        )
        ctx = await impl.get_context(user_id=user_id, project_id=project_id)
        assert ctx.voice_profiles_text == ""
        # Preferences still present:
        assert ctx.preference_text != ""

    @pytest.mark.asyncio
    async def test_no_providers_at_all(self) -> None:
        impl = AdaptiveContextProviderImpl(
            preference_provider=None,
            profile_provider=None,
        )
        ctx = await impl.get_context(user_id=uuid4(), project_id=uuid4())
        assert ctx.preference_text == ""
        assert ctx.voice_profiles_text == ""
        assert ctx.style_constraints_text == ""
        assert ctx.avoidance_patterns_text == ""
        assert ctx.has_any_signal is False

    @pytest.mark.asyncio
    async def test_preference_provider_raises_returns_empty_preference(self) -> None:
        """RULE-11: provider failure does NOT crash; returns empty fields."""
        impl = AdaptiveContextProviderImpl(
            preference_provider=FakePreferenceProvider(raises=RuntimeError("mem0 down")),
            profile_provider=FakeProfileProvider(_make_writing_profile()),
        )
        ctx = await impl.get_context(user_id=uuid4(), project_id=uuid4())
        # Provider failed — preference-derived fields are empty:
        assert ctx.preference_text == ""
        assert ctx.style_constraints_text == ""
        assert ctx.avoidance_patterns_text == ""
        # Profile provider still succeeded — voice profiles present:
        assert "Alice" in ctx.voice_profiles_text

    @pytest.mark.asyncio
    async def test_profile_provider_raises_returns_empty_voice(self) -> None:
        """RULE-11: profile provider failure does NOT crash."""
        user_id = uuid4()
        project_id = uuid4()
        impl = AdaptiveContextProviderImpl(
            preference_provider=FakePreferenceProvider(
                _make_preference_profile(user_id, project_id),
            ),
            profile_provider=FakeProfileProvider(raises=RuntimeError("DB down")),
        )
        ctx = await impl.get_context(user_id=user_id, project_id=project_id)
        assert ctx.voice_profiles_text == ""
        # Preference provider still succeeded:
        assert ctx.preference_text != ""

    @pytest.mark.asyncio
    async def test_profile_provider_returns_none(self) -> None:
        """ProfileProvider returns None for project without writing profile."""
        user_id = uuid4()
        project_id = uuid4()
        impl = AdaptiveContextProviderImpl(
            preference_provider=FakePreferenceProvider(
                _make_preference_profile(user_id, project_id),
            ),
            profile_provider=FakeProfileProvider(profile=None),
        )
        ctx = await impl.get_context(user_id=user_id, project_id=project_id)
        assert ctx.voice_profiles_text == ""
        assert ctx.preference_text != ""


class TestDerivationHeuristic:
    """Phase 2 derivation: style_constraints from PreferenceProfile.style,
    avoidance_patterns from PreferenceProfile.constraints.

    The exact format is heuristic and tunable in Phase 3 via Eval.
    Phase 2 establishes the contract: non-empty when source data exists.
    """

    @pytest.mark.asyncio
    async def test_style_dict_produces_constraints_text(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        impl = AdaptiveContextProviderImpl(
            preference_provider=FakePreferenceProvider(
                _make_preference_profile(
                    user_id,
                    project_id,
                    style={"tone": "dark", "pov": "first-person"},
                    constraints=[],
                ),
            ),
            profile_provider=None,
        )
        ctx = await impl.get_context(user_id=user_id, project_id=project_id)
        assert ctx.style_constraints_text != ""
        # Avoidance empty since no constraints:
        assert ctx.avoidance_patterns_text == ""

    @pytest.mark.asyncio
    async def test_constraints_list_produces_avoidance_text(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        impl = AdaptiveContextProviderImpl(
            preference_provider=FakePreferenceProvider(
                _make_preference_profile(
                    user_id,
                    project_id,
                    style={},
                    constraints=["no passive voice", "no adverbs"],
                ),
            ),
            profile_provider=None,
        )
        ctx = await impl.get_context(user_id=user_id, project_id=project_id)
        assert ctx.avoidance_patterns_text != ""
        # Style empty since no style dict entries:
        assert ctx.style_constraints_text == ""

    @pytest.mark.asyncio
    async def test_empty_preference_profile_produces_empty_derived(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        impl = AdaptiveContextProviderImpl(
            preference_provider=FakePreferenceProvider(
                _make_preference_profile(
                    user_id,
                    project_id,
                    style={},
                    constraints=[],
                ),
            ),
            profile_provider=None,
        )
        ctx = await impl.get_context(user_id=user_id, project_id=project_id)
        assert ctx.style_constraints_text == ""
        assert ctx.avoidance_patterns_text == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/api/adaptive/test_adaptive_context_provider.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'narrare.adaptive'`.

- [ ] **Step 3: Write minimal implementation**

Create `apps/api/narrare/adaptive/__init__.py`:

```python
"""Adaptive Context Backend domain.

Phase 2 (ADR-069): scaffold provider impl only.
Phase 3 will add: contracts.py (AdaptiveContextServiceProtocol),
schemas.py, service.py, router.py, dependencies.py, repository.py.
"""
```

Create `apps/api/narrare/adaptive/adaptive_context_provider.py`:

```python
"""Backend AdaptiveContextProvider implementation.

Composes the existing ``PreferenceProvider`` (mem0-backed, ADR-033)
and ``ProfileProvider`` (Core Protocol from ``ai_invocation.contracts``)
into a single ``AdaptiveContext`` bundle for the Core
``AdaptiveContextEnricher``.

Mirrors the ADR-067 ``KBContextProvider`` pattern: Core Protocol +
Backend composer impl.

Phase 2 scaffold (ADR-069 Retrofit-Plan step 6):
- Loads ``PreferenceProfile`` via ``PreferenceProvider.get_preferences``.
- Loads ``ProjectWritingProfile`` via ``ProfileProvider.get_profile``.
- Derives ``style_constraints_text`` from ``PreferenceProfile.style`` dict
  (heuristic bullet list — tunable in Phase 3 via Eval).
- Derives ``avoidance_patterns_text`` from ``PreferenceProfile.constraints``
  list (heuristic bullet list — tunable in Phase 3 via Eval).
- Returns default ``AdaptiveSettings()`` (no persistence; Phase 3 reads
  from ``ProjectSettings.adaptive_settings`` JSONB).
- Does NOT write ``invocation_evidence.adaptive_*`` columns (Phase 3).

ADR-055/057 boundary: this impl copies ONLY the descriptive
``formatted_voice_profiles`` text into ``AdaptiveContext.voice_profiles_text``.
The numeric ``voice_metrics`` are never read, copied, or returned.

See:
    ADR-069 Decision 3 (Provider Pattern),
    ADR-067 (KBContextProvider precedent),
    ADR-033 (mem0 boundary via PreferenceProvider),
    ADR-055/057 (voice_metrics boundary),
    CONSTRAINTS.md RULE-07 / RULE-08 / RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.ai_invocation.adaptive_context import (
        AdaptiveContext,
        AdaptiveSettings,
    )
    from narrare_core.ai_invocation.contracts import ProfileProvider
    from narrare_core.memory.protocols import PreferenceProvider

logger = structlog.get_logger(__name__)


class AdaptiveContextProviderImpl:
    """Composes PreferenceProvider + ProfileProvider into AdaptiveContext.

    Args:
        preference_provider: mem0-backed provider (``None`` for graceful
            no-op — e.g., mem0 not installed).
        profile_provider: Core ``ProfileProvider`` for the
            ``ProjectWritingProfile`` (``None`` when not yet wired —
            Phase 4 will add the production Backend impl).
    """

    def __init__(
        self,
        preference_provider: PreferenceProvider | None,
        profile_provider: ProfileProvider | None,
    ) -> None:
        self._preference_provider = preference_provider
        self._profile_provider = profile_provider

    async def get_context(self, user_id: UUID, project_id: UUID) -> AdaptiveContext:
        """Assemble AdaptiveContext from preferences + writing profile.

        Graceful degradation: when a provider is None or raises, the
        corresponding text fields are empty. The method never raises
        for missing data — only for programmer errors.
        """
        # Late import to keep Core contracts under TYPE_CHECKING.
        from narrare_core.ai_invocation.adaptive_context import AdaptiveContext

        preference_text = ""
        style_constraints_text = ""
        avoidance_patterns_text = ""

        if self._preference_provider is not None:
            try:
                pref = await self._preference_provider.get_preferences(
                    user_id=user_id,
                    project_id=project_id,
                )
                preference_text = pref.to_prompt_text()
                style_constraints_text = _derive_style_constraints(pref)
                avoidance_patterns_text = _derive_avoidance_patterns(pref)
            except Exception:
                logger.warning(
                    "adaptive_provider_preference_failed",
                    user_id=str(user_id),
                    project_id=str(project_id),
                    exc_info=True,
                )

        voice_profiles_text = ""
        if self._profile_provider is not None:
            try:
                writing = await self._profile_provider.get_profile(project_id)
                if writing is not None:
                    # ADR-055/057 boundary: formatted_voice_profiles renders
                    # ONLY the descriptive speech_summary — never voice_metrics.
                    voice_profiles_text = writing.formatted_voice_profiles
            except Exception:
                logger.warning(
                    "adaptive_provider_profile_failed",
                    user_id=str(user_id),
                    project_id=str(project_id),
                    exc_info=True,
                )

        source_parts: list[str] = []
        if preference_text:
            source_parts.append("preferences")
        if voice_profiles_text:
            source_parts.append("voice profiles")
        source_summary = ", ".join(source_parts) if source_parts else "no signals"

        return AdaptiveContext(
            user_id=user_id,
            project_id=project_id,
            preference_text=preference_text,
            voice_profiles_text=voice_profiles_text,
            style_constraints_text=style_constraints_text,
            avoidance_patterns_text=avoidance_patterns_text,
            source_summary=source_summary,
        )

    async def get_settings(self, user_id: UUID, project_id: UUID) -> AdaptiveSettings:
        """Return default AdaptiveSettings (Phase 2 scaffold).

        Phase 3 will load from ``ProjectSettings.adaptive_settings`` JSONB
        via the settings repository + Alembic migration. Returns the same
        defaults for every caller in Phase 2 — adaptivity is enabled with
        the spec defaults (preference=0.7, voice_fidelity=0.9,
        style_constraints=1.0, avoidance=1.0).
        """
        del user_id, project_id  # Phase 3 will use these for persistence.
        from narrare_core.ai_invocation.adaptive_context import AdaptiveSettings

        return AdaptiveSettings()


# ---------------------------------------------------------------------------
# Heuristic derivation helpers (Phase 2 — tunable in Phase 3 via Eval)
# ---------------------------------------------------------------------------


def _derive_style_constraints(pref: object) -> str:
    """Derive style_constraints text from PreferenceProfile.style dict.

    Phase 2 heuristic: each entry becomes a bullet ``- {key}: {value}``.
    The exact format is tunable in Phase 3 via the Pydantic Eval suite
    (RULE-18b); the contract here is: non-empty iff the style dict has
    at least one entry.
    """
    style = getattr(pref, "style", None)
    if not isinstance(style, dict) or not style:
        return ""
    return "\n".join(f"- {k}: {v}" for k, v in style.items())


def _derive_avoidance_patterns(pref: object) -> str:
    """Derive avoidance_patterns text from PreferenceProfile.constraints list.

    Phase 2 heuristic: each entry becomes a bullet ``- {entry}``.
    Tunable in Phase 3 via Eval.
    """
    constraints = getattr(pref, "constraints", None)
    if not isinstance(constraints, (list, tuple)) or not constraints:
        return ""
    return "\n".join(f"- {entry}" for entry in constraints)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/api/adaptive/test_adaptive_context_provider.py -v`
Expected: PASS — all 13 tests green.

- [ ] **Step 5: Run full check suite**

Run: `just check`
Expected: All 9 step groups pass. Architecture step's RULE-04 check should confirm `adaptive_context_provider.py` is under 250 LOC.

- [ ] **Step 6: Commit**

```bash
git add apps/api/narrare/adaptive/__init__.py \
        apps/api/narrare/adaptive/adaptive_context_provider.py \
        tests/unit/api/adaptive/__init__.py \
        tests/unit/api/adaptive/test_adaptive_context_provider.py
git commit -m "feat(api): add AdaptiveContextProviderImpl (Phase 2 scaffold)

Backend impl composes PreferenceProvider (mem0) + ProfileProvider
(Core Protocol) into AdaptiveContext. Mirrors ADR-067 KBContextProvider
pattern. Graceful degradation for None providers and provider failures
(RULE-11). Derives style_constraints_text + avoidance_patterns_text
heuristically from PreferenceProfile data (tunable via Eval in Phase 3).

Phase 2 scaffold boundaries:
- get_settings() returns defaults (no persistence — Phase 3)
- no invocation_evidence.adaptive_* writes (Phase 3)

ADR-055/057 boundary preserved: only descriptive formatted_voice_profiles
text is copied; voice_metrics are never read or returned.

ADR-069 Decision 3 / Retrofit-Plan step 6."
```

---

### Task 8: Rewire production DI to use `AdaptiveContextEnricher`

**Files:**
- Modify: `apps/api/narrare/_app/dependencies_pipeline.py` (replace enricher wiring)
- Test: `tests/unit/api/_app/test_dependencies_pipeline_adaptive.py` (new file)

**Interfaces:**
- Consumes: `AdaptiveContextEnricher` from Task 6, `AdaptiveContextProviderImpl` from Task 7.
- Produces: production `InvocationPipeline` now wires `AdaptiveContextEnricher` instead of `PreferenceContextEnricherImpl`. All prose-bearing services (writing, analysis, planning, chat) now go through the new enricher. KB / generation / embed / research are unaffected (they were never wired with the preference enricher).

**Note:** This is the **breaking cutover** in production code. `PreferenceContextEnricherImpl` is no longer referenced by production code after this commit (only by tests + the probe, which Task 9 migrates and Task 10 deletes).

**Profile provider wiring:** Phase 2 wires `profile_provider=None` because no Backend `ProfileProvider` impl exists yet (Phase 4 will wire it). The new enricher still writes `user_preferences`, `style_constraints`, and `avoidance_patterns` from `PreferenceProfile` data — three of the four variables now flow. `character_voice_profiles` stays empty until Phase 4 wires `ProfileProvider`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/api/_app/test_dependencies_pipeline_adaptive.py`:

```python
"""Tests that the production InvocationPipeline wires AdaptiveContextEnricher.

After ADR-069 Phase 2 cutover (this task), the production pipeline MUST
use AdaptiveContextEnricher — NOT the legacy PreferenceContextEnricherImpl.

See: ADR-069 Decision 1 / Retrofit-Plan step 7.
"""

from __future__ import annotations

from narrare._app.dependencies_pipeline import get_invocation_pipeline
from narrare_core.ai_invocation.enrichers.adaptive import AdaptiveContextEnricher


class TestPipelineWiresAdaptiveEnricher:
    """Production pipeline MUST use the new adaptive enricher."""

    def test_pipeline_has_at_least_one_adaptive_enricher(self) -> None:
        pipeline = get_invocation_pipeline()
        adaptive_enrichers = [
            e for e in pipeline._enrichers if isinstance(e, AdaptiveContextEnricher)
        ]
        assert len(adaptive_enrichers) >= 1, (
            "Production pipeline must wire at least one AdaptiveContextEnricher. "
            "Found enricher types: "
            + ", ".join(type(e).__name__ for e in pipeline._enrichers)
        )

    def test_pipeline_does_not_use_legacy_preference_enricher(self) -> None:
        """PreferenceContextEnricherImpl must NOT be wired after cutover.
        This assertion is a regression guard: even after Task 10 deletes
        the class, this test stays as a structural guard (the import will
        fail if someone re-introduces a same-named class)."""
        from narrare_core.ai_invocation.enrichers.preferences import (
            PreferenceContextEnricherImpl,
        )

        pipeline = get_invocation_pipeline()
        for enricher in pipeline._enrichers:
            assert not isinstance(enricher, PreferenceContextEnricherImpl), (
                f"Legacy PreferenceContextEnricherImpl must not be wired. "
                f"Found instance in pipeline: {enricher!r}"
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/api/_app/test_dependencies_pipeline_adaptive.py -v`
Expected: FAIL — `AssertionError: Production pipeline must wire at least one AdaptiveContextEnricher` (the first assertion fails because the legacy enricher is still wired).

- [ ] **Step 3: Write minimal implementation**

Modify `apps/api/narrare/_app/dependencies_pipeline.py`. Replace the function body of `get_invocation_pipeline` (current lines ~22-76) with the updated wiring:

```python
@lru_cache
def get_invocation_pipeline() -> InvocationPipeline:
    """Create InvocationPipeline with production implementations.

    Assembles the pipeline with all P0.3 + ADR-069 components:
    - RuntimeVariableValidatorImpl (pre-composition checks)
    - IntentOutputBudgetResolverImpl (budget resolution)
    - FinalPromptValidatorImpl (post-composition checks)
    - AdaptiveContextEnricher (ADR-069 — writes all four adaptive
      prompt variables: user_preferences, style_constraints,
      avoidance_patterns, character_voice_profiles; replaces the
      legacy single-variable PreferenceContextEnricherImpl)
    - KBSuggestedContextEnricher (backed by KB repository)

    Note:
        The ``evidence_sink`` is resolved by ``get_evidence_sink()`` based on
        the ``use_persistent_evidence`` setting: ``PersistentEvidenceSink``
        (PostgreSQL) when enabled, ``LoggingEvidenceSink`` otherwise (default).

        The ``KBSuggestedProviderImpl`` uses ``get_session_factory()`` to
        create per-call database sessions because this function is cached
        (singleton) and cannot depend on request-scoped sessions.

        Phase 2 boundary (ADR-069): ``AdaptiveContextProviderImpl`` is
        wired with ``profile_provider=None`` — no Backend ProfileProvider
        exists yet (Phase 4 wires it). The adaptive enricher still writes
        three of four variables (user_preferences, style_constraints,
        avoidance_patterns) from PreferenceProfile data;
        character_voice_profiles stays empty until Phase 4.
    """
    from narrare._app.database import get_session_factory
    from narrare.adaptive.adaptive_context_provider import (
        AdaptiveContextProviderImpl,
    )
    from narrare.kb.kb_suggested_provider import KBSuggestedProviderImpl
    from narrare_core.ai_invocation import (
        FinalPromptValidatorImpl,
        IntentOutputBudgetResolverImpl,
        InvocationPipeline,
        RuntimeVariableValidatorImpl,
    )
    from narrare_core.ai_invocation.enrichers import (
        AdaptiveContextEnricher,
        KBSuggestedContextEnricher,
    )

    preference_service = _get_preference_service_instance()

    # Adaptive enricher (ADR-069) — single canonical writer of all four
    # adaptive prompt variables. Phase 2 wires profile_provider=None;
    # Phase 4 will wire the production Backend ProfileProvider.
    adaptive_provider = AdaptiveContextProviderImpl(
        preference_provider=preference_service,
        profile_provider=None,
    )
    enrichers: list[ContextEnricher] = [
        AdaptiveContextEnricher(adaptive_provider=adaptive_provider),
    ]

    # KB-suggested enricher runs before budget resolution so the resolver
    # can decide whether token budget allows KB context inclusion.
    # Uses get_session_factory() to avoid coupling the singleton pipeline
    # to request-scoped sessions — each get_suggested_context() call
    # creates its own session (lightweight, read-only query).
    kb_provider = KBSuggestedProviderImpl(session_factory=get_session_factory())
    enrichers.append(KBSuggestedContextEnricher(kb_provider=kb_provider))

    return InvocationPipeline(
        enrichers=enrichers,
        variable_validator=RuntimeVariableValidatorImpl(),
        budget_resolver=IntentOutputBudgetResolverImpl(),
        final_validator=FinalPromptValidatorImpl(),
        evidence_sink=get_evidence_sink(),
    )
```

The import of `PreferenceContextEnricherImpl` from `narrare_core.ai_invocation.enrichers` is removed (Task 10 deletes the class entirely; for now, the `__init__.py` still re-exports it, but production code no longer uses it).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/api/_app/test_dependencies_pipeline_adaptive.py -v`
Expected: PASS — both tests green.

- [ ] **Step 5: Run the existing enricher + writing tests**

The existing tests (`test_writing_preference_enricher.py`, `enrichers/test_preferences.py`, `scripts/probes/preference_enrichment_probe.py`) still reference `PreferenceContextEnricherImpl`. They MUST still pass — the class still exists in `enrichers/preferences.py` and is still re-exported from `enrichers/__init__.py`. These tests test the enricher class in isolation; they do NOT touch production wiring.

Run: `uv run pytest tests/unit/core/ai_invocation/ -v`
Expected: PASS — all existing tests still green. They will be migrated in Task 9.

Run: `uv run pytest tests/integration/ -v -k "writing or pipeline" --timeout=120`
Expected: PASS — writing-path invocations still receive `user_preferences` (the new enricher writes the same key from the same source text).

- [ ] **Step 6: Run full check suite**

Run: `just check`
Expected: All 9 step groups pass.

- [ ] **Step 7: Commit**

```bash
git add apps/api/narrare/_app/dependencies_pipeline.py \
        tests/unit/api/_app/test_dependencies_pipeline_adaptive.py
git commit -m "feat(api): rewire production pipeline to AdaptiveContextEnricher

Production InvocationPipeline now wires AdaptiveContextEnricher
(ADR-069) instead of the legacy single-variable
PreferenceContextEnricherImpl. All prose-bearing services (writing,
analysis, planning, chat) now flow through the new enricher.

Phase 2 boundary: AdaptiveContextProviderImpl is constructed with
profile_provider=None — three of four adaptive variables
(user_preferences, style_constraints, avoidance_patterns) now flow
from PreferenceProfile data. character_voice_profiles stays empty
until Phase 4 wires the production Backend ProfileProvider.

The legacy PreferenceContextEnricherImpl class still exists
(Task 10 deletes it). Existing tests still pass unchanged; Task 9
migrates them to the new enricher.

ADR-069 Decision 1 + Decision 4 / Retrofit-Plan step 7."
```

---

### Task 9: Migrate existing tests + probe to `AdaptiveContextEnricher`

**Files:**
- Modify: `tests/unit/core/ai_invocation/test_writing_preference_enricher.py` (replace `PreferenceContextEnricherImpl` with `AdaptiveContextEnricher` + a local `FakeAdaptiveContextProvider`)
- Delete: `tests/unit/core/ai_invocation/enrichers/test_preferences.py` (its coverage is subsumed by `test_adaptive_enricher.py`)
- Modify: `scripts/probes/preference_enrichment_probe.py` (same migration)

**Interfaces:**
- Consumes: `AdaptiveContextEnricher` from Task 6, `AdaptiveContext` + `AdaptiveSettings` from Tasks 2+3.
- Produces: no production-code changes; only test/probe code now references `AdaptiveContextEnricher` exclusively. After this task, NO code in the repo references `PreferenceContextEnricherImpl` — Task 10 is then free to delete the class.

**Migration strategy:**

The existing tests construct `PreferenceContextEnricherImpl(preference_provider=FakePreferenceProvider(...))` and assert that `dynamic_inputs["user_preferences"]` ends up populated. The migration replaces that with:

```python
AdaptiveContextEnricher(
    adaptive_provider=FakeAdaptiveContextProvider(
        context=AdaptiveContext(
            user_id=user_id,
            project_id=project_id,
            preference_text=<the text the old FakePreferenceProvider would have produced>,
        ),
    ),
)
```

Where `FakeAdaptiveContextProvider` is a small async fake defined locally in each test module (the codebase pattern is local fakes per module).

The assertions stay the same: `result.dynamic_inputs["user_preferences"]` must contain the expected text.

- [ ] **Step 1: Confirm existing tests still pass pre-migration**

Run: `uv run pytest tests/unit/core/ai_invocation/test_writing_preference_enricher.py tests/unit/core/ai_invocation/enrichers/test_preferences.py -v`
Expected: PASS (these still reference the old class, which still exists).

- [ ] **Step 2: Verify probe still runs**

Run: `uv run python scripts/probes/preference_enrichment_probe.py --help` (or the probe's documented invocation)
Expected: PASS (the probe still references the old class).

- [ ] **Step 3: Migrate `test_writing_preference_enricher.py`**

Edit `tests/unit/core/ai_invocation/test_writing_preference_enricher.py`. Update the imports:

```python
from narrare_core.ai_invocation.adaptive_context import AdaptiveContext
from narrare_core.ai_invocation.enrichers.adaptive import AdaptiveContextEnricher
from narrare_core.ai_invocation.models import PromptInvocationContext
```

Remove the import of `PreferenceContextEnricherImpl`. Keep `FakePreferenceProvider` (it is still used to back the composer's preference gate test).

Add a new fake at the top of the test helpers section (after `FakePreferenceProvider`):

```python
class FakeAdaptiveProvider:
    """Async fake AdaptiveContextProvider for the writing-path tests.

    Returns a programmable AdaptiveContext. Mirrors the production
    AdaptiveContextProviderImpl shape — the writing tests use this to
    isolate the pipeline+composer integration from any mem0/DB I/O.
    """

    def __init__(self, context: AdaptiveContext) -> None:
        self._context = context
        self.calls: list[tuple[object, object]] = []

    async def get_context(self, user_id: object, project_id: object) -> AdaptiveContext:
        self.calls.append((user_id, project_id))
        return self._context

    async def get_settings(self, user_id: object, project_id: object):
        from narrare_core.ai_invocation.adaptive_context import AdaptiveSettings

        del user_id, project_id
        return AdaptiveSettings()
```

Replace every `PreferenceContextEnricherImpl(preference_provider=provider)` with:

```python
AdaptiveContextEnricher(
    adaptive_provider=FakeAdaptiveProvider(
        context=AdaptiveContext(
            user_id=user_id,
            project_id=project_id,
            preference_text=provider._profile.to_prompt_text(),
        ),
    ),
)
```

The assertions (`"dark, atmospheric prose" in result.merged_context.user_preferences`, etc.) stay unchanged — the new enricher writes the same key from the same source text.

- [ ] **Step 4: Delete `enrichers/test_preferences.py` after coverage check**

This file is the unit test for `PreferenceContextEnricherImpl`. After migration, its coverage is redundant with `test_adaptive_enricher.py` (Task 6).

Before deletion, run coverage to confirm no gap:

Run: `uv run pytest tests/unit/core/ai_invocation/test_adaptive_enricher.py --cov=narrare_core.ai_invocation.enrichers.adaptive --cov-report=term-missing`
Expected: 100% coverage of `enrichers/adaptive.py`. If any line is uncovered, add the missing test case to `test_adaptive_enricher.py` BEFORE deleting `test_preferences.py`.

Action: `git rm tests/unit/core/ai_invocation/enrichers/test_preferences.py`

- [ ] **Step 5: Migrate `scripts/probes/preference_enrichment_probe.py`**

Open the probe. Identify the section that wires `PreferenceContextEnricherImpl` and replace with `AdaptiveContextEnricher` + an inline fake provider. The probe runs in CI as part of the adoption-evidence pipeline (ADR-056); it MUST continue to produce the same evidence marker shape.

Replace:

```python
from narrare_core.ai_invocation.enrichers.preferences import (
    PreferenceContextEnricherImpl,
)

enricher = PreferenceContextEnricherImpl(preference_provider=provider)
```

with:

```python
from narrare_core.ai_invocation.adaptive_context import (
    AdaptiveContext,
    AdaptiveSettings,
)
from narrare_core.ai_invocation.enrichers.adaptive import AdaptiveContextEnricher


class _ProbeAdaptiveProvider:
    """Inline fake matching the AdaptiveContextProvider Protocol."""

    def __init__(self, preference_text: str, user_id: object, project_id: object) -> None:
        self._context = AdaptiveContext(
            user_id=user_id,
            project_id=project_id,
            preference_text=preference_text,
        )

    async def get_context(self, user_id: object, project_id: object) -> AdaptiveContext:
        del user_id, project_id
        return self._context

    async def get_settings(self, user_id: object, project_id: object) -> AdaptiveSettings:
        del user_id, project_id
        return AdaptiveSettings()


# Compute the preference_text the same way the old enricher did:
profile = await provider.get_preferences(user_id=user_id, project_id=project_id)
preference_text = profile.to_prompt_text()

enricher = AdaptiveContextEnricher(
    adaptive_provider=_ProbeAdaptiveProvider(
        preference_text=preference_text,
        user_id=user_id,
        project_id=project_id,
    ),
)
```

If the probe asserts on `dynamic_inputs["user_preferences"]`, the assertion is unchanged.

- [ ] **Step 6: Run migrated tests + probe**

Run: `uv run pytest tests/unit/core/ai_invocation/test_writing_preference_enricher.py tests/unit/core/ai_invocation/test_adaptive_enricher.py -v`
Expected: PASS — all migrated tests + new adaptive enricher tests green.

Run: `uv run python scripts/probes/preference_enrichment_probe.py` (or the documented probe invocation)
Expected: PASS — produces the same evidence marker shape as before.

- [ ] **Step 7: Verify no remaining references to `PreferenceContextEnricherImpl`**

Run: `rg -ln "PreferenceContextEnricherImpl" /home/kiesow/projects/narrare/ --type py`
Expected: only `packages/core/narrare_core/ai_invocation/enrichers/preferences.py` (the class definition) and `packages/core/narrare_core/ai_invocation/enrichers/__init__.py` (the re-export). NO test file, NO probe, NO production code references the class. Task 10 is now safe.

- [ ] **Step 8: Run full check suite**

Run: `just check`
Expected: All 9 step groups pass.

- [ ] **Step 9: Commit**

```bash
git add tests/unit/core/ai_invocation/test_writing_preference_enricher.py \
        scripts/probes/preference_enrichment_probe.py
git rm tests/unit/core/ai_invocation/enrichers/test_preferences.py
git commit -m "refactor(tests): migrate preference enricher tests + probe to AdaptiveContextEnricher

After Task 8 rewired production DI, the existing tests and probe still
referenced the legacy PreferenceContextEnricherImpl. This commit:

- Migrates test_writing_preference_enricher.py: replaces
  PreferenceContextEnricherImpl(preference_provider=...) with
  AdaptiveContextEnricher(adaptive_provider=FakeAdaptiveProvider(...))
- Deletes enrichers/test_preferences.py: its coverage is fully
  subsumed by test_adaptive_enricher.py (14 tests vs 9, including
  the four-variable write that the legacy tests could not express)
- Migrates scripts/probes/preference_enrichment_probe.py

No production-code change. After this commit, NO code in the repo
references PreferenceContextEnricherImpl — Task 10 is free to delete
the class.

ADR-069 Decision 1 / Retrofit-Plan steps 8+9."
```

---

### Task 10: Delete `PreferenceContextEnricherImpl` (Phase 2 cleanup)

**Files:**
- Delete: `packages/core/narrare_core/ai_invocation/enrichers/preferences.py` (entire file)
- Modify: `packages/core/narrare_core/ai_invocation/enrichers/__init__.py` (remove the re-export)
- Test: `tests/unit/core/ai_invocation/test_adaptive_enricher.py` (append structural-guard tests)

**Interfaces:**
- Consumes: Tasks 6-9 confirm nothing references `PreferenceContextEnricherImpl`.
- Produces: the legacy class is gone. The Core `ContextEnricher` Protocol stays (in `contracts.py`). The Core `PreferenceContextEnricher` Protocol (specialised marker) stays in `contracts.py` — only the impl is removed. `AdaptiveContextEnricher` is the single canonical writer.

**Important:** Verified by reading the file in plan-research — `preferences.py` contains only the `PreferenceContextEnricherImpl` class + `PREFERENCE_KEY` constant + module docstring (115 LOC, nothing else). Therefore delete the entire file.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/core/ai_invocation/test_adaptive_enricher.py`:

```python
class TestPreferenceContextEnricherImplRemoved:
    """After Task 10, the legacy class is deleted. The Protocols stay."""

    def test_legacy_impl_import_fails(self) -> None:
        """Importing PreferenceContextEnricherImpl MUST fail after deletion."""
        with pytest.raises(ImportError):
            from narrare_core.ai_invocation.enrichers.preferences import (  # noqa: F401
                PreferenceContextEnricherImpl,
            )

    def test_preference_context_enricher_protocol_stays(self) -> None:
        """The PreferenceContextEnricher Protocol in contracts.py stays."""
        from narrare_core.ai_invocation.contracts import PreferenceContextEnricher

        assert PreferenceContextEnricher is not None

    def test_context_enricher_protocol_stays(self) -> None:
        """The base ContextEnricher Protocol stays."""
        from narrare_core.ai_invocation.contracts import ContextEnricher

        assert ContextEnricher is not None

    def test_adaptive_enricher_remains_importable_from_package(self) -> None:
        """The new enricher remains the only adaptive enricher."""
        from narrare_core.ai_invocation.enrichers import AdaptiveContextEnricher

        assert AdaptiveContextEnricher is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/core/ai_invocation/test_adaptive_enricher.py::TestPreferenceContextEnricherImplRemoved -v`
Expected: FAIL — `test_legacy_impl_import_fails` fails because the class still exists.

- [ ] **Step 3: Write minimal implementation**

Delete the entire file:

```bash
git rm packages/core/narrare_core/ai_invocation/enrichers/preferences.py
```

Modify `packages/core/narrare_core/ai_invocation/enrichers/__init__.py`:

```python
"""Enrichers for the AI invocation pipeline.

Enrichers add runtime context to a PromptInvocationContext before
prompt composition runs. Each enricher is a focused, single-responsibility
implementation of the ContextEnricher Protocol.

See:
    ADR-038, ADR-039, ADR-040, ADR-069 (Decision 1 enricher swap),
    INFRA-013, CONSTRAINTS.md RULE-06.
"""

from narrare_core.ai_invocation.enrichers.adaptive import (
    AdaptiveContextEnricher,
)
from narrare_core.ai_invocation.enrichers.consistency import (
    KBConsistencyEnricher,
)
from narrare_core.ai_invocation.enrichers.kb_suggested import (
    KBSuggestedContextEnricher,
)

__all__ = [
    "AdaptiveContextEnricher",
    "KBConsistencyEnricher",
    "KBSuggestedContextEnricher",
]
```

Note: any test that imports `PREFERENCE_KEY` from `enrichers.preferences` must now import it from `enrichers.adaptive` (where the new `PREFERENCE_KEY` constant lives). Verified by Task 9 — no remaining importers.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/core/ai_invocation/test_adaptive_enricher.py::TestPreferenceContextEnricherImplRemoved -v`
Expected: PASS — all 4 tests green.

- [ ] **Step 5: Run full test suite to catch any orphan import**

Run: `uv run pytest tests/unit/ -v`
Expected: PASS — no orphan imports.

If any test fails with `ImportError: ... preferences`, fix the import by repointing to `enrichers.adaptive` (Task 9 should have caught all of them, but defensive verification).

- [ ] **Step 6: Run full check suite**

Run: `just check`
Expected: All 9 step groups pass. The Architecture step's import-cycle checker confirms no remaining reference to the deleted module.

- [ ] **Step 7: Commit**

```bash
git rm packages/core/narrare_core/ai_invocation/enrichers/preferences.py
git add packages/core/narrare_core/ai_invocation/enrichers/__init__.py \
        tests/unit/core/ai_invocation/test_adaptive_enricher.py
git commit -m "refactor(core): delete PreferenceContextEnricherImpl (Phase 2 cleanup)

The legacy single-variable enricher is gone. AdaptiveContextEnricher
(Task 6) is the single canonical writer of all four adaptive prompt
variables, per ADR-069 Decision 1.

Removed:
- packages/core/narrare_core/ai_invocation/enrichers/preferences.py
  (the file contained only the class + PREFERENCE_KEY constant)
- The re-export from enrichers/__init__.py

Kept (in contracts.py):
- ContextEnricher Protocol (base)
- PreferenceContextEnricher Protocol (specialised marker — documents
  the preference-injection intent; still useful for typed DI)

After this commit, the codebase has exactly ONE adaptive enricher.
Phase 2 (Core Foundation) of ADR-069 is complete.

ADR-069 Decision 1 / Retrofit-Plan step 10."
```

---

## Self-Review

Run this checklist against the plan with fresh eyes.

### 1. Spec coverage (ADR-069 Retrofit-Plan steps 1-10)

| Retrofit step | Plan task | Covered? |
|---------------|-----------|----------|
| 1. Add `AdaptiveWeights`, `AdaptiveContext`, `AdaptiveSettings` dataclasses | Tasks 1, 2, 3 | Yes — three frozen slotted dataclasses in `adaptive_context.py`, full TDD per class |
| 2. Add `AdaptiveContextProvider` Protocol | Task 4 | Yes — Protocol in `contracts.py` with `get_context()` + `get_settings()`, conformance test with Fake |
| 3. Add `LLMIntent.DIALOGUE_COACH` enum member + docs entry | Task 5 | Yes — enum member + `_docs_ai_assist.py` aggregator entry |
| 4. Register `characters` + `text_to_analyze` variables | Task 5 | Yes — `characters` in `SYSTEM_VARS`, `text_to_analyze` in `USER_CONTENT_VARS` |
| 5. Implement `AdaptiveContextEnricher` (writes all 4 variables) | Task 6 | Yes — Core enricher with 14 tests covering success, no-provider, missing-IDs, provider-failure, disabled, no-signal, partial-signal, immutability, protocol-conformance |
| 6. Implement Backend `AdaptiveContextProviderImpl` | Task 7 | Yes — scaffold impl composing PreferenceProvider + ProfileProvider, Phase 2 boundaries documented |
| 7. Rewire `dependencies_pipeline.py` | Task 8 | Yes — production DI swap with structural regression test |
| 8. Run existing enricher tests (must still pass) | Task 8 Step 5 + Task 9 | Yes — existing tests pass post-rewiring; then migrated |
| 9. Add new tests for three additional variables | Task 6 | Yes — `test_adaptive_enricher.py::TestAdaptiveEnricherSuccess::test_all_four_variables_written` + `TestAdaptiveEnricherPartialSignal` |
| 10. Delete `PreferenceContextEnricherImpl` | Task 10 | Yes — file deletion + `__init__.py` cleanup + structural guard test |

**Phase 3+ items explicitly NOT in this plan (verified absent):**
- ProjectSettings JSONB column + Alembic migration -> Phase 3 step 11
- invocation_evidence adaptive_* columns -> Phase 3 step 12
- AdaptiveContextService + REST endpoints -> Phase 3 step 13
- DIALOGUE_COACH route_table entry -> Phase 4 step 17
- governed template `_bundled/ai_assist/...` -> Phase 4 step 15
- manifest + adoption registry entries -> Phase 4 step 16
- DialogueCoachAgent + Service -> Phase 4 steps 18-19
- Frontend components + i18n -> Phase 5
- Evals -> Phase 6

### 2. Placeholder scan

Searched plan for red flags:
- No "TBD", "TODO", "implement later", "fill in details"
- No "add appropriate error handling" — error handling is shown explicitly in each test (provider raises -> context unchanged) and impl (try/except + structlog warning)
- No "similar to Task N" without code — every task has full code blocks
- Every test step has actual runnable test code (not prose)
- Every impl step has actual runnable Python code (not pseudocode)

### 3. Type consistency

Cross-checked names + signatures across tasks:
- `AdaptiveWeights` fields: `preference`, `voice_fidelity`, `style_constraints`, `avoidance` — same in Task 1 (definition), Task 2 (used in `AdaptiveContext.weights`), Task 3 (used in `AdaptiveSettings.weights`), Task 6 (enricher logs `preference_length`), Task 7 (provider returns defaults). Consistent.
- `AdaptiveContext` fields: `user_id`, `project_id`, `preference_text`, `voice_profiles_text`, `style_constraints_text`, `avoidance_patterns_text`, `weights`, `source_summary` — same in Task 2 (definition), Task 4 (Protocol return type), Task 6 (enricher consumes), Task 7 (Backend impl returns), Task 9 (Fake constructs). Consistent.
- `AdaptiveContextProvider` Protocol methods: `async def get_context(self, user_id: UUID, project_id: UUID) -> AdaptiveContext` + `async def get_settings(self, user_id: UUID, project_id: UUID) -> AdaptiveSettings` — same in Task 4 (Protocol), Task 6 (Fake + consumed), Task 7 (impl). Consistent.
- `AdaptiveContextEnricher` constructor: `__init__(self, adaptive_provider: AdaptiveContextProvider | None)` — same in Task 6 (definition), Task 8 (wiring), Task 9 (Fake in migrated tests). Consistent.
- `AdaptiveContextProviderImpl` constructor: `__init__(self, preference_provider: PreferenceProvider | None, profile_provider: ProfileProvider | None)` — same in Task 7 (definition), Task 8 (wiring). Consistent.
- Four key constants: `PREFERENCE_KEY`, `STYLE_CONSTRAINTS_KEY`, `AVOIDANCE_PATTERNS_KEY`, `CHARACTER_VOICE_PROFILES_KEY` — defined in Task 6, used in Task 6 tests, kept in Task 10 after `preferences.py` deletion (constants live in `adaptive.py`). Consistent.

### 4. RULE-04 sizing

Predicted LOC per file vs cap:

| File | Cap | Predicted LOC | Margin |
|------|-----|---------------|--------|
| `packages/core/narrare_core/ai_invocation/adaptive_context.py` | <= 200 | ~150 (3 classes + module docstring) | OK |
| `packages/core/narrare_core/ai_invocation/enrichers/adaptive.py` | <= 150 | ~145 (class + 4 constants + module docstring + log statements) | TIGHT |
| `apps/api/narrare/adaptive/adaptive_context_provider.py` | <= 250 | ~150 (class + 2 derivation helpers + module docstring) | OK |
| `packages/core/narrare_core/ai_invocation/contracts.py` | (existing) | +~70 lines for the new Protocol | OK |
| `packages/core/narrare_core/llm/intents/_docs_ai_assist.py` | (no cap, docs) | ~30 | OK |

**Mitigation for `enrichers/adaptive.py` tightness:** if pyright or the file-size checker complains, split the four well-known key constants into a sibling `_keys.py` module. Plan does NOT pre-emptively split — the file fits at ~145 LOC under the 150 cap. If the implementer finds it overflows during Task 6 Step 5, they should split BEFORE committing.

### 5. Hard-constraint verification

- **ADR-055/057 boundary:** `AdaptiveContext` has NO `voice_metrics` field (structurally asserted in Task 2 test `test_does_not_carry_voice_metrics_field`). The Backend impl in Task 7 copies ONLY `formatted_voice_profiles` (which renders `speech_summary` only per `profiles/models.py:55-66`).
- **RULE-03 (Contract first):** Task 4 lands the Protocol before Tasks 6+7 implement against it. Each task's `Interfaces` block makes the dependency explicit.
- **RULE-07 (Dependency direction):** Core (`adaptive_context.py`, `enrichers/adaptive.py`, `contracts.py`) imports only from `narrare_core.*` (stdlib + structlog). Backend (`adaptive/adaptive_context_provider.py`) imports from `narrare_core.*` — never the reverse.
- **RULE-11 (No silent failures):** every provider call in Tasks 6 + 7 is wrapped in try/except with a structlog warning + graceful return. Verified by tests (`TestAdaptiveEnricherProviderFailure`, `TestGetContextGracefulDegradation`).
- **No workarounds:** the legacy `PreferenceContextEnricherImpl` is fully replaced (not bypassed, not aliased, not internally rewired under the old name). ADR-069 Decision 1 Option beta honored exactly.
- **Phase 2 scaffold boundaries honored:** Task 7 `get_settings()` returns defaults (no persistence); no `invocation_evidence.adaptive_*` writes. Documented in the impl's module docstring + the test `TestGetSettingsPhase2Scaffold`.

### 6. Risks identified for the implementer

1. **`enrichers/adaptive.py` is close to the 150 LOC cap.** If implementation pushes over, split constants into `_keys.py` before committing (do NOT compress code or delete docstrings — RULE-04 explicitly forbids compression).
2. **Task 8 wiring change is the highest-risk cutover.** Run the full integration test suite (`uv run pytest tests/integration/`) after Task 8 Step 5, not just unit tests. If any integration test asserts on `dynamic_inputs["user_preferences"]` content from the production pipeline, those assertions may need updating — the new enricher writes the same key from the same source text, but via a different code path.
3. **Task 9 file deletion (`enrichers/test_preferences.py`) depends on `test_adaptive_enricher.py` having full coverage.** Run coverage BEFORE deletion (Step 4 explicit instruction). If coverage is incomplete, add the missing tests to `test_adaptive_enricher.py` first.
4. **Task 10 file deletion (`enrichers/preferences.py`) depends on Task 9 having migrated every reference.** Task 9 Step 7 includes an `rg` check that verifies this. If the check fails, fix the orphan import before Task 10.
5. **Probe migration in Task 9 may affect CI evidence markers.** Run the probe manually (Step 6) and diff its output against the pre-migration output. The evidence marker SHAPE should be unchanged; only internal wiring differs.

### 7. Estimated effort per task (T-shirt sizing)

| Task | Effort | Reasoning |
|------|--------|-----------|
| Task 1 — AdaptiveWeights | S | One dataclass, 8 tests, pure value object |
| Task 2 — AdaptiveContext | S | One dataclass, 10 tests, depends on Task 1 |
| Task 3 — AdaptiveSettings | S | One dataclass, 7 tests, depends on Task 1 |
| Task 4 — AdaptiveContextProvider Protocol | S | Protocol definition, 5 tests with Fake |
| Task 5 — DIALOGUE_COACH enum + variables | M | Multiple file edits (4 source files + 2 test files); docs entry has substantial prose |
| Task 6 — AdaptiveContextEnricher | M | Largest Core piece; 14 tests covering 7 scenarios; close to LOC cap |
| Task 7 — Backend AdaptiveContextProviderImpl | M | Composes 2 existing providers + derivation logic; 13 tests covering 5 scenarios |
| Task 8 — Rewire DI | S | Single-file production change, 2 tests; well-bounded cutover |
| Task 9 — Migrate tests + probe | M | Three files to migrate mechanically; coverage check; probe output diff |
| Task 10 — Delete legacy class | S | Two-file cleanup, 4 structural-guard tests |

**Total estimated effort:** 5xS + 4xM + 0xL. Realistic single-session execution for one Platform-Specialist pair.

### 8. Feasibility concerns

**None identified.** Every task has a clear contract, complete code, and a bounded test cycle. The Phase 2 scaffold scope (no persistence, no evidence writes) keeps Task 7 small enough to land in Phase 2 without leaking Phase 3 concerns. The user's note about the scaffold is honored exactly: `get_settings()` returns defaults; no `ProjectSettings.adaptive_settings` reads; no `invocation_evidence.adaptive_*` writes.

The one boundary worth flagging: **Task 7's derivation heuristics** (`_derive_style_constraints` + `_derive_avoidance_patterns`) are intentionally simple in Phase 2. The ADR explicitly defers richer derivation to Phase 3 + Eval tuning (RULE-18b). This is not a feasibility concern — it is the documented scope boundary.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-07-20-adaptive-context-core-foundation.md`.**

Total tasks: **10** (Phase 1: Tasks 1-5; Phase 2: Tasks 6-10).
Estimated effort: 5xS + 4xM (single session with review checkpoints).
Each task ends with `just check` green + a focused conventional commit.

Two execution options:

**1. Subagent-Driven (recommended)** — A fresh subagent per task, with two-stage review (test-only review -> impl review) between tasks. Best for catching drift early; each subagent gets a clean context window sized for one task. Use superpowers:subagent-driven-development.

**2. Inline Execution** — Execute tasks in this session using superpowers:executing-plans, batch execution with checkpoints for review between Phase 1 and Phase 2.

**Which approach?**
