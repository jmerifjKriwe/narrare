"""The bundled demo corpus as the WP's golden fixture.

Everything the shipping demos are must hold here: all three parse into a
complete novel (chapters, entities, valid types, resolvable edges), the
engine's determinism survives real prose — parse → serialize reproduces the
bundled bytes exactly, so a hand edit of any bundled file turns the gate red —
and the setup page's picker manifest mirrors this one.
"""

import re
from pathlib import Path

from app.kernel.contracts.models import ENTITY_TYPES
from app.kernel.interchange import parse_archive, serialize_archive
from app.kernel.interchange.demos import DEMOS, DemoInfo, demo_tree

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
    """The corpus-relative golden gate: what the engine produces from a demo is
    the bundled bytes themselves. A hand edit of any bundled file — a key
    reordered, a blank line added, a file renamed — turns this red."""
    for info in DEMOS:
        tree = demo_tree(info.slug)
        bundled = {"metadata.json", *tree.chapter_names(), *tree.kb_names()}
        files = serialize_archive(parse_archive(tree))
        assert set(files) == bundled
        for name, data in files.items():
            assert tree.read_bytes(name) == data, f"{info.slug}/{name} is not a format fixed point"


def test_web_manifest_matches_the_python_manifest() -> None:
    """The picker's TS constant in `SetupPage.tsx` mirrors the kernel manifest:
    same slugs, same titles, same languages, same order. A demo added to one
    side and not the other — or renamed, retitled, reordered — is red here."""
    page = (
        Path(__file__).parents[2] / "capabilities" / "setup" / "web" / "SetupPage.tsx"
    ).read_text(encoding="utf-8")
    entries = re.findall(
        r'\{\s*slug:\s*"([^"]+)"\s*,\s*title:\s*"([^"]+)"\s*,\s*language:\s*"([^"]+)"',
        page,
    )
    web = [DemoInfo(slug=slug, title=title, language=language) for slug, title, language in entries]
    assert web == list(DEMOS)
