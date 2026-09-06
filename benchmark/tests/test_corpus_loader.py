"""Unit tests for ``benchmark.corpus_loader`` — corpus materialization.

The committed corpus (``benchmark/corpus/``) is committed, read-only fixture
data and is loaded directly; drift scenarios operate on tmp copies with
surgically mutated registries/manifests/chapter files. Gates pinned here:
chapter↔disk match, L09 chapter-scoped injection (the anchor legitimately
recurs in ch-10/11/12), X07+L06 disjoint anchors in one chapter, G2
exactly-once pre-flight, G3 replacement absence, manifest ``chapters_touched``
equality, and the word corridor as a WARN-level (non-fatal) finding. Rider
sources: plan Task 5 + ``benchmark/corpus/README.md`` gate catalogue.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from functools import lru_cache
from pathlib import Path
from shutil import copytree
from typing import Any, Final, cast

import pytest

from benchmark.corpus_loader import (
    Corpus,
    CorpusDriftError,
    CorpusError,
    ErrorSpec,
    PartialDate,
    load_corpus,
)

CORPUS_ROOT: Final[Path] = Path(__file__).resolve().parents[1] / "corpus"


@lru_cache(maxsize=1)
def real_corpus() -> Corpus:
    return load_corpus(CORPUS_ROOT)


def corpus_copy(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    copytree(CORPUS_ROOT, root)
    return root


def mutate(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"mutation anchor absent in {path.name}: {old!r}"
    path.write_text(text.replace(old, new), encoding="utf-8")


def chapters_by_stem(corpus: Corpus, variant: str) -> dict[str, str]:
    return {chapter.stem: chapter.text for chapter in corpus.chapters(variant)}


class TestCleanLoad:
    def test_clean_loads_twelve_chapters_in_corpus_order(self) -> None:
        corpus = real_corpus()

        chapters = corpus.chapters("clean")

        assert [c.stem for c in chapters] == [f"ch-{i:02d}" for i in range(1, 13)]
        first = chapters[0]
        assert first.title == "Ein Abend im Mai"
        assert first.text.startswith("# Ein Abend im Mai")  # text stays as-is
        assert first.word_count == len(first.text.split())

    def test_clean_chapters_are_read_as_is(self) -> None:
        corpus = real_corpus()

        chapter = next(c for c in corpus.chapters("clean") if c.stem == "ch-08")

        assert chapter.text == (CORPUS_ROOT / "clean/chapters/ch-08.md").read_text(encoding="utf-8")

    def test_real_corpus_raises_no_corridor_warnings(self) -> None:
        assert real_corpus().warnings == ()

    def test_corridor_violation_is_warning_not_error(self, tmp_path: Path) -> None:
        root = corpus_copy(tmp_path)
        # Add a NEW short chapter (registered in corpus.yaml) — overwriting an
        # existing chapter would break the variant registries' anchors in it.
        (root / "clean/chapters/ch-13.md").write_text(
            "# Kurz\n\nSechs Worte in diesem Kapiteltext.\n", encoding="utf-8"
        )
        mutate(root / "corpus.yaml", "ch-11, ch-12]", "ch-11, ch-12, ch-13]")

        corpus = load_corpus(root)

        corridor = [w for w in corpus.warnings if w.code == "word_corridor"]
        assert len(corridor) == 1
        assert "ch-13" in corridor[0].detail


class TestVariantApplication:
    def test_light_applies_all_ten_errors_chapter_scoped(self) -> None:
        corpus = real_corpus()

        specs = corpus.errors("light")
        variant = chapters_by_stem(corpus, "light")

        assert len(specs) == 10
        assert len(corpus.chapters("light")) == 12  # full corpus, not only touched chapters
        for spec in specs:  # all light errors are disjoint: replacement ≠ anchor superset
            assert spec.replacement in variant[spec.chapter], spec.id
            assert spec.anchor not in variant[spec.chapter], spec.id

    def test_variant_leaves_untouched_chapters_identical_to_clean(self) -> None:
        corpus = real_corpus()
        touched = {spec.chapter for spec in corpus.errors("light")}

        for chapter in corpus.chapters("light"):
            clean_text = next(c.text for c in corpus.chapters("clean") if c.stem == chapter.stem)
            if chapter.stem not in touched:
                assert chapter.text == clean_text, chapter.stem

    def test_l09_applies_only_in_its_own_chapter(self) -> None:
        corpus = real_corpus()

        variant = chapters_by_stem(corpus, "light")

        # L09 (chapter: ch-08, anchor: "einundvierzig Jahre") — the anchor
        # legitimately recurs in ch-10/11/12 and must stay untouched there.
        assert "vierundvierzig Jahre" in variant["ch-08"]
        assert "einundvierzig Jahre" not in variant["ch-08"]
        assert variant["ch-10"].count("einundvierzig Jahre") == 2
        assert variant["ch-11"].count("einundvierzig Jahre") == 1
        assert variant["ch-12"].count("einundvierzig Jahre") == 1
        for stem in ("ch-10", "ch-11", "ch-12"):
            assert "vierundvierzig Jahre" not in variant[stem], stem

    def test_complex_applies_disjoint_anchors_in_same_chapter(self) -> None:
        corpus = real_corpus()

        specs = corpus.errors("complex")
        variant = chapters_by_stem(corpus, "complex")
        x07 = next(s for s in specs if s.id == "X07")
        x01 = next(s for s in specs if s.id == "X01")
        x02 = next(s for s in specs if s.id == "X02")

        assert len(specs) == 8
        assert x07.error_class == "retcon"
        assert x07.replacement in variant["ch-12"]
        assert x07.anchor not in variant["ch-12"]
        # Two disjoint anchors in one chapter within THIS variant: X01+X02 (ch-09)
        for spec in (x01, x02):
            assert spec.replacement in variant[spec.chapter], spec.id

    def test_registries_do_not_collide_on_ch12_disjoint_anchors(self) -> None:
        corpus = real_corpus()

        light = chapters_by_stem(corpus, "light")
        complex_ = chapters_by_stem(corpus, "complex")

        # X07 (complex) and L06 (light) anchor disjoint fragments of the SAME
        # ch-12 passage (registry design note) — each variant applies only its
        # own error and leaves the other registry's anchor untouched.
        x07_anchor = "Der Zeichentisch stand am Fenster, wo er seit fünf Jahren stand"
        l06_anchor = "hier, in der Türkenstraße 41"
        assert l06_anchor not in light["ch-12"]  # L06 applied (light)
        assert x07_anchor in light["ch-12"]  # X07's anchor untouched (complex-only)
        assert x07_anchor not in complex_["ch-12"]  # X07 applied (complex)
        assert l06_anchor in complex_["ch-12"]  # L06's anchor untouched (light-only)

    def test_complex_applies_all_errors_including_nested_extensions(self) -> None:
        corpus = real_corpus()

        variant = chapters_by_stem(corpus, "complex")

        for spec in corpus.errors("complex"):
            assert spec.replacement in variant[spec.chapter], spec.id
        # Nested-extension errors (X01, X08): the replacement embeds the own
        # anchor, so the anchor text legitimately remains as its prefix — the
        # injected clause is what must appear.
        ch09_extension = "auf Rat von Anna übrigens, die sie aus gemeinsamen Studententagen kannte"
        assert ch09_extension in variant["ch-09"]  # X01
        assert (
            "auf die Rückseite hatte Peter eine zweite Zeile gravieren lassen" in variant["ch-11"]
        )  # X08

    def test_error_specs_expose_registry_fields(self) -> None:
        specs: dict[str, ErrorSpec] = {s.id: s for s in real_corpus().errors("light")}

        l09 = specs["L09"]
        assert l09.error_class == "attribute_value"
        assert l09.chapter == "ch-08"
        assert l09.ground_truth_ref == "F077"
        assert "teaching career length" in l09.description

    def test_unknown_variant_is_rejected(self) -> None:
        corpus = real_corpus()

        with pytest.raises(CorpusError, match="unknown variant"):
            corpus.chapters("bogus")
        with pytest.raises(CorpusError, match="unknown variant"):
            corpus.errors("bogus")


class TestReference:
    def test_reference_typed_views_expose_ids(self) -> None:
        reference = real_corpus().reference()

        anna = next(e for e in reference.persons if e.id == "p_anna_meyer")
        f132 = next(f for f in anna.facts if f.id == "F132")
        assert (f132.predicate, f132.value) == ("age_stated", "35")
        assert f132.source_chapters == (12,)
        f006 = next(f for f in anna.facts if f.id == "F006")
        assert f006.valid_from == PartialDate(2015)
        f005 = next(f for f in anna.facts if f.id == "F005")
        assert f005.valid_from is None
        assert f005.valid_to == PartialDate(2017, month=2)

        wolf = next(e for e in reference.persons if e.id == "p_alexander_wolf")
        assert wolf.aliases == ("Alex", "Sascha", "Alexander")

        r001 = next(r for r in reference.relations if r.id == "R001")
        assert (r001.subject, r001.predicate, r001.object) == (
            "p_anna_meyer",
            "sibling_of",
            "p_thomas_meyer",
        )
        assert r001.valid_from is None and r001.valid_to is None

        e009 = next(e for e in reference.events if e.id == "E009")
        assert e009.date == PartialDate(2018, month=5, day=26)
        assert "p_anna_meyer" in e009.participants

    def test_views_are_read_only(self) -> None:
        chapter = real_corpus().chapters("clean")[0]

        with pytest.raises(FrozenInstanceError):
            cast("Any", chapter).text = "mutated"


class TestDriftGates:
    def test_anchor_with_zero_occurrences_is_drift_error(self, tmp_path: Path) -> None:
        root = corpus_copy(tmp_path)
        mutate(
            root / "variants/light/errors.yaml",
            'anchor: "Anna war fünfunddreißig in diesem September"',
            'anchor: "Dieser Anker existiert nirgendwo"',
        )

        with pytest.raises(CorpusDriftError, match=r"L01.*0 times"):
            load_corpus(root)

    def test_anchor_with_two_occurrences_is_drift_error(self, tmp_path: Path) -> None:
        root = corpus_copy(tmp_path)
        # L09's anchor occurs exactly twice in ch-10 (real recurrence data);
        # the manifest is updated too so ONLY the G2 gate fires.
        mutate(
            root / "variants/light/errors.yaml",
            'chapter: ch-08\n    anchor: "einundvierzig Jahre"',
            'chapter: ch-10\n    anchor: "einundvierzig Jahre"',
        )
        mutate(
            root / "variants/light/manifest.yaml",
            "ch-08, ch-09, ch-11",
            "ch-08, ch-09, ch-10, ch-11",
        )

        with pytest.raises(CorpusDriftError, match=r"L09.*2 times"):
            load_corpus(root)

    def test_manifest_chapters_touched_mismatch_is_hard_error(self, tmp_path: Path) -> None:
        root = corpus_copy(tmp_path)
        mutate(
            root / "variants/light/manifest.yaml",
            "ch-04, ch-06, ch-08",
            "ch-04, ch-08",
        )

        with pytest.raises(CorpusError, match=r"chapters_touched.*ch-06"):
            load_corpus(root)


class TestChapterDiskMatch:
    def test_missing_chapter_file_is_hard_error(self, tmp_path: Path) -> None:
        root = corpus_copy(tmp_path)
        (root / "clean/chapters/ch-07.md").unlink()

        with pytest.raises(CorpusError, match="ch-07"):
            load_corpus(root)

    def test_unlisted_chapter_file_is_hard_error(self, tmp_path: Path) -> None:
        root = corpus_copy(tmp_path)
        (root / "clean/chapters/ch-13.md").write_text("# Extra\n\nText.\n", encoding="utf-8")

        with pytest.raises(CorpusError, match="ch-13"):
            load_corpus(root)
