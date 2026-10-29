"""The bundled demo corpus as the WP's golden fixture.

Everything the shipping demos are must hold here: all three parse into a
complete novel (chapters, entities, valid types, resolvable edges), and the
engine's determinism survives real prose — every bundled file is a byte
fixed point of the format, so the corpus cannot drift from the parser.
(The setup page's picker manifest is cross-checked against this one in the
setup capability's own suite.)
"""

from app.kernel.contracts.models import ENTITY_TYPES
from app.kernel.interchange import parse_archive, serialize_archive
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
    """The corpus-relative golden gate: every bundled file is a byte fixed
    point of the format — what the engine produces from a demo is exactly
    the bundled bytes. An edit that changes what the engine would write (a
    key reordered, a value-bearing line moved or dropped, a file renamed)
    turns this red; whitespace the format itself reproduces (an appended
    EOF newline) is by definition not drift."""
    for info in DEMOS:
        tree = demo_tree(info.slug)
        bundled = {"metadata.json", *tree.chapter_names(), *tree.kb_names()}
        files = serialize_archive(parse_archive(tree))
        assert set(files) == bundled
        for name, data in files.items():
            assert tree.read_bytes(name) == data, f"{info.slug}/{name} is not a format fixed point"
