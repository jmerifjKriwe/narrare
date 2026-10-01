"""Pilot substrate for the ADR-090 rerank pilot (Task 16) — cases, pools, scorers.

Split from ``evals/rerank_pilot.py`` for RULE-04 (file-size limit); the
pipeline, metrics, report, and CLI live there. This module owns the
measurement *substrate*:

- The multilingual case set (carry note 1): en cases come from the ADR-032
  ``rewrite_selection`` dataset; the de/fr selections are pilot-local so the
  shared suite baseline stays untouched. Language is a recorded dimension.
- Candidate pools: gold = a case's own non-empty context blocks (labeled by
  position ``before``/``after``); distractors = a seeded deterministic
  selection from the other cases' context blocks.
- Deterministic scoring primitives: the lexical-overlap surrogate (baseline
  arm stand-in for hybrid scoring) and the dry-run seeded scorer (carry note
  4 — relevance-blind pseudo-scores so a dry run never masquerades as a real
  measurement).
"""

from __future__ import annotations

import hashlib
import re
import sys
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from narrare_core.embeddings import RerankCandidate

if TYPE_CHECKING:
    from collections.abc import Sequence

    from evals.models import RewriteSelectionInput

_RewriteMode = Literal["tone", "style", "voice", "fix", "custom"]

_TOKEN_RE = re.compile(r"\w+")


@dataclass(frozen=True, slots=True)
class PilotCase:
    """One measurement case; ``language`` is a recorded dimension."""

    name: str
    language: str
    inputs: RewriteSelectionInput


@dataclass(frozen=True, slots=True)
class Block:
    """A candidate context block (gold or distractor)."""

    block_id: str  # stable label: "<case>:<position>"
    text: str
    is_gold: bool
    origin_case: str
    position: str  # "before" | "after"


# (name, language, selection_text, context_before, context_after, mode, instruction)
_LOCAL_CASE_ROWS: tuple[tuple[str, str, str, str, str, _RewriteMode, str], ...] = (
    (
        "tone-soften-de",
        "de",
        "Ihr habt uns im Stich gelassen, und das weiß jeder.",
        "Der Ratssaal verstummte.",
        "Mara wand sich zuerst weg.",
        "tone",
        "Mache die Anschuldigung weniger grausam, aber weiterhin angespannt.",
    ),
    (
        "voice-character-de",
        "de",
        "Wir sollten vor Sonnenaufgang aufbrechen.",
        "Iven überprüfte die Sattelgurte.",
        "Die Pferde schnaubten in der Kälte.",
        "voice",
        "Benutze Hauptmann Ivens knappen Soldatenton.",
    ),
    (
        "tone-soften-fr",
        "fr",
        "Vous nous avez trahis, et tout le monde le sait.",
        "La salle du conseil retint son souffle.",
        "Mara détourna le regard la première.",
        "tone",
        "Rends l'accusation moins cruelle mais toujours tendue.",
    ),
    (
        "voice-character-fr",
        "fr",
        "Nous devrions partir avant l'aube.",
        "Iven vérifia les sangles de la selle.",
        "Les chevaux piétinaient dans le froid.",
        "voice",
        "Utilise la voix brève du capitaine Iven.",
    ),
)


def _ensure_repo_root_importable() -> None:
    """Make ``evals.*`` importable when run as a script file.

    The repo root is a virtual uv workspace container (``[tool.uv] package =
    false``), so ``evals`` is not an installed package: running
    ``python evals/rerank_pilot.py`` puts ``evals/`` (not the root) on
    ``sys.path``. ``narrare_core`` resolves from the installed workspace member.
    """
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)


def pilot_local_cases() -> list[PilotCase]:
    """Build the pilot-local de/fr selections (carry note 1)."""
    _ensure_repo_root_importable()
    from evals.models import RewriteSelectionInput

    return [
        PilotCase(
            name=name,
            language=language,
            inputs=RewriteSelectionInput(
                selection_text=selection,
                context_before=before,
                context_after=after,
                rewrite_mode=mode,
                instruction=instruction,
            ),
        )
        for name, language, selection, before, after, mode, instruction in _LOCAL_CASE_ROWS
    ]


def load_cases() -> list[PilotCase]:
    """Load en cases from the ADR-032 dataset plus the pilot-local de/fr cases."""
    _ensure_repo_root_importable()
    from evals.datasets.rewrite_selection import build_dataset

    dataset_cases = [
        PilotCase(name=str(case.name), language="en", inputs=case.inputs)
        for case in build_dataset().cases
    ]
    return dataset_cases + pilot_local_cases()


def case_blocks(case: PilotCase) -> list[Block]:
    """Extract the case's non-empty context blocks as gold, labeled by position."""
    blocks: list[Block] = []
    for position, text in (
        ("before", case.inputs.context_before),
        ("after", case.inputs.context_after),
    ):
        if text.strip():
            blocks.append(
                Block(
                    block_id=f"{case.name}:{position}",
                    text=text,
                    is_gold=True,
                    origin_case=case.name,
                    position=position,
                )
            )
    return blocks


def build_pool(
    case: PilotCase, all_cases: Sequence[PilotCase], *, seed: int, n_distractors: int
) -> list[Block]:
    """Gold blocks first, then distractors selected from other cases (seeded).

    Distractor selection: the ``n_distractors`` other-case blocks with the
    smallest ``sha256(f"{seed}:{case.name}:{block_id}")`` — deterministic
    across runs and machines, no PRNG involved.
    """
    gold = case_blocks(case)
    other_blocks = [
        block for other in all_cases if other.name != case.name for block in case_blocks(other)
    ]
    keyed = sorted(
        other_blocks,
        key=lambda block: hashlib.sha256(
            f"{seed}:{case.name}:{block.block_id}".encode()
        ).hexdigest(),
    )
    # Gold-ness is pool-relative: blocks borrowed from other cases are
    # distractors here even though they are their own case's gold.
    distractors = [replace(block, is_gold=False) for block in keyed[:n_distractors]]
    return gold + distractors


def lexical_surrogate(query: str, text: str) -> float:
    """Deterministic hybrid-score surrogate: Jaccard over lowercased word tokens."""
    query_tokens = set(_TOKEN_RE.findall(query.lower()))
    text_tokens = set(_TOKEN_RE.findall(text.lower()))
    if not query_tokens or not text_tokens:
        return 0.0
    return len(query_tokens & text_tokens) / len(query_tokens | text_tokens)


def to_candidate(block: Block, base_score: float) -> RerankCandidate:
    """Map a pilot block to the ADR-090 Decision-3 candidate shape (stable IDs)."""
    return RerankCandidate(
        source_id=uuid.uuid5(uuid.NAMESPACE_URL, f"rerank-pilot:{block.block_id}"),
        source_type=f"{block.origin_case}:{block.position}",
        text=block.text,
        base_score=base_score,
    )


def seeded_scores(query: str, texts: Sequence[str], *, seed: int) -> list[float]:
    """Dry-run scorer: deterministic content-seeded pseudo-scores in [0, 1).

    Deliberately relevance-blind (SHA-256, stable across runs and machines):
    a dry run must not produce numbers that look like a real measurement.
    """
    return [
        int(hashlib.sha256((f"{seed}:" + query + "\x00" + text).encode()).hexdigest()[:12], 16)
        / float(16**12)
        for text in texts
    ]
