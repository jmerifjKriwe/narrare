"""Series-history context tier (Spec 2, Task 6 — SERIES-002).

Produces the ``Previously in this series:`` text block injected at
generation time via the ``{{series_history}}`` prompt variable. The tier
applies a **recency-window**: the last ``window_size`` bands (before the
current novel) contribute their full summary (or a user override), while
older bands contribute only their one-sentence short summary. When the
running total exceeds ``token_budget``, older bands are sacrificed first
— truncated at the boundary, then dropped — so the most recent context is
always preserved.

Pure formatting + truncation
----------------------------
This module performs **no I/O and no DB access**. The Backend caller
(Layer-3 service) pre-fetches :class:`BandSummaryData` from
``BandSummaryRepository`` + ``NovelRepository`` (positions/titles) and
hands the list to :meth:`SeriesHistoryTier.assemble`. This keeps Core
pure (RULE-07: Core has zero ``apps/`` imports) while concentrating the
recency / override / truncation logic here (RULE-06: one responsibility
— series-history assembly + formatting + budget enforcement).

``BandSummaryData`` is a frozen dataclass by deliberate convention, matching
the other cross-boundary value types in this package
(:class:`~narrare_core.context.suggestion.EntityMetadata`,
:class:`~narrare_core.context.suggestion.Suggestion`,
:class:`~narrare_core.context.types.TierBudget`) — lightweight info handed
from the API layer to Core.

See:
    docs/superpowers/plans/2026-08-02-series-generation-context.md (Task 6),
    docs/architecture/decisions/ADR-025-feature-adoption-infrastructure.md,
    docs/_shared/CONSTRAINTS.md (RULE-06, RULE-07, RULE-11).
"""

from __future__ import annotations

from dataclasses import dataclass

from narrare_core.context.budget import DEFAULT_SERIES_HISTORY_BUDGET

__all__ = ["BandSummaryData", "SeriesHistoryPreview", "SeriesHistoryTier"]

# ---------------------------------------------------------------------------
# Token-estimation constants
# ---------------------------------------------------------------------------

#: Approximate characters per token. ``tiktoken`` is not a Core dependency,
#: so we use the standard 4-chars/token heuristic. This is deliberately
#: conservative-simple — the writing pipeline's real budgeting happens at
#: the assembler level; this tier only needs a stable, monotonic estimate
#: for "keep most recent" decisions.
_CHARS_PER_TOKEN: int = 4

#: Minimum token headroom required before we bother truncating a boundary
#: band's text. Below this we drop the band entirely — a 19-token slice of a
#: multi-paragraph summary is less useful than cleanly omitting it, and
#: avoids emitting a near-empty "Band N — Title: …" line.
_MIN_TRUNCATE_TOKENS: int = 20

#: Header prepended to every non-empty series-history block.
_HEADER: str = "Previously in this series:\n\n"

#: Ellipsis appended to truncated summaries to signal an incomplete cut.
_ELLIPSIS: str = "…"


# ---------------------------------------------------------------------------
# Cross-boundary value type
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BandSummaryData:
    """Pre-fetched band-summary data passed from the Backend into Core.

    The Backend caller constructs one instance per prior band in the series
    (the current novel is excluded by the caller). Fields mirror the
    ``BandSummary`` ORM model plus the novel's series position and title,
    which Core needs for formatting but cannot fetch itself (RULE-07).

    Analogous to :class:`~narrare_core.context.suggestion.EntityMetadata`:
    lightweight info crossing the API→Core boundary.

    Attributes:
        position: 1-based ``series_position`` of the novel (band number).
        title: Novel title, rendered in the ``Band N — Title`` header.
        full_summary: Auto-generated multi-paragraph summary, used for bands
            inside the recency window. ``None`` if not yet generated.
        short_summary: Auto-generated one-sentence summary, used for bands
            outside the recency window. ``None`` if not yet generated.
        override: Optional user-curated text that replaces ``full_summary``
            within the recency window (empty string falls back to
            ``full_summary``). Ignored outside the window.
    """

    position: int
    title: str
    full_summary: str | None = None
    short_summary: str | None = None
    override: str | None = None


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


# ---------------------------------------------------------------------------
# Token helpers (module-private)
# ---------------------------------------------------------------------------


