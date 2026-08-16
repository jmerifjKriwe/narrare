# C1 — Context-Window Slider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose `SeriesSettings.context_window_size` as a 1–10 slider in the Series-Workspace Settings tab with a live honesty preview computed server-side from the series' **actual** band summaries against the **effective** post-C5/ADR-082 budgets (program item C1 of the Post-Export Follow-ups program).

**Architecture:** One pure-Core prediction seam (`SeriesHistoryTier.preview` — same `_select_text` / `_fit_to_budget` / `_estimate_tokens` code path as real assembly, **no second fitting algorithm**), one backend read model (`SeriesHistoryPreviewService` + `GET /series/{id}/settings/context-preview` returning previews for all candidate window sizes in one snapshot), budgets consumed **verbatim** via the ADR-082 chain (`TokenLimitsService` cascade → `resolve_context_budgets` with `series_in_scope=True`), and a frontend rewrite of the existing number input into slider + preview (PATCH stays on the existing settings endpoint — no new router, no migration).

**Tech Stack:** Python 3.14 (dataclasses, Pydantic), FastAPI, TanStack Query, next-intl (ICU plurals), Vitest + Testing Library, native `<input type="range">` (established `ContextBudget.tsx` slider pattern).

**Binding spec:** `docs/superpowers/specs/2026-08-14-post-export-followups-design.md` §4 (C1 — binding decisions: slider range **1–10**; placement **Series-Workspace → Settings tab** with value display + help text; **PATCH via the existing series-settings endpoint**; **live preview from actual summaries against effective budgets**, pattern `"3 Bände voll — ca. 440 / 16 000 Tokens; größeres Window wird vom Budget gekürzt"`). ADR-082 (✅ Implemented) `Implementation Notes → C1 dependency`: the preview **consumes `EffectiveContextBudgets` verbatim via `resolve_context_budgets`** — same resolver, no second computation path; the standalone-vs-series tier-base difference must be reflected in preview copy. This plan implements exactly that — nothing more, nothing less.

## Global Constraints

