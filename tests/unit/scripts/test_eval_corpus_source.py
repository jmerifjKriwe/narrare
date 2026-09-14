"""Unit tests for the eval corpus source (spec 2026-09-14 §9 Slice 1).

Scope per spec: valid manifest; missing/empty genre → error; title/word_count
derivation (replicated ``parse_chapter`` semantics); default corpus root;
tolerance of unknown manifest keys (named-key reads only).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from scripts.evals.corpus_source import (
    DEFAULT_CORPUS_ROOT,
    CorpusSourceError,
    load_eval_corpus,
)

if TYPE_CHECKING:
    from pathlib import Path

VALID_MANIFEST = """\
name: eval-test-corpus
version: 1
language: de
genre: Literary Fiction
description: unknown top-level key the loader must tolerate
variants:
  - name: light
    registry: variants/light/errors.yaml
chapters: [ch-01, ch-02]
"""

CHAPTER_TITLED = "# Kapitel Eins\n\nDer Wald lag still im ersten Licht.\n"
CHAPTER_UNTITLED = "Kein Titel an dieser Stelle.\n\nDer Text folgt hier.\n"


def _write_corpus(root: Path, manifest: str, chapters: dict[str, str]) -> Path:
    (root / "clean" / "chapters").mkdir(parents=True)
    (root / "corpus.yaml").write_text(manifest, encoding="utf-8")
    for stem, text in chapters.items():
        (root / "clean" / "chapters" / f"{stem}.md").write_text(text, encoding="utf-8")
    return root


def _write_valid_corpus(root: Path) -> Path:
    return _write_corpus(root, VALID_MANIFEST, {"ch-01": CHAPTER_TITLED, "ch-02": CHAPTER_UNTITLED})


def test_load_eval_corpus_with_valid_manifest_returns_typed_corpus(tmp_path: Path) -> None:
    root = _write_valid_corpus(tmp_path)

    manifest = load_eval_corpus(root)

    assert manifest.name == "eval-test-corpus"
    assert manifest.version == 1
    assert manifest.language == "de"
    assert manifest.genre == "Literary Fiction"
    assert [chapter.stem for chapter in manifest.chapters] == ["ch-01", "ch-02"]


def test_load_eval_corpus_when_genre_missing_raises_error(tmp_path: Path) -> None:
    root = _write_valid_corpus(tmp_path)
    (root / "corpus.yaml").write_text(
        VALID_MANIFEST.replace("genre: Literary Fiction\n", ""), encoding="utf-8"
    )

    with pytest.raises(CorpusSourceError, match="genre"):
        load_eval_corpus(root)


def test_load_eval_corpus_when_genre_empty_raises_error(tmp_path: Path) -> None:
    root = _write_valid_corpus(tmp_path)
    (root / "corpus.yaml").write_text(
        VALID_MANIFEST.replace("genre: Literary Fiction", 'genre: ""'),
        encoding="utf-8",
    )

    with pytest.raises(CorpusSourceError, match="genre"):
        load_eval_corpus(root)


def test_load_eval_corpus_when_genre_not_a_string_raises_error(tmp_path: Path) -> None:
    root = _write_valid_corpus(tmp_path)
    (root / "corpus.yaml").write_text(
        VALID_MANIFEST.replace("genre: Literary Fiction", "genre: 42"),
        encoding="utf-8",
    )

    with pytest.raises(CorpusSourceError, match="genre"):
        load_eval_corpus(root)


def test_load_eval_corpus_derives_title_and_word_count(tmp_path: Path) -> None:
    root = _write_valid_corpus(tmp_path)

    manifest = load_eval_corpus(root)

    titled, untitled = manifest.chapters
    assert titled.title == "Kapitel Eins"
    assert titled.text == CHAPTER_TITLED
    assert titled.word_count == len(CHAPTER_TITLED.split())
    assert untitled.title is None
    assert untitled.word_count == len(CHAPTER_UNTITLED.split())


def test_load_eval_corpus_when_chapter_file_missing_raises_error(tmp_path: Path) -> None:
    manifest = VALID_MANIFEST.replace("chapters: [ch-01, ch-02]", "chapters: [ch-99]")
    _write_corpus(tmp_path, manifest, {"ch-01": CHAPTER_TITLED})

    with pytest.raises(CorpusSourceError, match="ch-99"):
        load_eval_corpus(tmp_path)


def test_load_eval_corpus_when_chapters_list_empty_raises_error(tmp_path: Path) -> None:
    manifest = VALID_MANIFEST.replace("chapters: [ch-01, ch-02]", "chapters: []")
    _write_corpus(tmp_path, manifest, {"ch-01": CHAPTER_TITLED})

    with pytest.raises(CorpusSourceError, match="chapters"):
        load_eval_corpus(tmp_path)


def test_default_corpus_root_points_at_benchmark_corpus() -> None:
    assert DEFAULT_CORPUS_ROOT.name == "corpus"
    assert DEFAULT_CORPUS_ROOT.parent.name == "benchmark"
    assert (DEFAULT_CORPUS_ROOT / "corpus.yaml").is_file()


def test_load_eval_corpus_from_real_manifest_carries_genre() -> None:
    """Tolerance proof: the real corpus.yaml (with unknown keys) loads typed."""
    manifest = load_eval_corpus(DEFAULT_CORPUS_ROOT)

    assert manifest.genre == "Literary Fiction"
    assert manifest.language == "de"
    assert len(manifest.chapters) == 12
    assert manifest.chapters[0].stem == "ch-01"
    assert all(chapter.word_count > 0 for chapter in manifest.chapters)
