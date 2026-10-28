"""The bundled demo corpus as the WP's golden fixture.

Everything the shipping demos are must hold here: all three parse into a
complete novel (chapters, entities, valid types, resolvable edges), and the
engine's determinism survives real prose — parse → serialize → parse →
serialize is byte-identical, so a demo exported twice, or imported and
re-exported, cannot drift.
"""

from app.kernel.contracts.models import ENTITY_TYPES
from app.kernel.interchange import ArchiveTree, parse_archive, serialize_archive
from app.kernel.interchange.demos import DEMOS, demo_tree

# The corpus facts the manifest pins: title and language must match the
# bundled metadata.json, and the counts are the ported v1 stats.
EXPECTED = {
    "im-stillen-wald": {"title": "Im Stillen Wald", "language": "de", "chapters": 2, "entities": 6},
    "dead-signal": {"title": "Dead Signal", "language": "en", "chapters": 3, "entities": 8},
    "echoes-of-the-thornwall": {
        "title": "Echoes of the Thornwall",
        "language": "en",
        "chapters": 4,
        "entities": 16,
    },
}


def test_every_demo_parses() -> None:
    assert [info.slug for info in DEMOS] == [
        "im-stillen-wald",
        "dead-signal",
        "echoes-of-the-thornwall",
    ]
    for info in DEMOS:
        expected = EXPECTED[info.slug]
        assert info.title == expected["title"]
        assert info.language == expected["language"]
        archive = parse_archive(demo_tree(info.slug))
        assert archive.title == expected["title"]
        assert archive.language == expected["language"]
        assert archive.author, "a demo without an author hides the porting source"
        assert len(archive.chapters) == expected["chapters"]
        assert len(archive.entities) == expected["entities"]
        assert archive.relations, "a demo without edges loses the v1 relationship map"
        assert all(entity.type in ENTITY_TYPES for entity in archive.entities)
        names = [entity.name.casefold() for entity in archive.entities]
        assert len(set(names)) == len(names), "duplicate entity names"
        for edge in archive.relations:
            assert edge.from_name.casefold() in names, edge
            assert edge.to_name.casefold() in names, edge


def test_demo_golden_round_trip_is_byte_identical() -> None:
    for info in DEMOS:
        first = serialize_archive(parse_archive(demo_tree(info.slug)))
        second = serialize_archive(parse_archive(ArchiveTree(first)))
        assert second == first