def _estimate_tokens(text: str) -> int:
    """Rough token count via the chars/4 heuristic (no tiktoken dependency)."""
    return len(text) // _CHARS_PER_TOKEN


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate *text* to ~``max_tokens``, cutting at a word boundary.

    Appends an ellipsis so consumers can see the cut. If *text* already
    fits, it is returned unchanged.
    """
    if max_tokens <= 0 or not text:
        return ""
    max_chars = max(max_tokens * _CHARS_PER_TOKEN, 1)
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    # Prefer a clean word boundary (don't cut mid-word).
    last_space = cut.rfind(" ")
    if last_space > 0:
        cut = cut[:last_space]
    return cut.rstrip(" ,.;:-—") + _ELLIPSIS


def _render_entry(band: BandSummaryData, text: str) -> str:
    """Format one band's contribution line (shared by assemble + preview).

    Formatting helper placed among the token helpers on purpose: the module
    has no separate formatting section, and it belongs with
    ``_truncate_to_tokens`` as a seam shared by assemble and preview.
    """
    return f"Band {band.position} — {band.title}: {text}"


# ---------------------------------------------------------------------------
# Tier
# ---------------------------------------------------------------------------


class SeriesHistoryTier:
    """Context tier that assembles the series-history text block.

    Recency-window logic:

        For a series with bands ``1..N-1`` (the current novel ``N`` is
        excluded by the caller) and ``window_size = K``:

        * the last ``K`` bands (highest positions) → ``override or
          full_summary``;
        * older bands → ``short_summary`` only.

    Bands whose selected text is ``None``/empty are skipped (RULE-11
    graceful degradation) rather than crashing.

    Token budget: entries are emitted newest-first. The first entry that
    does not fit fully is truncated to the remaining headroom (if at least
    ``_MIN_TRUNCATE_TOKENS`` remain); all older entries are dropped. This
    realises "keep most recent, sacrifice older first".

    The class is stateless — all inputs are parameters to
    :meth:`assemble`. It is async for interface consistency with the
    context-assembler ecosystem it plugs into (Task 7 wires it into the
    async writing pipeline); the body is pure and performs no I/O.
    """

    async def assemble(
        self,
        bands: list[BandSummaryData],
        window_size: int = 3,
        token_budget: int = DEFAULT_SERIES_HISTORY_BUDGET,
    ) -> str:
        """Assemble the series-history context string.

        Args:
            bands: Prior bands in the series (current novel excluded by the
                caller), in any order — they are sorted newest-first here.
            window_size: How many of the most-recent bands receive their
                full summary. ``0`` means every band uses ``short_summary``.
                Negative values are treated as ``0``.
            token_budget: Maximum (estimated) tokens for the whole block,
                header included. ``<= 0`` yields an empty string.
                Default 16,000 (ADR-082 D1; the API passes the resolved
                cascade value — the parameter stays explicit).

        Returns:
            The formatted ``Previously in this series:`` block, or an empty
            string when there is nothing to show (standalone novel, all
            summaries missing, or budget too small to fit any band).
        """
        if token_budget <= 0 or not bands:
            return ""

        # Newest-first ordering, regardless of how the caller supplied them.
        ordered = sorted(bands, key=lambda b: b.position, reverse=True)

        # Distinct positions, descending; the top `window_size` are "in window".
        positions_desc = sorted({b.position for b in ordered}, reverse=True)
        window_positions = set(positions_desc[: max(window_size, 0)])

        entries: list[str] = []
        for band in ordered:
            text = self._select_text(band, in_window=band.position in window_positions)
            if not text:
                continue  # RULE-11: missing summary → skip, don't crash
            entries.append(_render_entry(band, text))

        if not entries:
            return ""

        fitted = self._fit_to_budget(entries, token_budget)
        if not fitted:
            return ""  # nothing fit — don't emit a lone header
        return _HEADER + "\n\n".join(fitted)

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
        for entry, in_window in zip(entries, in_window_flags, strict=True):
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _select_text(band: BandSummaryData, *, in_window: bool) -> str | None:
        """Pick the summary text for a band, or ``None`` to skip it.

        * In window  → ``override or full_summary`` (override precedence;
          empty-string override is falsy and falls back to full).
        * Out of window → ``short_summary`` (override is deliberately
          ignored outside the window — it only curates the full record).
        """
        if in_window:
            return band.override or band.full_summary
        return band.short_summary

    @staticmethod
    def _fit_to_budget(entries: list[str], token_budget: int) -> list[str]:
        """Greedily fit entries (newest-first) into ``token_budget``.

        Returns the sublist of entries to render (already in display order).
        The first entry that doesn't fit fully is truncated to the remaining
        headroom when that headroom is meaningful (``>=
        _MIN_TRUNCATE_TOKENS``); otherwise it and all older entries are
        dropped. The header cost is reserved from the budget.
        """
        remaining = token_budget - _estimate_tokens(_HEADER)
        output: list[str] = []
        for entry in entries:
            if remaining <= 0:
                break
            cost = _estimate_tokens(entry)
            if cost <= remaining:
                output.append(entry)
                remaining -= cost
                continue
            # Doesn't fit fully — truncate to remaining headroom, then stop.
            if remaining >= _MIN_TRUNCATE_TOKENS:
                output.append(_truncate_to_tokens(entry, remaining))
            break
        return output
