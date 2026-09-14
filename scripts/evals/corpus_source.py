"""Corpus source for the beta-reader eval instrument.

Spec: ``docs/superpowers/specs/2026-09-14-beta-reader-eval-design.md`` — §4
chain step 1 (corpus source) and §7/D5 (corpus manifest genre, single source).

This is the eval's OWN manifest reader over ``benchmark/corpus/corpus.yaml``:
the eval owns the ``genre`` key (PO ruling 2); the benchmark loader stays
genre-agnostic (its runs do not consume genre). Boundary (spec §3): the corpus
is consumed as files via paths — this module never imports from ``benchmark/``
or ``evals/``. Benchmark ``parse_chapter`` semantics are replicated here
(title = first ``# `` line, ``word_count = len(text.split())``), deliberately
not imported.

Tolerance: the loader reads named keys only — unknown top-level manifest keys
(``description``, ``variants``, ``reference``, …) are ignored, matching the
verified named-key tolerance of ``benchmark/corpus_loader.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

__all__ = [
    "DEFAULT_CORPUS_ROOT",
    "CorpusSourceError",
    "EvalChapter",
    "EvalCorpusManifest",
    "load_eval_corpus",
]

#: Repository corpus the instrument reads by default (spec §3 data dependency).
DEFAULT_CORPUS_ROOT: Path = Path(__file__).resolve().parents[2] / "benchmark" / "corpus"

#: Scalar manifest keys the eval reads (named-key tolerance, spec §7).
_SCALAR_KEYS: tuple[str, ...] = ("name", "version", "language", "genre")


class CorpusSourceError(ValueError):
    """Raised when the corpus manifest or a chapter file fails to load."""


class EvalChapter(BaseModel):
    """Materialized chapter view (read-only): text as-is, derived title/words."""

    model_config = ConfigDict(frozen=True)

    stem: str = Field(min_length=1)
    title: str | None = None
    text: str
    word_count: int = Field(ge=0)


class EvalCorpusManifest(BaseModel):
    """Typed manifest contract — the eval's own reader (spec §7).

    ``genre`` is required and non-empty (the eval is the genre owner);
    ``chapters`` are the materialized chapter views in manifest order.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    version: int = Field(ge=1)
    language: str = Field(min_length=1)
    genre: str = Field(min_length=1)
    chapters: list[EvalChapter] = Field(min_length=1)


def load_eval_corpus(root: Path | None = None) -> EvalCorpusManifest:
    """Load and validate the eval corpus rooted at ``root`` (holds corpus.yaml).

    ``root`` defaults to :data:`DEFAULT_CORPUS_ROOT`. Raises
    :class:`CorpusSourceError` on unreadable/invalid YAML, invalid manifest
    fields (genre is required, non-empty), or missing chapter files — never
    returns a partially validated corpus.
    """
    corpus_root = DEFAULT_CORPUS_ROOT if root is None else root
    raw = _load_yaml_mapping(corpus_root / "corpus.yaml")
    chapters = [_load_chapter(corpus_root, stem) for stem in _chapter_stems(raw)]
    return _build_manifest(raw, chapters)


def _load_yaml_mapping(manifest_path: Path) -> dict[str, Any]:
    try:
        loaded: object = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CorpusSourceError(f"corpus.yaml: unreadable ({exc})") from exc
    except yaml.YAMLError as exc:
        raise CorpusSourceError(f"corpus.yaml: invalid YAML ({exc})") from exc
    if not isinstance(loaded, dict):
        raise CorpusSourceError("corpus.yaml: must be a YAML mapping")
    return cast("dict[str, Any]", loaded)


def _chapter_stems(raw: dict[str, Any]) -> list[str]:
    value: object = raw.get("chapters")
    if not isinstance(value, list) or not value:
        raise CorpusSourceError("corpus.yaml: 'chapters' must be a non-empty list of stems")
    stems: list[str] = []
    for item in cast("list[object]", value):
        if not isinstance(item, str) or not item:
            raise CorpusSourceError(
                f"corpus.yaml: 'chapters' entries must be non-empty strings, got {item!r}"
            )
        if item in stems:
            raise CorpusSourceError(f"corpus.yaml: duplicate chapter stem {item!r}")
        stems.append(item)
    return stems


def _load_chapter(corpus_root: Path, stem: str) -> EvalChapter:
    path = corpus_root / "clean" / "chapters" / f"{stem}.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CorpusSourceError(f"clean/chapters/{stem}.md: unreadable ({exc})") from exc
    return _parse_chapter(stem, text)


def _parse_chapter(stem: str, text: str) -> EvalChapter:
    """Replicate benchmark ``parse_chapter`` semantics (spec §4 step 1)."""
    lines = text.splitlines()
    first_line = lines[0] if lines else ""
    title = first_line[2:].strip() if first_line.startswith("# ") else None
    return EvalChapter(stem=stem, title=title, text=text, word_count=len(text.split()))


def _build_manifest(raw: dict[str, Any], chapters: list[EvalChapter]) -> EvalCorpusManifest:
    payload: dict[str, Any] = {key: raw[key] for key in _SCALAR_KEYS if key in raw}
    payload["chapters"] = chapters
    try:
        return EvalCorpusManifest.model_validate(payload)
    except ValidationError as exc:
        raise CorpusSourceError(f"corpus.yaml: invalid manifest ({exc})") from exc
