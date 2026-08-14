"""Committed baselines for the Golden-Pages acceptance test (Slice 7).

Each fixture has a ``baselines/{name}.json`` carrying the drift metrics
established from the CURRENT narrare-roman output (rendered through the real
pipeline). The golden test asserts ``actual <= baseline`` for the drift
metrics + an exact sha256 match; unintentional drift = CI failure. Intentional
drift (a narrare-roman / Typst / pandoc change) is blessed by regenerating the
baselines via ``just golden-update`` (or ``pytest --golden-update``) and
committing the new values — the documented human-review path.

Baseline schema (per fixture)::

    {
      "schema_version": 1,
      "sha256": "<hex>",                    # byte-reproducibility golden anchor
      "page_count": <int>,                  # drift — exact match
      "right_edge_max_error_mm": <float>,   # drift — actual <= baseline (omitted when N/A)
      "word_gap_stdev_pt": <float>          # drift — actual <= baseline (omitted when N/A)
    }

The ``right_edge_max_error_mm`` / ``word_gap_stdev_pt`` keys are present only
for fixtures that exercise those probes (justified multi-line body text). The
invariant probes (ToUnicode, folio numbering, running heads, recto start,
scene break) are NOT baselined — they assert a fixed property, not a drift
value.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tests.golden.export._typst_probe_helpers import doc_page_count
from tests.golden.export.harness import probes

if TYPE_CHECKING:
    import pymupdf

    from tests.golden.export.harness.corpus import CorpusFixture

#: Schema version — bump if the baseline JSON shape changes incompatibly.
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Baseline:
    """Drift metrics for one fixture, established from current output.

    ``right_edge_max_error_mm`` / ``word_gap_stdev_pt`` are ``None`` when the
    fixture does not exercise those probes (they are omitted from the JSON).
    """

    sha256: str
    page_count: int
    right_edge_max_error_mm: float | None = None
    word_gap_stdev_pt: float | None = None

    def to_json(self) -> dict[str, object]:
        """Serialize to the committed JSON shape (omits ``None`` metrics).

        Drift metrics are stored at FULL float precision — rounding would make
        ``actual <= baseline`` fail on the exact same output (the rounded
        baseline truncates below the unrounded measurement). Typst + PyMuPDF
        are deterministic, so full precision gives an exact-match comparison.
        """
        payload: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "sha256": self.sha256,
            "page_count": self.page_count,
        }
        if self.right_edge_max_error_mm is not None:
            payload["right_edge_max_error_mm"] = self.right_edge_max_error_mm
        if self.word_gap_stdev_pt is not None:
            payload["word_gap_stdev_pt"] = self.word_gap_stdev_pt
        return payload

    @staticmethod
    def from_json(data: dict[str, object]) -> Baseline:
        """Deserialize from the committed JSON shape."""
        return Baseline(
            sha256=str(data["sha256"]),
            page_count=int(data["page_count"]),  # type: ignore[arg-type]
            right_edge_max_error_mm=(
                float(data["right_edge_max_error_mm"])  # type: ignore[arg-type]
                if "right_edge_max_error_mm" in data
                else None
            ),
            word_gap_stdev_pt=(
                float(data["word_gap_stdev_pt"])  # type: ignore[arg-type]
                if "word_gap_stdev_pt" in data
                else None
            ),
        )


def load_baseline(fixture: CorpusFixture) -> Baseline:
    """Read the committed baseline for ``fixture`` from its JSON file."""
    data: dict[str, object] = json.loads(fixture.baseline_file.read_text(encoding="utf-8"))
    return Baseline.from_json(data)


def save_baseline(fixture: CorpusFixture, baseline: Baseline) -> None:
    """Write ``baseline`` to the fixture's JSON file (pretty-printed, sorted)."""
    fixture.baseline_file.write_text(
        json.dumps(baseline.to_json(), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def capture_baseline(doc: pymupdf.Document, fixture: CorpusFixture, sha256_hex: str) -> Baseline:
    """Build a :class:`Baseline` from a rendered document + its sha256.

    Renders happen in the test (twice — for reproducibility + the golden
    sha256); this function only extracts the drift metrics from the open
    document. Used by the ``--golden-update`` regeneration path.
    """
    right_edge = (
        probes.right_edge_max_error_mm(doc) if "right_edge_max_error" in fixture.probes else None
    )
    word_gap = probes.word_gap_stdev_pt(doc) if "word_gap_stdev" in fixture.probes else None
    return Baseline(
        sha256=sha256_hex,
        page_count=doc_page_count(doc),
        right_edge_max_error_mm=right_edge,
        word_gap_stdev_pt=word_gap,
    )
