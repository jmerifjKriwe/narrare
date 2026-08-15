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

__all__ = ["BandSummaryData", "SeriesHistoryTier"]

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
            entries.append(f"Band {band.position} — {band.title}: {text}")

        if not entries:
            return ""

        fitted = self._fit_to_budget(entries, token_budget)
        if not fitted:
            return ""  # nothing fit — don't emit a lone header
        return _HEADER + "\n\n".join(fitted)

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
