# C5 — Token-Budget Governance (ADR-082) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lift the four hardcoded input-context token budgets into the SET-005 cascade (defaults 32,000 total / 16,000 series-history) and cap every input budget against the configured model's context window via a new pure Core resolver (ADR-082 Decisions 1–9; closes the CR-08 P0 item "model-boundary/tier-budget adoption").

**Architecture:** Contract-first Core resolver (`ContextBudgetResolver` Protocol + `EffectiveContextBudgets` result model in `context/contracts.py`, implementation in new `context/budget_resolver.py`, mirroring `DefaultRunLimitResolver`'s injected-provider pattern). Two new SET-005 cascade keys on `TokenLimitOverrides` (JSONB — no migration) with operator-env Fields; a single API-side adapter (`settings/token_limits/context_budgets.py::resolve_context_budgets`) feeds six production wiring points (five writing deps factories + the beta-reader factory). Budgets are ceilings; the resolver only ever caps **down** (min() principle, D5).

**Tech Stack:** Python 3.14, Pydantic (frozen result model), structlog, pytest (existing `tests/unit/` conventions), models.dev-backed `get_model_limits` window source (already wired, 24 h cache).

**Binding spec:** `docs/architecture/decisions/ADR-082-token-budget-governance.md` (Decisions 1–9, Contract Sketches, Implementation Notes, Completeness Gate). Program context: `docs/superpowers/specs/2026-08-14-post-export-followups-design.md` §3 (C5, D1–D6). This plan implements exactly the ADR — nothing more, nothing less. Review Triggers (tiktoken etc.) are out of scope.

## Global Constraints

- **Slice semantics (RULE-20):** Tasks 1a–3d are sequentially executable sub-slices of ONE coherent slice. The feature is "on" only after Task 3d's final gate passes; no sub-task may be merged alone into a state where keys exist but wiring doesn't (or vice versa). Each sub-task is independently testable and commits cleanly.
- **Contract-first (RULE-03):** `packages/core/narrare_core/context/contracts.py` (Task 1a) and `apps/api/narrare/settings/token_limits/contracts.py` (Task 2a) are authored FIRST in their tasks and are **untouchable** for the remainder of the slice. Any later need to change them = STOP and report to the coordinator (ADR-082 re-review required).
- **Package sizing:** ≤3 production files and ≤250 new LOC per delegated sub-task (test files and docs do not count toward the file cap). *ADR-082 Task-1b ruling:* docstring-only corrections that accompany a task's semantic change (no logic) do not count against the ≤3-production-file cap; they are part of the same logical unit and land in the same commit.
- **Regression-first:** every new test is written and run (expected FAIL) before the implementation step that satisfies it; every re-defaulted constant's pin test is written before the constant changes.
- **Commits:** implementer edits + runs gates, then reports; **Platform specialist commits with the verbatim message in each task's commit step**. No `--no-verify`/`-n`, no push. On hook failure: STOP and report.
- **Language / locating:** English everywhere (code, comments, tests, commit messages). Locate edit targets by semantic name/text (the code blocks below quote the current text) — never by line number.
- **No UI, no migration, no new dependency** (ADR-082 Decisions 1/7; JSONB absorbs the keys; TECH_STACK unchanged).
- **Test commands:** focused runs via `just test-file <path>`; per-task gate `just test-unit`. On machines with <12 GB available RAM use `just test-lowmem` instead of `just test-unit`. Architecture checker: `just check-architecture`. Slice-final gates (Task 3d): `just check-architecture`, `just typecheck`, `just lint-check`, `just test-unit`.
- **Interpretation note (ADR-082 Decision 6, locked for this plan):** `series_in_scope` means *this request actually assembles the series-history block* — true only for the main writing path on a series novel; `False` for extend/rewrite/coauthor/style-variants (they never inject `{{series_history}}`) and for analysis. Rationale: the carve-out exists to preserve containment (`series_history + tier_base ≤ total`); carving out on paths that never inject the block would waste half the budget with nothing filling it, contradicting "budgets are ceilings, tiers fill by content availability" (D6). The resolver signature (`series_in_scope: bool  # provider knows`) matches: the provider-level call decides.

---

### Task 1a: Core contracts + resolver + writing-total constant

**Files:**
- Modify: `packages/core/narrare_core/context/contracts.py` (add `EffectiveContextBudgets` + `ContextBudgetResolver` — contract file, untouchable afterward)
- Modify: `packages/core/narrare_core/context/budget.py` (4 new module constants; `TokenBudgetManager.DEFAULT_TOTAL_BUDGET` 6,000 → 32,000)
- Create: `packages/core/narrare_core/context/budget_resolver.py` (`DefaultContextBudgetResolver`)
- Test: `tests/unit/core/context/test_budget_resolver.py` (new)

**Interfaces:**
- Consumes: `narrare_core.llm.cost_rates.get_model_limits(provider, model_id) -> ModelLimits | None` (existing; `ModelLimits(context, output)`), `narrare_core.llm.cost_rates.ModelLimits`.
- Produces (verbatim for all later tasks):
  - `EffectiveContextBudgets(BaseModel)` — frozen; fields `context_total: int`, `series_history: int`, `writing_tier_base: int`, `reserve_tokens: int | None`, `context_window: int | None`, `source: str`.
  - `ContextBudgetResolver(Protocol)` — `resolve(*, configured_total: int, configured_series_history: int, effective_output_limit: int, series_in_scope: bool, provider_name: str, model_id: str) -> EffectiveContextBudgets`.
  - `DefaultContextBudgetResolver(model_limits_provider: Callable[[str, str], ModelLimits | None] = get_model_limits)`.
  - Constants in `narrare_core.context.budget`: `DEFAULT_TOTAL_BUDGET = 32_000`, `DEFAULT_SERIES_HISTORY_BUDGET = 16_000`, `RESERVE_FIXED = 4_000`, `SERIES_HISTORY_MAX_SHARE = 0.5`.

- [ ] **Step 1: Write the failing resolver tests**

Create `tests/unit/core/context/test_budget_resolver.py`:

```python
"""Unit tests for the ADR-082 context budget resolver.

Covers the ADR Implementation Notes test list: default no-cap (128k window),
8k-window capping (total 6,000 / series-history 3,000 continuity property),
unknown-window passthrough + source tag, reserve boundary
min(fixed + output, window // 4), and the containment invariant
(series_history + writing_tier_base == context_total).

The window provider is always injected — these tests never touch the
models.dev cache or the network (RULE-07 pure Core).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from narrare_core.context.budget import (
    DEFAULT_SERIES_HISTORY_BUDGET,
    DEFAULT_TOTAL_BUDGET,
    RESERVE_FIXED,
    SERIES_HISTORY_MAX_SHARE,
)
from narrare_core.context.budget_resolver import DefaultContextBudgetResolver
from narrare_core.context.contracts import (
    ContextBudgetResolver,
    EffectiveContextBudgets,
)
from narrare_core.llm import ModelLimits


def _window_provider(window: int | None):
    """Build a ModelLimits provider returning a fixed context window."""

    def _provider(_provider_name: str, _model_id: str) -> ModelLimits | None:
        if window is None:
            return None
        return ModelLimits(context=window, output=4096)

    return _provider


def _resolver(window: int | None) -> DefaultContextBudgetResolver:
    return DefaultContextBudgetResolver(model_limits_provider=_window_provider(window))


def _resolve(resolver: DefaultContextBudgetResolver, **overrides: object) -> EffectiveContextBudgets:
    kwargs: dict[str, object] = {
        "configured_total": 32_000,
        "configured_series_history": 16_000,
        "effective_output_limit": 4_096,
        "series_in_scope": True,
        "provider_name": "anthropic",
        "model_id": "claude-sonnet-4-5-20251020",
    }
    kwargs.update(overrides)
    return resolver.resolve(**kwargs)  # type: ignore[arg-type]


class TestContract:
    def test_default_resolver_satisfies_protocol(self) -> None:
        assert isinstance(DefaultContextBudgetResolver(), ContextBudgetResolver)

    def test_result_model_is_frozen(self) -> None:
        budgets = _resolve(_resolver(128_000))
        with pytest.raises(PydanticValidationError):
            budgets.context_total = 1  # type: ignore[misc]


class TestDefaultNoCap:
    def test_128k_window_applies_full_configured_budget(self) -> None:
        """128k window: reserve 8,096 → cap 119,904 → full 32,000 applies."""
        budgets = _resolve(_resolver(128_000))

        assert budgets.context_total == 32_000
        assert budgets.series_history == 16_000  # 16k = exactly 50% of 32k
        assert budgets.writing_tier_base == 16_000
        assert budgets.reserve_tokens == 8_096  # min(4_000 + 4_096, 128_000 // 4)
        assert budgets.context_window == 128_000
        assert budgets.source == "cascade:uncapped"


class TestSmallWindowCapping:
    def test_8k_window_caps_total_to_6000_and_series_to_3000(self) -> None:
        """PO-approved continuity property: 8k model → reserve 2,000 →
        effective total 6,000 (today's working set, now window-valid),
        series-history ≤ 3,000."""
        budgets = _resolve(_resolver(8_000))

        assert budgets.reserve_tokens == 2_000  # min(8_096, 8_000 // 4)
        assert budgets.context_total == 6_000  # min(32_000, 8_000 - 2_000)
        assert budgets.series_history == 3_000  # min(16_000, floor(0.5 * 6_000))
        assert budgets.writing_tier_base == 3_000
        assert budgets.source == "cascade:capped_to_window"


class TestUnknownWindow:
    def test_unknown_window_passes_configured_through_with_source_tag(self) -> None:
        """RULE-11: no capping on unknown window; proceed + tag provenance."""
        budgets = _resolve(_resolver(None))

        assert budgets.context_total == 32_000
        assert budgets.series_history == 16_000
        assert budgets.writing_tier_base == 16_000
        assert budgets.reserve_tokens is None
        assert budgets.context_window is None
        assert budgets.source == "cascade:window_unknown"


class TestReserveBoundary:
    def test_reserve_uses_fixed_plus_output_on_large_windows(self) -> None:
        budgets = _resolve(_resolver(128_000), effective_output_limit=2_000)

        assert budgets.reserve_tokens == RESERVE_FIXED + 2_000  # 6_000 < 32_000

    def test_reserve_uses_window_quarter_on_small_windows(self) -> None:
        budgets = _resolve(_resolver(8_000), effective_output_limit=4_096)

        assert budgets.reserve_tokens == 8_000 // 4  # 2_000 < 8_096

    def test_reserve_at_equality_boundary(self) -> None:
        """fixed + output == window // 4 → both branches agree on 8,000."""
        budgets = _resolve(_resolver(32_000), effective_output_limit=4_000)

        assert budgets.reserve_tokens == 8_000


class TestMinPrinciple:
    def test_never_scales_up(self) -> None:
        """Configured total below the cap stays as-is (D5 min() only)."""
        budgets = _resolve(
            _resolver(128_000),
            configured_total=4_096,
            configured_series_history=2_048,
        )

        assert budgets.context_total == 4_096
        assert budgets.series_history == 2_048
        assert budgets.source == "cascade:uncapped"


class TestStandaloneAsymmetry:
    def test_standalone_allocates_full_total_to_tiers(self) -> None:
        """series_in_scope=False → no carve-out; tier base = full total."""
        budgets = _resolve(_resolver(128_000), series_in_scope=False)

        assert budgets.series_history == 0
        assert budgets.writing_tier_base == 32_000


class TestContainmentInvariant:
    @pytest.mark.parametrize(
        ("window", "series_in_scope"),
        [
            (128_000, True),
            (128_000, False),
            (8_000, True),
            (8_000, False),
            (None, True),
            (None, False),
        ],
    )
    def test_series_history_plus_tier_base_equals_total(
        self, window: int | None, series_in_scope: bool
    ) -> None:
        budgets = _resolve(
            _resolver(window),
            series_in_scope=series_in_scope,
            configured_series_history=DEFAULT_SERIES_HISTORY_BUDGET,
            configured_total=DEFAULT_TOTAL_BUDGET,
        )

        assert budgets.series_history + budgets.writing_tier_base == budgets.context_total
        assert SERIES_HISTORY_MAX_SHARE == 0.5  # guard pin (ADR-082 Axis 3 Option C)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test-file tests/unit/core/context/test_budget_resolver.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'narrare_core.context.budget_resolver'` (collection error).

- [ ] **Step 3: Add the contract (Protocol + result model) to `context/contracts.py`**

In `packages/core/narrare_core/context/contracts.py`:

3a. Extend the imports (current first import block):

```python
from pydantic import BaseModel, ConfigDict
```

(add after the `from __future__ import annotations` block's existing stdlib import line `from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable` — i.e. the pydantic import becomes the first third-party import, before `from narrare_core.context._kb_envelope import (`).

3b. Extend `__all__` (currently starting with `"ContextAssemblerProtocol",`) to:

```python
__all__ = [
    "ContextAssemblerProtocol",
    "ContextBudgetResolver",
    "EffectiveContextBudgets",
    "KBContextEnvelope",
    "KBContextSource",
    "OmissionReason",
    "ProactiveContextProtocol",
    "ProvenanceField",
    "RenderOptions",
    "RenderedKBContext",
]
```

3c. Append at the end of the file:

```python
class EffectiveContextBudgets(BaseModel):
    """Resolved, model-boundary-capped input-context budgets (frozen).

    Result of :class:`ContextBudgetResolver` (ADR-082 Decision 3). Pure
    data — provenance travels in *source* so consumers can log/preview
    why a value was capped (C1's slider preview reads this verbatim).

    Containment invariant (ADR-082 Decision 6):
    ``series_history + writing_tier_base == context_total`` always holds.
    """

    model_config = ConfigDict(frozen=True)

    context_total: int
    """Effective writing/analysis input total (D2/D4, after window capping)."""
    series_history: int
    """Effective series-history ceiling (D1/D3); ``0`` when not in scope."""
    writing_tier_base: int
    """Total minus series_history (series novels) or the full total."""
    reserve_tokens: int | None
    """Reserve actually applied (``None`` = window unknown, no capping)."""
    context_window: int | None
    """Window used for capping (``None`` = unknown/offline, RULE-11)."""
    source: str
    """Provenance: "cascade:capped_to_window" / "cascade:window_unknown" /
    "cascade:uncapped"."""


@runtime_checkable
class ContextBudgetResolver(Protocol):
    """Resolve configured context budgets against the model boundary (D4).

    Pure resolution contract — implementations must perform no I/O; the
    model-window source is injected (default ``get_model_limits``),
    mirroring ``DefaultRunLimitResolver`` in ``llm/run_limits.py``.
    """

    def resolve(
        self,
        *,
        configured_total: int,
        configured_series_history: int,
        effective_output_limit: int,
        series_in_scope: bool,
        provider_name: str,
        model_id: str,
    ) -> EffectiveContextBudgets:
        """Resolve cascade-configured budgets against the model window.

        Args:
            configured_total: From ``TokenLimitsService`` (cascade).
            configured_series_history: From ``TokenLimitsService`` (cascade).
            effective_output_limit: Resolved output limit (token profiles).
            series_in_scope: Whether this request assembles the
                series-history block (guarded carve-out, Decision 6).
            provider_name: Provider of the effective model for this intent.
            model_id: Model whose context window caps the budgets.

        Returns:
            Frozen effective budgets with provenance. Unknown window →
            configured values pass through uncapped, tagged
            ``"cascade:window_unknown"`` (RULE-11 — never block generation).
        """
        ...
```

This file is now **untouchable** for the remainder of the slice.

- [ ] **Step 4: Add the four Core constants to `context/budget.py` and re-default the writing total**

In `packages/core/narrare_core/context/budget.py`:

4a. In the module docstring, replace the line `Tier allocation (default 6000-token budget):` with `Tier allocation (default 32,000-token budget, ADR-082 Decision 2):`.

4b. After the import line `from narrare_core.context.types import TierBudget`, insert:

```python
# ---------------------------------------------------------------------------
# ADR-082 cascade constants — single source for every input-context budget
# default (backend defaults import these; no literal may exist twice).
# ---------------------------------------------------------------------------

#: Default total input-context budget for writing **and** analysis
#: (ADR-082 Decisions 2/5). Ceiling, not a consumption mandate — tiers
#: fill by content availability (design doc D6).
DEFAULT_TOTAL_BUDGET: int = 32_000

#: Default series-history block ceiling **within** the total (ADR-082
#: Decisions 1/3 — guarded carve-out, not additive). Sits exactly at the
#: 50% guard boundary (16k = 50% of 32k).
DEFAULT_SERIES_HISTORY_BUDGET: int = 16_000

#: Fixed reserve component (ADR-082 Decision 4): auto-injected meta +
#: universal capabilities (≈750 tok), feature system prompt (≈900 tok),
#: unbudgeted pass-through variables (≈1,350 tok) — headroom-rounded.
RESERVE_FIXED: int = 4_000

#: Maximum share of the effective total the series-history block may
#: consume (ADR-082 Axis 3 Option C): structurally prevents the
#: degenerate small-window carve-out (both sides always ≥ half).
SERIES_HISTORY_MAX_SHARE: float = 0.5
```

4c. In `class TokenBudgetManager`, replace the class attribute:

```python
    DEFAULT_TOTAL_BUDGET: int = 6000
```

with:

```python
    DEFAULT_TOTAL_BUDGET: int = DEFAULT_TOTAL_BUDGET
```

(The RHS resolves to the new module-level constant — the class attribute remains for backward compatibility; the `total_budget: int = DEFAULT_TOTAL_BUDGET` default in `__init__` picks it up unchanged.)

- [ ] **Step 5: Create `context/budget_resolver.py`**

Create `packages/core/narrare_core/context/budget_resolver.py`:

```python
"""Model-boundary capping for input-context token budgets (ADR-082).

Pure resolution arithmetic — no I/O. Mirrors ``DefaultRunLimitResolver``
(``llm/run_limits.py``): the window provider callable is injected
(default ``get_model_limits``, models.dev-backed with local cache), so
unit tests never touch the cache or network (RULE-07).

Arithmetic (ADR-082 Decisions 3/4):

    reserve         = min(RESERVE_FIXED + effective_output_limit, window // 4)
    effective_total = min(configured_total, window - reserve)    if window known
                    = configured_total                            if unknown
    series_history  = min(configured_sh, floor(SERIES_HISTORY_MAX_SHARE * total))
                      -- in-scope only; 0 for standalone requests
    tier_base       = total - series_history

The resolver only ever caps **down** (min() principle, design doc D5);
the ``window // 4`` guard makes ``window - reserve`` structurally
positive (reserve ≤ window/4 < window).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.context.budget import RESERVE_FIXED, SERIES_HISTORY_MAX_SHARE
from narrare_core.context.contracts import EffectiveContextBudgets
from narrare_core.llm.cost_rates import get_model_limits

if TYPE_CHECKING:
    from collections.abc import Callable

    from narrare_core.llm.cost_rates import ModelLimits

logger = structlog.get_logger(__name__)

__all__ = ["DefaultContextBudgetResolver"]


class DefaultContextBudgetResolver:
    """Default implementation of the ADR-082 ContextBudgetResolver contract."""

    def __init__(
        self,
        *,
        model_limits_provider: Callable[[str, str], ModelLimits | None] = get_model_limits,
    ) -> None:
        self._model_limits_provider = model_limits_provider

    def resolve(
        self,
        *,
        configured_total: int,
        configured_series_history: int,
        effective_output_limit: int,
        series_in_scope: bool,
        provider_name: str,
        model_id: str,
    ) -> EffectiveContextBudgets:
        """Resolve configured context budgets against the model boundary."""
        provider_limits = self._model_limits_provider(provider_name, model_id)
        window = provider_limits.context if provider_limits is not None else None

        if window is None:
            # RULE-11: unknown window (unknown model / offline no cache) →
            # no capping, proceed with configured values, tag provenance
            # (mirrors ``provider_max_unknown`` in run_limits.py).
            logger.warning(
                "context_budget_window_unknown",
                provider=provider_name,
                model=model_id,
            )
            series_history = configured_series_history if series_in_scope else 0
            return EffectiveContextBudgets(
                context_total=configured_total,
                series_history=series_history,
                writing_tier_base=configured_total - series_history,
                reserve_tokens=None,
                context_window=None,
                source="cascade:window_unknown",
            )

        reserve = min(RESERVE_FIXED + effective_output_limit, window // 4)
        capped_total = window - reserve
        if configured_total <= capped_total:
            total = configured_total
            source = "cascade:uncapped"
        else:
            total = capped_total
            source = "cascade:capped_to_window"

        series_history = 0
        if series_in_scope:
            series_history = min(
                configured_series_history,
                int(SERIES_HISTORY_MAX_SHARE * total),
            )

        return EffectiveContextBudgets(
            context_total=total,
            series_history=series_history,
            writing_tier_base=total - series_history,
            reserve_tokens=reserve,
            context_window=window,
            source=source,
        )
```

- [ ] **Step 6: Run the resolver tests to verify they pass**

Run: `just test-file tests/unit/core/context/test_budget_resolver.py`
Expected: PASS — all 16 tests (2 contract + 1 no-cap + 1 8k + 1 unknown + 3 reserve + 1 min + 1 standalone + 6 containment params).

- [ ] **Step 7: Run the context/budget neighborhood to catch default-change fallout**

Run: `just test-file tests/unit/core/context/ tests/unit/core/writing/test_budget.py tests/unit/core/writing/test_context_assembler.py`
Expected: PASS. (The default change 6,000→32,000 is safe: existing tests pin the default only *relatively* — `tests/unit/core/context/test_assembler.py` asserts `asm.total_budget == TokenBudgetManager.DEFAULT_TOTAL_BUDGET` — or pass explicit budgets. Any failure here that asserts a literal `6000` on a default-constructed manager/assembler is an unexpected default-regression: fix the assertion to the new default and record it in the task report.)

- [ ] **Step 8: Commit (via Platform, verbatim)**

```bash
git add packages/core/narrare_core/context/contracts.py \
        packages/core/narrare_core/context/budget.py \
        packages/core/narrare_core/context/budget_resolver.py \
        tests/unit/core/context/test_budget_resolver.py
```

Commit message:

```
feat(core): add context budget resolver and ADR-082 core budget constants

Implements ADR-082 Decisions 2-4 (Core half):
- context/contracts.py: EffectiveContextBudgets frozen result model +
  ContextBudgetResolver Protocol (RULE-03, authored first; untouchable
  for the remainder of the C5 slice)
- context/budget_resolver.py: DefaultContextBudgetResolver — pure
  arithmetic, injected window provider (default get_model_limits),
  mirroring DefaultRunLimitResolver (ADR-045 pattern). reserve =
  min(RESERVE_FIXED + effective_output_limit, window // 4);
  effective_total = min(configured, window - reserve); unknown window
  -> uncapped passthrough + "cascade:window_unknown" source tag (RULE-11)
- context/budget.py: DEFAULT_TOTAL_BUDGET 6,000 -> 32,000 as exported
  module constant (single source); new DEFAULT_SERIES_HISTORY_BUDGET =
  16,000, RESERVE_FIXED = 4_000, SERIES_HISTORY_MAX_SHARE = 0.5

Intentional default break (documented, migration-free — ADR-082
Decision 7): writing total ceiling 6,000 -> 32,000; budgets are
ceilings, not consumption mandates (design doc D6). Resolver only ever
caps down (min() principle, D5).

Tests: 16 resolver unit tests (128k no-cap, 8k-window continuity
property 6,000/3,000, unknown-window tag, reserve boundary, containment
invariant, standalone asymmetry, never-scales-up).

Refs: ADR-082, docs/superpowers/specs/2026-08-14-post-export-followups-design.md §3 (C5)
```

---

### Task 1b: Core re-defaults — series-history 16k, analysis 32k

**Files:**
- Modify: `packages/core/narrare_core/context/series_history.py` (`assemble` default 512 → `DEFAULT_SERIES_HISTORY_BUDGET`)
- Modify: `packages/core/narrare_core/analysis/budget.py` (`AnalysisBudgetManager.DEFAULT_TOTAL_BUDGET` 6,000 → Core constant reference)
- Modify: `packages/core/narrare_core/analysis/contracts.py` (docstring-only — stale 6,000-default reference, Step 5)
- Modify: `packages/core/narrare_core/analysis/assembler.py` (docstring-only — stale 6,000-default references, Step 5)
- Test: `tests/unit/core/context/test_series_history.py` (add default-budget pins), `tests/unit/core/analysis/test_budget.py` (rewrite the default assertion), `tests/unit/core/writing/test_budget.py` (add writing-manager default pin)

**Interfaces:**
- Consumes: `narrare_core.context.budget.DEFAULT_SERIES_HISTORY_BUDGET`, `narrare_core.context.budget.DEFAULT_TOTAL_BUDGET` (Task 1a).
- Produces: `SeriesHistoryTier.assemble(bands, window_size=3, token_budget=DEFAULT_SERIES_HISTORY_BUDGET)`; `AnalysisBudgetManager.DEFAULT_TOTAL_BUDGET == 32_000` (same Core constant, no third literal).

- [ ] **Step 1: Write the failing default-pin tests**

1a. In `tests/unit/core/context/test_series_history.py`, extend the top import block:

```python
from narrare_core.context.budget import DEFAULT_SERIES_HISTORY_BUDGET
from narrare_core.context.series_history import BandSummaryData, SeriesHistoryTier
```

(replacing the single existing `from narrare_core.context.series_history import ...` line), then append at the end of the file:

```python
# ---------------------------------------------------------------------------
# Default budget (ADR-082 D1: 512 -> 16,000)
# ---------------------------------------------------------------------------


class TestDefaultBudget:
    """The re-defaulted 16,000-token budget fixes the C5 headline defect:
    the default recency window (3 full band summaries) now fits."""

    async def test_default_budget_delivers_three_full_bands(self) -> None:
        bands = [
            _band(1, full=_long("B1"), short="S1"),
            _band(2, full=_long("B2"), short="S2"),
            _band(3, full=_long("B3"), short="S3"),
        ]
        tier = SeriesHistoryTier()

        result = await tier.assemble(bands=bands, window_size=3)

        # All three bands complete — under the old 512 default, band 2
        # truncated and band 3+ was silently dropped.
        assert "B1START" in result and "B1END" in result
        assert "B2START" in result and "B2END" in result
        assert "B3START" in result and "B3END" in result

    async def test_assemble_default_token_budget_is_core_constant(self) -> None:
        import inspect

        signature = inspect.signature(SeriesHistoryTier.assemble)

        assert signature.parameters["token_budget"].default == DEFAULT_SERIES_HISTORY_BUDGET
```

1b. In `tests/unit/core/analysis/test_budget.py`:
- Extend imports: add `from narrare_core.context.budget import DEFAULT_TOTAL_BUDGET` after the existing `from narrare_core.analysis.budget import AnalysisBudgetManager` line.
- Replace the class docstring `"""Default 6000-token budget with 50/30/20 split."""` with `"""Default 32,000-token budget (ADR-082) with 50/30/20 split."""`.
- Rewrite the default assertion (class `TestTotalBudgetProperty`):

```python
    def test_default_total_budget(self) -> None:
        manager = AnalysisBudgetManager()
        assert manager.total_budget == DEFAULT_TOTAL_BUDGET  # ADR-082: 32,000
```

(The `total_budget=6000` fixtures elsewhere in the file stay — explicit inputs are allocation-arithmetic fixtures, not default regressions.)

1c. In `tests/unit/core/writing/test_budget.py`, extend imports with `from narrare_core.context.budget import DEFAULT_TOTAL_BUDGET` and append:

```python
class TestDefaultTotalBudget:
    def test_default_total_budget_is_core_constant(self) -> None:
        """ADR-082 D2: writing manager default re-defaulted 6,000 -> 32,000."""
        assert TokenBudgetManager.DEFAULT_TOTAL_BUDGET == DEFAULT_TOTAL_BUDGET
        assert TokenBudgetManager().total_budget == DEFAULT_TOTAL_BUDGET
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test-file tests/unit/core/context/test_series_history.py tests/unit/core/analysis/test_budget.py tests/unit/core/writing/test_budget.py`
Expected: FAIL — new default tests fail against the still-old defaults (512 / 6,000); `test_default_total_budget` fails with `AssertionError: assert 6000 == 32000`.

- [ ] **Step 3: Re-default `SeriesHistoryTier.assemble`**

In `packages/core/narrare_core/context/series_history.py`:

3a. Add after the `from dataclasses import dataclass` import:

```python
from narrare_core.context.budget import DEFAULT_SERIES_HISTORY_BUDGET
```

3b. In `SeriesHistoryTier.assemble`, replace the parameter default:

```python
        token_budget: int = 512,
```

with:

```python
        token_budget: int = DEFAULT_SERIES_HISTORY_BUDGET,
```

and extend its docstring line `token_budget: Maximum (estimated) tokens for the whole block,` with the following line inserted after it:

```python
                Default 16,000 (ADR-082 D1; the API passes the resolved
                cascade value — the parameter stays explicit).
```

- [ ] **Step 4: Re-default `AnalysisBudgetManager`**

In `packages/core/narrare_core/analysis/budget.py`:

4a. Replace the module docstring line `Tier allocation (default 6000-token budget):` with `Tier allocation (default 32,000-token budget, ADR-082 Decision 5 — shares context_total_budget with writing):`.

4b. Add after the `from narrare_core.context.types import TierBudget` import:

```python
from narrare_core.context.budget import DEFAULT_TOTAL_BUDGET
```

4c. Replace the class attribute:

```python
    DEFAULT_TOTAL_BUDGET: int = 6000
```

with:

```python
    # ADR-082 Decision 5: analysis joins context_total_budget — same Core
    # constant as the writing manager, never a third literal.
    DEFAULT_TOTAL_BUDGET: int = DEFAULT_TOTAL_BUDGET
```

(The class-body RHS resolves to the module-level import; `__init__`'s `total_budget: int = DEFAULT_TOTAL_BUDGET` default picks it up unchanged.)

- [ ] **Step 5: Correct the stale 6,000-default docstrings (docstring-only, no behavior change)**

5a. In `packages/core/narrare_core/analysis/contracts.py`, in the `AnalysisAssemblerProtocol` docstring, replace the line:

```python
    Tier allocation (default 6000-token budget):
```

with:

```python
    Tier allocation (default 32,000-token budget, ADR-082 Decision 5):
```

5b. In `packages/core/narrare_core/analysis/assembler.py`, in the `AnalysisContextAssembler` docstring, replace the line:

```python
    Tier allocation (default 6000-token budget):
```

with:

```python
    Tier allocation (default 32,000-token budget, ADR-082 Decision 5):
```

and in the same docstring's usage example, replace:

```python
        assembler = AnalysisContextAssembler(total_budget=6000)
```

with:

```python
        assembler = AnalysisContextAssembler(total_budget=32_000)
```

(Docstring-only edits — no runtime behavior changes, tests unaffected.)

- [ ] **Step 6: Run the tests to verify they pass**

Run: `just test-file tests/unit/core/context/test_series_history.py tests/unit/core/analysis/test_budget.py tests/unit/core/writing/test_budget.py`
Expected: PASS — including the pre-existing explicit-budget fixtures (unchanged behavior at explicit inputs).

- [ ] **Step 7: Sweep the re-defaulted Core modules for stale literals**

Run: `rg -n "6_000|6000|= 512" packages/core/narrare_core/context/budget.py packages/core/narrare_core/analysis/budget.py packages/core/narrare_core/context/series_history.py packages/core/narrare_core/analysis/contracts.py packages/core/narrare_core/analysis/assembler.py`
Expected: **no output** (zero matches — the sweep now also covers the Step 5 docstring files).

- [ ] **Step 8: Run the wider analysis/assembler neighborhood**

Run: `just test-file tests/unit/core/analysis/ tests/unit/core/writing/test_series_history_variable.py tests/unit/api/series/test_series_history_provider.py`
Expected: PASS. (`tests/unit/api/analysis/test_beta_reader_kb_context.py` uses `AnalysisContextAssembler()` with small fixtures — headroom only grows; if any test asserted truncation relative to the 6,000 default, rewrite that assertion to the new 32,000-based expectation and record it in the task report.)

- [ ] **Step 9: Commit (via Platform, verbatim)**

```bash
git add packages/core/narrare_core/context/series_history.py \
        packages/core/narrare_core/analysis/budget.py \
        packages/core/narrare_core/analysis/contracts.py \
        packages/core/narrare_core/analysis/assembler.py \
        tests/unit/core/context/test_series_history.py \
        tests/unit/core/analysis/test_budget.py \
        tests/unit/core/writing/test_budget.py
```

Commit message:

```
feat(core): re-default series-history and analysis budgets per ADR-082

Lifts ADR-082 inventory items (a)1 and (a)4 into the new defaults:
- SeriesHistoryTier.assemble token_budget default 512 -> 16,000
  (DEFAULT_SERIES_HISTORY_BUDGET). Fixes the C5 headline defect: the
  default recency window (3 full band summaries, ~1,200+ tokens) could
  never fit 512 — band 2 truncated, band 3+ silently dropped. Parameter
  stays explicit; the API passes the resolved cascade value (Task 3).
- AnalysisBudgetManager.DEFAULT_TOTAL_BUDGET 6,000 -> 32,000,
  referencing the same narrare_core.context.budget constant as the
  writing manager (Decision 5: one knob, no third literal). The
  analysis content tier (50%) now covers ~12,300 words instead of
  ~2,300 — most chapters are no longer silently cut.
- Stale 6,000-default docstrings corrected (docstring-only) in
  analysis/contracts.py and analysis/assembler.py — tier-allocation
  docs and the usage example now state the 32,000 default.

Documented intentional default break (ADR-082 Decision 7): regression
pins rewritten/added (default = imported Core constant, drift-proof);
explicit-budget fixtures unchanged (allocation arithmetic is
budget-agnostic).

Refs: ADR-082, docs/superpowers/specs/2026-08-14-post-export-followups-design.md §3.3
```

---

### Task 2a: SET-005 cascade keys — contracts + write-boundary validators

**Files:**
- Modify: `apps/api/narrare/settings/token_limits/contracts.py` (+2 fields on `TokenLimitOverrides` — contract file, untouchable afterward within this slice)
- Modify: `apps/api/narrare/settings/token_limits/_validators.py` (+2 keys in `VALID_OVERRIDE_FIELDS`, `ge=1_024` bounds at the write boundary)
- Test: `tests/unit/api/settings/test_token_limits_context_budgets.py` (new)

**Interfaces:**
- Consumes: `narrare_core.context.budget.DEFAULT_TOTAL_BUDGET`, `DEFAULT_SERIES_HISTORY_BUDGET` (Task 1a).
- Produces (verbatim for all later tasks): `TokenLimitOverrides.context_total_budget: int = 32_000`, `TokenLimitOverrides.series_history_budget: int = 16_000`; validator accepts both keys with `int >= 1_024`, rejects below-bound / non-int with code `INVALID_BUDGET_BOUNDS`.

- [ ] **Step 1: Write the failing contract + validator tests**

Create `tests/unit/api/settings/test_token_limits_context_budgets.py`:

```python
"""Contract + write-boundary tests for the ADR-082 context budget keys.

Covers: defaults single-sourced from Core constants (DEFAULT_TOKEN_PROFILE
precedent — backend and Core cannot drift), write-boundary bounds
(ge=1_024, ADR-082 Decision 1), and unknown-key rejection unchanged.
"""

from __future__ import annotations

import pytest

from narrare.settings.token_limits._validators import (
    VALID_OVERRIDE_FIELDS,
    validate_token_overrides,
)
from narrare.settings.token_limits.contracts import TokenLimitOverrides
from narrare_core.context.budget import (
    DEFAULT_SERIES_HISTORY_BUDGET,
    DEFAULT_TOTAL_BUDGET,
)
from narrare_core.shared.errors import ValidationError


class TestContractDefaults:
    def test_context_total_budget_defaults_to_core_constant(self) -> None:
        assert TokenLimitOverrides().context_total_budget == DEFAULT_TOTAL_BUDGET

    def test_series_history_budget_defaults_to_core_constant(self) -> None:
        assert TokenLimitOverrides().series_history_budget == DEFAULT_SERIES_HISTORY_BUDGET

    def test_defaults_are_32k_and_16k(self) -> None:
        """ADR-082 Decisions 1/2 — literal pin (catches accidental constant
        re-defaults without a plan)."""
        assert TokenLimitOverrides().context_total_budget == 32_000
        assert TokenLimitOverrides().series_history_budget == 16_000

    def test_explicit_values_preserved(self) -> None:
        overrides = TokenLimitOverrides(
            context_total_budget=65_536, series_history_budget=8_192
        )
        assert overrides.context_total_budget == 65_536
        assert overrides.series_history_budget == 8_192


class TestWriteBoundary:
    def test_both_keys_are_valid_override_fields(self) -> None:
        assert "context_total_budget" in VALID_OVERRIDE_FIELDS
        assert "series_history_budget" in VALID_OVERRIDE_FIELDS

    @pytest.mark.parametrize(
        "overrides",
        [
            {"context_total_budget": 65_536},
            {"series_history_budget": 8_192},
            {"context_total_budget": 1_024, "series_history_budget": 1_024},
            # Sibling keys still validate (unchanged behavior).
            {"context_total_budget": 65_536, "ws_timeout": 3_600},
        ],
    )
    def test_accepts_valid_values(self, overrides: dict[str, object]) -> None:
        validate_token_overrides(overrides)  # must not raise

    @pytest.mark.parametrize(
        "overrides",
        [
            {"context_total_budget": 1_023},  # below ge=1_024
            {"series_history_budget": 0},
            {"context_total_budget": 2_048, "series_history_budget": 512},
        ],
    )
    def test_rejects_below_bound(self, overrides: dict[str, object]) -> None:
        with pytest.raises(ValidationError, match="must be >=") as excinfo:
            validate_token_overrides(overrides)
        assert excinfo.value.code == "INVALID_BUDGET_BOUNDS"

    @pytest.mark.parametrize(
        "overrides",
        [
            {"context_total_budget": "32000"},  # str, not int
            {"series_history_budget": 16_000.5},  # float
            {"context_total_budget": True},  # bool is not an int budget
        ],
    )
    def test_rejects_non_int_values(self, overrides: dict[str, object]) -> None:
        with pytest.raises(ValidationError, match="must be an integer"):
            validate_token_overrides(overrides)

    def test_unknown_field_still_rejected(self) -> None:
        # Deliberately typo'd key — unknown-field rejection is unchanged.
        with pytest.raises(ValidationError, match="Unknown token limit override field"):
            validate_token_overrides({"context_total_budgt": 32_000})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test-file tests/unit/api/settings/test_token_limits_context_budgets.py`
Expected: FAIL — contract tests fail with `TypeError: unexpected keyword argument 'context_total_budget'` (dataclass lacks the fields); validator tests fail (`context_total_budget` not in `VALID_OVERRIDE_FIELDS` makes the valid-value tests raise; the bound/non-int tests fail because no `ValidationError` is raised).

- [ ] **Step 3: Add the two fields to `TokenLimitOverrides`**

In `apps/api/narrare/settings/token_limits/contracts.py`:

3a. Extend imports — add after the existing `from narrare_core.llm.token_profiles import (` block:

```python
from narrare_core.context.budget import (
    DEFAULT_SERIES_HISTORY_BUDGET,
    DEFAULT_TOTAL_BUDGET,
)
```

3b. In `TokenLimitOverrides`, append after the `max_selection_words` field (whose docstring ends `"""Maximum word count for co-author selection text (SET-005 cascade)."""`):

```python
    context_total_budget: int = DEFAULT_TOTAL_BUDGET
    """Total input-context token budget for writing AND analysis
    (ADR-082 Decisions 1/5 — one knob). Ceiling, not a consumption
    mandate; capped against the model's context window at runtime by the
    ContextBudgetResolver (``min(configured, window - reserve)``; the
    resolver never scales up — design doc D5). Default single-sourced
    from Core (DEFAULT_TOKEN_PROFILE precedent).
    """
    series_history_budget: int = DEFAULT_SERIES_HISTORY_BUDGET
    """Series-history block ceiling WITHIN the total (ADR-082 Decisions
    1/3 — guarded carve-out, not additive). Effective value =
    ``min(configured, 50% x effective_total)`` when series history is in
    scope.
    """
```

This contract file is now **untouchable** for the remainder of the slice.

- [ ] **Step 4: Extend the write-boundary validators**

In `apps/api/narrare/settings/token_limits/_validators.py`:

4a. Extend `VALID_OVERRIDE_FIELDS` — insert before the closing `}` (after the `"max_selection_words",` entry):

```python
    # Input-context budgets (ADR-082 / C5)
    "context_total_budget",
    "series_history_budget",
```

4b. After the `VALID_OVERRIDE_FIELDS` definition, add:

```python
#: Minimum sane values for integer budget keys (write boundary, ADR-082
#: Decision 1 — "ge=1_024-style sanity bounds"). Guards against
#: degenerate overrides (e.g. 1-token totals) without capping ambition.
_INT_FIELD_MINIMA: dict[str, int] = {
    "context_total_budget": 1_024,
    "series_history_budget": 1_024,
}
```

4c. In `validate_token_overrides`, after the existing `token_profile` check block (ending with `code="INVALID_TOKEN_PROFILE",\n            )`), append inside the `for` loop:

```python
        minimum = _INT_FIELD_MINIMA.get(key)
        if minimum is not None:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValidationError(
                    f"Token limit override '{key}' must be an integer, "
                    f"got {type(value).__name__}",
                    code="INVALID_BUDGET_BOUNDS",
                )
            if value < minimum:
                raise ValidationError(
                    f"Token limit override '{key}' must be >= {minimum}, got {value}",
                    code="INVALID_BUDGET_BOUNDS",
                )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `just test-file tests/unit/api/settings/test_token_limits_context_budgets.py`
Expected: PASS — 16 tests.

Also run the existing validator/update suites to prove no regression:
Run: `just test-file tests/unit/api/settings/test_token_limits_updates.py tests/unit/api/settings/test_token_limits_service.py`
Expected: PASS.

- [ ] **Step 6: Commit (via Platform, verbatim)**

```bash
git add apps/api/narrare/settings/token_limits/contracts.py \
        apps/api/narrare/settings/token_limits/_validators.py \
        tests/unit/api/settings/test_token_limits_context_budgets.py
```

Commit message:

```
feat(api): add context_total_budget and series_history_budget cascade keys

ADR-082 Decision 1 (Axis 1 Option C — extend the existing SET-005
vocabulary): two new keys on TokenLimitOverrides, defaults
single-sourced from narrare_core.context.budget (32,000 / 16,000) so
backend and Core cannot drift (DEFAULT_TOKEN_PROFILE precedent).

- contracts.py: context_total_budget (one knob for writing AND
  analysis, Decision 5) + series_history_budget (guarded carve-out
  within the total, Decision 6). JSONB overrides store absorbs both —
  no Alembic migration (RULE-14). Contract authored first (RULE-03);
  untouchable for the remainder of the C5 slice.
- _validators.py: both keys join VALID_OVERRIDE_FIELDS; write boundary
  enforces integer values >= 1,024 (INVALID_BUDGET_BOUNDS).

No UI in C5 (design doc §11 — expert-invisible; the existing
token-limits PATCH API becomes the user-configuration surface D5
requires). Env layer + resolution merge follow in the next commit.

Refs: ADR-082, docs/superpowers/specs/2026-08-14-post-export-followups-design.md §3.1 (D1/D2/D5)
```

---

### Task 2b: Operator-env layer + service merge + provider default

**Files:**
- Modify: `apps/api/narrare/_app/settings_model.py` (+2 env Fields)
- Modify: `apps/api/narrare/settings/token_limits/service.py` (`_apply_env_layer` + `_merge_overrides` carry the new fields)
- Modify: `apps/api/narrare/series/series_history_provider.py` (`_DEFAULT_TOKEN_BUDGET` derives from the Core constant)
- Test: `tests/unit/api/settings/test_token_limits_resolution.py` (extend `_FakeConfig` + new resolution tests), `tests/unit/api/series/test_series_history_provider.py` (constant-derivation pin)

**Interfaces:**
- Consumes: `TokenLimitOverrides.context_total_budget` / `.series_history_budget` (Task 2a); `DEFAULT_SERIES_HISTORY_BUDGET` (Task 1a).
- Produces: `Settings.context_total_budget` / `Settings.series_history_budget` (env `NARRARE_CONTEXT_TOTAL_BUDGET` / `NARRARE_SERIES_HISTORY_BUDGET`, `ge=1_024`, Core-derived defaults); full three-layer resolution for both keys (user-DB → project-DB → operator-env → code-defaults); `SeriesHistoryProvider` module constant `_DEFAULT_TOKEN_BUDGET == DEFAULT_SERIES_HISTORY_BUDGET`.

**Why `_merge_overrides` must change too (correctness note):** `_merge_overrides` constructs a fresh `TokenLimitOverrides` listing every field explicitly. A field missing there is silently reset to the class default — which would discard operator-env values on every DB merge. The ADR wiring sketch names `_apply_env_layer`; `_merge_overrides` is equally load-bearing and is included here.

- [ ] **Step 1: Write the failing resolution + provider tests**

1a. In `tests/unit/api/settings/test_token_limits_resolution.py`:

- Extend the `_FakeConfig` dataclass (currently ending with `default_max_selection_words: int = 2000`) by appending:

```python
    context_total_budget: int = DEFAULT_TOTAL_BUDGET
    series_history_budget: int = DEFAULT_SERIES_HISTORY_BUDGET
```

- Add to the import block at the top:

```python
from narrare_core.context.budget import (
    DEFAULT_SERIES_HISTORY_BUDGET,
    DEFAULT_TOTAL_BUDGET,
)
```

- Append a new test class after `TestGetResolvedLimits`:

```python
class TestContextBudgetResolution:
    """ADR-082: the two context-budget keys resolve through the full
    cascade (user-DB -> project-DB -> operator-env -> code defaults)."""

    async def test_no_overrides_returns_core_constants(self, service: Any) -> None:
        limits = await service.get_resolved_limits(user_id="user_ctx_default")

        assert limits.context_total_budget == DEFAULT_TOTAL_BUDGET  # 32,000
        assert limits.series_history_budget == DEFAULT_SERIES_HISTORY_BUDGET  # 16,000

    async def test_env_layer_applies_operator_values(
        self, store: _FakeStore, fake_config: _FakeConfig
    ) -> None:
        fake_config.context_total_budget = 48_000
        fake_config.series_history_budget = 12_000
        service = _make_service(store, fake_config)

        limits = await service.get_resolved_limits(user_id="user_ctx_env")

        assert limits.context_total_budget == 48_000
        assert limits.series_history_budget == 12_000

    async def test_user_override_wins_over_env(
        self, store: _FakeStore, fake_config: _FakeConfig
    ) -> None:
        fake_config.context_total_budget = 48_000
        service = _make_service(store, fake_config)
        store.seed_user("user_ctx_win", {"context_total_budget": 65_536})

        limits = await service.get_resolved_limits(user_id="user_ctx_win")

        assert limits.context_total_budget == 65_536
        assert limits.series_history_budget == DEFAULT_SERIES_HISTORY_BUDGET

    async def test_project_override_applies_without_user_override(
        self, store: _FakeStore, service: Any
    ) -> None:
        store.seed_project("project_ctx", {"series_history_budget": 8_192})

        limits = await service.get_resolved_limits(
            user_id="user_ctx_project", project_id="project_ctx"
        )

        assert limits.series_history_budget == 8_192

    async def test_env_values_survive_unrelated_db_merge(
        self, store: _FakeStore, fake_config: _FakeConfig
    ) -> None:
        """Regression for the _merge_overrides carry-through: an override
        dict for OTHER keys must not reset the env-layer budget values to
        code defaults."""
        fake_config.context_total_budget = 48_000
        service = _make_service(store, fake_config)
        store.seed_user("user_ctx_merge", {"ws_timeout": 3_600})

        limits = await service.get_resolved_limits(user_id="user_ctx_merge")

        assert limits.ws_timeout == 3_600
        assert limits.context_total_budget == 48_000
```

- Add a `_make_service` helper right after the `service` fixture (reusing the fixture's construction so the new tests can vary `fake_config`):

```python
def _make_service(store: _FakeStore, fake_config: _FakeConfig) -> Any:
    """TokenLimitsService over the shared fakes (config varies per test)."""
    from narrare.settings.token_limits.service import TokenLimitsService

    return TokenLimitsService(
        user_repo=_FakeUserRepo(store.users),  # pyright: ignore[reportArgumentType]
        project_repo=_FakeProjectRepo(store.projects),  # pyright: ignore[reportArgumentType]
        config=fake_config,  # pyright: ignore[reportArgumentType]
    )
```

1b. In `tests/unit/api/series/test_series_history_provider.py`, append:

```python
class TestDefaultTokenBudget:
    def test_provider_default_derives_from_core_constant(self) -> None:
        """ADR-082 inventory (a)2: the mirror constant must not drift from
        the Core default (the old 512/512 mirror pair was the defect)."""
        from narrare.series.series_history_provider import _DEFAULT_TOKEN_BUDGET
        from narrare_core.context.budget import DEFAULT_SERIES_HISTORY_BUDGET

        assert _DEFAULT_TOKEN_BUDGET == DEFAULT_SERIES_HISTORY_BUDGET
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test-file tests/unit/api/settings/test_token_limits_resolution.py tests/unit/api/series/test_series_history_provider.py`
Expected: FAIL — the env-layer tests fail with `AssertionError: assert 32000 == 48000`-style errors (`_apply_env_layer` drops the new fields), and `test_env_values_survive_unrelated_db_merge` fails (`_merge_overrides` resets env values to code defaults). `test_no_overrides_returns_core_constants` passes already (Task 2a contract defaults) — that is expected; it pins the code-defaults layer. The provider test fails with `AssertionError: assert 512 == 16000`.

- [ ] **Step 3: Add the two operator-env Fields**

In `apps/api/narrare/_app/settings_model.py`:

3a. Add after the `from pydantic_settings import BaseSettings, SettingsConfigDict` import:

```python
from narrare_core.context.budget import (
    DEFAULT_SERIES_HISTORY_BUDGET,
    DEFAULT_TOTAL_BUDGET,
)
```

3b. In the `# Token Limits (Operator-Config)` section, insert directly after the `default_max_tokens` field (docstring `"""Default output token limit for LLM calls. Used as fallback when no token_limit_profile is set."""`):

```python
    context_total_budget: int = Field(
        default=DEFAULT_TOTAL_BUDGET,
        ge=1_024,
        alias="NARRARE_CONTEXT_TOTAL_BUDGET",
    )
    """Default total input-context budget for writing + analysis (ADR-082).

    Ceiling, not a consumption mandate; runtime capping against the
    model's context window applies on top (min(configured, window -
    reserve) — never scaled up).
    """

    series_history_budget: int = Field(
        default=DEFAULT_SERIES_HISTORY_BUDGET,
        ge=1_024,
        alias="NARRARE_SERIES_HISTORY_BUDGET",
    )
    """Default series-history block ceiling within the total (ADR-082)."""
```

- [ ] **Step 4: Carry the fields through the service cascade**

In `apps/api/narrare/settings/token_limits/service.py`:

4a. In `_apply_env_layer`, extend the returned constructor (currently ending with `max_selection_words=cfg.default_max_selection_words,`) by appending:

```python
            context_total_budget=cfg.context_total_budget,
            series_history_budget=cfg.series_history_budget,
```

4b. In `_merge_overrides`, extend the returned constructor (currently ending with `max_selection_words=cast("int", overrides.get("max_selection_words", base.max_selection_words)),`) by appending:

```python
            context_total_budget=cast(
                "int", overrides.get("context_total_budget", base.context_total_budget)
            ),
            series_history_budget=cast(
                "int",
                overrides.get("series_history_budget", base.series_history_budget),
            ),
```

- [ ] **Step 5: Re-default the provider mirror constant**

In `apps/api/narrare/series/series_history_provider.py`:

5a. Extend imports — replace:

```python
from narrare_core.context.series_history import BandSummaryData, SeriesHistoryTier
```

with:

```python
from narrare_core.context.budget import DEFAULT_SERIES_HISTORY_BUDGET
from narrare_core.context.series_history import BandSummaryData, SeriesHistoryTier
```

5b. Replace the constant and its comment:

```python
#: Default token budget for the series-history block. Mirrors the tier default;
#: the writing pipeline's real budgeting happens at the assembler level.
_DEFAULT_TOKEN_BUDGET: int = 512
```

with:

```python
#: Default token budget for the series-history block (ADR-082 D1: 16,000,
#: derived from the Core constant — the old 512/512 mirror pair was the C5
#: defect). The production call site passes the resolved cascade value
#: (writing/_helpers.py, Task 3); this default covers unparameterized calls.
_DEFAULT_TOKEN_BUDGET: int = DEFAULT_SERIES_HISTORY_BUDGET
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `just test-file tests/unit/api/settings/test_token_limits_resolution.py tests/unit/api/series/test_series_history_provider.py tests/unit/api/settings/test_token_limits_context_budgets.py`
Expected: PASS — all new resolution + provider tests green; Task 2a tests still green.

- [ ] **Step 7: Run the full settings suite + architecture checker**

Run: `just test-file tests/unit/api/settings/ && just check-architecture`
Expected: PASS both (new module imports follow the existing API→Core direction automatically).

- [ ] **Step 8: Commit (via Platform, verbatim)**

```bash
git add apps/api/narrare/_app/settings_model.py \
        apps/api/narrare/settings/token_limits/service.py \
        apps/api/narrare/series/series_history_provider.py \
        tests/unit/api/settings/test_token_limits_resolution.py \
        tests/unit/api/series/test_series_history_provider.py
```

Commit message:

```
feat(api): wire context budget keys through env layer and service merge

Completes the ADR-082 Decision 1 cascade surface:
- settings_model.py: operator-env Fields NARRARE_CONTEXT_TOTAL_BUDGET /
  NARRARE_SERIES_HISTORY_BUDGET (ge=1_024, defaults imported from Core —
  no drift possible)
- service.py::_apply_env_layer: env values enter the cascade
- service.py::_merge_overrides: both fields carried through DB merges
  (a missing field here would silently reset env values to code
  defaults on every merge — covered by an explicit regression test)
- series_history_provider.py: _DEFAULT_TOKEN_BUDGET 512 -> derived from
  DEFAULT_SERIES_HISTORY_BUDGET (ADR-082 inventory (a)2 — the mirror
  constant can no longer drift from the tier default)

Resolution tests pin the full chain for both keys: user-DB beats env,
project-DB applies without user override, code defaults = Core
constants, env values survive unrelated DB merges (RULE-18b
storage -> resolver evidence; runtime consumers follow in Task 3).

Refs: ADR-082, docs/superpowers/specs/2026-08-14-post-export-followups-design.md §3.1 (D1)
```

---

### Task 3a: Writing pipeline/service/helpers seam — thread the resolved values

**Files:**
- Modify: `apps/api/narrare/writing/deps_pipeline.py` (`create_pipeline` + `total_budget` param)
- Modify: `apps/api/narrare/writing/service.py` (`WritingService` + `series_history_budget` ctor param, pass-through)
- Modify: `apps/api/narrare/writing/_helpers.py` (`fetch_series_history` + `token_budget`; `prepare_generation_context` pass-through)
- Test: `tests/unit/api/writing/test_context_budget_wiring.py` (new — the C5 wiring test home), `tests/unit/api/writing/test_writing_service_series_history.py` (add budget pass-through test)

**Interfaces:**
- Consumes: nothing new from Tasks 1–2 at runtime (seam only; resolution follows in 3b).
- Produces (verbatim for 3b/3c/3d):
  - `create_pipeline(draft_processor, tier_overrides=None, total_budget: int | None = None) -> WritingPipeline` — `None` keeps the assembler's Core default.
  - `WritingService(..., series_history_provider=None, series_history_budget: int | None = None)`.
  - `prepare_generation_context(request_model, *, tone_service, relationship_repo, session_memory, series_history_provider=None, series_history_budget: int | None = None)`.
  - `fetch_series_history(provider, novel_id, *, token_budget: int | None = None) -> str` — `None` → provider default (16,000 post-Task 2b).

- [ ] **Step 1: Write the failing seam tests**

1a. Create `tests/unit/api/writing/test_context_budget_wiring.py`:

```python
"""C5 / ADR-082 wiring tests — resolved budgets reach the runtime consumers.

Enforcement evidence for RULE-18b: create_pipeline is the ONLY
WritingContextAssembler construction point, and fetch_series_history is
the ONLY series-history assembly call site — pinning both proves the
resolved cascade values reach the runtime consumers.

Factory-level wiring (deps_* resolving against the model window) is
added in Tasks 3b/3c in this same file.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

from narrare.writing._helpers import fetch_series_history
from narrare_core.writing.draft_processor import DraftProcessor


class TestCreatePipelineForwardsTotalBudget:
    def test_forwards_total_budget_to_assembler(self) -> None:
        from narrare.writing.deps_pipeline import create_pipeline

        pipeline = create_pipeline(DraftProcessor(), total_budget=24_000)

        assert pipeline._context_assembler.total_budget == 24_000

    def test_without_total_budget_keeps_core_default(self) -> None:
        from narrare_core.context.budget import DEFAULT_TOTAL_BUDGET
        from narrare.writing.deps_pipeline import create_pipeline

        pipeline = create_pipeline(DraftProcessor())

        assert pipeline._context_assembler.total_budget == DEFAULT_TOTAL_BUDGET


class TestFetchSeriesHistoryBudget:
    async def test_passes_token_budget_through_to_provider(self) -> None:
        provider = AsyncMock()
        provider.assemble_series_history.return_value = "block"
        novel_id = uuid.uuid4()

        result = await fetch_series_history(provider, novel_id, token_budget=12_000)

        assert result == "block"
        provider.assemble_series_history.assert_awaited_once_with(
            novel_id, token_budget=12_000
        )

    async def test_none_budget_calls_provider_without_token_budget(self) -> None:
        """Backward-compatible default: no budget → provider default (16,000)."""
        provider = AsyncMock()
        provider.assemble_series_history.return_value = "block"
        novel_id = uuid.uuid4()

        await fetch_series_history(provider, novel_id)

        provider.assemble_series_history.assert_awaited_once_with(novel_id)

    async def test_none_provider_returns_empty(self) -> None:
        assert await fetch_series_history(None, uuid.uuid4(), token_budget=12_000) == ""
```

1b. In `tests/unit/api/writing/test_writing_service_series_history.py`, append a test class (reuses the file's existing `mock_repo` / `config` fixtures and helpers):

```python
class TestStreamGenerationSeriesHistoryBudget:
    async def test_forwards_series_history_budget_to_provider(
        self,
        mock_repo: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        """C5/ADR-082: the resolved series-history ceiling reaches the
        provider call (RULE-18b runtime-consumer evidence)."""
        user_id = uuid.uuid4()
        request_model = _make_request_model(user_id)
        mock_repo.get_by_id.return_value = request_model

        pipeline = _make_streaming_pipeline()
        provider = AsyncMock()
        provider.assemble_series_history.return_value = "Previously…"

        service = WritingService(
            repo=mock_repo,
            pipeline=pipeline,
            draft_processor=_make_draft_processor(),
            config=config,
            series_history_provider=provider,
            series_history_budget=12_000,
        )

        _ = [chunk async for chunk in service.stream_generation(request_model.id, str(user_id))]

        provider.assemble_series_history.assert_awaited_once_with(
            request_model.novel_id, token_budget=12_000
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test-file tests/unit/api/writing/test_context_budget_wiring.py tests/unit/api/writing/test_writing_service_series_history.py`
Expected: FAIL — `create_pipeline() got an unexpected keyword argument 'total_budget'` (TypeError) and `fetch_series_history() got an unexpected keyword argument 'token_budget'`; the service test fails on the unexpected ctor kwarg `series_history_budget`.

- [ ] **Step 3: Extend `create_pipeline`**

In `apps/api/narrare/writing/deps_pipeline.py`, replace the whole `create_pipeline` function (signature through `return WritingPipeline(...)`) with:

```python
def create_pipeline(
    draft_processor: DraftProcessor,
    tier_overrides: dict[str, float] | None = None,
    total_budget: int | None = None,
) -> WritingPipeline:
    """Create a WritingPipeline with the invocation pipeline wired.

    Shared helper used by all writing service factories to avoid
    duplicating the WritingPipeline construction (RULE-04 compliance).

    Args:
        draft_processor: Shared DraftProcessor instance (also passed to
            the service for direct use).
        tier_overrides: Optional per-tier percentage overrides forwarded
            verbatim to :class:`WritingContextAssembler` (and on to
            :class:`TokenBudgetManager`).  ``None`` (default) preserves the
            mode-specific allocations (extend / rewrite / first-chapter).
            Production factories source this from the resolved
            ``TokenLimitsService.get_resolved_limits().tier_percentages``
            (FIND-012 / CR-AUFG-08-02).
        total_budget: Resolved input-context total (ADR-082 — the tier
            base after model-boundary capping and the series-history
            carve-out).  ``None`` (default) keeps the assembler's Core
            default (32,000); production factories pass the resolver's
            ``writing_tier_base``.

    Returns:
        Configured WritingPipeline with InvocationPipeline attached.
    """
    from narrare.writing.voice_profile_adapter import make_voice_profile_consumer
    from narrare_core.writing.context_assembler import WritingContextAssembler
    from narrare_core.writing.pipeline import WritingPipeline

    if total_budget is None:
        context_assembler = WritingContextAssembler(tier_overrides=tier_overrides)
    else:
        context_assembler = WritingContextAssembler(
            tier_overrides=tier_overrides,
            total_budget=total_budget,
        )

    return WritingPipeline(
        registry=get_model_registry(),
        composer=get_composer(),
        context_assembler=context_assembler,
        draft_processor=draft_processor,
        agent_registry=get_agent_registry(),
        invocation_pipeline=get_invocation_pipeline(),
        voice_profile_consumer_factory=make_voice_profile_consumer,
    )
```

- [ ] **Step 4: Extend `WritingService` and the helper pass-through**

4a. In `apps/api/narrare/writing/service.py`:
- In `__init__`, append the parameter after `series_history_provider: SeriesHistoryProvider | None = None,`:

```python
        series_history_budget: int | None = None,
```

- Append the assignment after `self._series_history_provider = series_history_provider`:

```python
        self._series_history_budget = series_history_budget
```

- In `stream_generation`, extend the `prepare_generation_context(...)` call — after the line `series_history_provider=self._series_history_provider,` add:

```python
            series_history_budget=self._series_history_budget,
```

4b. In `apps/api/narrare/writing/_helpers.py`:

- In `prepare_generation_context`, append the keyword parameter after `series_history_provider: SeriesHistoryProvider | None = None,`:

```python
    series_history_budget: int | None = None,
```

- Extend its docstring `Args:` section — after the `series_history_provider:` description block, add:

```python
        series_history_budget: Resolved series-history token ceiling
            (ADR-082; ``None`` → provider default).
```

- Replace the call at the end of the function body:

```python
    series_history = await fetch_series_history(
        series_history_provider,
        request_model.novel_id,
    )
```

with:

```python
    series_history = await fetch_series_history(
        series_history_provider,
        request_model.novel_id,
        token_budget=series_history_budget,
    )
```

- Replace the whole `fetch_series_history` function with:

```python
async def fetch_series_history(
    provider: SeriesHistoryProvider | None,
    novel_id: UUID,
    *,
    token_budget: int | None = None,
) -> str:
    """Fetch the series-history block (Spec 2 / SERIES-002, ADR-082).

    Args:
        provider: Optional SeriesHistoryProvider (no-op if None).
        novel_id: The novel being generated for.
        token_budget: Resolved series-history ceiling from the
            ContextBudgetResolver (ADR-082 — the API always passes the
            resolved value; the parameter stays explicit per the ADR
            inventory).  ``None`` → provider default (16,000).

    Returns:
        The ``Previously in this series:`` block, or empty string when the
        provider is absent or the novel is standalone (RULE-11 graceful).
    """
    if provider is None:
        return ""
    if token_budget is None:
        return await provider.assemble_series_history(novel_id)
    return await provider.assemble_series_history(novel_id, token_budget=token_budget)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `just test-file tests/unit/api/writing/test_context_budget_wiring.py tests/unit/api/writing/test_writing_service_series_history.py tests/unit/api/writing/test_deps_tier_overrides.py`
Expected: PASS — new seam tests green; existing series-history service tests green (the no-budget path is backward-compatible — `assert_awaited_once_with(request_model.novel_id)` still holds); FIND-012 tier tests green (`create_pipeline` default behavior unchanged).

- [ ] **Step 6: Commit (via Platform, verbatim)**

```bash
git add apps/api/narrare/writing/deps_pipeline.py \
        apps/api/narrare/writing/service.py \
        apps/api/narrare/writing/_helpers.py \
        tests/unit/api/writing/test_context_budget_wiring.py \
        tests/unit/api/writing/test_writing_service_series_history.py
```

Commit message:

```
feat(api): thread resolved context budgets through writing pipeline seam

ADR-082 wiring step 1 of 3 — the seam every factory will use:
- create_pipeline gains total_budget (None keeps the Core default;
  factories pass the resolver's writing_tier_base). Backward-compatible:
  existing FIND-012 tier-override wiring and tests unchanged.
- WritingService gains series_history_budget; stream_generation
  forwards it through prepare_generation_context.
- fetch_series_history gains an explicit token_budget parameter (the
  ADR inventory keeps the provider parameter explicit — the API always
  passes the resolved value; None falls back to the re-defaulted
  provider constant).

RULE-18b runtime-consumer evidence: seam tests pin
create_pipeline -> WritingContextAssembler.total_budget and
WritingService -> provider.assemble_series_history(token_budget=...)
forwards. Factory resolution against the model window follows next.

Refs: ADR-082, docs/superpowers/specs/2026-08-14-post-export-followups-design.md §3.2 (scope 1)
```

---

### Task 3b: Resolution adapter + writing/extend factories

**Files:**
- Create: `apps/api/narrare/settings/token_limits/context_budgets.py` (`resolve_context_budgets` adapter)
- Modify: `apps/api/narrare/writing/deps_writing.py` (resolve budgets, series-scope lookup, wire `total_budget` + `series_history_budget`)
- Modify: `apps/api/narrare/writing/deps_extend.py` (resolve budgets, wire `total_budget`)
- Test: `tests/unit/api/writing/test_context_budget_wiring.py` (extend — adapter unit tests + factory wiring tests), `tests/unit/api/writing/test_deps_tier_overrides.py` (keep existing factory tests hermetic)

**Interfaces:**
- Consumes: `DefaultContextBudgetResolver`, `EffectiveContextBudgets`, `ContextBudgetResolver` (Task 1a); `TokenLimitOverrides.context_total_budget` / `.series_history_budget` / `.effective_output_limit` (Tasks 2a/2b); `create_pipeline(total_budget=...)`, `WritingService(series_history_budget=...)` (Task 3a).
- Produces (verbatim for 3c/3d): `resolve_context_budgets(*, limits: TokenLimitOverrides, config: ResolvedModelConfig, series_in_scope: bool, resolver: ContextBudgetResolver | None = None) -> EffectiveContextBudgets`.

- [ ] **Step 1: Write the failing adapter + factory wiring tests**

1a. In `tests/unit/api/writing/test_context_budget_wiring.py`, extend the module docstring's last paragraph (replace `Factory-level wiring (deps_* resolving against the model window) is added in Tasks 3b/3c in this same file.` with `Factory-level wiring (deps_* resolving against the model window) lives in the classes below.`) and append:

```python
class TestResolveContextBudgetsAdapter:
    """The API-side adapter delegates to the injected resolver with the
    cascade's configured values and the routed model identity."""

    def test_delegates_with_cascade_values(self) -> None:
        from unittest.mock import MagicMock

        from narrare.settings.token_limits.context_budgets import resolve_context_budgets
        from narrare.settings.token_limits.contracts import TokenLimitOverrides
        from narrare_core.llm import ResolvedModelConfig

        canned = EffectiveContextBudgets(
            context_total=24_000,
            series_history=12_000,
            writing_tier_base=12_000,
            reserve_tokens=8_096,
            context_window=128_000,
            source="cascade:uncapped",
        )
        spy = MagicMock(name="resolver", return_value=canned)
        limits = TokenLimitOverrides(context_total_budget=24_000, series_history_budget=12_000)
        config = ResolvedModelConfig(provider_name="ollama", model_id="llama3")

        result = resolve_context_budgets(
            limits=limits, config=config, series_in_scope=True, resolver=spy
        )

        assert result is canned
        spy.resolve.assert_called_once_with(
            configured_total=24_000,
            configured_series_history=12_000,
            # TokenLimitOverrides default profile (balanced) resolves 2,000.
            effective_output_limit=limits.effective_output_limit,
            series_in_scope=True,
            provider_name="ollama",
            model_id="llama3",
        )


def _canned_budgets(tier_base: int, series_history: int) -> EffectiveContextBudgets:
    return EffectiveContextBudgets(
        context_total=tier_base + series_history,
        series_history=series_history,
        writing_tier_base=tier_base,
        reserve_tokens=4_096,
        context_window=128_000,
        source="cascade:uncapped",
    )


def _budget_patch_context(module_path: str, budgets: EffectiveContextBudgets):
    """Run a writing factory hermetically: routing resolver, token
    limits, the context-budget adapter, and create_pipeline are patched.
    Returns (ctx-managers, create_pipeline spy, adapter spy)."""
    from types import SimpleNamespace
    from unittest.mock import patch

    from narrare._app.config import Settings
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare.settings.token_limits.contracts import TokenLimitOverrides
    from narrare.settings.token_limits.service import TokenLimitsService
    from narrare.writing.deps_pipeline import create_pipeline

    fake_limits = TokenLimitOverrides()
    fake_token_service = MagicMock(spec=TokenLimitsService, name="token_limits_service")
    fake_token_service.get_resolved_limits = AsyncMock(return_value=fake_limits)

    fake_resolved = SimpleNamespace(
        config=_fake_resolved_config(),
        api_key=None,
        base_url=None,
    )
    fake_routing = MagicMock(spec=ModelRoutingResolverImpl)
    fake_routing.resolve = AsyncMock(return_value=fake_resolved)

    adapter_spy = MagicMock(name="resolve_context_budgets", return_value=budgets)
    pipeline_spy = MagicMock(spec=create_pipeline, name="create_pipeline_spy")

    ctx = (
        patch(f"{module_path}.get_model_routing_resolver", return_value=fake_routing),
        patch(
            "narrare.settings.token_limits.service.TokenLimitsService",
            return_value=fake_token_service,
        ),
        patch(
            "narrare.settings.token_limits.context_budgets.resolve_context_budgets",
            adapter_spy,
        ),
        patch("narrare.writing.deps_pipeline.create_pipeline", pipeline_spy),
        patch(
            "narrare._app.config.get_settings",
            return_value=MagicMock(spec=Settings, name="settings"),
        ),
    )
    return ctx, pipeline_spy, adapter_spy


class TestDepsWritingFactoryWiring:
    async def test_passes_resolved_tier_base_and_series_budget(self) -> None:
        import importlib

        budgets = _canned_budgets(tier_base=16_000, series_history=16_000)
        ctx, pipeline_spy, adapter_spy = _budget_patch_context(
            "narrare.writing.deps_writing", budgets
        )
        module = importlib.import_module("narrare.writing.deps_writing")

        with ctx[0], ctx[1], ctx[2], ctx[3], ctx[4]:
            # project_id=None -> series_in_scope=False path (no novel lookup).
            service = await module.get_writing_service(
                session=_fake_session(),
                user_id=str(uuid.uuid4()),
                project_id=None,
            )

        assert pipeline_spy.call_args.kwargs["total_budget"] == 16_000
        assert service._series_history_budget == 16_000
        assert adapter_spy.call_args.kwargs["series_in_scope"] is False

    async def test_series_novel_marks_series_in_scope(self) -> None:
        """A novel with series membership resolves with the carve-out."""
        import importlib
        from types import SimpleNamespace
        from unittest.mock import patch as _patch

        budgets = _canned_budgets(tier_base=16_000, series_history=16_000)
        ctx, pipeline_spy, adapter_spy = _budget_patch_context(
            "narrare.writing.deps_writing", budgets
        )
        module = importlib.import_module("narrare.writing.deps_writing")

        series_novel = SimpleNamespace(series_id=uuid.uuid4())
        with (
            ctx[0],
            ctx[1],
            ctx[2],
            ctx[3],
            ctx[4],
            _patch("narrare.novels.repository.NovelRepository") as novel_repo_cls,
        ):
            novel_repo_cls.return_value.get = AsyncMock(return_value=series_novel)
            await module.get_writing_service(
                session=_fake_session(),
                user_id=str(uuid.uuid4()),
                project_id=uuid.uuid4(),
            )

        assert adapter_spy.call_args.kwargs["series_in_scope"] is True


class TestDepsExtendFactoryWiring:
    async def test_passes_resolved_tier_base_full_total(self) -> None:
        import importlib

        budgets = _canned_budgets(tier_base=32_000, series_history=0)
        ctx, pipeline_spy, adapter_spy = _budget_patch_context(
            "narrare.writing.deps_extend", budgets
        )
        module = importlib.import_module("narrare.writing.deps_extend")

        with ctx[0], ctx[1], ctx[2], ctx[3], ctx[4]:
            await module.get_extend_service(
                session=_fake_session(),
                user_id=str(uuid.uuid4()),
                project_id=uuid.uuid4(),
            )

        # Extend never injects series history -> full total as tier base.
        assert adapter_spy.call_args.kwargs["series_in_scope"] is False
        assert pipeline_spy.call_args.kwargs["total_budget"] == 32_000
```

Also extend the import block at the top of the file to (isort order: stdlib → third-party → first-party; this replaces the initial `import uuid` / `from unittest.mock import AsyncMock` block):

```python
import uuid
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from narrare.writing._helpers import fetch_series_history
from narrare_core.context.contracts import EffectiveContextBudgets
from narrare_core.llm import ResolvedModelConfig
from narrare_core.writing.draft_processor import DraftProcessor
```

and add the two shared helpers (mirroring `test_deps_tier_overrides.py`):

```python
def _fake_resolved_config() -> ResolvedModelConfig:
    """A valid ResolvedModelConfig for ``dataclasses.replace`` in factories."""
    return ResolvedModelConfig(
        provider_name="anthropic",
        model_id="claude-sonnet-4-5-20251020",
        temperature=0.7,
        max_tokens=4096,
    )


def _fake_session() -> MagicMock:
    """A spec'd AsyncSession mock for factory repository construction."""
    return MagicMock(spec=AsyncSession, name="session")
```

1b. In `tests/unit/api/writing/test_deps_tier_overrides.py`, keep the existing FIND-012 tests hermetic now that factories call the adapter: in `_factory_patch_context`, extend the `ctx` tuple (before the closing `)` of the tuple) with one more patch, and thread it through:

Replace:

```python
    ctx = (
        patch(f"{module_path}.get_model_routing_resolver", return_value=fake_resolver),
        patch(
            "narrare.settings.token_limits.service.TokenLimitsService",
            return_value=fake_token_service,
        ),
        patch("narrare.writing.deps_pipeline.create_pipeline", pipeline_spy),
        patch(
            "narrare._app.config.get_settings",
            return_value=MagicMock(spec=Settings, name="settings"),
        ),
    )
    return ctx, pipeline_spy
```

with:

```python
    from narrare_core.context.contracts import EffectiveContextBudgets

    canned_budgets = EffectiveContextBudgets(
        context_total=32_000,
        series_history=0,
        writing_tier_base=32_000,
        reserve_tokens=8_096,
        context_window=128_000,
        source="cascade:uncapped",
    )
    budget_adapter = MagicMock(name="resolve_context_budgets_stub", return_value=canned_budgets)

    ctx = (
        patch(f"{module_path}.get_model_routing_resolver", return_value=fake_resolver),
        patch(
            "narrare.settings.token_limits.service.TokenLimitsService",
            return_value=fake_token_service,
        ),
        patch(
            "narrare.settings.token_limits.context_budgets.resolve_context_budgets",
            budget_adapter,
        ),
        patch("narrare.writing.deps_pipeline.create_pipeline", pipeline_spy),
        patch(
            "narrare._app.config.get_settings",
            return_value=MagicMock(spec=Settings, name="settings"),
        ),
    )
    return ctx, pipeline_spy
```

And in the three test methods of `TestFactoriesWireTierOverrides`, update the context-manager line `with ctx[0], ctx[1], ctx[2], ctx[3]:` to `with ctx[0], ctx[1], ctx[2], ctx[3], ctx[4]:`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test-file tests/unit/api/writing/test_context_budget_wiring.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'narrare.settings.token_limits.context_budgets'` (adapter missing) and factory kwargs `total_budget` not passed (`KeyError: 'total_budget'` on the spy).

- [ ] **Step 3: Create the adapter**

Create `apps/api/narrare/settings/token_limits/context_budgets.py`:

```python
"""Cascade → effective context budgets adapter (ADR-082 Decision 3).

Single API-side seam turning resolved ``TokenLimitOverrides`` plus the
routed model config into model-boundary-capped
:class:`~narrare_core.context.contracts.EffectiveContextBudgets`.

Pure delegation — all arithmetic lives in Core
(``DefaultContextBudgetResolver``); this adapter exists so the six
production wiring points (five writing deps factories + the beta-reader
factory) share one resolution call instead of each constructing the
resolver (RULE-04). Window source: ``get_model_limits`` (models.dev,
24 h local cache, typed offline statuses — ADR-082 finding F1).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.context.budget_resolver import DefaultContextBudgetResolver
from narrare_core.context.contracts import ContextBudgetResolver, EffectiveContextBudgets

if TYPE_CHECKING:
    from narrare.settings.token_limits.contracts import TokenLimitOverrides
    from narrare_core.llm.model_config import ResolvedModelConfig

__all__ = ["resolve_context_budgets"]


def resolve_context_budgets(
    *,
    limits: TokenLimitOverrides,
    config: ResolvedModelConfig,
    series_in_scope: bool,
    resolver: ContextBudgetResolver | None = None,
) -> EffectiveContextBudgets:
    """Resolve configured context budgets against the model boundary.

    Args:
        limits: Fully resolved cascade values (TokenLimitsService).
        config: Routed model config — provider/model identify the window.
        series_in_scope: Whether this request assembles the series-history
            block (series novel on the writing path; always ``False`` for
            analysis and for paths that never inject ``{{series_history}}``
            — ADR-082 Decision 6 asymmetry).
        resolver: Optional resolver override (tests inject a fake; the
            default constructs ``DefaultContextBudgetResolver`` with the
            real models.dev-backed window provider).

    Returns:
        Frozen effective budgets (capped totals, series-history ceiling,
        tier base, applied reserve, provenance source tag).
    """
    effective_resolver = resolver or DefaultContextBudgetResolver()
    return effective_resolver.resolve(
        configured_total=limits.context_total_budget,
        configured_series_history=limits.series_history_budget,
        effective_output_limit=limits.effective_output_limit,
        series_in_scope=series_in_scope,
        provider_name=config.provider_name,
        model_id=config.model_id,
    )
```

- [ ] **Step 4: Wire `deps_writing.py`**

In `apps/api/narrare/writing/deps_writing.py`:

4a. In the lazy import block inside `get_writing_service`, replace:

```python
    from narrare.writing.deps_pipeline import create_pipeline
```

with:

```python
    from narrare.settings.token_limits.context_budgets import resolve_context_budgets
    from narrare.writing.deps_pipeline import create_pipeline
```

4b. After the `limits = await token_limits_service.get_resolved_limits(...)` block and **before** the `config = replace(` line, insert:

```python
    # ADR-082: resolve input-context budgets against the writing model's
    # window. Series membership decides the guarded carve-out (Decision 6):
    # series novels allocate tiers over total - series_history; standalones
    # over the full total.
    from narrare.novels.repository import NovelRepository

    series_in_scope = False
    if project_id is not None:
        novel = await NovelRepository(session).get(project_id)
        series_in_scope = novel is not None and novel.series_id is not None

    budgets = resolve_context_budgets(
        limits=limits,
        config=resolved.config,
        series_in_scope=series_in_scope,
    )
```

4c. Replace the pipeline line:

```python
    pipeline = create_pipeline(draft_processor, tier_overrides=limits.tier_percentages)
```

with:

```python
    pipeline = create_pipeline(
        draft_processor,
        tier_overrides=limits.tier_percentages,
        total_budget=budgets.writing_tier_base,
    )
```

4d. In the series-history provider block, delete the now-duplicate import line `from narrare.novels.repository import NovelRepository` (it was hoisted in 4b; the block keeps its `from narrare.series.band_summary_repository import BandSummaryRepository` / `from narrare.series.repository import SeriesRepository` / `from narrare.series.series_history_provider import SeriesHistoryProvider` lines unchanged).

4e. In the `return WritingService(` block, add after `series_history_provider=series_history_provider,`:

```python
        series_history_budget=budgets.series_history,
```

- [ ] **Step 5: Wire `deps_extend.py`**

In `apps/api/narrare/writing/deps_extend.py`:

5a. Replace the lazy import line:

```python
    from narrare.writing.deps_pipeline import create_pipeline
```

with:

```python
    from narrare.settings.token_limits.context_budgets import resolve_context_budgets
    from narrare.writing.deps_pipeline import create_pipeline
```

5b. Replace the pipeline construction block:

```python
    draft_processor = DraftProcessor()
    pipeline = create_pipeline(draft_processor, tier_overrides=limits.tier_percentages)
```

with:

```python
    # ADR-082: extend never injects {{series_history}} -> tiers allocate
    # over the full effective total (Decision 6 standalone semantics).
    budgets = resolve_context_budgets(
        limits=limits,
        config=resolved.config,
        series_in_scope=False,
    )
    draft_processor = DraftProcessor()
    pipeline = create_pipeline(
        draft_processor,
        tier_overrides=limits.tier_percentages,
        total_budget=budgets.writing_tier_base,
    )
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `just test-file tests/unit/api/writing/`
Expected: PASS — new adapter/factory tests green; FIND-012 tier tests green (hermetic via the added patch); all existing writing router/service tests green.

- [ ] **Step 7: Commit (via Platform, verbatim)**

```bash
git add apps/api/narrare/settings/token_limits/context_budgets.py \
        apps/api/narrare/writing/deps_writing.py \
        apps/api/narrare/writing/deps_extend.py \
        tests/unit/api/writing/test_context_budget_wiring.py \
        tests/unit/api/writing/test_deps_tier_overrides.py
```

Commit message:

```
feat(api): resolve model-capped budgets in writing deps factories

ADR-082 wiring step 2 of 3 — runtime consumers resolve against the
model boundary:
- new settings/token_limits/context_budgets.py: resolve_context_budgets
  adapter — the single API-side seam over Core's
  DefaultContextBudgetResolver (six wiring points share one call,
  RULE-04; window source get_model_limits, models.dev-backed)
- deps_writing: novel series-membership lookup decides the guarded
  carve-out (series -> tier base = total - series_history; standalone
  -> full total); create_pipeline receives writing_tier_base;
  WritingService receives the resolved series-history ceiling
- deps_extend: resolves with series_in_scope=False (extend never
  injects {{series_history}} -> full total as tier base)

RULE-18b evidence: factory wiring tests pin cascade values -> adapter
(configured_total / configured_series_history / effective_output_limit
/ provider/model identity) -> create_pipeline(total_budget) ->
WritingService(series_history_budget). Existing FIND-012 tests stay
hermetic (adapter patched in their fixture).

Refs: ADR-082, docs/superpowers/specs/2026-08-14-post-export-followups-design.md §3.1 (D3/D4)
```

---

### Task 3c: Remaining writing factories — rewrite, coauthor, style variants

**Files:**
- Modify: `apps/api/narrare/writing/deps_rewrite.py`
- Modify: `apps/api/narrare/writing/deps_coauthor.py`
- Modify: `apps/api/narrare/writing/deps_style_variants.py`
- Test: `tests/unit/api/writing/test_context_budget_wiring.py` (extend — parametrized wiring tests), `tests/unit/api/writing/test_deps_factories.py` (keep the style-variants factory test hermetic)

**Interfaces:**
- Consumes: `resolve_context_budgets` (Task 3b), `create_pipeline(total_budget=...)` (Task 3a).
- Produces: nothing new — completes the writing-side adoption (all five pipeline factories resolve).

**Note:** these three paths never inject `{{series_history}}` (only `WritingService.stream_generation` assembles the block — verified single call site of `prepare_generation_context`), so all three resolve with `series_in_scope=False` (tier base = full effective total). See Global Constraints interpretation note.

- [ ] **Step 1: Write the failing parametrized wiring tests**

In `tests/unit/api/writing/test_context_budget_wiring.py`, append:

```python
class TestRemainingWritingFactoriesWiring:
    """rewrite / coauthor / style-variants resolve like extend:
    series_in_scope=False (they never inject series history)."""

    async def test_deps_rewrite_passes_resolved_tier_base(self) -> None:
        import importlib

        budgets = _canned_budgets(tier_base=32_000, series_history=0)
        ctx, pipeline_spy, adapter_spy = _budget_patch_context(
            "narrare.writing.deps_rewrite", budgets
        )
        module = importlib.import_module("narrare.writing.deps_rewrite")

        with ctx[0], ctx[1], ctx[2], ctx[3], ctx[4]:
            await module.get_rewrite_service(
                session=_fake_session(),
                user_id=str(uuid.uuid4()),
                project_id=uuid.uuid4(),
            )

        assert adapter_spy.call_args.kwargs["series_in_scope"] is False
        assert pipeline_spy.call_args.kwargs["total_budget"] == 32_000

    async def test_deps_coauthor_passes_resolved_tier_base(self) -> None:
        import importlib

        budgets = _canned_budgets(tier_base=24_000, series_history=0)
        ctx, pipeline_spy, _adapter = _budget_patch_context(
            "narrare.writing.deps_coauthor", budgets
        )
        module = importlib.import_module("narrare.writing.deps_coauthor")

        with ctx[0], ctx[1], ctx[2], ctx[3], ctx[4]:
            await module.get_coauthor_service(
                session=_fake_session(),
                user_id=str(uuid.uuid4()),
                project_id=uuid.uuid4(),
            )

        assert pipeline_spy.call_args.kwargs["total_budget"] == 24_000

    async def test_deps_style_variants_passes_resolved_tier_base(self) -> None:
        import importlib

        budgets = _canned_budgets(tier_base=28_000, series_history=0)
        ctx, pipeline_spy, _adapter = _budget_patch_context(
            "narrare.writing.deps_style_variants", budgets
        )
        module = importlib.import_module("narrare.writing.deps_style_variants")

        with ctx[0], ctx[1], ctx[2], ctx[3], ctx[4]:
            await module.get_style_variant_service(
                session=_fake_session(),
                user_id=str(uuid.uuid4()),
                project_id=uuid.uuid4(),
            )

        assert pipeline_spy.call_args.kwargs["total_budget"] == 28_000
```

(Verify the exact factory names before running: `get_rewrite_service` / `get_coauthor_service` / `get_style_variant_service` — locate via `rg -n "^async def get_" apps/api/narrare/writing/deps_rewrite.py apps/api/narrare/writing/deps_coauthor.py apps/api/narrare/writing/deps_style_variants.py` and adjust the test method names/calls if the real names differ.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test-file tests/unit/api/writing/test_context_budget_wiring.py`
Expected: FAIL — `KeyError: 'total_budget'` for all three factories (they still call `create_pipeline` without the kwarg; the adapter patch is also not yet consumed — `adapter_spy.call_args` may be `None`).

- [ ] **Step 3: Wire the three factories**

Apply the identical edit pattern from Task 3b Step 5 to each of the three files (`deps_rewrite.py`, `deps_coauthor.py`, `deps_style_variants.py`):

3a. Replace the lazy import line:

```python
    from narrare.writing.deps_pipeline import create_pipeline
```

with:

```python
    from narrare.settings.token_limits.context_budgets import resolve_context_budgets
    from narrare.writing.deps_pipeline import create_pipeline
```

3b. Replace the pipeline construction block:

```python
    draft_processor = DraftProcessor()
    pipeline = create_pipeline(draft_processor, tier_overrides=limits.tier_percentages)
```

with:

```python
    # ADR-082: this path never injects {{series_history}} -> tiers
    # allocate over the full effective total (Decision 6 standalone
    # semantics for rewrite/coauthor/style-variants).
    budgets = resolve_context_budgets(
        limits=limits,
        config=resolved.config,
        series_in_scope=False,
    )
    draft_processor = DraftProcessor()
    pipeline = create_pipeline(
        draft_processor,
        tier_overrides=limits.tier_percentages,
        total_budget=budgets.writing_tier_base,
    )
```

(In `deps_style_variants.py` the `create_pipeline` call site may read slightly differently around whitespace — locate by the semantic text `pipeline = create_pipeline(draft_processor, tier_overrides=limits.tier_percentages)`.)

- [ ] **Step 4: Keep `test_deps_factories.py` hermetic**

In `tests/unit/api/writing/test_deps_factories.py`, in `test_execution_returns_style_variant_service` (the style-variants execution test that patches `narrare.writing.deps_pipeline.create_pipeline`), extend the `with (...)` block with one more patch — add:

```python
            patch(
                "narrare.settings.token_limits.context_budgets.resolve_context_budgets",
                return_value=EffectiveContextBudgets(
                    context_total=32_000,
                    series_history=0,
                    writing_tier_base=32_000,
                    reserve_tokens=8_096,
                    context_window=128_000,
                    source="cascade:uncapped",
                ),
            ),
```

and extend the file imports with:

```python
from narrare_core.context.contracts import EffectiveContextBudgets
```

- [ ] **Step 5: Run the writing suite to verify everything passes**

Run: `just test-file tests/unit/api/writing/`
Expected: PASS — all wiring tests, FIND-012 tests, factory tests, router tests.

- [ ] **Step 6: Commit (via Platform, verbatim)**

```bash
git add apps/api/narrare/writing/deps_rewrite.py \
        apps/api/narrare/writing/deps_coauthor.py \
        apps/api/narrare/writing/deps_style_variants.py \
        tests/unit/api/writing/test_context_budget_wiring.py \
        tests/unit/api/writing/test_deps_factories.py
```

Commit message:

```
feat(api): adopt resolved context budgets in remaining writing factories

ADR-082 wiring step 3 of 3 (writing side): deps_rewrite, deps_coauthor
and deps_style_variants now resolve their input-context total through
resolve_context_budgets and pass writing_tier_base to create_pipeline —
no writing path silently relies on the class-default total anymore
(CR-08 P0: every tier budget enters through the cascade and adopts the
model boundary).

All three paths never inject {{series_history}} (single call site is
WritingService.stream_generation), so they resolve with
series_in_scope=False -> tiers allocate over the full effective total
(ADR-082 Decision 6 standalone semantics; documented in-code).

Wiring pinned per factory (total_budget forward) in
test_context_budget_wiring.py; style-variants execution test kept
hermetic via the adapter patch.

Refs: ADR-082, docs/superpowers/specs/2026-08-14-post-export-followups-design.md §3.1 (D3)
```

---

### Task 3d: Beta-reader wiring + rewritten-default sweep + docs (slice-final gate)

**Files:**
- Modify: `apps/api/narrare/analysis/dependencies_beta_reader.py` (async factory resolving the analysis budget)
- Modify (docs): `docs/architecture/decisions/ADR-082-token-budget-governance.md` (one-line Decision 3 window-source clarification), `docs/features/settings/SET-005-configurable-token-limits.md`, `docs/_shared/CURRENT_STATE.md`
- Test: `tests/unit/api/analysis/test_analysis_dependencies.py` (rewrite the beta-reader factory test for the async signature + budget assertion)

**Interfaces:**
- Consumes: `resolve_context_budgets` (Task 3b); `TokenLimitsService.get_resolved_limits` (Task 2b); `AnalysisContextAssembler(total_budget=...)`.
- Produces: `get_beta_reader_service(session, user_id, novel_id) -> BetaReaderService` (async; FastAPI resolves `novel_id` from the endpoints' declared `novel_id` parameter (query) and `user_id` via `CurrentUserIdDep` — both beta-reader endpoints declare them). `BetaReaderService` itself is **unchanged** (it already accepts `budget_assembler`).

- [ ] **Step 1: Rewrite the beta-reader factory test (failing first)**

In `tests/unit/api/analysis/test_analysis_dependencies.py`, replace the whole `TestGetBetaReaderService` class with:

```python
class TestGetBetaReaderService:
    """get_beta_reader_service(session, user_id, novel_id) — async factory.

    C5/ADR-082: resolves context_total_budget through the cascade and the
    model boundary, and injects it as the budget assembler's total
    (RULE-18b runtime-consumer evidence for the analysis side).
    """

    async def test_returns_beta_reader_service_with_resolved_budget(self) -> None:
        """All deps wired; budget_assembler.total_budget = resolved total."""
        import uuid as _uuid

        from narrare._app.config import Settings
        from narrare.settings.token_limits.contracts import TokenLimitOverrides
        from narrare.settings.token_limits.service import TokenLimitsService
        from narrare_core.context.contracts import EffectiveContextBudgets

        session = AsyncMock(spec=AsyncSession)
        mock_registry = MagicMock(spec=["get_model", "register_model"])
        mock_composer = MagicMock(spec=["compose", "build"])
        mock_config = MagicMock(spec=["model_id", "provider_name", "temperature", "max_tokens"])
        mock_pipeline = MagicMock(spec=["generate"])

        fake_limits = TokenLimitOverrides(context_total_budget=24_000)
        fake_token_service = MagicMock(spec=TokenLimitsService)
        fake_token_service.get_resolved_limits = AsyncMock(return_value=fake_limits)

        canned = EffectiveContextBudgets(
            context_total=24_000,
            series_history=0,
            writing_tier_base=24_000,
            reserve_tokens=4_096,
            context_window=128_000,
            source="cascade:uncapped",
        )

        with (
            patch("narrare._app.dependencies.get_model_registry", return_value=mock_registry),
            patch("narrare._app.dependencies.get_composer", return_value=mock_composer),
            patch(
                "narrare._app.dependencies_services.build_system_default_config",
                return_value=mock_config,
            ),
            patch("narrare._app.dependencies.get_invocation_pipeline", return_value=mock_pipeline),
            patch("narrare.chapters.repository.ChapterRepository"),
            patch("narrare.kb.repository.KBRepository"),
            patch("narrare.kb.relationship_repository.RelationshipRepository"),
            patch("narrare.novels.repository.NovelRepository"),
            patch("narrare.kb._context_provider.KBContextProvider"),
            patch("narrare.analysis.context_assembler.ContextAssembler"),
            patch("narrare_core.cache.InMemorySessionCache"),
            patch("narrare.analysis.beta_reader_cache.BetaReaderCache"),
            patch(
                "narrare.settings.token_limits.service.TokenLimitsService",
                return_value=fake_token_service,
            ),
            patch(
                "narrare.settings.token_limits.context_budgets.resolve_context_budgets",
                return_value=canned,
            ),
            patch(
                "narrare._app.config.get_settings",
                return_value=MagicMock(spec=Settings, name="settings"),
            ),
        ):
            result = await get_beta_reader_service(
                session, user_id=str(_uuid.uuid4()), novel_id=_uuid.uuid4()
            )

        assert result._budget_assembler.total_budget == 24_000
```

(The remaining `TestGetSentimentService` / `TestGetReadabilityService` / `TestGetPovService` classes in the file are untouched. `get_settings` is patched for hermeticity, matching the tier-override factory-test pattern: the factory calls `get_settings()` for `TokenLimitsService(config=...)`, and the `Settings` instance is only ever passed to the already-mocked service class — no real settings construction runs.)

- [ ] **Step 2: Run the test to verify it fails**

Run: `just test-file tests/unit/api/analysis/test_analysis_dependencies.py`
Expected: FAIL — `get_beta_reader_service() takes 1 positional argument but 3 were given` (sync single-arg signature).

- [ ] **Step 3: Wire the beta-reader factory**

In `apps/api/narrare/analysis/dependencies_beta_reader.py`, replace the whole file content after the module docstring with:

```python
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from narrare._app.dependencies import (  # noqa: TC001 — needed at runtime for FastAPI DI
    CurrentUserIdDep,
    SessionDep,
)

if TYPE_CHECKING:
    from narrare.analysis.beta_reader_service import BetaReaderService


async def get_beta_reader_service(
    session: SessionDep,
    user_id: CurrentUserIdDep,
    novel_id: uuid.UUID,
) -> BetaReaderService:
    """Create a BetaReaderService with injected dependencies.

    Production wiring:
    - ModelRegistry for LLM model resolution
    - PromptComposer for system prompt assembly
    - ChapterRepository + NovelRepository for context
    - Canonical KBContextProvider (ADR-067) for kb_characters / kb_locations,
      rendered through the ADR-050 envelope with provenance (FIND-017).
    - InMemorySessionCache for result caching (30min TTL)
    - InvocationPipeline for invocation evidence (ADR-040)
    - AnalysisContextAssembler at the resolved, model-capped
      context_total_budget (ADR-082 Decision 5 — analysis joins
      context_total_budget, capped by the analysis model's window).

    FastAPI resolves ``novel_id`` from the endpoints' declared
    ``novel_id`` parameter (query) and ``user_id`` via
    ``CurrentUserIdDep`` (both beta-reader endpoints declare them).
    """
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare._app.dependencies_services import (
        SystemModelCategory,
        build_system_default_config,
    )
    from narrare._app.config import get_settings
    from narrare.analysis.beta_reader_cache import BetaReaderCache
    from narrare.analysis.beta_reader_service import BetaReaderService
    from narrare.analysis.context_assembler import ContextAssembler
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb._context_provider import KBContextProvider
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare.settings.token_limits.context_budgets import resolve_context_budgets
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService
    from narrare_core.analysis.assembler import AnalysisContextAssembler
    from narrare_core.cache import InMemorySessionCache

    registry = get_model_registry()
    composer = get_composer()
    config = build_system_default_config(SystemModelCategory.ANALYSIS)
    invocation_pipeline = get_invocation_pipeline()

    # Repositories
    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)

    # Canonical KB-context provider (ADR-067): single fetch+render source for
    # the beta-reader's kb_characters / kb_locations slots, rendered through
    # the ADR-050 envelope with provenance annotated (FIND-017). Degrades
    # gracefully (RULE-11).
    kb_context_provider = KBContextProvider(
        kb_repo=KBRepository(session),
        relationship_repo=RelationshipRepository(session),
    )

    # Context assembler
    assembler = ContextAssembler(
        chapter_repo=chapter_repo,
        kb_context_provider=kb_context_provider,
        novel_repo=novel_repo,
    )

    # ADR-082: resolve the analysis input-context total through the cascade
    # and against the analysis model's window. Analysis has no series-history
    # tier -> series_in_scope=False (full total; Decision 5).
    token_limits_service = TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=get_settings(),
    )
    limits = await token_limits_service.get_resolved_limits(
        user_id=user_id,
        project_id=str(novel_id),
    )
    budgets = resolve_context_budgets(
        limits=limits,
        config=config,
        series_in_scope=False,
    )

    # In-memory cache with 30min TTL (ADR-080)
    cache = InMemorySessionCache()
    beta_cache = BetaReaderCache(cache)

    return BetaReaderService(
        context_assembler=assembler,
        cache=beta_cache,
        registry=registry,
        config=config,
        composer=composer,
        budget_assembler=AnalysisContextAssembler(total_budget=budgets.context_total),
        invocation_pipeline=invocation_pipeline,
    )
```

(The module docstring at the top of the file stays unchanged.)

- [ ] **Step 4: Run the analysis suite to verify it passes**

Run: `just test-file tests/unit/api/analysis/`
Expected: PASS — rewritten factory test green; beta-reader service/agent/cache/router tests green (service constructors unchanged; router uses `Depends(get_beta_reader_service)` — FastAPI supports async dependencies and resolves the additional params from the endpoints' declared `novel_id` parameter (query) + `CurrentUserIdDep`).

- [ ] **Step 5: Full unit sweep — rewritten-default regression gate**

Run: `rg -n "DEFAULT_TOTAL_BUDGET: int = 6000|token_budget: int = 512|_DEFAULT_TOKEN_BUDGET: int = 512" packages/ apps/`
Expected: **no output** (all four lifted constants re-defaulted; ADR inventory items (a)1–4 complete).

Run: `just test-unit`
Expected: PASS. Decision rule for any failure: (a) assertion on a *default* value → rewrite to the new default (or to the imported Core constant — prefer the constant); (b) test invoking a writing/analysis factory hermetically but now hitting the adapter → patch `narrare.settings.token_limits.context_budgets.resolve_context_budgets` in that test (never relax the production seam); (c) anything else → STOP and report (do not work around).

- [ ] **Step 6: Update the SET-005 feature spec + ADR-082 window-source note**

In `docs/features/settings/SET-005-configurable-token-limits.md`, insert a new subsection directly **before** the `### Core Changes` heading:

```markdown
### Context Budget Keys (ADR-082 / C5, 2026-08-15)

Input-context token budgets joined the cascade (previously hardcoded
constants bypassing it — CR-08 P0):

| Key | Default | Bounds | Meaning |
|---|---|---|---|
| `context_total_budget` | 32,000 | ≥ 1,024 | Total input-context ceiling for writing **and** analysis (one knob) |
| `series_history_budget` | 16,000 | ≥ 1,024 | Series-history block ceiling **within** the total (guarded carve-out: effective = `min(configured, 50% × effective_total)`) |

Operator env: `NARRARE_CONTEXT_TOTAL_BUDGET` / `NARRARE_SERIES_HISTORY_BUDGET`
(`apps/api/narrare/_app/settings_model.py`). Defaults single-sourced from
`narrare_core.context.budget` (no backend/Core drift possible).

Model-boundary capping (ADR-082 Decision 3/4): `DefaultContextBudgetResolver`
(`packages/core/narrare_core/context/budget_resolver.py`) caps every input
budget against the configured model's context window:
`effective = min(configured, window − reserve)` with
`reserve = min(4,000 + effective_output_limit, window // 4)`. Unknown window
(offline, no cache) → uncapped passthrough, tagged
`cascade:window_unknown` (RULE-11 — never blocks generation). The resolver
only ever caps **down** (min() principle — scaling up requires explicit user
configuration).

**CR-08 P0 closure note (2026-08-15):** this closes the remaining P0 item
"model-boundary/tier-budget adoption" — all four previously hardcoded
constants (writing 6,000→32,000; analysis 6,000→32,000; series-history
512→16,000 ×2) now flow through the cascade and adopt the model boundary,
completing what `run_limits.py` did for the output side (input-side
capping). No UI in C5 (expert-invisible; the existing token-limits PATCH
API is the configuration surface).
```

And append a row to the `## Status & History` table (after the 2026-06-20 row):

```markdown
| 2026-08-15 | CR-08 P0 closed (ADR-082/C5): `context_total_budget` (32k) + `series_history_budget` (16k) cascade keys, model-boundary input capping via `DefaultContextBudgetResolver`, all four hardcoded input budgets lifted | Stable |
```

Finally, in `docs/architecture/decisions/ADR-082-token-budget-governance.md`, append a one-line clarification note at the end of Decision item 3 (after the unknown-window paragraph, directly before numbered item 4):

```markdown
> **Clarification (2026-08-15, C5 plan):** the window source is `get_model_limits` (`narrare_core.llm.cost_rates`) — the `ModelLimits | None` wrapper mirroring `DefaultRunLimitResolver`, as the Contract Sketch and resolver Protocol specify; the `get_model_limit_calibration` naming above is superseded.
```

- [ ] **Step 7: Update CURRENT_STATE (item 13 + new date entry)**

7a. In `docs/_shared/CURRENT_STATE.md`, in the numbered feature list, replace the item-13 opening (literal old text):

```
13. ✅ SET-005: Configurable Token Limits — storage/API/UI cascade exists; the CR-08 P0–P4 value-level work remains on disk (P0 model-boundary/tier-budget adoption; P1 token profile vocabulary, UI/API/Core parity/FIND-013, model-limit calibration, and suitability warnings/blocks; P2 operator/default governance; P3 governed defaults manifest; P4 status taxonomy).
```

with:

```
13. ✅ SET-005: Configurable Token Limits — storage/API/UI cascade exists; **CR-08 P0 closed 2026-08-15 (ADR-082 / C5): model-boundary/tier-budget adoption** — new cascade keys `context_total_budget` (32k, writing + analysis) and `series_history_budget` (16k, guarded carve-out within the total), input-side window capping via `DefaultContextBudgetResolver` (`min(configured, window − reserve)`, `reserve = min(4,000 + effective_output_limit, window // 4)`, RULE-11 unknown-window passthrough), all four hardcoded input budgets lifted (6,000→32,000 ×2, 512→16,000 ×2). Remaining on disk: P1 token profile vocabulary, UI/API/Core parity/FIND-013, model-limit calibration, and suitability warnings/blocks; P2 operator/default governance; P3 governed defaults manifest; P4 status taxonomy.
```

7b. Insert a new date entry directly **below** the `## Last Updated` heading (above the existing `Date: 2026-08-15 (Post-Export-Follow-ups program approved …` entry):

```
Date: 2026-08-15 (C5 — Token-Budget Governance **implemented**; [ADR-082](architecture/decisions/ADR-082-token-budget-governance.md) ✅ Implemented; CR-08 P0 "model-boundary/tier-budget adoption" closed. Two new SET-005 cascade keys — `context_total_budget` (default 32,000; one knob for writing **and** analysis, ADR-082 Decision 5) and `series_history_budget` (default 16,000; guarded carve-out `min(configured, 50% × effective_total)` within the total) — on `TokenLimitOverrides` + write-boundary bounds (≥ 1,024) + operator-env Fields `NARRARE_CONTEXT_TOTAL_BUDGET`/`NARRARE_SERIES_HISTORY_BUDGET`; JSONB store, **no migration**. New pure Core resolver `DefaultContextBudgetResolver` (`context/budget_resolver.py`, Protocol in `context/contracts.py`, mirrors `DefaultRunLimitResolver`): `reserve = min(4,000 + effective_output_limit, window // 4)`, `effective_total = min(configured, window − reserve)`, unknown window → uncapped passthrough + `cascade:window_unknown` tag (RULE-11); window source `get_model_limits` (models.dev, 24 h cache). All four hardcoded constants lifted: writing `TokenBudgetManager` 6,000→32,000, analysis `AnalysisBudgetManager` 6,000→32,000 (same Core constant), series-history tier + provider mirror 512→16,000 — documented intentional default break, regressions rewritten/pinned to the Core constants. Wiring: all five writing deps factories + beta-reader factory resolve via `settings/token_limits/context_budgets.py::resolve_context_budgets`; series-vs-standalone tier-base asymmetry per ADR-082 Decision 6 (carve-out only where `{{series_history}}` is actually injected). RULE-18b evidence: resolver unit tests (128k no-cap, 8k-window continuity 6,000/3,000, reserve boundary, containment) + per-factory wiring tests + cascade resolution tests (user→project→env→defaults). No UI, no new dependency (design doc §11; C1's slider preview consumes `EffectiveContextBudgets` next). Plan: [2026-08-15-c5-token-budget-governance.md](superpowers/plans/2026-08-15-c5-token-budget-governance.md).)
```

- [ ] **Step 8: Slice-final gates (ADR-082 Implementation Completeness Gate)**

Run each and record exact results in the task report:

```bash
just check-architecture
just typecheck
just lint-check
just test-unit
```

Expected: all four PASS. Completeness-gate checklist (verify each, cite evidence in the report):
1. ✅ Resolver + tests green (Task 1a).
2. ✅ Both cascade keys end-to-end: storage (JSONB overrides + validators) → API (`TokenLimitOverrides` + env layer) → runtime consumers (5 writing factories + beta reader) → enforcement tests (`test_token_limits_context_budgets.py`, `test_token_limits_resolution.py::TestContextBudgetResolution`, `test_context_budget_wiring.py`, `test_analysis_dependencies.py`).
3. ✅ All four lifted constants re-defaulted with rewritten/pinned regressions (Tasks 1a/1b/2b + Step 5 sweep).
4. ✅ Inventory documented in code comments (the four new constants + the ADR-082-tagged re-default sites; heuristic/stay constants already carry rationale comments — `_CHARS_PER_TOKEN`, `SUGGEST_MAX_TOKENS`, `APPROX_TOKEN_FACTOR`).
5. ✅ CR-08 P0 closure recorded in CURRENT_STATE (Step 7).

- [ ] **Step 9: Commit (via Platform, verbatim)**

```bash
git add apps/api/narrare/analysis/dependencies_beta_reader.py \
        tests/unit/api/analysis/test_analysis_dependencies.py \
        docs/architecture/decisions/ADR-082-token-budget-governance.md \
        docs/features/settings/SET-005-configurable-token-limits.md \
        docs/_shared/CURRENT_STATE.md
```

Commit message:

```
feat(api): wire beta reader to resolved context budget, close CR-08 P0

ADR-082 final wiring + slice closure:
- dependencies_beta_reader.py: factory becomes async and resolves
  context_total_budget through the cascade (user -> project=novel ->
  env -> defaults) and the analysis model's window; injects
  AnalysisContextAssembler(total_budget=resolved). FastAPI resolves
  novel_id from the endpoints' declared novel_id parameter (query) +
  user_id (CurrentUserIdDep) — both beta-reader endpoints already
  declare them. BetaReaderService itself unchanged.
- ADR-082: one-line Decision 3 clarification — the window source is
  get_model_limits (cost_rates.py ModelLimits | None wrapper, the
  DefaultRunLimitResolver mirror), superseding the
  get_model_limit_calibration naming.
- SET-005 feature spec: context-budget keys section + CR-08 P0 closure
  note (tier budgets enter the cascade and adopt the model boundary —
  input-side counterpart of run_limits.py output capping)
- CURRENT_STATE: item 13 P0 marked closed + dated C5 implementation
  entry (ADR-082 ✅ Implemented per the ADR completeness gate)

Slice-complete per RULE-20: keys + resolver + all six wiring points +
regression/pin/resolution tests landed together across Tasks 1a-3d.
Four hardcoded constants lifted (6,000 -> 32,000 x2, 512 -> 16,000 x2),
documented intentional default break, no migration, no UI, no new
dependency.

Refs: ADR-082, docs/superpowers/specs/2026-08-14-post-export-followups-design.md §3.2 (scope 4)
```

---

## Post-plan verification summary (design doc §12, C5 gate)

| Gate | Where |
|---|---|
| Budget-resolver unit tests | Task 1a (`test_budget_resolver.py` — capping arithmetic, unknown window, reserve, containment) |
| Rewritten default regressions | Tasks 1a/1b/2b (default pins against imported Core constants; literal 512/6000 defaults eliminated — swept) |
| Cascade resolution tests | Task 2b (`TestContextBudgetResolution`) |
| Runtime-consumer enforcement | Tasks 3a–3d (seam + per-factory wiring tests, RULE-18b) |
| `just verify` / full gates | Task 3d Step 8 (`check-architecture` + `typecheck` + `lint-check` + `test-unit`; run `just verify` if integration environment is up) |

## Deviations & Interpretations (honest record — read before executing)

1. **Sub-splitting for the ≤3-file cap:** the ADR's three-slice order is preserved as Tasks 1 (1a/1b), 2 (2a/2b), 3 (3a–3d). Split points: 1a/1b = contracts+resolver+writing-total vs. remaining re-defaults; 2a/2b = contract files vs. env/service/provider (service.py and settings_model.py must land together — `_apply_env_layer` reads the new Settings attributes); 3a/3b/3c/3d = seam / adapter+2 factories / 3 factories / analysis+docs.
2. **`_merge_overrides` also changes (Task 2b):** the ADR wiring sketch names `_apply_env_layer` only; `_merge_overrides` reconstructs `TokenLimitOverrides` field-by-field and would silently discard env values for any field omitted — both functions carry the new keys, with an explicit regression test (`test_env_values_survive_unrelated_db_merge`).
3. **Default-regression surface is smaller than "rewrite every 512/6000 assertion":** the sweeping `rg` hit list is dominated by *explicit* `total_budget=6000` / `token_budget=512` test fixtures (allocation-arithmetic inputs, not default regressions — they stay valid and untouched). The true default assertions found: `tests/unit/core/analysis/test_budget.py::test_default_total_budget` (rewritten in 1b) and the relative pin in `tests/unit/core/context/test_assembler.py` (passes unchanged). New positive default pins added for the writing manager (1b), the tier default (1b), and the provider mirror (2b); Step 5 of Task 3d sweeps production for stale literals.
4. **`series_in_scope` interpretation (locked, see Global Constraints):** carve-out applies only where the series-history block is actually assembled (writing main path on a series novel). Extend/rewrite/coauthor/style-variants and analysis resolve with `False` (full total). Documented in-code at each call site.
5. **Beta-reader factory signature change (async + 2 params):** required because cascade resolution needs `user_id`/`novel_id`; both router endpoints already declare these params, so FastAPI resolves them without router changes. One existing test class rewritten (Task 3d Step 1).
6. **New API-side adapter file** (`settings/token_limits/context_budgets.py`): the ADR sketch listed wiring "indicative; finalized in the C5 implementation plan". Six call sites sharing one resolver construction justifies the module (RULE-04); it also gives tests a single hermetic patch point.
7. **Window-source naming (ADR-082 Decision 3):** Decision 3 names `get_model_limit_calibration` (F1) as the resolver's window source, but the ADR's Contract Sketch/F1 and the resolver Protocol signature require `get_model_limits` — the `ModelLimits | None` wrapper in `core/llm/cost_rates.py:240`, the exact `DefaultRunLimitResolver` mirror the ADR mandates. Resolved to `get_model_limits` (used throughout this plan); Task 3d's docs step adds a one-line clarification note to ADR-082 Decision 3.