- **Slice semantics (RULE-20):** Tasks 1–8 are sequentially executable sub-slices of ONE coherent slice. The feature is user-visible only after Task 7b's gate passes; Tasks 4–6 land typed-but-unused plumbing that Task 7 consumes (mirroring C5's seam-first ordering). Each sub-task is independently testable and commits cleanly.
- **Package sizing:** ≤3 production files and ≤250 new LOC per delegated sub-task (test files and docs do not count toward the file cap; docstring-only corrections riding along with a task's semantic change are cap-exempt per the C5 Task-1b ruling).
- **Contract-first (RULE-03):** `apps/api/narrare/series/series_history_preview_contracts.py` + `series_history_preview_schemas.py` (Task 2) are authored FIRST and are **untouchable** for the remainder of the slice. Any later need to change them = STOP and report to the coordinator.
- **File-size limits** (`pyproject.toml [tool.narrare.architecture.file_size_limits]`; pre-commit `architecture-constraints` hook enforces them — a violation BLOCKS the commit): `series/schemas.py` is at 196/200 and `series/service.py` at 275/300 — **neither may be touched**; that is why this plan creates separate `series_history_preview_*` files (module precedent: `series_voice_schemas.py`, `band_summary_contracts.py`). `core/context/series_history.py` (253 lines, default limit 400) grows by ~125 lines — stay lean.
- **Configurable-defaults checker:** module-/class-level numeric literals > 5 are violations. The slider top (10) therefore enters the backend ONLY as the constructor-parameter default `slider_max: int = 10` (function defaults are exempt); the frontend keeps its own `MAX_WINDOW = 10` (JS — checker is Python-only). The `_DEFAULT_WINDOW_SIZE: int = 3` mirror constant is allowed (3 ≤ 5).
- **Regression-first TDD:** every new test is written and run (expected FAIL) before the implementation step that satisfies it.
- **Commits:** implementer edits + runs gates, then reports; **Platform specialist commits with the verbatim message in each task's commit step**. No `--no-verify`/`-n`, no push. On hook failure: STOP and report.
- **Language / locating:** English everywhere (code, comments, tests, commit messages; i18n message FILES excepted — en/de/fr values). Locate edit targets by semantic name/text (the code blocks below quote the current text) — never by line number.
- **No new router file, no migration, no new dependency** (design §4.1: PATCH via the existing endpoint; JSONB/Integer columns already exist — Alembic 0038).
- **Preview honesty requirements (design §4.1, verbatim binding):** real summary data (no fabricated estimates); effective budgets from `resolve_context_budgets` (never raw configured values, never a second computation path); budget-clipping warning when window × full summaries exceed the effective series-history budget; the series-vs-standalone tier-base semantics stated in preview copy (from the Series-Workspace the subject is always a series band → carve-out applies; the copy states what the remaining tier base is reserved for).
- **i18n:** 3 locales × the new `series.settings.contextPreview.*` keys in `packages/i18n/messages/{en,de,fr}/studio.json`, following the existing `series.settings.contextWindow.*` conventions.
- **Test commands:** backend focused runs via `just test-file <path>`; per-task backend gate `just test-unit` (use `just test-lowmem` on <12 GB RAM machines). Frontend: `cd packages/web && pnpm test <path-filter>` (scoped), `pnpm type-check`, `pnpm lint:check`; frontend gate `just test-frontend`. Architecture checker: `just check-architecture`. Slice-final gates (Task 8): `just check-architecture`, `just typecheck`, `just lint-check`, `just test-unit`, frontend `pnpm type-check` + `pnpm lint:check`, `just test-frontend`.
- **Next-band semantics (ruling, locked for this plan):** from the Series-Workspace the preview subject is **the next band** — every positioned member novel of the series is a prior band. Rationale: when band N+1 is generated, all N existing bands are prior bands (exactly what `SeriesHistoryProvider.assemble_series_history` would see for that novel); this needs no "current novel" selection and is well-defined for every series. Model routing + cascade resolve at user level (`project_id=None`) because the next band has no novel id yet; project-level routing/cascade overrides for a *specific* existing novel may differ at its generation time — documented in the service docstring and the feature spec (Task 8), not surfaced in the UI (YAGNI).
- **Design-discrepancy context (read before executing):** design §4 says `context_window_size` is "not exposed: no settings-API surface, no UI". **Empirically false at plan time (2026-08-16):** the API surface exists (`SeriesSettingsResponse.context_window_size`, `SeriesSettingsUpdateRequest.context_window_size` bounded `[1, 50]`, wired through `SeriesService.get_settings`/`update_settings` → `SeriesRepository.update_settings`) AND a UI exists (`SeriesContextWindowField` number input [1, 50] on the Settings tab). What is genuinely missing — and what this plan delivers — is the **1–10 slider** and the **honesty preview**. The existing component's docstring rationale for a number input ("Precision … not the approximation a slider implies") is superseded by the approved design §4.1. The API bound stays `[1, 50]` (a superset settable via MCP/CLI); the UI clamps to 1–10 and handles a saved out-of-range value honestly (see Task 3 service + Task 7b).

---

### Task 1: Core — `SeriesHistoryTier.preview` prediction seam

**Files:**
- Modify: `packages/core/narrare_core/context/series_history.py` (extract `_render_entry`; add `SeriesHistoryPreview` dataclass + `preview` method)
- Test: `tests/unit/core/context/test_series_history_preview.py` (new)

**Interfaces:**
- Consumes: nothing new (pure extension of the existing module's internals).
- Produces (verbatim for all later tasks):
  - `SeriesHistoryPreview` — frozen slots dataclass, fields: `window_size: int`, `token_budget: int`, `estimated_tokens: int`, `bands_total: int`, `bands_full: int`, `bands_short: int`, `bands_truncated: int`, `bands_dropped: int`, `bands_missing: int`, `budget_clipped: bool`.
  - `SeriesHistoryTier.preview(bands: list[BandSummaryData], window_size: int = 3, token_budget: int = DEFAULT_SERIES_HISTORY_BUDGET) -> SeriesHistoryPreview` (async, pure).
  - Invariant: `bands_full + bands_short + bands_truncated + bands_dropped + bands_missing == bands_total`, and `estimated_tokens` equals `_estimate_tokens` of exactly what `assemble(bands, window_size, token_budget)` would render.

**No second fitting algorithm (the core ruling of this task):** `preview` builds the identical entry list `assemble` builds (same `_select_text` call, same `_render_entry` formatter — newly extracted so both paths share one format string), then calls the **same** `_fit_to_budget(entries, token_budget)` and classifies each entry by walking the fitted output: an input entry that appears unchanged in `fitted` was rendered in full; the single entry where `fitted[i] != entry` is the truncated boundary band (the only other thing `_fit_to_budget` can emit there); entries after the fitted list ends were dropped. Entries are distinguishable by their distinct `"Band {position} — "` prefixes, so equality comparison is unambiguous.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/core/context/test_series_history_preview.py`:

```python
"""Tests for SeriesHistoryTier.preview (C1 — Context-Window Slider).

The preview must predict EXACTLY what :meth:`assemble` renders at a given
window size / token budget — same entry building, same greedy fit. The
consistency tests run both side by side and assert the prediction matches
the real output line for line. Pure data, no I/O (RULE-07).
"""

from __future__ import annotations

import pytest

from narrare_core.context.series_history import (
    _HEADER,
    _estimate_tokens,
    BandSummaryData,
    SeriesHistoryPreview,
    SeriesHistoryTier,
)


def _band(
    position: int,
    *,
    title: str = "Untitled",
    full: str | None = None,
    short: str | None = None,
    override: str | None = None,
) -> BandSummaryData:
    return BandSummaryData(
        position=position,
        title=title,
        full_summary=full,
        short_summary=short,
        override=override,
    )


def _long(tag: str, chars: int = 1500) -> str:
    """~375+ tokens of text with unique start/end markers."""
    return f"{tag}START " + ("x" * chars) + f" {tag}END"


def _four_bands() -> list[BandSummaryData]:
    return [
        _band(1, full=_long("B1"), short="One.", title="First"),
        _band(2, full=_long("B2"), short="Two.", title="Second"),
        _band(3, full=_long("B3"), short="Three.", title="Third"),
        _band(4, full=_long("B4"), short="Four.", title="Fourth"),
    ]


class TestFullShortClassification:
    async def test_window_two_full_recent_short_older(self) -> None:
        result = await SeriesHistoryTier().preview(_four_bands(), 2, 100_000)

        assert result.bands_total == 4
        assert result.bands_full == 2  # bands 4, 3 (newest)
        assert result.bands_short == 2  # bands 2, 1
        assert result.bands_truncated == 0
        assert result.bands_dropped == 0
        assert result.bands_missing == 0
        assert result.budget_clipped is False

    async def test_window_larger_than_band_count_treats_all_full(self) -> None:
        result = await SeriesHistoryTier().preview(_four_bands(), 10, 100_000)

        assert result.bands_full == 4
        assert result.bands_short == 0

    async def test_override_counts_as_full_within_window(self) -> None:
        bands = [
            _band(1, full=_long("B1"), short="One."),
            _band(2, full=None, short="Two.", override="Curated."),
        ]
        result = await SeriesHistoryTier().preview(bands, 1, 100_000)

        assert result.bands_full == 1  # band 2 via override
        assert result.bands_short == 1

    async def test_missing_summaries_depend_on_window(self) -> None:
        """A band without full summary is missing in-window, but its short
        summary still counts out-of-window (mirrors _select_text)."""
        bands = [_band(1, full=None, short="One."), _band(2, full=_long("B2"), short="Two.")]
        tier = SeriesHistoryTier()

        large = await tier.preview(bands, 5, 100_000)
        small = await tier.preview(bands, 1, 100_000)

        assert large.bands_missing == 1  # band 1 has no full text
        assert small.bands_missing == 0  # band 1 out of window -> short used


class TestBudgetClipping:
    async def test_boundary_band_truncated_older_dropped(self) -> None:
        """Budget fits band 4 fully + a slice of band 3 -> band 3 truncated,
        bands 2 and 1 dropped (sacrifice older first)."""
        tier = SeriesHistoryTier()
        band4 = f"Band 4 — Fourth: {_long('B4')}"
        budget = _estimate_tokens(band4) + 200  # room for band 4 + a 200-tok slice

        result = await tier.preview(_four_bands(), 4, budget)

        assert result.bands_full == 1
        assert result.bands_truncated == 1
        assert result.bands_dropped == 2
        assert result.budget_clipped is True

    async def test_budget_below_truncate_floor_drops_without_truncating(self) -> None:
        """Remaining headroom < _MIN_TRUNCATE_TOKENS -> nothing appended.

        Budget 25: 25 - _HEADER (7 tokens) = 18 < 20, so the boundary band
        is dropped whole. Budget 30 must NOT be used here: 30 - 7 = 23 >= 20
        puts the boundary band into the truncation band (exactly the
        consistency suite's budget=30 parametrization below), which would
        contradict the drop-expectation.
        """
        result = await SeriesHistoryTier().preview(_four_bands(), 4, 25)

        assert result.bands_full == 0
        assert result.bands_truncated == 0
        assert result.bands_dropped == 4
        assert result.budget_clipped is True

    async def test_zero_budget_drops_everything(self) -> None:
        result = await SeriesHistoryTier().preview(_four_bands(), 3, 0)

        assert result.estimated_tokens == 0
        assert result.bands_dropped == 4

    async def test_estimated_tokens_never_exceed_budget(self) -> None:
        tier = SeriesHistoryTier()
        for budget in (0, 30, 200, 800, 2_000, 100_000):
            result = await tier.preview(_four_bands(), 4, budget)
            assert result.estimated_tokens <= max(budget, 0), budget


class TestEdgeCases:
    async def test_empty_bands_all_zero(self) -> None:
        result = await SeriesHistoryTier().preview([], 3, 16_000)

        assert result == SeriesHistoryPreview(
            window_size=3,
            token_budget=16_000,
            estimated_tokens=0,
            bands_total=0,
            bands_full=0,
            bands_short=0,
            bands_truncated=0,
            bands_dropped=0,
            bands_missing=0,
            budget_clipped=False,
        )

    async def test_window_size_reported_clamped_at_zero(self) -> None:
        """Negative window mirrors assemble's max(window, 0) treatment."""
        result = await SeriesHistoryTier().preview(_four_bands(), -1, 100_000)

        assert result.window_size == 0
        assert result.bands_full == 0
        assert result.bands_short == 4


class TestAssembleConsistency:
    """The preview predicts assemble's real output — the no-second-algorithm
    guarantee, asserted end to end."""

    @pytest.mark.parametrize("window_size", [0, 1, 2, 3, 4, 7])
    @pytest.mark.parametrize("token_budget", [0, 30, 200, 800, 2_000, 100_000])
    async def test_preview_matches_assemble_output(
        self, window_size: int, token_budget: int
    ) -> None:
        tier = SeriesHistoryTier()
        bands = _four_bands() + [_band(5, full=None, short=None)]  # one fully-missing band

        preview = await tier.preview(bands, window_size, token_budget)
        output = await tier.assemble(bands, window_size, token_budget)

        rendered_lines = sum(
            1 for line in output.split("\n\n") if line.startswith("Band ")
        )
        rendered = preview.bands_full + preview.bands_short + preview.bands_truncated
        assert rendered_lines == rendered
        if rendered > 0:
            assert output.startswith(_HEADER)
            assert preview.estimated_tokens == _estimate_tokens(output)
        else:
            assert output == ""
            assert preview.estimated_tokens == 0

    @pytest.mark.parametrize("window_size", [1, 3, 5])
    @pytest.mark.parametrize("token_budget", [30, 800, 100_000])
    async def test_classification_invariant(self, window_size: int, token_budget: int) -> None:
        result = await SeriesHistoryTier().preview(_four_bands(), window_size, token_budget)

        assert (
            result.bands_full
            + result.bands_short
            + result.bands_truncated
            + result.bands_dropped
            + result.bands_missing
            == result.bands_total
            == 4
        )
        assert result.budget_clipped == (result.bands_truncated + result.bands_dropped > 0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test-file tests/unit/core/context/test_series_history_preview.py`
Expected: FAIL — `ImportError: cannot import name 'SeriesHistoryPreview'` (collection error).

- [ ] **Step 3: Extract `_render_entry` (shared format string)**

In `packages/core/narrare_core/context/series_history.py`:

3a. Replace the `__all__` line:

```python
__all__ = ["BandSummaryData", "SeriesHistoryTier"]
```

with:

```python
__all__ = ["BandSummaryData", "SeriesHistoryPreview", "SeriesHistoryTier"]
```

3b. In the "Token helpers (module-private)" section, after the `_truncate_to_tokens` function, add (the module has no separate formatting-helpers section — the cohesion choice is recorded in the helper's docstring):

```python
def _render_entry(band: BandSummaryData, text: str) -> str:
    """Format one band's contribution line (shared by assemble + preview).

    Formatting helper placed among the token helpers on purpose: the module
    has no separate formatting section, and it belongs with
    ``_truncate_to_tokens`` as a seam shared by assemble and preview.
    """
    return f"Band {band.position} — {band.title}: {text}"
```

3c. In `SeriesHistoryTier.assemble`, replace the line:

```python
            entries.append(f"Band {band.position} — {band.title}: {text}")
```

with:

```python
            entries.append(_render_entry(band, text))
```

- [ ] **Step 4: Add the `SeriesHistoryPreview` dataclass**

In the same file, directly after the `BandSummaryData` class (before the `# Token helpers (module-private)` section header), insert:

```python
@dataclass(frozen=True, slots=True)
class SeriesHistoryPreview:
    """Outcome prediction for :meth:`SeriesHistoryTier.assemble` (C1 slider).

    Classifies every prior band for one candidate ``window_size`` /
    ``token_budget`` pair. Derived from the SAME greedy fit
    (``_fit_to_budget``) the real assembly runs — never a second algorithm.
    Consumed by the Backend preview service (C1) for the Settings-tab
    honesty preview; pure data, no I/O.

    Invariant:
        ``bands_full + bands_short + bands_truncated + bands_dropped +
        bands_missing == bands_total`` and ``estimated_tokens`` is the
        chars/4 estimate of exactly the string ``assemble`` would render.
    """

    window_size: int
    """Effective window (negatives clamped to 0, mirroring assemble)."""
    token_budget: int
    """Budget the prediction was computed against (as passed)."""
    estimated_tokens: int
    """Estimated tokens of the block assemble would render (header incl.)."""
    bands_total: int
    """Prior bands considered (len of the input list)."""
    bands_full: int
    """In-window bands rendered with their full/override summary."""
    bands_short: int
    """Out-of-window bands rendered with their one-sentence summary."""
    bands_truncated: int
    """Boundary band truncated to the remaining headroom (0 or 1)."""
    bands_dropped: int
    """Bands dropped entirely by budget exhaustion (oldest first)."""
    bands_missing: int
    """Bands skipped because their selected text is empty/None (per window)."""
    budget_clipped: bool
    """True when truncation or drops occurred (window exceeds the budget)."""
```

- [ ] **Step 5: Add the `preview` method**

In the same file, inside `class SeriesHistoryTier`, directly after the `assemble` method (before the `# Internal helpers` section header), insert:

```python
    async def preview(
        self,
        bands: list[BandSummaryData],
        window_size: int = 3,
        token_budget: int = DEFAULT_SERIES_HISTORY_BUDGET,
    ) -> SeriesHistoryPreview:
        """Predict what :meth:`assemble` would render (C1 slider preview).

        Reuses the exact assembly path — ``_select_text`` for text choice,
        ``_render_entry`` for formatting, ``_fit_to_budget`` for the greedy
        fit — and classifies the result instead of joining it:

        * an input entry appearing unchanged in the fitted output was
          rendered in full (``bands_full`` in window / ``bands_short``
          outside);
        * the single fitted entry that differs from its input entry is the
          truncated boundary band (``bands_truncated``);
        * input entries after the fitted output ends were dropped
          (``bands_dropped``); entries never built have no usable text
          (``bands_missing``).

        Args:
            bands: Prior bands (current novel excluded by the caller), any
                order — sorted newest-first here, as in ``assemble``.
            window_size: Candidate recency window (slider position).
            token_budget: Effective series-history ceiling (ADR-082 —
                pass the resolved ``EffectiveContextBudgets.series_history``).

        Returns:
            Frozen per-window prediction (see :class:`SeriesHistoryPreview`).
        """
        ordered = sorted(bands, key=lambda b: b.position, reverse=True)
        effective_window = max(window_size, 0)
        positions_desc = sorted({b.position for b in ordered}, reverse=True)
        window_positions = set(positions_desc[:effective_window])

        entries: list[str] = []
        in_window_flags: list[bool] = []
        missing = 0
        for band in ordered:
            text = self._select_text(band, in_window=band.position in window_positions)
            if not text:
                missing += 1  # RULE-11 mirror: skipped, not crashed
                continue
            entries.append(_render_entry(band, text))
            in_window_flags.append(band.position in window_positions)

        fitted = self._fit_to_budget(entries, token_budget)

        full = short = truncated = 0
        fitted_index = 0
        for entry, in_window in zip(entries, in_window_flags):
            if fitted_index >= len(fitted):
                continue  # budget exhausted — dropped
            if fitted[fitted_index] == entry:
                if in_window:
                    full += 1
                else:
                    short += 1
            else:
                truncated += 1  # boundary band, truncated to headroom
            fitted_index += 1
        dropped = len(entries) - full - short - truncated

        estimated = _estimate_tokens(_HEADER + "\n\n".join(fitted)) if fitted else 0
        return SeriesHistoryPreview(
            window_size=effective_window,
            token_budget=token_budget,
            estimated_tokens=estimated,
            bands_total=len(bands),
            bands_full=full,
            bands_short=short,
            bands_truncated=truncated,
            bands_dropped=dropped,
            bands_missing=missing,
            budget_clipped=truncated > 0 or dropped > 0,
        )
```

- [ ] **Step 6: Run the preview tests to verify they pass**

Run: `just test-file tests/unit/core/context/test_series_history_preview.py`
Expected: PASS — all tests (classification, clipping, edges, 36 consistency params, 9 invariant params).

- [ ] **Step 7: Run the existing series-history suite to prove no regression**

Run: `just test-file tests/unit/core/context/test_series_history.py tests/unit/api/series/test_series_history_provider.py tests/unit/core/writing/test_series_history_variable.py`
Expected: PASS — the `_render_entry` extraction is behavior-identical (same format string).

- [ ] **Step 8: Commit (via Platform, verbatim)**

```bash
git add packages/core/narrare_core/context/series_history.py \
        tests/unit/core/context/test_series_history_preview.py
```

Commit message:

```
feat(core): add SeriesHistoryTier.preview — window/budget outcome prediction

C1 (Post-Export Follow-ups program, design §4): the slider needs an
honesty preview that predicts what the series-history block will contain
at a given window size against the effective ADR-082 budget.

- SeriesHistoryPreview: frozen dataclass classifying every prior band
  (full / short / truncated / dropped / missing) plus the estimated
  token total; invariant full+short+truncated+dropped+missing == total.
- SeriesHistoryTier.preview: reuses the exact assembly path —
  _select_text for text choice, _render_entry (newly extracted so
  assemble and preview share ONE format string) for formatting, and the
  SAME _fit_to_budget greedy fit for classification. NO second fitting
  algorithm: classification is derived by walking the fitted output
  against the input entries (distinct "Band N — " prefixes make the
  equality walk unambiguous).
- assemble: behavior-identical refactor — the inline entry f-string
  becomes a _render_entry call (single source for the line format).

Tests: classification (window/override/missing-per-window), budget
clipping (truncate boundary + drop older, sub-floor drop, zero budget,
estimate-never-exceeds-budget), edge cases (empty bands, negative
window), and assemble-consistency parametrized suites asserting the
preview matches the real output line for line (the no-drift guarantee).

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §4 (C1), ADR-082 Implementation Notes (C1 dependency)
```

---

### Task 2: API — preview schemas + service contract (contract-first, untouchable after)

**Files:**
- Create: `apps/api/narrare/series/series_history_preview_schemas.py`
- Create: `apps/api/narrare/series/series_history_preview_contracts.py`
- Test: `tests/unit/api/series/test_series_history_preview_contracts.py` (new)

**Interfaces:**
- Consumes: nothing from Task 1 at the schema level (the entry mirrors the Core dataclass field-for-field; the service maps in Task 3).
- Produces (verbatim for all later tasks):
  - `SeriesHistoryPreviewEntry(BaseModel)` — fields `window_size: int`, `token_budget: int`, `estimated_tokens: int`, `bands_total: int`, `bands_full: int`, `bands_short: int`, `bands_truncated: int`, `bands_dropped: int`, `bands_missing: int`, `budget_clipped: bool`.
  - `SeriesHistoryPreviewResponse(BaseModel)` — fields `series_id: uuid.UUID`, `current_window_size: int`, `effective_series_history_budget: int`, `effective_context_total: int`, `effective_tier_base: int`, `model_context_window: int | None`, `budget_source: str`, `previews: list[SeriesHistoryPreviewEntry]`.
  - `SeriesHistoryPreviewServiceProtocol` — `async get_preview(series_id: uuid.UUID, user_id: uuid.UUID) -> SeriesHistoryPreviewResponse`.
- **Why separate files (not `schemas.py`/`contracts.py`):** `series/schemas.py` is at 196/200 and `series/contracts.py` at 197/200 of their RULE-04 file-size limits — the pre-commit `architecture-constraints` hook would reject the commit. The `series_voice_schemas.py` / `band_summary_contracts.py` extraction precedent applies.

- [ ] **Step 1: Write the failing contract tests**

Create `tests/unit/api/series/test_series_history_preview_contracts.py`:

```python
"""Contract tests for the C1 series-history preview surface (RULE-03).

Schemas mirror the Core SeriesHistoryPreview field-for-field (the service
maps via dataclasses.asdict — name parity is load-bearing) and the Protocol
fixes the service surface the router will depend on.
"""

from __future__ import annotations

from narrare.series.series_history_preview_contracts import (
    SeriesHistoryPreviewServiceProtocol,
)
from narrare.series.series_history_preview_schemas import (
    SeriesHistoryPreviewEntry,
    SeriesHistoryPreviewResponse,
)


class TestEntrySchema:
    def test_mirrors_core_preview_fields(self) -> None:
        from dataclasses import fields as dc_fields

        from narrare_core.context.series_history import SeriesHistoryPreview

        core_names = {f.name for f in dc_fields(SeriesHistoryPreview)}
        schema_names = set(SeriesHistoryPreviewEntry.model_fields)
        assert schema_names == core_names

    def test_constructs_from_core_dict(self) -> None:
        payload = {
            "window_size": 3,
            "token_budget": 16_000,
            "estimated_tokens": 440,
            "bands_total": 5,
            "bands_full": 3,
            "bands_short": 2,
            "bands_truncated": 0,
            "bands_dropped": 0,
            "bands_missing": 0,
            "budget_clipped": False,
        }
        entry = SeriesHistoryPreviewEntry.model_validate(payload)
        assert entry.bands_full == 3
        assert entry.budget_clipped is False


class TestResponseSchema:
    def test_holds_effective_budget_metadata(self) -> None:
        response = SeriesHistoryPreviewResponse(
            series_id="00000000-0000-0000-0000-000000000001",
            current_window_size=3,
            effective_series_history_budget=16_000,
            effective_context_total=32_000,
            effective_tier_base=16_000,
            model_context_window=128_000,
            budget_source="cascade:uncapped",
            previews=[
                SeriesHistoryPreviewEntry.model_validate(
                    {
                        "window_size": 1,
                        "token_budget": 16_000,
                        "estimated_tokens": 150,
                        "bands_total": 5,
                        "bands_full": 1,
                        "bands_short": 4,
                        "bands_truncated": 0,
                        "bands_dropped": 0,
                        "bands_missing": 0,
                        "budget_clipped": False,
                    }
                )
            ],
        )
        assert response.model_context_window == 128_000
        assert response.previews[0].window_size == 1

    def test_model_context_window_allows_none(self) -> None:
        response = SeriesHistoryPreviewResponse(
            series_id="00000000-0000-0000-0000-000000000001",
            current_window_size=3,
            effective_series_history_budget=16_000,
            effective_context_total=32_000,
            effective_tier_base=16_000,
            model_context_window=None,
            budget_source="cascade:window_unknown",
            previews=[],
        )
        assert response.model_context_window is None


class TestProtocol:
    def test_protocol_exposes_get_preview(self) -> None:
        assert hasattr(SeriesHistoryPreviewServiceProtocol, "get_preview")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test-file tests/unit/api/series/test_series_history_preview_contracts.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'narrare.series.series_history_preview_schemas'`.

- [ ] **Step 3: Create the schemas file**

Create `apps/api/narrare/series/series_history_preview_schemas.py`:

```python
"""Pydantic schemas for the series-history preview (C1 — Context-Window
Slider, design §4; RULE-04: separate file because ``series/schemas.py`` is
at its 200-line limit — ``series_voice_schemas.py`` precedent).

The response is a derived READ MODEL, not persisted state: per-window
predictions computed from the series' actual band summaries against the
effective ADR-082 budgets. ``SeriesHistoryPreviewEntry`` mirrors the Core
``SeriesHistoryPreview`` dataclass field-for-field so the service can map
via ``dataclasses.asdict`` (name parity is load-bearing).

Next-band semantics: the preview describes generating the NEXT band of
this series — every positioned member novel is a prior band (the exact
view ``SeriesHistoryProvider.assemble_series_history`` would have for
that novel). See the feature spec (SERIES-002) and the service docstring.
"""

from __future__ import annotations

import uuid  # noqa: TC003 - needed at runtime for Pydantic model resolution

from pydantic import BaseModel


class SeriesHistoryPreviewEntry(BaseModel):
    """Prediction for one candidate window size (mirrors Core)."""

    window_size: int
    token_budget: int
    """Effective series-history ceiling this prediction was computed against."""
    estimated_tokens: int
    bands_total: int
    bands_full: int
    bands_short: int
    bands_truncated: int
    bands_dropped: int
    bands_missing: int
    budget_clipped: bool


class SeriesHistoryPreviewResponse(BaseModel):
    """GET /api/v1/series/{id}/settings/context-preview response.

    Budget metadata is ``EffectiveContextBudgets`` verbatim (ADR-082 — the
    same resolver output the writing pipeline consumes; no second
    computation path): series novels carve the series-history ceiling out
    of the context total, and the remaining tier base serves the current
    band's own context — the preview copy states this asymmetry.
    """

    series_id: uuid.UUID
    current_window_size: int
    """Saved setting (default 3 when no settings row exists)."""
    effective_series_history_budget: int
    """EffectiveContextBudgets.series_history — the preview's token ceiling."""
    effective_context_total: int
    """EffectiveContextBudgets.context_total."""
    effective_tier_base: int
    """EffectiveContextBudgets.writing_tier_base (total − series history)."""
    model_context_window: int | None
    """Window used for capping (None = unknown/offline, RULE-11 — uncapped)."""
    budget_source: str
    """EffectiveContextBudgets.source provenance tag."""
    previews: list[SeriesHistoryPreviewEntry]
    """Window sizes 1..max(slider top, current_window_size) — one snapshot."""
```

- [ ] **Step 4: Create the contracts file**

Create `apps/api/narrare/series/series_history_preview_contracts.py`:

```python
"""Service contract for the series-history preview (C1 — RULE-03 contract
first; RULE-04: separate file because ``series/contracts.py`` is at its
200-line limit — ``band_summary_contracts.py`` precedent).

Ownership contract (mirrors ``SeriesServiceProtocol``): ``get_preview``
verifies the caller owns the series BEFORE any read; a missing series and
a not-owned series BOTH surface as ``ForbiddenError`` (HTTP 403,
anti-enumeration — never 404).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.series.series_history_preview_schemas import (
        SeriesHistoryPreviewResponse,
    )


@runtime_checkable
class SeriesHistoryPreviewServiceProtocol(Protocol):
    """Read surface for the C1 slider honesty preview."""

    async def get_preview(
        self, series_id: uuid.UUID, user_id: uuid.UUID
    ) -> SeriesHistoryPreviewResponse:
        """Compute per-window previews for a series' actual summaries.

        Args:
            series_id: The series whose Settings-tab preview is requested.
            user_id: Authenticated caller (ownership enforced, 403 on
                missing/not-owned — anti-enumeration).

        Returns:
            Window sizes 1..max(slider top, current saved window) computed
            against the effective ADR-082 series-history ceiling.
        """
        ...
```

- [ ] **Step 5: Run the contract tests to verify they pass**

Run: `just test-file tests/unit/api/series/test_series_history_preview_contracts.py`
Expected: PASS — 5 tests.

- [ ] **Step 6: Run the architecture checker**

Run: `just check-architecture`
Expected: PASS (both new files under their `schemas`/`contracts` size limits; import direction one-way).

- [ ] **Step 7: Commit (via Platform, verbatim)**

```bash
git add apps/api/narrare/series/series_history_preview_schemas.py \
        apps/api/narrare/series/series_history_preview_contracts.py \
        tests/unit/api/series/test_series_history_preview_contracts.py
```

Commit message:

```
feat(api): add series-history preview schemas and service contract

C1 contract-first step (RULE-03): the response/read surface the slider
preview will consume, authored before the service.

- series_history_preview_schemas.py: SeriesHistoryPreviewEntry (mirrors
  the Core SeriesHistoryPreview dataclass field-for-field — the service
  maps via dataclasses.asdict, name parity is load-bearing and pinned by
  a contract test) + SeriesHistoryPreviewResponse carrying
  EffectiveContextBudgets verbatim (series-history ceiling, context
  total, tier base, model window, provenance source) alongside the
  per-window predictions. Separate file: series/schemas.py is at its
  200-line RULE-04 limit (series_voice_schemas.py precedent).
- series_history_preview_contracts.py:
  SeriesHistoryPreviewServiceProtocol — get_preview(series_id, user_id)
  with the module's ownership contract (403 anti-enumeration on
  missing/not-owned, mirroring SeriesServiceProtocol).

Next-band semantics documented at the schema level: the preview
describes generating the NEXT band — every positioned member is a prior
band. Contract files are untouchable for the remainder of the C1 slice.

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §4 (C1), ADR-082 (EffectiveContextBudgets verbatim)
```

---

### Task 3: API — preview service + provider band-data accessor

**Files:**
- Modify: `apps/api/narrare/series/series_history_provider.py` (+ public `collect_series_band_data`)
- Create: `apps/api/narrare/series/series_history_preview_service.py`
- Test: `tests/unit/api/series/test_series_history_preview_service.py` (new), `tests/unit/api/series/test_series_history_provider.py` (extend)

**Interfaces:**
- Consumes: `SeriesHistoryTier.preview` + `SeriesHistoryPreview` (Task 1); `SeriesHistoryPreviewEntry` / `SeriesHistoryPreviewResponse` (Task 2); `SeriesRepositoryProtocol.get/get_settings/list_novels`; `EffectiveContextBudgets` (`narrare_core.context.contracts`); `ForbiddenError` (`narrare_core.shared.errors`).
- Produces (verbatim for Tasks 4/7):
  - `SeriesHistoryProvider.collect_series_band_data(series_id: uuid.UUID) -> list[BandSummaryData]` — all positioned members, next-band semantics.
  - `SeriesHistoryPreviewService(*, series_repo: SeriesRepositoryProtocol, provider: SeriesHistoryProvider, budgets_provider: Callable[[], EffectiveContextBudgets], tier: SeriesHistoryTier | None = None, slider_max: int = 10)`.
  - `SeriesHistoryPreviewService.get_preview(series_id, user_id) -> SeriesHistoryPreviewResponse` — previews for window sizes `1..max(slider_max, current_window_size)`.

- [ ] **Step 1: Write the failing service tests**

Create `tests/unit/api/series/test_series_history_preview_service.py`:

```python
"""Tests for SeriesHistoryPreviewService (C1 — honesty preview read model).

Domain fakes (ADR-030): FakeSeriesRepository for ownership + settings;
the REAL SeriesHistoryProvider over FakeSeriesRepository /
FakeBandSummaryRepository (its collect_series_band_data landed in this
same task); the REAL Core tier; a canned budgets_provider returning a
frozen EffectiveContextBudgets (the factory's ADR-082 resolution is
pinned by wiring tests, not duplicated here).
"""

from __future__ import annotations

import uuid

import pytest

from narrare.series.band_summary_models import BandSummary
from narrare.series.series_history_preview_contracts import (
    SeriesHistoryPreviewServiceProtocol,
)
from narrare.series.series_history_preview_service import SeriesHistoryPreviewService
from narrare.series.series_history_provider import SeriesHistoryProvider
from narrare_core.context.contracts import EffectiveContextBudgets
from narrare_core.series.schemas import Series
from narrare_core.shared.errors import ForbiddenError
from tests.fakes.fake_band_summary_repo import FakeBandSummaryRepository
from tests.fakes.fake_series_repo import FakeSeriesRepository


def _series(user_id: uuid.UUID) -> Series:
    return Series(id=uuid.uuid4(), user_id=user_id, title="Chronicles")


def _budgets(series_history: int = 16_000) -> EffectiveContextBudgets:
    return EffectiveContextBudgets(
        context_total=32_000,
        series_history=series_history,
        writing_tier_base=32_000 - series_history,
        reserve_tokens=8_096,
        context_window=128_000,
        source="cascade:uncapped",
    )


def _summary(novel_id: uuid.UUID, full: str, short: str) -> BandSummary:
    return BandSummary(novel_id=novel_id, full_summary=full, short_summary=short)


def _make_service(
    *,
    series_repo: FakeSeriesRepository,
    band_repo: FakeBandSummaryRepository | None = None,
    series_history: int = 16_000,
) -> SeriesHistoryPreviewService:
    provider = SeriesHistoryProvider(
        novel_repo=None,  # type: ignore[arg-type] — unused by collect_series_band_data
        series_repo=series_repo,
        band_summary_repo=band_repo or FakeBandSummaryRepository(),
    )
    return SeriesHistoryPreviewService(
        series_repo=series_repo,
        provider=provider,
        budgets_provider=lambda: _budgets(series_history),
    )


class TestOwnership:
    async def test_unknown_series_raises_forbidden(self) -> None:
        service = _make_service(series_repo=FakeSeriesRepository())

        with pytest.raises(ForbiddenError):
            await service.get_preview(uuid.uuid4(), uuid.uuid4())

    async def test_foreign_series_raises_forbidden(self) -> None:
        owner, stranger = uuid.uuid4(), uuid.uuid4()
        series_repo = FakeSeriesRepository()
        series_repo.seed(_series(owner))
        series_id = next(iter(series_repo._series))
        service = _make_service(series_repo=series_repo)

        with pytest.raises(ForbiddenError):
            await service.get_preview(series_id, stranger)


class TestWindowRange:
    async def test_default_settings_row_missing_yields_range_1_to_10(self) -> None:
        owner = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        series = _series(owner)
        series_repo.seed(series)
        series_repo._settings.pop(series.id)  # fake has no public unset — private pop
        service = _make_service(series_repo=series_repo)

        result = await service.get_preview(series.id, owner)

        assert result.current_window_size == 3
        assert [p.window_size for p in result.previews] == list(range(1, 11))

    async def test_saved_window_within_slider_range(self) -> None:
        owner = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        series_repo.seed(_series(owner))
        await series_repo.update_settings(
            next(iter(series_repo._series)), {"context_window_size": 7}
        )
        service = _make_service(series_repo=series_repo)

        result = await service.get_preview(next(iter(series_repo._series)), owner)

        assert result.current_window_size == 7
        assert [p.window_size for p in result.previews] == list(range(1, 11))

    async def test_saved_window_above_slider_extends_range(self) -> None:
        """API/MCP can save up to 50 — the preview stays honest for it."""
        owner = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        series_repo.seed(_series(owner))
        series_id = next(iter(series_repo._series))
        await series_repo.update_settings(series_id, {"context_window_size": 12})
        service = _make_service(series_repo=series_repo)

        result = await service.get_preview(series_id, owner)

        assert result.current_window_size == 12
        assert [p.window_size for p in result.previews] == list(range(1, 13))


class TestComputation:
    async def test_actual_summaries_flow_into_counts(self) -> None:
        owner = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        series = _series(owner)
        band_repo = FakeBandSummaryRepository()

        # Three positioned member novels (next-band semantics: all prior).
        # Plain attribute shapes are enough — FakeSeriesRepository.list_novels
        # runs NovelRow.model_validate(n), and NovelRow is
        # extra="allow", from_attributes=True.
        novels = []
        summaries = []
        for position in (1, 2, 3):
            novel_id = uuid.uuid4()
            novels.append(
                type(
                    "NovelRow",
                    (),
                    {
                        "id": novel_id,
                        "title": f"Band {position}",
                        "series_position": position,
                    },
                )()
            )
            summaries.append(
                _summary(novel_id, full="Full text. " * 80, short=f"Short {position}.")
            )
        series_repo.seed(series, novels=novels)
        band_repo.seed(*summaries)
        service = _make_service(series_repo=series_repo, band_repo=band_repo)

        result = await service.get_preview(series.id, owner)

        entry = next(p for p in result.previews if p.window_size == 10)
        assert entry.bands_total == 3
        assert entry.bands_full == 3
        assert entry.bands_missing == 0
        assert entry.estimated_tokens > 0

    async def test_every_entry_uses_effective_series_history_budget(self) -> None:
        owner = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        series_repo.seed(_series(owner))
        service = _make_service(series_repo=series_repo, series_history=3_000)

        result = await service.get_preview(next(iter(series_repo._series)), owner)

        assert result.effective_series_history_budget == 3_000
        assert all(p.token_budget == 3_000 for p in result.previews)

    async def test_budget_metadata_passthrough_verbatim(self) -> None:
        owner = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        series_repo.seed(_series(owner))
        service = _make_service(series_repo=series_repo)

        result = await service.get_preview(next(iter(series_repo._series)), owner)

        assert result.effective_context_total == 32_000
        assert result.effective_tier_base == 16_000
        assert result.model_context_window == 128_000
        assert result.budget_source == "cascade:uncapped"

    async def test_empty_series_yields_zero_counts(self) -> None:
        owner = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        series_repo.seed(_series(owner))
        service = _make_service(series_repo=series_repo)

        result = await service.get_preview(next(iter(series_repo._series)), owner)

        assert all(p.bands_total == 0 and p.estimated_tokens == 0 for p in result.previews)

    def test_service_satisfies_protocol(self) -> None:
        service = _make_service(series_repo=FakeSeriesRepository())
        assert isinstance(service, SeriesHistoryPreviewServiceProtocol)
```

> **Note on the test above:** `novel_repo=None` in `_make_service` is deliberate — `collect_series_band_data` touches only `series_repo` + `band_summary_repo`; passing `None` for the unused repo keeps the test honest about the consumed surface (the `# type: ignore` is scoped to the test). The member-novel shapes are plain `type("NovelRow", (), {...})()` objects — `FakeSeriesRepository.list_novels` runs `NovelRow.model_validate(n)` over them and `NovelRow` carries `extra="allow", from_attributes=True`, so attribute shapes validate.

- [ ] **Step 2: Write the failing provider test**

In `tests/unit/api/series/test_series_history_provider.py`, append:

```python
class TestCollectSeriesBandData:
    """C1: series-keyed band-data fetch with next-band semantics (ALL
    positioned members are prior bands — no position filtering, unlike
    assemble_series_history which filters below the current novel)."""

    async def test_returns_all_positioned_members_with_summaries(self) -> None:
        series_id = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        novel_row = _novel_row(series_id=series_id, position=1, title="Band 1")
        unpositioned = _novel_row(series_id=series_id, position=None, title="Draft")
        series_repo.seed(_series(series_id), novels=[novel_row, unpositioned])
        band_repo = FakeBandSummaryRepository()
        band_repo.seed(
            BandSummary(
                novel_id=novel_row.id,
                full_summary="Full summary.",
                short_summary="Short.",
            )
        )
        provider = SeriesHistoryProvider(
            novel_repo=FakeNovelRepository(),
            series_repo=series_repo,
            band_summary_repo=band_repo,
        )

        result = await provider.collect_series_band_data(series_id)

        assert len(result) == 1  # unpositioned member excluded
        assert result[0].position == 1
        assert result[0].title == "Band 1"
        assert result[0].full_summary == "Full summary."
        assert result[0].short_summary == "Short."

    async def test_member_without_summary_row_yields_none_texts(self) -> None:
        series_id = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        member = _novel_row(series_id=series_id, position=2)
        series_repo.seed(_series(series_id), novels=[member])
        provider = SeriesHistoryProvider(
            novel_repo=FakeNovelRepository(),
            series_repo=series_repo,
            band_summary_repo=FakeBandSummaryRepository(),
        )

        result = await provider.collect_series_band_data(series_id)

        assert result[0].full_summary is None
        assert result[0].short_summary is None
        assert result[0].override is None
```

(The file already imports `uuid`, `BandSummary`, `SeriesHistoryProvider`, `FakeBandSummaryRepository`, `FakeNovelRepository`, `FakeSeriesRepository` and defines `_series(series_id)` / `_novel_row(*, series_id, position, title=…)` helpers — reuse them; if `_novel_row` lacks a `novel_id` kwarg in your checkout, pass `novel_id=uuid.uuid4()` explicitly. The file's existing `_novel_row` returns a `NovelRow` with an `id` attribute — the band repo is seeded with that id.)

- [ ] **Step 3: Run the tests to verify they fail**

Run: `just test-file tests/unit/api/series/test_series_history_preview_service.py tests/unit/api/series/test_series_history_provider.py`
Expected: FAIL — service tests with `ModuleNotFoundError: No module named 'narrare.series.series_history_preview_service'`; provider tests with `AttributeError: 'SeriesHistoryProvider' object has no attribute 'collect_series_band_data'`.

- [ ] **Step 4: Add the provider accessor**

In `apps/api/narrare/series/series_history_provider.py`, directly after the `assemble_series_history` method (before `resolve_kb_fetch_mode`), insert:

```python
    async def collect_series_band_data(self, series_id: uuid.UUID) -> list[BandSummaryData]:
        """Fetch band data for EVERY positioned member of a series (C1).

        Next-band semantics: unlike :meth:`assemble_series_history` (which
        keeps only positions below the current novel), this returns all
        positioned members — the Series-Workspace preview describes the
        generation of the NEXT band, for which every existing band is a
        prior band. Pure data fetch; no windowing or budgeting here (the
        caller runs the Core tier's ``preview`` over the result).
        """
        members = await self._series_repo.list_novels(series_id)
        positioned = [m for m in members if m.series_position is not None]
        return await self._collect_band_data(positioned)
```

- [ ] **Step 5: Create the service**

Create `apps/api/narrare/series/series_history_preview_service.py`:

```python
"""Series-history preview service (C1 — Context-Window Slider, design §4).

Read model behind ``GET /series/{id}/settings/context-preview``: computes
what the series-history block would contain per candidate window size,
from the series' ACTUAL band summaries against the EFFECTIVE ADR-082
budgets. Honest by construction — no fabricated estimates:

* band data comes from the real ``BandSummary`` rows (via the provider's
  ``collect_series_band_data``, next-band semantics);
* budgets come from the injected ``budgets_provider``, which the DI
  factory builds over the exact production resolution chain
  (``TokenLimitsService`` cascade → model routing →
  ``resolve_context_budgets(series_in_scope=True)``) — the same
  ``EffectiveContextBudgets`` the writing pipeline consumes, never a
  second computation path;
* the prediction itself is the Core tier's ``preview`` (same greedy fit
  as real assembly).

Model routing + cascade resolve at user level (``project_id=None``):
the next band has no novel id yet; project-level routing/cascade
overrides for a specific existing novel may differ at that novel's
generation time (documented limitation, see the SERIES-002 spec).

RULE-04: separate file — ``series/service.py`` is at its 300-line limit.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

import structlog

from narrare.series.series_history_preview_schemas import (
    SeriesHistoryPreviewEntry,
    SeriesHistoryPreviewResponse,
)
from narrare_core.context.series_history import SeriesHistoryTier
from narrare_core.shared.errors import ForbiddenError

if TYPE_CHECKING:
    import uuid
    from collections.abc import Callable

    from narrare.series.series_history_provider import SeriesHistoryProvider
    from narrare.series.contracts import SeriesRepositoryProtocol
    from narrare_core.context.contracts import EffectiveContextBudgets

logger = structlog.get_logger(__name__)

#: Window used when no SeriesSettings row exists yet (mirrors the ORM
#: default + migration 0038 server_default + provider constant).
_DEFAULT_WINDOW_SIZE: int = 3


class SeriesHistoryPreviewService:
    """Compute per-window series-history previews for the Settings tab."""

    def __init__(
        self,
        *,
        series_repo: SeriesRepositoryProtocol,
        provider: SeriesHistoryProvider,
        budgets_provider: Callable[[], EffectiveContextBudgets],
        tier: SeriesHistoryTier | None = None,
        slider_max: int = 10,
    ) -> None:
        """Initialize with injected dependencies (all I/O behind fakes-able seams).

        Args:
            series_repo: Ownership check + settings read (window default).
            provider: Band-data fetch (next-band semantics).
            budgets_provider: Zero-arg callable returning the frozen
                :class:`EffectiveContextBudgets` — built by the DI factory
                over the ADR-082 resolution chain.
            tier: Optional Core tier override (default → real).
            slider_max: Slider upper bound (design §4: 1–10). Function
                default, not a module constant, by the
                configurable-defaults checker ruling. The computed range
                extends to ``max(slider_max, current_window_size)`` so an
                API-saved value above 10 stays honestly previewable.
        """
        self._series_repo = series_repo
        self._provider = provider
        self._budgets_provider = budgets_provider
        self._tier = tier or SeriesHistoryTier()
        self._slider_max = slider_max

    async def get_preview(
        self, series_id: uuid.UUID, user_id: uuid.UUID
    ) -> SeriesHistoryPreviewResponse:
        """Compute previews for window sizes 1..max(slider, saved).

        Raises:
            ForbiddenError: If the series is missing or not owned by
                ``user_id`` (anti-enumeration — 403, never 404).
        """
        series = await self._series_repo.get(series_id)
        if series is None or series.user_id != user_id:
            raise ForbiddenError("You do not have access to this series")

        settings = await self._series_repo.get_settings(series_id)
        if settings is None:
            current = _DEFAULT_WINDOW_SIZE
        else:
            value = getattr(settings, "context_window_size", _DEFAULT_WINDOW_SIZE)
            current = int(value) if value is not None else _DEFAULT_WINDOW_SIZE

        bands = await self._provider.collect_series_band_data(series_id)
        budgets = self._budgets_provider()

        top = max(self._slider_max, current)
        previews = [
            SeriesHistoryPreviewEntry.model_validate(
                asdict(
                    await self._tier.preview(
                        bands, window_size=k, token_budget=budgets.series_history
                    )
                )
            )
            for k in range(1, top + 1)
        ]

        logger.info(
            "series_history_preview_computed",
            series_id=str(series_id),
            bands=len(bands),
            current_window=current,
            series_history_budget=budgets.series_history,
        )
        return SeriesHistoryPreviewResponse(
            series_id=series_id,
            current_window_size=current,
            effective_series_history_budget=budgets.series_history,
            effective_context_total=budgets.context_total,
            effective_tier_base=budgets.writing_tier_base,
            model_context_window=budgets.context_window,
            budget_source=budgets.source,
            previews=previews,
        )
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `just test-file tests/unit/api/series/test_series_history_preview_service.py tests/unit/api/series/test_series_history_provider.py`
Expected: PASS — all new service + provider tests green.

- [ ] **Step 7: Run the series suite for regressions**

Run: `just test-file tests/unit/api/series/`
Expected: PASS — provider untouched on the assemble path; contracts/schema tests from Task 2 green.

- [ ] **Step 8: Commit (via Platform, verbatim)**

```bash
git add apps/api/narrare/series/series_history_provider.py \
        apps/api/narrare/series/series_history_preview_service.py \
        tests/unit/api/series/test_series_history_preview_service.py \
        tests/unit/api/series/test_series_history_provider.py
```

Commit message:

```
feat(api): add SeriesHistoryPreviewService + provider band-data accessor

C1 service layer: computes the slider honesty preview from real data.

- series_history_provider.py: new public collect_series_band_data
  (series_id) — band data for EVERY positioned member, next-band
  semantics (when band N+1 is generated, all N existing bands are prior
  bands — exactly what assemble_series_history would see for that
  novel). The assemble path is untouched.
- series_history_preview_service.py: SeriesHistoryPreviewService —
  ownership check (403 anti-enumeration, mirroring SeriesService),
  window range 1..max(slider_max, saved) so API-saved values above the
  slider top stay honestly previewable, one Core tier.preview call per
  candidate window against budgets.series_history, EffectiveContextBudgets
  passed through verbatim (ceiling, total, tier base, model window,
  source). slider_max=10 is a constructor default by the
  configurable-defaults checker ruling (module literals >5 are flagged).
  Separate file: series/service.py is at its 300-line RULE-04 limit.

Tests: ownership (missing/foreign -> ForbiddenError), window range
(default 3 -> 1..10; saved 7 -> 1..10; saved 12 -> 1..12), actual
summaries flowing into counts, every entry budgeted at the effective
ceiling, budget metadata passthrough, empty series, protocol
satisfaction; provider accessor (positioned members only, missing
summary rows -> None texts).

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §4 (C1), ADR-082 Implementation Notes (C1 dependency)
```

---

### Task 4: API — router route + DI factory

**Files:**
- Modify: `apps/api/narrare/series/router.py` (+GET route, ~15 lines)
- Modify: `apps/api/narrare/series/dependencies.py` (+async factory)
- Test: `tests/unit/api/series/test_router_settings_preview.py` (new)

**Interfaces:**
- Consumes: `SeriesHistoryPreviewService.get_preview` (Task 3); `resolve_context_budgets` (`narrare.settings.token_limits.context_budgets`); `TokenLimitsService`; `get_model_routing_resolver`; `LLMIntent.WRITE`.
- Produces: `GET /api/v1/series/{series_id}/settings/context-preview -> SeriesHistoryPreviewResponse`; `get_series_history_preview_service(session, user_id) -> SeriesHistoryPreviewService` (FastAPI dependency; resolves budgets via the exact ADR-082 production chain with `series_in_scope=True`, `project_id=None`).

**Routing decision (why `project_id=None`):** the preview subject is the next band, which has no novel id. User-level routing + cascade apply (operator env + user overrides are honored); a project-level override for a specific future novel cannot exist before that novel does. Documented limitation, mirrored in the spec (Task 8).

- [ ] **Step 1: Write the failing router tests**

Create `tests/unit/api/series/test_router_settings_preview.py`:

```python
"""Router tests for GET /series/{id}/settings/context-preview (C1).

Mirrors test_router.py conventions: the conftest app/client fixtures with
DB + auth overridden; the preview service is mocked per-test via the
dependency override (service logic is covered by its own unit tests).
"""

from __future__ import annotations

import uuid
from httpx import AsyncClient
from fastapi import FastAPI, status
from unittest.mock import AsyncMock

from narrare.series.dependencies import get_series_history_preview_service
from narrare.series.series_history_preview_schemas import (
    SeriesHistoryPreviewEntry,
    SeriesHistoryPreviewResponse,
)
from narrare_core.shared.errors import ForbiddenError


def _response(series_id: uuid.UUID) -> SeriesHistoryPreviewResponse:
    return SeriesHistoryPreviewResponse(
        series_id=series_id,
        current_window_size=3,
        effective_series_history_budget=16_000,
        effective_context_total=32_000,
        effective_tier_base=16_000,
        model_context_window=128_000,
        budget_source="cascade:uncapped",
        previews=[
            SeriesHistoryPreviewEntry(
                window_size=k,
                token_budget=16_000,
                estimated_tokens=100 * k,
                bands_total=4,
                bands_full=min(k, 4),
                bands_short=max(4 - k, 0),
                bands_truncated=0,
                bands_dropped=0,
                bands_missing=0,
                budget_clipped=False,
            )
            for k in range(1, 11)
        ],
    )


def _use_preview_service(app: FastAPI, service: AsyncMock) -> None:
    app.dependency_overrides[get_series_history_preview_service] = lambda: service


class TestGetSettingsContextPreview:
    async def test_returns_200_with_preview(self, app: FastAPI, client: AsyncClient) -> None:
        series_id = uid()
        mock = AsyncMock()
        mock.get_preview.return_value = _response(series_id)
        _use_preview_service(app, mock)

        response = await client.get(f"/api/v1/series/{series_id}/settings/context-preview")

        assert response.status_code == status.HTTP_200_OK
        body = SeriesHistoryPreviewResponse.model_validate(response.json())
        assert body.series_id == series_id
        assert [p.window_size for p in body.previews] == list(range(1, 11))
        mock.get_preview.assert_awaited_once_with(series_id, uuid.UUID(TEST_USER_ID))

    async def test_missing_or_foreign_series_maps_to_403(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        mock = AsyncMock()
        mock.get_preview.side_effect = ForbiddenError("You do not have access to this series")
        _use_preview_service(app, mock)

        response = await client.get(f"/api/v1/series/{uid()}/settings/context-preview")

        assert response.status_code == status.HTTP_403_FORBIDDEN


def uid() -> uuid.UUID:
    return uuid.uuid4()


TEST_USER_ID = "00000000-0000-0000-0000-0000000000ff"
```

(`TEST_USER_ID` / `uid()` are defined at the bottom to keep the class-first reading order of this file; if the linter objects, hoist them above the class — content identical. `TEST_USER_ID` must equal the conftest fixture's authenticated user constant `00000000-0000-0000-0000-0000000000ff` so the router's `uuid.UUID(user_id)` argument matches the asserted call.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test-file tests/unit/api/series/test_router_settings_preview.py`
Expected: FAIL — `ImportError: cannot import name 'get_series_history_preview_service'` (collection error).

- [ ] **Step 3: Add the route**

In `apps/api/narrare/series/router.py`:

3a. Extend the imports — replace:

```python
from narrare.series.dependencies import get_series_service
from narrare.series.schemas import (
    SeriesCreateRequest,
    SeriesResponse,
    SeriesSettingsResponse,
    SeriesSettingsUpdateRequest,
    SeriesSummary,
    SeriesUpdateRequest,
)
from narrare.series.service import SeriesService
```

with:

```python
from narrare.series.dependencies import (
    get_series_history_preview_service,
    get_series_service,
)
from narrare.series.schemas import (
    SeriesCreateRequest,
    SeriesResponse,
    SeriesSettingsResponse,
    SeriesSettingsUpdateRequest,
    SeriesSummary,
    SeriesUpdateRequest,
)
from narrare.series.series_history_preview_schemas import SeriesHistoryPreviewResponse
from narrare.series.series_history_preview_service import SeriesHistoryPreviewService
from narrare.series.service import SeriesService
```

3b. Append at the end of the file:

```python
@router.get(
    "/{series_id}/settings/context-preview",
    response_model=SeriesHistoryPreviewResponse,
)
async def get_settings_context_preview(
    series_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: SeriesHistoryPreviewService = Depends(get_series_history_preview_service),
) -> SeriesHistoryPreviewResponse:
    """Live preview: series-history context per candidate window size (C1).

    Read-only derived view (design §4.1) — computed from the series' actual
    band summaries against the effective ADR-082 budgets. Saving stays on
    PATCH /{series_id}/settings.
    """
    return await service.get_preview(series_id, uuid.UUID(user_id))
```

- [ ] **Step 4: Add the DI factory**

In `apps/api/narrare/series/dependencies.py`:

4a. Extend the `TYPE_CHECKING` block — add to the existing `if TYPE_CHECKING:` section:

```python
    from narrare_core.context.contracts import EffectiveContextBudgets
```

(Everything else the factory needs is already imported at module level — `SessionDep`, `get_current_user_id`, `Depends`, `UUID`, `get_model_routing_resolver`, `LLMIntent`, `NovelRepository`, `SeriesRepository`, `BandSummaryRepository` — all present for the existing factories. The closure's return annotation is a string under `from __future__ import annotations`, so the TYPE_CHECKING import satisfies pyright. The heavy imports stay lazy inside the function body, matching `build_band_summary_service` style.)

4b. Append at the end of the file:

```python
async def get_series_history_preview_service(
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
) -> SeriesHistoryPreviewService:
    """Request-scoped SeriesHistoryPreviewService (C1 slider preview).

    Resolves the effective budgets through the exact ADR-082 production
    chain so the preview can never drift from generation-time values:
    WRITE-intent model routing → TokenLimitsService cascade →
    resolve_context_budgets(series_in_scope=True). ``project_id=None``
    because the preview subject is the NEXT band (no novel id yet) —
    user/operator-level routing and cascade overrides apply; the
    project-level caveat is documented in the SERIES-002 spec.
    """
    from narrare._app.config import get_settings
    from narrare.settings.token_limits.context_budgets import resolve_context_budgets
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService
    from narrare.series.series_history_preview_service import SeriesHistoryPreviewService
    from narrare.series.series_history_provider import SeriesHistoryProvider

    resolver = get_model_routing_resolver(session)
    resolved = await resolver.resolve(LLMIntent.WRITE, UUID(user_id), None)

    token_limits_service = TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=get_settings(),
    )
    limits = await token_limits_service.get_resolved_limits(
        user_id=user_id,
        project_id=None,
    )

    def budgets_provider() -> EffectiveContextBudgets:
        return resolve_context_budgets(
            limits=limits,
            config=resolved.config,
            series_in_scope=True,
        )

    series_repo = SeriesRepository(session)
    provider = SeriesHistoryProvider(
        novel_repo=NovelRepository(session),
        series_repo=series_repo,
        band_summary_repo=BandSummaryRepository(session),
    )
    return SeriesHistoryPreviewService(
        series_repo=series_repo,
        provider=provider,
        budgets_provider=budgets_provider,
    )
```

- [ ] **Step 5: Run the router tests to verify they pass**

Run: `just test-file tests/unit/api/series/test_router_settings_preview.py`
Expected: PASS — 2 tests (200 shape + 403 mapping).

- [ ] **Step 6: Run the full series suite + architecture checker**

Run: `just test-file tests/unit/api/series/ && just check-architecture`
Expected: PASS both (router.py ~116/150 lines; dependencies.py ~235/400).

- [ ] **Step 7: Commit (via Platform, verbatim)**

```bash
git add apps/api/narrare/series/router.py \
        apps/api/narrare/series/dependencies.py \
        tests/unit/api/series/test_router_settings_preview.py
```

Commit message:

```
feat(api): expose GET /series/{id}/settings/context-preview

C1 HTTP surface (design §4.1: preview read; PATCH stays on the existing
settings endpoint — no new router file):

- router.py: one thin GET route on the existing series router,
  response_model=SeriesHistoryPreviewResponse, delegating immediately
  to the service (RULE-06; ForbiddenError -> 403 via the global
  NarrareError handler, anti-enumeration).
- dependencies.py: get_series_history_preview_service — resolves the
  effective budgets through the exact ADR-082 production chain
  (WRITE-intent routing -> TokenLimitsService cascade ->
  resolve_context_budgets(series_in_scope=True)) so the preview can
  never drift from generation-time values. project_id=None: the preview
  subject is the NEXT band, which has no novel id yet — user/operator
  overrides apply, the project-level caveat is documented in the spec.

Tests: 200 round trip (shape + window range 1..10 + service called with
the authenticated user id), missing/foreign series -> 403.

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §4 (C1), ADR-082 Implementation Notes (C1 dependency)
```

---

### Task 5: Web — types + API client + query key

**Files:**
- Modify: `packages/web/types/series.ts` (+2 interfaces after `SeriesSettings`)
- Modify: `packages/web/lib/api/series.ts` (+1 client function + type import)
- Modify: `packages/web/lib/hooks/seriesKeys.ts` (+1 key + doc line)

**Interfaces:**
- Consumes: the Task 4 response shape (snake_case preserved to match the Pydantic SSOT — RULE-17 parity).
- Produces (verbatim for Tasks 6/7):
  - `SeriesHistoryPreviewEntry`, `SeriesHistoryPreviewResponse` (exported from `@/types`).
  - `seriesApi.getSettingsContextPreview(seriesId: string): Promise<SeriesHistoryPreviewResponse>`.
  - `seriesKeys.settingsPreview(seriesId: string): readonly ["series", string, "settingsPreview"]`.

- [ ] **Step 1: Add the types**

In `packages/web/types/series.ts`, directly after the `SeriesSettings` interface (before the `// --- Band Summary types (Spec 2 Task 8) ---` comment), insert:

```ts
// --- Series-history context preview (C1 — Context-Window Slider) -------------
//
// Mirror apps/api/narrare/series/series_history_preview_schemas.py
// (SeriesHistoryPreviewEntry / SeriesHistoryPreviewResponse, RULE-17 parity).
// snake_case preserved to match the Pydantic SSOT.

/** One candidate window size's prediction (mirrors the Core preview). */
export interface SeriesHistoryPreviewEntry {
  window_size: number;
  /** Effective series-history ceiling this prediction was computed against. */
  token_budget: number;
  estimated_tokens: number;
  bands_total: number;
  bands_full: number;
  bands_short: number;
  bands_truncated: number;
  bands_dropped: number;
  bands_missing: number;
  budget_clipped: boolean;
}

/** GET /series/{id}/settings/context-preview response (C1 live preview). */
export interface SeriesHistoryPreviewResponse {
  series_id: string;
  current_window_size: number;
  /** EffectiveContextBudgets verbatim (ADR-082 — effective, not configured). */
  effective_series_history_budget: number;
  effective_context_total: number;
  effective_tier_base: number;
  /** null = model window unknown (uncapped, RULE-11). */
  model_context_window: number | null;
  budget_source: string;
  previews: SeriesHistoryPreviewEntry[];
}
```

- [ ] **Step 2: Add the API client function**

In `packages/web/lib/api/series.ts`:

2a. In the `import type { ... }` block, add after the `SeriesSettings,` entry:

```ts
  SeriesHistoryPreviewResponse,
```

(isort-style: keep the block alphabetical — it sorts between `SeriesSettings,` and `SeriesSettingsUpdate,`.)

2b. Directly after the `updateSettings` entry (before the `// --- Series-Canon KB CRUD (Slice 5) ---` comment), insert:

```ts
  /** GET /series/{id}/settings/context-preview — live slider preview (C1). */
  getSettingsContextPreview: (seriesId: string) =>
    fetchApi<SeriesHistoryPreviewResponse>(
      `/series/${seriesId}/settings/context-preview`,
    ),
```

- [ ] **Step 3: Add the query key**

In `packages/web/lib/hooks/seriesKeys.ts`:

3a. Extend the header comment's key-shape list — after the line
`["series", seriesId, "settings"]    — series settings`, add:

```ts
 *   ["series", seriesId, "settingsPreview"] — context-window preview (C1)
```

3b. Directly after the `settings:` entry, add:

```ts
  /** Context-window slider preview (C1) — invalidated on settings PATCH. */
  settingsPreview: (seriesId: string) =>
    [...seriesKeys.detail(seriesId), "settingsPreview"] as const,
```

- [ ] **Step 4: Verify the data layer compiles and nothing regresses**

Run: `cd packages/web && pnpm type-check && pnpm lint:check && pnpm test components/series`
Expected: PASS — types compile; the series component tests are untouched and green (the new plumbing is not yet consumed).

- [ ] **Step 5: Commit (via Platform, verbatim)**

```bash
git add packages/web/types/series.ts \
        packages/web/lib/api/series.ts \
        packages/web/lib/hooks/seriesKeys.ts
```

Commit message:

```
feat(web): types + API client + query key for the context preview

C1 frontend data plumbing (consumed by Tasks 6-7):
- types/series.ts: SeriesHistoryPreviewEntry + SeriesHistoryPreviewResponse
  mirroring series_history_preview_schemas.py (RULE-17 parity, snake_case
  preserved); budget metadata fields carry EffectiveContextBudgets
  verbatim, model_context_window nullable for the RULE-11 unknown case.
- lib/api/series.ts: getSettingsContextPreview — GET
  /series/{id}/settings/context-preview through the standard fetchApi.
- lib/hooks/seriesKeys.ts: settingsPreview key under the series detail
  neighborhood (invalidated together with settings on PATCH).

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §4 (C1)
```

---

### Task 6: i18n — `series.settings.contextPreview.*` (en/de/fr)

**Files:**
- Modify: `packages/i18n/messages/en/studio.json`
- Modify: `packages/i18n/messages/de/studio.json`
- Modify: `packages/i18n/messages/fr/studio.json`

**Interfaces:**
- Produces (verbatim for Task 7): keys `series.settings.contextPreview.{bandsLine, tokenLine, truncatedNote, droppedNote, missingNote, clippedWarning, budgetLine, windowUnknown, savedOutOfRange, loading, error}` in all three locales. Copy implements the design §4.1 pattern ("3 Bände voll — ca. 440 / 16 000 Tokens; größeres Window wird vom Budget gekürzt") with ICU plurals; numbers format per locale via `{value, number}`.

- [ ] **Step 1: Insert the `contextPreview` block into each locale**

In each of the three files, `series.settings.contextWindow` is the LAST key of the `settings` object (immediately followed by the `}` that closes `settings` and the `"join": {` block). Insert a comma after the `contextWindow` object's closing `}` and add the following block at the same indentation level (6 spaces for the key, 8 for values):

`en/studio.json`:

```json
      "contextPreview": {
        "bandsLine": "{full, plural, =0 {No bands in full} one {# band in full} other {# bands in full}} · {short, plural, =0 {no short summaries} one {# short summary} other {# short summaries}}",
        "tokenLine": "approx. {tokens, number} / {budget, number} tokens",
        "truncatedNote": "{count, plural, one {# band is truncated} other {# bands are truncated}}",
        "droppedNote": "{count, plural, one {# older band is dropped} other {# older bands are dropped}}",
        "missingNote": "{count, plural, one {# band has no summary yet} other {# bands have no summary yet}}",
        "clippedWarning": "A larger window would be clipped by the token budget.",
        "budgetLine": "Series history may use up to {seriesBudget, number} of {totalBudget, number} context tokens; the remaining {tierBase, number} are reserved for the current band's context.",
        "windowUnknown": "Model context window unknown — the budget is shown uncapped.",
        "savedOutOfRange": "Saved value {value, number} is outside the slider range (1–{max, number}). Moving the slider replaces it.",
        "loading": "Computing preview…",
        "error": "Preview unavailable."
      }
```

`de/studio.json`:

```json
      "contextPreview": {
        "bandsLine": "{full, plural, =0 {Keine Bände voll} one {# Band voll} other {# Bände voll}} · {short, plural, =0 {keine Kurzzusammenfassungen} one {# Kurzzusammenfassung} other {# Kurzzusammenfassungen}}",
        "tokenLine": "ca. {tokens, number} / {budget, number} Tokens",
        "truncatedNote": "{count, plural, one {# Band wird gekürzt} other {# Bänder werden gekürzt}}",
        "droppedNote": "{count, plural, one {# älteres Band fällt weg} other {# ältere Bände fallen weg}}",
        "missingNote": "{count, plural, one {# Band hat noch keine Zusammenfassung} other {# Bänder haben noch keine Zusammenfassung}}",
        "clippedWarning": "Ein größeres Window wird vom Token-Budget gekürzt.",
        "budgetLine": "Die Reihen-Historie darf bis zu {seriesBudget, number} von {totalBudget, number} Kontext-Tokens nutzen; die übrigen {tierBase, number} bleiben für den Kontext des aktuellen Bands reserviert.",
        "windowUnknown": "Modell-Kontextfenster unbekannt — das Budget wird ungekappt angezeigt.",
        "savedOutOfRange": "Gespeicherter Wert {value, number} liegt außerhalb des Slider-Bereichs (1–{max, number}). Das Bewegen des Sliders ersetzt ihn.",
        "loading": "Vorschau wird berechnet…",
        "error": "Vorschau nicht verfügbar."
      }
```

`fr/studio.json`:

```json
      "contextPreview": {
        "bandsLine": "{full, plural, =0 {Aucun tome complet} one {# tome complet} other {# tomes complets}} · {short, plural, =0 {aucun résumé court} one {# résumé court} other {# résumés courts}}",
        "tokenLine": "env. {tokens, number} / {budget, number} tokens",
        "truncatedNote": "{count, plural, one {# tome est tronqué} other {# tomes sont tronqués}}",
        "droppedNote": "{count, plural, one {# tome plus ancien est omis} other {# tomes plus anciens sont omis}}",
        "missingNote": "{count, plural, one {# tome n'a pas encore de résumé} other {# tomes n'ont pas encore de résumé}}",
        "clippedWarning": "Une fenêtre plus grande serait tronquée par le budget de tokens.",
        "budgetLine": "L'historique de la série peut utiliser jusqu'à {seriesBudget, number} des {totalBudget, number} tokens de contexte ; les {tierBase, number} restants sont réservés au contexte du tome actuel.",
        "windowUnknown": "Fenêtre de contexte du modèle inconnue — le budget est affiché sans plafonnement.",
        "savedOutOfRange": "La valeur enregistrée {value, number} est hors de la plage du curseur (1–{max, number}). Déplacer le curseur la remplace.",
        "loading": "Calcul de l'aperçu…",
        "error": "Aperçu indisponible."
      }
```

- [ ] **Step 2: Verify JSON validity + three-locale key parity**

Run:

```bash
python3 -c "
import json
expected = {'bandsLine','tokenLine','truncatedNote','droppedNote','missingNote','clippedWarning','budgetLine','windowUnknown','savedOutOfRange','loading','error'}
for loc in ('en','de','fr'):
    d = json.load(open(f'packages/i18n/messages/{loc}/studio.json'))
    keys = set(d['series']['settings']['contextPreview'])
    assert keys == expected, (loc, keys ^ expected)
print('parity OK: 3 locales x 11 keys')
"
```

Expected: `parity OK: 3 locales x 11 keys`.

- [ ] **Step 3: Commit (via Platform, verbatim)**

```bash
git add packages/i18n/messages/en/studio.json \
        packages/i18n/messages/de/studio.json \
        packages/i18n/messages/fr/studio.json
```

Commit message:

```
feat(i18n): context-preview copy for the C1 slider (en/de/fr)

series.settings.contextPreview.* — 11 keys x 3 locales, following the
existing series.settings.contextWindow conventions:

- bandsLine + tokenLine implement the design §4.1 pattern
  ("3 Bände voll — ca. 440 / 16 000 Tokens") with ICU plurals and
  locale-aware number formatting ({value, number}).
- clippedWarning surfaces the honesty requirement: a larger window
  being clipped by the token budget.
- budgetLine states the ADR-082 series/standalone tier-base semantics
  from the series perspective: the series-history ceiling carved out
  of the context total, the remainder reserved for the current band.
- windowUnknown covers the RULE-11 uncapped case; savedOutOfRange
  handles API-saved values above the 1-10 slider range.

Parity gate: python key-set comparison en/de/fr (11 keys each).

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §4 (C1), ADR-082 (tier-base budgetLine copy)
```

---

### Task 7a: Web — preview hook + presentational component

**Files:**
- Modify: `packages/web/lib/hooks/useSeries.ts` (+`useSeriesHistoryPreview`; extend `useUpdateSeriesSettings` invalidation)
- Create: `packages/web/components/series/SeriesContextPreview.tsx`
- Test: `packages/web/components/series/__tests__/SeriesContextPreview.test.tsx` (new)

**Interfaces:**
- Consumes: `seriesApi.getSettingsContextPreview`, `seriesKeys.settingsPreview` (Task 5); `series.settings.contextPreview.*` keys (Task 6).
- Produces (verbatim for Task 7b): `useSeriesHistoryPreview(seriesId: string)` (query); `SeriesContextPreview({ entry: SeriesHistoryPreviewEntry; meta: SeriesHistoryPreviewResponse })` with testids `series-context-preview` (+ `data-window`), `series-context-preview-line`, `-truncated`, `-dropped`, `-missing`, `-clipped`, `-budget`, `-window-unknown`.

- [ ] **Step 1: Write the failing component tests**

Create `packages/web/components/series/__tests__/SeriesContextPreview.test.tsx`:

```tsx
/**
 * SeriesContextPreview component tests (C1 — honesty preview display).
 *
 * Pure presentational: renders the entry's band classification + token
 * estimate and the budget metadata. Conventions mirror
 * SeriesContextWindowField.test.tsx: the centralized setupTests mock
 * returns i18n KEY STRINGS verbatim, so assertions check for keys.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SeriesHistoryPreviewEntry, SeriesHistoryPreviewResponse } from "@/types";
import { SeriesContextPreview } from "@/components/series/SeriesContextPreview";

const entry: SeriesHistoryPreviewEntry = {
  window_size: 3,
  token_budget: 16_000,
  estimated_tokens: 440,
  bands_total: 5,
  bands_full: 3,
  bands_short: 2,
  bands_truncated: 0,
  bands_dropped: 0,
  bands_missing: 0,
  budget_clipped: false,
};

const meta: SeriesHistoryPreviewResponse = {
  series_id: "series-1",
  current_window_size: 3,
  effective_series_history_budget: 16_000,
  effective_context_total: 32_000,
  effective_tier_base: 16_000,
  model_context_window: 128_000,
  budget_source: "cascade:uncapped",
  previews: [],
};

describe("SeriesContextPreview", () => {
  it("renders the bands + tokens line for the entry's window", () => {
    render(<SeriesContextPreview entry={entry} meta={meta} />);
    expect(screen.getByTestId("series-context-preview").getAttribute("data-window")).toBe("3");
    expect(screen.getByTestId("series-context-preview-line").textContent).toContain(
      "series.settings.contextPreview.bandsLine",
    );
    expect(screen.getByTestId("series-context-preview-line").textContent).toContain(
      "series.settings.contextPreview.tokenLine",
    );
  });

  it("always renders the budget line (tier-base semantics)", () => {
    render(<SeriesContextPreview entry={entry} meta={meta} />);
    expect(screen.getByTestId("series-context-preview-budget")).toBeDefined();
  });

  it("hides conditional notes when counts are zero and not clipped", () => {
    render(<SeriesContextPreview entry={entry} meta={meta} />);
    expect(screen.queryByTestId("series-context-preview-truncated")).toBeNull();
    expect(screen.queryByTestId("series-context-preview-dropped")).toBeNull();
    expect(screen.queryByTestId("series-context-preview-missing")).toBeNull();
    expect(screen.queryByTestId("series-context-preview-clipped")).toBeNull();
    expect(screen.queryByTestId("series-context-preview-window-unknown")).toBeNull();
  });

  it("shows truncation/drop/missing/clipped notes when present", () => {
    const clipped: SeriesHistoryPreviewEntry = {
      ...entry,
      bands_truncated: 1,
      bands_dropped: 2,
      bands_missing: 1,
      budget_clipped: true,
    };
    render(<SeriesContextPreview entry={clipped} meta={meta} />);
    expect(screen.getByTestId("series-context-preview-truncated")).toBeDefined();
    expect(screen.getByTestId("series-context-preview-dropped")).toBeDefined();
    expect(screen.getByTestId("series-context-preview-missing")).toBeDefined();
    expect(screen.getByTestId("series-context-preview-clipped")).toBeDefined();
  });

  it("shows the window-unknown note only when the model window is null", () => {
    const unknown: SeriesHistoryPreviewResponse = { ...meta, model_context_window: null };
    render(<SeriesContextPreview entry={entry} meta={unknown} />);
    expect(screen.getByTestId("series-context-preview-window-unknown")).toBeDefined();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd packages/web && pnpm test components/series/__tests__/SeriesContextPreview.test.tsx`
Expected: FAIL — `Cannot find module '@/components/series/SeriesContextPreview'`.

- [ ] **Step 3: Add the hook + invalidation**

In `packages/web/lib/hooks/useSeries.ts`:

3a. Append at the end of the file:

```ts
// --- Series-history context preview (C1 — Context-Window Slider) ---

/** GET /api/v1/series/{id}/settings/context-preview — live slider preview. */
export function useSeriesHistoryPreview(seriesId: string) {
  return useQuery({
    queryKey: seriesKeys.settingsPreview(seriesId),
    queryFn: () => seriesApi.getSettingsContextPreview(seriesId),
    enabled: !!seriesId,
  });
}
```

3b. In `useUpdateSeriesSettings`, extend the `onSuccess` invalidation — replace:

```ts
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: seriesKeys.settings(seriesId) });
    },
```

with:

```ts
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: seriesKeys.settings(seriesId) });
      // C1: the saved window change may extend the preview's computed
      // range (1..max(10, saved)) — refetch alongside the settings.
      void queryClient.invalidateQueries({ queryKey: seriesKeys.settingsPreview(seriesId) });
    },
```

- [ ] **Step 4: Create the component**

Create `packages/web/components/series/SeriesContextPreview.tsx`:

```tsx
"use client";

/**
 * SeriesContextPreview — live honesty preview for the context-window slider
 * (C1, design §4.1): renders what the series-history block would contain at
 * the selected window size — band classification (full / short / truncated /
 * dropped / missing) and the estimated token total against the EFFECTIVE
 * series-history budget (ADR-082 EffectiveContextBudgets, computed
 * server-side from the series' actual summaries; never fabricated
 * client-side). Pure presentational; no data fetching.
 */
import { useTranslations } from "next-intl";
import type { SeriesHistoryPreviewEntry, SeriesHistoryPreviewResponse } from "@/types";

interface SeriesContextPreviewProps {
  readonly entry: SeriesHistoryPreviewEntry;
  readonly meta: SeriesHistoryPreviewResponse;
}

export function SeriesContextPreview({ entry, meta }: SeriesContextPreviewProps) {
  const t = useTranslations("studio");

  return (
    <div
      data-testid="series-context-preview"
      data-window={entry.window_size}
      className="space-y-1 rounded-md border border-border bg-card p-3 text-xs text-muted-foreground"
    >
      <p data-testid="series-context-preview-line" className="text-sm text-foreground">
        {t("series.settings.contextPreview.bandsLine", {
          full: entry.bands_full,
          short: entry.bands_short,
        })}
        {" — "}
        {t("series.settings.contextPreview.tokenLine", {
          tokens: entry.estimated_tokens,
          budget: entry.token_budget,
        })}
      </p>
      {entry.bands_truncated > 0 ? (
        <p data-testid="series-context-preview-truncated">
          {t("series.settings.contextPreview.truncatedNote", {
            count: entry.bands_truncated,
          })}
        </p>
      ) : null}
      {entry.bands_dropped > 0 ? (
        <p data-testid="series-context-preview-dropped">
          {t("series.settings.contextPreview.droppedNote", { count: entry.bands_dropped })}
        </p>
      ) : null}
      {entry.bands_missing > 0 ? (
        <p data-testid="series-context-preview-missing">
          {t("series.settings.contextPreview.missingNote", { count: entry.bands_missing })}
        </p>
      ) : null}
      {entry.budget_clipped ? (
        <p data-testid="series-context-preview-clipped" className="text-amber-600">
          {t("series.settings.contextPreview.clippedWarning")}
        </p>
      ) : null}
      <p data-testid="series-context-preview-budget">
        {t("series.settings.contextPreview.budgetLine", {
          seriesBudget: meta.effective_series_history_budget,
          totalBudget: meta.effective_context_total,
          tierBase: meta.effective_tier_base,
        })}
      </p>
      {meta.model_context_window === null ? (
        <p data-testid="series-context-preview-window-unknown">
          {t("series.settings.contextPreview.windowUnknown")}
        </p>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd packages/web && pnpm test components/series/__tests__/SeriesContextPreview.test.tsx`
Expected: PASS — 5 tests.

- [ ] **Step 6: Commit (via Platform, verbatim)**

```bash
git add packages/web/lib/hooks/useSeries.ts \
        packages/web/components/series/SeriesContextPreview.tsx \
        packages/web/components/series/__tests__/SeriesContextPreview.test.tsx
```

Commit message:

```
feat(web): useSeriesHistoryPreview hook + SeriesContextPreview component

C1 preview consumption (design §4.1 honesty requirements):
- useSeries.ts: useSeriesHistoryPreview (query under the settingsPreview
  key); useUpdateSeriesSettings now also invalidates the preview — a
  saved window change may extend the computed range 1..max(10, saved).
- SeriesContextPreview.tsx: pure presentational renderer of one preview
  entry + budget metadata — bands/tokens line (design pattern "3 Bände
  voll — ca. 440 / 16 000 Tokens"), conditional truncated/dropped/
  missing notes, amber budget-clipping warning, the ADR-082 tier-base
  budget line, and the RULE-11 window-unknown note. All copy via
  series.settings.contextPreview.* (Task 6 keys); no client-side
  computation of budgets or fits.

Tests: line rendering + data-window pin, budget line always present,
conditional notes shown/hidden, window-unknown only when null.

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §4 (C1), ADR-082 (budget metadata rendering)
```

---

### Task 7b: Web — slider rewrite of `SeriesContextWindowField`

**Files:**
- Modify: `packages/web/components/series/SeriesContextWindowField.tsx` (full rewrite: number input → 1–10 slider + preview)
- Test: `packages/web/components/series/__tests__/SeriesContextWindowField.test.tsx` (rewrite), `packages/web/components/series/__tests__/SeriesSettings.test.tsx` (extend the hook mock)

**Interfaces:**
- Consumes: `useSeriesSettings` / `useUpdateSeriesSettings` / `useSeriesHistoryPreview` (existing + Task 7a); `SeriesContextPreview` (Task 7a); `series.settings.contextWindow.*` + `series.settings.contextPreview.*` keys; `SeriesField`.
- Produces: the C1 user-facing surface — slider testids `series-context-window-slider` / `-value` / `-save` / `-loading` / `-error` / `-out-of-range` / `series-context-preview-loading` / `-error` (preview states), delegating preview rendering to `SeriesContextPreview`.

**Behavior specification (binding for the implementer):**
- Slider: native `<input type="range">` with `min=1 max=10 step=1`, `accent-foreground` class + aria-label (the `ContextBudget.tsx` slider pattern), aria-describedby (carried over from the current `SeriesContextWindowField`), and a `tabular-nums` value display.
- `draft` local state re-syncs from server data only while clean (dirty guard, mirroring `SeriesMetadataForm`); initial draft = saved value (even above 10 — the preview range covers it). `dirty` clears only when the refetched settings confirm the draft and no PATCH is in flight — never in the PATCH `onSuccess`, where still-stale settings would run the re-sync effect and flash the old slider position.
- Slider interaction clamps to [1, 10] and marks dirty; the Save button appears only while the draft differs from the saved value (PATCH via `useUpdateSeriesSettings`, unchanged endpoint); sliding back to the saved value (or a no-change save) collapses dirty without a request.
- Saved value > 10 (API/MCP-settable up to 50): honest notice (`savedOutOfRange`) + the preview still renders the saved value's entry (server extends the range); the next slider save replaces it.
- Preview query states render `loading` / `error` lines (slider remains usable — the preview is an enhancement, not a gate).

- [ ] **Step 1: Rewrite the field tests (failing first)**

Replace the entire content of `packages/web/components/series/__tests__/SeriesContextWindowField.test.tsx` with:

```tsx
/**
 * SeriesContextWindowField component tests (C1 — slider + live preview).
 *
 * The field renders a 1-10 slider (design §4.1) bound to the saved
 * context_window_size, a live honesty preview from
 * useSeriesHistoryPreview, and saves via PATCH /series/{id}/settings.
 * Conventions: the centralized setupTests mock returns i18n KEY STRINGS
 * verbatim, so assertions check for keys; hooks mocked per-file.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SeriesHistoryPreviewResponse, SeriesSettings } from "@/types";

// --- Per-file mutable mock state (hoisted) -----------------------------------
const mock = vi.hoisted(() => ({
  result: {
    data: undefined as SeriesSettings | undefined,
    isLoading: false,
    isError: false,
    error: null as unknown,
  },
  update: vi.fn(),
  updatePending: false,
  updateError: false,
  preview: {
    data: undefined as SeriesHistoryPreviewResponse | undefined,
    isLoading: false,
    isError: false,
    error: null as unknown,
  },
}));

vi.mock("@/lib/hooks/useSeries", () => ({
  useSeriesSettings: () => mock.result,
  useUpdateSeriesSettings: () => ({
    mutate: (...args: unknown[]) => mock.update(...args),
    isPending: mock.updatePending,
    isError: mock.updateError,
  }),
  useSeriesHistoryPreview: () => mock.preview,
}));

import { SeriesContextWindowField } from "@/components/series/SeriesContextWindowField";

const settingsDefault: SeriesSettings = {
  series_id: "series-1",
  author_voice: null,
  context_window_size: 3,
};

function makePreview(current: number): SeriesHistoryPreviewResponse {
  const top = Math.max(10, current);
  return {
    series_id: "series-1",
    current_window_size: current,
    effective_series_history_budget: 16_000,
    effective_context_total: 32_000,
    effective_tier_base: 16_000,
    model_context_window: 128_000,
    budget_source: "cascade:uncapped",
    previews: Array.from({ length: top }, (_, i) => ({
      window_size: i + 1,
      token_budget: 16_000,
      estimated_tokens: 100 * (i + 1),
      bands_total: 5,
      bands_full: Math.min(i + 1, 5),
      bands_short: Math.max(5 - (i + 1), 0),
      bands_truncated: 0,
      bands_dropped: 0,
      bands_missing: 0,
      budget_clipped: i + 1 >= 5,
    })),
  };
}

function resetResult(): void {
  mock.result = { data: settingsDefault, isLoading: false, isError: false, error: null };
  mock.update = vi.fn();
  mock.updatePending = false;
  mock.updateError = false;
  mock.preview = { data: makePreview(3), isLoading: false, isError: false, error: null };
}

describe("SeriesContextWindowField", () => {
  beforeEach(() => {
    resetResult();
  });

  it("shows a loading state while settings are loading", () => {
    mock.result = { data: undefined, isLoading: true, isError: false, error: null };
    render(<SeriesContextWindowField seriesId="series-1" />);
    expect(screen.getByTestId("series-context-window-loading")).toBeDefined();
  });

  it("shows an error state when settings fail to load", () => {
    mock.result = { data: undefined, isLoading: false, isError: true, error: new Error("x") };
    render(<SeriesContextWindowField seriesId="series-1" />);
    expect(screen.getByTestId("series-context-window-error")).toBeDefined();
  });

  it("renders a range slider bounded 1-10 with the saved value", () => {
    render(<SeriesContextWindowField seriesId="series-1" />);
    const slider = screen.getByTestId("series-context-window-slider") as HTMLInputElement;
    expect(slider.type).toBe("range");
    expect(slider.min).toBe("1");
    expect(slider.max).toBe("10");
    expect(slider.value).toBe("3");
    expect(screen.getByTestId("series-context-window-value").textContent).toBe("3");
  });

  it("renders the live preview for the current window", () => {
    render(<SeriesContextWindowField seriesId="series-1" />);
    expect(screen.getByTestId("series-context-preview").getAttribute("data-window")).toBe("3");
  });

  it("switches the preview when the slider moves (no refetch needed)", () => {
    render(<SeriesContextWindowField seriesId="series-1" />);

    fireEvent.change(screen.getByTestId("series-context-window-slider"), {
      target: { value: "7" },
    });

    expect(screen.getByTestId("series-context-preview").getAttribute("data-window")).toBe("7");
    expect(screen.getByTestId("series-context-window-value").textContent).toBe("7");
    expect(mock.update).not.toHaveBeenCalled();
  });

  it("shows Save only after a change and PATCHes the slider value", async () => {
    const user = userEvent.setup();
    render(<SeriesContextWindowField seriesId="series-1" />);

    expect(screen.queryByTestId("series-context-window-save")).toBeNull();

    fireEvent.change(screen.getByTestId("series-context-window-slider"), {
      target: { value: "7" },
    });

    const saveBtn = await waitFor(() => screen.getByTestId("series-context-window-save"));
    await user.click(saveBtn);

    expect(mock.update).toHaveBeenCalled();
    expect(mock.update.mock.calls[0][0]).toEqual({ context_window_size: 7 });
  });

  it("renders the help text describing what the window controls", () => {
    render(<SeriesContextWindowField seriesId="series-1" />);
    expect(screen.getByText("series.settings.contextWindow.help")).toBeDefined();
  });

  it("shows a dedicated loading line while the preview loads (slider usable)", () => {
    mock.preview = { data: undefined, isLoading: true, isError: false, error: null };
    render(<SeriesContextWindowField seriesId="series-1" />);
    expect(screen.getByTestId("series-context-preview-loading")).toBeDefined();
    expect(screen.getByTestId("series-context-window-slider")).toBeDefined();
  });

  it("shows a dedicated error line when the preview fails (slider usable)", () => {
    mock.preview = { data: undefined, isLoading: false, isError: true, error: new Error("x") };
    render(<SeriesContextWindowField seriesId="series-1" />);
    expect(screen.getByTestId("series-context-preview-error")).toBeDefined();
    expect(screen.getByTestId("series-context-window-slider")).toBeDefined();
  });

  it("handles a saved value above the slider range honestly", () => {
    mock.result = {
      data: { ...settingsDefault, context_window_size: 12 },
      isLoading: false,
      isError: false,
      error: null,
    };
    mock.preview = { data: makePreview(12), isLoading: false, isError: false, error: null };

    render(<SeriesContextWindowField seriesId="series-1" />);

    expect(screen.getByTestId("series-context-window-out-of-range")).toBeDefined();
    expect(screen.getByTestId("series-context-window-value").textContent).toBe("12");
    // The extended server range covers the saved value's preview.
    expect(screen.getByTestId("series-context-preview").getAttribute("data-window")).toBe("12");
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd packages/web && pnpm test components/series/__tests__/SeriesContextWindowField.test.tsx`
Expected: FAIL — `series-context-window-slider` testid not found (the component still renders the number input; `useSeriesHistoryPreview` is not part of its mock surface in the OLD component but IS in the new test's mock — the component fails to find the slider).

- [ ] **Step 3: Rewrite the component**

Replace the entire content of `packages/web/components/series/SeriesContextWindowField.tsx` with:

```tsx
"use client";

/**
 * SeriesContextWindowField — slider editor for the Series recency-window
 * setting (SERIES-002; C1 — Context-Window Slider, design §4 2026-08-14).
 *
 * Replaces the original number input [1, 50] with a 1-10 slider plus a
 * live preview (SeriesContextPreview) computed server-side from the
 * series' ACTUAL band summaries against the EFFECTIVE post-C5/ADR-082
 * budgets — the slider alone would be a lie by omission: the token budget
 * silently clips oversized windows (design §4.2). The original
 * input-choice rationale (number input for precision) was superseded by
 * the approved C1 design; the API bound stays [1, 50] (superset,
 * MCP/CLI-settable) — a saved value outside 1-10 is shown honestly via a
 * notice + the extended preview range and is replaced on the next save.
 *
 * Persists via PATCH /series/{id}/settings (existing endpoint, design
 * §4.1). Owns its local state, dirty-gated Save, and loading/error
 * states, mirroring the NovelDetailsTab / SeriesMetadataForm pattern.
 */
import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import {
  useSeriesHistoryPreview,
  useSeriesSettings,
  useUpdateSeriesSettings,
} from "@/lib/hooks/useSeries";
import { SeriesContextPreview } from "./SeriesContextPreview";
import { SeriesField as Field } from "./SeriesField";

interface SeriesContextWindowFieldProps {
  readonly seriesId: string;
}

const MIN_WINDOW = 1;
const MAX_WINDOW = 10;

export function SeriesContextWindowField({ seriesId }: SeriesContextWindowFieldProps) {
  const t = useTranslations("studio");
  const { data: settings, isLoading, isError } = useSeriesSettings(seriesId);
  const previewQuery = useSeriesHistoryPreview(seriesId);
  const update = useUpdateSeriesSettings(seriesId);

  const [draft, setDraft] = useState<number>(3);
  const [dirty, setDirty] = useState(false);

  // Re-sync from server data only while clean — mirrors SeriesMetadataForm's
  // dirty guard so a background refetch (new object identity) can't clobber
  // the user's in-flight edit.
  useEffect(() => {
    if (dirty) return;
    if (settings) setDraft(settings.context_window_size);
  }, [settings, dirty]);

  const saved = settings?.context_window_size ?? null;
  const previewData = previewQuery.data;
  // The server range is 1..max(10, saved) — the lookup also covers a saved
  // value above the slider top (shown until the user moves the slider).
  const entry = previewData?.previews.find((p) => p.window_size === draft) ?? undefined;

  // Clear dirty only once the server round-trip confirms the draft (fresh
  // settings equal it, no PATCH in flight). Clearing it in mutate's
  // onSuccess instead would run the re-sync effect above against
  // still-stale settings and flash the old slider position before the
  // refetched data lands.
  useEffect(() => {
    if (dirty && !update.isPending && saved !== null && draft === saved) {
      setDirty(false);
    }
  }, [dirty, saved, draft, update.isPending]);

  function handleSlide(raw: number): void {
    setDraft(Math.min(Math.max(raw, MIN_WINDOW), MAX_WINDOW));
    setDirty(true);
  }

  function handleSave(): void {
    if (draft < MIN_WINDOW || draft > MAX_WINDOW) return;
    // No-op if unchanged (e.g. Save clicked in the window between sliding
    // back to the saved value and the confirmation effect above flushing).
    if (saved !== null && draft === saved) return;
    update.mutate({ context_window_size: draft });
  }

  if (isLoading) {
    return (
      <div
        data-testid="series-context-window-loading"
        className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground"
      >
        <Loader2 className="h-5 w-5 animate-spin" />
        {t("series.settings.loading")}
      </div>
    );
  }

  if (isError || !settings) {
    return (
      <div
        data-testid="series-context-window-error"
        className="py-8 text-center text-sm text-muted-foreground"
      >
        {t("series.settings.error")}
      </div>
    );
  }

  const label = t("series.settings.contextWindow.label");
  const canSave = dirty && draft >= MIN_WINDOW && draft <= MAX_WINDOW;

  return (
    <section data-testid="series-context-window" className="space-y-4">
      <div className="space-y-3 rounded-lg border border-border bg-card p-6">
        <Field label={label}>
          <div className="flex items-center gap-3">
            <input
              data-testid="series-context-window-slider"
              type="range"
              min={MIN_WINDOW}
              max={MAX_WINDOW}
              step={1}
              value={Math.min(draft, MAX_WINDOW)}
              onChange={(e) => handleSlide(Number(e.target.value))}
              aria-label={label}
              aria-describedby="series-context-window-help"
              className="flex-1 accent-foreground"
            />
            <span
              data-testid="series-context-window-value"
              className="w-8 text-right text-sm tabular-nums"
            >
              {draft}
            </span>
          </div>
        </Field>
        <p
          id="series-context-window-help"
          className="text-xs leading-relaxed text-muted-foreground"
        >
          {t("series.settings.contextWindow.help")}
        </p>
        {saved !== null && saved > MAX_WINDOW ? (
          <p
            data-testid="series-context-window-out-of-range"
            className="text-xs text-amber-600"
          >
            {t("series.settings.contextPreview.savedOutOfRange", {
              value: saved,
              max: MAX_WINDOW,
            })}
          </p>
        ) : null}
        {previewQuery.isLoading ? (
          <p
            data-testid="series-context-preview-loading"
            className="text-xs text-muted-foreground"
          >
            {t("series.settings.contextPreview.loading")}
          </p>
        ) : previewQuery.isError ? (
          <p
            data-testid="series-context-preview-error"
            className="text-xs text-muted-foreground"
          >
            {t("series.settings.contextPreview.error")}
          </p>
        ) : entry && previewData ? (
          <SeriesContextPreview entry={entry} meta={previewData} />
        ) : null}
      </div>

      {dirty ? (
        <div className="flex justify-end">
          <button
            type="button"
            data-testid="series-context-window-save"
            onClick={handleSave}
            disabled={!canSave || update.isPending}
            className="flex items-center gap-2 rounded-md bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground shadow-sm transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {update.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {t("series.settings.save")}
          </button>
        </div>
      ) : null}
    </section>
  );
}
```

- [ ] **Step 4: Keep the parent Settings-tab test hermetic**

In `packages/web/components/series/__tests__/SeriesSettings.test.tsx`, inside the existing `vi.mock("@/lib/hooks/useSeries", ...)` factory, extend the mocked exports — after the `useUpdateSeriesSettings: () => ({ ... }),` stub, add:

```ts
  // SeriesContextWindowField's preview query (C1) — stubbed so the field
  // renders cleanly without preview data; preview behaviour is covered by
  // SeriesContextWindowField.test.tsx / SeriesContextPreview.test.tsx.
  useSeriesHistoryPreview: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
  }),
```

- [ ] **Step 5: Run the frontend series tests to verify everything passes**

Run: `cd packages/web && pnpm test components/series && pnpm type-check && pnpm lint:check`
Expected: PASS — rewritten field tests (10), preview component tests (5, Task 7a), parent Settings tests with the extended mock, type-check, biome.

- [ ] **Step 6: Commit (via Platform, verbatim)**

```bash
git add packages/web/components/series/SeriesContextWindowField.tsx \
        packages/web/components/series/__tests__/SeriesContextWindowField.test.tsx \
        packages/web/components/series/__tests__/SeriesSettings.test.tsx
```

Commit message:

```
feat(web): replace context-window number input with 1-10 slider + live preview

C1 user-facing surface (design §4.1: slider range 1-10, Series-Workspace
Settings tab, value display + help text, live preview):

- SeriesContextWindowField rewritten: native range slider (min 1 / max
  10 / step 1; ContextBudget.tsx slider pattern: accent-foreground +
  aria-label; aria-describedby carried over from the previous
  SeriesContextWindowField) with a tabular-nums value display;
  dirty-gated Save PATCHing via the UNCHANGED settings endpoint;
  preview states (loading / error) render dedicated lines while the
  slider stays usable.
- Honesty handling for API-saved values above the slider top (bound is
  [1, 50] server-side): savedOutOfRange notice + preview of the saved
  value via the extended server range (1..max(10, saved)); the next
  slider save replaces it. The old number-input rationale (precision)
  is superseded by the approved C1 design — documented in the component
  docstring.
- SeriesSettings.test.tsx: hook mock extended with the preview query
  stub (hermeticity).

Tests: slider bounds/type/initial value, preview rendering + window
switch without refetch, dirty-gated Save PATCH payload {window: 7},
help text, preview loading/error with usable slider, out-of-range
saved value (notice + preview at 12 + value display 12).

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §4 (C1), docs/features/series/SERIES-002-generation-context.md
```

---

### Task 8: Docs — SERIES-002 spec closure + CURRENT_STATE entry + slice-final gates

**Files:**
- Modify (docs): `docs/features/series/SERIES-002-generation-context.md`
- Modify (docs): `docs/_shared/CURRENT_STATE.md`

> **Production-file count: 0** — docs-only task (cap-exempt by definition; test files and docs do not count).

**Interfaces:**
- Consumes: everything landed in Tasks 1–7b.
- Produces: honest documentation of the C1 closure, including the two documented limitations (project-level routing caveat; slider 1–10 vs API [1, 50]).

- [ ] **Step 1: Update the SERIES-002 feature spec**

In `docs/features/series/SERIES-002-generation-context.md`:

1a. In the Limitations section, replace the bullet (locate by its opening text):

```markdown
- **`context_window_size` tunability** — the column exists and the provider
  reads it (default 3), but the settings PATCH/GET API surface and the
  user-facing slider to change it are **open work** (tracked below). The
  feature is correct at the default until then.
```

with:

```markdown
- **`context_window_size` tunability — CLOSED (C1, 2026-08-16)** — the
  settings PATCH/GET API surface had already landed with the field
  (`SeriesSettingsUpdateRequest` / `SeriesSettingsResponse`, bounded
  [1, 50]); the C1 slider (1–10, Series-Workspace → Settings tab) with the
  live token preview (`GET /api/v1/series/{id}/settings/context-preview`)
  completes the user-facing surface. The slider clamps to 1–10 while the
  API bound stays [1, 50] (MCP/CLI-settable); a saved value above 10 is
  shown honestly via a notice and the extended preview range.
```

1b. Replace the whole "Open Work" section (header + the Context Window slider bullet) with:

```markdown
## Open Work (not blocking stability)

- None currently — the C1 slider + preview (2026-08-16) closed the last
  item.
```

1c. In the `## Status & History` section, append:

```markdown
- **2026-08-16:** C1 (Post-Export Follow-ups program, design §4) closed the
  slider remainder: `SeriesHistoryTier.preview` (Core — same
  `_select_text` / `_render_entry` / `_fit_to_budget` code path as real
  assembly, no second fitting algorithm), `SeriesHistoryPreviewService` +
  `collect_series_band_data` (next-band semantics: every positioned member
  is a prior band), `GET /series/{id}/settings/context-preview`
  (budgets consumed verbatim via `resolve_context_budgets`,
  `series_in_scope=True`, user-level routing — a project-level routing
  override for a specific novel may differ at that novel's generation
  time), and the 1–10 slider + preview UI (`SeriesContextWindowField` +
  `SeriesContextPreview`, i18n en/de/fr). PATCH stays on the existing
  settings endpoint.
```

- [ ] **Step 2: Update CURRENT_STATE**

In `docs/_shared/CURRENT_STATE.md`, insert a new date entry directly **below** the `## Last Updated` heading (above the existing `Date: 2026-08-15 (C5 — Token-Budget Governance …` entry):

```markdown
Date: 2026-08-16 (C1 — Context-Window Slider **implemented**; program item C1 of the [Post-Export Follow-ups program](superpowers/specs/2026-08-14-post-export-followups-design.md) §4). `context_window_size` (SERIES-002, DB since Alembic 0038) is now user-tunable: **1–10 slider** in the Series-Workspace Settings tab (`SeriesContextWindowField` rewritten from number input to native range slider + value display; PATCH via the **unchanged** settings endpoint) with a **live honesty preview** (`SeriesContextPreview` + `useSeriesHistoryPreview`, i18n `series.settings.contextPreview.*` en/de/fr) computed **server-side from the series' actual band summaries against the effective ADR-082 budgets** — pattern "3 Bände voll — ca. 440 / 16 000 Tokens; größeres Window wird vom Token-Budget gekürzt". Backend: pure-Core `SeriesHistoryTier.preview` (`packages/core/narrare_core/context/series_history.py` — classifies full/short/truncated/dropped/missing bands by walking the **same** `_fit_to_budget` greedy fit real assembly runs; `_render_entry` extracted so assemble + preview share one format string; **no second fitting algorithm**, pinned by parametrized assemble-consistency tests) + `SeriesHistoryPreviewService` (`series/series_history_preview_service.py`) + `SeriesHistoryProvider.collect_series_band_data` (next-band semantics: every positioned member is a prior band — the exact view `assemble_series_history` has for the next novel) + `GET /api/v1/series/{id}/settings/context-preview` (router + `get_series_history_preview_service` DI factory resolving budgets through the **exact ADR-082 production chain**: WRITE-intent routing → `TokenLimitsService` cascade → `resolve_context_budgets(series_in_scope=True)` — `EffectiveContextBudgets` verbatim, response carries ceiling/total/tier-base/model-window/source; RULE-11 `window_unknown` surfaced). Response covers window sizes 1..max(10, saved) in one snapshot (slider switches client-side, no refetch). Documented limitations: user-level routing (`project_id=None` — the next band has no novel id; project-level overrides for a specific existing novel may differ at its generation time); slider clamps to 1–10 while the API bound stays [1, 50] (MCP/CLI-settable — out-of-range saved values shown honestly via notice + extended preview range). Design-doc discrepancy recorded honestly: §4's "no settings-API surface, no UI" was empirically stale — both existed (schemas + `SeriesContextWindowField` number input); C1's delta is the slider + preview. Frontend data layer: `SeriesHistoryPreviewEntry/Response` types (RULE-17 parity), `seriesApi.getSettingsContextPreview`, `seriesKeys.settingsPreview` (invalidated together with settings on PATCH). SERIES-002 spec Open Work closed.
```

- [ ] **Step 3: Slice-final gates (design §12, C1 gate)**

Run each and record exact results in the task report:

```bash
just check-architecture
just typecheck
just lint-check
just test-unit
cd packages/web && pnpm type-check && pnpm lint:check
just test-frontend
```

Expected: all PASS. Design §12 C1 gate mapping — "Slider + preview tests (live computation, honesty display)": Tasks 1/3 (live computation: actual-summaries flow, per-entry effective budget, assemble-consistency), Task 7a/7b (honesty display: clipping warning, budget line, window-unknown, out-of-range). "Settings PATCH tests": existing `tests/unit/api/series/test_router.py::TestSettings` (unchanged endpoint) + Task 7b's PATCH-payload test.

- [ ] **Step 4: Commit (via Platform, verbatim)**

```bash
git add docs/features/series/SERIES-002-generation-context.md \
        docs/_shared/CURRENT_STATE.md
```

Commit message:

```
docs(series): close SERIES-002 slider remainder — C1 shipped

- SERIES-002: the `context_window_size` tunability limitation is CLOSED
  (C1, 2026-08-16) — corrects the stale "settings PATCH/GET API surface
  ... open work" claim (the surface had landed with the field; C1's
  delta is the 1-10 slider + live preview); Open Work section emptied
  with an honest note; Status & History row records the full C1
  delivery (Core preview seam, preview service + provider accessor,
  context-preview endpoint, slider UI + i18n) and the two documented
  limitations (user-level routing for the next-band subject; slider
  1-10 vs API [1, 50] with honest out-of-range handling).
- CURRENT_STATE: dated C1 implementation entry (design §4 binding
  decisions 1:1; ADR-082 budgets consumed verbatim via
  resolve_context_budgets; design-doc discrepancy recorded honestly).

Slice-complete per RULE-20: Core seam + service + endpoint + UI + i18n
+ docs landed together across Tasks 1-8; no migration, no new router
file, no new dependency.

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §4 + §12 (C1 gate)
```

---

## Post-plan verification summary (design doc §12, C1 gate)

| Gate | Where |
|---|---|
| Slider + preview tests — live computation | Task 1 (`test_series_history_preview.py` — assemble-consistency parametrized suites), Task 3 (`test_series_history_preview_service.py` — actual summaries flow, per-entry effective budget, budget metadata verbatim) |
| Slider + preview tests — honesty display | Task 7a (`SeriesContextPreview.test.tsx` — clipping warning, budget line, window-unknown), Task 7b (bounds, preview switch, out-of-range saved value) |
| Settings PATCH tests | Existing `tests/unit/api/series/test_router.py::TestSettings` (endpoint unchanged) + Task 7b PATCH-payload test |
| Preview honesty requirements (design §4.1) | Actual summaries (provider accessor, Task 3); effective budgets via `resolve_context_budgets` (DI factory, Task 4); clipping warning (`budget_clipped` → `clippedWarning`, Tasks 1/6/7a); tier-base semantics in copy (`budgetLine`, Tasks 2/6) |
| i18n en/de/fr | Task 6 (11 keys × 3 locales, parity gate) |
| Full gates | Task 8 Step 3 (`check-architecture`, `typecheck`, `lint-check`, `test-unit`, frontend `type-check`/`lint:check`, `test-frontend`) |

## Deviations & Interpretations (honest record — read before executing)

1. **Design §4 factual discrepancy (flagged to coordinator at plan time):** the design doc claims `context_window_size` has "no settings-API surface, no UI". Empirically (probed 2026-08-16): `SeriesSettingsResponse.context_window_size` + `SeriesSettingsUpdateRequest.context_window_size` (`ge=1, le=50`) exist and are wired through `SeriesService.get_settings`/`update_settings` → `SeriesRepository.update_settings`; the frontend `SeriesContextWindowField` (number input [1, 50]) renders on the Settings tab. CURRENT_STATE's 2026-08-02 entry ("not yet exposed on SeriesSettingsUpdateRequest/SeriesSettingsResponse") is likewise stale. **Ruling:** implement the binding decisions as written (slider 1–10 + preview; PATCH via existing endpoint) — the work is strictly smaller than the design assumed; the stale claims are corrected in the Task 8 docs pass, not silently.
2. **Slider bound 1–10 vs API bound [1, 50]:** the PATCH schema is NOT tightened to `le=10` — DB rows with stored values 11–50 exist (tightening would break their round-trips or force a data migration), and the wider bound keeps the published contract stable (RULE-17 parity; no schema change without cause). The UI clamps to 1–10 (design binding) and handles out-of-range saved values honestly (notice + extended preview range `1..max(10, saved)`); a superset bound is harmless.
3. **Preview data-flow ruling (batch GET, no per-position fetch):** `GET /settings/context-preview` returns previews for ALL candidate window sizes in ONE response computed from ONE snapshot (bands + budgets). Alternatives rejected: (a) per-window query param — slider drags would spam requests and need debouncing, and two fetches could straddle a summary edit (inconsistent preview across positions); (b) client-side fitting — would duplicate `_fit_to_budget` in TypeScript, violating the no-second-algorithm requirement; (c) folding into `GET /settings` — would make every settings read/PATCH response carry band-summary fetches + cascade + model-window resolution, and the PATCH response does not need it. Cost of the batch: 10 pure-function calls over in-memory data (microseconds).
4. **Next-band semantics (locked, Global Constraints):** the preview subject is the next band; all positioned members are prior bands. Consequence: model routing + cascade resolve with `project_id=None` (the next band has no novel id). A project-level routing/cascade override for a *specific* existing novel applies at that novel's generation but cannot be known from the series workspace — documented limitation (service docstring, Task 4 factory docstring, Task 8 spec), not surfaced in the UI (YAGNI — the preview's subject is explicitly the next band).
5. **`slider_max` as constructor default, not a module constant:** the configurable-defaults checker (`scripts/architecture/_checkers/hardcoded_values.py`) flags module-/class-level numeric literals > 5; function-parameter defaults are exempt. The value 10 therefore lives in `SeriesHistoryPreviewService.__init__(slider_max: int = 10)` with a design-§4 reference; the frontend keeps its own `MAX_WINDOW = 10`.
6. **File-limit-driven split:** `series/schemas.py` (196/200), `series/contracts.py` (197/200), and `series/service.py` (275/300) are at/near their RULE-04 limits — all C1 backend surface lives in new `series_history_preview_{schemas,contracts,service}.py` files (module precedent: `series_voice_schemas.py`, `band_summary_contracts.py`), the route joins the existing `router.py` (101→~116/150), and the factory joins `dependencies.py` (179→~235/400).
7. **`SeriesHistoryProvider.collect_series_band_data` as the single band-data construction seam:** the preview service could have duplicated the provider's 10-line `_collect_band_data` loop; instead the provider gains a public series-keyed accessor (next-band semantics documented in-code). All `BandSummaryData` construction stays in one class — future changes to band-data assembly propagate to both consumers.
8. **Task 1 `_render_entry` extraction:** `assemble`'s inline entry f-string becomes a module-private helper shared with `preview`, so the line format has one source. Behavior-identical (same string); pinned by running the existing series-history suites unchanged (Task 1 Step 7).
9. **Task 3 test-fixture construction:** the service tests build member-novel shapes inline as plain attribute objects (`type("NovelRow", (), {...})()`) because `FakeSeriesRepository.list_novels` validates through `NovelRow.model_validate` (`extra="allow", from_attributes=True` — attribute shapes validate) and `FakeSeriesRepository.seed(novels=...)` accepts arbitrary objects. The provider is constructed with `novel_repo=None` — `collect_series_band_data` consumes only `series_repo` + `band_summary_repo`, and the test documents that surface honestly.
10. **No ADR:** design §4 is a feature-level decision on an existing, ADR-077-governed surface; ADR-082's C1 dependency note is satisfied (verbatim `EffectiveContextBudgets` consumption) and needs no amendment — its wording already describes what this plan builds.
