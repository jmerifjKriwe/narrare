"""Corpus materializer — loads the benchmark corpus and materializes variants.

Loads ``corpus.yaml``, the clean chapters, the reference YAMLs, and the variant
registries, and materializes chapters in memory: clean chapters are read as-is;
variant chapters are the clean text with each registered error applied as an
exact find/replace scoped to the error's OWN chapter (registry ``chapter``
field — never corpus-wide; anchors legitimately recur across chapters, e.g. L09
"einundvierzig Jahre" in ch-08/10/11/12). Errors apply in registry order; every
gate runs against the working text at apply time, so disjoint anchors in one
chapter (X07+X01/X02 in ch-12/ch-09) apply cleanly in any order.

Hard gates (``CorpusError``/``CorpusDriftError``, raised at load):
- corpus.yaml chapter list matches the files on disk (both directions);
- per variant, ``manifest.yaml`` ``chapters_touched`` equals the registry-
  derived chapter set;
- G2 pre-flight: each anchor occurs EXACTLY ONCE in its chapter at apply time
  (runtime re-run of the corpus gate G2 — 0 or >1 is corpus drift);
- G3: the replacement is absent from every clean chapter before applying;
- post-apply: the replacement is present in the chapter text (the anchor is
  NOT required to vanish: nested-extension errors X01/X08 embed their own
  anchor as the replacement's prefix).

Warnings (non-fatal, exposed to callers for run-artifact reporting):
- word corridor: clean-chapter word counts outside 2400-3600 (gate G5) are
  collected as ``CorpusWarning(code="word_corridor", ...)``; the runner
  reports them.

This module is the single public import surface (typed views are re-exported
from ``benchmark.corpus_views``): ``from benchmark.corpus_loader import
load_corpus, Corpus, ...``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, cast

import yaml

from benchmark.corpus_views import (
    Chapter,
    CorpusDriftError,
    CorpusError,
    Entity,
    ErrorSpec,
    Event,
    Fact,
    PartialDate,
    Reference,
    Relation,
    as_mapping,
    mapping_entries,
    parse_chapter,
    parse_errors,
    parse_reference,
    str_tuple,
)

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "CORRIDOR_MAX_WORDS",
    "CORRIDOR_MIN_WORDS",
    "Chapter",
    "Corpus",
    "CorpusDriftError",
    "CorpusError",
    "CorpusWarning",
    "Entity",
    "ErrorSpec",
    "Event",
    "Fact",
    "PartialDate",
    "Reference",
    "Relation",
    "load_corpus",
]

CORRIDOR_MIN_WORDS: Final[int] = 2400
CORRIDOR_MAX_WORDS: Final[int] = 3600


@dataclass(frozen=True)
class CorpusWarning:
    """Non-fatal load finding the runner reports (e.g. word corridor)."""

    code: str
    detail: str


@dataclass(frozen=True)
class _Variant:
    name: str
    errors: tuple[ErrorSpec, ...]
    chapters: tuple[Chapter, ...]


class Corpus:
    """Loaded corpus: materialized chapters, typed reference, registries."""

    def __init__(
        self,
        stems: tuple[str, ...],
        clean: tuple[Chapter, ...],
        variants: tuple[_Variant, ...],
        reference: Reference,
        warnings: tuple[CorpusWarning, ...],
    ) -> None:
        self._stems = stems
        self._clean = clean
        self._variants = variants
        self._reference = reference
        self.warnings = warnings

    @property
    def stems(self) -> tuple[str, ...]:
        return self._stems

    @property
    def variant_names(self) -> tuple[str, ...]:
        return tuple(variant.name for variant in self._variants)

    def chapters(self, variant: str = "clean") -> tuple[Chapter, ...]:
        """Materialized chapters in corpus.yaml order (read-only view)."""
        if variant == "clean":
            return self._clean
        return self._variant(variant).chapters

    def errors(self, variant: str) -> tuple[ErrorSpec, ...]:
        """Registry error specs for a variant, in registry order."""
        return self._variant(variant).errors

    def reference(self) -> Reference:
        """Typed ground truth for the clean corpus."""
        return self._reference

    def _variant(self, name: str) -> _Variant:
        for variant in self._variants:
            if variant.name == name:
                return variant
        raise CorpusError(f"unknown variant {name!r} (known: {', '.join(self.variant_names)})")


def load_corpus(root: Path) -> Corpus:
    """Load and fully validate the corpus rooted at ``root`` (holds corpus.yaml)."""
    config = as_mapping(_load_yaml(root / "corpus.yaml", "corpus.yaml"), "corpus.yaml")
    stems = _chapter_stems(config)
    _validate_chapters_on_disk(root, stems)
    clean_texts = {stem: _read_chapter(root, stem) for stem in stems}
    clean = tuple(parse_chapter(stem, clean_texts[stem]) for stem in stems)
    variants = tuple(
        _load_variant(root, stems, clean_texts, spec)
        for spec in mapping_entries(config.get("variants"), "corpus.yaml: variants")
    )
    return Corpus(
        stems=stems,
        clean=clean,
        variants=variants,
        reference=_load_reference(root, config),
        warnings=_corridor_warnings(clean),
    )


def _load_yaml(path: Path, label: str) -> object:
    try:
        loaded: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CorpusError(f"{label}: invalid YAML ({exc})") from exc
    if loaded is None:
        raise CorpusError(f"{label}: empty YAML document")
    return loaded


def _chapter_stems(config: dict[str, object]) -> tuple[str, ...]:
    stems = str_tuple(config, "chapters", "corpus.yaml")
    if not stems:
        raise CorpusError("corpus.yaml: 'chapters' must be a non-empty list of stems")
    return stems


def _validate_chapters_on_disk(root: Path, stems: tuple[str, ...]) -> None:
    expected = {f"{stem}.md" for stem in stems}
    actual = {path.name for path in (root / "clean" / "chapters").glob("*.md")}
    missing = sorted(expected - actual)
    unlisted = sorted(actual - expected)
    if missing:
        raise CorpusError(f"clean/chapters: corpus.yaml chapters missing on disk: {missing}")
    if unlisted:
        raise CorpusError(f"clean/chapters: files on disk not listed in corpus.yaml: {unlisted}")


def _read_chapter(root: Path, stem: str) -> str:
    return (root / "clean" / "chapters" / f"{stem}.md").read_text(encoding="utf-8")


def _corridor_warnings(clean: tuple[Chapter, ...]) -> tuple[CorpusWarning, ...]:
    return tuple(
        CorpusWarning(
            code="word_corridor",
            detail=(
                f"{chapter.stem}: {chapter.word_count} words outside "
                f"{CORRIDOR_MIN_WORDS}-{CORRIDOR_MAX_WORDS}"
            ),
        )
        for chapter in clean
        if not CORRIDOR_MIN_WORDS <= chapter.word_count <= CORRIDOR_MAX_WORDS
    )


def _load_reference(root: Path, config: dict[str, object]) -> Reference:
    paths = config.get("reference")
    if not isinstance(paths, dict):
        raise CorpusError("corpus.yaml: 'reference' must be a mapping")
    ref_paths = cast("dict[str, object]", paths)

    def load(kind: str) -> object:
        rel = _req_str(ref_paths, kind, "corpus.yaml reference")
        return _load_yaml(root / rel, f"reference/{rel}")

    return parse_reference(load("entities"), load("relations"), load("events"))


def _req_str(raw: dict[str, object], key: str, where: str = "corpus.yaml") -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise CorpusError(f"{where}: key {key!r} must be a non-empty string, got {value!r}")
    return value


def _load_variant(
    root: Path,
    stems: tuple[str, ...],
    clean: dict[str, str],
    spec: dict[str, object],
) -> _Variant:
    name = _req_str(spec, "name", "corpus.yaml variants")
    registry_rel = _req_str(spec, "registry", "corpus.yaml variants")
    registry_path = root / registry_rel
    registry = as_mapping(_load_yaml(registry_path, registry_rel), registry_rel)
    base = _req_str(registry, "base", registry_rel)
    if base != "clean":
        raise CorpusError(f"{registry_rel}: unsupported base {base!r} (only 'clean')")
    errors = parse_errors(registry.get("errors"), registry_rel)
    _validate_manifest(registry_path, errors)
    texts = dict(clean)
    for error in errors:
        if error.chapter not in texts:
            raise CorpusError(
                f"{error.id}: registry chapter {error.chapter!r} is not a corpus chapter"
            )
        texts[error.chapter] = _apply_error(texts[error.chapter], error, clean)
    return _Variant(
        name=name,
        errors=errors,
        chapters=tuple(parse_chapter(stem, texts[stem]) for stem in stems),
    )


def _validate_manifest(registry_path: Path, errors: tuple[ErrorSpec, ...]) -> None:
    manifest_rel = f"{registry_path.parent.name}/manifest.yaml"
    manifest = as_mapping(
        _load_yaml(registry_path.parent / "manifest.yaml", manifest_rel), manifest_rel
    )
    derived = sorted({error.chapter for error in errors})
    listed = sorted(str_tuple(manifest, "chapters_touched", manifest_rel))
    if listed != derived:
        raise CorpusError(
            f"{manifest_rel}: chapters_touched {listed} != registry-derived {derived}"
        )


def _apply_error(text: str, error: ErrorSpec, clean: dict[str, str]) -> str:
    """Apply one error chapter-scoped under the G2/G3/post-apply gates."""
    count = text.count(error.anchor)
    if count != 1:
        raise CorpusDriftError(
            f"{error.id}: anchor occurs {count} times in {error.chapter} (exactly once required)"
        )
    polluted = sorted(stem for stem, clean_text in clean.items() if error.replacement in clean_text)
    if polluted:
        raise CorpusDriftError(
            f"{error.id}: replacement already present in clean chapters {polluted}"
        )
    applied = text.replace(error.anchor, error.replacement)
    if error.replacement not in applied:
        raise CorpusDriftError(f"{error.id}: replacement missing in {error.chapter} after apply")
    return applied
