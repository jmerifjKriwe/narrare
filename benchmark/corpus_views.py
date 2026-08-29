"""Typed corpus/reference views, their YAML parsing, and corpus error types.

The read-only dataclasses here mirror the committed corpus shapes
(``benchmark/corpus/README.md``): reference entities/relations/events with
their fact ids, materialized chapters, and variant error specs (``class`` is
a Python keyword → ``error_class``). The shape guards narrow the ``object``
values produced by ``yaml.safe_load`` and fail with precise
``<file>.<key>`` paths; the load/validation GATES themselves (G2/G3,
manifest, disk match, corridor) live in ``benchmark.corpus_loader``.

All views are frozen; sequence fields are tuples.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast


class CorpusError(RuntimeError):
    """Hard corpus/registry inconsistency; load-time validation failed."""


class CorpusDriftError(CorpusError):
    """Materialization drift: an anchor/replacement gate (G2/G3) failed."""


# ---------------------------------------------------------------------------
# Typed read-only views
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PartialDate:
    """YAML ``{year, month?, day?}`` — precision as the prose states it."""

    year: int
    month: int | None = None
    day: int | None = None


@dataclass(frozen=True)
class Fact:
    """Entity fact with its reference id (F*), value, and optional interval."""

    id: str
    predicate: str
    value: str
    valid_from: PartialDate | None
    valid_to: PartialDate | None
    source_chapters: tuple[int, ...]


@dataclass(frozen=True)
class Entity:
    """Person/place/object with its facts (same facts shape per README)."""

    id: str
    name: str
    aliases: tuple[str, ...]
    facts: tuple[Fact, ...]


@dataclass(frozen=True)
class Relation:
    """Directed subject→object relation with its reference id (R*)."""

    id: str
    subject: str
    predicate: str
    object: str
    valid_from: PartialDate | None
    valid_to: PartialDate | None
    source_chapters: tuple[int, ...]


@dataclass(frozen=True)
class Event:
    """Dated event with its reference id (E*) and participant entity ids."""

    id: str
    name: str
    date: PartialDate
    participants: tuple[str, ...]
    location: str
    source_chapters: tuple[int, ...]


@dataclass(frozen=True)
class Reference:
    """Typed read-only ground truth for the CLEAN corpus."""

    persons: tuple[Entity, ...]
    places: tuple[Entity, ...]
    objects: tuple[Entity, ...]
    relations: tuple[Relation, ...]
    events: tuple[Event, ...]


@dataclass(frozen=True)
class Chapter:
    """Materialized chapter: text as-is, derived title and word count."""

    stem: str
    title: str | None
    text: str
    word_count: int


@dataclass(frozen=True)
class ErrorSpec:
    """Registry error entry (``class`` is a keyword → ``error_class``)."""

    id: str
    error_class: str
    chapter: str
    anchor: str
    replacement: str
    ground_truth_ref: str
    description: str


# ---------------------------------------------------------------------------
# YAML shape guards (narrow ``object`` from safe_load; precise failure paths)
# ---------------------------------------------------------------------------


def _req_str(raw: dict[str, object], key: str, where: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise CorpusError(f"{where}: key {key!r} must be a non-empty string, got {value!r}")
    return value


def _int_field(raw: dict[str, object], key: str, where: str, *, required: bool) -> int | None:
    value = raw.get(key)
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise CorpusError(f"{where}: key {key!r} must be an int, got {value!r}")
    return value


def str_tuple(raw: dict[str, object], key: str, where: str) -> tuple[str, ...]:
    """Read an optional YAML string list as a tuple; absent means empty."""
    value = raw.get(key)
    if value is None:
        return ()
    if not isinstance(value, list):
        raise CorpusError(f"{where}: key {key!r} must be a list of strings, got {value!r}")
    items: list[str] = []
    for item in cast("list[object]", value):
        if not isinstance(item, str) or not item:
            raise CorpusError(f"{where}: key {key!r} must hold non-empty strings, got {value!r}")
        items.append(item)
    return tuple(items)


def _int_tuple(raw: dict[str, object], key: str, where: str) -> tuple[int, ...]:
    value = raw.get(key)
    if not isinstance(value, list):
        raise CorpusError(f"{where}: key {key!r} must be a list of ints, got {value!r}")
    items: list[int] = []
    for item in cast("list[object]", value):
        if isinstance(item, bool) or not isinstance(item, int):
            raise CorpusError(f"{where}: key {key!r} must hold ints, got {value!r}")
        items.append(item)
    return tuple(items)


def as_mapping(data: object, label: str) -> dict[str, object]:
    """Narrow a raw YAML value to a mapping or fail naming ``label``."""
    if not isinstance(data, dict):
        raise CorpusError(f"{label}: top level must be a mapping, got {type(data).__name__}")
    return cast("dict[str, object]", data)


def mapping_entries(data: object, label: str) -> list[dict[str, object]]:
    """Narrow a YAML list of mappings; an absent value is an empty list."""
    if data is None:
        return []
    if not isinstance(data, list):
        raise CorpusError(f"{label}: must be a list, got {type(data).__name__}")
    return [as_mapping(item, label) for item in cast("list[object]", data)]


def _opt_date(raw: dict[str, object], key: str, where: str) -> PartialDate | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise CorpusError(f"{where}: key {key!r} must be a date mapping, got {value!r}")
    date = cast("dict[str, object]", value)
    return PartialDate(
        year=_int_field(date, "year", where, required=True) or 0,
        month=_int_field(date, "month", where, required=False),
        day=_int_field(date, "day", where, required=False),
    )


# ---------------------------------------------------------------------------
# Parsing into the typed views
# ---------------------------------------------------------------------------


def _fact(raw: dict[str, object], where: str) -> Fact:
    return Fact(
        id=_req_str(raw, "id", where),
        predicate=_req_str(raw, "predicate", where),
        value=_req_str(raw, "value", where),
        valid_from=_opt_date(raw, "valid_from", where),
        valid_to=_opt_date(raw, "valid_to", where),
        source_chapters=_int_tuple(raw, "source_chapters", where),
    )


def _entity(raw: dict[str, object], where: str) -> Entity:
    facts = mapping_entries(raw.get("facts"), f"{where}: facts")
    return Entity(
        id=_req_str(raw, "id", where),
        name=_req_str(raw, "name", where),
        aliases=str_tuple(raw, "aliases", where),
        facts=tuple(_fact(entry, f"{where}.facts[{index}]") for index, entry in enumerate(facts)),
    )


def _relation(raw: dict[str, object], where: str) -> Relation:
    return Relation(
        id=_req_str(raw, "id", where),
        subject=_req_str(raw, "subject", where),
        predicate=_req_str(raw, "predicate", where),
        object=_req_str(raw, "object", where),
        valid_from=_opt_date(raw, "valid_from", where),
        valid_to=_opt_date(raw, "valid_to", where),
        source_chapters=_int_tuple(raw, "source_chapters", where),
    )


def _event(raw: dict[str, object], where: str) -> Event:
    date = _opt_date(raw, "date", where)
    if date is None:
        raise CorpusError(f"{where}: key 'date' is required")
    return Event(
        id=_req_str(raw, "id", where),
        name=_req_str(raw, "name", where),
        date=date,
        participants=str_tuple(raw, "participants", where),
        location=_req_str(raw, "location", where),
        source_chapters=_int_tuple(raw, "source_chapters", where),
    )


def parse_reference(entities: object, relations: object, events: object) -> Reference:
    """Parse the three raw reference YAML documents into typed views."""
    persons = as_mapping(entities, "reference/entities.yaml")
    return Reference(
        persons=tuple(
            _entity(entry, f"entities.yaml:persons[{index}]")
            for index, entry in enumerate(
                mapping_entries(persons.get("persons"), "entities.yaml: persons")
            )
        ),
        places=tuple(
            _entity(entry, f"entities.yaml:places[{index}]")
            for index, entry in enumerate(
                mapping_entries(persons.get("places"), "entities.yaml: places")
            )
        ),
        objects=tuple(
            _entity(entry, f"entities.yaml:objects[{index}]")
            for index, entry in enumerate(
                mapping_entries(persons.get("objects"), "entities.yaml: objects")
            )
        ),
        relations=tuple(
            _relation(entry, f"relations.yaml[{index}]")
            for index, entry in enumerate(mapping_entries(relations, "relations.yaml"))
        ),
        events=tuple(
            _event(entry, f"events.yaml[{index}]")
            for index, entry in enumerate(mapping_entries(events, "events.yaml"))
        ),
    )


def parse_errors(raw: object, registry_rel: str) -> tuple[ErrorSpec, ...]:
    """Parse a variant registry's ``errors`` list into typed specs."""
    return tuple(
        _error_spec(entry, f"{registry_rel}[{index}]")
        for index, entry in enumerate(mapping_entries(raw, f"{registry_rel}: errors"))
    )


def _error_spec(raw: dict[str, object], where: str) -> ErrorSpec:
    return ErrorSpec(
        id=_req_str(raw, "id", where),
        error_class=_req_str(raw, "class", where),
        chapter=_req_str(raw, "chapter", where),
        anchor=_req_str(raw, "anchor", where),
        replacement=_req_str(raw, "replacement", where),
        ground_truth_ref=_req_str(raw, "ground_truth_ref", where),
        description=_req_str(raw, "description", where),
    )


def parse_chapter(stem: str, text: str) -> Chapter:
    """Build the read-only chapter view: text as-is, derived title/word count."""
    lines = text.splitlines()
    first_line = lines[0] if lines else ""
    title = first_line[2:].strip() if first_line.startswith("# ") else None
    return Chapter(stem=stem, title=title, text=text, word_count=len(text.split()))
