"""The setup page's picker manifest mirrors the kernel's — and the truth.

The TS `DEMOS` constant in `SetupPage.tsx` and the kernel's
`app/kernel/interchange/demos.py` must carry the same demos in the same
order (same slugs, titles, languages), and every card's chapter/entity
counts must equal the bundled archive's real counts — a card cannot claim
five chapters for a four-chapter demo. This suite owns the check because it
is about this capability's page; depending on the kernel is the allowed
direction, the reverse never is.
"""

import re
from pathlib import Path

from app.kernel.interchange import parse_archive
from app.kernel.interchange.demos import DEMOS, DemoInfo, demo_tree

PAGE = Path(__file__).parents[2] / "setup" / "web" / "SetupPage.tsx"

ENTRY = re.compile(
    r'\{\s*slug:\s*"([^"]+)"\s*,\s*title:\s*"([^"]+)"\s*,\s*language:\s*"([^"]+)"'
    r"\s*,\s*chapters:\s*(\d+)\s*,\s*entities:\s*(\d+)\s*,?\s*\}"
)


def web_manifest() -> list[tuple[str, str, str, int, int]]:
    """The picker's entries as (slug, title, language, chapters, entities)."""
    return [
        (slug, title, language, int(chapters), int(entities))
        for slug, title, language, chapters, entities in ENTRY.findall(
            PAGE.read_text(encoding="utf-8")
        )
    ]


def test_web_manifest_matches_the_python_manifest() -> None:
    web = [
        DemoInfo(slug=slug, title=title, language=language)
        for slug, title, language, _chapters, _entities in web_manifest()
    ]
    assert web == list(DEMOS)


def test_web_manifest_counts_match_the_bundled_archives() -> None:
    for slug, _title, _language, chapters, entities in web_manifest():
        archive = parse_archive(demo_tree(slug))
        assert chapters == len(archive.chapters), f"{slug}: card says {chapters} chapters"
        assert entities == len(archive.entities), f"{slug}: card says {entities} entities"
